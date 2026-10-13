from fastapi import APIRouter

from app.core.config import settings
from app.core.runtime_mode import allows_connector_stubs, normalize_app_env

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "georisk-engine",
        "git_sha": settings.git_sha or "unknown",
        "app_env": normalize_app_env(settings.app_env),
        "connector_stubs_permitted": allows_connector_stubs(settings),
    }
