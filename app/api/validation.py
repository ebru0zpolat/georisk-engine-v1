from fastapi import APIRouter, Depends

from app.api.deps import require_scopes
from app.schemas.validation import (
    BenchmarkRequest,
    ValidationReport,
    ValidationResult,
)
from app.services.validation_service import ValidationService

router = APIRouter()
_service = ValidationService()


@router.post(
    "/validation/benchmark",
    response_model=ValidationReport,
    dependencies=[Depends(require_scopes("validation:write"))],
)
def benchmark(body: BenchmarkRequest) -> ValidationReport:
    """Benchmark a company's reported metrics against GeoRisk signals."""

    return _service.benchmark(body)


@router.get(
    "/validation/benchmark/{company_id}/{year}",
    response_model=ValidationReport,
)
def get_benchmark(company_id: str, year: int) -> ValidationReport:
    """Return the stored validation report for a company/year pair."""

    return _service.get_report(company_id, year)


@router.get(
    "/validation/evidence/{validation_id}",
    response_model=ValidationResult,
)
def get_evidence(validation_id: str) -> ValidationResult:
    """Return a single evidence record with its full audit trail."""

    return _service.get_evidence(validation_id)
