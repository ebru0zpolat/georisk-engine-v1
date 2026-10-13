"""GEO-151 actor-tree BFS propagation — deterministic delta attenuation across dependencies."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from app.scoring.scenario_score import ScenarioScoreResult

DEFAULT_HOP_DECAY = 0.55
DEFAULT_MAX_HOPS_UPSTREAM = 2
DEFAULT_MAX_HOPS_DOWNSTREAM = 2

SeverityLevel = Literal["NORMAL", "ELEVATED", "CRITICAL"]
PropagationDirection = Literal["upstream", "downstream"]

_SEVERITY_RANK: dict[SeverityLevel, int] = {
    "NORMAL": 0,
    "ELEVATED": 1,
    "CRITICAL": 2,
}


@dataclass(frozen=True)
class PropagationConfig:
    hop_decay: float = DEFAULT_HOP_DECAY
    max_hops_upstream: int = DEFAULT_MAX_HOPS_UPSTREAM
    max_hops_downstream: int = DEFAULT_MAX_HOPS_DOWNSTREAM


@dataclass(frozen=True)
class ActorEdge:
    """Directed dependency edge: ``source_id`` → ``target_id`` (downstream flow)."""

    source_id: str
    target_id: str
    dependency_weight: float


@dataclass(frozen=True)
class ActorGraph:
    edges: tuple[ActorEdge, ...]


@dataclass(frozen=True)
class ScoringProvenance:
    asset_geometry_hash: str
    data_snapshot_id: str
    coefficient_table_version: str
    coefficient_table_hash: str
    model_version: str


@dataclass(frozen=True)
class DirectImpact:
    node_id: str
    scenario_delta_points: float
    scenario_score: int
    severity: SeverityLevel


@dataclass(frozen=True)
class PropagatedImpact:
    node_id: str
    hop: int
    direction: PropagationDirection
    attenuation_factor: float
    attenuated_delta_points: float
    attenuated_scenario_score: float
    severity: SeverityLevel
    path: tuple[str, ...]


@dataclass(frozen=True)
class PropagationSummary:
    total_nodes_affected: int
    severity_escalations: int
    max_hop_depth_reached: int


@dataclass(frozen=True)
class PropagationResult:
    scoring_provenance: ScoringProvenance
    direct_impacts: tuple[DirectImpact, ...]
    propagated_impacts: tuple[PropagatedImpact, ...]
    propagation_summary: PropagationSummary


def classify_severity(attenuated_scenario_score: float) -> SeverityLevel:
    if attenuated_scenario_score >= 70:
        return "CRITICAL"
    if attenuated_scenario_score >= 50:
        return "ELEVATED"
    return "NORMAL"


def _provenance_from_origin(origin: ScenarioScoreResult) -> ScoringProvenance:
    return ScoringProvenance(
        asset_geometry_hash=origin.asset_geometry_hash,
        data_snapshot_id=origin.data_snapshot_id,
        coefficient_table_version=origin.coefficient_table_version,
        coefficient_table_hash=origin.coefficient_table_hash,
        model_version=origin.model_version,
    )


def _adjacency_downstream(graph: ActorGraph) -> dict[str, list[tuple[str, float]]]:
    adj: dict[str, list[tuple[str, float]]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.source_id, []).append(
            (edge.target_id, edge.dependency_weight)
        )
    return adj


def _adjacency_upstream(graph: ActorGraph) -> dict[str, list[tuple[str, float]]]:
    """Reverse edges: walk from consumer to supplier."""
    adj: dict[str, list[tuple[str, float]]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.target_id, []).append(
            (edge.source_id, edge.dependency_weight)
        )
    return adj


def _bfs_propagate(
    *,
    origin_node_id: str,
    origin_delta: float,
    adjacency: dict[str, list[tuple[str, float]]],
    max_hops: int,
    hop_decay: float,
    direction: PropagationDirection,
    node_baselines: dict[str, int],
    default_baseline: int,
) -> dict[str, PropagatedImpact]:
    """Return best (max attenuated delta) impact per reached node."""
    best: dict[str, PropagatedImpact] = {}
    queue: deque[tuple[str, int, float, tuple[str, ...]]] = deque(
        [(origin_node_id, 0, 1.0, (origin_node_id,))]
    )

    while queue:
        node_id, hop, weight_product, path = queue.popleft()
        if hop >= max_hops:
            continue

        for neighbor_id, edge_weight in adjacency.get(node_id, []):
            if neighbor_id in path:
                continue

            next_hop = hop + 1
            next_weight_product = weight_product * edge_weight
            attenuation_factor = (hop_decay**next_hop) * next_weight_product
            attenuated_delta = origin_delta * attenuation_factor
            baseline = node_baselines.get(neighbor_id, default_baseline)
            attenuated_score = baseline + attenuated_delta
            candidate = PropagatedImpact(
                node_id=neighbor_id,
                hop=next_hop,
                direction=direction,
                attenuation_factor=attenuation_factor,
                attenuated_delta_points=attenuated_delta,
                attenuated_scenario_score=attenuated_score,
                severity=classify_severity(attenuated_score),
                path=path + (neighbor_id,),
            )

            existing = best.get(neighbor_id)
            if existing is None or candidate.attenuated_delta_points > existing.attenuated_delta_points:
                best[neighbor_id] = candidate

            queue.append((neighbor_id, next_hop, next_weight_product, candidate.path))

    return best


def propagate_actor_tree(
    *,
    origin: ScenarioScoreResult,
    origin_node_id: str,
    graph: ActorGraph,
    node_baselines: dict[str, int] | None = None,
    config: PropagationConfig | None = None,
) -> PropagationResult:
    """BFS propagation from origin; multi-path max-delta wins; cycle-safe."""
    cfg = config or PropagationConfig()
    baselines = node_baselines or {}
    origin_delta = float(origin.scenario_delta_points)

    direct = DirectImpact(
        node_id=origin_node_id,
        scenario_delta_points=origin_delta,
        scenario_score=origin.scenario_score,
        severity=classify_severity(float(origin.scenario_score)),
    )

    downstream = _bfs_propagate(
        origin_node_id=origin_node_id,
        origin_delta=origin_delta,
        adjacency=_adjacency_downstream(graph),
        max_hops=cfg.max_hops_downstream,
        hop_decay=cfg.hop_decay,
        direction="downstream",
        node_baselines=baselines,
        default_baseline=origin.baseline_score,
    )
    upstream = _bfs_propagate(
        origin_node_id=origin_node_id,
        origin_delta=origin_delta,
        adjacency=_adjacency_upstream(graph),
        max_hops=cfg.max_hops_upstream,
        hop_decay=cfg.hop_decay,
        direction="upstream",
        node_baselines=baselines,
        default_baseline=origin.baseline_score,
    )

    merged: dict[str, PropagatedImpact] = {}
    for impacts in (downstream, upstream):
        for node_id, impact in impacts.items():
            existing = merged.get(node_id)
            if existing is None or impact.attenuated_delta_points > existing.attenuated_delta_points:
                merged[node_id] = impact

    propagated = tuple(
        sorted(merged.values(), key=lambda item: (item.hop, item.node_id))
    )
    origin_rank = _SEVERITY_RANK[direct.severity]
    severity_escalations = sum(
        1 for item in propagated if _SEVERITY_RANK[item.severity] > origin_rank
    )
    max_hop = max((item.hop for item in propagated), default=0)

    return PropagationResult(
        scoring_provenance=_provenance_from_origin(origin),
        direct_impacts=(direct,),
        propagated_impacts=propagated,
        propagation_summary=PropagationSummary(
            total_nodes_affected=1 + len(propagated),
            severity_escalations=severity_escalations,
            max_hop_depth_reached=max_hop,
        ),
    )
