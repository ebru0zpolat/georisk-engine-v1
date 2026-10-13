from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.services.asset_snapshot_store import clear_snapshots

SCENARIO_BODY_TEMPLATE = {
    "scenario_config": {
        "model": "CMIP6",
        "pathway": "SSP5-8.5",
        "target_year": 2050,
        "hazards": ["flood", "drought", "wildfire"],
    },
    "parameters": {
        "return_period": [10, 50, 100],
        "spatial_resolution": "100m",
    },
    "metadata": {
        "client_context": "tsrs-compliance-audit",
        "workflow_id": "deerflow-skill-exec-001",
    },
}


def test_scenario_run_response_contract() -> None:
    clear_snapshots()
    client = TestClient(app)

    preview = client.post(
        "/v1/risk/preview",
        json={"location": "39.97, 32.74"},
    )
    assert preview.status_code == 200
    asset_id = preview.json()["audit_id"]

    run = client.post(
        "/v1/scenario/run",
        json={"asset_id": asset_id, **SCENARIO_BODY_TEMPLATE},
    )
    assert run.status_code == 200
    data = run.json()

    assert data["status"] == "completed"
    assert data["scenario_id"].startswith("scen_")
    assert "flood" in data["hazard_results"]
    flood = data["hazard_results"]["flood"]
    assert "severity_index" in flood
    assert "affected_fraction" in flood
    assert "10y" in flood["return_periods"]
    assert "50y" in flood["return_periods"]
    assert "100y" in flood["return_periods"]

    assert data["shocks"]["correlated_events"]
    assert 0 <= data["shocks"]["systemic_risk_score"] <= 1

    assert data["propagation"]["node"]
    assert data["propagation"]["impact_path"][0]["tier"] == "direct"
    assert data["propagation"]["impact_path"][0]["target"] == "production_capacity"
    assert len(data["propagation"]["impact_path"]) >= 2
    assert any(
        step["tier"] == "supply_chain_tier1"
        for step in data["propagation"]["impact_path"]
    )

    assert data["audit_context"]["linked_audit_ids"]
    assert "Deterministic Engine" in data["audit_context"]["disclaimer"]

    scoring = data["scenario_scoring"]
    assert scoring["baseline_score"] >= 0
    assert scoring["scenario_score"] >= scoring["baseline_score"] or scoring["scenario_delta_points"] <= 0
    assert scoring["coefficient_table_version"] == "scenario_coefficients_v1.0"
    assert len(scoring["coefficient_table_hash"]) == 64
    assert scoring["asset_geometry_hash"]
    assert scoring["hazard_multiplier_type"] == "weighted_effective"
    assert scoring["hazard_driver_multipliers"]
    assert scoring["hazard_multiplier"] >= 1.0
    assert scoring["confidence_reasons"]
    assert scoring["drivers"]


def test_scenario_run_reproducible_same_inputs() -> None:
    clear_snapshots()
    client = TestClient(app)
    preview = client.post("/v1/risk/preview", json={"location": "36.85, 30.75"})
    asset_id = preview.json()["audit_id"]
    body = {"asset_id": asset_id, **SCENARIO_BODY_TEMPLATE}

    r1 = client.post("/v1/scenario/run", json=body).json()
    r2 = client.post("/v1/scenario/run", json=body).json()
    assert r1["scenario_scoring"] == r2["scenario_scoring"]


def test_scenario_run_unknown_asset() -> None:
    clear_snapshots()
    client = TestClient(app)
    body = {
        "asset_id": "00000000-0000-4000-8000-000000000099",
        **SCENARIO_BODY_TEMPLATE,
    }
    run = client.post("/v1/scenario/run", json=body)
    assert run.status_code == 404
    assert run.json()["error"]["code"] == "asset_not_found"
