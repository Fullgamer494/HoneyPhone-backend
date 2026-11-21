from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import CIDR, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from honeyphone.core.database import Base


class DataSource(StrEnum):
    LIVE = "LIVE"
    DEMO = "DEMO"


class SignalKind(StrEnum):
    WIFI_SECURITY = "WIFI_SECURITY"
    CAPTIVE_PORTAL = "CAPTIVE_PORTAL"
    DNS = "DNS"
    HTTPS = "HTTPS"


class SignalOutcome(StrEnum):
    PASS = "PASS"
    ATTENTION = "ATTENTION"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallVerdict(StrEnum):
    NO_DISCREPANCIES = "NO_DISCREPANCIES"
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


class RunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HoneypotState(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    INTERRUPTED = "INTERRUPTED"


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


class Installation(Base):
    __tablename__ = "installations"
    installation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="ANDROID", server_default="ANDROID")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    checks: Mapped[list["NetworkCheck"]] = relationship(back_populates="installation", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("platform = 'ANDROID'", name="ck_installations_platform"),
        CheckConstraint("length(app_version) > 0", name="ck_installations_app_version"),
        CheckConstraint("last_seen_at >= first_seen_at", name="ck_installations_seen_order"),
    )


class NetworkCheck(Base):
    __tablename__ = "network_checks"
    check_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    installation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("installations.installation_id", ondelete="CASCADE"), nullable=False)
    source: Mapped[DataSource] = mapped_column(Enum(DataSource, name="data_source", values_callable=enum_values, native_enum=True), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    android_api_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    run_status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="check_run_status", values_callable=enum_values, native_enum=True), nullable=False)
    verdict: Mapped[OverallVerdict] = mapped_column(Enum(OverallVerdict, name="overall_verdict", values_callable=enum_values, native_enum=True), nullable=False)
    has_attention: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    network_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    wifi_metrics: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    installation: Mapped[Installation] = relationship(back_populates="checks")
    signals: Mapped[list["CheckSignal"]] = relationship(back_populates="check", cascade="all, delete-orphan", order_by="CheckSignal.kind")
    __table_args__ = (
        CheckConstraint("length(app_version) > 0", name="ck_checks_app_version"),
        CheckConstraint("android_api_level BETWEEN 29 AND 100", name="ck_checks_android_api_level"),
        CheckConstraint("finished_at >= started_at", name="ck_checks_time_order"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_checks_payload_sha256"),
        CheckConstraint("network_label IS NULL OR (length(network_label) BETWEEN 1 AND 40 AND network_label = btrim(network_label) AND network_label !~ '[[:cntrl:]]')", name="ck_checks_label"),
        CheckConstraint("wifi_metrics IS NULL OR jsonb_typeof(wifi_metrics) = 'object'", name="ck_checks_metrics_object"),
        CheckConstraint("wifi_metrics IS NULL OR (wifi_metrics - ARRAY['rssi_dbm','frequency_mhz','wifi_standard','link_speed_mbps','tx_link_speed_mbps','rx_link_speed_mbps','internet_validated']) = '{}'::jsonb", name="ck_checks_metrics_keys"),
        CheckConstraint("wifi_metrics IS NULL OR octet_length(wifi_metrics::text) <= 1024", name="ck_checks_metrics_size"),
        Index("idx_checks_install_time", "installation_id", started_at.desc(), check_id.desc()),
        Index("idx_checks_source_time", "source", started_at.desc(), check_id.desc()),
    )


class CheckSignal(Base):
    __tablename__ = "check_signals"
    signal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    check_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("network_checks.check_id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[SignalKind] = mapped_column(Enum(SignalKind, name="signal_kind", values_callable=enum_values, native_enum=True), nullable=False)
    outcome: Mapped[SignalOutcome] = mapped_column(Enum(SignalOutcome, name="signal_outcome", values_callable=enum_values, native_enum=True), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check: Mapped[NetworkCheck] = relationship(back_populates="signals")
    __table_args__ = (
        UniqueConstraint("check_id", "kind", name="uq_check_signals_check_kind"),
        CheckConstraint("reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_signals_reason_code"),
        CheckConstraint("elapsed_ms BETWEEN 0 AND 300000", name="ck_signals_elapsed_ms"),
        CheckConstraint("jsonb_typeof(evidence) = 'object'", name="ck_signals_evidence_object"),
        CheckConstraint("(evidence - ARRAY['security_type','reported_by_os','validated','reason','elapsed_ms','probe_config_version']) = '{}'::jsonb", name="ck_signals_evidence_keys"),
        CheckConstraint("octet_length(evidence::text) <= 2048", name="ck_signals_evidence_size"),
    )


class HoneypotSession(Base):
    __tablename__ = "honeypot_sessions"
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    installation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("installations.installation_id", ondelete="CASCADE"), nullable=False)
    source: Mapped[DataSource] = mapped_column(Enum(DataSource, name="data_source", values_callable=enum_values, native_enum=True), nullable=False)
    listen_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8080, server_default="8080")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[HoneypotState] = mapped_column(Enum(HoneypotState, name="honeypot_state", values_callable=enum_values, native_enum=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    events: Mapped[list["HoneypotEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("listen_port BETWEEN 1024 AND 65535", name="ck_honeypot_sessions_listen_port"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_honeypot_sessions_time_order"),
        CheckConstraint("(state = 'RUNNING' AND ended_at IS NULL) OR (state IN ('STOPPED','INTERRUPTED') AND ended_at IS NOT NULL)", name="ck_honeypot_sessions_state_dates"),
        Index("idx_sessions_install_time", "installation_id", started_at.desc(), session_id.desc()),
    )


class HoneypotEvent(Base):
    __tablename__ = "honeypot_events"
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("honeypot_sessions.session_id", ondelete="CASCADE"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source_ip_masked: Mapped[str] = mapped_column(CIDR, nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    request_path: Mapped[str] = mapped_column(String(256), nullable=False)
    user_agent_family: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content_length: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    response_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    session: Mapped[HoneypotSession] = relationship(back_populates="events")
    __table_args__ = (
        UniqueConstraint("session_id", "event_id", name="uq_honeypot_events_session_event"),
        CheckConstraint("http_method IN ('GET','HEAD','POST','OTHER')", name="ck_honeypot_events_method"),
        CheckConstraint("request_path IN ('/','/admin','/login','/robots.txt','/other')", name="ck_honeypot_events_path"),
        CheckConstraint("user_agent_family IS NULL OR user_agent_family IN ('BROWSER','SCANNER','OTHER','UNKNOWN')", name="ck_honeypot_events_user_agent_family"),
        CheckConstraint("content_length BETWEEN 0 AND 2147483647", name="ck_honeypot_events_content_length"),
        CheckConstraint("response_code BETWEEN 100 AND 599", name="ck_honeypot_events_response_code"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_honeypot_events_payload_sha256"),
        CheckConstraint("((family(source_ip_masked) = 4 AND masklen(source_ip_masked) = 24) OR (family(source_ip_masked) = 6 AND masklen(source_ip_masked) = 64))", name="ck_honeypot_events_source_ip_mask"),
        Index("idx_events_session_time", "session_id", occurred_at.desc(), event_id.desc()),
    )
