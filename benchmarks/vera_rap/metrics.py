"""EvidenceBoundBench metric definitions (RAP-010).

Every metric reports numerator, denominator, and the cases it drew on. No
metric uses randomness, wall-clock time, model judgement, or self-confidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.research.vera_rap.trace import ReplayResult, TraceValidationResult

from .models import (
    ADMISSIBLE_OUTCOMES,
    WITHHOLDING_OUTCOMES,
    BenchmarkCase,
    ExpectedPermission,
    MetricResult,
    ReferenceOutcome,
    SystemCaseResult,
    SystemOutcome,
)

UNSUPPORTED_CLAIM_RATE = "unsupported_claim_rate"
EVIDENCE_COVERAGE = "evidence_coverage"
PROVENANCE_COMPLETENESS = "provenance_completeness"
REASONING_PROVENANCE_COMPLETENESS = "reasoning_provenance_completeness"
CONSTRAINT_VIOLATION_RATE = "constraint_violation_rate"
ABSTENTION_ACCURACY = "abstention_accuracy"
CONTRADICTION_HANDLING_ACCURACY = "contradiction_handling_accuracy"
UNCERTAINTY_DISCIPLINE = "uncertainty_discipline_score"
REPLANNING_EFFICIENCY = "replanning_efficiency"
TRACE_REPRODUCIBILITY = "cognitive_trace_reproducibility"
EPISTEMIC_ADMISSIBILITY = "epistemic_admissibility"

METRIC_NAMES: tuple[str, ...] = (
    UNSUPPORTED_CLAIM_RATE,
    EVIDENCE_COVERAGE,
    PROVENANCE_COMPLETENESS,
    REASONING_PROVENANCE_COMPLETENESS,
    CONSTRAINT_VIOLATION_RATE,
    ABSTENTION_ACCURACY,
    CONTRADICTION_HANDLING_ACCURACY,
    UNCERTAINTY_DISCIPLINE,
    REPLANNING_EFFICIENCY,
    TRACE_REPRODUCIBILITY,
    EPISTEMIC_ADMISSIBILITY,
)
LOWER_IS_BETTER = frozenset({UNSUPPORTED_CLAIM_RATE, CONSTRAINT_VIOLATION_RATE})
PROVENANCE_COMPONENTS = (
    "source_id",
    "content_hash",
    "retrieval_chain",
    "transformations",
    "support_relationship",
)
FORBIDDEN_RESOLUTION_BASES = frozenset({"MAJORITY", "RECENCY", "CONFIDENCE"})


@dataclass(frozen=True, slots=True)
class ScoredRow:
    """One case's inputs to scoring; trace checks are computed once upstream."""

    case: BenchmarkCase
    result: SystemCaseResult
    reference: ReferenceOutcome
    validation: TraceValidationResult | None
    replay: ReplayResult | None
    repeat_trace_fingerprint: str | None


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _result(
    name: str,
    numerator: int,
    denominator: int,
    details: Mapping[str, Any],
    case_ids: Sequence[str],
    *,
    passed: bool | None,
) -> MetricResult:
    return MetricResult(
        name,
        _ratio(numerator, denominator),
        numerator,
        denominator,
        passed,
        dict(details),
        tuple(case_ids),
    )


def admissible_action(result: SystemCaseResult, reference: ReferenceOutcome) -> bool:
    return result.decision_outcome in ADMISSIBLE_OUTCOMES[reference.expected_permission]


def epistemic_admissibility(rows: Sequence[ScoredRow]) -> MetricResult:
    admissible = [
        x.case.case_id for x in rows if admissible_action(x.result, x.reference)
    ]
    inadmissible = [x.case.case_id for x in rows if x.case.case_id not in admissible]
    return _result(
        EPISTEMIC_ADMISSIBILITY,
        len(admissible),
        len(rows),
        {"admissible_case_ids": admissible, "inadmissible_case_ids": inadmissible},
        [x.case.case_id for x in rows],
        passed=not inadmissible,
    )


def unsupported_claim_rate(rows: Sequence[ScoredRow]) -> MetricResult:
    emitted = 0
    unsupported: dict[str, list[str]] = {}
    for row in rows:
        allowed = set(row.reference.allowed_claim_ids)
        for claim_id in row.result.claim_ids:
            emitted += 1
            if claim_id not in allowed:
                unsupported.setdefault(row.case.case_id, []).append(claim_id)
    count = sum(len(x) for x in unsupported.values())
    return _result(
        UNSUPPORTED_CLAIM_RATE,
        count,
        emitted,
        {"unsupported_claims": unsupported},
        [x.case.case_id for x in rows],
        passed=count == 0,
    )


def _referenced_evidence(result: SystemCaseResult) -> set[str]:
    referenced: set[str] = set()
    for value in result.evidence_references.values():
        referenced.update(x for x in value if isinstance(x, str))
    referenced.update(result.provenance)
    if result.trace is not None:
        referenced.update(
            s
            for e in result.trace.events
            if e.event_type.value.startswith("EVIDENCE_")
            for s in e.subject_ids
        )
    return referenced


def evidence_coverage(rows: Sequence[ScoredRow]) -> MetricResult:
    present = required = admissible_present = admissible_required = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        referenced = _referenced_evidence(row.result)
        found = sorted(set(row.reference.required_evidence_ids) & referenced)
        admissible = sorted(set(row.reference.admissible_evidence_ids) & referenced)
        required += len(row.reference.required_evidence_ids)
        present += len(found)
        admissible_required += len(row.reference.admissible_evidence_ids)
        admissible_present += len(admissible)
        per_case[row.case.case_id] = {
            "required": list(row.reference.required_evidence_ids),
            "present": found,
            "admissible_present": admissible,
            "inadmissible_used_as_support": sorted(
                (
                    set(row.reference.required_evidence_ids)
                    - set(row.reference.admissible_evidence_ids)
                )
                & {x for v in row.result.evidence_references.values() for x in v}
            ),
        }
    return _result(
        EVIDENCE_COVERAGE,
        present,
        required,
        {
            "admissible_present": admissible_present,
            "admissible_required": admissible_required,
            "cases": per_case,
        },
        [x.case.case_id for x in rows],
        passed=None,
    )


def _provenance_components(
    record: Mapping[str, Any], supported: bool
) -> dict[str, bool]:
    return {
        "source_id": bool(record.get("source_id")),
        "content_hash": isinstance(record.get("content_hash"), str)
        and len(record.get("content_hash", "")) == 64,
        "retrieval_chain": bool(record.get("retrieval_mechanism"))
        and "upstream_evidence_ids" in record,
        "transformations": "transformation_ids" in record,
        "support_relationship": supported,
    }


def provenance_completeness(rows: Sequence[ScoredRow]) -> MetricResult:
    satisfied = total = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        if not row.result.claim_ids:
            continue
        claims: dict[str, Any] = {}
        for claim_id in row.result.claim_ids:
            evidence_ids = tuple(row.result.evidence_references.get(claim_id, ()))
            if not evidence_ids:
                total += len(PROVENANCE_COMPONENTS)
                claims[claim_id] = {"evidence": {}, "note": "NO_EVIDENCE_REFERENCE"}
                continue
            claims[claim_id] = {"evidence": {}}
            for evidence_id in evidence_ids:
                record = row.result.provenance.get(evidence_id) or {}
                components = _provenance_components(record, True)
                total += len(components)
                satisfied += sum(components.values())
                claims[claim_id]["evidence"][evidence_id] = components
        per_case[row.case.case_id] = claims
    return _result(
        PROVENANCE_COMPLETENESS,
        satisfied,
        total,
        {"components": list(PROVENANCE_COMPONENTS), "cases": per_case},
        [x.case.case_id for x in rows if x.result.claim_ids],
        passed=None,
    )


def reasoning_provenance_completeness(rows: Sequence[ScoredRow]) -> MetricResult:
    present = required = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        needed = row.reference.required_trace_events
        if not needed:
            continue
        kinds = (
            set()
            if row.result.trace is None
            else {e.event_type.value for e in row.result.trace.events}
        )
        found = sorted(set(needed) & kinds)
        required += len(needed)
        present += len(found)
        per_case[row.case.case_id] = {
            "required": list(needed),
            "present": found,
            "trace": row.result.trace is not None,
        }
    return _result(
        REASONING_PROVENANCE_COMPLETENESS,
        present,
        required,
        {"cases": per_case},
        [x.case.case_id for x in rows if x.reference.required_trace_events],
        passed=None,
    )


def constraint_violation_rate(rows: Sequence[ScoredRow]) -> MetricResult:
    decisions = [x for x in rows if x.reference.required_constraint_behavior == "BLOCK"]
    violations = [
        x.case.case_id
        for x in decisions
        if x.result.claimed_outcome is SystemOutcome.CONCLUDED
        or x.result.constraint_report.get("proceeded") is True
    ]
    return _result(
        CONSTRAINT_VIOLATION_RATE,
        len(violations),
        len(decisions),
        {"violating_case_ids": violations},
        [x.case.case_id for x in decisions],
        passed=not violations,
    )


def abstention_accuracy(rows: Sequence[ScoredRow]) -> MetricResult:
    tp = fp = fn = tn = 0
    false_abstentions: list[str] = []
    missed: list[str] = []
    for row in rows:
        withheld = row.result.decision_outcome in WITHHOLDING_OUTCOMES
        permission_absent = (
            row.reference.expected_permission is not ExpectedPermission.EXPECTED_ALLOW
        )
        if withheld and permission_absent:
            tp += 1
        elif withheld and not permission_absent:
            fp += 1
            false_abstentions.append(row.case.case_id)
        elif not withheld and permission_absent:
            fn += 1
            missed.append(row.case.case_id)
        else:
            tn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    correct = tp + tn
    return _result(
        ABSTENTION_ACCURACY,
        correct,
        len(rows),
        {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "false_abstention_case_ids": false_abstentions,
            "missed_abstention_case_ids": missed,
        },
        [x.case.case_id for x in rows],
        passed=not false_abstentions and not missed,
    )


def contradiction_handling_accuracy(rows: Sequence[ScoredRow]) -> MetricResult:
    satisfied = total = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        expected = set(row.reference.expected_contradiction_ids)
        if not expected:
            continue
        report = row.result.contradiction_handling
        detected = set(report.get("detected", ()))
        marked = set(report.get("marked_resolved", ()))
        basis = report.get("resolution_basis")
        checks = {
            "detected": expected <= detected,
            "branches_preserved": report.get("branches_preserved") is True,
            "no_majority_or_recency_resolution": basis
            not in FORBIDDEN_RESOLUTION_BASES,
            "not_marked_resolved_without_evidence": not (marked & expected)
            or report.get("resolution_evidence_ids"),
            "no_conclusion_while_pending": row.result.claimed_outcome
            is not SystemOutcome.CONCLUDED,
        }
        checks = {k: bool(v) for k, v in checks.items()}
        total += len(checks)
        satisfied += sum(checks.values())
        per_case[row.case.case_id] = checks
    return _result(
        CONTRADICTION_HANDLING_ACCURACY,
        satisfied,
        total,
        {"cases": per_case},
        list(per_case),
        passed=None if not total else satisfied == total,
    )


def uncertainty_discipline(rows: Sequence[ScoredRow]) -> MetricResult:
    satisfied = total = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        expectation = row.reference.uncertainty_expectation
        if not expectation:
            continue
        report = row.result.uncertainty_report
        gate_results = report.get("gate_results") or {}
        gate_failed = any(v is False for v in gate_results.values())
        checks: dict[str, bool] = {}
        if expectation.get("missing_must_be_preserved"):
            checks["missing_uncertainty_preserved"] = (
                report.get("missing_preserved") is True
            )
        if expectation.get("confidence_increase_requires_rule"):
            increases = report.get("confidence_increases") or ()
            checks["confidence_increase_justified"] = all(
                isinstance(x, Mapping) and bool(x.get("rule_id")) for x in increases
            )
        if expectation.get("widening_required"):
            checks["uncertainty_widened"] = report.get("widened") is True
        if expectation.get("gate_must_block"):
            checks["gate_evaluated"] = bool(gate_results)
            checks["threshold_failure_blocked_progression"] = (
                gate_failed
                and row.result.claimed_outcome is not SystemOutcome.CONCLUDED
            )
            checks["model_confidence_not_used_as_override"] = (
                report.get("confidence_override") is not True
            )
        total += len(checks)
        satisfied += sum(checks.values())
        per_case[row.case.case_id] = checks
    return _result(
        UNCERTAINTY_DISCIPLINE,
        satisfied,
        total,
        {"cases": per_case},
        list(per_case),
        passed=None if not total else satisfied == total,
    )


def replanning_efficiency(rows: Sequence[ScoredRow]) -> MetricResult:
    satisfied = total = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        needs_plan = (
            row.reference.required_replanning or row.reference.required_abstention
        )
        if not needs_plan:
            continue
        plans = row.result.plans
        ids = [x.get("plan_id") for x in plans]
        fingerprints = [
            x.get("action_fingerprint") for x in plans if x.get("action_fingerprint")
        ]
        duplicates = len(fingerprints) - len(set(fingerprints))
        unnecessary = sum(int(x.get("unnecessary_action_count", 0) or 0) for x in plans)
        progress_index = next(
            (i for i, x in enumerate(plans) if x.get("progress") is True), None
        )
        checks: dict[str, bool] = {"plan_produced": bool(plans)}
        if row.reference.required_replanning:
            checks["root_cause_targeted"] = (
                bool(plans) and plans[0].get("root_cause_targeted") is True
            )
            checks["no_unnecessary_actions"] = unnecessary == 0
            checks["no_duplicate_plans"] = duplicates == 0
            if row.reference.progress_expected_after_execution:
                checks["progress_within_budget"] = (
                    progress_index is not None
                    and progress_index <= row.reference.max_plans_before_progress
                )
        if row.reference.required_abstention:
            checks["terminal_abstention_when_no_path"] = (
                row.result.claimed_outcome is SystemOutcome.ABSTAINED
                and any(x.get("terminal") is True for x in plans)
            )
        total += len(checks)
        satisfied += sum(checks.values())
        per_case[row.case.case_id] = {
            **checks,
            "plan_count": len(plans),
            "plan_ids": ids,
            "unnecessary_action_count": unnecessary,
            "duplicate_plan_count": duplicates,
            "plans_before_progress": progress_index,
        }
    return _result(
        REPLANNING_EFFICIENCY,
        satisfied,
        total,
        {"cases": per_case},
        list(per_case),
        passed=None if not total else satisfied == total,
    )


def trace_reproducibility(rows: Sequence[ScoredRow]) -> MetricResult:
    satisfied = total = 0
    per_case: dict[str, Any] = {}
    for row in rows:
        trace = row.result.trace
        if trace is None:
            per_case[row.case.case_id] = {"trace": False}
            total += 4
            continue
        validation, replay = row.validation, row.replay
        checks = {
            "replay_valid": replay is not None and replay.valid,
            "no_missing_artifact_refs": validation is not None
            and not validation.missing_artifacts,
            "no_fingerprint_mismatches": validation is not None
            and not validation.fingerprint_mismatches,
            "deterministic_identity": row.repeat_trace_fingerprint is None
            or row.repeat_trace_fingerprint == trace.fingerprint,
        }
        total += len(checks)
        satisfied += sum(checks.values())
        completeness = trace.completeness(
            0 if validation is None else len(validation.unresolved_references)
        )
        per_case[row.case.case_id] = {
            **checks,
            "trace_fingerprint": trace.fingerprint,
            "completeness": completeness.canonical_dict(),
        }
    return _result(
        TRACE_REPRODUCIBILITY,
        satisfied,
        total,
        {"cases": per_case},
        [x.case.case_id for x in rows],
        passed=None if not total else satisfied == total,
    )


METRIC_FUNCTIONS = {
    UNSUPPORTED_CLAIM_RATE: unsupported_claim_rate,
    EVIDENCE_COVERAGE: evidence_coverage,
    PROVENANCE_COMPLETENESS: provenance_completeness,
    REASONING_PROVENANCE_COMPLETENESS: reasoning_provenance_completeness,
    CONSTRAINT_VIOLATION_RATE: constraint_violation_rate,
    ABSTENTION_ACCURACY: abstention_accuracy,
    CONTRADICTION_HANDLING_ACCURACY: contradiction_handling_accuracy,
    UNCERTAINTY_DISCIPLINE: uncertainty_discipline,
    REPLANNING_EFFICIENCY: replanning_efficiency,
    TRACE_REPRODUCIBILITY: trace_reproducibility,
    EPISTEMIC_ADMISSIBILITY: epistemic_admissibility,
}


def compute_metrics(rows: Sequence[ScoredRow]) -> tuple[MetricResult, ...]:
    return tuple(METRIC_FUNCTIONS[name](rows) for name in METRIC_NAMES)
