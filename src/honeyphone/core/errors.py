from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "La solicitud contiene datos inválidos."},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    del request
    if isinstance(exc.detail, dict) and {"code", "message"} <= exc.detail.keys():
        body = exc.detail
    else:
        body = {"code": "NOT_FOUND" if exc.status_code == 404 else "REQUEST_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    del request, exc
    return JSONResponse(
        status_code=503,
        content={"code": "DATABASE_UNAVAILABLE", "message": "La base de datos no está disponible."},
    )
