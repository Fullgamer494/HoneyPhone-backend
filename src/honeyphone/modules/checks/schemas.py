from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from honeyphone.modules.checks.models import DataSource, OverallVerdict, RunStatus, SignalKind, SignalOutcome


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, from_attributes=True)


class ReasonCode(StrEnum):
    OS_SECURITY_REPORTED = "OS_SECURITY_REPORTED"
    OPEN_NETWORK = "OPEN_NETWORK"
    LEGACY_SECURITY = "LEGACY_SECURITY"
    OS_PORTAL_NOT_DETECTED = "OS_PORTAL_NOT_DETECTED"
    PORTAL_DETECTED = "PORTAL_DETECTED"
    FIELD_UNAVAILABLE = "FIELD_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NO_WIFI = "NO_WIFI"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NETWORK_CHANGED = "NETWORK_CHANGED"
    CANCELLED = "CANCELLED"
    DNS_MATCH = "DNS_MATCH"
    DNS_MISMATCH = "DNS_MISMATCH"
    REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    TLS_VALID = "TLS_VALID"
    TLS_INVALID = "TLS_INVALID"


class SignalEvidence(StrictModel):
    security_type: Literal["OPEN", "WEP", "PSK_UNSPECIFIED", "SAE", "OWE", "EAP", "EAP_WPA3", "WAPI", "PASSPOINT", "UNKNOWN"] = Field(default=None)
    reported_by_os: bool = Field(default=None)
    validated: bool = Field(default=None)
    reason: Literal["NOT_CONFIGURED", "PERMISSION_DENIED", "FIELD_UNAVAILABLE", "NO_WIFI", "NETWORK_CHANGED", "CANCELLED"] = Field(default=None)
    elapsed_ms: int = Field(default=None, ge=0, le=300000)
    probe_config_version: str = Field(default=None, min_length=1, max_length=32)


class CheckSignalCreate(StrictModel):
    signal_id: UUID
    kind: SignalKind
    outcome: SignalOutcome
    reason_code: ReasonCode
    evidence: SignalEvidence
    elapsed_ms: int | None = Field(default=None, ge=0, le=300000)



class WifiMetrics(StrictModel):
    """Snapshot of connection telemetry. Missing values remain null."""
    rssi_dbm: int | None = Field(default=None, strict=True, ge=-126, le=-1)
    frequency_mhz: int | None = Field(default=None, strict=True, ge=2400, le=71000)
    wifi_standard: Literal["LEGACY", "WIFI_4", "WIFI_5", "WIFI_6", "WIFI_7", "WIGIG", "UNKNOWN"] | None = None
    link_speed_mbps: int | None = Field(default=None, strict=True, ge=1, le=100000)
    tx_link_speed_mbps: int | None = Field(default=None, strict=True, ge=1, le=100000)
    rx_link_speed_mbps: int | None = Field(default=None, strict=True, ge=1, le=100000)
    internet_validated: bool | None = Field(default=None, strict=True)


class CheckCreate(StrictModel):
    check_id: UUID
    installation_id: UUID
    source: DataSource
    network_label: str | None = Field(default=None, min_length=1, max_length=40)
    wifi_metrics: WifiMetrics | None = None
    app_version: str = Field(min_length=1, max_length=32)
    android_api_level: int = Field(ge=29, le=100)
    started_at: datetime
    finished_at: datetime
    run_status: RunStatus
    signals: list[CheckSignalCreate] = Field(min_length=4, max_length=4)

    @field_validator("network_label")
    @classmethod
    def validate_label(cls, value):
        if value is None:
            return None
        if value != value.strip() or not all(c.isalnum() or c in " ._-" for c in value):
            raise ValueError("Etiqueta manual inválida: usa letras, números, espacios, punto, guion o guion bajo.")
        return value

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.finished_at < self.started_at:
            raise ValueError("finished_at debe ser igual o posterior a started_at.")
        expected = {kind.value for kind in SignalKind}
        kinds = [signal.kind for signal in self.signals]
        if len(set(kinds)) != 4 or {kind.value if isinstance(kind, SignalKind) else kind for kind in kinds} != expected:
            raise ValueError("Debe incluir exactamente una señal de cada tipo.")
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(set(signal_ids)) != len(signal_ids):
            raise ValueError("signal_id debe ser único dentro de la revisión.")
        for signal in self.signals:
            validate_signal(signal)
        if self.wifi_metrics is not None:
            if self.run_status == RunStatus.CANCELLED or any(s.reason_code in {"NO_WIFI", "NETWORK_CHANGED"} for s in self.signals):
                raise ValueError("Una lectura sin Wi-Fi o interrumpida no puede incluir métricas de conexión.")
            portal = next(s for s in self.signals if s.kind == "CAPTIVE_PORTAL")
            if portal.evidence.validated is not None and self.wifi_metrics.internet_validated is not None and portal.evidence.validated != self.wifi_metrics.internet_validated:
                raise ValueError("La validación de Internet debe ser consistente con la señal del sistema.")
        if self.run_status == RunStatus.CANCELLED and not any(s.reason_code in {"CANCELLED", "NETWORK_CHANGED"} for s in self.signals):
            raise ValueError("Una revisión cancelada debe identificar la señal interrumpida.")
        return self


_ALLOWED = {
    "WIFI_SECURITY": {"OS_SECURITY_REPORTED": "PASS", "OPEN_NETWORK": "ATTENTION", "LEGACY_SECURITY": "ATTENTION", "FIELD_UNAVAILABLE": "UNKNOWN", "PERMISSION_DENIED": "UNKNOWN", "NO_WIFI": "UNKNOWN", "NETWORK_CHANGED": "UNKNOWN", "CANCELLED": "UNKNOWN"},
    "CAPTIVE_PORTAL": {"OS_PORTAL_NOT_DETECTED": "PASS", "PORTAL_DETECTED": "UNKNOWN", "FIELD_UNAVAILABLE": "UNKNOWN", "PERMISSION_DENIED": "UNKNOWN", "NO_WIFI": "UNKNOWN", "NETWORK_CHANGED": "UNKNOWN", "CANCELLED": "UNKNOWN"},
    "DNS": {"DNS_MATCH": "PASS", "DNS_MISMATCH": "ATTENTION", "NOT_CONFIGURED": "UNKNOWN", "REFERENCE_UNAVAILABLE": "UNKNOWN", "TIMEOUT": "UNKNOWN", "NETWORK_ERROR": "UNKNOWN", "NETWORK_CHANGED": "UNKNOWN", "CANCELLED": "UNKNOWN"},
    "HTTPS": {"TLS_VALID": "PASS", "TLS_INVALID": "ATTENTION", "NOT_CONFIGURED": "UNKNOWN", "TIMEOUT": "UNKNOWN", "NETWORK_ERROR": "UNKNOWN", "NETWORK_CHANGED": "UNKNOWN", "CANCELLED": "UNKNOWN"},
}


def validate_signal(signal: CheckSignalCreate) -> None:
    kind = signal.kind.value if isinstance(signal.kind, SignalKind) else signal.kind
    outcome = signal.outcome.value if isinstance(signal.outcome, SignalOutcome) else signal.outcome
    reason = signal.reason_code.value if isinstance(signal.reason_code, ReasonCode) else signal.reason_code
    expected = _ALLOWED.get(kind, {}).get(reason)
    if expected is None or expected != outcome:
        raise ValueError(f"reason_code no permitido para {kind}/{outcome}.")
    evidence = signal.evidence.model_dump(exclude_none=True)
    allowed_by_kind = {
        "WIFI_SECURITY": {"security_type", "reported_by_os", "reason", "elapsed_ms"},
        "CAPTIVE_PORTAL": {"reported_by_os", "validated", "reason", "elapsed_ms"},
        "DNS": {"validated", "reason", "elapsed_ms", "probe_config_version"},
        "HTTPS": {"validated", "reason", "elapsed_ms", "probe_config_version"},
    }
    if set(evidence) - allowed_by_kind[kind]:
        raise ValueError(f"evidence contiene campos incompatibles con {kind}.")
    if "reason" in evidence and evidence["reason"] != reason:
        raise ValueError("evidence.reason debe coincidir con reason_code.")


class CheckSignalResponse(StrictModel):
    signal_id: UUID
    kind: SignalKind
    outcome: SignalOutcome
    reason_code: ReasonCode
    evidence: dict
    elapsed_ms: int | None = None


class CheckResponse(StrictModel):
    network_label: str | None = None
    wifi_metrics: WifiMetrics | None = None
    check_id: UUID
    installation_id: UUID
    source: DataSource
    app_version: str
    android_api_level: int
    started_at: datetime
    finished_at: datetime
    run_status: RunStatus
    signals: list[CheckSignalResponse]
    verdict: OverallVerdict
    has_attention: bool
    received_at: datetime


class CheckPage(StrictModel):
    items: list[CheckResponse]
    next_cursor: str | None


class Health(StrictModel):
    status: Literal["ok", "degraded"]
    database: Literal["ready", "unavailable"]


class ErrorResponse(StrictModel):
    code: str
    message: str
    request_id: str = Field(default=None, min_length=1, max_length=64)
