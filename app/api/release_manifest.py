"""Release-readiness evidence endpoint."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.release_manifest import ReleaseManifest
from app.services.release_manifest import build_release_manifest

router = APIRouter()


@router.get("/release-manifest", response_model=ReleaseManifest)
def release_manifest() -> ReleaseManifest:
    return build_release_manifest(settings)
