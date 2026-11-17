from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from honeyphone.core.database import get_session
from honeyphone.modules.checks.schemas import Health

router = APIRouter()


@router.get("/healthz", response_model=Health, responses={503: {"model": Health}})
def health(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ready"}
    except SQLAlchemyError as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
