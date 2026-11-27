from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from honeyphone.core.config import settings
from honeyphone.core.errors import database_error_handler, http_error_handler, validation_error_handler
from honeyphone.core.middleware import BodySizeLimitMiddleware
from honeyphone.core.http_security import RateLimitMiddleware, SecurityHeadersMiddleware
from honeyphone.modules.checks.router import router as checks_router
from honeyphone.modules.health.router import router as health_router
from honeyphone.modules.devices.router import router as devices_router
from honeyphone.modules.honeypot.router import router as honeypot_router
from honeyphone.modules.accounts.router import router as accounts_router
from honeyphone.modules.site.router import router as site_router

app = FastAPI(
    title="HoneyPhone API",
    version="0.5.0",
    description="API de HoneyPhone con cuentas, autenticación y datos aislados por usuario.",
    openapi_tags=[{"name": "P0 health"}, {"name": "P0 checks"}],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.include_router(health_router)
app.include_router(checks_router)
app.include_router(devices_router)
app.include_router(honeypot_router)
app.include_router(accounts_router)
app.include_router(site_router)
