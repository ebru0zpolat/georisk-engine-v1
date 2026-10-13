"""Universal asset schema (§3.1), RiskBatchAsset extension, valuation_date, B.7, CSV/GeoJSON."""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.main import app
from app.schemas.adaptation import AdaptationOutcome, MeasureStatus
from app.schemas.portfolio import (
    PORTFOLIO_MAX_ASSETS,
    PortfolioUploadRequest,
    UniversalAsset,
)
from app.schemas.risk import RiskBatchAsset, RiskBatchRequest
from app.services.portfolio_ingest import parse_portfolio_csv, parse_portfolio_geojson


def test_risk_batch_asset_accepts_p0_fields() -> None:
    asset = RiskBatchAsset(
        id="B1",
        lat=41.0,
        lon=29.0,
        asset_value=1_000_000,
        building_type="office",
        use_class="commercial",
        construction_year=2010,
        floors=12,
        ltv=0.6,
        adaptation=AdaptationOutcome(measure_status=MeasureStatus.recommended),
    )
    assert asset.asset_value == 1_000_000
    assert asset.adaptation is not None


def test_risk_batch_request_valuation_date_optional() -> None:
    body = RiskBatchRequest(
        preset_id="industrial_v1",
        valuation_date=date(2020, 1, 1),
        assets=[RiskBatchAsset(id="A", lat=41.0, lon=29.0)],
    )
    assert body.valuation_date == date(2020, 1, 1)
    # Backward compatible: id/lat/lon only still valid
    bare = RiskBatchRequest(
        preset_id="industrial_v1",
        assets=[RiskBatchAsset(id="A", lat=41.0, lon=29.0)],
    )
    assert bare.valuation_date is None


def test_universal_asset_to_batch_asset() -> None:
    ua = UniversalAsset(
        asset_id="X",
        latitude=36.8,
        longitude=30.7,
        asset_value=2e6,
        building_type="hotel",
        use_class="tourism",
        adaptation=AdaptationOutcome(measure_status=MeasureStatus.implemented),
    )
    batch = ua.to_batch_asset()
    assert batch.id == "X"
    assert batch.asset_value == 2e6
    assert batch.adaptation is not None


def test_universal_asset_requires_location() -> None:
    with pytest.raises(ValidationError):
        UniversalAsset(
            asset_id="A1",
            asset_value=1_000_000,
            building_type="residential",
            use_class="multifamily",
        )


def test_adaptation_outcome_annex_b7_fields() -> None:
    outcome = AdaptationOutcome(
        measure_id="cool-roof-v1",
        measure_status=MeasureStatus.implemented,
        implemented_date=date(2024, 6, 1),
        post_implementation_review="Peak indoor temp down ~3C.",
        share_outcome_consented=True,
        anonymise_in_aggregate=True,
    )
    asset = UniversalAsset(
        asset_id="TR-ANT-001",
        latitude=36.8969,
        longitude=30.7133,
        asset_value=4_200_000,
        building_type="apartment",
        use_class="residential",
        adaptation=outcome,
    )
    assert asset.adaptation is not None
    assert asset.adaptation.measure_status == MeasureStatus.implemented


def test_portfolio_requires_valuation_date() -> None:
    with pytest.raises(ValidationError):
        PortfolioUploadRequest(
            assets=[
                UniversalAsset(
                    asset_id="A1",
                    latitude=41.0,
                    longitude=29.0,
                    asset_value=100.0,
                    building_type="office",
                    use_class="commercial",
                )
            ]
        )


def test_portfolio_max_assets() -> None:
    assets = [
        UniversalAsset(
            asset_id=f"A{i}",
            latitude=41.0,
            longitude=29.0,
            asset_value=100.0 + i,
            building_type="office",
            use_class="commercial",
        )
        for i in range(PORTFOLIO_MAX_ASSETS + 1)
    ]
    with pytest.raises(ValidationError):
        PortfolioUploadRequest(valuation_date=date(2024, 1, 1), assets=assets)


def test_parse_portfolio_csv_happy_path() -> None:
    csv_text = (
        "asset_id,address,lat,lon,asset_value,building_type,use_class,"
        "construction_year,floors,ltv,measure_status,implemented_date,"
        "share_outcome_consented,anonymise_in_aggregate,existing_adaptation_measures\n"
        "TR-001,,36.88,30.70,1500000,hotel,tourism,2005,8,0.65,implemented,"
        "2023-08-15,true,true,cool roof|shutters\n"
        'TR-002,"Kadıköy, Istanbul",,,2000000,apartment,residential,2012,4,,,,,,,\n'
    )
    parsed = parse_portfolio_csv(csv_text, valuation_date=date(2021, 7, 1))
    assert parsed.valuation_date == date(2021, 7, 1)
    assert len(parsed.assets) == 2
    assert parsed.assets[0].adaptation is not None
    assert parsed.assets[0].adaptation.measure_status == MeasureStatus.implemented
    assert parsed.assets[0].existing_adaptation_measures == ["cool roof", "shutters"]
    assert parsed.assets[1].address == "Kadıköy, Istanbul"


def test_parse_portfolio_geojson_happy_path() -> None:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [30.7133, 36.8969]},
                "properties": {
                    "asset_id": "ANT-01",
                    "asset_value": 3_500_000,
                    "building_type": "hotel",
                    "use_class": "tourism",
                    "measure_status": "recommended",
                    "share_outcome_consented": False,
                },
            },
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "id": "ANT-02",
                    "address": "Lara Beach Rd",
                    "asset_value": 1_200_000,
                    "building_type": "apartment",
                    "use_class": "residential",
                    "adaptation": {
                        "measure_status": "implemented",
                        "implemented_date": "2022-01-15",
                        "post_implementation_review": "Flood barrier held.",
                        "share_outcome_consented": True,
                        "anonymise_in_aggregate": True,
                    },
                },
            },
        ],
    }
    parsed = parse_portfolio_geojson(fc, valuation_date=date(2019, 12, 31))
    assert len(parsed.assets) == 2
    assert parsed.assets[0].latitude == pytest.approx(36.8969)
    assert parsed.assets[0].adaptation is not None
    assert parsed.assets[0].adaptation.measure_status == MeasureStatus.recommended
    assert parsed.assets[1].address == "Lara Beach Rd"
    assert parsed.assets[1].adaptation is not None
    assert parsed.assets[1].adaptation.implemented_date == date(2022, 1, 15)


def test_post_portfolio_assets_json() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/assets",
        json={
            "valuation_date": "2021-07-28",
            "portfolio_id": "demo-antalya",
            "assets": [
                {
                    "asset_id": "ANT-01",
                    "latitude": 36.8969,
                    "longitude": 30.7133,
                    "asset_value": 3_500_000,
                    "building_type": "hotel",
                    "use_class": "tourism",
                    "adaptation": {
                        "measure_status": "recommended",
                        "share_outcome_consented": False,
                        "anonymise_in_aggregate": True,
                    },
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["portfolio_id"] == "demo-antalya"
    assert data["source"] == "json"
    assert data["assets"][0]["adaptation"]["measure_status"] == "recommended"


def test_post_portfolio_csv_upload() -> None:
    client = TestClient(app)
    csv_bytes = (
        b"asset_id,lat,lon,asset_value,building_type,use_class,measure_status\n"
        b"IST-01,41.015,28.98,1200000,office,commercial,accepted\n"
    )
    r = client.post(
        "/v1/portfolio/upload",
        data={"valuation_date": "2019-12-31", "portfolio_id": "pf-csv-1"},
        files={"file": ("portfolio.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "csv"
    assert r.json()["asset_count"] == 1


def test_post_portfolio_geojson_upload() -> None:
    client = TestClient(app)
    body = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [29.0, 41.0]},
                "properties": {
                    "asset_id": "G1",
                    "asset_value": 500000,
                    "building_type": "retail",
                    "use_class": "commercial",
                },
            }
        ],
    }
    r = client.post(
        "/v1/portfolio/upload",
        data={"valuation_date": "2020-06-01"},
        files={
            "file": (
                "portfolio.geojson",
                json.dumps(body).encode(),
                "application/geo+json",
            )
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["source"] == "geojson"
    assert data["assets"][0]["latitude"] == pytest.approx(41.0)


def test_post_portfolio_csv_invalid_rows_envelope() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/upload",
        data={"valuation_date": "2020-01-01"},
        files={
            "file": (
                "bad.csv",
                b"asset_id,asset_value,building_type,use_class\nA,100,office,commercial\n",
                "text/csv",
            )
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
