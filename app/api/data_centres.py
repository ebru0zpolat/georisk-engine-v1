"""Data-centre physical-climate decision-support API."""

from fastapi import APIRouter

from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.data_centres import assess_data_centre, reporting_boundary
from app.data_centres.contracts import (
    DataCentreAssessmentRequest,
    DataCentreAssessmentResponse,
    EUDataCentreReportingBoundary,
)

router = APIRouter()


@router.get(
    "/risk/data-centre/contract",
    response_model=EUDataCentreReportingBoundary,
)
def get_data_centre_contract() -> EUDataCentreReportingBoundary:
    return reporting_boundary()


@router.post(
    "/risk/data-centre/assess",
    response_model=DataCentreAssessmentResponse,
)
def assess_data_centre_risk(
    body: DataCentreAssessmentRequest,
) -> DataCentreAssessmentResponse:
    if not settings.data_centre_assess_enabled:
        raise GeoRiskApiError(
            code=codes.DATA_CENTRE_ASSESS_DISABLED,
            message=(
                "Data-centre assessment is disabled. Set DATA_CENTRE_ASSESS_ENABLED=true "
                "to expose the decision-support contract. Downtime and monetary models "
                "remain unreleased."
            ),
            status_code=503,
        )
    return assess_data_centre(body)
