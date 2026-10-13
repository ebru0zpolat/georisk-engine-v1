"""Portfolio ingest API — universal asset schema + CSV / GeoJSON upload (§3.1)."""

from __future__ import annotations

import json
from datetime import date
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_principal, require_scopes
from app.core import error_codes as codes
from app.core.config import DEPLOYED_RUNTIMES, settings
from app.core.exceptions import GeoRiskApiError
from app.core.runtime_mode import normalize_app_env
from app.core.security import Principal
from app.portfolios.golden import (
    GOLDEN_ANTALYA_ID,
    GOLDEN_ANTALYA_VALUATION_DATE,
    GOLDEN_ROTTERDAM_PORT_ID,
    GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
    load_golden_antalya_assets,
    load_golden_rotterdam_port_assets,
)
from app.schemas.five_layer import FiveLayerResult, FiveLayerRunRequest, FiveLayerRunResponse
from app.schemas.portfolio import (
    PortfolioUploadRequest,
    PortfolioUploadResponse,
    new_portfolio_id,
)
from app.schemas.portfolio_demo import (
    PortfolioDemoNarrative,
    PortfolioDemoRunRequest,
    PortfolioDemoRunResponse,
)
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail
from app.services.five_layer_pipeline import METHODOLOGY_VERSION as FIVE_LAYER_METHODOLOGY_VERSION
from app.services.five_layer_pipeline import run_five_layer
from app.services.portfolio_demo import (
    DemoNoAnalyzableAssetsError,
    run_golden_antalya_demo,
    run_golden_rotterdam_port_demo,
    run_portfolio_demo,
)
from app.services.portfolio_ingest import parse_portfolio_csv_bytes, parse_portfolio_geojson
from app.services.portfolio_run_service import RunPersistenceError, RunSummary, execute_persisted_run

router = APIRouter()
T = TypeVar("T")

#: HTTP status for each named run refusal; anything else is a 500.
_RUN_ERROR_STATUS = {
    codes.AUDIT_CHAIN_CONTENDED: 503,
    codes.AUDIT_CHAIN_STRUCTURE_BROKEN: 409,
}


async def _execute_run(principal: Principal, compute: Callable[[AppendOnlyAuditTrail], tuple[T, RunSummary]]) -> tuple[T, str | None]:
    """Run ``compute`` as a persisted run, or on the local file trail without a DB.

    With ``DATABASE_URL`` the run row and its audit records commit together in
    one transaction (WP-3 item 0) and the run id is returned. Without a
    database, only a local/dev/test runtime may fall back to the process file
    trail (STUBS #20; no run row, no run id); a deployed runtime refuses.
    """
    if not settings.database_url:
        if normalize_app_env(settings.app_env) in DEPLOYED_RUNTIMES:
            raise GeoRiskApiError(
                code=codes.AUDIT_STORE_UNAVAILABLE,
                message="Runs require the database audit store in a deployed runtime.",
                status_code=503,
            )
        result, _summary = await run_in_threadpool(compute, get_audit_trail())
        return result, None

    from app.db.session import get_session_factory

    try:
        persisted = await execute_persisted_run(
            organisation_id=principal.organisation_id,
            compute=compute,
            session_factory=get_session_factory(),
            source_commit=settings.git_sha,
        )
    except RunPersistenceError as exc:
        raise GeoRiskApiError(
            code=exc.code,
            message=str(exc),
            status_code=_RUN_ERROR_STATUS.get(exc.code, 500),
        ) from exc
    return persisted.result, persisted.run_id


def _accept(body: PortfolioUploadRequest, *, source: str) -> PortfolioUploadResponse:
    return PortfolioUploadResponse(
        portfolio_id=body.portfolio_id or new_portfolio_id(),
        valuation_date=body.valuation_date,
        asset_count=len(body.assets),
        assets=body.assets,
        source=source,  # type: ignore[arg-type]
    )


@router.post("/portfolio/assets", response_model=PortfolioUploadResponse)
def upload_portfolio_json(body: PortfolioUploadRequest) -> PortfolioUploadResponse:
    """Accept a JSON portfolio (universal asset schema + ``valuation_date``)."""
    return _accept(body, source="json")


@router.post(
    "/portfolio/upload",
    response_model=PortfolioUploadResponse,
    dependencies=[Depends(require_scopes("portfolio:write"))],
)
async def upload_portfolio_file(
    file: UploadFile = File(..., description="CSV or GeoJSON portfolio (utf-8)."),
    valuation_date: date = Form(
        ...,
        description="As-of analysis date (Annex B.1). ISO ``YYYY-MM-DD``.",
    ),
    portfolio_id: str | None = Form(default=None),
) -> PortfolioUploadResponse:
    """Accept CSV or GeoJSON portfolio upload with required ``valuation_date``."""
    filename = (file.filename or "").lower()
    max_bytes = settings.portfolio_upload_max_bytes
    content_length = file.headers.get("content-length") if file.headers else None
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise GeoRiskApiError(
                    code=codes.VALIDATION_ERROR,
                    message=(
                        f"Upload exceeds maximum size of {max_bytes} bytes "
                        f"({max_bytes // 1_000_000} MB)."
                    ),
                    status_code=413,
                    details={"max_bytes": max_bytes},
                )
        except ValueError:
            pass

    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message=(
                f"Upload exceeds maximum size of {max_bytes} bytes "
                f"({max_bytes // 1_000_000} MB)."
            ),
            status_code=413,
            details={"max_bytes": max_bytes},
        )
    if not raw.strip():
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message="Upload file is empty.",
            status_code=422,
        )

    is_csv = filename.endswith(".csv")
    is_geojson = filename.endswith(".geojson") or filename.endswith(".json")
    if filename and not (is_csv or is_geojson):
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message="Portfolio upload must be .csv, .geojson, or .json.",
            status_code=422,
            details={"filename": file.filename},
        )

    stripped = raw.lstrip()
    looks_json = stripped.startswith(b"{") or stripped.startswith(b"[")
    use_geojson = is_geojson or (not is_csv and looks_json)

    try:
        if use_geojson:
            parsed = parse_portfolio_geojson(
                raw, valuation_date=valuation_date, portfolio_id=portfolio_id
            )
            source = "geojson"
        else:
            parsed = parse_portfolio_csv_bytes(
                raw, valuation_date=valuation_date, portfolio_id=portfolio_id
            )
            source = "csv"
    except UnicodeDecodeError as exc:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message="File must be UTF-8 encoded.",
            status_code=422,
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message=str(exc),
            status_code=422,
        ) from exc

    return _accept(parsed, source=source)


@router.post(
    "/portfolio/analyze",
    response_model=FiveLayerRunResponse,
    dependencies=[Depends(require_scopes("portfolio:write"))],
)
async def analyze_portfolio_asset(
    body: FiveLayerRunRequest,
    principal: Principal = Depends(get_principal),
) -> FiveLayerRunResponse:
    """Run the five-layer pipeline for one asset as a persisted run (WP-3 item 0)."""

    def compute(trail: AppendOnlyAuditTrail) -> tuple[FiveLayerResult, RunSummary]:
        result = run_five_layer(
            body.asset, body.valuation_date, parameters=body.parameters, trail=trail
        )
        return result, RunSummary(
            methodology_version=FIVE_LAYER_METHODOLOGY_VERSION,
            analyzed_count=1,
            valuation_date=body.valuation_date,
        )

    try:
        result, run_id = await _execute_run(principal, compute)
    except ValueError as exc:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message=str(exc),
            status_code=422,
        ) from exc
    return FiveLayerRunResponse(result=result, run_id=run_id)


@router.get("/portfolio/golden/antalya", response_model=PortfolioUploadResponse)
def get_golden_antalya_portfolio() -> PortfolioUploadResponse:
    """Return the Antalya golden portfolio for the single-screen demo."""
    assets = load_golden_antalya_assets()
    return PortfolioUploadResponse(
        portfolio_id=GOLDEN_ANTALYA_ID,
        valuation_date=GOLDEN_ANTALYA_VALUATION_DATE,
        asset_count=len(assets),
        assets=assets,
        source="json",
    )


@router.get("/portfolio/golden/rotterdam-port", response_model=PortfolioUploadResponse)
def get_golden_rotterdam_port_portfolio() -> PortfolioUploadResponse:
    """Return the Rotterdam port/logistics golden portfolio (Annex B.6 NL-next)."""
    assets = load_golden_rotterdam_port_assets()
    return PortfolioUploadResponse(
        portfolio_id=GOLDEN_ROTTERDAM_PORT_ID,
        valuation_date=GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
        asset_count=len(assets),
        assets=assets,
        source="json",
    )


def _demo_summary(narrative: PortfolioDemoNarrative) -> RunSummary:
    return RunSummary(
        methodology_version=narrative.methodology.pipeline,
        analyzed_count=narrative.asset_count,
        excluded_count=narrative.coverage.excluded_count,
        portfolio_id=narrative.portfolio_id,
        valuation_date=narrative.valuation_date,
    )


async def _demo_response(
    principal: Principal,
    run: Callable[[AppendOnlyAuditTrail], PortfolioDemoNarrative],
) -> PortfolioDemoRunResponse:
    def compute(trail: AppendOnlyAuditTrail) -> tuple[PortfolioDemoNarrative, RunSummary]:
        narrative = run(trail)
        return narrative, _demo_summary(narrative)

    try:
        narrative, run_id = await _execute_run(principal, compute)
    except DemoNoAnalyzableAssetsError as exc:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message=str(exc),
            status_code=422,
            details={
                "coverage": exc.coverage.model_dump(mode="json"),
                "excluded": [row.model_dump(mode="json") for row in exc.coverage.excluded],
            },
        ) from exc
    except FileNotFoundError as exc:
        raise GeoRiskApiError(
            code=codes.NOT_FOUND,
            message=str(exc),
            status_code=404,
        ) from exc
    except ValueError as exc:
        raise GeoRiskApiError(
            code=codes.VALIDATION_ERROR,
            message=str(exc),
            status_code=422,
        ) from exc
    return PortfolioDemoRunResponse(narrative=narrative, run_id=run_id)


@router.post(
    "/portfolio/demo-run",
    response_model=PortfolioDemoRunResponse,
    dependencies=[Depends(require_scopes("portfolio:write"))],
)
async def run_portfolio_demo_endpoint(
    body: PortfolioDemoRunRequest,
    principal: Principal = Depends(get_principal),
) -> PortfolioDemoRunResponse:
    """Single-screen demo: upload → hazard → expected loss → adaptation → avoided loss."""
    return await _demo_response(
        principal,
        lambda trail: run_portfolio_demo(
            body.assets,
            body.valuation_date,
            portfolio_id=body.portfolio_id,
            source="upload",
            max_assets=body.max_assets,
            trail=trail,
        ),
    )


@router.post(
    "/portfolio/demo-run/golden-antalya",
    response_model=PortfolioDemoRunResponse,
    dependencies=[Depends(require_scopes("portfolio:write"))],
)
async def run_golden_antalya_demo_endpoint(
    max_assets: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(get_principal),
) -> PortfolioDemoRunResponse:
    """Run the Antalya golden portfolio through the demo narrative (no map)."""
    return await _demo_response(
        principal, lambda trail: run_golden_antalya_demo(max_assets=max_assets, trail=trail)
    )


@router.post(
    "/portfolio/demo-run/golden-rotterdam-port",
    response_model=PortfolioDemoRunResponse,
    dependencies=[Depends(require_scopes("portfolio:write"))],
)
async def run_golden_rotterdam_port_demo_endpoint(
    max_assets: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(get_principal),
) -> PortfolioDemoRunResponse:
    """Run Rotterdam port golden through the demo narrative (same stub pipeline; EUR)."""
    return await _demo_response(
        principal,
        lambda trail: run_golden_rotterdam_port_demo(max_assets=max_assets, trail=trail),
    )


__all__ = ["router"]
