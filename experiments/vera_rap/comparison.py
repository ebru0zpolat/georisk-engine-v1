"""Metric-by-metric comparison across system families (RAP-011).

Nothing is collapsed into a winner. Lower-is-better metrics are explicit,
missing capabilities are NOT_AVAILABLE rather than failures, and every pairwise
delta keeps its absolute value and a documented direction.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from benchmarks.vera_rap import (
    EPISTEMIC_ADMISSIBILITY,
    METRIC_NAMES,
    REASONING_PROVENANCE_COMPLETENESS,
    REPLANNING_EFFICIENCY,
    TRACE_REPRODUCIBILITY,
    UNCERTAINTY_DISCIPLINE,
    UNSUPPORTED_CLAIM_RATE,
    BenchmarkRunResult,
    MetricResult,
    SystemCaseResult,
)
from benchmarks.vera_rap.metrics import LOWER_IS_BETTER

from .models import (
    ComparisonResult,
    E1ComparisonReport,
    E1ExperimentManifest,
    E1RunResult,
    MetricAvailability,
    MetricSystemValue,
    PairwiseDelta,
    SystemConfig,
)

PRIMARY_METRIC = UNSUPPORTED_CLAIM_RATE
COMPARED_METRICS: tuple[str, ...] = METRIC_NAMES


def metric_availability(
    metric_name: str, metric: MetricResult, results: Sequence[SystemCaseResult]
) -> tuple[MetricAvailability, str | None]:
    """Distinguish a capability the system lacks from a metric with nothing to score."""
    if metric_name in {
        TRACE_REPRODUCIBILITY,
        REASONING_PROVENANCE_COMPLETENESS,
    } and not any(x.trace is not None for x in results):
        return MetricAvailability.NOT_AVAILABLE, "system emits no cognitive trace"
    if (
        metric_name == REPLANNING_EFFICIENCY
        and not any(x.plans for x in results)
        and metric.denominator
    ):
        return MetricAvailability.NOT_AVAILABLE, "system emits no explicit plans"
    if (
        metric_name == UNCERTAINTY_DISCIPLINE
        and metric.denominator
        and not any(x.uncertainty_report.get("gate_results") for x in results)
    ):
        return (
            MetricAvailability.NOT_AVAILABLE,
            "system reports no uncertainty gate results",
        )
    if metric.denominator == 0:
        return (
            MetricAvailability.NOT_APPLICABLE,
            "no scored observations for this metric",
        )
    return MetricAvailability.AVAILABLE, None


def compare_metric(
    metric_name: str,
    runs: Sequence[tuple[SystemConfig, BenchmarkRunResult, Sequence[SystemCaseResult]]],
) -> ComparisonResult:
    lower_is_better = metric_name in LOWER_IS_BETTER
    values: list[MetricSystemValue] = []
    for config, run, results in runs:
        metric = run.metric(metric_name)
        availability, note = metric_availability(metric_name, metric, results)
        values.append(
            MetricSystemValue(
                config.system_id,
                availability,
                metric.value if availability is MetricAvailability.AVAILABLE else None,
                metric.numerator,
                metric.denominator,
                metric.passed if availability is MetricAvailability.AVAILABLE else None,
                note,
            )
        )
    available = [
        x
        for x in values
        if x.availability is MetricAvailability.AVAILABLE and x.value is not None
    ]
    ordered = sorted(available, key=lambda x: ((x.value if lower_is_better else -x.value), x.system_id))  # type: ignore[operator]
    rank_order = tuple(x.system_id for x in ordered)
    best = tuple(
        x.system_id for x in ordered if ordered and x.value == ordered[0].value
    )
    groups: dict[float, list[str]] = {}
    for item in ordered:
        groups.setdefault(item.value, []).append(item.system_id)  # type: ignore[arg-type]
    ties = tuple(tuple(v) for v in groups.values() if len(v) > 1)
    deltas: list[PairwiseDelta] = []
    for a in ordered:
        for b in ordered:
            if a.system_id == b.system_id:
                continue
            absolute = a.value - b.value  # type: ignore[operator]
            relative = None if a.value == 0 else absolute / abs(a.value)  # type: ignore[operator]
            direction = (
                f"positive means {b.system_id} lower (better) than {a.system_id}"
                if lower_is_better
                else f"positive means {a.system_id} higher (better) than {b.system_id}"
            )
            deltas.append(
                PairwiseDelta(a.system_id, b.system_id, absolute, relative, direction)
            )
    return ComparisonResult(
        metric_name,
        lower_is_better,
        metric_name == PRIMARY_METRIC,
        tuple(values),
        rank_order,
        best,
        ties,
        tuple(deltas),
        {
            "delta_formula": "absolute_delta = value(system_a) - value(system_b); relative_improvement = absolute_delta / |value(system_a)| or null when value(system_a) is 0",
            "lower_is_better": lower_is_better,
            "compared_system_ids": [x.system_id for x in values],
            "unavailable_system_ids": [
                x.system_id
                for x in values
                if x.availability is MetricAvailability.NOT_AVAILABLE
            ],
            "not_applicable_system_ids": [
                x.system_id
                for x in values
                if x.availability is MetricAvailability.NOT_APPLICABLE
            ],
        },
    )


def compare_runs(
    runs: Sequence[tuple[SystemConfig, BenchmarkRunResult, Sequence[SystemCaseResult]]],
    metric_names: Sequence[str] = COMPARED_METRICS,
) -> tuple[ComparisonResult, ...]:
    if len({config.system_id for config, _, _ in runs}) != len(runs):
        raise ValueError("duplicate system ID in comparison")
    return tuple(compare_metric(name, runs) for name in metric_names)


def comparison_summary(comparisons: Sequence[ComparisonResult]) -> dict[str, Any]:
    """Compact machine-readable view: per metric, values and ranks; no winner."""
    return {
        item.metric_name: {
            "primary": item.primary,
            "lower_is_better": item.lower_is_better,
            "values": {
                x.system_id: (
                    x.value
                    if x.availability is MetricAvailability.AVAILABLE
                    else x.availability.value
                )
                for x in item.system_values
            },
            "rank_order": list(item.rank_order),
            "best_system_ids": list(item.best_system_ids),
        }
        for item in comparisons
    } | {"admissibility_metric": EPISTEMIC_ADMISSIBILITY}


def build_comparison_report(
    run: E1RunResult,
    manifest: E1ExperimentManifest,
    *,
    limitations: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> E1ComparisonReport:
    """Machine-readable report: manifest, per-system summary, comparisons, case diffs."""
    from .models import CaseComparison

    system_summary = {
        item.system_config.system_id: {
            "system_family": item.system_config.system_family.value,
            "system_version": item.system_config.system_version,
            "adapter_id": item.system_config.adapter_id,
            "adapter_version": item.system_config.adapter_version,
            "retriever_id": item.system_config.retriever_id,
            "prompt_template_version": item.system_config.prompt_template_version,
            "scored_case_count": len(item.benchmark_run_result.case_results),
            "parsing_failure_count": len(item.parsing_failures),
            "case_failure_counts": {
                kind: sum(1 for x in item.case_failures if x.failure_type.value == kind)
                for kind in sorted({x.failure_type.value for x in item.case_failures})
            },
            "identical_case_output_rate": item.determinism_summary.identical_case_output_rate,
            "identical_benchmark_fingerprint_rate": item.determinism_summary.identical_benchmark_fingerprint_rate,
            "benchmark_run_fingerprint": item.benchmark_run_result.fingerprint,
        }
        for item in run.system_runs
    }
    primary = run.comparison(PRIMARY_METRIC)
    primary_summary = {
        "metric_name": PRIMARY_METRIC,
        "lower_is_better": True,
        "values": {
            x.system_id: {
                "availability": x.availability.value,
                "value": x.value,
                "unsupported": x.numerator,
                "emitted": x.denominator,
            }
            for x in primary.system_values
        },
        "rank_order": list(primary.rank_order),
        "best_system_ids": list(primary.best_system_ids),
        "pairwise_deltas": [x.canonical_dict() for x in primary.pairwise_deltas],
    }
    cases = tuple(
        CaseComparison.from_dict(x)
        for x in (run.metadata or {}).get("case_comparisons", ())
    )
    base_limitations = (
        "OFFLINE FIXTURE PILOT: fixture baselines encode scripted behaviours, not commercial LLM providers.",
        "No statistical significance testing; deterministic repetitions are not independent observations.",
        "Metrics marked NOT_AVAILABLE reflect absent capabilities, not failures.",
    )
    return E1ComparisonReport(
        manifest,
        system_summary,
        run.comparisons,
        cases,
        primary_summary,
        (*base_limitations, *limitations),
        {"run_fingerprint": run.fingerprint, **dict(metadata or {})},
    )
