from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from honeyphone.core.config import settings
from honeyphone.core.errors import database_error_handler, http_error_handler, validation_error_handler
from honeyphone.core.middleware import BodySizeLimitMiddleware
from honeyphone.modules.checks.router import router as checks_router
from honeyphone.modules.health.router import router as health_router
from honeyphone.modules.devices.router import router as devices_router
from honeyphone.modules.honeypot.router import router as honeypot_router

app = FastAPI(
    title="HoneyPhone Local Demo API",
    version="0.3.0",
    description="API P0 local para revisiones de red. Sin autenticación; no exponer fuera del laboratorio.",
    openapi_tags=[{"name": "P0 health"}, {"name": "P0 checks"}],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.include_router(health_router)
app.include_router(checks_router)
app.include_router(devices_router)
app.include_router(honeypot_router)
