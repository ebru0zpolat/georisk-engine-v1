"""Experiment E1 runner (RAP-011): same cases, several systems, repetitions.

A system error, parsing failure, or invalid citation becomes a structured
case failure; it never aborts the experiment and never fabricates output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.research.vera_rap.evidence import _timestamp
from benchmarks.vera_rap import (
    BENCHMARK_VERSION,
    UNSUPPORTED_CLAIM_RATE,
    BenchmarkCase,
    BenchmarkCasePair,
    BenchmarkRunResult,
    BenchmarkScenarioType,
    CaseEvaluation,
    ReferenceOutcome,
    ScoredRow,
    SystemCaseResult,
    SystemOutcome,
    build_manifest,
    compute_metrics,
    evaluate_case,
)
from benchmarks.vera_rap.evaluator import _trace_checks

from .adapters import ExperimentSystem, case_evidence_ids
from .comparison import compare_runs
from .models import (
    CaseComparison,
    DeterminismSummary,
    E1ExperimentConfig,
    E1RunResult,
    ExperimentCaseFailure,
    ExperimentFailureType,
    ParsingFailure,
    ParsingFailureResult,
    SystemConfig,
    SystemExperimentResult,
    _sha,
)

_VIOLATION_FAILURES: dict[str, ExperimentFailureType] = {
    "UNSUPPORTED_CLAIM": ExperimentFailureType.UNSUPPORTED_CLAIM,
    "CONSTRAINT_VIOLATION": ExperimentFailureType.CONSTRAINT_BYPASS,
    "CONTRADICTION_MISHANDLED": ExperimentFailureType.CONTRADICTION_BYPASS,
    "UNCERTAINTY_INDISCIPLINE": ExperimentFailureType.UNCERTAINTY_BYPASS,
    "NONDETERMINISTIC_RESULT": ExperimentFailureType.NONDETERMINISTIC_OUTPUT,
}


def _pairs(
    benchmark_cases: Sequence[BenchmarkCase | BenchmarkCasePair],
    reference_outcomes: Sequence[ReferenceOutcome],
    case_ids: Sequence[str],
) -> tuple[BenchmarkCasePair, ...]:
    cases: dict[str, BenchmarkCase] = {}
    references: dict[str, ReferenceOutcome] = {x.case_id: x for x in reference_outcomes}
    for item in benchmark_cases:
        case = item.case if isinstance(item, BenchmarkCasePair) else item
        if isinstance(item, BenchmarkCasePair):
            references[case.case_id] = item.reference
        cases[case.case_id] = case
    missing = sorted(set(case_ids) - set(cases))
    if missing:
        raise ValueError(f"benchmark cases missing for: {', '.join(missing)}")
    unreferenced = sorted(set(case_ids) - set(references))
    if unreferenced:
        raise ValueError(f"reference outcomes missing for: {', '.join(unreferenced)}")
    return tuple(BenchmarkCasePair(cases[x], references[x]) for x in sorted(case_ids))


def _raw_output(
    system: ExperimentSystem, case_id: str, result: SystemCaseResult | None
) -> Mapping[str, Any]:
    """Audit record safe to fingerprint: raw provider text appears only as a SHA-256."""
    outputs = getattr(system, "outputs", None)
    if isinstance(outputs, Mapping) and case_id in outputs:
        output = outputs[case_id]
        if hasattr(output, "audit_dict"):
            return {"kind": type(output).__name__, **output.audit_dict()}
        payload = output.canonical_dict()
        raw = payload.pop("raw_response", None)
        return {
            "kind": type(output).__name__,
            **payload,
            "raw_response_sha256": None if raw is None else _sha(raw),
        }
    if result is None:
        return {"kind": "none", "case_id": case_id}
    return {
        "kind": "SystemCaseResult",
        "case_id": case_id,
        "fingerprint": result.fingerprint,
        "claimed_outcome": result.claimed_outcome.value,
        "claim_ids": list(result.claim_ids),
        "trace_fingerprint": None if result.trace is None else result.trace.fingerprint,
    }


def _citation_failures(
    config: SystemConfig, case: BenchmarkCase, result: SystemCaseResult
) -> list[ExperimentCaseFailure]:
    known = case_evidence_ids(case)
    cited: set[str] = set()
    for value in result.evidence_references.values():
        cited.update(x for x in value if isinstance(x, str))
    cited.update(k for k in result.provenance if isinstance(k, str))
    unknown = sorted(cited - known)
    if not unknown:
        return []
    return [
        ExperimentCaseFailure(
            case.case_id,
            config.system_id,
            ExperimentFailureType.INVALID_CITATION,
            "cited evidence IDs do not exist in the case",
            {"unknown_evidence_ids": unknown},
        )
    ]


def capability_filtered_violations(
    result: SystemCaseResult, violations: Sequence[str]
) -> tuple[str, ...]:
    """Drop violations that only encode an absent capability, never a behaviour."""
    dropped: set[str] = set()
    if not result.plans:
        dropped.add("REPLANNING_INEFFICIENT")
    if not result.uncertainty_report.get("gate_results"):
        dropped.add("UNCERTAINTY_INDISCIPLINE")
    if result.trace is None:
        dropped.add("TRACE_NOT_REPRODUCIBLE")
    return tuple(x for x in violations if x not in dropped)


def _behaviour_failures(
    config: SystemConfig,
    case: BenchmarkCase,
    result: SystemCaseResult,
    evaluation: CaseEvaluation,
) -> list[ExperimentCaseFailure]:
    failures: list[ExperimentCaseFailure] = []
    for violation in capability_filtered_violations(result, evaluation.violations):
        kind = _VIOLATION_FAILURES.get(violation)
        if kind is not None:
            failures.append(
                ExperimentCaseFailure(
                    case.case_id,
                    config.system_id,
                    kind,
                    f"benchmark violation {violation}",
                )
            )
    if result.claimed_outcome is SystemOutcome.CONCLUDED:
        scenario = case.scenario_type
        if scenario is BenchmarkScenarioType.STALE_EVIDENCE:
            failures.append(
                ExperimentCaseFailure(
                    case.case_id,
                    config.system_id,
                    ExperimentFailureType.STALE_EVIDENCE_USE,
                    "concluded from evidence that is stale at the evaluation instant",
                )
            )
        if scenario in {
            BenchmarkScenarioType.INVALID_TRANSFORMATION,
            BenchmarkScenarioType.CORRUPTED_SOURCE,
        }:
            failures.append(
                ExperimentCaseFailure(
                    case.case_id,
                    config.system_id,
                    ExperimentFailureType.INVALID_TRANSFORMATION_USE,
                    "concluded through invalid transformation lineage or a corrupted source",
                )
            )
    return failures


def score_system(
    config: SystemConfig,
    system: ExperimentSystem,
    pairs: Sequence[BenchmarkCasePair],
    *,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> tuple[
    BenchmarkRunResult,
    dict[str, SystemCaseResult],
    tuple[Mapping[str, Any], ...],
    tuple[ParsingFailureResult, ...],
    tuple[ExperimentCaseFailure, ...],
]:
    """Score one system once. Errors and parsing failures are structured, not scored."""
    _timestamp(started_at, "started_at")
    results: dict[str, SystemCaseResult] = {}
    parsing: list[ParsingFailureResult] = []
    failures: list[ExperimentCaseFailure] = []
    raw: list[Mapping[str, Any]] = []
    for pair in pairs:
        case_id = pair.case.case_id
        try:
            result = system.evaluate_case(pair.case)
        except ParsingFailure as exc:
            parsing.append(exc.result)
            failures.append(
                ExperimentCaseFailure(
                    case_id,
                    config.system_id,
                    ExperimentFailureType.PARSING_FAILURE,
                    exc.result.reason_code,
                )
            )
            raw.append(_raw_output(system, case_id, None))
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(
                ExperimentCaseFailure(
                    case_id,
                    config.system_id,
                    ExperimentFailureType.SYSTEM_ERROR,
                    f"{type(exc).__name__}: {exc}"[:500],
                )
            )
            raw.append(
                {"kind": "error", "case_id": case_id, "error_type": type(exc).__name__}
            )
            continue
        if result.system_id != config.system_id:
            failures.append(
                ExperimentCaseFailure(
                    case_id,
                    config.system_id,
                    ExperimentFailureType.SYSTEM_ERROR,
                    "result carries a different system ID",
                )
            )
            continue
        results[case_id] = result
        raw.append(_raw_output(system, case_id, result))
        failures.extend(_citation_failures(config, pair.case, result))
    rows: list[ScoredRow] = []
    evaluations: list[CaseEvaluation] = []
    for pair in pairs:
        result = results.get(pair.case.case_id)
        if result is None:
            continue
        evaluation = evaluate_case(pair.case, result, pair.reference)
        evaluations.append(evaluation)
        failures.extend(_behaviour_failures(config, pair.case, result, evaluation))
        validation, replay = _trace_checks(result)
        rows.append(
            ScoredRow(pair.case, result, pair.reference, validation, replay, None)
        )
    manifest = build_manifest([x.case for x in pairs], created_at=started_at)
    run = BenchmarkRunResult(
        BENCHMARK_VERSION,
        config.system_id,
        config.system_version,
        tuple(evaluations),
        compute_metrics(rows),
        started_at,
        completed_at or started_at,
        manifest.fingerprint,
        {
            "system_family": config.system_family.value,
            "adapter_id": config.adapter_id,
            "adapter_version": config.adapter_version,
            "scored_case_ids": sorted(results),
            "unscored_case_ids": sorted(
                {
                    x.case_id
                    for x in failures
                    if x.failure_type
                    in {
                        ExperimentFailureType.PARSING_FAILURE,
                        ExperimentFailureType.SYSTEM_ERROR,
                    }
                }
            ),
        },
    )
    return run, results, tuple(raw), tuple(parsing), tuple(failures)


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": None if denominator == 0 else numerator / denominator,
    }


def build_case_comparisons(
    pairs: Sequence[BenchmarkCasePair],
    system_runs: Sequence[SystemExperimentResult],
    results_by_system: Mapping[str, Mapping[str, SystemCaseResult]],
) -> tuple[CaseComparison, ...]:
    comparisons: list[CaseComparison] = []
    for pair in pairs:
        case_id = pair.case.case_id
        outcomes: dict[str, Any] = {}
        claims: dict[str, Any] = {}
        abstained: dict[str, Any] = {}
        violations: dict[str, Any] = {}
        ucr: dict[str, Any] = {}
        failures: list[ExperimentCaseFailure] = []
        for run in system_runs:
            system_id = run.system_config.system_id
            result = results_by_system.get(system_id, {}).get(case_id)
            evaluation = next(
                (
                    x
                    for x in run.benchmark_run_result.case_results
                    if x.case_id == case_id
                ),
                None,
            )
            outcomes[system_id] = (
                None
                if result is None
                else {
                    "claimed": result.claimed_outcome.value,
                    "decision": result.decision_outcome.value,
                }
            )
            claims[system_id] = None if result is None else list(result.claim_ids)
            abstained[system_id] = None if result is None else result.abstained
            violations[system_id] = (
                None
                if evaluation is None or result is None
                else list(capability_filtered_violations(result, evaluation.violations))
            )
            if evaluation is None:
                ucr[system_id] = None
            else:
                metric = evaluation.metric(UNSUPPORTED_CLAIM_RATE)
                ucr[system_id] = {
                    "unsupported": metric.numerator,
                    "emitted": metric.denominator,
                }
            failures.extend(x for x in run.case_failures if x.case_id == case_id)
        comparisons.append(
            CaseComparison(
                case_id,
                pair.case.scenario_type.value,
                pair.reference.expected_permission,
                outcomes,
                claims,
                abstained,
                violations,
                ucr,
                tuple(failures),
            )
        )
    return tuple(comparisons)


def run_e1_experiment(
    config: E1ExperimentConfig,
    benchmark_cases: Sequence[BenchmarkCase | BenchmarkCasePair],
    reference_outcomes: Sequence[ReferenceOutcome],
    systems: Sequence[ExperimentSystem],
    *,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> E1RunResult:
    """Run every configured system over the same case set; deterministic when systems are."""
    started = started_at or config.evaluation_timestamp
    pairs = _pairs(benchmark_cases, reference_outcomes, config.case_ids)
    manifest = build_manifest(
        [x.case for x in pairs], created_at=config.evaluation_timestamp
    )
    if manifest.fingerprint != config.benchmark_manifest_fingerprint:
        raise ValueError(
            "benchmark manifest fingerprint does not match the configured case set"
        )
    by_id = {system.system_id: system for system in systems}
    if len(by_id) != len(systems):
        raise ValueError("duplicate system ID among systems")
    system_runs: list[SystemExperimentResult] = []
    comparison_inputs = []
    results_by_system: dict[str, Mapping[str, SystemCaseResult]] = {}
    for system_config in config.system_configs:
        system = by_id.get(system_config.system_id)
        if system is None:
            raise ValueError(f"no system supplied for {system_config.system_id}")
        if system.system_family is not system_config.system_family:
            raise ValueError(
                f"{system_config.system_id} family does not match its config"
            )
        runs: list[BenchmarkRunResult] = []
        repetition_results: list[dict[str, SystemCaseResult]] = []
        raw_first: tuple[Mapping[str, Any], ...] = ()
        parsing: dict[str, ParsingFailureResult] = {}
        failures: dict[tuple[str, str, str], ExperimentCaseFailure] = {}
        for repetition in range(config.repetitions):
            run, results, raw, failed_parsing, failed = score_system(
                system_config,
                system,
                pairs,
                started_at=started,
                completed_at=completed_at,
            )
            runs.append(run)
            repetition_results.append(results)
            if repetition == 0:
                raw_first = raw
            for item in failed_parsing:
                parsing[item.fingerprint] = item
            for item in failed:
                failures[(item.case_id, item.failure_type.value, item.reason)] = item
        scored = (
            sorted(set.intersection(*[set(x) for x in repetition_results]))
            if repetition_results
            else []
        )
        identical_cases = 0
        for case_id in scored:
            if len({x[case_id].fingerprint for x in repetition_results}) == 1:
                identical_cases += 1
            else:
                item = ExperimentCaseFailure(
                    case_id,
                    system_config.system_id,
                    ExperimentFailureType.NONDETERMINISTIC_OUTPUT,
                    "repetitions produced different results",
                )
                failures[(case_id, item.failure_type.value, item.reason)] = item
        identical_runs = sum(1 for x in runs if x.fingerprint == runs[0].fingerprint)
        summary = DeterminismSummary(
            config.repetitions,
            tuple(scored),
            _rate(identical_cases, len(scored)),
            _rate(identical_runs, len(runs)),
            {
                case_id: [x[case_id].fingerprint for x in repetition_results]
                for case_id in scored
            },
            tuple(x.fingerprint for x in runs),
            tuple(sorted({x.case_id for x in parsing.values()})),
        )
        system_runs.append(
            SystemExperimentResult(
                system_config,
                runs[0],
                tuple(runs),
                raw_first,
                tuple(parsing.values()),
                summary,
                tuple(failures.values()),
            )
        )
        comparison_inputs.append(
            (system_config, runs[0], tuple(repetition_results[0].values()))
        )
        results_by_system[system_config.system_id] = repetition_results[0]
    comparisons = compare_runs(comparison_inputs)
    case_comparisons = build_case_comparisons(pairs, system_runs, results_by_system)
    return E1RunResult(
        config.experiment_id,
        config.experiment_version,
        config.benchmark_manifest_fingerprint,
        config.fingerprint,
        tuple(system_runs),
        comparisons,
        started,
        completed_at or started,
        {
            "repetitions": config.repetitions,
            "case_count": len(pairs),
            "case_comparisons": [x.canonical_dict() for x in case_comparisons],
            **dict(metadata or {}),
        },
    )
