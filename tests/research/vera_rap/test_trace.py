import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from app.research.vera_rap import (
    AbstractionEdge,
    AbstractionGraph,
    AbstractionLevel,
    AbstractionNode,
    AbstractionRule,
    AbstractionStatus,
    ArtifactRegistry,
    ArtifactType,
    ClaimEvaluationResult,
    ClaimNode,
    CognitiveTrace,
    CognitiveTraceBuilder,
    ContradictionObject,
    ContradictionStatus,
    ContradictionType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    PlanExecutionResult,
    PlanningTarget,
    PlanningTargetType,
    PlanStatus,
    PropagationRule,
    PropagationRuleType,
    ResolutionRequirement,
    ResolutionRequirementType,
    ThresholdMetric,
    ThresholdOperator,
    TraceEvent,
    TraceEventType,
    TransitionStatus,
    UncertaintyThreshold,
    build_controlled_demonstrator,
    derive_claim_uncertainty,
    evaluate_transition,
    evaluate_uncertainty_gate,
    identify_blockers,
    plan_evidence,
    reference_for,
    replan,
    replay_trace,
    validate_trace,
    verify_abstraction,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)
ACTOR = {"actor_id": "vera-rap", "actor_version": "1"}
PLANNER = {"planner_id": "planner", "planner_version": "1"}


def swap(graph: EvidenceGraph, node_id: str, node: object) -> EvidenceGraph:
    return EvidenceGraph(
        tuple(node if x.node_id == node_id else x for x in graph.nodes.values()),  # type: ignore[arg-type]
        graph.edges,
    )


def stale_graph() -> EvidenceGraph:
    demo = build_controlled_demonstrator()
    old = demo.graph.nodes["E1"].evidence  # type: ignore[union-attr]
    return swap(demo.graph, "E1", EvidenceNode(replace(old, valid_until=T0)))


def abstraction_graph():
    demo = build_controlled_demonstrator()
    tr = demo.transitions[0]
    a1 = AbstractionNode(
        "A1", AbstractionLevel.OBSERVATION, "obs", claim_ids=("C1",), created_at=T1
    )
    a2 = AbstractionNode(
        "A2",
        AbstractionLevel.PHYSICAL_STATE,
        "phys",
        claim_ids=("C2",),
        source_abstraction_ids=("A1",),
        created_at=T1,
    )
    rule = AbstractionRule(
        "R",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.PHYSICAL_STATE,
        ("abstracts",),
        tr.transition_type,
        (),
        False,
        "1",
        "adjacent",
    )
    return AbstractionGraph(
        (a1, a2), (AbstractionEdge("A1", "A2", tr.transition_id, True),), (rule,), (tr,)
    )


def verified_episode(graph: EvidenceGraph, *, at: datetime = T1):
    """Full chain evidence -> claim -> support -> transition -> uncertainty -> abstraction."""
    demo = build_controlled_demonstrator()
    builder = CognitiveTraceBuilder(("A2",), started_at=T0, **ACTOR)
    builder.register_evidence(graph.nodes["E1"].evidence)  # type: ignore[union-attr]
    for claim_id in ("C1", "C2"):
        builder.declare_claim(graph.nodes[claim_id].claim)  # type: ignore[union-attr]
    builder.evaluate_staleness(graph.nodes["E1"].evidence, at=at)  # type: ignore[union-attr]
    builder.evaluate_support(graph.is_support_complete("C2", at=at), graph)
    evaluation = evaluate_transition(demo.transitions[0], graph, at=at)
    builder.evaluate_transition(evaluation, graph)
    rule = PropagationRule(
        "r1", PropagationRuleType.PASS_THROUGH, "1", ("C1",), "C2", {}, (), "pass"
    )
    propagation = derive_claim_uncertainty("C2", graph, (rule,), at=at)
    builder.propagate_uncertainty(propagation)
    threshold = UncertaintyThreshold(
        "no-contradiction",
        ThresholdMetric.NO_CONTRADICTION_UNCERTAINTY,
        ThresholdOperator.EQUAL,
        True,
        None,
        (),
        True,
        "gate",
    )
    gate = evaluate_uncertainty_gate(propagation.output_profile, threshold)
    builder.evaluate_gate(gate, propagation.output_profile, at=at)
    ag = abstraction_graph()
    builder.propose_abstraction(ag.nodes["A1"], abstraction_graph=ag)
    builder.propose_abstraction(ag.nodes["A2"], abstraction_graph=ag)
    v1 = verify_abstraction(
        ag.nodes["A1"],
        ag,
        graph,
        {},
        {},
        (),
        {},
        at=at,
        verifier_id="v",
        verifier_version="1",
    )
    ag = ag.with_node(ag.nodes["A1"].with_verification(v1))
    builder.verify_abstraction(v1, node=ag.nodes["A1"], evidence_graph=graph)
    v2 = verify_abstraction(
        ag.nodes["A2"],
        ag,
        graph,
        {evaluation.transition_id: evaluation},
        {},
        (),
        {},
        at=at,
        verifier_id="v",
        verifier_version="1",
    )
    builder.verify_abstraction(
        v2, node=ag.nodes["A2"].with_verification(v2), evidence_graph=graph
    )
    return builder, evaluation, v2, ag


def test_full_verified_cognitive_trace_is_replayable() -> None:
    graph = build_controlled_demonstrator().graph
    builder, evaluation, v2, ag = verified_episode(graph)
    builder.checkpoint(
        at=T1,
        evidence_graph=graph,
        abstraction_graph=ag,
        admissible_state={"T1": "ALLOWED", "A2": "VERIFIED"},
    )
    trace = builder.build(ended_at=T1)
    assert (
        evaluation.status is TransitionStatus.ALLOWED
        and v2.status is AbstractionStatus.VERIFIED
    )
    kinds = {x.event_type for x in trace.events}
    assert {
        TraceEventType.EVIDENCE_REGISTERED,
        TraceEventType.EVIDENCE_VERIFIED,
        TraceEventType.CLAIM_DECLARED,
        TraceEventType.SUPPORT_EVALUATED,
        TraceEventType.TRANSITION_EVALUATED,
        TraceEventType.UNCERTAINTY_PROPAGATED,
        TraceEventType.UNCERTAINTY_GATE_EVALUATED,
        TraceEventType.ABSTRACTION_PROPOSED,
        TraceEventType.ABSTRACTION_VERIFIED,
        TraceEventType.TRACE_CHECKPOINT,
    } <= kinds
    assert TraceEventType.EVIDENCE_BECAME_STALE not in kinds
    for event in trace.events:
        assert set(event.artifact_fingerprints) == set(event.artifact_ids)
        for artifact_id, digest in event.artifact_fingerprints.items():
            assert trace.artifact_map[artifact_id].fingerprint == digest
    validation = validate_trace(trace, builder.registry)
    assert validation.valid and not validation.unresolved_references
    result = replay_trace(trace, builder.registry)
    assert result.valid and result.halted_at_event_id is None
    assert len(result.replayed_event_ids) == len(trace.events)
    assert result.subject_outcomes["T1"]["outcome"] == "ALLOWED"
    assert result.subject_outcomes["A2"]["outcome"] == "VERIFIED"


def blocked_episode(graph: EvidenceGraph):
    builder, evaluation, v2, ag = verified_episode(graph)
    target = PlanningTarget(
        "A2", PlanningTargetType.ABSTRACTION_VERIFICATION, abstraction_id="A2"
    )
    verifications = (ag.nodes["A1"].verification_history[-1], v2)
    blockers = identify_blockers(
        target=target,
        evidence_graph=graph,
        transition_evaluations=(evaluation,),
        abstraction_verifications=verifications,
        abstraction_graph=ag,
        at=T1,
    )
    builder.identify_blockers(target, blockers, at=T1)
    plan = plan_evidence(
        target,
        evidence_graph=graph,
        at=T1,
        transition_evaluations=(evaluation,),
        abstraction_verifications=verifications,
        abstraction_graph=ag,
        **PLANNER,
    )
    builder.record_plan(plan)
    return builder, plan, evaluation, v2


def test_blocked_trace_preserves_root_cause_and_plan() -> None:
    graph = stale_graph()
    builder, plan, evaluation, v2 = blocked_episode(graph)
    trace = builder.build()
    assert evaluation.status is TransitionStatus.BLOCKED_STALE_EVIDENCE
    assert (
        v2.status is AbstractionStatus.BLOCKED
        and plan.status is not PlanStatus.COMPLETED
    )
    kinds = [x.event_type for x in trace.events]
    for kind in (
        TraceEventType.EVIDENCE_BECAME_STALE,
        TraceEventType.SUPPORT_EVALUATED,
        TraceEventType.TRANSITION_EVALUATED,
        TraceEventType.ABSTRACTION_BLOCKED,
        TraceEventType.BLOCKERS_IDENTIFIED,
        TraceEventType.PLAN_CREATED,
    ):
        assert kind in kinds
    explanation = trace.explain("A2")
    assert explanation.current_epistemic_outcome["outcome"] == "BLOCKED"
    assert explanation.current_planning_outcome["outcome"] == "WAITING_FOR_EVIDENCE"
    assert explanation.blocking_event_ids and explanation.planning_event_ids
    upstream_types = {
        explanation.event_types[x] for x in explanation.upstream_event_ids
    }
    assert (
        "EVIDENCE_BECAME_STALE" in upstream_types
        and "SUPPORT_EVALUATED" in upstream_types
    )
    plan_event = next(
        x for x in trace.events if x.event_type is TraceEventType.PLAN_CREATED
    )
    assert plan_event.details["action_blockers"]
    assert "REFRESH_STALE_EVIDENCE" in plan_event.details["action_types"].values()
    assert validate_trace(trace, builder.registry).valid


def test_contradiction_trace_cannot_imply_resolution() -> None:
    graph = build_controlled_demonstrator().graph
    builder = CognitiveTraceBuilder(("C1",), started_at=T0, **ACTOR)
    builder.register_evidence(graph.nodes["E1"].evidence)  # type: ignore[union-attr]
    builder.declare_claim(graph.nodes["C1"].claim)  # type: ignore[union-attr]
    artifact = ContradictionObject(
        "X",
        ContradictionType.DIRECT_VALUE_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        evidence_ids=("E1",),
        claim_ids=("C1",),
        detected_at=T1,
        conflict_dimensions=("measurement.value",),
        resolution_requirements=(
            ResolutionRequirement(
                "req-independent",
                ResolutionRequirementType.INDEPENDENT_EVIDENCE_REQUIRED,
                ("E1",),
                {},
                True,
                "independent",
            ),
        ),
    )
    builder.detect_contradiction(artifact)
    target = PlanningTarget("X", PlanningTargetType.CONTRADICTION_RESOLUTION)
    blockers = identify_blockers(
        target=target, evidence_graph=graph, contradiction_artifacts=(artifact,), at=T1
    )
    builder.identify_blockers(target, blockers, at=T1)
    plan = plan_evidence(
        target,
        evidence_graph=graph,
        at=T1,
        contradiction_artifacts=(artifact,),
        **PLANNER,
    )
    builder.record_plan(plan)
    trace = builder.build()
    kinds = {x.event_type for x in trace.events}
    assert TraceEventType.CONTRADICTION_DETECTED in kinds
    assert TraceEventType.CONTRADICTION_EVALUATED not in kinds
    detected = next(
        x for x in trace.events if x.event_type is TraceEventType.CONTRADICTION_DETECTED
    )
    assert list(detected.details["conflicting_evidence_ids"]) == ["E1"]
    assert (
        detected.details["resolution_requirements"][0]["requirement_type"]
        == "INDEPENDENT_EVIDENCE_REQUIRED"
    )
    assert trace.explain("X").current_epistemic_outcome["outcome"] == "UNRESOLVED"
    plan_event = next(
        x for x in trace.events if x.event_type is TraceEventType.PLAN_CREATED
    )
    assert "REQUEST_INDEPENDENT_EVIDENCE" in plan_event.details["action_types"].values()
    with pytest.raises(ValueError, match="resolution result"):
        builder.evaluate_contradiction(artifact)


def test_replanning_trace_preserves_prior_plan_history() -> None:
    stale = stale_graph()
    demo = build_controlled_demonstrator()
    builder = CognitiveTraceBuilder(("T1",), started_at=T0, **ACTOR)
    builder.register_evidence(stale.nodes["E1"].evidence)  # type: ignore[union-attr]
    for claim_id in ("C1", "C2"):
        builder.declare_claim(stale.nodes[claim_id].claim)  # type: ignore[union-attr]
    builder.evaluate_staleness(stale.nodes["E1"].evidence, at=T1)  # type: ignore[union-attr]
    builder.evaluate_support(stale.is_support_complete("C2", at=T1), stale)
    old_evaluation = evaluate_transition(demo.transitions[0], stale, at=T1)
    builder.evaluate_transition(old_evaluation, stale)
    target = PlanningTarget(
        "T1", PlanningTargetType.TRANSITION_PERMISSION, transition_id="T1"
    )
    blockers = identify_blockers(
        target=target,
        evidence_graph=stale,
        transition_evaluations=(old_evaluation,),
        at=T1,
    )
    builder.identify_blockers(target, blockers, at=T1)
    first = plan_evidence(
        target,
        evidence_graph=stale,
        at=T1,
        transition_evaluations=(old_evaluation,),
        **PLANNER,
    )
    first_event = builder.record_plan(first)
    fresh = demo.graph
    execution = PlanExecutionResult(
        first.plan_id,
        (first.actions[0].action_id,),
        (),
        ("E1",),
        (),
        (),
        (),
        (),
        (),
        T2,
        "executor",
        "1",
    )
    execution_event = builder.record_execution(execution, first)
    builder.register_evidence(fresh.nodes["E1"].evidence, at=T2)  # type: ignore[union-attr]
    builder.evaluate_support(fresh.is_support_complete("C2", at=T2), fresh)
    new_evaluation = evaluate_transition(demo.transitions[0], fresh, at=T2)
    builder.evaluate_transition(new_evaluation, fresh)
    second = replan(
        first,
        execution,
        evidence_graph=fresh,
        at=T2,
        transition_evaluations=(new_evaluation,),
    )
    second_event = builder.record_plan(second, inputs=(execution_event.event_id,))
    trace = builder.build()
    assert (
        second.status is PlanStatus.COMPLETED
        and second.previous_plan_id == first.plan_id
    )
    assert second_event.event_type is TraceEventType.REPLAN_CREATED
    assert execution_event.event_id in second_event.input_event_ids
    assert first_event.event_id in execution_event.input_event_ids
    assert first.plan_id in trace.artifact_map and second.plan_id in trace.artifact_map
    explanation = trace.explain("T1")
    assert explanation.current_epistemic_outcome["outcome"] == "ALLOWED"
    assert explanation.current_planning_outcome["outcome"] == "COMPLETED"
    outcomes = [
        x.outcome
        for x in trace.events_for("T1")
        if x.event_type is TraceEventType.TRANSITION_EVALUATED
    ]
    assert outcomes == ["BLOCKED_STALE_EVIDENCE", "ALLOWED"]
    assert validate_trace(trace, builder.registry).valid


def test_abstention_is_explicit_trace_outcome() -> None:
    graph = build_controlled_demonstrator().graph
    from app.research.vera_rap import ContradictionResolutionResult, evaluate_resolution

    artifact = ContradictionObject(
        "X",
        ContradictionType.CLAIM_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        claim_ids=("C1",),
        detected_at=T1,
        conflict_dimensions=("claim",),
        resolution_requirements=(
            ResolutionRequirement(
                "req-1",
                ResolutionRequirementType.HUMAN_REVIEW_REQUIRED,
                ("C1",),
                {},
                True,
                "review",
            ),
        ),
    )
    exhausted = evaluate_resolution(
        artifact,
        ContradictionResolutionResult(
            ContradictionStatus.IRRESOLVABLE,
            (),
            ("req-1",),
            (),
            (),
            (),
            (),
            "r",
            "1",
            T1,
            "exhausted",
        ),
        graph,
    )
    builder = CognitiveTraceBuilder(("C1",), started_at=T0, **ACTOR)
    builder.declare_claim(graph.nodes["C1"].claim)  # type: ignore[union-attr]
    builder.detect_contradiction(artifact)
    builder.evaluate_contradiction(exhausted)
    target = PlanningTarget("X", PlanningTargetType.CONTRADICTION_RESOLUTION)
    blockers = identify_blockers(
        target=target, evidence_graph=graph, contradiction_artifacts=(exhausted,), at=T1
    )
    builder.identify_blockers(target, blockers, at=T1)
    plan = plan_evidence(
        target,
        evidence_graph=graph,
        at=T1,
        contradiction_artifacts=(exhausted,),
        **PLANNER,
    )
    event = builder.record_plan(plan)
    trace = builder.build()
    assert plan.terminal and event.event_type is TraceEventType.PLANNER_ABSTAINED
    assert event.details["abstain_reason"] == "NO_ADMISSIBLE_RESOLUTION_PATH"
    assert trace.explain("X").current_epistemic_outcome["outcome"] == "IRRESOLVABLE"
    assert trace.explain("X").current_planning_outcome["outcome"] == "ABSTAINED"
    kinds = {x.event_type for x in trace.events}
    assert not kinds & {
        TraceEventType.TRANSITION_EVALUATED,
        TraceEventType.ABSTRACTION_VERIFIED,
    }
    evaluated = next(
        x
        for x in trace.events
        if x.event_type is TraceEventType.CONTRADICTION_EVALUATED
    )
    assert evaluated.details["outcome"] == "IRRESOLVABLE" and list(
        evaluated.details["unsatisfied_requirement_ids"]
    ) == ["req-1"]
    assert replay_trace(trace, builder.registry).valid


def test_trace_detects_artifact_version_tampering() -> None:
    graph = build_controlled_demonstrator().graph
    builder, _, _, _ = verified_episode(graph)
    trace = builder.build()
    assert validate_trace(trace, builder.registry).valid
    victim = next(
        x
        for x in trace.artifacts
        if x.artifact_type is ArtifactType.TRANSITION_EVALUATION
    )
    tampered = ArtifactRegistry(
        tuple(x for x in trace.artifacts if x.artifact_id != victim.artifact_id)
    )
    tampered.register(replace(victim, fingerprint="f" * 64))
    validation = validate_trace(trace, tampered)
    assert (
        not validation.valid and victim.artifact_id in validation.fingerprint_mismatches
    )
    assert not replay_trace(trace, tampered).valid
    with pytest.raises(ValueError, match="different fingerprint"):
        tampered.register(victim)
    with pytest.raises(ValueError, match="different version"):
        trace.append_event(
            TraceEvent(
                TraceEventType.TRACE_CHECKPOINT,
                ("A2",),
                (victim.artifact_id,),
                (),
                T2,
                "x",
                "1",
                None,
                {victim.artifact_id: "f" * 64},
            )
        )


def event(
    kind: TraceEventType, subject: str, inputs: tuple[str, ...] = (), at: datetime = T1
) -> TraceEvent:
    return TraceEvent(
        kind, (subject,), (), inputs, at, "x", "1", {"outcome": "TEST"}, {}
    )


def test_missing_predecessor_event_invalidates_trace() -> None:
    evaluated = event(TraceEventType.TRANSITION_EVALUATED, "T1")
    trace = CognitiveTrace(("T1",), (evaluated,), (), T0)
    validation = validate_trace(trace)
    assert not validation.valid and validation.unresolved_references
    with pytest.raises(ValueError, match="missing input events"):
        CognitiveTrace(
            ("T1",),
            (event(TraceEventType.TRANSITION_EVALUATED, "T1", ("event-missing",)),),
            (),
            T0,
        )
    early = event(TraceEventType.SUPPORT_EVALUATED, "C1", at=T1)
    late = event(TraceEventType.CLAIM_DECLARED, "C1", at=T2)
    with pytest.raises(ValueError, match="chronology"):
        CognitiveTrace(
            ("C1",),
            (
                late,
                TraceEvent(
                    TraceEventType.SUPPORT_EVALUATED,
                    ("C1",),
                    (),
                    (late.event_id,),
                    T1,
                    "x",
                    "1",
                    None,
                    {},
                ),
            ),
            (),
            T0,
        )
    del early


def test_trace_event_cycle_is_rejected() -> None:
    a = event(TraceEventType.CLAIM_DECLARED, "C1")
    b = TraceEvent(
        TraceEventType.CLAIM_EVALUATED,
        ("C1",),
        (),
        (a.event_id,),
        T1,
        "x",
        "1",
        {"outcome": "SUPPORTED"},
        {},
    )
    # Content-addressed identities make a forged cycle unconstructible through the schema.
    payload = json.loads(a.canonical_json())
    payload["input_event_ids"] = [b.event_id]
    with pytest.raises(ValueError, match="event_id"):
        TraceEvent.from_dict(payload)
    # Even a cycle injected past the constructor is rejected by DAG validation.
    object.__setattr__(a, "input_event_ids", (b.event_id,))
    with pytest.raises(ValueError, match="cycle"):
        CognitiveTrace(("C1",), (a, b), (), T0)


def test_historical_trace_is_not_rewritten_by_new_epistemic_state() -> None:
    fresh = build_controlled_demonstrator().graph
    builder, evaluation, v2, _ = verified_episode(fresh)
    first = builder.build(ended_at=T1)
    serialized = first.canonical_json()
    successor = first.successor(("A2",), T2)
    stale = stale_graph()
    later = CognitiveTraceBuilder(("A2",), started_at=T2, parent=first, **ACTOR)
    later.register_evidence(stale.nodes["E1"].evidence, at=T2)  # type: ignore[union-attr]
    later.evaluate_staleness(stale.nodes["E1"].evidence, at=T2)  # type: ignore[union-attr]
    later.declare_claim(stale.nodes["C2"].claim, at=T2)  # type: ignore[union-attr]
    later.evaluate_support(stale.is_support_complete("C2", at=T2), stale)
    blocked = evaluate_transition(evaluation.transition_definition, stale, at=T2)
    later.evaluate_transition(blocked, stale)
    second = later.build()
    assert (
        first.canonical_json() == serialized
        and first.explain("T1").current_epistemic_outcome["outcome"] == "ALLOWED"
    )
    assert (
        successor.parent_trace_id == first.trace_id
        and successor.parent_trace_fingerprint == first.fingerprint
    )
    assert second.parent_trace_fingerprint == first.fingerprint
    assert (
        second.explain("T1").current_epistemic_outcome["outcome"]
        == "BLOCKED_STALE_EVIDENCE"
    )
    assert v2.status is AbstractionStatus.VERIFIED
    with pytest.raises(FrozenInstanceError):
        first.ended_at = T2  # type: ignore[misc]
    with pytest.raises(ValueError, match="both"):
        CognitiveTrace(("A2",), (), (), T2, parent_trace_id=first.trace_id)


def test_trace_identity_is_insertion_order_independent() -> None:
    graph = build_controlled_demonstrator().graph
    trace = verified_episode(graph)[0].build()
    reordered = CognitiveTrace(
        trace.root_subject_ids,
        tuple(reversed(trace.events)),
        tuple(reversed(trace.artifacts)),
        trace.started_at,
    )
    assert (
        reordered.fingerprint == trace.fingerprint
        and reordered.trace_id == trace.trace_id
    )
    again = verified_episode(graph)[0].build()
    assert again.fingerprint == trace.fingerprint
    restored = CognitiveTrace.from_canonical_json(trace.canonical_json())
    assert restored.fingerprint == trace.fingerprint


def test_trace_schema_rejects_private_reasoning_fields() -> None:
    graph = build_controlled_demonstrator().graph
    trace = verified_episode(graph)[0].build()
    for key in ("chain_of_thought", "internal_reasoning", "scratchpad"):
        payload = json.loads(trace.canonical_json())
        payload[key] = "I think the evidence is fine"
        with pytest.raises(ValueError, match="schema"):
            CognitiveTrace.from_dict(payload)
        with pytest.raises(ValueError, match="private reasoning"):
            TraceEvent(
                TraceEventType.TRACE_CHECKPOINT,
                ("A2",),
                (),
                (),
                T1,
                "x",
                "1",
                {key: "..."},
                {},
            )
        with pytest.raises(ValueError, match="private reasoning"):
            TraceEvent(
                TraceEventType.TRACE_CHECKPOINT,
                ("A2",),
                (),
                (),
                T1,
                "x",
                "1",
                {"nested": {key: "..."}},
                {},
            )
    payload = json.loads(trace.canonical_json())
    payload["events"][0]["event_type"] = "MODEL_THOUGHT"
    with pytest.raises(ValueError):
        CognitiveTrace.from_dict(payload)
    payload = json.loads(trace.canonical_json())
    payload["trace_id"] = "trace-forged"
    with pytest.raises(ValueError, match="trace_id"):
        CognitiveTrace.from_dict(payload)
    for member in (TraceEventType.PLAN_CREATED, ArtifactType.PLAN):
        with pytest.raises(TypeError):
            bool(member)


def test_trace_explain_returns_machine_readable_lineage() -> None:
    graph = stale_graph()
    builder, plan, _, _ = blocked_episode(graph)
    trace = builder.build()
    explanation = trace.explain("A2")
    types = set(explanation.event_types.values())
    assert {
        "EVIDENCE_REGISTERED",
        "CLAIM_DECLARED",
        "SUPPORT_EVALUATED",
        "TRANSITION_EVALUATED",
        "UNCERTAINTY_PROPAGATED",
        "ABSTRACTION_PROPOSED",
        "ABSTRACTION_BLOCKED",
        "BLOCKERS_IDENTIFIED",
        "PLAN_CREATED",
    } <= types
    assert plan.plan_id in explanation.artifact_ids
    assert any(x.startswith("E1@") for x in explanation.artifact_ids)
    payload = json.loads(explanation.canonical_json())
    assert set(payload) == {
        "subject_id",
        "related_event_ids",
        "artifact_ids",
        "upstream_event_ids",
        "downstream_event_ids",
        "current_epistemic_outcome",
        "current_planning_outcome",
        "blocking_event_ids",
        "planning_event_ids",
        "event_types",
    }
    summary = trace.completeness()
    assert summary.claim_evaluation_coverage["denominator"] == 2
    assert summary.abstraction_trace_coverage == {
        "numerator": 2,
        "denominator": 2,
        "fraction": 1.0,
    }
    assert summary.planning_trace_coverage["numerator"] == 1


def test_claim_evaluation_is_distinct_from_declaration() -> None:
    graph = build_controlled_demonstrator().graph
    declared = graph.nodes["C1"].claim  # type: ignore[union-attr]
    supported = declared.with_evaluation(
        ClaimEvaluationResult(
            EpistemicState.SUPPORTED, ("E1",), (), (), (), (), "evaluator", "1", T1
        )
    )
    builder = CognitiveTraceBuilder(("C1",), started_at=T0, **ACTOR)
    builder.register_evidence(graph.nodes["E1"].evidence)  # type: ignore[union-attr]
    declaration = builder.declare_claim(declared)
    evaluation = builder.evaluate_claim(
        supported, graph=swap(graph, "C1", ClaimNode(supported))
    )
    trace = builder.build()
    assert declaration.event_id in evaluation.input_event_ids
    assert (
        reference_for(declared).artifact_id == "C1@v0"
        and reference_for(supported).artifact_id == "C1@v1"
    )
    assert {
        reference_for(declared).artifact_id,
        reference_for(supported).artifact_id,
    } <= set(trace.artifact_map)
    assert any(
        trace.artifact_map[x].artifact_type is ArtifactType.CLAIM_EVALUATION
        for x in evaluation.artifact_ids
    )
    assert trace.explain("C1").current_epistemic_outcome["outcome"] == "SUPPORTED"
    assert validate_trace(trace, builder.registry).valid
