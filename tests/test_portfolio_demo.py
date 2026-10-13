"""Single-screen portfolio demo narrative API."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_VERSION,
    FORMULAS,
    ExpectedLossFinancialTranslation,
)
from app.main import app
from app.pipeline.stubs import StubFinancialTranslation, StubFiveLayerPipeline
from app.portfolios.golden import GOLDEN_ANTALYA_ID
from app.schemas.portfolio_demo import (
    EXCLUSION_MISSING_COORDINATES,
    METHODOLOGY_DOCUMENT_VERSION,
    SYNTHETIC_CALIBRATION_BADGE,
)
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail, reset_audit_trail_for_tests


def test_demo_pipeline_uses_eal_v0_3_registry_not_stub_financial() -> None:
    """Guard: a clean merge must not leave the demo on StubFinancialTranslation."""
    assert EXPECTED_LOSS_METHODOLOGY_VERSION == "expected-loss-v0.3"
    assert "expected-loss-v0.3" in FORMULAS
    pipe = StubFiveLayerPipeline(trail=AppendOnlyAuditTrail())
    assert isinstance(pipe.financial_translation, ExpectedLossFinancialTranslation)
    assert not isinstance(pipe.financial_translation, StubFinancialTranslation)


def test_golden_antalya_demo_run_narrative() -> None:
    client = TestClient(app)
    r = client.post("/v1/portfolio/demo-run/golden-antalya?max_assets=8")
    assert r.status_code == 200, r.text
    narrative = r.json()["narrative"]
    assert narrative["portfolio_id"] == GOLDEN_ANTALYA_ID
    assert narrative["asset_count"] == 8
    assert narrative["source"] == "golden-antalya"
    assert narrative["currency"] == "TRY"
    assert narrative["calibration_badge"] == SYNTHETIC_CALIBRATION_BADGE
    assert narrative["methodology"]["document"] == METHODOLOGY_DOCUMENT_VERSION
    assert narrative["methodology"]["expected_loss"] == "expected-loss-v0.3"
    assert narrative["methodology"]["calibration_badge"] == SYNTHETIC_CALIBRATION_BADGE
    coverage = narrative["coverage"]
    # Golden file has 100 assets; max_assets=8 → 92 explicitly excluded (cap), not dropped.
    assert coverage["submitted_count"] == 100
    assert coverage["analyzed_count"] == 8
    assert coverage["excluded_count"] == 92
    assert coverage["message"] == (
        "Analyzed 8 of 100 assets (92 excluded: demo max_assets cap)"
    )
    assert coverage["eal_scope"] == "analyzed assets only"
    assert all(
        row["reason"] == "beyond demo max_assets cap" for row in coverage["excluded"]
    )
    for key in ("upload", "hazard", "expected_loss", "adaptation", "avoided_loss"):
        assert key in narrative
        assert "message" in narrative[key]
        assert narrative[key]["calibration_badge"] == SYNTHETIC_CALIBRATION_BADGE
        assert narrative[key].get("methodology_version")
    assert narrative["expected_loss"]["eal_sum"] >= 0
    assert narrative["expected_loss"]["coverage_scope"] == "analyzed assets only"
    assert "analyzed assets only" in narrative["expected_loss"]["message"].lower()
    assert (
        narrative["expected_loss"]["horizon_method"]
        == "not_available_without_climate_scenario_data"
    )
    assert narrative["expected_loss"]["horizon_status"] == "not_available"
    assert "horizon_scales" not in narrative["expected_loss"]
    assert "omitted" in narrative["expected_loss"]["horizon_disclaimer"].lower()
    assert narrative["avoided_loss"]["avoided_loss_sum"] >= 0
    assert "eal_2030_sum" not in narrative["expected_loss"]
    assert "eal_2050_sum" not in narrative["expected_loss"]
    assert all(row["eal_2030"] is None for row in narrative["assets"])
    assert all(row["eal_2050"] is None for row in narrative["assets"])
    assert len(narrative["assets"]) == 8
    # No map payload — geometry is not part of the narrative contract
    assert "map" not in narrative
    assert "tiles" not in narrative
    # Verification walkthrough shows the audit story
    verify = narrative["verification"]
    assert verify is not None
    assert verify["agreement"] == "PASS"
    assert verify["pipeline_eal"] == verify["independent_eal"]
    assert verify["steps"]
    assert verify["trail_record_id"].startswith("atr_")
    assert verify["calibration_badge"] == SYNTHETIC_CALIBRATION_BADGE
    for row in narrative["assets"]:
        assert row["calibration_badge"] == SYNTHETIC_CALIBRATION_BADGE
        assert row["methodology_version"] == "expected-loss-v0.3"
        assert row["eal_audit_record_id"]


def test_golden_rotterdam_port_demo_run_narrative() -> None:
    from app.portfolios.golden import GOLDEN_ROTTERDAM_PORT_ID

    client = TestClient(app)
    r = client.post("/v1/portfolio/demo-run/golden-rotterdam-port?max_assets=5")
    assert r.status_code == 200, r.text
    narrative = r.json()["narrative"]
    assert narrative["portfolio_id"] == GOLDEN_ROTTERDAM_PORT_ID
    assert narrative["source"] == "golden-rotterdam-port"
    assert narrative["currency"] == "EUR"
    assert narrative["asset_count"] == 5
    assert "pack-nl" in (narrative.get("honesty_note") or "").lower() or (
        "not pack-nl" in (narrative.get("honesty_note") or "").lower()
    )
    assert set(narrative["hazard"]["mean_components"]) == {"flood", "extreme_heat", "wildfire", "earthquake"}
    assert narrative["verification"]["agreement"] == "PASS"


def test_demo_run_from_uploaded_assets() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/demo-run",
        json={
            "valuation_date": "2021-07-01",
            "portfolio_id": "demo-mini",
            "max_assets": 2,
            "assets": [
                {
                    "asset_id": "D1",
                    "latitude": 36.88,
                    "longitude": 30.70,
                    "asset_value": 2_000_000,
                    "building_type": "hotel",
                    "use_class": "tourism",
                },
                {
                    "asset_id": "D2",
                    "latitude": 36.86,
                    "longitude": 30.64,
                    "asset_value": 1_200_000,
                    "building_type": "apartment",
                    "use_class": "residential",
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    narrative = r.json()["narrative"]
    assert narrative["asset_count"] == 2
    assert narrative["coverage"]["submitted_count"] == 2
    assert narrative["coverage"]["analyzed_count"] == 2
    assert narrative["coverage"]["excluded_count"] == 0
    assert narrative["upload"]["asset_count"] == 2
    assert narrative["hazard"]["mean_composite_intensity"] >= 0
    assert narrative["verification"]["agreement"] == "PASS"
    assert "risk/score" in narrative["upload"]["message"].lower() or "five-layer" in narrative[
        "upload"
    ]["message"].lower()


def test_demo_partitions_missing_coordinates_into_excluded() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/demo-run",
        json={
            "valuation_date": "2021-07-01",
            "portfolio_id": "demo-partial",
            "max_assets": 10,
            "assets": [
                {
                    "asset_id": "WITH-COORDS",
                    "latitude": 36.88,
                    "longitude": 30.70,
                    "asset_value": 2_000_000,
                    "building_type": "hotel",
                    "use_class": "tourism",
                },
                {
                    "asset_id": "NO-COORDS",
                    "address": "Antalya, TR",
                    "asset_value": 1_000_000,
                    "building_type": "apartment",
                    "use_class": "residential",
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    narrative = r.json()["narrative"]
    coverage = narrative["coverage"]
    assert coverage["submitted_count"] == 2
    assert coverage["analyzed_count"] == 1
    assert coverage["excluded_count"] == 1
    assert coverage["message"] == (
        "Analyzed 1 of 2 assets (1 excluded: no coordinates)"
    )
    assert coverage["excluded"] == [
        {
            "asset_id": "NO-COORDS",
            "reason": EXCLUSION_MISSING_COORDINATES,
        }
    ]
    assert [a["asset_id"] for a in narrative["assets"]] == ["WITH-COORDS"]
    assert narrative["expected_loss"]["coverage_scope"] == "analyzed assets only"


def test_demo_zero_analyzable_returns_422_with_exclusion_list() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/demo-run",
        json={
            "valuation_date": "2021-07-01",
            "portfolio_id": "demo-none",
            "assets": [
                {
                    "asset_id": "A-ONLY",
                    "address": "Somewhere",
                    "asset_value": 500_000,
                    "building_type": "office",
                    "use_class": "commercial",
                },
                {
                    "asset_id": "B-ONLY",
                    "address": "Elsewhere",
                    "asset_value": 400_000,
                    "building_type": "retail",
                    "use_class": "commercial",
                },
            ],
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert "error" in body
    assert "No analyzable assets" in body["error"]["message"]
    details = body["error"]["details"]
    assert details["coverage"]["analyzed_count"] == 0
    assert details["coverage"]["excluded_count"] == 2
    assert len(details["excluded"]) == 2
    assert {row["asset_id"] for row in details["excluded"]} == {"A-ONLY", "B-ONLY"}
    assert all(row["reason"] == EXCLUSION_MISSING_COORDINATES for row in details["excluded"])


def test_demo_never_mentions_map_only_view() -> None:
    client = TestClient(app)
    r = client.post("/v1/portfolio/demo-run/golden-antalya?max_assets=3")
    body = r.json()["narrative"]
    blob = str(body).lower()
    assert "map_only" not in blob
    assert body.get("verification") is not None
    assert body.get("coverage") is not None


def test_demo_run_without_database_falls_back_to_file_trail(tmp_path, monkeypatch) -> None:
    """Without DATABASE_URL (local dev only) the demo uses the shared file trail.

    No run row exists on this path, so no run id is returned (STUBS #20).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", None)
    trail_path = tmp_path / "demo_expected_loss.jsonl"
    reset_audit_trail_for_tests(trail_path)
    client = TestClient(app)
    r = client.post("/v1/portfolio/demo-run/golden-antalya?max_assets=2")
    assert r.status_code == 200, r.text
    assert r.json()["run_id"] is None
    narrative = r.json()["narrative"]
    record_id = narrative["verification"]["trail_record_id"]
    trail = get_audit_trail()
    assert trail.path == trail_path
    assert trail.get(record_id) is not None
    assert trail_path.is_file()
    text = trail_path.read_text(encoding="utf-8")
    assert record_id in text
    # Reload from disk — durable across process-local trail instance swap
    reloaded = AppendOnlyAuditTrail(path=trail_path)
    assert reloaded.get(record_id) is not None
