from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from honeyphone.core.config import settings
from honeyphone.core.database import get_session
from honeyphone.modules.accounts.models import User
from honeyphone.modules.accounts.security import get_current_user, hash_password, issue_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["accounts"])


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class GoogleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=20, max_length=8192)


@router.post("/register", status_code=201)
def register(payload: AccountInput, session: Session = Depends(get_session)):
    if session.scalar(select(User.user_id).where(User.email == payload.email)):
        raise HTTPException(409, detail={"code": "EMAIL_IN_USE", "message": "Ya existe una cuenta con ese correo."})
    user = User(user_id=uuid4(), email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, detail={"code": "EMAIL_IN_USE", "message": "Ya existe una cuenta con ese correo."}) from exc
    session.refresh(user)
    return issue_token(user)


@router.post("/login")
def login(payload: AccountInput, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Correo o contraseña incorrectos."}, headers={"WWW-Authenticate": "Bearer"})
    if not user.active:
        raise HTTPException(403, detail={"code": "ACCOUNT_DISABLED", "message": "La cuenta está desactivada."})
    return issue_token(user)


@router.post("/google")
def google_login(payload: GoogleInput, session: Session = Depends(get_session)):
    if not settings.google_audiences:
        raise HTTPException(503, detail={"code": "GOOGLE_LOGIN_UNAVAILABLE", "message": "El acceso con Google aún no está configurado en el servidor."})
    try:
        claims = id_token.verify_oauth2_token(payload.id_token, GoogleRequest(), audience=settings.google_audiences)
    except TransportError as exc:
        raise HTTPException(503, detail={"code": "GOOGLE_AUTH_UNAVAILABLE", "message": "No se pudo contactar a Google para validar el acceso."}) from exc
    except ValueError as exc:
        raise HTTPException(401, detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Google no pudo validar el inicio de sesión."}) from exc
    email = str(claims.get("email", "")).strip().lower()
    subject = str(claims.get("sub", ""))
    if not email or not subject or claims.get("email_verified") is not True:
        raise HTTPException(401, detail={"code": "GOOGLE_EMAIL_UNVERIFIED", "message": "La cuenta de Google no tiene un correo verificado."})
    user = session.scalar(select(User).where(User.google_subject == subject))
    if user is None:
        user = session.scalar(select(User).where(User.email == email))
        if user is not None and user.google_subject not in (None, subject):
            raise HTTPException(409, detail={"code": "ACCOUNT_LINK_CONFLICT", "message": "Este correo ya está vinculado a otra cuenta de Google."})
        if user is None:
            user = User(user_id=uuid4(), email=email, google_subject=subject, display_name=claims.get("name"))
            session.add(user)
        else:
            user.google_subject = subject
            user.display_name = user.display_name or claims.get("name")
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, detail={"code": "ACCOUNT_LINK_CONFLICT", "message": "No se pudo vincular esta cuenta de Google."}) from exc
        session.refresh(user)
    if not user.active:
        raise HTTPException(403, detail={"code": "ACCOUNT_DISABLED", "message": "La cuenta está desactivada."})
    return issue_token(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": str(user.user_id), "email": user.email, "display_name": user.display_name}
