"""GEO-193 actor graph loader and propagation adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.scoring.actor_graph_loader import (
    DEFAULT_ACTOR_GRAPH_PATH,
    get_default_actor_graph,
    load_actor_graph,
    resolve_origin_node_id,
)
from app.scoring.propagation import propagate_actor_tree
from app.scoring.propagation_adapter import propagation_to_scenario_response
from app.scoring.scenario_score import ScenarioScoreResult
from app.services.asset_snapshot_store import AssetSnapshot


def _snapshot(**overrides: object) -> AssetSnapshot:
    base = dict(
        audit_id="00000000-0000-4000-8000-000000000001",
        asset_name="Erdemir Steel",
        latitude=41.0,
        longitude=31.0,
        radius_km=10.0,
        sector="industrial",
        overall_score=60,
        components={"ocean": 60, "pollution": 60, "land": 60, "industrial": 60},
        model_version="scenario_scoring_v1",
        data_snapshot_id="snap-test",
        asset_geometry_hash="abc123",
        uses_connector_fallback=False,
    )
    base.update(overrides)
    return AssetSnapshot(**base)  # type: ignore[arg-type]


def _score_result(**overrides: object) -> ScenarioScoreResult:
    base = dict(
        asset_id="asset-001",
        asset_geometry_hash="abc123",
        model_version="scenario_scoring_v1",
        data_snapshot_id="snap-test",
        coefficient_table_version="scenario_coefficients_v1.0",
        coefficient_table_hash="9bf73db0bd19",
        baseline_score=60,
        scenario="SSP5-8.5",
        horizon=2050,
        hazard_score=60,
        exposure_score=60,
        vulnerability_score=60,
        hazard_multiplier=1.367,
        hazard_multiplier_type="weighted_effective",
        hazard_driver_multipliers={"flood": 1.3},
        raw_adjusted_hazard=81.0,
        adjusted_hazard_score=81,
        raw_scenario_score=72.0,
        scenario_score=72,
        scenario_delta_points=12,
        scenario_delta_pct=20.0,
        scenario_delta_cap_applied=False,
        confidence="medium",
        confidence_reasons=["baseline_present"],
        drivers=["flood"],
    )
    base.update(overrides)
    return ScenarioScoreResult(**base)  # type: ignore[arg-type]


def test_default_actor_graph_fixture_loads() -> None:
    loaded = load_actor_graph(DEFAULT_ACTOR_GRAPH_PATH)
    assert loaded.metadata.default_origin_node_id == "production_capacity"
    assert "logistics_hub_istanbul" in loaded.metadata.node_ids
    assert len(loaded.graph.edges) >= 4


def test_resolve_origin_falls_back_to_default() -> None:
    loaded = get_default_actor_graph()
    snapshot = _snapshot()
    origin = resolve_origin_node_id(
        snapshot,
        loaded.metadata,
        facility_slug="erdemir_steel",
    )
    assert origin == "production_capacity"


def test_propagation_adapter_maps_direct_and_tier1() -> None:
    loaded = get_default_actor_graph()
    result = propagate_actor_tree(
        origin=_score_result(scenario_delta_points=12),
        origin_node_id="production_capacity",
        graph=loaded.graph,
        node_baselines=loaded.metadata.baselines,
    )
    response = propagation_to_scenario_response(
        result,
        facility_node="erdemir_steel",
        node_labels=loaded.metadata.labels,
    )
    assert response.node == "erdemir_steel"
    assert response.impact_path[0].tier == "direct"
    assert response.impact_path[0].target == "production_capacity"
    assert response.impact_path[0].loss == pytest.approx(0.48, abs=0.01)
    tier1_targets = {
        step.target for step in response.impact_path if step.tier == "supply_chain_tier1"
    }
    assert "logistics_hub_istanbul" in tier1_targets
    assert "raw_material_sourcing" in tier1_targets


def test_load_actor_graph_rejects_unknown_edge_nodes(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"version":"1.0","default_origin_node_id":"a","nodes":[{"id":"a","label":"A","sector":"industrial"}],'
        '"edges":[{"source":"a","target":"missing","dependency_weight":1.0}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown nodes"):
        load_actor_graph(bad)
