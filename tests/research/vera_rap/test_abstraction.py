from datetime import UTC, datetime
from dataclasses import FrozenInstanceError
import pytest
from app.research.vera_rap import *  # noqa: F403

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def fixture():
    demo = build_controlled_demonstrator()
    transition = demo.transitions[0]
    evaluation = evaluate_transition(transition, demo.graph, at=NOW)
    a1 = AbstractionNode(
        "A1",
        AbstractionLevel.OBSERVATION,
        "observation",
        claim_ids=("C1",),
        created_at=NOW,
    )
    a2 = AbstractionNode(
        "A2",
        AbstractionLevel.PHYSICAL_STATE,
        "physical",
        claim_ids=("C2",),
        source_abstraction_ids=("A1",),
        created_at=NOW,
    )
    rule = AbstractionRule(
        "R",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.PHYSICAL_STATE,
        ("abstracts",),
        transition.transition_type,
        (),
        False,
        "1",
        "adjacent",
    )
    graph = AbstractionGraph(
        (a1, a2),
        (AbstractionEdge("A1", "A2", transition.transition_id, True),),
        (rule,),
        (transition,),
    )
    return demo, evaluation, a1, a2, graph


def test_abstraction_models_are_immutable_and_deterministic():
    _, _, a1, _, graph = fixture()
    with pytest.raises(FrozenInstanceError):
        a1.status = AbstractionStatus.VERIFIED
    assert graph.fingerprint == fixture()[4].fingerprint
    with pytest.raises(TypeError):
        bool(AbstractionLevel.OBSERVATION)


def test_verified_abstraction_must_be_earned_not_declared():
    with pytest.raises(ValueError, match="earned"):
        AbstractionNode(
            "A",
            AbstractionLevel.OBSERVATION,
            "x",
            AbstractionStatus.VERIFIED,
            created_at=NOW,
        )


def test_abstraction_level_skip_requires_explicit_rule():
    demo = build_controlled_demonstrator()
    a = AbstractionNode("A", AbstractionLevel.OBSERVATION, "x", created_at=NOW)
    b = AbstractionNode("B", AbstractionLevel.MATERIALITY, "y", created_at=NOW)
    t = demo.transitions[0]
    rule = AbstractionRule(
        "R",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.MATERIALITY,
        (),
        t.transition_type,
        (),
        False,
        "1",
        "no skip",
    )
    with pytest.raises(ValueError, match="level"):
        AbstractionGraph(
            (a, b), (AbstractionEdge("A", "B", t.transition_id, True),), (rule,), (t,)
        )


def test_abstraction_chain_verifies_when_every_boundary_is_admissible():
    demo, evaluation, a1, a2, graph = fixture()
    v1 = verify_abstraction(
        a1,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    graph = graph.with_node(a1.with_verification(v1))
    v2 = verify_abstraction(
        a2,
        graph,
        demo.graph,
        {evaluation.transition_id: evaluation},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    assert (
        v1.status is AbstractionStatus.VERIFIED
        and v2.status is AbstractionStatus.VERIFIED
    )


def test_invalid_lower_abstraction_and_blocked_transition_block_downstream():
    demo, _, _, a2, graph = fixture()
    result = verify_abstraction(
        a2,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    assert result.status is AbstractionStatus.BLOCKED
    assert {
        AbstractionFailure.MISSING_UPSTREAM_ABSTRACTION,
        AbstractionFailure.TRANSITION_BLOCKED,
    } <= set(result.failed_requirements)


def test_unresolved_contradiction_and_uncertainty_gate_block_abstraction():
    demo, evaluation, a1, a2, graph = fixture()
    v1 = verify_abstraction(
        a1,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    graph = graph.with_node(a1.with_verification(v1))
    contradiction = ContradictionObject(
        "X",
        ContradictionType.CLAIM_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        claim_ids=("C2",),
        detected_at=NOW,
        conflict_dimensions=("claim",),
    )
    result = verify_abstraction(
        a2,
        graph,
        demo.graph,
        {evaluation.transition_id: evaluation},
        {},
        (contradiction,),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    assert AbstractionFailure.UNRESOLVED_CONTRADICTION in result.failed_requirements


def test_historical_verification_not_rewritten_and_supersession_explicit():
    demo, _, a1, _, graph = fixture()
    old = verify_abstraction(
        a1,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    verified = a1.with_verification(old)
    superseded = verified.supersede("A-new")
    assert (
        old.status is AbstractionStatus.VERIFIED
        and verified.status is AbstractionStatus.VERIFIED
    )
    assert (
        superseded.status is AbstractionStatus.SUPERSEDED
        and superseded.superseded_by == "A-new"
    )


def test_abstraction_graph_serialization_round_trip_and_forgery_rejection():
    import json

    graph = fixture()[4]
    restored = AbstractionGraph.from_canonical_json(graph.canonical_json())
    assert restored.fingerprint == graph.fingerprint
    payload = graph.canonical_dict()
    payload["nodes"][0]["status"] = "VERIFIED"
    with pytest.raises(ValueError, match="history"):
        AbstractionGraph.from_canonical_json(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )


def test_uncertainty_gate_blocks_higher_abstraction():
    demo, evaluation, a1, a2, old_graph = fixture()
    transition = demo.transitions[0]
    rule = AbstractionRule(
        "R",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.PHYSICAL_STATE,
        ("abstracts",),
        transition.transition_type,
        ("confidence-90",),
        False,
        "1",
        "adjacent with uncertainty gate",
    )
    a2 = AbstractionNode(
        "A2",
        AbstractionLevel.PHYSICAL_STATE,
        "physical",
        claim_ids=("C2",),
        source_abstraction_ids=("A1",),
        uncertainty_profile_id="P2",
        created_at=NOW,
    )
    graph = AbstractionGraph((a1, a2), old_graph.edges, (rule,), (transition,))
    v1 = verify_abstraction(
        a1,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    graph = graph.with_node(a1.with_verification(v1))
    failed_gate = UncertaintyGateResult(
        "confidence-90", False, 0.78, 0.9, ("u1",), "below threshold"
    )
    result = verify_abstraction(
        a2,
        graph,
        demo.graph,
        {evaluation.transition_id: evaluation},
        {"P2": object()},
        (),
        {"confidence-90": failed_gate},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    assert result.status is AbstractionStatus.BLOCKED
    assert AbstractionFailure.UNCERTAINTY_GATE_FAILED in result.failed_requirements


def test_required_claim_predicates_are_machine_checked():
    demo, evaluation, a1, a2, old_graph = fixture()
    bad_rule = AbstractionRule(
        "R",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.PHYSICAL_STATE,
        ("predicate-not-present",),
        demo.transitions[0].transition_type,
        (),
        False,
        "1",
        "requires explicit predicate",
    )
    graph = AbstractionGraph(
        (a1, a2), old_graph.edges, (bad_rule,), demo.transitions[:1]
    )
    v1 = verify_abstraction(
        a1,
        graph,
        demo.graph,
        {},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    graph = graph.with_node(a1.with_verification(v1))
    result = verify_abstraction(
        a2,
        graph,
        demo.graph,
        {evaluation.transition_id: evaluation},
        {},
        (),
        {},
        at=NOW,
        verifier_id="v",
        verifier_version="1",
    )
    assert AbstractionFailure.MISSING_CLAIM in result.failed_requirements
