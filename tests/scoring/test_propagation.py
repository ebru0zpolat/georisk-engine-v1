"""GEO-151 actor-tree BFS propagation tests."""

from __future__ import annotations

from app.scoring.propagation import (
    ActorEdge,
    ActorGraph,
    PropagationConfig,
    propagate_actor_tree,
)
from app.scoring.scenario_score import ScenarioScoreResult


def _origin(**overrides: object) -> ScenarioScoreResult:
    base = dict(
        asset_id="asset-001",
        asset_geometry_hash="abc123",
        model_version="scenario_scoring_v1",
        data_snapshot_id="snap-2024-q4",
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


def test_linear_chain_downstream_two_hops() -> None:
    """Linear chain: origin → hop1 → hop2 (max downstream depth)."""
    graph = ActorGraph(
        edges=(
            ActorEdge("origin", "hop1", 1.0),
            ActorEdge("hop1", "hop2", 1.0),
            ActorEdge("hop2", "hop3", 1.0),
        )
    )
    result = propagate_actor_tree(
        origin=_origin(),
        origin_node_id="origin",
        graph=graph,
    )
    assert len(result.propagated_impacts) == 2
    by_node = {item.node_id: item for item in result.propagated_impacts}
    assert by_node["hop1"].hop == 1
    assert by_node["hop2"].hop == 2
    assert "hop3" not in by_node
    assert result.propagation_summary.max_hop_depth_reached == 2


def test_diamond_graph_max_delta_dedup() -> None:
    """Diamond: two paths to ``merge`` — stronger path wins."""
    graph = ActorGraph(
        edges=(
            ActorEdge("origin", "left", 0.5),
            ActorEdge("origin", "right", 0.9),
            ActorEdge("left", "merge", 0.5),
            ActorEdge("right", "merge", 0.5),
        )
    )
    cfg = PropagationConfig(hop_decay=0.55)
    result = propagate_actor_tree(
        origin=_origin(scenario_delta_points=12),
        origin_node_id="origin",
        graph=graph,
        config=cfg,
    )
    merge = next(item for item in result.propagated_impacts if item.node_id == "merge")
    via_right = (0.55**2) * 0.9 * 0.5 * 12.0
    via_left = (0.55**2) * 0.5 * 0.5 * 12.0
    assert merge.attenuated_delta_points == max(via_right, via_left)
    assert merge.path == ("origin", "right", "merge")


def test_cycle_guard_no_infinite_loop() -> None:
    """Cycle a→b→c→a terminates; path revisits blocked; BFS completes within hop cap."""
    graph = ActorGraph(
        edges=(
            ActorEdge("origin", "a", 1.0),
            ActorEdge("a", "b", 1.0),
            ActorEdge("b", "c", 1.0),
            ActorEdge("c", "a", 1.0),
        )
    )
    result = propagate_actor_tree(
        origin=_origin(),
        origin_node_id="origin",
        graph=graph,
    )
    nodes = {item.node_id for item in result.propagated_impacts}
    assert nodes == {"a", "b"}
    assert result.propagation_summary.max_hop_depth_reached == 2


def test_zero_weight_edge_produces_zero_delta() -> None:
    graph = ActorGraph(edges=(ActorEdge("origin", "dead_end", 0.0),))
    result = propagate_actor_tree(
        origin=_origin(scenario_delta_points=12),
        origin_node_id="origin",
        graph=graph,
    )
    dead = next(item for item in result.propagated_impacts if item.node_id == "dead_end")
    assert dead.attenuated_delta_points == 0.0
    assert dead.attenuation_factor == 0.0


def test_calibration_hop1_delta() -> None:
    """hop-1 delta = 12 × 0.55 × 0.8 = 5.28 ± 0.1."""
    graph = ActorGraph(edges=(ActorEdge("origin", "supplier", 0.8),))
    result = propagate_actor_tree(
        origin=_origin(scenario_delta_points=12, baseline_score=60, scenario_score=72),
        origin_node_id="origin",
        graph=graph,
        config=PropagationConfig(hop_decay=0.55),
    )
    hop1 = next(item for item in result.propagated_impacts if item.node_id == "supplier")
    assert hop1.hop == 1
    assert abs(hop1.attenuated_delta_points - 5.28) <= 0.1
    assert abs(hop1.attenuation_factor - (0.55 * 0.8)) <= 0.001


def test_scoring_provenance_carried_from_origin() -> None:
    origin = _origin(
        asset_geometry_hash="geom-deadbeef",
        data_snapshot_id="snap-test",
        coefficient_table_version="scenario_coefficients_v1.0",
        coefficient_table_hash="hash-xyz",
        model_version="scenario_scoring_v1",
    )
    result = propagate_actor_tree(
        origin=origin,
        origin_node_id="origin",
        graph=ActorGraph(edges=()),
    )
    prov = result.scoring_provenance
    assert prov.asset_geometry_hash == "geom-deadbeef"
    assert prov.data_snapshot_id == "snap-test"
    assert prov.coefficient_table_version == "scenario_coefficients_v1.0"
    assert prov.coefficient_table_hash == "hash-xyz"
    assert prov.model_version == "scenario_scoring_v1"


def test_severity_critical_at_70() -> None:
    graph = ActorGraph(edges=(ActorEdge("origin", "node", 1.0),))
    result = propagate_actor_tree(
        origin=_origin(scenario_delta_points=20, baseline_score=55, scenario_score=75),
        origin_node_id="origin",
        graph=graph,
        config=PropagationConfig(hop_decay=1.0),
    )
    direct = result.direct_impacts[0]
    assert direct.severity == "CRITICAL"
    propagated = result.propagated_impacts[0]
    assert propagated.severity == "CRITICAL"
