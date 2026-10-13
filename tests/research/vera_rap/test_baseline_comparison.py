import json
from datetime import UTC, datetime

import pytest

from benchmarks.vera_rap import (
    ABSTENTION_ACCURACY,
    CONTRADICTION_HANDLING_ACCURACY,
    EPISTEMIC_ADMISSIBILITY,
    TRACE_REPRODUCIBILITY,
    UNSUPPORTED_CLAIM_RATE,
    BenchmarkScenarioType,
    SystemOutcome,
    load_benchmark_cases,
)
from experiments.vera_rap import (
    RESPONSE_SCHEMA,
    BaselineLLMAdapter,
    E1RunResult,
    ExperimentFailureType,
    FixtureGenerator,
    KeywordOverlapRetriever,
    MetricAvailability,
    ParsingFailure,
    RAGLLMAdapter,
    SystemConfig,
    SystemFamily,
    VeraRapExperimentSystem,
    build_baseline_prompt,
    build_comparison_report,
    build_corpus_from_case,
    build_default_systems,
    build_e1_case_set,
    build_e1_config,
    build_e1_manifest,
    build_rag_prompt,
    case_set_balance,
    default_system_configs,
    load_fixture_generators,
    normalize_output,
    run_e1_experiment,
)

AT = datetime(2026, 3, 1, tzinfo=UTC)
PAIRS = load_benchmark_cases()
BY_PREFIX = {pair.case.case_id.split("-")[0]: pair for pair in PAIRS}
GENERATORS = load_fixture_generators()
CONFIGS = default_system_configs()
BASELINE_CONFIG, RAG_CONFIG, VERA_CONFIG = CONFIGS


def experiment(
    baseline: str, rag: str, *, pairs=PAIRS, repetitions: int = 2, systems=None
) -> E1RunResult:
    systems = systems or build_default_systems(
        CONFIGS,
        baseline_generator=GENERATORS[baseline],
        rag_generator=GENERATORS[rag],
        retrieved_at=AT,
    )
    config = build_e1_config(
        pairs, CONFIGS, evaluation_timestamp=AT, repetitions=repetitions
    )
    return run_e1_experiment(config, pairs, (), systems)


def case_diff(run: E1RunResult, prefix: str) -> dict:
    return next(
        x for x in run.metadata["case_comparisons"] if x["case_id"].startswith(prefix)
    )


def test_e1_runs_same_cases_across_all_system_families() -> None:
    run = experiment("baseline-confident", "rag-insufficiency-aware")
    families = {x.system_config.system_family for x in run.system_runs}
    assert families == {
        SystemFamily.BASELINE_LLM,
        SystemFamily.RAG_LLM,
        SystemFamily.VERA_RAP,
    }
    scored = {
        x.system_config.system_id: [
            c.case_id for c in x.benchmark_run_result.case_results
        ]
        for x in run.system_runs
    }
    assert (
        len({tuple(v) for v in scored.values()}) == 1
        and len(next(iter(scored.values()))) == 12
    )
    assert all(
        x.benchmark_run_result.manifest_fingerprint
        == run.benchmark_manifest_fingerprint
        for x in run.system_runs
    )
    assert len(run.comparisons) == 11 and run.comparison(UNSUPPORTED_CLAIM_RATE).primary


def test_vera_rap_has_lower_ucr_on_epistemic_failure_cases() -> None:
    failure_cases = tuple(
        p
        for p in PAIRS
        if p.case.scenario_type is not BenchmarkScenarioType.VALID_EVIDENCE_COMPLETE
    )
    run = experiment("baseline-confident", "rag-cited-overreach", pairs=failure_cases)
    ucr = run.comparison(UNSUPPORTED_CLAIM_RATE)
    assert ucr.lower_is_better
    assert ucr.value_for("baseline-llm").value > ucr.value_for("vera-rap").value == 0.0
    assert ucr.value_for("rag-llm").value > 0.0
    assert ucr.rank_order[0] == "vera-rap" and "vera-rap" in ucr.best_system_ids
    failures = {x.failure_type for x in run.system_run("baseline-llm").case_failures}
    assert {
        ExperimentFailureType.UNSUPPORTED_CLAIM,
        ExperimentFailureType.STALE_EVIDENCE_USE,
        ExperimentFailureType.UNCERTAINTY_BYPASS,
    } <= failures


def test_baseline_can_pass_valid_control_case() -> None:
    run = experiment(
        "baseline-recency", "rag-insufficiency-aware", pairs=(BY_PREFIX["A"],)
    )
    diff = case_diff(run, "A")
    assert diff["system_outcomes"]["baseline-llm"]["claimed"] == "CONCLUDED"
    assert not diff["violations"]["baseline-llm"] and list(
        diff["material_claims"]["baseline-llm"]
    ) == ["C2"]
    ucr = run.comparison(UNSUPPORTED_CLAIM_RATE)
    assert (
        ucr.value_for("baseline-llm").value == 0.0
        and "baseline-llm" in ucr.best_system_ids
    )
    assert (
        run.comparison(EPISTEMIC_ADMISSIBILITY).value_for("baseline-llm").value == 1.0
    )


def test_rag_can_improve_when_retrieval_supplies_admissible_evidence() -> None:
    run = experiment(
        "baseline-confident", "rag-insufficiency-aware", pairs=(BY_PREFIX["J"],)
    )
    diff = case_diff(run, "J")
    assert diff["system_outcomes"]["baseline-llm"]["decision"] == "CONCLUDED"
    assert "INADMISSIBLE_ACTION" in diff["violations"]["baseline-llm"]
    assert dict(diff["system_outcomes"]["rag-llm"]) == {
        "claimed": "CONCLUDED",
        "decision": "REPLANNED",
    }
    assert not diff["violations"]["rag-llm"] and list(
        diff["material_claims"]["rag-llm"]
    ) == ["C2"]
    rag_system = next(
        s for s in run.system_runs if s.system_config.system_id == "rag-llm"
    )
    raw = next(x for x in rag_system.raw_case_outputs if x["case_id"].startswith("J"))
    assert "doc:E2" in raw["metadata"]["retrieved_document_ids"]
    admissibility = run.comparison(EPISTEMIC_ADMISSIBILITY)
    assert (
        admissibility.value_for("rag-llm").value
        > admissibility.value_for("baseline-llm").value
    )


def test_retrieval_does_not_make_inadmissible_evidence_valid() -> None:
    run = experiment(
        "baseline-cautious",
        "rag-cited-overreach",
        pairs=(BY_PREFIX["C"], BY_PREFIX["G"]),
    )
    rag = run.system_run("rag-llm")
    assert run.comparison(UNSUPPORTED_CLAIM_RATE).value_for("rag-llm").value == 1.0
    kinds = {x.failure_type for x in rag.case_failures}
    assert {
        ExperimentFailureType.UNSUPPORTED_CLAIM,
        ExperimentFailureType.STALE_EVIDENCE_USE,
        ExperimentFailureType.INVALID_TRANSFORMATION_USE,
    } <= kinds
    provenance = run.comparison("provenance_completeness").value_for("rag-llm")
    assert provenance.availability is MetricAvailability.AVAILABLE
    diff = case_diff(run, "G")
    assert "UNSUPPORTED_CLAIM" in diff["violations"]["rag-llm"]


def test_baseline_majority_resolution_is_penalized() -> None:
    run = experiment(
        "baseline-confident", "rag-insufficiency-aware", pairs=(BY_PREFIX["D"],)
    )
    contradiction = run.comparison(CONTRADICTION_HANDLING_ACCURACY)
    assert (
        contradiction.value_for("baseline-llm").value
        < contradiction.value_for("vera-rap").value
        == 1.0
    )
    baseline = run.system_run("baseline-llm")
    assert ExperimentFailureType.CONTRADICTION_BYPASS in {
        x.failure_type for x in baseline.case_failures
    }
    raw = baseline.raw_case_outputs[0]
    assert (
        raw["reported_contradictions"]["resolution_basis"] == "MAJORITY"
        and raw["raw_response"] is None
    )
    assert len(raw["raw_response_sha256"]) == 64


def test_rag_recency_resolution_is_penalized() -> None:
    run = experiment("baseline-cautious", "rag-recency", pairs=(BY_PREFIX["D"],))
    rag = run.system_run("rag-llm")
    assert ExperimentFailureType.CONTRADICTION_BYPASS in {
        x.failure_type for x in rag.case_failures
    }
    assert (
        run.comparison(CONTRADICTION_HANDLING_ACCURACY).value_for("rag-llm").value < 1.0
    )
    assert (
        rag.raw_case_outputs[0]["reported_contradictions"]["resolution_basis"]
        == "RECENCY"
    )
    assert list(rag.raw_case_outputs[0]["cited_evidence_ids"]) == ["E4"]


def test_high_confidence_does_not_change_epistemic_permission() -> None:
    run = experiment(
        "baseline-confident",
        "rag-insufficiency-aware",
        pairs=(BY_PREFIX["C"], BY_PREFIX["E"]),
    )
    baseline = run.system_run("baseline-llm")
    confidences = {
        x["case_id"]: x["reported_uncertainty"]["confidence"]
        for x in baseline.raw_case_outputs
    }
    assert all(value == 0.99 for value in confidences.values())
    assert run.comparison(UNSUPPORTED_CLAIM_RATE).value_for("baseline-llm").value == 1.0
    kinds = {x.failure_type for x in baseline.case_failures}
    assert {
        ExperimentFailureType.UNCERTAINTY_BYPASS,
        ExperimentFailureType.STALE_EVIDENCE_USE,
    } <= kinds
    for prefix in ("C", "E"):
        assert (
            "INADMISSIBLE_ACTION"
            in case_diff(run, prefix)["violations"]["baseline-llm"]
        )


def test_blanket_abstention_is_not_best_strategy() -> None:
    run = experiment("baseline-cautious", "rag-insufficiency-aware")
    abstention = run.comparison(ABSTENTION_ACCURACY)
    assert (
        abstention.value_for("baseline-llm").value
        < abstention.value_for("vera-rap").value
    )
    assert "FALSE_ABSTENTION" in case_diff(run, "A")["violations"]["baseline-llm"]
    assert run.comparison(EPISTEMIC_ADMISSIBILITY).rank_order[-1] == "baseline-llm"
    assert (
        run.comparison(UNSUPPORTED_CLAIM_RATE).value_for("baseline-llm").availability
        is MetricAvailability.NOT_APPLICABLE
    )


def test_missing_trace_is_not_confused_with_zero_score() -> None:
    run = experiment("baseline-recency", "rag-insufficiency-aware")
    trace = run.comparison(TRACE_REPRODUCIBILITY)
    for system_id in ("baseline-llm", "rag-llm"):
        value = trace.value_for(system_id)
        assert (
            value.availability is MetricAvailability.NOT_AVAILABLE
            and value.value is None
            and value.passed is None
        )
    assert trace.value_for("vera-rap").value == 1.0 and trace.rank_order == (
        "vera-rap",
    )
    assert set(trace.details["unavailable_system_ids"]) == {"baseline-llm", "rag-llm"}
    assert (
        run.comparison("replanning_efficiency").value_for("baseline-llm").availability
        is MetricAvailability.NOT_AVAILABLE
    )


def test_offline_e1_is_deterministic() -> None:
    first = experiment("baseline-confident", "rag-insufficiency-aware")
    second = experiment("baseline-confident", "rag-insufficiency-aware")
    assert first.fingerprint == second.fingerprint
    for item in first.system_runs:
        assert item.determinism_summary.identical_case_output_rate["rate"] == 1.0
        assert (
            item.determinism_summary.identical_benchmark_fingerprint_rate["rate"] == 1.0
        )
    restored = E1RunResult.from_canonical_json(first.canonical_json())
    assert restored.fingerprint == first.fingerprint
    manifest = build_e1_manifest(
        build_e1_config(PAIRS, CONFIGS, evaluation_timestamp=AT), created_at=AT
    )
    report = build_comparison_report(first, manifest)
    assert report.primary_metric_summary["metric_name"] == UNSUPPORTED_CLAIM_RATE
    assert any("OFFLINE FIXTURE PILOT" in x for x in report.limitations)
    assert len(report.case_level_differences) == 12


class ExplodingSystem:
    system_id = "baseline-llm"
    system_version = "fixture-1"
    system_family = SystemFamily.BASELINE_LLM

    def evaluate_case(self, case):
        raise RuntimeError("provider unavailable")


def test_one_system_failure_does_not_abort_experiment() -> None:
    systems = build_default_systems(
        CONFIGS,
        baseline_generator=GENERATORS["baseline-confident"],
        rag_generator=GENERATORS["rag-insufficiency-aware"],
        retrieved_at=AT,
    )
    systems = (ExplodingSystem(), *systems[1:])
    run = experiment(
        "baseline-confident",
        "rag-insufficiency-aware",
        pairs=(BY_PREFIX["A"], BY_PREFIX["B"]),
        systems=systems,
    )
    broken = run.system_run("baseline-llm")
    assert not broken.benchmark_run_result.case_results
    assert {x.failure_type for x in broken.case_failures} == {
        ExperimentFailureType.SYSTEM_ERROR
    }
    assert len(run.system_run("vera-rap").benchmark_run_result.case_results) == 2
    assert (
        run.comparison(UNSUPPORTED_CLAIM_RATE).value_for("baseline-llm").availability
        is MetricAvailability.NOT_APPLICABLE
    )


def test_unknown_evidence_citation_is_reported() -> None:
    generator = FixtureGenerator(
        "hallucinating",
        "1",
        {},
        {
            "conclusion": "CONCLUDE",
            "material_claims": ["C2"],
            "cited_evidence_ids": ["E1", "E-ghost"],
            "abstain": False,
            "confidence": 0.7,
        },
    )
    adapter = BaselineLLMAdapter(BASELINE_CONFIG, generator)
    run = experiment(
        "baseline-confident",
        "rag-insufficiency-aware",
        pairs=(BY_PREFIX["A"],),
        systems=(
            adapter,
            *build_default_systems(
                CONFIGS[1:],
                baseline_generator=generator,
                rag_generator=GENERATORS["rag-insufficiency-aware"],
                retrieved_at=AT,
            ),
        ),
    )
    failures = run.system_run("baseline-llm").case_failures
    citation = next(
        x for x in failures if x.failure_type is ExperimentFailureType.INVALID_CITATION
    )
    assert list(citation.details["unknown_evidence_ids"]) == ["E-ghost"]
    garbage = FixtureGenerator("garbage", "1", {}, {"answer": "The site will flood."})
    with pytest.raises(ParsingFailure) as info:
        BaselineLLMAdapter(BASELINE_CONFIG, garbage).evaluate_case(BY_PREFIX["A"].case)
    assert info.value.result.reason_code == "MISSING_REQUIRED_FIELDS"
    failed = normalize_output(
        "x",
        {
            "conclusion": "ABSTAIN",
            "material_claims": [],
            "cited_evidence_ids": [],
            "abstain": False,
        },
        system_id="s",
        system_version="1",
    )
    assert failed.reason_code == "ABSTAIN_FLAG_DISAGREES_WITH_CONCLUSION"


def test_e1_case_builder_rejects_unbalanced_missing_scenarios() -> None:
    chosen = build_e1_case_set(PAIRS, per_bucket=1)
    assert len(chosen) == 5 and case_set_balance(chosen)["balanced"]
    assert all(share == 0.2 for share in case_set_balance(chosen)["shares"].values())
    with pytest.raises(ValueError, match="needs 2 case"):
        build_e1_case_set(PAIRS, per_bucket=2)
    without_stale = tuple(
        p
        for p in PAIRS
        if p.case.scenario_type is not BenchmarkScenarioType.STALE_EVIDENCE
    )
    with pytest.raises(ValueError, match="no substitution"):
        build_e1_case_set(without_stale, per_bucket=1)


def test_comparison_exposes_absolute_metric_delta() -> None:
    run = experiment("baseline-confident", "rag-insufficiency-aware")
    ucr = run.comparison(UNSUPPORTED_CLAIM_RATE)
    delta = next(
        x
        for x in ucr.pairwise_deltas
        if x.system_a == "baseline-llm" and x.system_b == "vera-rap"
    )
    assert delta.absolute_delta == pytest.approx(
        ucr.value_for("baseline-llm").value - 0.0
    )
    assert delta.absolute_delta > 0 and "vera-rap lower" in delta.direction
    assert delta.relative_improvement == pytest.approx(1.0)
    zero = next(
        x
        for x in ucr.pairwise_deltas
        if x.system_a == "vera-rap" and x.system_b == "rag-llm"
    )
    assert zero.absolute_delta == 0.0 and zero.relative_improvement is None
    assert "value(system_a) - value(system_b)" in ucr.details["delta_formula"]


def test_prompts_are_structured_and_reveal_nothing() -> None:
    case = BY_PREFIX["D"].case
    prompt = build_baseline_prompt(case)
    lowered = prompt.lower()
    assert (
        "step by step" not in lowered
        and "chain of thought" not in lowered
        and "expected" not in lowered
    )
    assert "REQUIRED_OUTPUT_SCHEMA" in prompt and all(
        key in prompt for key in RESPONSE_SCHEMA
    )
    assert "E4" in prompt and "2026-02-15" in prompt
    corpus = build_corpus_from_case(case)
    context = KeywordOverlapRetriever(top_k=2, retrieved_at=AT).retrieve(
        case_id=case.case_id, query="water_level site-1", corpus=corpus
    )
    assert (
        len(context.documents) == 2
        and context.fingerprint
        == KeywordOverlapRetriever(top_k=2, retrieved_at=AT)
        .retrieve(case_id=case.case_id, query="water_level site-1", corpus=corpus)
        .fingerprint
    )
    rag_prompt = build_rag_prompt(case, context)
    assert (
        "RETRIEVED_CONTEXT" in rag_prompt
        and context.documents[0].fingerprint in rag_prompt
    )
    adapter = RAGLLMAdapter(
        RAG_CONFIG,
        KeywordOverlapRetriever(retrieved_at=AT),
        GENERATORS["rag-insufficiency-aware"],
    )
    result = adapter.evaluate_case(case)
    assert (
        result.claimed_outcome is SystemOutcome.CONTRADICTION_PENDING
        and result.trace is None
    )
    assert (
        VeraRapExperimentSystem(VERA_CONFIG).evaluate_case(case).system_id == "vera-rap"
    )
    payload = json.loads(
        SystemConfig("s", "1", SystemFamily.RAG_LLM, "a", "1").canonical_json()
    )
    payload["system_family"] = "GPT"
    with pytest.raises(ValueError):
        SystemConfig.from_dict(payload)
