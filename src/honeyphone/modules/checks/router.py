from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from honeyphone.core.database import get_session
from honeyphone.modules.checks.models import DataSource
from honeyphone.modules.checks.schemas import CheckCreate, CheckPage, CheckResponse, ErrorResponse
from honeyphone.modules.checks.service import CheckService
from honeyphone.modules.accounts.models import User
from honeyphone.modules.accounts.security import get_current_user

router = APIRouter(prefix="/api/v1/network-checks", tags=["P0 checks"])


@router.post("", response_model=CheckResponse, status_code=201, responses={200: {"model": CheckResponse}, 409: {"model": ErrorResponse, "description": "ID con contenido distinto"}, 413: {"model": ErrorResponse, "description": "Carga mayor que 64 KiB"}, 422: {"model": ErrorResponse, "description": "Datos inválidos"}, 503: {"model": ErrorResponse, "description": "Base de datos no disponible"}})
def create_check(payload: CheckCreate, response: Response, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    check, created = CheckService(session).create(payload, user.user_id)
    response.status_code = 201 if created else 200
    return check


@router.get("", response_model=CheckPage, responses={422: {"model": ErrorResponse, "description": "Cursor o filtros inválidos"}, 503: {"model": ErrorResponse, "description": "Base de datos no disponible"}})
def list_checks(installation_id: UUID | None = None, source: DataSource | None = None, limit: int = Query(default=20, ge=1, le=50), cursor: str | None = Query(default=None, max_length=512), session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    items, next_cursor = CheckService(session).list(user.user_id, installation_id, source, limit, cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/{check_id}", response_model=CheckResponse, responses={404: {"model": ErrorResponse, "description": "No encontrado"}, 422: {"model": ErrorResponse, "description": "Identificador inválido"}, 503: {"model": ErrorResponse, "description": "Base de datos no disponible"}})
def get_check(check_id: UUID, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return CheckService(session).get(check_id, user.user_id)


@router.delete("/{check_id}", status_code=204, responses={404: {"model": ErrorResponse, "description": "No encontrado"}, 422: {"model": ErrorResponse, "description": "Identificador inválido"}, 503: {"model": ErrorResponse, "description": "Base de datos no disponible"}})
def delete_check(check_id: UUID, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    CheckService(session).delete(check_id, user.user_id)
    return Response(status_code=204)
