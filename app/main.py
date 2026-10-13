from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit_chain import router as audit_chain_router
from app.api.cases import router as cases_router
from app.api.evidence import router as evidence_router
from app.api.deps import require_scopes
from app.api.data_sources import router as data_sources_router
from app.api.demo import router as demo_router
from app.api.gee import router as gee_router
from app.api.health import router as health_router
from app.api.oras5 import router as oras5_router
from app.api.portfolio import router as portfolio_router
from app.api.preview import router as preview_router
from app.api.report import router as report_router
from app.api.release_manifest import router as release_manifest_router
from app.api.risk import router as risk_router
from app.api.scenario import router as scenario_router
from app.api.tiles import router as tiles_router
from app.api.validation import router as validation_router
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.runtime_mode import assert_production_live_sources
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_body_limit import RequestBodyLimitMiddleware
from app.core.validation_errors import validation_error_parts
from app.schemas.errors import ErrorDetail, ErrorEnvelope

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    assert_production_live_sources(settings)
    if settings.effective_snapshot_store_backend == "db":
        from app.services.asset_snapshot_store import set_snapshot_backend
        from app.storage.snapshot_repository import SqlAlchemySnapshotBackend

        set_snapshot_backend(SqlAlchemySnapshotBackend())
    yield


app = FastAPI(
    title="GeoRisk Engine",
    version="0.1.0",
    description="Location-based ESG and operational risk intelligence API.",
    lifespan=lifespan,
)

# Last add_middleware = outermost (runs first on the request).
# Body limit must wrap ASGI ``receive`` before Starlette multipart parsing.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestBodyLimitMiddleware)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(GeoRiskApiError)
async def georisk_api_error_handler(request: Request, exc: GeoRiskApiError) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    code, message, details = validation_error_parts(list(exc.errors()))
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, details=details),
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())



# Every /v1 router is gated by the API-key dependency except health and
# release-manifest (liveness / readiness probes must stay reachable).
app.include_router(health_router, prefix="/v1", tags=["health"])
app.include_router(audit_chain_router, prefix="/v1", tags=["audit-chain"])
app.include_router(evidence_router, prefix="/v1", tags=["evidence"])
app.include_router(cases_router, prefix="/v1", tags=["cases"], dependencies=[Depends(require_scopes("cases:read"))])
app.include_router(data_sources_router, prefix="/v1", tags=["data-sources"], dependencies=[Depends(require_scopes("data_sources:read"))])
app.include_router(demo_router, prefix="/v1", tags=["demo"], dependencies=[Depends(require_scopes("demo:read"))])
app.include_router(gee_router, prefix="/v1", tags=["gee"], dependencies=[Depends(require_scopes("connectors:read"))])
app.include_router(oras5_router, prefix="/v1", tags=["oras5"], dependencies=[Depends(require_scopes("connectors:read"))])
app.include_router(portfolio_router, prefix="/v1", tags=["portfolio"], dependencies=[Depends(require_scopes("portfolio:read"))])
app.include_router(report_router, prefix="/v1", tags=["reports"], dependencies=[Depends(require_scopes("reports:read"))])
app.include_router(release_manifest_router, prefix="/v1", tags=["release-readiness"])
app.include_router(risk_router, prefix="/v1", tags=["risk"], dependencies=[Depends(require_scopes("risk:read"))])
app.include_router(preview_router, prefix="/v1", tags=["risk-preview"], dependencies=[Depends(require_scopes("risk:read"))])
app.include_router(scenario_router, prefix="/v1", tags=["scenario-lab"], dependencies=[Depends(require_scopes("scenario:write"))])
app.include_router(tiles_router, prefix="/v1", tags=["tiles"], dependencies=[Depends(require_scopes("tiles:read"))])
app.include_router(validation_router, prefix="/v1", tags=["validation"], dependencies=[Depends(require_scopes("validation:read"))])


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    from app.core.config import settings as app_settings
    from app.db.session import ping_db

    db_status = "skipped"
    if app_settings.database_url:
        db_status = "ok" if await ping_db() else "error"

    status = "ok" if db_status in {"ok", "skipped"} else "degraded"
    return {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "api": "ok",
            "db": db_status,
        },
    }


if settings.app_env in {"local", "dev"}:
    from app.api.oras5_debug import router as oras5_debug_router

    app.include_router(oras5_debug_router, prefix="/v1", tags=["oras5-debug"])
