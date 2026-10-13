"""Risk API: industrial verification bundle keyed by ``audit_id``."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app


def test_risk_score_industrial_verification_off_by_default() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Test",
        "latitude": 39.97,
        "longitude": 32.74,
        "radius_km": 10,
        "sector": "industrial",
    }
    r = client.post("/v1/risk/score", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["industrial_verification"] is None


def test_risk_score_industrial_verification_linked_audit_near_ankara() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Near Astor AOI",
        "latitude": 39.972,
        "longitude": 32.743,
        "radius_km": 10,
        "sector": "industrial",
        "include_industrial_verification_ref": True,
    }
    r = client.post("/v1/risk/score", json=body)
    assert r.status_code == 200
    data = r.json()
    iv = data["industrial_verification"]
    assert iv is not None
    assert iv["linked_audit_id"] == data["audit_id"]
    assert iv["nearest_primary_audit"] is not None
    assert iv["nearest_primary_audit"]["facility_id"] == "astor_enerji_ankara"
    assert len(iv["pipelines"]) >= 2


def test_demo_run_includes_industrial_verification() -> None:
    client = TestClient(app)
    r = client.get("/v1/demo/run?asset_id=coastal_industrial_med")
    assert r.status_code == 200
    data = r.json()
    iv = data.get("industrial_verification")
    assert iv is not None
    assert iv["linked_audit_id"] == data["audit"]["audit_id"]
    assert iv["nearest_primary_audit"] is None


def test_risk_markdown_report_includes_industrial_by_default() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Near Astor AOI",
        "latitude": 39.972,
        "longitude": 32.743,
        "radius_km": 10,
        "sector": "industrial",
    }
    r = client.post("/v1/reports/risk", json=body)
    assert r.status_code == 200
    text = r.text
    assert "## Industrial verification" in text
    assert "Linked audit ID" in text
    assert "astor_enerji_ankara" in text


def test_risk_markdown_report_omits_industrial_when_disabled() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Near Astor AOI",
        "latitude": 39.972,
        "longitude": 32.743,
        "radius_km": 10,
        "sector": "industrial",
        "include_industrial_verification_ref": False,
    }
    r = client.post("/v1/reports/risk", json=body)
    assert r.status_code == 200
    assert "## Industrial verification" not in r.text
