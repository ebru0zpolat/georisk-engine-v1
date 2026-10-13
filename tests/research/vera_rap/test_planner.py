import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from app.research.vera_rap import (
    NO_ADMISSIBLE_RESOLUTION_PATH,
    AbstractionEdge,
    AbstractionGraph,
    AbstractionLevel,
    AbstractionNode,
    AbstractionRule,
    AbstractionStatus,
    BlockerSeverity,
    BlockerType,
    ClaimNode,
    ClaimObject,
    CognitiveState,
    CognitiveTransition,
    ContradictionObject,
    ContradictionResolutionResult,
    ContradictionStatus,
    ContradictionType,
    EpistemicState,
    EvidenceAction,
    EvidenceActionType,
    EvidenceGraph,
    EvidenceNode,
    EvidencePlan,
    PlanExecutionResult,
    PlanningTarget,
    PlanningTargetType,
    PlanStatus,
    RequirementType,
    ResolutionRequirement,
    ResolutionRequirementType,
    TransitionRequirement,
    TransitionStatus,
    Uncertainty,
    build_controlled_demonstrator,
    evaluate_resolution,
    evaluate_transition,
    identify_blockers,
    is_action_admissible,
    plan_evidence,
    replan,
    verify_abstraction,
)

AT = datetime(2026, 1, 2, tzinfo=UTC)
LATER = datetime(2026, 1, 3, tzinfo=UTC)
PLANNER = {"planner_id": "planner", "planner_version": "1"}


def swap(graph: EvidenceGraph, node_id: str, node: object) -> EvidenceGraph:
    nodes = tuple(node if x.node_id == node_id else x for x in graph.nodes.values())
    return EvidenceGraph(nodes, graph.edges)  # type: ignore[arg-type]


def stale_graph() -> EvidenceGraph:
    demo = build_controlled_demonstrator()
    old = demo.graph.nodes["E1"].evidence  # type: ignore[union-attr]
    expiring = EvidenceNode(replace(old, valid_until=datetime(2026, 1, 1, tzinfo=UTC)))
    return swap(demo.graph, "E1", expiring)


def transition(*requirements: TransitionRequirement) -> CognitiveTransition:
    return CognitiveTransition(
        "TX",
        "synthetic",
        CognitiveState("source", "SOURCE", 0, ("C1",), ("E1",)),
        CognitiveState("target", "TARGET", 1, ("C2",)),
        requirements,
        "evaluator",
        "1",
    )


def requirement(
    kind: RequirementType, subject: str, parameters: dict | None = None, rid: str = "R1"
) -> TransitionRequirement:
    return TransitionRequirement(rid, kind, subject, parameters or {}, True, "gate")


TARGET = PlanningTarget(
    "tx", PlanningTargetType.TRANSITION_PERMISSION, transition_id="TX"
)


def mandatory_types(plan: EvidencePlan) -> list[EvidenceActionType]:
    return [x.action_type for x in plan.actions if x.mandatory]


def abstraction_fixture(graph: EvidenceGraph):
    demo = build_controlled_demonstrator()
    tr = demo.transitions[0]
    evaluation = evaluate_transition(tr, graph, at=AT)
    a1 = AbstractionNode(
        "A1",
        AbstractionLevel.OBSERVATION,
        "observation",
        claim_ids=("C1",),
        created_at=AT,
    )
    a2 = AbstractionNode(
        "A2",
        AbstractionLevel.PHYSICAL_STATE,
        "physical",
        claim_ids=("C2",),
        source_abstraction_ids=("A1",),
        created_at=AT,
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
    ag = AbstractionGraph(
        (a1, a2), (AbstractionEdge("A1", "A2", tr.transition_id, True),), (rule,), (tr,)
    )
    v1 = verify_abstraction(
        a1, ag, graph, {}, {}, (), {}, at=AT, verifier_id="v", verifier_version="1"
    )
    v2 = verify_abstraction(
        a2,
        ag,
        graph,
        {evaluation.transition_id: evaluation},
        {},
        (),
        {},
        at=AT,
        verifier_id="v",
        verifier_version="1",
    )
    return ag, evaluation, v1, v2


def test_missing_evidence_plan_targets_actual_deficit() -> None:
    demo = build_controlled_demonstrator()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "missing")),
        demo.graph,
        at=AT,
    )
    plan = plan_evidence(
        TARGET,
        evidence_graph=demo.graph,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    assert mandatory_types(plan) == [
        EvidenceActionType.RETRIEVE_EVIDENCE,
        EvidenceActionType.RECOMPUTE_SUPPORT,
        EvidenceActionType.REEVALUATE_TRANSITION,
    ]
    retrieve = plan.actions[0]
    missing = next(
        x for x in plan.blockers if x.blocker_type is BlockerType.MISSING_EVIDENCE
    )
    assert retrieve.subject_ids == ("missing",)
    assert missing.blocker_id in retrieve.addresses_blocker_ids
    assert plan.status is PlanStatus.WAITING_FOR_EVIDENCE and not plan.terminal


def test_stale_evidence_produces_refresh_action() -> None:
    graph = stale_graph()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1")), graph, at=AT
    )
    assert evaluation.status is TransitionStatus.BLOCKED_STALE_EVIDENCE
    plan = plan_evidence(
        TARGET,
        evidence_graph=graph,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    assert mandatory_types(plan) == [
        EvidenceActionType.REFRESH_STALE_EVIDENCE,
        EvidenceActionType.RECOMPUTE_SUPPORT,
        EvidenceActionType.REEVALUATE_TRANSITION,
    ]
    assert plan.actions[0].subject_ids == ("E1",)
    assert EvidenceActionType.RETRIEVE_EVIDENCE not in mandatory_types(plan)


def contradiction(
    requirements: tuple[ResolutionRequirement, ...],
) -> ContradictionObject:
    return ContradictionObject(
        "X",
        ContradictionType.DIRECT_VALUE_CONFLICT,
        ContradictionStatus.UNRESOLVED,
        evidence_ids=("E1",),
        claim_ids=("C1",),
        detected_at=AT,
        conflict_dimensions=("measurement.value",),
        resolution_requirements=requirements,
    )


def test_planner_uses_contradiction_resolution_requirements() -> None:
    demo = build_controlled_demonstrator()
    artifact = contradiction(
        (
            ResolutionRequirement(
                "req-independent",
                ResolutionRequirementType.INDEPENDENT_EVIDENCE_REQUIRED,
                ("E1",),
                {},
                True,
                "independent evidence required",
            ),
        )
    )
    target = PlanningTarget("X", PlanningTargetType.CONTRADICTION_RESOLUTION)
    plan = plan_evidence(
        target,
        evidence_graph=demo.graph,
        at=AT,
        contradiction_artifacts=(artifact,),
        **PLANNER,
    )
    assert mandatory_types(plan) == [
        EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT,
    ]
    request, resolve = plan.actions
    assert request.parameters["requirement_id"] == "req-independent"
    assert resolve.preconditions == (request.action_id,)
    assert artifact.status is ContradictionStatus.UNRESOLVED
    assert all("RESOLVED" not in x.parameters.values() for x in plan.actions)


def uncertain_graph() -> EvidenceGraph:
    demo = build_controlled_demonstrator()
    claim = ClaimObject(
        "C2",
        "abstracts",
        "physical_state",
        "hazard",
        None,
        EpistemicState.INFERRED,
        parent_claim_ids=("C1",),
        uncertainty=Uncertainty("declared", confidence=0.5),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        derivation_method="synthetic",
    )
    return swap(demo.graph, "C2", ClaimNode(claim))


def test_uncertainty_blocker_generates_evidence_reduction_plan() -> None:
    graph = uncertain_graph()
    evaluation = evaluate_transition(
        transition(
            requirement(
                RequirementType.MAX_UNCERTAINTY,
                "C2",
                {"metric": "minimum_confidence", "threshold": 0.9},
            )
        ),
        graph,
        at=AT,
    )
    assert evaluation.status is TransitionStatus.BLOCKED_UNCERTAINTY
    plan = plan_evidence(
        TARGET,
        evidence_graph=graph,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    assert mandatory_types(plan) == [
        EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        EvidenceActionType.REDUCE_UNCERTAINTY,
        EvidenceActionType.REEVALUATE_TRANSITION,
    ]
    request, reduce, _ = plan.actions
    assert reduce.preconditions == (request.action_id,)
    assert next(
        x for x in plan.blockers if x.blocker_type is BlockerType.EXCESSIVE_UNCERTAINTY
    )


def test_planner_targets_root_cause_not_downstream_symptoms() -> None:
    graph = stale_graph()
    ag, evaluation, v1, v2 = abstraction_fixture(graph)
    assert v2.status is AbstractionStatus.BLOCKED
    target = PlanningTarget(
        "A2", PlanningTargetType.ABSTRACTION_VERIFICATION, abstraction_id="A2"
    )
    plan = plan_evidence(
        target,
        evidence_graph=graph,
        at=AT,
        transition_evaluations=(evaluation,),
        abstraction_verifications=(v1, v2),
        abstraction_graph=ag,
        **PLANNER,
    )
    types = mandatory_types(plan)
    assert types.count(EvidenceActionType.REFRESH_STALE_EVIDENCE) == 1
    assert types[0] is EvidenceActionType.REFRESH_STALE_EVIDENCE
    assert types[-1] is EvidenceActionType.REEVALUATE_ABSTRACTION
    assert set(types) == {
        EvidenceActionType.REFRESH_STALE_EVIDENCE,
        EvidenceActionType.RECOMPUTE_SUPPORT,
        EvidenceActionType.REEVALUATE_TRANSITION,
        EvidenceActionType.REEVALUATE_ABSTRACTION,
    }
    stale = [x for x in plan.blockers if x.blocker_type is BlockerType.STALE_EVIDENCE]
    assert len(stale) == 1 and stale[0].subject_id == "E1"
    kinds = {x.blocker_type for x in plan.blockers}
    assert {
        BlockerType.SUPPORT_INCOMPLETE,
        BlockerType.TRANSITION_BLOCKED,
        BlockerType.ABSTRACTION_BLOCKED,
    } <= kinds
    root = next(
        x
        for x in plan.blockers
        if x.blocker_type is BlockerType.ABSTRACTION_BLOCKED and x.subject_id == "A2"
    )
    assert root.caused_by


def test_irresolvable_blocker_causes_abstention() -> None:
    demo = build_controlled_demonstrator()
    artifact = contradiction(
        (
            ResolutionRequirement(
                "req-1",
                ResolutionRequirementType.HUMAN_REVIEW_REQUIRED,
                ("C1",),
                {},
                True,
                "review",
            ),
        )
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
            "resolver",
            "1",
            AT,
            "exhausted",
        ),
        demo.graph,
    )
    target = PlanningTarget("X", PlanningTargetType.CONTRADICTION_RESOLUTION)
    plan = plan_evidence(
        target,
        evidence_graph=demo.graph,
        at=AT,
        contradiction_artifacts=(exhausted,),
        **PLANNER,
    )
    assert plan.terminal and plan.status is PlanStatus.ABSTAINED
    assert plan.abstain_reason == NO_ADMISSIBLE_RESOLUTION_PATH
    assert [x.action_type for x in plan.actions] == [EvidenceActionType.ABSTAIN]
    terminal = plan.blockers[-1]
    assert terminal.severity is BlockerSeverity.TERMINAL and not terminal.resolvable


def execution(
    plan: EvidencePlan, *, completed: bool, new_evidence: tuple[str, ...] = ()
) -> PlanExecutionResult:
    ids = tuple(x.action_id for x in plan.actions[:1])
    return PlanExecutionResult(
        plan.plan_id,
        ids if completed else (),
        () if completed else ids,
        new_evidence,
        (),
        (),
        (),
        (),
        (),
        LATER,
        "executor",
        "1",
    )


def test_replanning_uses_new_epistemic_state() -> None:
    stale = stale_graph()
    definition = transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1"))
    old_evaluation = evaluate_transition(definition, stale, at=AT)
    first = plan_evidence(
        TARGET,
        evidence_graph=stale,
        at=AT,
        transition_evaluations=(old_evaluation,),
        **PLANNER,
    )
    assert first.actions[0].action_type is EvidenceActionType.REFRESH_STALE_EVIDENCE
    fresh = build_controlled_demonstrator().graph
    second = replan(
        first,
        execution(first, completed=True, new_evidence=("E1",)),
        evidence_graph=fresh,
        at=LATER,
        transition_evaluations=(old_evaluation,),
    )
    assert second.previous_plan_id == first.plan_id
    assert BlockerType.STALE_EVIDENCE not in {x.blocker_type for x in second.blockers}
    assert mandatory_types(second) == [EvidenceActionType.REEVALUATE_TRANSITION]
    assert list(second.metadata["plan_history"]) == [first.plan_id]
    allowed = evaluate_transition(definition, fresh, at=LATER)
    third = replan(
        second,
        execution(second, completed=True),
        evidence_graph=fresh,
        at=LATER,
        transition_evaluations=(allowed,),
    )
    assert third.status is PlanStatus.COMPLETED and third.terminal and not third.actions


def test_replanning_does_not_repeat_identical_plan_forever() -> None:
    stale = stale_graph()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1")), stale, at=AT
    )
    first = plan_evidence(
        TARGET,
        evidence_graph=stale,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    second = replan(
        first,
        execution(first, completed=False),
        evidence_graph=stale,
        at=LATER,
        transition_evaluations=(evaluation,),
    )
    assert (
        second.status is PlanStatus.BLOCKED
        and not second.terminal
        and second.no_progress_count == 1
    )
    third = replan(
        second,
        execution(second, completed=False),
        evidence_graph=stale,
        at=LATER,
        transition_evaluations=(evaluation,),
    )
    assert third.terminal and third.status is PlanStatus.ABSTAINED
    assert third.abstain_reason == NO_ADMISSIBLE_RESOLUTION_PATH
    assert list(third.metadata["plan_history"]) == [first.plan_id, second.plan_id]
    with pytest.raises(ValueError, match="terminal"):
        replan(third, execution(third, completed=False), evidence_graph=stale, at=LATER)


def candidates(blocker_id: str, **fields: object) -> tuple[EvidenceAction, ...]:
    return tuple(
        EvidenceAction(
            EvidenceActionType.RETRIEVE_EVIDENCE,
            ("missing",),
            (blocker_id,),
            {"source": name},
            (),
            "evidence registered",
            fields[name][0],  # type: ignore[index]
            fields[name][1],  # type: ignore[index]
            True,
        )
        for name in sorted(fields)
    )


def missing_evidence_case() -> tuple[EvidenceGraph, tuple, str]:
    demo = build_controlled_demonstrator()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "missing")),
        demo.graph,
        at=AT,
    )
    blockers = identify_blockers(
        target=TARGET,
        evidence_graph=demo.graph,
        transition_evaluations=(evaluation,),
        at=AT,
    )
    blocker_id = next(
        x.blocker_id for x in blockers if x.blocker_type is BlockerType.MISSING_EVIDENCE
    )
    return demo.graph, (evaluation,), blocker_id


def test_planner_prefers_lower_cost_equivalent_action() -> None:
    graph, evaluations, blocker_id = missing_evidence_case()
    plan = plan_evidence(
        TARGET,
        evidence_graph=graph,
        at=AT,
        transition_evaluations=evaluations,
        candidate_actions=candidates(
            blocker_id, archive=(10.0, None), sensor=(2.0, None)
        ),
        **PLANNER,
    )
    chosen = plan.actions[0]
    assert chosen.action_type is EvidenceActionType.RETRIEVE_EVIDENCE
    assert chosen.parameters["source"] == "sensor" and chosen.estimated_cost == 2.0
    assert mandatory_types(plan).count(EvidenceActionType.RETRIEVE_EVIDENCE) == 1


def test_information_gain_breaks_equal_cost_ties() -> None:
    graph, evaluations, blocker_id = missing_evidence_case()
    plan = plan_evidence(
        TARGET,
        evidence_graph=graph,
        at=AT,
        transition_evaluations=evaluations,
        candidate_actions=candidates(blocker_id, alpha=(2.0, 0.4), beta=(2.0, 0.8)),
        **PLANNER,
    )
    assert plan.actions[0].parameters["source"] == "beta"
    assert plan.actions[0].estimated_information_gain == 0.8


def test_historical_plan_is_immutable() -> None:
    stale = stale_graph()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1")), stale, at=AT
    )
    first = plan_evidence(
        TARGET,
        evidence_graph=stale,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    serialized = first.canonical_json()
    fresh = build_controlled_demonstrator().graph
    second = replan(
        first,
        execution(first, completed=True, new_evidence=("E1",)),
        evidence_graph=fresh,
        at=LATER,
        transition_evaluations=(evaluation,),
    )
    assert first.canonical_json() == serialized
    assert second.plan_id != first.plan_id and second.created_at == LATER
    with pytest.raises(FrozenInstanceError):
        first.status = PlanStatus.COMPLETED  # type: ignore[misc]
    restored = EvidencePlan.from_canonical_json(serialized)
    assert restored.fingerprint == first.fingerprint
    again = plan_evidence(
        TARGET,
        evidence_graph=stale,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    assert again.fingerprint == first.fingerprint


def test_plan_creation_does_not_change_epistemic_state() -> None:
    graph = stale_graph()
    ag, evaluation, v1, v2 = abstraction_fixture(graph)
    fingerprint = graph.fingerprint
    plan = plan_evidence(
        PlanningTarget(
            "A2", PlanningTargetType.ABSTRACTION_VERIFICATION, abstraction_id="A2"
        ),
        evidence_graph=graph,
        at=AT,
        transition_evaluations=(evaluation,),
        abstraction_verifications=(v1, v2),
        abstraction_graph=ag,
        **PLANNER,
    )
    assert plan.status is not PlanStatus.COMPLETED and plan.mandatory_actions
    assert evaluation.status is TransitionStatus.BLOCKED_STALE_EVIDENCE
    assert v2.status is AbstractionStatus.BLOCKED
    assert graph.fingerprint == fingerprint
    assert (
        evaluate_transition(ag.transitions["T1"], graph, at=AT).status
        is TransitionStatus.BLOCKED_STALE_EVIDENCE
    )
    with pytest.raises(ValueError, match="inconsistent|COMPLETED"):
        EvidencePlan(
            plan.target,
            plan.blockers,
            (),
            True,
            None,
            PlanStatus.COMPLETED,
            "p",
            "1",
            AT,
        )


def test_action_admissibility_rejects_bypass_and_stale_verification() -> None:
    graph = stale_graph()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "E1")), graph, at=AT
    )
    blockers = identify_blockers(
        target=TARGET, evidence_graph=graph, transition_evaluations=(evaluation,), at=AT
    )
    stale = next(x for x in blockers if x.blocker_type is BlockerType.STALE_EVIDENCE)
    verify = EvidenceAction(
        EvidenceActionType.VERIFY_EVIDENCE,
        ("E1",),
        (stale.blocker_id,),
        {},
        (),
        "x",
        None,
        None,
        True,
    )
    assert is_action_admissible(verify, blockers, graph, at=AT)[0] is False
    reduce = EvidenceAction(
        EvidenceActionType.REDUCE_UNCERTAINTY,
        ("C2",),
        (stale.blocker_id,),
        {},
        (),
        "x",
        None,
        None,
        True,
    )
    assert is_action_admissible(reduce, blockers, graph, at=AT)[0] is False
    with pytest.raises(ValueError, match="mutation"):
        EvidenceAction(
            EvidenceActionType.RETRIEVE_EVIDENCE,
            ("E1",),
            (stale.blocker_id,),
            {"mark_valid": True},
            (),
            "x",
            None,
            None,
            True,
        )
    assert not any(
        name in {"IGNORE_STALENESS", "USE_ANYWAY", "MANUALLY_MARK_VALID"}
        for name in EvidenceActionType.__members__
    )


def test_enum_coercion_and_forgery_are_rejected() -> None:
    for member in (
        PlanningTargetType.CLAIM_SUPPORT,
        BlockerType.STALE_EVIDENCE,
        EvidenceActionType.ABSTAIN,
        PlanStatus.READY,
    ):
        with pytest.raises(TypeError):
            bool(member)
        with pytest.raises(TypeError):
            str(member)
    demo = build_controlled_demonstrator()
    evaluation = evaluate_transition(
        transition(requirement(RequirementType.EVIDENCE_VERIFIED, "missing")),
        demo.graph,
        at=AT,
    )
    plan = plan_evidence(
        TARGET,
        evidence_graph=demo.graph,
        at=AT,
        transition_evaluations=(evaluation,),
        **PLANNER,
    )
    payload = json.loads(plan.canonical_json())
    payload["status"], payload["terminal"] = "COMPLETED", True
    with pytest.raises(ValueError):
        EvidencePlan.from_canonical_json(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    payload = json.loads(plan.canonical_json())
    payload["plan_id"] = "plan-forged"
    with pytest.raises(ValueError, match="plan_id"):
        EvidencePlan.from_dict(payload)
    result = execution(plan, completed=True)
    assert (
        PlanExecutionResult.from_canonical_json(result.canonical_json()).fingerprint
        == result.fingerprint
    )
    assert PlanningTarget.from_canonical_json(TARGET.canonical_json()) == TARGET


def test_claim_support_target_ends_with_recompute_support() -> None:
    graph = stale_graph()
    target = PlanningTarget("C2", PlanningTargetType.CLAIM_SUPPORT, claim_id="C2")
    plan = plan_evidence(target, evidence_graph=graph, at=AT, **PLANNER)
    types = mandatory_types(plan)
    assert types[0] is EvidenceActionType.REFRESH_STALE_EVIDENCE
    assert types[-1] is EvidenceActionType.RECOMPUTE_SUPPORT
    assert graph.nodes["C2"].claim.epistemic_state is EpistemicState.INFERRED  # type: ignore[union-attr]
    complete = plan_evidence(
        target, evidence_graph=build_controlled_demonstrator().graph, at=AT, **PLANNER
    )
    assert complete.status is PlanStatus.COMPLETED and not complete.actions
