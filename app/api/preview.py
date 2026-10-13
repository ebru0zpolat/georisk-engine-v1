from fastapi import APIRouter

from app.schemas.preview import PreviewRiskScoreRequest, PreviewRiskScorecard
from app.services.preview_risk_service import PreviewRiskService

router = APIRouter()
_service = PreviewRiskService()


@router.post("/risk/preview", response_model=PreviewRiskScorecard)
def preview_risk_score(body: PreviewRiskScoreRequest) -> PreviewRiskScorecard:
    """1-minute indicative climate risk scorecard (coordinate, address, or demo id)."""
    return _service.compute_preview_risk_score(body)
