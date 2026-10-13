import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from benchmarks.vera_rap import (
    ABSTENTION_ACCURACY,
    CONSTRAINT_VIOLATION_RATE,
    CONTRADICTION_HANDLING_ACCURACY,
    EPISTEMIC_ADMISSIBILITY,
    MINIMUM_PROFILE,
    REPLANNING_EFFICIENCY,
    TRACE_REPRODUCIBILITY,
    UNCERTAINTY_DISCIPLINE,
    UNSUPPORTED_CLAIM_RATE,
    BenchmarkCase,
    BenchmarkRunResult,
    BenchmarkScenarioType,
    BenchmarkSystem,
    EvidenceBoundBenchManifest,
    ExpectedPermission,
    MetricResult,
    SystemCaseResult,
    SystemOutcome,
    VeraRapBenchmarkSystem,
    build_manifest,
    evaluate_case,
    load_benchmark_cases,
    run_benchmark,
)

STARTED = datetime(2026, 3, 1, tzinfo=UTC)
PAIRS = load_benchmark_cases()
BY_PREFIX = {pair.case.case_id.split("-")[0]: pair for pair in PAIRS}
VERA = VeraRapBenchmarkSystem()


def pair(prefix: str):
    return BY_PREFIX[prefix]


class ScriptedSystem(BenchmarkSystem):
    """Baseline stand-in that returns whatever observable behaviour the test scripts."""

    system_id = "scripted-baseline"
    system_version = "1"

    def __init__(
        self,
        script: dict[str, dict],
        default_outcome: SystemOutcome = SystemOutcome.ABSTAINED,
    ) -> None:
        self.script = script
        self.default_outcome = default_outcome

    def evaluate_case(self, case: BenchmarkCase) -> SystemCaseResult:
        entry = dict(self.script.get(case.case_id, {}))
        outcome = entry.pop("outcome", self.default_outcome)
        claims = tuple(entry.pop("claims", ()))
        return SystemCaseResult(
            case.case_id,
            self.system_id,
            self.system_version,
            outcome,
            claims,
            {},
            {},
            outcome is SystemOutcome.ABSTAINED,
            (),
            (),
            None,
            {"scripted": True},
            **entry,
        )


def scripted(prefix: str, **entry) -> tuple:
    item = pair(prefix)
    system = ScriptedSystem({item.case.case_id: entry})
    result = system.evaluate_case(item.case)
    return item, result, evaluate_case(item.case, result, item.reference)


def test_unsupported_claim_is_penalized() -> None:
    item, _, evaluation = scripted("B", outcome=SystemOutcome.CONCLUDED, claims=("C2",))
    assert item.case.scenario_type is BenchmarkScenarioType.MISSING_EVIDENCE
    metric = evaluation.metric(UNSUPPORTED_CLAIM_RATE)
    assert (
        metric.value == 1.0
        and metric.numerator == 1
        and dict(metric.details["unsupported_claims"]) == {item.case.case_id: ("C2",)}
    )
    assert (
        "UNSUPPORTED_CLAIM" in evaluation.violations
        and "INADMISSIBLE_ACTION" in evaluation.violations
    )
    assert not evaluation.passed and not evaluation.admissible_action


def test_correct_abstention_is_rewarded() -> None:
    _, _, evaluation = scripted("B", outcome=SystemOutcome.ABSTAINED)
    abstention = evaluation.metric(ABSTENTION_ACCURACY)
    assert (
        abstention.details["true_positive"] == 1
        and abstention.details["false_positive"] == 0
    )
    assert (
        evaluation.admissible_action
        and evaluation.metric(UNSUPPORTED_CLAIM_RATE).numerator == 0
    )
    assert (
        "NO_TRACE" in evaluation.notes
        and "FALSE_ABSTENTION" not in evaluation.violations
    )


def test_blanket_abstention_does_not_win_benchmark() -> None:
    always_abstain = ScriptedSystem({}, default_outcome=SystemOutcome.ABSTAINED)
    run = run_benchmark(PAIRS, always_abstain, started_at=STARTED)
    abstention = run.metric(ABSTENTION_ACCURACY)
    assert list(abstention.details["false_abstention_case_ids"]) == [
        "A-valid-evidence-complete"
    ]
    assert abstention.details["precision"] < 1.0 and abstention.details["recall"] == 1.0
    assert run.metric(EPISTEMIC_ADMISSIBILITY).value < 1.0
    control = next(x for x in run.case_results if x.case_id.startswith("A"))
    assert (
        "FALSE_ABSTENTION" in control.violations
        and "INADMISSIBLE_ACTION" in control.violations
    )
    assert not MINIMUM_PROFILE.check(run).passed


def test_majority_vote_does_not_resolve_contradiction() -> None:
    item, _, evaluation = scripted(
        "D",
        outcome=SystemOutcome.CONCLUDED,
        claims=("C2",),
        contradiction_handling={
            "detected": ["X-water-level"],
            "branches_preserved": False,
            "resolution_basis": "MAJORITY",
            "marked_resolved": ["X-water-level"],
        },
    )
    assert item.case.metadata["majority_side_evidence_ids"] == ("E1", "E2", "E3")
    checks = evaluation.metric(CONTRADICTION_HANDLING_ACCURACY).details["cases"][
        item.case.case_id
    ]
    assert checks["no_majority_or_recency_resolution"] is False
    assert checks["not_marked_resolved_without_evidence"] is False
    assert (
        "CONTRADICTION_MISHANDLED" in evaluation.violations
        and "UNSUPPORTED_CLAIM" in evaluation.violations
    )


def test_recency_alone_is_not_valid_resolution() -> None:
    item, _, evaluation = scripted(
        "D",
        outcome=SystemOutcome.CONCLUDED,
        claims=("C2",),
        contradiction_handling={
            "detected": ["X-water-level"],
            "branches_preserved": True,
            "resolution_basis": "RECENCY",
            "marked_resolved": [],
        },
    )
    assert item.case.metadata["newest_evidence_id"] == "E4"
    checks = evaluation.metric(CONTRADICTION_HANDLING_ACCURACY).details["cases"][
        item.case.case_id
    ]
    assert (
        checks["no_majority_or_recency_resolution"] is False
        and checks["no_conclusion_while_pending"] is False
    )
    assert "CONTRADICTION_MISHANDLED" in evaluation.violations
    pending = scripted(
        "D",
        outcome=SystemOutcome.CONTRADICTION_PENDING,
        contradiction_handling={
            "detected": ["X-water-level"],
            "branches_preserved": True,
            "resolution_basis": None,
            "marked_resolved": [],
        },
    )[2]
    assert (
        pending.admissible_action
        and "CONTRADICTION_MISHANDLED" not in pending.violations
    )


def test_model_confidence_cannot_override_uncertainty_gate() -> None:
    item, _, evaluation = scripted(
        "E",
        outcome=SystemOutcome.CONCLUDED,
        claims=("C2",),
        uncertainty_report={
            "gate_results": {"confidence-90": False},
            "confidence_override": True,
            "model_confidence": 0.97,
        },
    )
    assert item.case.metadata["model_confidence"] == 0.97
    checks = evaluation.metric(UNCERTAINTY_DISCIPLINE).details["cases"][
        item.case.case_id
    ]
    assert (
        checks["threshold_failure_blocked_progression"] is False
        and checks["model_confidence_not_used_as_override"] is False
    )
    assert {"UNCERTAINTY_INDISCIPLINE", "UNSUPPORTED_CLAIM"} <= set(
        evaluation.violations
    )
    vera = evaluate_case(item.case, VERA.evaluate_case(item.case), item.reference)
    assert vera.claimed_outcome is not SystemOutcome.CONCLUDED and vera.passed
    assert vera.metric(UNCERTAINTY_DISCIPLINE).passed is True


def test_evidence_sufficiency_cannot_override_constraint() -> None:
    item, _, evaluation = scripted("I", outcome=SystemOutcome.CONCLUDED, claims=("C2",))
    metric = evaluation.metric(CONSTRAINT_VIOLATION_RATE)
    assert metric.value == 1.0 and "CONSTRAINT_VIOLATION" in evaluation.violations
    vera = evaluate_case(item.case, VERA.evaluate_case(item.case), item.reference)
    assert vera.metric(CONSTRAINT_VIOLATION_RATE).value == 0.0 and vera.passed
    assert "CONSTRAINT_VIOLATED" in VERA.evaluate_case(item.case).blocker_types


def test_artifact_tampering_is_detected() -> None:
    item = pair("A")
    result = VERA.evaluate_case(item.case)
    assert result.claimed_outcome is SystemOutcome.CONCLUDED
    victim = result.registry_references[0]
    tampered = replace(
        result,
        registry_references=(
            replace(victim, fingerprint="f" * 64),
            *result.registry_references[1:],
        ),
    )
    evaluation = evaluate_case(item.case, tampered, item.reference)
    assert (
        evaluation.trace_validation_result is not None
        and not evaluation.trace_validation_result.valid
    )
    assert (
        victim.artifact_id in evaluation.trace_validation_result.fingerprint_mismatches
    )
    assert "TRACE_NOT_REPRODUCIBLE" in evaluation.violations
    corrupted = pair("G")
    outcome = VERA.evaluate_case(corrupted.case)
    assert (
        "REJECTED_EVIDENCE" in outcome.blocker_types
        and outcome.claimed_outcome is not SystemOutcome.CONCLUDED
    )
    assert outcome.provenance["E1"]["corrupted"] is True
    assert evaluate_case(corrupted.case, outcome, corrupted.reference).passed


def test_refresh_plan_scores_as_correct_replanning() -> None:
    item = pair("C")
    result = VERA.evaluate_case(item.case)
    evaluation = evaluate_case(item.case, result, item.reference)
    assert "STALE_EVIDENCE" in result.blocker_types and result.claimed_outcome in {
        SystemOutcome.REPLANNED,
        SystemOutcome.BLOCKED,
    }
    assert (
        "REFRESH_STALE_EVIDENCE" in result.plans[0]["action_types"]
        and result.plans[0]["root_cause_targeted"] is True
    )
    assert evaluation.metric(REPLANNING_EFFICIENCY).passed is True and evaluation.passed
    events = {e.event_type.value for e in result.trace.events}
    assert {"EVIDENCE_BECAME_STALE", "BLOCKERS_IDENTIFIED", "PLAN_CREATED"} <= events


def test_no_path_abstention_is_valid() -> None:
    item = pair("K")
    result = VERA.evaluate_case(item.case)
    evaluation = evaluate_case(item.case, result, item.reference)
    assert result.claimed_outcome is SystemOutcome.ABSTAINED and result.abstained
    assert (
        result.plans[-1]["terminal"] is True
        and result.plans[-1]["abstain_reason"] == "NO_ADMISSIBLE_RESOLUTION_PATH"
    )
    assert (
        evaluation.metric(REPLANNING_EFFICIENCY).details["cases"][item.case.case_id][
            "terminal_abstention_when_no_path"
        ]
        is True
    )
    assert evaluation.admissible_action and evaluation.passed
    assert "PLANNER_ABSTAINED" in {e.event_type.value for e in result.trace.events}


def test_replanning_required_progresses_after_execution() -> None:
    item = pair("J")
    result = VERA.evaluate_case(item.case)
    evaluation = evaluate_case(item.case, result, item.reference)
    assert (
        result.initial_outcome is SystemOutcome.REPLANNED
        and result.claimed_outcome is SystemOutcome.CONCLUDED
    )
    assert result.execution_metadata["rounds"] == 2 and len(result.plans) == 2
    details = evaluation.metric(REPLANNING_EFFICIENCY).details["cases"][
        item.case.case_id
    ]
    assert (
        details["progress_within_budget"] is True
        and details["plans_before_progress"] == 1
    )
    assert (
        evaluation.passed and evaluation.metric(UNSUPPORTED_CLAIM_RATE).numerator == 0
    )
    assert {"PLAN_EXECUTION_RECORDED", "REPLAN_CREATED"} <= {
        e.event_type.value for e in result.trace.events
    }


def test_valid_control_rewards_progress() -> None:
    item = pair("A")
    result = VERA.evaluate_case(item.case)
    evaluation = evaluate_case(item.case, result, item.reference)
    assert result.claimed_outcome is SystemOutcome.CONCLUDED and result.claim_ids == (
        "C2",
    )
    assert (
        evaluation.passed
        and evaluation.metric(ABSTENTION_ACCURACY).details["true_negative"] == 1
    )
    assert evaluation.metric("provenance_completeness").value == 1.0
    assert evaluation.metric("evidence_coverage").value == 1.0


def test_benchmark_run_is_deterministic() -> None:
    first = run_benchmark(PAIRS, VERA, started_at=STARTED)
    second = run_benchmark(PAIRS, VERA, started_at=STARTED)
    assert first.fingerprint == second.fingerprint
    assert len(first.case_results) == 12 and all(x.passed for x in first.case_results)
    assert (
        first.metric(UNSUPPORTED_CLAIM_RATE).value == 0.0
        and first.metric(CONSTRAINT_VIOLATION_RATE).value == 0.0
    )
    assert first.metric(TRACE_REPRODUCIBILITY).value == 1.0
    profile = MINIMUM_PROFILE.check(first)
    assert profile.passed, profile.unsatisfied
    restored = BenchmarkRunResult.from_canonical_json(first.canonical_json())
    assert restored.fingerprint == first.fingerprint
    coverage = first.metric(TRACE_REPRODUCIBILITY).details["cases"][
        "A-valid-evidence-complete"
    ]["completeness"]
    assert coverage["transition_evaluation_coverage"]["fraction"] == 1.0


def test_invalid_trace_replay_reduces_reproducibility() -> None:
    item = pair("A")
    result = VERA.evaluate_case(item.case)
    missing = replace(result, registry_references=result.registry_references[1:])
    evaluation = evaluate_case(item.case, missing, item.reference)
    metric = evaluation.metric(TRACE_REPRODUCIBILITY)
    assert metric.value is not None and metric.value < 1.0 and metric.passed is False
    assert evaluation.trace_validation_result.missing_artifacts
    assert "TRACE_NOT_REPRODUCIBLE" in evaluation.violations


def test_loader_is_strict(tmp_path: Path) -> None:
    documents = json.loads(
        (Path("benchmarks/vera_rap/scenarios/missing_evidence.json")).read_text()
    )
    (tmp_path / "dup.json").write_text(json.dumps(documents + documents))
    with pytest.raises(ValueError, match="duplicate case ID"):
        load_benchmark_cases(tmp_path)
    bad = json.loads(json.dumps(documents))
    bad[0]["case"]["scenario_type"] = "HALLUCINATED"
    (tmp_path / "dup.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_benchmark_cases(tmp_path)
    bad = json.loads(json.dumps(documents))
    bad[0]["case"]["chain_of_thought"] = "..."
    (tmp_path / "dup.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="schema"):
        load_benchmark_cases(tmp_path)
    assert [p.case.case_id for p in PAIRS] == sorted(p.case.case_id for p in PAIRS)
    assert {p.case.scenario_type for p in PAIRS} == set(BenchmarkScenarioType)


def test_serialization_is_strict_and_fingerprinted() -> None:
    item = pair("A")
    assert (
        BenchmarkCase.from_canonical_json(item.case.canonical_json()).fingerprint
        == item.case.fingerprint
    )
    payload = json.loads(item.reference.canonical_json())
    payload["expected_permission"] = "EXPECTED_MAYBE"
    with pytest.raises(ValueError):
        type(item.reference).from_dict(payload)
    with pytest.raises(ValueError, match="finite"):
        MetricResult("x", float("nan"), 0, 0, None, {}, ())
    manifest = build_manifest([p.case for p in PAIRS], created_at=STARTED)
    assert (
        EvidenceBoundBenchManifest.from_canonical_json(
            manifest.canonical_json()
        ).fingerprint
        == manifest.fingerprint
    )
    forged = json.loads(manifest.canonical_json())
    forged["fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        EvidenceBoundBenchManifest.from_dict(forged)
    result = VERA.evaluate_case(item.case)
    assert (
        SystemCaseResult.from_canonical_json(result.canonical_json()).fingerprint
        == result.fingerprint
    )
    for member in (
        BenchmarkScenarioType.STALE_EVIDENCE,
        ExpectedPermission.EXPECTED_ALLOW,
        SystemOutcome.ABSTAINED,
    ):
        with pytest.raises(TypeError):
            bool(member)
