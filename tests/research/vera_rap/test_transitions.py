from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap import (
    ClaimEvaluationResult,
    ClaimNode,
    CognitiveState,
    CognitiveTransition,
    ConstraintNode,
    ConstraintStatus,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    GraphEdge,
    RequirementType,
    TransitionEvaluation,
    TransitionRequirement,
    TransitionStatus,
    TransformationNode,
    VerificationStatus,
    build_controlled_demonstrator,
    evaluate_transition,
)

AT = datetime(2026, 1, 2, tzinfo=UTC)


def requirement(
    kind: RequirementType,
    subject: str,
    parameters: dict[str, object] | None = None,
    *,
    mandatory: bool = True,
    requirement_id: str = "R1",
) -> TransitionRequirement:
    return TransitionRequirement(
        requirement_id, kind, subject, parameters or {}, mandatory, "synthetic gate"
    )


def transition(
    *requirements: TransitionRequirement,
) -> tuple[CognitiveTransition, EvidenceGraph]:
    demo = build_controlled_demonstrator()
    definition = CognitiveTransition(
        "TX",
        "synthetic",
        CognitiveState("source", "SOURCE", 0, ("C1",), ("E1",)),
        CognitiveState("target", "TARGET", 1, ("C2",)),
        requirements,
        "test-evaluator",
        "1",
        {"order": {"b": 2, "a": 1}},
    )
    return definition, demo.graph


def replace_node(
    graph: EvidenceGraph, node_id: str, replacement: object
) -> EvidenceGraph:
    nodes = tuple(
        replacement if node.node_id == node_id else node
        for node in graph.nodes.values()
    )
    return EvidenceGraph(nodes, graph.edges)  # type: ignore[arg-type]


def test_models_are_immutable_and_nested_inputs_are_frozen() -> None:
    parameters = {"allowed_states": ["OBSERVED"]}
    req = requirement(RequirementType.CLAIM_STATE, "C1", parameters)
    state = CognitiveState("S", "TYPE", 0, scope={"nested": [1]})
    definition, graph = transition(req)
    evaluation = evaluate_transition(definition, graph, at=AT)
    for obj, name in (
        (state, "state_id"),
        (req, "subject_id"),
        (definition, "transition_id"),
        (evaluation, "status"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, "changed")
    with pytest.raises(TypeError):
        req.parameters["allowed_states"] += ("INFERRED",)
    parameters["allowed_states"].append("INFERRED")
    assert req.parameters["allowed_states"] == ("OBSERVED",)


def test_deterministic_fingerprints_and_requirement_order_independence() -> None:
    r1 = requirement(RequirementType.EVIDENCE_VERIFIED, "E1", requirement_id="a")
    r2 = requirement(RequirementType.SUPPORT_COMPLETE, "C2", requirement_id="b")
    first, graph = transition(r2, r1)
    second, _ = transition(r1, r2)
    one = evaluate_transition(first, graph, at=AT)
    two = evaluate_transition(second, graph, at=AT)
    assert first.fingerprint == second.fingerprint
    assert CognitiveTransition.from_canonical_json(first.canonical_json()) == first
    assert one.canonical_json() == two.canonical_json()
    assert one.fingerprint == two.fingerprint
    assert (
        CognitiveState.from_canonical_json(first.source_state.canonical_json())
        == first.source_state
    )
    assert TransitionRequirement.from_canonical_json(r1.canonical_json()) == r1


def test_enum_coercion_is_rejected() -> None:
    for value in (RequirementType.SUPPORT_COMPLETE, TransitionStatus.ALLOWED):
        with pytest.raises(TypeError):
            bool(value)
        with pytest.raises(TypeError):
            str(value)


def test_transition_allowed_only_when_all_mandatory_requirements_pass() -> None:
    definition, graph = transition(
        requirement(RequirementType.EVIDENCE_VERIFIED, "E1", requirement_id="evidence"),
        requirement(RequirementType.SUPPORT_COMPLETE, "C2", requirement_id="support"),
        requirement(
            RequirementType.CONSTRAINT_SATISFIED, "K1", requirement_id="constraint"
        ),
    )
    result = evaluate_transition(definition, graph, at=AT)
    assert result.status is TransitionStatus.ALLOWED
    assert result.allowed
    assert all(item.passed for item in result.requirement_results)


def test_missing_mandatory_evidence_blocks_transition() -> None:
    definition, graph = transition(
        requirement(RequirementType.EVIDENCE_VERIFIED, "missing")
    )
    result = evaluate_transition(definition, graph, at=AT)
    assert result.status is TransitionStatus.BLOCKED_MISSING_EVIDENCE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (VerificationStatus.UNVERIFIED, TransitionStatus.BLOCKED_UNVERIFIED_EVIDENCE),
        (VerificationStatus.REJECTED, TransitionStatus.BLOCKED_REJECTED_EVIDENCE),
        (VerificationStatus.STALE, TransitionStatus.BLOCKED_STALE_EVIDENCE),
    ],
    ids=["unverified", "rejected", "stale"],
)
def test_inadmissible_evidence_status_blocks(
    status: VerificationStatus, expected: TransitionStatus
) -> None:
    definition, graph = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    old = graph.nodes["E1"].evidence  # type: ignore[union-attr]
    changed = EvidenceNode(replace(old, verification_status=status))
    result = evaluate_transition(definition, replace_node(graph, "E1", changed), at=AT)
    assert result.status is expected


def test_transition_re_evaluation_respects_time_based_staleness() -> None:
    definition, graph = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    old = graph.nodes["E1"].evidence  # type: ignore[union-attr]
    expiring = EvidenceNode(replace(old, valid_until=datetime(2026, 2, 1, tzinfo=UTC)))
    graph = replace_node(graph, "E1", expiring)
    historical = evaluate_transition(definition, graph, at=AT)
    later = evaluate_transition(definition, graph, at=datetime(2026, 3, 1, tzinfo=UTC))
    assert historical.status is TransitionStatus.ALLOWED
    assert later.status is TransitionStatus.BLOCKED_STALE_EVIDENCE
    assert historical.status is TransitionStatus.ALLOWED


def test_upstream_stale_evidence_blocks_support_complete_transition() -> None:
    definition, graph = transition(requirement(RequirementType.SUPPORT_COMPLETE, "C3"))
    old = graph.nodes["E1"].evidence  # type: ignore[union-attr]
    expiring = EvidenceNode(replace(old, valid_until=datetime(2026, 2, 1, tzinfo=UTC)))
    graph = replace_node(graph, "E1", expiring)
    result = evaluate_transition(definition, graph, at=datetime(2026, 3, 1, tzinfo=UTC))
    assert result.status is TransitionStatus.BLOCKED_STALE_EVIDENCE


def graph_with_branch(kind: EdgeType) -> EvidenceGraph:
    demo = build_controlled_demonstrator()
    c1 = demo.graph.nodes["C1"].claim  # type: ignore[union-attr]
    if kind is EdgeType.CONTRADICTS:
        c1 = replace(c1, contradicting_evidence_ids=("E2",))
    nodes = tuple(
        ClaimNode(c1) if node.node_id == "C1" else node
        for node in demo.graph.nodes.values()
    ) + (
        EvidenceNode(replace(demo.graph.nodes["E1"].evidence, evidence_id="E2")),
    )  # type: ignore[union-attr]
    return EvidenceGraph(nodes, (*demo.graph.edges, GraphEdge("E2", "C1", kind)))


def test_unresolved_contradiction_blocks_transition() -> None:
    definition, _ = transition(
        requirement(RequirementType.NO_UNRESOLVED_CONTRADICTION, "C2")
    )
    result = evaluate_transition(
        definition, graph_with_branch(EdgeType.CONTRADICTS), at=AT
    )
    assert result.status is TransitionStatus.BLOCKED_CONTRADICTION


def test_invalidation_blocks_transition() -> None:
    definition, _ = transition(requirement(RequirementType.NO_INVALIDATION, "C1"))
    assert (
        evaluate_transition(
            definition, graph_with_branch(EdgeType.INVALIDATES), at=AT
        ).status
        is TransitionStatus.BLOCKED_INVALIDATION
    )


@pytest.mark.parametrize(
    ("constraint_status", "expected"),
    [
        (ConstraintStatus.UNRESOLVED, TransitionStatus.BLOCKED_CONSTRAINT),
        (ConstraintStatus.VIOLATED, TransitionStatus.BLOCKED_CONSTRAINT),
        (ConstraintStatus.SATISFIED, TransitionStatus.ALLOWED),
    ],
    ids=["unresolved", "violated", "satisfied"],
)
def test_required_constraint_must_be_satisfied(
    constraint_status: ConstraintStatus, expected: TransitionStatus
) -> None:
    definition, graph = transition(
        requirement(RequirementType.CONSTRAINT_SATISFIED, "K1")
    )
    constraint = ConstraintNode(
        "K1", "synthetic_integrity", "check", True, constraint_status
    )
    assert (
        evaluate_transition(
            definition, replace_node(graph, "K1", constraint), at=AT
        ).status
        is expected
    )


def test_uncertainty_threshold_is_fail_closed() -> None:
    definition, graph = transition(
        requirement(
            RequirementType.MAX_UNCERTAINTY,
            "C2",
            {"metric": "minimum_confidence", "threshold": 0.9},
        ),
        requirement(
            RequirementType.SUPPORT_COMPLETE, "C2", requirement_id="passing-support"
        ),
    )
    result = evaluate_transition(definition, graph, at=AT)
    assert result.status is TransitionStatus.BLOCKED_UNCERTAINTY
    assert not result.allowed


def test_transformation_and_dependency_requirements() -> None:
    missing, graph = transition(
        requirement(
            RequirementType.TRANSFORMATION_PRESENT,
            "C2",
            {"transformation_type": "normalization", "version": "1"},
        )
    )
    assert (
        evaluate_transition(missing, graph, at=AT).status
        is TransitionStatus.BLOCKED_TRANSFORMATION
    )
    transform = TransformationNode("TR", "normalization", "1", {}, {})
    transformed_graph = EvidenceGraph(
        (*graph.nodes.values(), transform),
        (
            *graph.edges,
            GraphEdge("E1", "TR", EdgeType.TRANSFORMS),
            GraphEdge("TR", "C2", EdgeType.DERIVES),
        ),
    )
    assert (
        evaluate_transition(missing, transformed_graph, at=AT).status
        is TransitionStatus.ALLOWED
    )
    dependency, graph = transition(
        requirement(
            RequirementType.DEPENDENCY_PRESENT,
            "C2",
            {"source_id": "missing", "target_id": "C2", "edge_type": "DERIVES"},
        )
    )
    assert (
        evaluate_transition(dependency, graph, at=AT).status
        is TransitionStatus.BLOCKED_DEPENDENCY
    )


def test_claim_state_is_explicit_not_inferred_as_supported() -> None:
    definition, graph = transition(
        requirement(
            RequirementType.CLAIM_STATE, "C2", {"allowed_states": ["SUPPORTED"]}
        )
    )
    result = evaluate_transition(definition, graph, at=AT)
    assert result.status is TransitionStatus.BLOCKED_CLAIM_STATE
    assert result.requirement_results[0].observed_value == EpistemicState.INFERRED.value


def test_historical_supported_state_does_not_override_current_graph_incompleteness() -> (
    None
):
    definition, graph = transition(requirement(RequirementType.SUPPORT_COMPLETE, "C1"))
    observed = graph.nodes["C1"].claim  # type: ignore[union-attr]
    supported = observed.with_evaluation(
        ClaimEvaluationResult(
            EpistemicState.SUPPORTED,
            ("E1",),
            (),
            (),
            (),
            (),
            "historical-evaluator",
            "1",
            AT,
        )
    )
    graph = EvidenceGraph(
        tuple(
            ClaimNode(supported) if node.node_id == "C1" else node
            for node in graph.nodes.values()
        ),
        tuple(
            edge
            for edge in graph.edges
            if not (edge.source_id == "E1" and edge.target_id == "C1")
        ),
    )
    assert supported.epistemic_state is EpistemicState.SUPPORTED
    assert (
        evaluate_transition(definition, graph, at=AT).status
        is TransitionStatus.BLOCKED_GRAPH_INCOMPLETE
    )


def test_optional_requirement_failure_does_not_block_but_remains_visible() -> None:
    definition, graph = transition(
        requirement(
            RequirementType.EVIDENCE_VERIFIED, "E1", requirement_id="mandatory"
        ),
        requirement(
            RequirementType.EVIDENCE_VERIFIED,
            "missing",
            mandatory=False,
            requirement_id="optional",
        ),
    )
    result = evaluate_transition(definition, graph, at=AT)
    assert result.status is TransitionStatus.ALLOWED
    optional = next(
        item for item in result.requirement_results if item.requirement_id == "optional"
    )
    assert not optional.passed and not optional.mandatory
    assert result.blocking_requirements == ()


def test_multiple_blockers_preserved_with_deterministic_priority() -> None:
    requirements = (
        requirement(
            RequirementType.CLAIM_STATE,
            "C2",
            {"allowed_states": ["SUPPORTED"]},
            requirement_id="z-state",
        ),
        requirement(
            RequirementType.EVIDENCE_VERIFIED, "missing", requirement_id="a-evidence"
        ),
    )
    first, graph = transition(*requirements)
    second, _ = transition(*reversed(requirements))
    for definition in (first, second):
        result = evaluate_transition(definition, graph, at=AT)
        assert result.status is TransitionStatus.BLOCKED_MISSING_EVIDENCE
        assert result.blocking_requirements == ("a-evidence", "z-state")


def test_allowed_transition_must_be_earned_not_declared() -> None:
    definition, graph = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    earned = evaluate_transition(definition, graph, at=AT)
    with pytest.raises(ValueError, match="earned"):
        TransitionEvaluation(
            *(
                getattr(earned, item)
                for item in (
                    "transition_id",
                    "transition_fingerprint",
                    "transition_definition",
                    "status",
                    "allowed",
                    "evaluated_at",
                    "source_state",
                    "target_state",
                    "requirement_results",
                    "blocking_requirements",
                    "evidence_ids",
                    "claim_ids",
                    "graph_fingerprint",
                    "evaluator_id",
                    "evaluator_version",
                )
            )
        )


def test_serialization_round_trip_and_forged_allowed_rejected() -> None:
    definition, graph = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    earned = evaluate_transition(definition, graph, at=AT)
    restored = TransitionEvaluation.from_canonical_json(earned.canonical_json())
    assert restored == earned
    assert restored.fingerprint == earned.fingerprint
    assert (
        type(earned.requirement_results[0]).from_canonical_json(
            earned.requirement_results[0].canonical_json()
        )
        == earned.requirement_results[0]
    )
    payload = json.loads(earned.canonical_json())
    payload["requirement_results"][0]["passed"] = False
    payload["requirement_results"][0]["failure_status"] = "BLOCKED_UNVERIFIED_EVIDENCE"
    with pytest.raises(ValueError, match="requirement"):
        TransitionEvaluation.from_canonical_json(json.dumps(payload))


def test_allowed_deserialization_is_bound_to_complete_transition_definition() -> None:
    definition, graph = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    payload = json.loads(evaluate_transition(definition, graph, at=AT).canonical_json())
    payload["transition_definition"]["requirements"][0]["subject_id"] = "E2"
    with pytest.raises(ValueError, match="definition"):
        TransitionEvaluation.from_canonical_json(json.dumps(payload))


def test_controlled_demonstrator_has_three_allowed_transitions() -> None:
    fixture = build_controlled_demonstrator()
    assert [item.transition_id for item in fixture.transitions] == ["T1", "T2", "T3"]
    assert all(
        evaluate_transition(item, fixture.graph, at=AT).allowed
        for item in fixture.transitions
    )
