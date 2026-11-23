import base64
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from honeyphone.modules.checks.models import CheckSignal, DataSource, NetworkCheck, OverallVerdict, SignalOutcome
from honeyphone.modules.checks.repository import CheckRepository
from honeyphone.modules.checks.schemas import CheckCreate


class CheckService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CheckRepository(session)

    def create(self, payload: CheckCreate, user_id: UUID) -> tuple[NetworkCheck, bool]:
        canonical = canonical_payload(payload)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        has_attention = any(signal.outcome == SignalOutcome.ATTENTION or signal.outcome == "ATTENTION" for signal in payload.signals)
        incomplete = payload.run_status == "CANCELLED" or any(signal.outcome == SignalOutcome.UNKNOWN or signal.outcome == "UNKNOWN" for signal in payload.signals)
        verdict = OverallVerdict.INCOMPLETE if incomplete else OverallVerdict.ATTENTION_REQUIRED if has_attention else OverallVerdict.NO_DISCREPANCIES

        try:
            self.repo.touch_installation(payload.installation_id, payload.app_version, user_id)
            existing = self.repo.get(payload.check_id, user_id)
            if existing is not None:
                if existing.payload_sha256 != digest:
                    raise HTTPException(status_code=409, detail={"code": "CHECK_ID_CONFLICT", "message": "check_id ya existe con contenido distinto."})
                self.session.commit()
                return existing, False
            check = NetworkCheck(
                check_id=payload.check_id,
                installation_id=payload.installation_id,
                source=payload.source,
                app_version=payload.app_version,
                android_api_level=payload.android_api_level,
                started_at=payload.started_at,
                finished_at=payload.finished_at,
                run_status=payload.run_status,
                verdict=verdict,
                has_attention=has_attention,
                payload_sha256=digest,
                network_label=payload.network_label,
                wifi_metrics=payload.wifi_metrics.model_dump(exclude_none=True) if payload.wifi_metrics is not None else None,
            )
            signals = [
                CheckSignal(
                    signal_id=s.signal_id,
                    check_id=payload.check_id,
                    kind=s.kind,
                    outcome=s.outcome,
                    reason_code=s.reason_code,
                    evidence=s.evidence.model_dump(exclude_none=True),
                    elapsed_ms=s.elapsed_ms,
                )
                for s in payload.signals
            ]
            self.repo.add(check, signals)
            self.session.commit()
            return check, True
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.repo.get(payload.check_id, user_id)
            if existing is not None and existing.payload_sha256 == digest:
                return existing, False
            raise HTTPException(status_code=409, detail={"code": "IDENTIFIER_CONFLICT", "message": "check_id o signal_id ya está asociado a contenido existente."}) from exc
        except Exception:
            self.session.rollback()
            raise

    def get(self, check_id: UUID, user_id: UUID) -> NetworkCheck:
        check = self.repo.get(check_id, user_id)
        if check is None:
            raise HTTPException(status_code=404, detail={"code": "CHECK_NOT_FOUND", "message": "No se encontró la revisión."})
        return check

    def list(self, user_id: UUID, installation_id: UUID | None, source: DataSource | None, limit: int, cursor_token: str | None):
        cursor = decode_cursor(cursor_token) if cursor_token else None
        rows = self.repo.list(user_id, installation_id, source, limit, cursor)
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].started_at, page[-1].check_id) if has_more and page else None
        return page, next_cursor

    def delete(self, check_id: UUID, user_id: UUID) -> None:
        try:
            if not self.repo.delete(check_id, user_id):
                raise HTTPException(status_code=404, detail={"code": "CHECK_NOT_FOUND", "message": "No se encontró la revisión."})
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


def canonical_payload(payload: CheckCreate) -> str:
    data = payload.model_dump(mode="json")
    # Preserve the canonical representation used by 0.1/0.2 clients.
    for field in ("network_label", "wifi_metrics"):
        if data.get(field) is None:
            data.pop(field, None)
    if "wifi_metrics" in data:
        data["wifi_metrics"] = payload.wifi_metrics.model_dump(exclude_none=True)
    data["signals"] = sorted(data["signals"], key=lambda item: item["kind"])
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def encode_cursor(started_at: datetime, check_id: UUID) -> str:
    raw = json.dumps({"started_at": started_at.astimezone(timezone.utc).isoformat(), "check_id": str(check_id)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token: str) -> tuple[datetime, UUID]:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded.encode()))
        stamp = datetime.fromisoformat(raw["started_at"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("cursor without timezone")
        return stamp.astimezone(timezone.utc), UUID(raw["check_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CURSOR", "message": "El cursor de paginación no es válido."}) from exc
