from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app


def test_preview_risk_scorecard_coordinates() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/preview",
        json={"location": "39.97, 32.74", "asset_name": "Preview test"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "indicative_climate_risk_score" in data
    assert 0 <= data["indicative_climate_risk_score"] <= 100
    assert data["resolved"]["resolution_method"] == "coordinates"
    assert data["location_input"] == "39.97, 32.74"
    assert len(data["components"]) == 8
    assert data["disclaimer"]
    assert data["audit_id"]


def test_preview_risk_scorecard_demo_asset() -> None:
    client = TestClient(app)
    r = client.post("/v1/risk/preview", json={"location": "coastal_industrial_med"})
    assert r.status_code == 200
    data = r.json()
    assert data["resolved"]["resolution_method"] == "demo_asset"
    assert data["resolved"]["resolution_detail"] == "coastal_industrial_med"


def test_preview_unresolved_location() -> None:
    client = TestClient(app)
    r = client.post("/v1/risk/preview", json={"location": "zzzz-unresolvable"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "location_unresolved"
