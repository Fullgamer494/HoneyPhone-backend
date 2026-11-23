from datetime import datetime, timezone
import hashlib, json, ipaddress
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from honeyphone.core.database import get_session
from honeyphone.modules.checks.models import DataSource, HoneypotEvent, HoneypotSession, HoneypotState, Installation
from honeyphone.modules.accounts.models import User
from honeyphone.modules.accounts.security import get_current_user

router = APIRouter(prefix="/api/v1/honeypot/sessions", tags=["honeypot"])

class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    installation_id: UUID
    source: DataSource = DataSource.LIVE
    listen_port: int = Field(default=8080, ge=1024, le=65535)
    started_at: datetime
    ended_at: datetime | None = None
    state: HoneypotState

    @model_validator(mode="after")
    def valid_dates(self):
        if self.started_at.tzinfo is None or (self.ended_at and self.ended_at.tzinfo is None):
            raise ValueError("Las fechas deben incluir zona horaria.")
        if self.state == HoneypotState.RUNNING and self.ended_at is not None:
            raise ValueError("Una sesión activa no puede tener ended_at.")
        if self.state != HoneypotState.RUNNING and self.ended_at is None:
            raise ValueError("Una sesión cerrada requiere ended_at.")
        return self

class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    occurred_at: datetime
    source_ip_masked: str = Field(max_length=64)
    http_method: str
    request_path: str
    user_agent_family: str | None = None
    content_length: int = Field(ge=0, le=2147483647)
    response_code: int = Field(ge=100, le=599)

class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[EventInput] = Field(min_length=1, max_length=100)

@router.post("", status_code=201)
def upsert_session(payload: SessionInput, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    device = session.get(Installation, payload.installation_id)
    if device is None or not device.active:
        raise HTTPException(403, detail={"code":"DEVICE_UNAVAILABLE","message":"El dispositivo no está registrado o fue revocado."})
    if device.owner_user_id is None:
        device.owner_user_id = user.user_id
    elif device.owner_user_id != user.user_id:
        raise HTTPException(403, detail={"code":"DEVICE_OWNED_BY_OTHER_ACCOUNT","message":"Esta instalación está asociada a otra cuenta."})
    row = session.get(HoneypotSession, payload.session_id)
    if row is None:
        row = HoneypotSession(**payload.model_dump())
        session.add(row)
    else:
        if row.installation_id != payload.installation_id or row.started_at != payload.started_at or row.listen_port != payload.listen_port:
            raise HTTPException(409, detail={"code":"SESSION_ID_CONFLICT","message":"El identificador de sesión ya tiene otros datos."})
        if row.state != HoneypotState.RUNNING and payload.state == HoneypotState.RUNNING:
            raise HTTPException(409, detail={"code":"SESSION_CLOSED","message":"No se puede reabrir una sesión cerrada."})
        row.state, row.ended_at = payload.state, payload.ended_at
    session.commit(); session.refresh(row)
    return row

@router.get("")
def list_sessions(installation_id: UUID | None = None, limit: int = Query(20, ge=1, le=50), session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    query = select(HoneypotSession).join(Installation).where(Installation.owner_user_id == user.user_id).order_by(HoneypotSession.started_at.desc()).limit(limit)
    if installation_id is not None: query = query.where(HoneypotSession.installation_id == installation_id)
    return {"items": list(session.scalars(query).all()), "next_cursor": None}

@router.post("/{session_id}/events")
def append_events(session_id: UUID, batch: EventBatch, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        owned_session = db.scalar(select(HoneypotSession).join(Installation).where(HoneypotSession.session_id == session_id, Installation.owner_user_id == user.user_id))
        if owned_session is None:
            raise HTTPException(404, detail={"code":"SESSION_NOT_FOUND","message":"No se encontró la sesión."})
        inserted = duplicates = 0
        for item in batch.events:
            try:
                network = ipaddress.ip_network(item.source_ip_masked, strict=True)
            except ValueError as exc:
                raise HTTPException(422, detail={"code":"INVALID_MASKED_IP","message":"La IP debe ser una red /24 IPv4 o /64 IPv6 ya enmascarada."}) from exc
            expected = 24 if network.version == 4 else 64
            if network.prefixlen != expected:
                raise HTTPException(422, detail={"code":"INVALID_MASKED_IP","message":"La máscara debe ser /24 IPv4 o /64 IPv6."})
            if item.occurred_at.tzinfo is None:
                raise HTTPException(422, detail={"code":"INVALID_TIMESTAMP","message":"La fecha debe incluir zona horaria."})
            if item.http_method not in {"GET","HEAD","POST","OTHER"} or item.request_path not in {"/","/admin","/login","/robots.txt","/other"}:
                raise HTTPException(422, detail={"code":"INVALID_EVENT","message":"Método o ruta no admitidos."})
            if item.user_agent_family not in {None,"BROWSER","SCANNER","OTHER","UNKNOWN"}:
                raise HTTPException(422, detail={"code":"INVALID_EVENT","message":"Familia User-Agent no admitida."})
            canonical = json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",",":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            existing = db.get(HoneypotEvent, item.event_id)
            if existing:
                if existing.session_id != session_id or existing.payload_sha256 != digest:
                    raise HTTPException(409, detail={"code":"EVENT_ID_CONFLICT","message":"El event_id ya existe con datos diferentes."})
                duplicates += 1
                continue
            db.add(HoneypotEvent(event_id=item.event_id, session_id=session_id, occurred_at=item.occurred_at.astimezone(timezone.utc),
                source_ip_masked=str(network), http_method=item.http_method, request_path=item.request_path,
                user_agent_family=item.user_agent_family, content_length=item.content_length, response_code=item.response_code, payload_sha256=digest))
            inserted += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"inserted_count":inserted,"duplicate_count":duplicates}

@router.get("/{session_id}/events")
def list_events(session_id: UUID, limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    owned_session = db.scalar(select(HoneypotSession.session_id).join(Installation).where(HoneypotSession.session_id == session_id, Installation.owner_user_id == user.user_id))
    if owned_session is None:
        raise HTTPException(404, detail={"code":"SESSION_NOT_FOUND","message":"No se encontró la sesión."})
    rows = db.scalars(select(HoneypotEvent).where(HoneypotEvent.session_id==session_id).order_by(HoneypotEvent.occurred_at.desc()).limit(limit)).all()
    return {"items":rows,"next_cursor":None}
