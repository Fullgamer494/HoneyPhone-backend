from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from honeyphone.core.database import get_session
from honeyphone.modules.checks.models import Installation

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_name: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, min_length=1, max_length=32)

def output(device: Installation):
    return {"installation_id": device.installation_id, "platform": device.platform,
            "device_name": device.device_name, "app_version": device.app_version,
            "active": device.active, "first_seen_at": device.first_seen_at,
            "last_seen_at": device.last_seen_at}

@router.post("", status_code=201)
def register_device(installation_id: UUID, app_version: str = "0.0.0", session: Session = Depends(get_session)):
    device = session.get(Installation, installation_id)
    if device is None:
        device = Installation(installation_id=installation_id, app_version=app_version)
        session.add(device)
        session.commit()
        session.refresh(device)
    return output(device)

@router.get("")
def list_devices(session: Session = Depends(get_session)):
    return {"items": [output(d) for d in session.scalars(select(Installation).order_by(Installation.last_seen_at.desc())).all()]}

@router.get("/{installation_id}")
def get_device(installation_id: UUID, session: Session = Depends(get_session)):
    device = session.get(Installation, installation_id)
    if device is None: raise HTTPException(404, detail={"code":"DEVICE_NOT_FOUND","message":"No se encontró el dispositivo."})
    return output(device)

@router.patch("/{installation_id}")
def update_device(installation_id: UUID, payload: DeviceUpdate, session: Session = Depends(get_session)):
    device = session.get(Installation, installation_id)
    if device is None: raise HTTPException(404, detail={"code":"DEVICE_NOT_FOUND","message":"No se encontró el dispositivo."})
    if not device.active: raise HTTPException(409, detail={"code":"DEVICE_REVOKED","message":"El dispositivo está revocado."})
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(device, key, value)
    session.commit(); session.refresh(device)
    return output(device)

@router.delete("/{installation_id}")
def revoke_device(installation_id: UUID, session: Session = Depends(get_session)):
    device = session.get(Installation, installation_id)
    if device is None: raise HTTPException(404, detail={"code":"DEVICE_NOT_FOUND","message":"No se encontró el dispositivo."})
    device.active = False
    session.commit()
    return output(device)
