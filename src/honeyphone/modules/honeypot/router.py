from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from honeyphone.core.database import get_session
from honeyphone.modules.checks.models import DataSource, HoneypotSession, HoneypotState, Installation

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

@router.post("", status_code=201)
def upsert_session(payload: SessionInput, session: Session = Depends(get_session)):
    device = session.get(Installation, payload.installation_id)
    if device is None or not device.active:
        raise HTTPException(403, detail={"code":"DEVICE_UNAVAILABLE","message":"El dispositivo no está registrado o fue revocado."})
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
def list_sessions(installation_id: UUID | None = None, limit: int = Query(20, ge=1, le=50), session: Session = Depends(get_session)):
    query = select(HoneypotSession).order_by(HoneypotSession.started_at.desc()).limit(limit)
    if installation_id is not None: query = query.where(HoneypotSession.installation_id == installation_id)
    return {"items": list(session.scalars(query).all()), "next_cursor": None}
