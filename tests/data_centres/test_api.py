from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.data_centres.test_assessment import _request, _request_with_complete_profile


def test_contract_endpoint_exposes_eu_boundary() -> None:
    response = TestClient(app).get("/v1/risk/data-centre/contract")
    assert response.status_code == 200
    assert response.json()["support_level"] == "supporting_evidence_only"


def test_assessment_endpoint_disabled_by_default() -> None:
    response = TestClient(app).post("/v1/risk/data-centre/assess", json=_request())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATA_CENTRE_ASSESS_DISABLED"


def test_assessment_endpoint_returns_fail_closed_output(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_centre_assess_enabled", True)
    response = TestClient(app).post(
        "/v1/risk/data-centre/assess", json=_request_with_complete_profile()
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness"] == "decision_support_only"
    assert payload["monetary_outputs"]["expected_annual_loss"] is None
    assert payload["production_release"] == "none"
    assert payload["downtime_model_released"] is False
    assert payload["monetary_model_released"] is False
    assert payload["disclaimer"].startswith("Decision-support evidence only")
