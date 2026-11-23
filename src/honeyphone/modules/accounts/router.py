import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from google.auth.exceptions import TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from honeyphone.core.config import settings
from honeyphone.core.database import get_session
from honeyphone.modules.accounts.email import EmailDeliveryError, send_password_reset, send_verification
from honeyphone.modules.accounts.models import AccountActionToken, User
from honeyphone.modules.accounts.security import get_current_user, hash_password, issue_token, verify_password
from honeyphone.modules.checks.models import Installation

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


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=256)


class PasswordResetInput(TokenInput):
    password: str = Field(min_length=10, max_length=128)


def _new_action_token(session: Session, user: User, purpose: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    for old in session.scalars(select(AccountActionToken).where(
        AccountActionToken.user_id == user.user_id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.consumed_at.is_(None),
    )):
        old.consumed_at = now
    raw = secrets.token_urlsafe(48)
    session.add(AccountActionToken(
        token_id=uuid4(), user_id=user.user_id, purpose=purpose,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=now + lifetime,
    ))
    session.commit()
    return raw


def _consume_action_token(session: Session, raw: str, purpose: str) -> tuple[AccountActionToken, User]:
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    action = session.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == token_hash,
        AccountActionToken.purpose == purpose,
    ))
    now = datetime.now(timezone.utc)
    if action is None or action.consumed_at is not None or action.expires_at <= now:
        raise HTTPException(400, detail={"code": "ACTION_LINK_INVALID", "message": "El enlace ya venció o no es válido. Solicita uno nuevo."})
    user = session.get(User, action.user_id)
    if user is None or not user.active:
        raise HTTPException(400, detail={"code": "ACTION_LINK_INVALID", "message": "El enlace ya venció o no es válido. Solicita uno nuevo."})
    action.consumed_at = now
    return action, user


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
    token = _new_action_token(session, user, "verify_email", timedelta(hours=24))
    try:
        send_verification(user.email, token)
    except EmailDeliveryError as exc:
        raise HTTPException(503, detail={"code": "EMAIL_DELIVERY_UNAVAILABLE", "message": "La cuenta se creó, pero no se pudo enviar el correo. Intenta reenviar la verificación."}) from exc
    return {"verification_required": True, "message": "Te enviamos un correo para confirmar tu cuenta."}


@router.post("/login")
def login(payload: AccountInput, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Correo o contraseña incorrectos."}, headers={"WWW-Authenticate": "Bearer"})
    if not user.active:
        raise HTTPException(403, detail={"code": "ACCOUNT_DISABLED", "message": "La cuenta está desactivada."})
    if user.email_verified_at is None:
        raise HTTPException(403, detail={"code": "EMAIL_NOT_VERIFIED", "message": "Confirma tu correo antes de iniciar sesión."})
    return issue_token(user)


@router.post("/verify-email/request", status_code=202)
def request_email_verification(payload: EmailInput, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.active and user.email_verified_at is None and user.password_hash is not None:
        raw = _new_action_token(session, user, "verify_email", timedelta(hours=24))
        try:
            send_verification(user.email, raw)
        except EmailDeliveryError as exc:
            raise HTTPException(503, detail={"code": "EMAIL_DELIVERY_UNAVAILABLE", "message": "No se pudo enviar el correo ahora. Inténtalo de nuevo más tarde."}) from exc
    return {"message": "Si la cuenta necesita verificación, recibirás un correo con los siguientes pasos."}


@router.post("/verify-email/confirm")
def confirm_email(payload: TokenInput, session: Session = Depends(get_session)):
    _, user = _consume_action_token(session, payload.token, "verify_email")
    user.email_verified_at = datetime.now(timezone.utc)
    session.commit()
    return {"verified": True, "message": "Correo confirmado. Ya puedes iniciar sesión en HoneyPhone."}


@router.post("/password/forgot", status_code=202)
def forgot_password(payload: EmailInput, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.active and user.password_hash is not None and user.email_verified_at is not None:
        raw = _new_action_token(session, user, "reset_password", timedelta(hours=1))
        try:
            send_password_reset(user.email, raw)
        except EmailDeliveryError as exc:
            raise HTTPException(503, detail={"code": "EMAIL_DELIVERY_UNAVAILABLE", "message": "No se pudo enviar el correo ahora. Inténtalo de nuevo más tarde."}) from exc
    return {"message": "Si hay una cuenta con ese correo, recibirás instrucciones para recuperar el acceso."}


@router.post("/password/reset")
def reset_password(payload: PasswordResetInput, session: Session = Depends(get_session)):
    action, user = _consume_action_token(session, payload.token, "reset_password")
    user.password_hash = hash_password(payload.password)
    # Consume any other reset link issued for this account.
    for old in session.scalars(select(AccountActionToken).where(
        AccountActionToken.user_id == user.user_id,
        AccountActionToken.purpose == "reset_password",
        AccountActionToken.consumed_at.is_(None),
        AccountActionToken.token_id != action.token_id,
    )):
        old.consumed_at = datetime.now(timezone.utc)
    session.commit()
    return {"updated": True, "message": "Contraseña actualizada. Ya puedes iniciar sesión."}


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
            user = User(user_id=uuid4(), email=email, google_subject=subject, display_name=claims.get("name"), email_verified_at=datetime.now(timezone.utc))
            session.add(user)
        else:
            user.google_subject = subject
            user.display_name = user.display_name or claims.get("name")
            user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, detail={"code": "ACCOUNT_LINK_CONFLICT", "message": "No se pudo vincular esta cuenta de Google."}) from exc
        session.refresh(user)
    if not user.active:
        raise HTTPException(403, detail={"code": "ACCOUNT_DISABLED", "message": "La cuenta está desactivada."})
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return issue_token(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": str(user.user_id), "email": user.email, "display_name": user.display_name, "email_verified": user.email_verified_at is not None}


@router.delete("/me", status_code=204)
def delete_me(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    # Remove installations first; database cascades then erase their checks,
    # signals, honeypot sessions, and events before the account row is deleted.
    session.execute(delete(Installation).where(Installation.owner_user_id == user.user_id))
    session.delete(user)
    session.commit()
    return Response(status_code=204)
