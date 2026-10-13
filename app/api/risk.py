"""Risk scoring HTTP API.

- ``POST /v1/risk/score`` — single-asset score
- ``POST /v1/risk/batch`` — synchronous multi-asset score (partial success)
- ``POST /v1/risk/batch/async`` — enqueue (202 + task_id); Celery/Redis when
  ``REDIS_URL`` is configured, in-process BackgroundTasks otherwise
- ``GET /v1/risk/batch/status/{task_id}`` — status poll (shared Redis store in production)
"""

from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse

from app.api.data_centres import router as data_centres_router
from app.api.deps import require_scopes
from app.core.security import Principal
from app.core import error_codes as codes
from app.core.exceptions import GeoRiskApiError
from app.core.preset_registry import DEFAULT_PRESET_ID, is_preset_registered
from app.core.sector_registry import DEFAULT_SECTOR_ID
from app.schemas.errors import ErrorDetail, ErrorEnvelope
from app.schemas.risk import RiskBatchRequest, RiskBatchResponse, RiskScoreRequest, RiskScoreResponse
from app.schemas.risk_async_batch import (
    AsyncBatchTaskStatusLiteral,
    RiskBatchAsyncAcceptedResponse,
    RiskBatchAsyncRequest,
    RiskBatchAsyncTaskStatusResponse,
)
from app.schemas.risk_query import risk_score_request_from_get
from app.core.config import settings
from app.services.async_batch_poc import run_async_batch_poc_task
from app.services.async_batch_store import get_async_batch_task_store
from app.services.risk_service import RiskService

router = APIRouter()
router.include_router(data_centres_router)
_service = RiskService()


@router.post(
    "/risk/score",
    response_model=RiskScoreResponse,
)
def score_risk(body: RiskScoreRequest) -> RiskScoreResponse:
    return _service.score(body)


@router.get("/risk/score", response_model=RiskScoreResponse)
def score_risk_get(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    preset_id: str = Query(DEFAULT_PRESET_ID, min_length=1),
    asset_name: str = Query("asset"),
    sector: str = Query(DEFAULT_SECTOR_ID),
    radius_km: float = Query(10, gt=0, le=100),
    include_industrial_verification_ref: bool = Query(False),
) -> RiskScoreResponse:
    """Query-param score (same engine as POST). Unknown ``preset_id`` → 422 envelope."""
    if not is_preset_registered(preset_id):
        raise GeoRiskApiError(
            code=codes.PRESET_NOT_FOUND,
            message="Unknown preset_id; see REGISTERED_PRESET_IDS.",
            status_code=422,
        )
    body = risk_score_request_from_get(
        lat=lat,
        lon=lon,
        preset_id=preset_id,
        asset_name=asset_name,
        sector=sector,
        radius_km=radius_km,
        include_industrial_verification_ref=include_industrial_verification_ref,
    )
    return _service.score(body)


@router.post(
    "/risk/batch",
    response_model=RiskBatchResponse,
)
def batch_risk(body: RiskBatchRequest) -> RiskBatchResponse:
    """Synchronous multi-asset risk scoring (same engine as ``/v1/risk/score``)."""
    return _service.batch_score(body)


@router.post(
    "/risk/batch/async",
    status_code=202,
    response_model=RiskBatchAsyncAcceptedResponse,
)
def batch_risk_async(
    body: RiskBatchAsyncRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_scopes("risk:read")),
) -> RiskBatchAsyncAcceptedResponse:
    """Enqueue batch, return ``task_id`` + status path.

    With ``REDIS_URL`` set the batch is dispatched to Celery workers over Redis;
    otherwise it runs in-process via BackgroundTasks (offline/PoC mode).
    """
    store = get_async_batch_task_store()
    task_id = store.create_pending(
        total=len(body.assets),
        callback_url=str(body.callback_url) if body.callback_url is not None else None,
        organisation_id=principal.organisation_id,
    )
    if settings.redis_url:
        from app.workers.tasks import risk_batch_score_task

        risk_batch_score_task.delay(task_id, body.model_dump(mode="json"))
    else:
        background_tasks.add_task(run_async_batch_poc_task, task_id, body)
    return RiskBatchAsyncAcceptedResponse(
        task_id=task_id,
        status_path=f"/v1/risk/batch/status/{task_id}",
    )


@router.get("/risk/batch/status/{task_id}", response_model=None)
def batch_async_status(
    task_id: str,
    principal: Principal = Depends(require_scopes("risk:read")),
) -> RiskBatchAsyncTaskStatusResponse | JSONResponse:
    rec = get_async_batch_task_store().get(task_id)
    # Another organisation's task reads exactly like an unknown one.
    if rec is None or rec.organisation_id != principal.organisation_id:
        return JSONResponse(
            status_code=404,
            content=ErrorEnvelope(
                error=ErrorDetail(
                    code=codes.NOT_FOUND,
                    message="Unknown task_id.",
                    details={"task_id": task_id},
                ),
            ).model_dump(),
        )
    return RiskBatchAsyncTaskStatusResponse(
        task_id=task_id,
        status=cast(AsyncBatchTaskStatusLiteral, rec.status),
        progress_processed=rec.progress_processed,
        progress_total=rec.progress_total,
        callback_url=rec.callback_url,
        failed_assets=rec.failed_assets,
        result=rec.result,
        error_message=rec.error_message,
    )
