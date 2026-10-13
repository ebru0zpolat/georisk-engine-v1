"""Case evaluation, benchmark runner, profiles, and the VERA-RAP adapter (RAP-010).

Scoring never uses randomness, wall-clock time, model judgement, or network
access. The VERA-RAP adapter only calls RAP-001..RAP-009 functions.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.research.vera_rap import (
    ArtifactRegistry,
    BlockerType,
    CognitiveTraceBuilder,
    ContradictionStatus,
    EvidenceGraph,
    EvidenceNode,
    PlanExecutionResult,
    PlanningTarget,
    PlanningTargetType,
    PlanStatus,
    PropagationRule,
    PropagationRuleType,
    TransitionStatus,
    UncertaintyComponent,
    UncertaintyDirection,
    UncertaintyProfile,
    UncertaintyType,
    derive_claim_uncertainty,
    evaluate_transition,
    evaluate_uncertainty_gate,
    find_contradictions,
    identify_blockers,
    plan_evidence,
    replan,
    replay_trace,
    validate_trace,
)
from app.research.vera_rap.evidence import _iso, _plain_json, _required_text, _timestamp
from app.research.vera_rap.evidence_graph import (
    ClaimNode,
    ConstraintNode,
    ConstraintStatus,
)
from app.research.vera_rap.trace import ReplayResult, TraceValidationResult

from .metrics import (
    ABSTENTION_ACCURACY,
    CONSTRAINT_VIOLATION_RATE,
    CONTRADICTION_HANDLING_ACCURACY,
    EPISTEMIC_ADMISSIBILITY,
    METRIC_NAMES,
    REPLANNING_EFFICIENCY,
    TRACE_REPRODUCIBILITY,
    UNCERTAINTY_DISCIPLINE,
    UNSUPPORTED_CLAIM_RATE,
    ScoredRow,
    admissible_action,
    compute_metrics,
)
from .models import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    SCHEMA_VERSION,
    BenchmarkCase,
    BenchmarkRunResult,
    BenchmarkSystem,
    CaseEvaluation,
    EvidenceBoundBenchManifest,
    MetricResult,
    ReferenceOutcome,
    SystemCaseResult,
    SystemOutcome,
    _canonical,
)
from .scenarios import BenchmarkCasePair, MaterializedCase, materialize_case

# --------------------------------------------------------------------------- #
# Case evaluation and benchmark runs
# --------------------------------------------------------------------------- #


def _trace_checks(
    result: SystemCaseResult,
) -> tuple[TraceValidationResult | None, ReplayResult | None]:
    if result.trace is None:
        return None, None
    references = result.registry_references or result.trace.artifacts
    registry = ArtifactRegistry()
    for reference in references:
        registry.register(reference)
    return validate_trace(result.trace, registry), replay_trace(result.trace, registry)


def evaluate_case(
    benchmark_case: BenchmarkCase,
    system_result: SystemCaseResult,
    reference_outcome: ReferenceOutcome,
    *,
    repeat_result: SystemCaseResult | None = None,
) -> CaseEvaluation:
    """Score one case; violations are explicit reason codes, never prose."""
    if (
        benchmark_case.case_id != system_result.case_id
        or benchmark_case.case_id != reference_outcome.case_id
    ):
        raise ValueError("case, result and reference must describe the same case")
    validation, replay = _trace_checks(system_result)
    repeat_fingerprint = (
        None
        if repeat_result is None or repeat_result.trace is None
        else repeat_result.trace.fingerprint
    )
    row = ScoredRow(
        benchmark_case,
        system_result,
        reference_outcome,
        validation,
        replay,
        repeat_fingerprint,
    )
    metrics = compute_metrics((row,))
    by_name = {x.metric_name: x for x in metrics}
    violations: set[str] = set()
    notes: set[str] = set()
    if not admissible_action(system_result, reference_outcome):
        violations.add("INADMISSIBLE_ACTION")
    if by_name[UNSUPPORTED_CLAIM_RATE].numerator:
        violations.add("UNSUPPORTED_CLAIM")
    if by_name[CONSTRAINT_VIOLATION_RATE].numerator:
        violations.add("CONSTRAINT_VIOLATION")
    abstention = by_name[ABSTENTION_ACCURACY].details
    if abstention["false_abstention_case_ids"]:
        violations.add("FALSE_ABSTENTION")
    if abstention["missed_abstention_case_ids"]:
        violations.add("MISSED_ABSTENTION")
    for name, code in (
        (CONTRADICTION_HANDLING_ACCURACY, "CONTRADICTION_MISHANDLED"),
        (UNCERTAINTY_DISCIPLINE, "UNCERTAINTY_INDISCIPLINE"),
        (REPLANNING_EFFICIENCY, "REPLANNING_INEFFICIENT"),
    ):
        if by_name[name].passed is False:
            violations.add(code)
    if system_result.trace is None:
        notes.add("NO_TRACE")
    elif by_name[TRACE_REPRODUCIBILITY].passed is False:
        violations.add("TRACE_NOT_REPRODUCIBLE")
    required = set(reference_outcome.required_blocker_types)
    if required and not system_result.blocker_types:
        notes.add("BLOCKERS_NOT_REPORTED")
    elif required and not required <= set(system_result.blocker_types):
        violations.add("REQUIRED_BLOCKER_MISSING")
    if (
        repeat_result is not None
        and repeat_result.fingerprint != system_result.fingerprint
    ):
        violations.add("NONDETERMINISTIC_RESULT")
    return CaseEvaluation(
        benchmark_case.case_id,
        metrics,
        tuple(sorted(violations)),
        not violations,
        validation,
        tuple(sorted(notes)),
        admissible_action(system_result, reference_outcome),
        system_result.claimed_outcome,
        reference_outcome.expected_permission,
    )


def build_manifest(
    cases: Sequence[BenchmarkCase],
    *,
    created_at: datetime,
    metadata: Mapping[str, Any] | None = None,
) -> EvidenceBoundBenchManifest:
    return EvidenceBoundBenchManifest(
        BENCHMARK_NAME,
        BENCHMARK_VERSION,
        tuple(x.case_id for x in cases),
        METRIC_NAMES,
        SCHEMA_VERSION,
        created_at,
        {
            "case_fingerprints": {x.case_id: x.fingerprint for x in cases},
            **dict(metadata or {}),
        },
    )


def run_benchmark(
    cases: Sequence[BenchmarkCase | BenchmarkCasePair],
    system: BenchmarkSystem,
    reference_outcomes: Sequence[ReferenceOutcome] = (),
    *,
    started_at: datetime,
    completed_at: datetime | None = None,
    repeat_for_determinism: bool = True,
    metadata: Mapping[str, Any] | None = None,
) -> BenchmarkRunResult:
    """Run every case in case-ID order; deterministic when the system is."""
    _timestamp(started_at, "started_at")
    case_map: dict[str, BenchmarkCase] = {}
    references: dict[str, ReferenceOutcome] = {x.case_id: x for x in reference_outcomes}
    for item in cases:
        case = item.case if isinstance(item, BenchmarkCasePair) else item
        if isinstance(item, BenchmarkCasePair):
            references[case.case_id] = item.reference
        if case.case_id in case_map:
            raise ValueError(f"duplicate case ID: {case.case_id}")
        case_map[case.case_id] = case
    missing = sorted(set(case_map) - set(references))
    if missing:
        raise ValueError(f"reference outcomes missing for: {', '.join(missing)}")
    ordered = [case_map[key] for key in sorted(case_map)]
    rows: list[ScoredRow] = []
    evaluations: list[CaseEvaluation] = []
    for case in ordered:
        result = system.evaluate_case(case)
        repeat = system.evaluate_case(case) if repeat_for_determinism else None
        evaluation = evaluate_case(
            case, result, references[case.case_id], repeat_result=repeat
        )
        evaluations.append(evaluation)
        validation, replay = _trace_checks(result)
        rows.append(
            ScoredRow(
                case,
                result,
                references[case.case_id],
                validation,
                replay,
                (
                    None
                    if repeat is None or repeat.trace is None
                    else repeat.trace.fingerprint
                ),
            )
        )
    manifest = build_manifest(ordered, created_at=started_at)
    return BenchmarkRunResult(
        BENCHMARK_VERSION,
        system.system_id,
        system.system_version,
        tuple(evaluations),
        compute_metrics(rows),
        started_at,
        completed_at or started_at,
        manifest.fingerprint,
        {"repeat_for_determinism": repeat_for_determinism, **dict(metadata or {})},
    )


# --------------------------------------------------------------------------- #
# Profiles: explicit minimum acceptable behaviour
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ProfileRequirement:
    metric_name: str
    operator: str
    threshold: float
    detail_key: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.metric_name, "metric_name")
        if self.operator not in {"==", ">=", "<="}:
            raise ValueError("operator must be ==, >= or <=")

    def observe(self, metric: MetricResult) -> float | None:
        value = (
            metric.value
            if self.detail_key is None
            else metric.details.get(self.detail_key)
        )
        return (
            value
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None
        )

    def satisfied(self, metric: MetricResult) -> bool:
        observed = self.observe(metric)
        if observed is None:
            return False
        if self.operator == "==":
            return observed == self.threshold
        if self.operator == ">=":
            return observed >= self.threshold
        return observed <= self.threshold

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "operator": self.operator,
            "threshold": self.threshold,
            "detail_key": self.detail_key,
        }


@dataclass(frozen=True, slots=True)
class ProfileResult:
    profile_name: str
    passed: bool
    satisfied: tuple[str, ...]
    unsatisfied: tuple[str, ...]
    observations: Mapping[str, Any]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "passed": self.passed,
            "satisfied": list(self.satisfied),
            "unsatisfied": list(self.unsatisfied),
            "observations": _plain_json(self.observations),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    name: str
    requirements: tuple[ProfileRequirement, ...]

    def check(self, run: BenchmarkRunResult) -> ProfileResult:
        satisfied: list[str] = []
        unsatisfied: list[str] = []
        observations: dict[str, Any] = {}
        for requirement in self.requirements:
            label = f"{requirement.metric_name}{'.' + requirement.detail_key if requirement.detail_key else ''} {requirement.operator} {requirement.threshold}"
            try:
                metric = run.metric(requirement.metric_name)
            except KeyError:
                unsatisfied.append(label)
                observations[label] = None
                continue
            observations[label] = requirement.observe(metric)
            (satisfied if requirement.satisfied(metric) else unsatisfied).append(label)
        return ProfileResult(
            self.name,
            not unsatisfied,
            tuple(satisfied),
            tuple(unsatisfied),
            observations,
        )


MINIMUM_PROFILE = BenchmarkProfile(
    "evidenceboundbench-minimum",
    (
        ProfileRequirement(UNSUPPORTED_CLAIM_RATE, "==", 0.0),
        ProfileRequirement(CONSTRAINT_VIOLATION_RATE, "==", 0.0),
        ProfileRequirement(TRACE_REPRODUCIBILITY, "==", 1.0),
        ProfileRequirement(ABSTENTION_ACCURACY, ">=", 1.0, "recall"),
        ProfileRequirement(ABSTENTION_ACCURACY, ">=", 1.0, "precision"),
        ProfileRequirement(EPISTEMIC_ADMISSIBILITY, "==", 1.0),
    ),
)


# --------------------------------------------------------------------------- #
# VERA-RAP adapter: orchestrates RAP-001..RAP-009 without re-implementing them
# --------------------------------------------------------------------------- #


def _declaration_order(graph: EvidenceGraph) -> list[str]:
    claims = {k: v.claim for k, v in graph.nodes.items() if isinstance(v, ClaimNode)}
    ordered: list[str] = []
    remaining = dict(sorted(claims.items()))
    while remaining:
        ready = [
            k
            for k, c in remaining.items()
            if all(p in ordered or p not in claims for p in c.parent_claim_ids)
        ]
        if not ready:
            raise ValueError("claim parents form a cycle")
        ordered.extend(ready)
        for key in ready:
            del remaining[key]
    return ordered


def _profile_from_claim(
    claim_id: str, graph: EvidenceGraph, at: datetime
) -> UncertaintyProfile | None:
    node = graph.nodes.get(claim_id)
    if not isinstance(node, ClaimNode):
        return None
    declared = node.claim.uncertainty
    if declared is None:
        component = UncertaintyComponent(
            f"{claim_id}-missing",
            UncertaintyType.MISSING_INFORMATION,
            UncertaintyDirection.EPISTEMIC,
            claim_id,
            source_ids=(claim_id,),
            method="missing-declared-uncertainty",
        )
        unresolved: tuple[str, ...] = (component.component_id,)
    else:
        component = UncertaintyComponent(
            f"{claim_id}-declared",
            UncertaintyType.MEASUREMENT,
            UncertaintyDirection.UNKNOWN,
            claim_id,
            declared.lower,
            declared.upper,
            declared.confidence,
            source_ids=(claim_id,),
            method=declared.kind,
        )
        unresolved = ()
    return UncertaintyProfile(
        f"profile-{claim_id}",
        claim_id,
        (component,),
        "DECLARED",
        component.lower,
        component.upper,
        component.confidence,
        unresolved,
        (),
        (claim_id,),
        at,
    )


def _default_rules(claim_id: str, graph: EvidenceGraph) -> tuple[PropagationRule, ...]:
    """Explicit pass-through/envelope rules so uncertainty is propagated, never guessed."""
    node = graph.nodes.get(claim_id)
    if not isinstance(node, ClaimNode):
        return ()
    subjects = tuple(
        sorted((*node.claim.supporting_evidence_ids, *node.claim.parent_claim_ids))
    )
    if not subjects:
        return ()
    kind = (
        PropagationRuleType.PASS_THROUGH
        if len(subjects) == 1
        else PropagationRuleType.INTERVAL_ENVELOPE
    )
    return (
        PropagationRule(
            f"benchmark-{kind.value.lower()}-{claim_id}",
            kind,
            "1",
            subjects,
            claim_id,
            {},
            (),
            "benchmark default propagation without reduction",
        ),
    )


class VeraRapBenchmarkSystem(BenchmarkSystem):
    """System under test that reasons only through VERA-RAP research primitives."""

    system_id = "vera-rap"
    system_version = "rap-001..009"

    def __init__(
        self, *, planner_id: str = "vera-rap-planner", planner_version: str = "1"
    ) -> None:
        self.planner_id = planner_id
        self.planner_version = planner_version

    def evaluate_case(self, case: BenchmarkCase) -> SystemCaseResult:
        material = materialize_case(case)
        target_transition = material.target.get("transition_id")
        material_claim = material.target.get("material_claim_id")
        if not isinstance(target_transition, str) or not isinstance(
            material_claim, str
        ):
            raise ValueError(
                "VERA-RAP adapter needs transition_id and material_claim_id targets"
            )
        starts = [
            x.evidence.retrieved_at
            for x in material.graph.nodes.values()
            if isinstance(x, EvidenceNode)
        ]
        starts += [
            x.claim.created_at
            for x in material.graph.nodes.values()
            if isinstance(x, ClaimNode)
        ]
        builder = CognitiveTraceBuilder(
            (target_transition, material_claim),
            started_at=min([*starts, material.at]),
            actor_id=self.system_id,
            actor_version=self.system_version,
        )
        state = self._round(
            material, material.graph, builder, material.at, previous=None
        )
        rounds = [state]
        if state["outcome"] is SystemOutcome.REPLANNED and material.follow_up_evidence:
            plan = state["plan"]
            evidence_actions = tuple(
                x.action_id
                for x in plan.mandatory_actions
                if x.action_type.value
                in {
                    "RETRIEVE_EVIDENCE",
                    "REFRESH_STALE_EVIDENCE",
                    "REQUEST_INDEPENDENT_EVIDENCE",
                }
            )
            later = max(x.retrieved_at for x in material.follow_up_evidence)
            later = max(later, material.at)
            execution = PlanExecutionResult(
                plan.plan_id,
                evidence_actions,
                (),
                tuple(x.evidence_id for x in material.follow_up_evidence),
                (),
                (),
                (),
                (),
                (),
                later,
                self.system_id,
                self.system_version,
            )
            execution_event = builder.record_execution(execution, plan)
            graph = material.graph
            for evidence in material.follow_up_evidence:
                graph = graph.with_node(EvidenceNode(evidence))
            state = self._round(
                material,
                graph,
                builder,
                later,
                previous=(plan, execution, execution_event.event_id),
            )
            rounds.append(state)
        final = rounds[-1]
        outcome: SystemOutcome = final["outcome"]
        graph = final["graph"]
        claims = (material_claim,) if outcome is SystemOutcome.CONCLUDED else ()
        lineage = (
            graph.explain(material_claim)
            if isinstance(graph.nodes.get(material_claim), ClaimNode)
            else None
        )
        provenance = {
            node.node_id: {
                "source_id": node.evidence.source_id,
                "content_hash": node.evidence.content_hash,
                "retrieval_mechanism": node.evidence.provenance.retrieval_mechanism,
                "upstream_evidence_ids": list(
                    node.evidence.provenance.upstream_evidence_ids
                ),
                "transformation_ids": list(node.evidence.provenance.transformation_ids),
                "verification_status": node.evidence.verification_status.value,
                "evidence_fingerprint": node.evidence.fingerprint,
                "corrupted": node.node_id in material.corrupted_evidence_ids,
            }
            for node in graph.nodes.values()
            if isinstance(node, EvidenceNode)
        }
        plans = []
        for index, item in enumerate(rounds):
            plan = item["plan"]
            if plan is None:
                continue
            blocking_roots = {
                b.blocker_id for b in plan.blockers if b.blocking and not b.caused_by
            }
            mandatory = plan.mandatory_actions
            plans.append(
                {
                    "plan_id": plan.plan_id,
                    "status": plan.status.value,
                    "terminal": plan.terminal,
                    "abstain_reason": plan.abstain_reason,
                    "action_types": [x.action_type.value for x in plan.actions],
                    "root_cause_targeted": bool(mandatory)
                    and bool(set(mandatory[0].addresses_blocker_ids) & blocking_roots),
                    "unnecessary_action_count": sum(
                        1
                        for x in mandatory
                        if not set(x.addresses_blocker_ids)
                        & {b.blocker_id for b in plan.blockers if b.blocking}
                    ),
                    "action_fingerprint": hashlib.sha256(
                        _canonical(
                            {"actions": [x.action_id for x in plan.actions]}
                        ).encode()
                    ).hexdigest(),
                    "progress": index > 0
                    and item["outcome"] is SystemOutcome.CONCLUDED
                    or plan.status is PlanStatus.COMPLETED,
                }
            )
        contradictions = final["contradictions"]
        return SystemCaseResult(
            case.case_id,
            self.system_id,
            self.system_version,
            outcome,
            claims,
            {k: v.status.value for k, v in final["evaluations"].items()},
            {},
            outcome is SystemOutcome.ABSTAINED,
            tuple(x["plan_id"] for x in plans),
            tuple(sorted({b.blocker_id for item in rounds for b in item["blockers"]})),
            builder.build(ended_at=final["at"]),
            {
                "rounds": len(rounds),
                "initial_outcome": rounds[0]["outcome"].value,
                "evaluation_time": _iso(final["at"]),
                "gate_results": final["gate_results"],
                "corrupted_evidence_ids": list(material.corrupted_evidence_ids),
            },
            (
                {material_claim: sorted(lineage.upstream_evidence)}
                if claims and lineage
                else {}
            ),
            provenance,
            {
                "detected": sorted(x.contradiction_id for x in contradictions),
                "branches_preserved": True,
                "resolution_basis": (
                    "REQUIREMENTS"
                    if any(x.resolution_history for x in contradictions)
                    else None
                ),
                "marked_resolved": sorted(
                    x.contradiction_id
                    for x in contradictions
                    if x.status is ContradictionStatus.RESOLVED
                ),
                "resolution_evidence_ids": sorted(
                    {
                        e
                        for x in contradictions
                        for r in x.resolution_history
                        for e in r.supporting_evidence_ids
                    }
                ),
                "statuses": {
                    x.contradiction_id: x.status.value for x in contradictions
                },
            },
            {
                "gate_results": final["gate_results"],
                "missing_preserved": final["missing_preserved"],
                "confidence_increases": [],
                "widened": False,
                "confidence_override": False,
                "effective_confidence": final["effective_confidence"],
            },
            {
                "violated_constraint_ids": sorted(
                    n.node_id
                    for n in graph.nodes.values()
                    if isinstance(n, ConstraintNode)
                    and n.status is ConstraintStatus.VIOLATED
                ),
                "proceeded": outcome is SystemOutcome.CONCLUDED,
            },
            tuple(plans),
            tuple(
                sorted(
                    {b.blocker_type.value for item in rounds for b in item["blockers"]}
                )
            ),
            builder.registry.references(),
            rounds[0]["outcome"],
        )

    def _round(
        self,
        material: MaterializedCase,
        graph: EvidenceGraph,
        builder: CognitiveTraceBuilder,
        at: datetime,
        *,
        previous: tuple[Any, Any, str] | None,
    ) -> dict[str, Any]:
        target_transition = material.target["transition_id"]
        material_claim = material.target["material_claim_id"]
        for node_id in sorted(graph.nodes):
            node = graph.nodes[node_id]
            if isinstance(node, EvidenceNode) and node_id not in builder.latest:
                builder.register_evidence(node.evidence)
        for claim_id in _declaration_order(graph):
            if claim_id not in builder.latest:
                builder.declare_claim(graph.nodes[claim_id].claim)  # type: ignore[union-attr]
        for node_id in sorted(graph.nodes):
            node = graph.nodes[node_id]
            if isinstance(node, EvidenceNode):
                builder.evaluate_staleness(node.evidence, at=at)
        builder.validate_graph(graph, at=at)
        found = {x.contradiction_id: x for x in find_contradictions(graph, at=at)}
        for item in material.contradictions:
            found[item.contradiction_id] = item
        contradictions = tuple(found[k] for k in sorted(found))
        for item in contradictions:
            if item.contradiction_id not in builder.latest:
                builder.detect_contradiction(item, at=at)
                if item.resolution_history:
                    builder.evaluate_contradiction(item)
        if isinstance(graph.nodes.get(material_claim), ClaimNode):
            builder.evaluate_support(
                graph.is_support_complete(material_claim, at=at), graph
            )
        evaluations = {}
        for transition in material.transitions:
            evaluation = evaluate_transition(transition, graph, at=at)
            evaluations[transition.transition_id] = evaluation
            builder.evaluate_transition(evaluation, graph)
        gate_results: dict[str, bool] = {}
        profile = None
        missing_preserved = True
        rules = material.propagation_rules or _default_rules(material_claim, graph)
        if rules and isinstance(graph.nodes.get(material_claim), ClaimNode):
            try:
                propagation = derive_claim_uncertainty(
                    material_claim, graph, rules, at=at
                )
            except ValueError:
                propagation = None
            if propagation is not None:
                builder.propagate_uncertainty(propagation)
                profile = propagation.output_profile
        if profile is None:
            profile = _profile_from_claim(material_claim, graph, at)
        if profile is not None:
            missing_preserved = (
                bool(profile.unresolved_components)
                or profile.effective_confidence is not None
            )
            for threshold in material.thresholds:
                gate = evaluate_uncertainty_gate(profile, threshold)
                gate_results[threshold.threshold_id] = gate.passed
                builder.evaluate_gate(gate, profile, at=at)
        target = PlanningTarget(
            f"{material.case_id}:{target_transition}",
            PlanningTargetType.TRANSITION_PERMISSION,
            transition_id=target_transition,
        )
        artifacts = dict(
            evidence_graph=graph,
            transition_evaluations=tuple(evaluations.values()),
            contradiction_artifacts=contradictions,
            at=at,
        )
        blockers = identify_blockers(target=target, **artifacts)
        blockers_event = builder.identify_blockers(target, blockers, at=at)
        if previous is None:
            plan = plan_evidence(
                target,
                planner_id=self.planner_id,
                planner_version=self.planner_version,
                **artifacts,
            )
            builder.record_plan(plan, inputs=(blockers_event.event_id,))
        else:
            plan = replan(previous[0], previous[1], **artifacts)
            builder.record_plan(plan, inputs=(blockers_event.event_id, previous[2]))
        evaluation = evaluations.get(target_transition)
        gates_pass = all(gate_results.values())
        active_contradiction = any(
            b.blocker_type
            in {
                BlockerType.UNRESOLVED_CONTRADICTION,
                BlockerType.CONTRADICTION_RESOLUTION_PENDING,
            }
            and b.blocking
            for b in blockers
        )
        if (
            evaluation is not None
            and evaluation.status is TransitionStatus.ALLOWED
            and gates_pass
            and not active_contradiction
        ):
            outcome = SystemOutcome.CONCLUDED
        elif plan.status is PlanStatus.ABSTAINED:
            outcome = SystemOutcome.ABSTAINED
        elif active_contradiction:
            outcome = SystemOutcome.CONTRADICTION_PENDING
        elif plan.mandatory_actions:
            outcome = SystemOutcome.REPLANNED
        else:
            outcome = SystemOutcome.BLOCKED
        return {
            "outcome": outcome,
            "graph": graph,
            "evaluations": evaluations,
            "contradictions": contradictions,
            "gate_results": gate_results,
            "plan": plan,
            "blockers": blockers,
            "at": at,
            "missing_preserved": missing_preserved,
            "effective_confidence": (
                None if profile is None else profile.effective_confidence
            ),
        }
