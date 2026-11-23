from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from honeyphone.core.config import settings

router = APIRouter(tags=["site"])
STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@router.get("/", include_in_schema=False)
def landing():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/account/verify", include_in_schema=False)
def verify_page():
    return FileResponse(STATIC_DIR / "account-action.html")


@router.get("/account/reset", include_in_schema=False)
def reset_page():
    return FileResponse(STATIC_DIR / "account-action.html")


@router.get("/download", include_in_schema=False)
def download_release():
    if not settings.apk_download_url.startswith("https://"):
        raise HTTPException(503, detail={"code": "RELEASE_NOT_PUBLISHED", "message": "La descarga de HoneyPhone todavía no está publicada."})
    return RedirectResponse(settings.apk_download_url, status_code=302)
