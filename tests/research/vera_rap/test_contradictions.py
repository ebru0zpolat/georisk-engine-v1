from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap import (
    ClaimNode,
    ClaimObject,
    ConstraintNode,
    ConstraintStatus,
    ContradictionObject,
    ContradictionResolutionResult,
    ContradictionStatus,
    ContradictionType,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    EvidenceObject,
    GraphEdge,
    Provenance,
    ResolutionRequirement,
    ResolutionRequirementType,
    TransformationNode,
    VerificationStatus,
    evaluate_resolution,
    find_contradictions,
    has_unresolved_contradiction,
)

NOW = datetime(2026, 1, 10, tzinfo=UTC)


def evidence(
    evidence_id: str,
    value: float,
    *,
    start: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    end: datetime = datetime(2026, 1, 31, tzinfo=UTC),
    scope: object = "scope-1",
    unit: str = "u",
    method: str = "observed",
    source: str | None = None,
    digest: str | None = None,
    confidence: float | None = None,
) -> EvidenceObject:
    source = source or f"source-{evidence_id}"
    digest = digest or f"{ord(evidence_id[-1]) % 10}" * 64
    from app.research.vera_rap import Uncertainty

    return EvidenceObject(
        evidence_id,
        "generic-measurement",
        source,
        f"urn:test:{evidence_id}",
        digest,
        NOW,
        start,
        start,
        end,
        None,
        scope,
        {"subject": "entity", "property": "property", "value": value, "method": method},
        unit,
        (
            None
            if confidence is None
            else Uncertainty("confidence", confidence=confidence)
        ),
        "test",
        VerificationStatus.VERIFIED,
        provenance=Provenance(source, "fixture", digest),
    )


def claim(
    contradictions: tuple[str, ...] = (), supports: tuple[str, ...] = ()
) -> ClaimObject:
    return ClaimObject(
        "C1",
        "has_value",
        "entity",
        1,
        "u",
        EpistemicState.OBSERVED,
        supports,
        contradictions,
        created_at=NOW,
        derivation_method="fixture",
    )


def requirement() -> ResolutionRequirement:
    return ResolutionRequirement(
        "R1",
        ResolutionRequirementType.INDEPENDENT_EVIDENCE_REQUIRED,
        ("E1", "E2"),
        {"minimum": 1},
        True,
        "Independent evidence is required",
    )


def contradiction(**changes: object) -> ContradictionObject:
    values: dict[str, object] = {
        "contradiction_id": "X1",
        "contradiction_type": ContradictionType.DIRECT_VALUE_CONFLICT,
        "status": ContradictionStatus.UNRESOLVED,
        "evidence_ids": ("E2", "E1"),
        "detected_at": NOW,
        "conflict_dimensions": ("measurement.value",),
        "resolution_requirements": (requirement(),),
        "metadata": {"model_confidence": 0.999, "nested": [1]},
    }
    values.update(changes)
    return ContradictionObject(**values)  # type: ignore[arg-type]


def resolution(
    status: ContradictionStatus = ContradictionStatus.RESOLVED, **changes: object
) -> ContradictionResolutionResult:
    values: dict[str, object] = {
        "target_status": status,
        "satisfied_requirement_ids": ("R1",),
        "unsatisfied_requirement_ids": (),
        "supporting_evidence_ids": ("E3",),
        "rejected_evidence_ids": ("E2",),
        "superseded_claim_ids": (),
        "retained_claim_ids": (),
        "resolver_id": "resolver",
        "resolver_version": "1",
        "resolved_at": NOW,
        "resolution_basis": "Independent verified observation",
        "notes_metadata": {"review": "explicit"},
    }
    values.update(changes)
    return ContradictionResolutionResult(**values)  # type: ignore[arg-type]


def test_models_are_immutable_and_nested_values_are_frozen() -> None:
    item = contradiction()
    with pytest.raises(FrozenInstanceError):
        item.status = ContradictionStatus.RESOLVED  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        item.resolution_requirements[0].mandatory = False  # type: ignore[misc]
    with pytest.raises(TypeError):
        item.metadata["nested"] += (2,)  # type: ignore[index]
    result = resolution()
    with pytest.raises(FrozenInstanceError):
        result.resolver_id = "other"  # type: ignore[misc]


def test_enums_reject_string_and_boolean_coercion() -> None:
    for value in (
        ContradictionType.CLAIM_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        ResolutionRequirementType.HUMAN_REVIEW_REQUIRED,
    ):
        with pytest.raises(TypeError):
            str(value)
        with pytest.raises(TypeError):
            bool(value)


def test_deterministic_fingerprint_and_insertion_order_independence() -> None:
    first = contradiction(metadata={"b": 2, "a": 1})
    second = contradiction(evidence_ids=("E1", "E2"), metadata={"a": 1, "b": 2})
    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint == second.fingerprint
    assert (
        resolution().fingerprint
        == resolution(notes_metadata={"review": "explicit"}).fingerprint
    )


def test_direct_and_overlapping_value_conflict_detection() -> None:
    graph = EvidenceGraph(
        (EvidenceNode(evidence("E1", 2.3)), EvidenceNode(evidence("E2", 8.9)))
    )
    found = find_contradictions(graph, at=NOW, value_tolerance=0.1)
    assert len(found) == 1
    assert found[0].contradiction_type is ContradictionType.DIRECT_VALUE_CONFLICT
    assert found[0].status is ContradictionStatus.UNRESOLVED


def test_temporal_non_conflict_and_overlapping_possible_conflict() -> None:
    first = EvidenceNode(evidence("E1", 1.2, end=datetime(2026, 1, 2, tzinfo=UTC)))
    later = EvidenceNode(evidence("E2", 1.9, start=datetime(2026, 1, 3, tzinfo=UTC)))
    assert find_contradictions(EvidenceGraph((first, later)), at=NOW) == ()
    overlapping = EvidenceNode(
        evidence("E2", 1.9, start=datetime(2026, 1, 2, tzinfo=UTC))
    )
    assert (
        find_contradictions(EvidenceGraph((first, overlapping)), at=NOW)[
            0
        ].contradiction_type
        is ContradictionType.DIRECT_VALUE_CONFLICT
    )


def test_different_scope_is_not_direct_conflict() -> None:
    graph = EvidenceGraph(
        (
            EvidenceNode(evidence("E1", 1, scope="city")),
            EvidenceNode(evidence("E2", 2, scope="site")),
        )
    )
    assert find_contradictions(graph, at=NOW) == ()


def test_unit_difference_requires_normalization_not_a_winner() -> None:
    graph = EvidenceGraph(
        (
            EvidenceNode(evidence("E1", 1, unit="metre")),
            EvidenceNode(evidence("E2", 100, unit="centimetre")),
        )
    )
    item = find_contradictions(graph, at=NOW)[0]
    assert item.contradiction_type is ContradictionType.UNIT_OR_REPRESENTATION_CONFLICT
    assert (
        item.resolution_requirements[0].requirement_type
        is ResolutionRequirementType.UNIT_NORMALIZATION_REQUIRED
    )
    assert item.status is ContradictionStatus.UNRESOLVED


def test_method_and_provenance_conflicts_are_explicit() -> None:
    methods = EvidenceGraph(
        (
            EvidenceNode(evidence("E1", 1, method="observed")),
            EvidenceNode(evidence("E2", 2, method="modelled")),
        )
    )
    assert (
        find_contradictions(methods, at=NOW)[0].contradiction_type
        is ContradictionType.METHOD_CONFLICT
    )
    provenance = EvidenceGraph(
        (
            EvidenceNode(evidence("E1", 1, source="source-a", digest="a" * 64)),
            EvidenceNode(evidence("E2", 1, source="source-b", digest="a" * 64)),
        )
    )
    assert any(
        item.contradiction_type is ContradictionType.PROVENANCE_CONFLICT
        for item in find_contradictions(provenance, at=NOW)
    )


def test_explicit_edges_claim_state_and_constraint_detection() -> None:
    e1, e2, e3 = evidence("E1", 1), evidence("E2", 2), evidence("E3", 3)
    c1 = claim(("E2",), ("E1",))
    violated = ConstraintNode("K1", "generic", "check", True, ConstraintStatus.VIOLATED)
    graph = EvidenceGraph(
        (EvidenceNode(e1), EvidenceNode(e2), EvidenceNode(e3), ClaimNode(c1), violated),
        (
            GraphEdge("E1", "C1", EdgeType.SUPPORTS),
            GraphEdge("E2", "C1", EdgeType.CONTRADICTS),
            GraphEdge("E3", "C1", EdgeType.INVALIDATES),
            GraphEdge("C1", "K1", EdgeType.REQUIRES),
        ),
    )
    types = {item.contradiction_type for item in find_contradictions(graph, at=NOW)}
    assert {
        ContradictionType.CLAIM_CONFLICT,
        ContradictionType.CONSTRAINT_CONFLICT,
    } <= types
    claim_conflicts = [
        item
        for item in find_contradictions(graph, at=NOW)
        if item.contradiction_type is ContradictionType.CLAIM_CONFLICT
    ]
    assert {item.conflict_dimensions[0] for item in claim_conflicts} >= {
        "contradicts",
        "invalidates",
    }


def test_transformation_conflict_detected_from_incompatible_producers() -> None:
    nodes = (
        EvidenceNode(evidence("E1", 1)),
        EvidenceNode(evidence("E2", 1)),
        EvidenceNode(evidence("E3", 1)),
        TransformationNode("T1", "normalize", "1", {}, {}),
        TransformationNode("T2", "normalize", "2", {}, {}),
    )
    edges = (
        GraphEdge("E1", "T1", EdgeType.TRANSFORMS),
        GraphEdge("E2", "T2", EdgeType.TRANSFORMS),
        GraphEdge("T1", "E3", EdgeType.DERIVES),
        GraphEdge("T2", "E3", EdgeType.DERIVES),
    )
    found = find_contradictions(EvidenceGraph(nodes, edges), at=NOW)
    assert any(
        item.contradiction_type is ContradictionType.TRANSFORMATION_CONFLICT
        for item in found
    )


def test_majority_vote_does_not_automatically_resolve() -> None:
    item = contradiction(evidence_ids=("E1", "E2", "E3", "E4"))
    assert item.status is ContradictionStatus.UNRESOLVED
    assert has_unresolved_contradiction((item,))


def test_newer_evidence_does_not_automatically_win() -> None:
    item = contradiction(metadata={"older": "E1", "newer": "E2"})
    assert item.status is ContradictionStatus.UNRESOLVED
    assert item.evidence_ids == ("E1", "E2")


def test_model_confidence_cannot_resolve_contradiction() -> None:
    assert (
        contradiction(metadata={"model_confidence": 1.0}).status
        is ContradictionStatus.UNRESOLVED
    )


def test_pending_resolution_is_first_class() -> None:
    pending = contradiction(status=ContradictionStatus.RESOLUTION_PENDING)
    assert pending.resolution_requirements and has_unresolved_contradiction((pending,))


def test_earned_resolution_requires_requirements_and_admissible_evidence() -> None:
    graph = EvidenceGraph((EvidenceNode(evidence("E3", 1)),))
    with pytest.raises(ValueError, match="mandatory"):
        evaluate_resolution(
            contradiction(),
            resolution(
                satisfied_requirement_ids=(), unsatisfied_requirement_ids=("R1",)
            ),
            graph,
        )
    resolved = evaluate_resolution(contradiction(), resolution(), graph)
    assert resolved.status is ContradictionStatus.RESOLVED
    assert resolved.evidence_ids == ("E1", "E2")
    assert resolved.resolution_history[-1].rejected_evidence_ids == ("E2",)


def test_irresolvable_preserves_original_branches() -> None:
    result = resolution(
        ContradictionStatus.IRRESOLVABLE,
        satisfied_requirement_ids=(),
        unsatisfied_requirement_ids=("R1",),
        supporting_evidence_ids=(),
        rejected_evidence_ids=(),
    )
    final = evaluate_resolution(contradiction(), result, EvidenceGraph())
    assert final.status is ContradictionStatus.IRRESOLVABLE
    assert final.evidence_ids == ("E1", "E2")


def test_resolved_contradiction_must_be_earned_not_declared() -> None:
    with pytest.raises(ValueError, match="earned"):
        contradiction(status=ContradictionStatus.RESOLVED)
    payload = json.loads(contradiction().canonical_json())
    payload["status"] = "RESOLVED"
    with pytest.raises(ValueError, match="history"):
        ContradictionObject.from_canonical_json(json.dumps(payload))


def test_serialization_round_trip_preserves_resolution_history() -> None:
    graph = EvidenceGraph((EvidenceNode(evidence("E3", 1)),))
    resolved = evaluate_resolution(contradiction(), resolution(), graph)
    restored = ContradictionObject.from_canonical_json(resolved.canonical_json())
    assert restored == resolved
    assert restored.fingerprint == resolved.fingerprint
    assert (
        ContradictionResolutionResult.from_dict(resolution().canonical_dict())
        == resolution()
    )
