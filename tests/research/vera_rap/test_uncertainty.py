from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap import (
    ClaimNode,
    ClaimObject,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    EvidenceObject,
    GraphEdge,
    PropagationRule,
    PropagationRuleType,
    Provenance,
    ResolutionRequirement,
    ResolutionRequirementType,
    ContradictionObject,
    ContradictionStatus,
    ContradictionType,
    ThresholdMetric,
    ThresholdOperator,
    Uncertainty,
    UncertaintyComponent,
    UncertaintyDirection,
    UncertaintyProfile,
    UncertaintyThreshold,
    UncertaintyType,
    VerificationStatus,
    derive_claim_uncertainty,
    evaluate_uncertainty_gate,
    propagate_uncertainty,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def component(
    subject: str,
    lower: float | None = 10,
    upper: float | None = 20,
    confidence: float | None = 0.8,
    *,
    unit: str | None = "u",
    kind: UncertaintyType = UncertaintyType.MEASUREMENT,
) -> UncertaintyComponent:
    return UncertaintyComponent(
        f"component-{subject}",
        kind,
        UncertaintyDirection.EPISTEMIC,
        subject,
        lower,
        upper,
        confidence,
        unit=unit,
        source_ids=(subject,),
        method="fixture",
        metadata={"nested": [1]},
    )


def profile(
    subject: str, item: UncertaintyComponent | None = None
) -> UncertaintyProfile:
    item = item or component(subject)
    unresolved = (
        (item.component_id,) if item.lower is None and item.confidence is None else ()
    )
    return UncertaintyProfile(
        f"profile-{subject}",
        subject,
        (item,),
        "declared",
        item.lower,
        item.upper,
        item.confidence,
        unresolved,
        (),
        (subject,),
        NOW,
    )


def rule(
    kind: PropagationRuleType,
    subjects: tuple[str, ...],
    target: str = "C1",
    parameters: dict[str, object] | None = None,
    assumptions: tuple[str, ...] = (),
) -> PropagationRule:
    return PropagationRule(
        "rule-1",
        kind,
        "1",
        subjects,
        target,
        parameters or {},
        assumptions,
        "explicit fixture rule",
    )


def evidence(
    evidence_id: str,
    uncertainty: Uncertainty | None,
    *,
    status: VerificationStatus = VerificationStatus.VERIFIED,
    until: datetime | None = None,
) -> EvidenceObject:
    digest = ("a" if evidence_id == "E1" else "b") * 64
    source = f"source-{evidence_id}"
    return EvidenceObject(
        evidence_id,
        "generic",
        source,
        f"urn:test:{evidence_id}",
        digest,
        NOW,
        NOW,
        NOW,
        until,
        None,
        None,
        {"value": 1},
        "u",
        uncertainty,
        "test",
        status,
        provenance=Provenance(source, "fixture", digest),
    )


def graph_for_claim(
    first: Uncertainty | None, second: Uncertainty | None = None
) -> EvidenceGraph:
    ids = ("E1",) if second is None else ("E1", "E2")
    claim = ClaimObject(
        "C1",
        "represents",
        "subject",
        1,
        "u",
        EpistemicState.OBSERVED,
        ids,
        uncertainty=None,
        created_at=NOW,
        derivation_method="fixture",
    )
    nodes = [EvidenceNode(evidence("E1", first)), ClaimNode(claim)]
    if second is not None:
        nodes.append(EvidenceNode(evidence("E2", second)))
    return EvidenceGraph(
        tuple(nodes), tuple(GraphEdge(item, "C1", EdgeType.SUPPORTS) for item in ids)
    )


def test_components_profiles_and_rules_are_immutable() -> None:
    item, aggregate, propagation = (
        component("E1"),
        profile("E1"),
        rule(PropagationRuleType.PASS_THROUGH, ("E1",)),
    )
    for value, name in (
        (item, "lower"),
        (aggregate, "effective_lower"),
        (propagation, "version"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, name, 0)
    with pytest.raises(TypeError):
        item.metadata["nested"] += (2,)  # type: ignore[index]


def test_enum_coercion_invalid_bounds_nonfinite_and_confidence_rejected() -> None:
    for value in (
        UncertaintyType.MODEL,
        UncertaintyDirection.MIXED,
        PropagationRuleType.PASS_THROUGH,
    ):
        with pytest.raises(TypeError):
            bool(value)
        with pytest.raises(TypeError):
            str(value)
    with pytest.raises(ValueError, match="lower"):
        component("E1", 2, 1)
    with pytest.raises(ValueError, match="finite"):
        component("E1", float("nan"), 1)
    with pytest.raises(ValueError, match="confidence"):
        component("E1", confidence=1.1)


def test_deterministic_fingerprints_and_insertion_order_independence() -> None:
    first = component("E1")
    second = replace(first, metadata={"b": 2, "a": 1})
    third = replace(first, metadata={"a": 1, "b": 2})
    assert second.fingerprint == third.fingerprint
    assert profile("E1", first).fingerprint == profile("E1", first).fingerprint


def test_direct_observation_preserves_uncertainty() -> None:
    result = propagate_uncertainty(
        (profile("E1"),), rule(PropagationRuleType.PASS_THROUGH, ("E1",)), at=NOW
    )
    assert (
        result.output_profile.effective_lower,
        result.output_profile.effective_upper,
        result.output_profile.effective_confidence,
    ) == (10, 20, 0.8)
    assert result.output_profile.components == profile("E1").components


def test_interval_envelope_does_not_average_away_uncertainty() -> None:
    result = propagate_uncertainty(
        (profile("E1"), profile("E2", component("E2", 12, 25))),
        rule(PropagationRuleType.INTERVAL_ENVELOPE, ("E1", "E2")),
        at=NOW,
    )
    assert (
        result.output_profile.effective_lower,
        result.output_profile.effective_upper,
    ) == (10, 25)


def test_downstream_confidence_cannot_exceed_weakest_dependency_by_default() -> None:
    result = propagate_uncertainty(
        (
            profile("E1", component("E1", confidence=0.95)),
            profile("E2", component("E2", confidence=0.70)),
        ),
        rule(PropagationRuleType.CONFIDENCE_FLOOR, ("E1", "E2")),
        at=NOW,
    )
    assert result.output_profile.effective_confidence == 0.70


def test_explicit_widening_and_transformation_penalty() -> None:
    for kind in (
        PropagationRuleType.UNCERTAINTY_WIDENING,
        PropagationRuleType.TRANSFORMATION_PENALTY,
    ):
        result = propagate_uncertainty(
            (profile("E1"),),
            rule(
                kind, ("E1",), parameters={"amount": 2}, assumptions=("declared loss",)
            ),
            at=NOW,
        )
        assert (
            result.output_profile.effective_lower,
            result.output_profile.effective_upper,
        ) == (8, 22)
        assert len(result.output_profile.components) == 2


def test_missing_uncertainty_is_not_zero_uncertainty() -> None:
    graph = graph_for_claim(None)
    result = derive_claim_uncertainty(
        "C1", graph, (rule(PropagationRuleType.PASS_THROUGH, ("E1",)),), at=NOW
    )
    assert result.output_profile.effective_lower is None
    assert result.output_profile.unresolved_components
    assert (
        result.output_profile.components[0].uncertainty_type
        is UncertaintyType.MISSING_INFORMATION
    )


def test_structural_non_numeric_uncertainty_is_first_class() -> None:
    item = component("E1", None, None, None, unit=None, kind=UncertaintyType.STRUCTURAL)
    assert profile("E1", item).unresolved_components == (item.component_id,)


def test_unresolved_contradiction_cannot_reduce_uncertainty() -> None:
    contradiction = ContradictionObject(
        "X1",
        ContradictionType.DIRECT_VALUE_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        ("E1", "E2"),
        detected_at=NOW,
        conflict_dimensions=("value",),
        resolution_requirements=(
            ResolutionRequirement(
                "R1",
                ResolutionRequirementType.HUMAN_REVIEW_REQUIRED,
                ("E1", "E2"),
                {},
                True,
                "review",
            ),
        ),
    )
    penalty = propagate_uncertainty(
        (profile("E1"),),
        rule(PropagationRuleType.CONTRADICTION_PENALTY, ("E1",)),
        at=NOW,
        contradictions=(contradiction,),
    )
    assert any(
        item.uncertainty_type is UncertaintyType.CONTRADICTION
        for item in penalty.output_profile.components
    )
    with pytest.raises(ValueError, match="contradiction"):
        propagate_uncertainty(
            (profile("E1"), profile("E2")),
            rule(
                PropagationRuleType.INDEPENDENT_EVIDENCE_REDUCTION,
                ("E1", "E2"),
                parameters={"independence_declared": True, "reduction_factor": 0.5},
            ),
            at=NOW,
            graph=graph_for_claim(
                Uncertainty("range", 10, 20), Uncertainty("range", 10, 20)
            ),
            contradictions=(contradiction,),
        )


def test_independent_evidence_reduction_requires_explicit_independence() -> None:
    graph = graph_for_claim(Uncertainty("range", 10, 20), Uncertainty("range", 10, 20))
    inputs = (profile("E1"), profile("E2"))
    with pytest.raises(ValueError, match="independence"):
        propagate_uncertainty(
            inputs,
            rule(
                PropagationRuleType.INDEPENDENT_EVIDENCE_REDUCTION,
                ("E1", "E2"),
                parameters={"reduction_factor": 0.5},
            ),
            at=NOW,
            graph=graph,
        )
    result = propagate_uncertainty(
        inputs,
        rule(
            PropagationRuleType.INDEPENDENT_EVIDENCE_REDUCTION,
            ("E1", "E2"),
            parameters={
                "independence_declared": True,
                "reduction_factor": 0.5,
                "confidence_gain": 0.1,
            },
        ),
        at=NOW,
        graph=graph,
    )
    assert (
        result.output_profile.effective_lower,
        result.output_profile.effective_upper,
    ) == (12.5, 17.5)
    assert result.output_profile.effective_confidence == 0.9


def test_incompatible_uncertainty_units_fail_closed() -> None:
    with pytest.raises(ValueError, match="units"):
        propagate_uncertainty(
            (
                profile("E1", component("E1", unit="metres")),
                profile("E2", component("E2", unit="percent")),
            ),
            rule(PropagationRuleType.INTERVAL_ENVELOPE, ("E1", "E2")),
            at=NOW,
        )


def test_claim_and_parent_claim_propagation() -> None:
    graph = graph_for_claim(Uncertainty("range", 10, 20, 0.8, "declared"))
    result = derive_claim_uncertainty(
        "C1", graph, (rule(PropagationRuleType.PASS_THROUGH, ("E1",)),), at=NOW
    )
    assert result.target_subject_id == "C1"
    c2 = ClaimObject(
        "C2",
        "derives",
        "subject",
        2,
        None,
        EpistemicState.INFERRED,
        parent_claim_ids=("C1",),
        uncertainty=Uncertainty("range", 10, 20, 0.8),
        created_at=NOW,
        derivation_method="fixture",
    )
    graph = EvidenceGraph(
        (*graph.nodes.values(), ClaimNode(c2)),
        (*graph.edges, GraphEdge("C1", "C2", EdgeType.DERIVES)),
    )
    parent = derive_claim_uncertainty(
        "C2",
        graph,
        (
            rule(PropagationRuleType.PASS_THROUGH, ("E1",), "C1"),
            replace(
                rule(PropagationRuleType.PASS_THROUGH, ("C1",), "C2"),
                rule_id="rule-2",
            ),
        ),
        at=NOW,
    )
    assert parent.output_profile.effective_confidence == 0.8


def test_stale_evidence_degrades_new_artifact_but_history_is_immutable() -> None:
    old = evidence(
        "E1", Uncertainty("range", 10, 20, 0.8), until=datetime(2026, 1, 2, tzinfo=UTC)
    )
    claim = ClaimObject(
        "C1",
        "represents",
        "subject",
        1,
        None,
        EpistemicState.OBSERVED,
        ("E1",),
        created_at=NOW,
        derivation_method="fixture",
    )
    graph = EvidenceGraph(
        (EvidenceNode(old), ClaimNode(claim)),
        (GraphEdge("E1", "C1", EdgeType.SUPPORTS),),
    )
    propagation_rule = rule(PropagationRuleType.PASS_THROUGH, ("E1",))
    historical = derive_claim_uncertainty("C1", graph, (propagation_rule,), at=NOW)
    later = derive_claim_uncertainty(
        "C1", graph, (propagation_rule,), at=datetime(2026, 2, 1, tzinfo=UTC)
    )
    assert not historical.output_profile.unresolved_components
    assert later.output_profile.unresolved_components
    assert not historical.output_profile.unresolved_components


def test_uncertainty_gate_blocks_when_threshold_not_met_and_passes_when_met() -> None:
    aggregate = profile("C1", component("C1", confidence=0.78))
    blocked = evaluate_uncertainty_gate(
        aggregate,
        UncertaintyThreshold(
            "T1",
            ThresholdMetric.CONFIDENCE_MIN,
            ThresholdOperator.GREATER_THAN_OR_EQUAL,
            0.9,
            None,
            (),
            True,
            "minimum",
        ),
    )
    passed = evaluate_uncertainty_gate(
        aggregate,
        UncertaintyThreshold(
            "T2",
            ThresholdMetric.CONFIDENCE_MIN,
            ThresholdOperator.GREATER_THAN_OR_EQUAL,
            0.7,
            None,
            (),
            True,
            "minimum",
        ),
    )
    assert not blocked.passed and passed.passed


def test_serialization_round_trips_and_recomputes_fingerprints() -> None:
    item = component("E1")
    restored = UncertaintyComponent.from_dict(json.loads(item.canonical_json()))
    assert restored == item and restored.fingerprint == item.fingerprint
    aggregate = profile("E1")
    assert (
        UncertaintyProfile.from_dict(json.loads(aggregate.canonical_json()))
        == aggregate
    )
    propagation_rule = rule(PropagationRuleType.PASS_THROUGH, ("E1",))
    assert (
        PropagationRule.from_dict(propagation_rule.canonical_dict()).fingerprint
        == propagation_rule.fingerprint
    )
    result = propagate_uncertainty((aggregate,), propagation_rule, at=NOW)
    assert (
        UncertaintyProfile.from_dict(result.output_profile.canonical_dict())
        == result.output_profile
    )
