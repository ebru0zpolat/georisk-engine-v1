from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.connectors import GeeConnector, GeePointRequest
from app.core.config import settings
from app.core.runtime_mode import gee_uses_stub, production_eligible_for_response
from app.schemas.baseline import optional_paired_dates_or_none
from app.schemas.gee import GeeFeaturesGetResponse, GeeFeatures, gee_baseline_from_raw

router = APIRouter()
connector = GeeConnector()


@router.get("/gee/features", response_model=GeeFeaturesGetResponse)
def gee_features(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    baseline_start_date: date | None = None,
    baseline_end_date: date | None = None,
) -> GeeFeaturesGetResponse:
    try:
        optional_paired_dates_or_none(
            baseline_start_date,
            baseline_end_date,
            label="baseline",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    payload = GeePointRequest(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        start_date=start_date,
        end_date=end_date,
        baseline_start_date=baseline_start_date or settings.climate_baseline_start,
        baseline_end_date=baseline_end_date or settings.climate_baseline_end,
    )
    raw = connector.fetch_features(payload)
    data_mode = "stub" if gee_uses_stub(settings) else "live"
    return GeeFeaturesGetResponse(
        current=GeeFeatures.model_validate(raw),
        gee_baseline=gee_baseline_from_raw(raw),
        data_mode=data_mode,
        production_eligible=False if data_mode == "stub" else production_eligible_for_response(settings),
    )
