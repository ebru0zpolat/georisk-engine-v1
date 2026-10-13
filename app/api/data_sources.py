from typing import Literal

from fastapi import APIRouter, Query

from app.core.exceptions import GeoRiskApiError
from app.schemas.data_sources import DataSourceValidationReport, DataSourcesListResponse, SourceValidationOut
from app.schemas.data_sources import build_data_sources_response
from app.services.data_source_validation_service import build_source_validation, build_validation_report

router = APIRouter()

DataSourceTierQuery = Literal["production", "audit", "roadmap"]


@router.get("/data-sources", response_model=DataSourcesListResponse)
def list_registered_data_sources(
    tier: DataSourceTierQuery | None = Query(
        default=None,
        description="Filter by integration tier: production (risk API), audit (operational scripts), roadmap.",
    ),
) -> DataSourcesListResponse:
    return build_data_sources_response(tier=tier)


@router.get("/data-sources/validation", response_model=DataSourceValidationReport)
def data_source_validation_report() -> DataSourceValidationReport:
    """Runtime validation posture for all registered data sources."""
    return build_validation_report()


@router.get("/data-sources/{source_id}/validation", response_model=SourceValidationOut)
def data_source_validation_for_id(source_id: str) -> SourceValidationOut:
    result = build_source_validation(source_id)
    if result is None:
        raise GeoRiskApiError(
            code="DATA_SOURCE_NOT_FOUND",
            message=f"Unknown data source id: {source_id}",
            status_code=404,
        )
    return result
