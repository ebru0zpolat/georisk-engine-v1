"""Agriculture sector attaches NDVI / soil proxies on GEE feature bundle."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.core.sector_registry import AGRICULTURE_SECTOR_ID, DEFAULT_SECTOR_ID
from app.main import app
from app.scoring.agriculture_surface import attach_agriculture_proxies_to_gee_dict
from app.schemas.risk import RiskScoreRequest


def test_attach_proxies_only_for_agriculture() -> None:
    base = {"night_lights_mean": 1.0, "no2_mean": 0.1}
    ind = RiskScoreRequest(
        asset_name="X",
        latitude=40.0,
        longitude=29.0,
        sector=DEFAULT_SECTOR_ID,
    )
    ag = ind.model_copy(update={"sector": AGRICULTURE_SECTOR_ID})
    out_i = attach_agriculture_proxies_to_gee_dict(base, ind)
    out_a = attach_agriculture_proxies_to_gee_dict(base, ag)
    assert out_i.get("ndvi_mean") is None
    assert out_i.get("soil_moisture_proxy") is None
    assert out_a["ndvi_mean"] is not None
    assert out_a["soil_moisture_proxy"] is not None


def test_risk_score_agriculture_includes_gee_proxies() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Farm test",
        "latitude": 38.22,
        "longitude": 32.48,
        "radius_km": 10,
        "sector": AGRICULTURE_SECTOR_ID,
    }
    r = client.post("/v1/risk/score", json=body)
    assert r.status_code == 200
    data = r.json()
    gee = data["gee_features"]
    assert gee["ndvi_mean"] is not None
    assert gee["soil_moisture_proxy"] is not None


def test_risk_report_markdown_lists_agriculture_proxies() -> None:
    client = TestClient(app)
    body = {
        "asset_name": "Farm test",
        "latitude": 38.22,
        "longitude": 32.48,
        "radius_km": 10,
        "sector": AGRICULTURE_SECTOR_ID,
    }
    r = client.post("/v1/reports/risk", json=body)
    assert r.status_code == 200
    assert "Agriculture surface proxies" in r.text
    assert "NDVI mean:" in r.text
