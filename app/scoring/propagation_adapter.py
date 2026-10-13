"""GEO-193 adapter: PropagationResult → ScenarioPropagation API contract."""

from __future__ import annotations

from app.schemas.scenario import ImpactPathStep, ScenarioPropagation
from app.scoring.propagation import DirectImpact, PropagatedImpact, PropagationResult
from app.scoring.scenario_pipeline import SCENARIO_DELTA_CAP_POINTS


def _delta_to_loss(delta_points: float) -> float:
    cap = float(SCENARIO_DELTA_CAP_POINTS)
    return round(min(1.0, max(0.0, delta_points / cap)), 2)


def _tier_for_propagated(impact: PropagatedImpact) -> str:
    if impact.direction == "upstream":
        return f"upstream_tier{impact.hop}"
    return f"supply_chain_tier{impact.hop}"


def _impact_target(node_id: str, labels: dict[str, str]) -> str:
    """API ``target`` uses graph node id (stable key for DeerFlow consumers)."""
    return node_id


def propagation_to_scenario_response(
    result: PropagationResult,
    *,
    facility_node: str,
    node_labels: dict[str, str],
) -> ScenarioPropagation:
    impact_path: list[ImpactPathStep] = []

    direct: DirectImpact = result.direct_impacts[0]
    impact_path.append(
        ImpactPathStep(
            tier="direct",
            target=_impact_target(direct.node_id, node_labels),
            loss=_delta_to_loss(direct.scenario_delta_points),
        )
    )

    for propagated in result.propagated_impacts:
        impact_path.append(
            ImpactPathStep(
                tier=_tier_for_propagated(propagated),
                target=_impact_target(propagated.node_id, node_labels),
                loss=_delta_to_loss(propagated.attenuated_delta_points),
            )
        )

    return ScenarioPropagation(node=facility_node, impact_path=impact_path)
