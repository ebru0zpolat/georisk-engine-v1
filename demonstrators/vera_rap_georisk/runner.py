"""Deterministic orchestration over the authoritative VERA-RAP primitives."""

from __future__ import annotations

from datetime import datetime

from app.research.vera_rap import (
    AbstractionEdge,
    AbstractionGraph,
    AbstractionLevel,
    AbstractionNode,
    AbstractionRule,
    ClaimEvaluationResult,
    ClaimNode,
    ClaimObject,
    CognitiveState,
    CognitiveTraceBuilder,
    CognitiveTransition,
    ConstraintNode,
    ConstraintStatus,
    ContradictionObject,
    ContradictionStatus,
    ContradictionType,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    GraphEdge,
    PlanningTarget,
    PlanningTargetType,
    RequirementType,
    ResolutionRequirement,
    ResolutionRequirementType,
    TransitionRequirement,
    VerificationStatus,
    evaluate_transition,
    plan_evidence,
    verify_abstraction,
)
from .evidence_adapter import GeoRiskEvidenceAdapter
from .models import (
    DemonstratorAsset,
    DemonstratorOutcome,
    DemonstratorQuestion,
    DemonstratorRunResult,
    fingerprint,
)


def run_georisk_demonstrator(
    asset: DemonstratorAsset,
    question: DemonstratorQuestion,
    evidence_inputs: list[dict],
    *,
    evaluation_time: datetime,
) -> DemonstratorRunResult:
    if (
        asset.asset_id != question.asset_id
        or evaluation_time != question.evaluation_time
    ):
        raise ValueError(
            "asset and deterministic evaluation time must match the question"
        )
    evidence = GeoRiskEvidenceAdapter().convert_all(
        evidence_inputs, evaluation_time=evaluation_time
    )
    applicable = tuple(
        e
        for e in evidence
        if e.spatial_scope and e.spatial_scope.get("asset_id") == asset.asset_id
    )
    by_type = {e.evidence_type: e for e in applicable}
    missing = [
        x.value for x in question.required_evidence_types if x.value not in by_type
    ]
    constraint_ok = all(
        question.constraints.get(k) == v
        for k, v in {
            "scenario": question.materiality_threshold.get("scenario"),
            "return_period_years": question.materiality_threshold.get(
                "return_period_years"
            ),
            "time_horizon": question.materiality_threshold.get("time_horizon"),
        }.items()
        if v is not None
    )
    flood = [e for e in applicable if e.evidence_type == "FLOOD_DEPTH"]
    for e in flood:
        m = e.measurement
        if m.get("scenario") != question.materiality_threshold.get("scenario"):
            missing.append("COMPATIBLE_CLIMATE_SCENARIO")
        if m.get("return_period_years") != question.materiality_threshold.get(
            "return_period_years"
        ):
            missing.append("COMPATIBLE_RETURN_PERIOD")
        if m.get("time_horizon") != question.materiality_threshold.get("time_horizon"):
            missing.append("COMPATIBLE_TIME_HORIZON")
        if e.unit != question.materiality_threshold.get("unit"):
            missing.append("EXPLICIT_UNIT_NORMALIZATION")
    contradictions = ()
    if len(flood) > 1 and len({e.measurement.get("value") for e in flood}) > 1:
        req = ResolutionRequirement(
            "resolve-flood-conflict",
            ResolutionRequirementType.INDEPENDENT_EVIDENCE_REQUIRED,
            tuple(e.evidence_id for e in flood),
            {},
            True,
            "independent resolution evidence; never majority or recency",
        )
        contradictions = (
            ContradictionObject(
                "flood-source-conflict",
                ContradictionType.DIRECT_VALUE_CONFLICT,
                ContradictionStatus.UNRESOLVED,
                evidence_ids=tuple(e.evidence_id for e in flood),
                detected_at=evaluation_time,
                conflict_dimensions=("flood_depth",),
                resolution_requirements=(req,),
            ),
        )
    excessive = [
        e.evidence_id
        for e in flood
        if e.uncertainty
        and e.uncertainty.upper is not None
        and e.uncertainty.lower is not None
        and (e.uncertainty.upper - e.uncertainty.lower) / 2
        > question.materiality_threshold.get("max_uncertainty", 1.0)
    ]
    rejected = [
        e.evidence_id
        for e in applicable
        if e.verification_status is VerificationStatus.REJECTED
    ]
    stale = [
        e.evidence_id
        for e in applicable
        if e.verification_status is VerificationStatus.STALE
    ]
    failed = sorted(
        set(
            missing
            + rejected
            + stale
            + excessive
            + ([] if constraint_ok else ["MANDATORY_CONSTRAINT"])
            + (["UNRESOLVED_CONTRADICTION"] if contradictions else [])
        )
    )
    declared = ClaimObject(
        "material-flood-exposure",
        "MATERIAL_FLOOD_EXPOSURE",
        {"asset_id": asset.asset_id},
        True,
        None,
        EpistemicState.INFERRED,
        supporting_evidence_ids=tuple(e.evidence_id for e in applicable),
        created_at=evaluation_time,
        derivation_method="RAP-012 abstraction path",
        scope={"asset_id": asset.asset_id},
    )
    state = (
        EpistemicState.SUPPORTED if not failed else EpistemicState.INSUFFICIENT_EVIDENCE
    )
    ev = ClaimEvaluationResult(
        state,
        tuple(
            e.evidence_id
            for e in applicable
            if e.verification_status is VerificationStatus.VERIFIED
        ),
        (),
        (),
        tuple(failed),
        (),
        "rap-012",
        "1",
        evaluation_time,
    )
    claim = declared.with_evaluation(ev)
    constraint = ConstraintNode(
        "scope-constraints",
        "FLOOD_SCOPE",
        "scenario, horizon and return period compatibility",
        True,
        ConstraintStatus.SATISFIED if constraint_ok else ConstraintStatus.VIOLATED,
    )
    nodes = tuple(EvidenceNode(e) for e in evidence) + (ClaimNode(claim), constraint)
    edges = tuple(
        GraphEdge(e.evidence_id, claim.claim_id, EdgeType.SUPPORTS) for e in applicable
    ) + (
        GraphEdge(claim.claim_id, "scope-constraints", EdgeType.REQUIRES),
    )
    graph = EvidenceGraph(nodes, edges)
    requirements = tuple(
        TransitionRequirement(
            f"verify-{e.evidence_id}",
            RequirementType.EVIDENCE_VERIFIED,
            e.evidence_id,
            {},
            True,
            "verified admissible evidence",
        )
        for e in applicable
    ) + (
        TransitionRequirement(
            "constraints",
            RequirementType.CONSTRAINT_SATISFIED,
            "scope-constraints",
            {},
            True,
            "mandatory scope compatibility",
        ),
    )
    transition = CognitiveTransition(
        "flood-materiality-transition",
        "FLOOD_MATERIALITY",
        CognitiveState(
            "observations",
            "OBSERVATION",
            0,
            claim_ids=(claim.claim_id,),
            evidence_ids=tuple(e.evidence_id for e in applicable),
        ),
        CognitiveState("materiality", "MATERIALITY", 6, claim_ids=(claim.claim_id,)),
        requirements,
        "rap-012",
        "1",
    )
    transition_eval = evaluate_transition(transition, graph, at=evaluation_time)
    obs = AbstractionNode(
        "flood-observations",
        AbstractionLevel.OBSERVATION,
        "verified flood observations",
        claim_ids=(claim.claim_id,),
        evidence_ids=tuple(e.evidence_id for e in applicable),
        created_at=evaluation_time,
    )
    mat = AbstractionNode(
        "flood-materiality",
        AbstractionLevel.MATERIALITY,
        "material exposure",
        claim_ids=(claim.claim_id,),
        source_abstraction_ids=(obs.abstraction_id,),
        created_at=evaluation_time,
    )
    rule = AbstractionRule(
        "flood-materiality-rule",
        (AbstractionLevel.OBSERVATION,),
        AbstractionLevel.MATERIALITY,
        ("MATERIAL_FLOOD_EXPOSURE",),
        transition.transition_type,
        (),
        True,
        "1",
        "explicit RAP-012 level skip via physical state and exposure checks",
    )
    ag = AbstractionGraph(
        (obs, mat),
        (
            AbstractionEdge(
                obs.abstraction_id, mat.abstraction_id, transition.transition_id, True
            ),
        ),
        (rule,),
        (transition,),
    )
    ov = verify_abstraction(
        obs,
        ag,
        graph,
        {},
        {},
        contradictions,
        {},
        at=evaluation_time,
        verifier_id="rap-012",
        verifier_version="1",
    )
    ag = ag.with_node(obs.with_verification(ov))
    mv = verify_abstraction(
        mat,
        ag,
        graph,
        {transition.transition_id: transition_eval},
        {},
        contradictions,
        {},
        at=evaluation_time,
        verifier_id="rap-012",
        verifier_version="1",
    )
    plans = ()
    if failed:
        target = PlanningTarget(
            "flood-materiality-transition",
            PlanningTargetType.TRANSITION_PERMISSION,
            transition_id=transition.transition_id,
        )
        plans = (
            plan_evidence(
                target,
                evidence_graph=graph,
                at=evaluation_time,
                transition_evaluations=(transition_eval,),
                contradiction_artifacts=contradictions,
                planner_id="rap-012",
                planner_version="1",
            ),
        )
    outcome = (
        DemonstratorOutcome.SUPPORTED
        if not failed
        else (
            DemonstratorOutcome.REPLAN_REQUIRED
            if plans and not any(x == "MANDATORY_CONSTRAINT" for x in failed)
            else DemonstratorOutcome.BLOCKED
        )
    )
    builder = CognitiveTraceBuilder(
        (question.question_id,),
        started_at=evaluation_time,
        actor_id="rap-012",
        actor_version="1",
    )
    for e in evidence:
        builder.register_evidence(e, at=evaluation_time)
        builder.evaluate_staleness(e, at=evaluation_time)
    builder.declare_claim(declared, at=evaluation_time)
    builder.evaluate_claim(claim, graph=graph)
    builder.validate_graph(graph, at=evaluation_time)
    builder.evaluate_transition(transition_eval, graph)
    for c in contradictions:
        builder.detect_contradiction(c)
    builder.propose_abstraction(obs, abstraction_graph=ag)
    builder.verify_abstraction(ov, node=obs, evidence_graph=graph)
    builder.propose_abstraction(mat, abstraction_graph=ag)
    builder.verify_abstraction(mv, node=mat, evidence_graph=graph)
    for p in plans:
        builder.record_plan(p)
    builder.checkpoint(
        at=evaluation_time,
        evidence_graph=graph,
        abstraction_graph=ag,
        plan=plans[0] if plans else None,
        admissible_state={"outcome": outcome.value},
    )
    trace = builder.build(ended_at=evaluation_time)
    identity = {
        "asset": asset.asset_id,
        "question": question.question_id,
        "evidence": [e.fingerprint for e in evidence],
        "outcome": outcome.value,
        "at": evaluation_time.isoformat(),
    }
    fp = fingerprint(identity)
    return DemonstratorRunResult(
        fp,
        asset,
        question,
        evidence,
        (claim,),
        graph.fingerprint,
        (transition_eval,),
        contradictions,
        (),
        (ov, mv),
        plans,
        trace,
        outcome,
        evaluation_time,
        tuple(failed),
        fp,
    )
