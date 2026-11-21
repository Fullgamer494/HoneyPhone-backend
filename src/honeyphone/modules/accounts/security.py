import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from honeyphone.core.config import settings
from honeyphone.core.database import get_session
from honeyphone.modules.accounts.models import User

_bearer = HTTPBearer(auto_error=False)
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, lifetime_seconds: int = 43200) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": str(user.user_id), "email": user.email, "iat": now, "exp": now + lifetime_seconds}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(settings.auth_secret_key.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def _decode_token(token: str) -> UUID:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = hmac.new(settings.auth_secret_key.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(payload))
        if claims.get("exp", 0) <= int(time.time()) or not claims.get("sub"):
            raise ValueError("expired token")
        return UUID(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "La sesión expiró o no es válida."}, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), session: Session = Depends(get_session)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Inicia sesión para continuar."}, headers={"WWW-Authenticate": "Bearer"})
    user = session.get(User, _decode_token(credentials.credentials))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail={"code": "ACCOUNT_UNAVAILABLE", "message": "La cuenta no está disponible."}, headers={"WWW-Authenticate": "Bearer"})
    return user


def issue_token(user: User) -> dict:
    return {"access_token": create_access_token(user), "token_type": "bearer", "expires_in": 43200,
            "user": {"user_id": str(user.user_id), "email": user.email, "display_name": user.display_name}}
