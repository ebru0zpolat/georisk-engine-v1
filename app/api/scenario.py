from fastapi import APIRouter

from app.schemas.scenario import ScenarioRunRequest, ScenarioRunResponse
from app.services.scenario_lab_service import ScenarioLabService

router = APIRouter()
_service = ScenarioLabService()


@router.post("/scenario/run", response_model=ScenarioRunResponse)
def run_scenario(body: ScenarioRunRequest) -> ScenarioRunResponse:
    """Scenario-Lab: CMIP6 pathway stress on a GeoRisk-scored asset (Layer 2)."""
    return _service.run(body)
