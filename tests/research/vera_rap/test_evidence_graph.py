from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap import (
    ClaimEvaluationResult,
    ClaimNode,
    ClaimObject,
    ConstraintNode,
    ConstraintStatus,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    EvidenceObject,
    GraphEdge,
    Provenance,
    TransformationNode,
    VerificationStatus,
)

T1 = datetime(2026, 1, 1, tzinfo=UTC)
T2 = datetime(2026, 3, 1, tzinfo=UTC)
HASHES = {name: char * 64 for name, char in zip(("E1", "E2", "E3"), "abc")}


def evidence(
    evidence_id: str,
    status: VerificationStatus = VerificationStatus.VERIFIED,
    *,
    valid_until: datetime | None = None,
) -> EvidenceObject:
    digest = HASHES[evidence_id]
    return EvidenceObject(
        evidence_id=evidence_id,
        evidence_type="generic",
        source_id=f"source-{evidence_id}",
        source_uri=f"https://example.test/{evidence_id}",
        content_hash=digest,
        retrieved_at=T1,
        observed_at=T1,
        valid_from=T1,
        valid_until=valid_until,
        jurisdiction=None,
        spatial_scope=None,
        measurement={"value": evidence_id},
        unit=None,
        uncertainty=None,
        licence_status="declared",
        verification_status=status,
        provenance=Provenance(f"source-{evidence_id}", "download", digest),
    )


def claim(
    claim_id: str,
    *,
    support: tuple[str, ...] = (),
    contradiction: tuple[str, ...] = (),
    parents: tuple[str, ...] = (),
) -> ClaimObject:
    state = (
        EpistemicState.OBSERVED
        if support
        else (EpistemicState.INFERRED if parents else EpistemicState.HYPOTHESISED)
    )
    return ClaimObject(
        claim_id=claim_id,
        predicate="has_value",
        subject={"id": claim_id},
        value=True,
        unit=None,
        epistemic_state=state,
        supporting_evidence_ids=support,
        contradicting_evidence_ids=contradiction,
        parent_claim_ids=parents,
        created_at=T1,
        derivation_method="test",
    )


def edge(source: str, target: str, kind: EdgeType) -> GraphEdge:
    return GraphEdge(source, target, kind)


def direct_graph(
    status: VerificationStatus = VerificationStatus.VERIFIED,
    *,
    constraint: ConstraintNode | None = None,
) -> EvidenceGraph:
    nodes = [
        EvidenceNode(evidence("E1", status)),
        ClaimNode(claim("C1", support=("E1",))),
    ]
    edges = [edge("E1", "C1", EdgeType.SUPPORTS)]
    if constraint:
        nodes.append(constraint)
        edges.append(edge("C1", constraint.node_id, EdgeType.REQUIRES))
    return EvidenceGraph(tuple(nodes), tuple(edges))


def test_nodes_and_edges_are_immutable_with_nested_freezing() -> None:
    metadata = {"nested": [1]}
    node = ConstraintNode(
        "K1", "generic", "check", True, ConstraintStatus.SATISFIED, metadata
    )
    graph_edge = edge("E1", "C1", EdgeType.SUPPORTS)
    with pytest.raises(FrozenInstanceError):
        node.required = False  # type: ignore[misc]
    with pytest.raises(TypeError):
        node.metadata["nested"] += (2,)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        graph_edge.target_id = "C2"  # type: ignore[misc]
    metadata["nested"].append(2)
    assert node.metadata["nested"] == (1,)  # type: ignore[index]


def test_deterministic_fingerprint_and_insertion_order_independence() -> None:
    e = EvidenceNode(evidence("E1"))
    c = ClaimNode(claim("C1", support=("E1",)))
    a = EvidenceGraph((e, c), (edge("E1", "C1", EdgeType.SUPPORTS),))
    b = EvidenceGraph((c, e), (edge("E1", "C1", EdgeType.SUPPORTS),))
    assert a.to_canonical_json() == b.to_canonical_json()
    assert a.fingerprint == b.fingerprint


def test_semantic_graph_difference_changes_fingerprint() -> None:
    first = direct_graph()
    second = direct_graph(VerificationStatus.UNVERIFIED)
    assert first.fingerprint != second.fingerprint


def test_duplicate_node_and_edge_rejected() -> None:
    node = EvidenceNode(evidence("E1"))
    with pytest.raises(ValueError, match="duplicate node"):
        EvidenceGraph((node, node))
    c = ClaimNode(claim("C1", support=("E1",)))
    relation = edge("E1", "C1", EdgeType.SUPPORTS)
    with pytest.raises(ValueError, match="duplicate graph edge"):
        EvidenceGraph((node, c), (relation, relation))


def test_missing_node_invalid_combination_and_self_loop_rejected() -> None:
    e = EvidenceNode(evidence("E1"))
    c = ClaimNode(claim("C1", support=("E1",)))
    with pytest.raises(ValueError, match="missing node"):
        EvidenceGraph((e,), (edge("E1", "C1", EdgeType.SUPPORTS),))
    with pytest.raises(ValueError, match="invalid SUPPORTS"):
        EvidenceGraph((e, c), (edge("C1", "E1", EdgeType.SUPPORTS),))
    with pytest.raises(ValueError, match="self-loop"):
        edge("C1", "C1", EdgeType.DERIVES)


def test_cycle_is_rejected_fail_closed() -> None:
    nodes = tuple(
        ClaimNode(
            claim(
                name,
                parents=(("C1",) if name == "C2" else ("C2",) if name == "C3" else ()),
            )
        )
        for name in ("C1", "C2", "C3")
    )
    graph = EvidenceGraph(
        nodes, (edge("C1", "C2", EdgeType.DERIVES), edge("C2", "C3", EdgeType.DERIVES))
    )
    with pytest.raises(ValueError, match=r"cycle detected: C1 -> C2 -> C3 -> C1"):
        graph.with_edge(edge("C3", "C1", EdgeType.DERIVES))


def test_claim_reference_without_graph_edge_is_not_support_complete() -> None:
    graph = EvidenceGraph(
        (EvidenceNode(evidence("E1")), ClaimNode(claim("C1", support=("E1",))))
    )
    validation = graph.validate_consistency()
    assert not validation.valid
    assert validation.missing_edges == ("E1 -SUPPORTS-> C1",)
    assert not graph.is_support_complete("C1", at=T1).complete


def test_parent_claim_reference_consistency() -> None:
    graph = EvidenceGraph(
        (ClaimNode(claim("C1")), ClaimNode(claim("C2", parents=("C1",))))
    )
    assert graph.validate_consistency().missing_edges == ("C1 -DERIVES-> C2",)


@pytest.mark.parametrize(
    ("status", "field"),
    [
        (VerificationStatus.UNVERIFIED, "unverified_evidence_ids"),
        (VerificationStatus.REJECTED, "rejected_evidence_ids"),
        (VerificationStatus.STALE, "stale_evidence_ids"),
        (VerificationStatus.CONTRADICTED, "contradicted_dependencies"),
    ],
    ids=["unverified", "rejected", "stale", "contradicted"],
)
def test_only_verified_admissible_evidence_satisfies_support(
    status: VerificationStatus, field: str
) -> None:
    result = direct_graph(status).is_support_complete("C1", at=T1)
    assert not result.complete
    assert getattr(result, field) == ("E1",)


def test_verified_direct_evidence_is_support_complete() -> None:
    result = direct_graph().is_support_complete("C1", at=T1)
    assert result.complete
    assert result.supporting_evidence_ids == ("E1",)


def chain_graph(
    valid_until: datetime,
) -> tuple[EvidenceGraph, EvidenceObject, tuple[ClaimObject, ...]]:
    root = evidence("E1", valid_until=valid_until)
    claims = (
        claim("C1", support=("E1",)),
        claim("C2", parents=("C1",)),
        claim("C3", parents=("C2",)),
    )
    graph = EvidenceGraph(
        (EvidenceNode(root), *(ClaimNode(item) for item in claims)),
        (
            edge("E1", "C1", EdgeType.SUPPORTS),
            edge("C1", "C2", EdgeType.DERIVES),
            edge("C2", "C3", EdgeType.DERIVES),
        ),
    )
    return graph, root, claims


def test_stale_root_evidence_invalidates_downstream_support_completeness() -> None:
    graph, root, claims = chain_graph(datetime(2026, 2, 1, tzinfo=UTC))
    fingerprints = (root.fingerprint, *(item.fingerprint for item in claims))
    assert all(
        graph.is_support_complete(item, at=T1).complete for item in ("C1", "C2", "C3")
    )
    assert all(
        not graph.is_support_complete(item, at=T2).complete
        for item in ("C1", "C2", "C3")
    )
    assert graph.is_support_complete("C3", at=T2).upstream_claim_issues
    assert fingerprints == (root.fingerprint, *(item.fingerprint for item in claims))


def test_contradictory_evidence_is_preserved_not_silently_resolved() -> None:
    c = claim("C1", support=("E1",), contradiction=("E2",))
    graph = EvidenceGraph(
        (EvidenceNode(evidence("E1")), EvidenceNode(evidence("E2")), ClaimNode(c)),
        (edge("E1", "C1", EdgeType.SUPPORTS), edge("E2", "C1", EdgeType.CONTRADICTS)),
    )
    lineage = graph.explain("C1")
    assert lineage.direct_support == ("E1",)
    assert lineage.direct_contradictions == ("E2",)
    assert not graph.is_support_complete("C1", at=T1).complete


@pytest.mark.parametrize(
    ("status", "complete", "field"),
    [
        (ConstraintStatus.SATISFIED, True, None),
        (ConstraintStatus.UNRESOLVED, False, "missing_constraints"),
        (ConstraintStatus.VIOLATED, False, "failed_constraints"),
    ],
    ids=["satisfied", "unresolved", "violated"],
)
def test_required_constraint_status_controls_completeness(
    status: ConstraintStatus, complete: bool, field: str | None
) -> None:
    constraint = ConstraintNode("K1", "generic", "mandatory check", True, status)
    result = direct_graph(constraint=constraint).is_support_complete("C1", at=T1)
    assert result.complete is complete
    if field:
        assert getattr(result, field) == ("K1",)


def test_structured_lineage_preserves_transformation() -> None:
    transform = TransformationNode(
        "T1", "normalization", "1", {"type": "raw"}, {"type": "normalized"}
    )
    graph = EvidenceGraph(
        (
            EvidenceNode(evidence("E1")),
            EvidenceNode(evidence("E2")),
            transform,
            ClaimNode(claim("C1", support=("E2",))),
        ),
        (
            edge("E1", "T1", EdgeType.TRANSFORMS),
            edge("T1", "E2", EdgeType.DERIVES),
            edge("E2", "C1", EdgeType.SUPPORTS),
        ),
    )
    lineage = graph.explain("C1")
    assert lineage.transformations == ("T1",)
    assert lineage.upstream_evidence == ("E1", "E2")
    assert graph.validate_consistency().valid


def test_transformed_evidence_preserves_upstream_admissibility_dependency() -> None:
    transform = TransformationNode("T1", "normalization", "1", {}, {})
    graph = EvidenceGraph(
        (
            EvidenceNode(evidence("E1", valid_until=datetime(2026, 2, 1, tzinfo=UTC))),
            EvidenceNode(evidence("E2")),
            transform,
            ClaimNode(claim("C1", support=("E2",))),
        ),
        (
            edge("E1", "T1", EdgeType.TRANSFORMS),
            edge("T1", "E2", EdgeType.DERIVES),
            edge("E2", "C1", EdgeType.SUPPORTS),
        ),
    )
    assert graph.is_support_complete("C1", at=T1).complete
    result = graph.is_support_complete("C1", at=T2)
    assert not result.complete
    assert result.stale_evidence_ids == ("E1",)


def test_transformation_can_explicitly_derive_claim_with_input_lineage() -> None:
    transform = TransformationNode("T1", "aggregation", "1", {}, {})
    graph = EvidenceGraph(
        (EvidenceNode(evidence("E1")), transform, ClaimNode(claim("C1"))),
        (
            edge("E1", "T1", EdgeType.TRANSFORMS),
            edge("T1", "C1", EdgeType.DERIVES),
        ),
    )
    assert graph.validate_consistency().valid
    assert graph.is_support_complete("C1", at=T1).complete
    assert graph.explain("C1").transformations == ("T1",)


def test_serialization_round_trip_preserves_types_and_fingerprint() -> None:
    graph = direct_graph(
        constraint=ConstraintNode(
            "K1", "generic", "check", True, ConstraintStatus.SATISFIED
        )
    )
    restored = EvidenceGraph.from_canonical_json(graph.to_canonical_json())
    assert restored.to_canonical_json() == graph.to_canonical_json()
    assert restored.fingerprint == graph.fingerprint
    assert isinstance(restored.nodes["E1"], EvidenceNode)
    assert isinstance(restored.nodes["C1"], ClaimNode)


def test_graph_deserialization_cannot_bypass_earned_claim_protection() -> None:
    payload = direct_graph().to_canonical_dict()
    claim_payload = next(
        item["payload"] for item in payload["nodes"] if item["node_type"] == "CLAIM"
    )
    claim_payload["epistemic_state"] = "SUPPORTED"
    claim_payload["evaluation_history"] = []
    with pytest.raises(ValueError, match="cannot manufacture"):
        EvidenceGraph.from_canonical_json(json.dumps(payload))


def test_historical_supported_claim_can_be_currently_incomplete() -> None:
    base = claim("C1", support=("E1",))
    result = ClaimEvaluationResult(
        EpistemicState.SUPPORTED, ("E1",), (), (), (), (), "eval", "1", T1
    )
    historical = base.with_evaluation(result)
    root = evidence("E1", valid_until=datetime(2026, 2, 1, tzinfo=UTC))
    graph = EvidenceGraph(
        (EvidenceNode(root), ClaimNode(historical)),
        (edge("E1", "C1", EdgeType.SUPPORTS),),
    )
    assert historical.epistemic_state is EpistemicState.SUPPORTED
    assert not graph.is_support_complete("C1", at=T2).complete
    assert historical.epistemic_state is EpistemicState.SUPPORTED
