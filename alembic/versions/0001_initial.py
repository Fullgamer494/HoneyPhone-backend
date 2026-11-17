"""Create P0 and planned P1 relational schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    enums = [
        postgresql.ENUM("LIVE", "DEMO", name="data_source", create_type=False),
        postgresql.ENUM("WIFI_SECURITY", "CAPTIVE_PORTAL", "DNS", "HTTPS", name="signal_kind", create_type=False),
        postgresql.ENUM("PASS", "ATTENTION", "UNKNOWN", "NOT_APPLICABLE", name="signal_outcome", create_type=False),
        postgresql.ENUM("NO_DISCREPANCIES", "ATTENTION_REQUIRED", "INCOMPLETE", name="overall_verdict", create_type=False),
        postgresql.ENUM("COMPLETED", "CANCELLED", name="check_run_status", create_type=False),
        postgresql.ENUM("RUNNING", "STOPPED", "INTERRUPTED", name="honeypot_state", create_type=False),
    ]
    for enum_type in enums: enum_type.create(bind, checkfirst=True)
    op.create_table("installations",
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(16), nullable=False, server_default="ANDROID"),
        sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("platform = 'ANDROID'", name="ck_installations_platform"),
        sa.CheckConstraint("length(app_version) > 0", name="ck_installations_app_version"),
        sa.CheckConstraint("last_seen_at >= first_seen_at", name="ck_installations_seen_order"))
    op.create_table("network_checks",
        sa.Column("check_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("installations.installation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", enums[0], nullable=False), sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("android_api_level", sa.SmallInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_status", enums[4], nullable=False), sa.Column("verdict", enums[3], nullable=False),
        sa.Column("has_attention", sa.Boolean(), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(app_version) > 0", name="ck_checks_app_version"),
        sa.CheckConstraint("android_api_level BETWEEN 29 AND 100", name="ck_checks_android_api_level"),
        sa.CheckConstraint("finished_at >= started_at", name="ck_checks_time_order"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_checks_payload_sha256"))
    op.create_table("check_signals",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("network_checks.check_id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", enums[1], nullable=False), sa.Column("outcome", enums[2], nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True), sa.UniqueConstraint("check_id", "kind", name="uq_check_signals_check_kind"),
        sa.CheckConstraint("reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_signals_reason_code"),
        sa.CheckConstraint("elapsed_ms BETWEEN 0 AND 300000", name="ck_signals_elapsed_ms"),
        sa.CheckConstraint("jsonb_typeof(evidence) = 'object'", name="ck_signals_evidence_object"),
        sa.CheckConstraint("(evidence - ARRAY['security_type','reported_by_os','validated','reason','elapsed_ms','probe_config_version']) = '{}'::jsonb", name="ck_signals_evidence_keys"),
        sa.CheckConstraint("octet_length(evidence::text) <= 2048", name="ck_signals_evidence_size"))
    op.create_table("honeypot_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("installations.installation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", enums[0], nullable=False), sa.Column("listen_port", sa.Integer(), nullable=False, server_default="8080"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", enums[5], nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("listen_port BETWEEN 1024 AND 65535", name="ck_honeypot_sessions_listen_port"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_honeypot_sessions_time_order"),
        sa.CheckConstraint("(state = 'RUNNING' AND ended_at IS NULL) OR (state IN ('STOPPED','INTERRUPTED') AND ended_at IS NOT NULL)", name="ck_honeypot_sessions_state_dates"))
    op.create_table("honeypot_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("honeypot_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_ip_masked", postgresql.CIDR(), nullable=False), sa.Column("http_method", sa.String(10), nullable=False),
        sa.Column("request_path", sa.String(256), nullable=False), sa.Column("user_agent_family", sa.String(16), nullable=True),
        sa.Column("content_length", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("response_code", sa.SmallInteger(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False), sa.UniqueConstraint("session_id", "event_id", name="uq_honeypot_events_session_event"),
        sa.CheckConstraint("http_method IN ('GET','HEAD','POST','OTHER')", name="ck_honeypot_events_method"),
        sa.CheckConstraint("request_path IN ('/','/admin','/login','/robots.txt','/other')", name="ck_honeypot_events_path"),
        sa.CheckConstraint("user_agent_family IS NULL OR user_agent_family IN ('BROWSER','SCANNER','OTHER','UNKNOWN')", name="ck_honeypot_events_user_agent_family"),
        sa.CheckConstraint("content_length BETWEEN 0 AND 2147483647", name="ck_honeypot_events_content_length"),
        sa.CheckConstraint("response_code BETWEEN 100 AND 599", name="ck_honeypot_events_response_code"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_honeypot_events_payload_sha256"),
        sa.CheckConstraint("((family(source_ip_masked) = 4 AND masklen(source_ip_masked) = 24) OR (family(source_ip_masked) = 6 AND masklen(source_ip_masked) = 64))", name="ck_honeypot_events_source_ip_mask"))
    op.create_index("idx_checks_install_time", "network_checks", ["installation_id", sa.text("started_at DESC"), sa.text("check_id DESC")])
    op.create_index("idx_checks_source_time", "network_checks", ["source", sa.text("started_at DESC"), sa.text("check_id DESC")])
    op.create_index("idx_sessions_install_time", "honeypot_sessions", ["installation_id", sa.text("started_at DESC"), sa.text("session_id DESC")])
    op.create_index("idx_events_session_time", "honeypot_events", ["session_id", sa.text("occurred_at DESC"), sa.text("event_id DESC")])

def downgrade() -> None:
    for name, table in [("idx_events_session_time", "honeypot_events"), ("idx_sessions_install_time", "honeypot_sessions"), ("idx_checks_source_time", "network_checks"), ("idx_checks_install_time", "network_checks")]: op.drop_index(name, table_name=table)
    for table in ("honeypot_events", "honeypot_sessions", "check_signals", "network_checks", "installations"): op.drop_table(table)
    for name in ("honeypot_state", "check_run_status", "overall_verdict", "signal_outcome", "signal_kind", "data_source"): postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
