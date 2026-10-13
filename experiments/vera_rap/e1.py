"""Experiment E1 case-set construction, configuration, and manifest (RAP-011)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from benchmarks.vera_rap import (
    BENCHMARK_VERSION,
    METRIC_NAMES,
    BenchmarkCasePair,
    BenchmarkScenarioType,
    build_manifest,
)

from .adapters import (
    PROMPT_TEMPLATE_VERSION,
    BaselineLLMAdapter,
    ExperimentSystem,
    FixtureGenerator,
    KeywordOverlapRetriever,
    RAGLLMAdapter,
    Retriever,
    StructuredGenerator,
    VeraRapExperimentSystem,
)
from .models import (
    EXPERIMENT_NAME,
    EXPERIMENT_VERSION,
    E1ExperimentConfig,
    E1ExperimentManifest,
    SystemConfig,
    SystemFamily,
)

# Planned E1 mix: five equal buckets of 20% each.
E1_MIX: Mapping[str, tuple[BenchmarkScenarioType, ...]] = {
    "missing_evidence": (BenchmarkScenarioType.MISSING_EVIDENCE,),
    "stale_evidence": (BenchmarkScenarioType.STALE_EVIDENCE,),
    "contradictory_evidence": (BenchmarkScenarioType.CONFLICTING_EVIDENCE,),
    "valid_evidence": (BenchmarkScenarioType.VALID_EVIDENCE_COMPLETE,),
    "invalid_or_corrupted_evidence": (
        BenchmarkScenarioType.INVALID_TRANSFORMATION,
        BenchmarkScenarioType.CORRUPTED_SOURCE,
    ),
}
E1_TARGET_SHARE = 0.2


def case_set_balance(
    pairs: Sequence[BenchmarkCasePair],
    mix: Mapping[str, tuple[BenchmarkScenarioType, ...]] = E1_MIX,
) -> dict[str, Any]:
    counts = {
        bucket: sum(1 for pair in pairs if pair.case.scenario_type in types)
        for bucket, types in mix.items()
    }
    total = sum(counts.values())
    return {
        "counts": counts,
        "shares": {
            bucket: (None if total == 0 else count / total)
            for bucket, count in counts.items()
        },
        "total": total,
        "balanced": total > 0 and len(set(counts.values())) == 1,
    }


def build_e1_case_set(
    pairs: Sequence[BenchmarkCasePair],
    *,
    per_bucket: int,
    mix: Mapping[str, tuple[BenchmarkScenarioType, ...]] = E1_MIX,
) -> tuple[BenchmarkCasePair, ...]:
    """Select `per_bucket` cases per E1 bucket, deterministically, or fail loudly."""
    if (
        isinstance(per_bucket, bool)
        or not isinstance(per_bucket, int)
        or per_bucket < 1
    ):
        raise ValueError("per_bucket must be a positive integer")
    selected: list[BenchmarkCasePair] = []
    for bucket, types in mix.items():
        candidates = sorted(
            (pair for pair in pairs if pair.case.scenario_type in types),
            key=lambda x: x.case.case_id,
        )
        if len(candidates) < per_bucket:
            raise ValueError(
                f"E1 bucket {bucket} needs {per_bucket} case(s) but only {len(candidates)} available; "
                "no substitution is performed"
            )
        selected.extend(candidates[:per_bucket])
    chosen = tuple(sorted(selected, key=lambda x: x.case.case_id))
    balance = case_set_balance(chosen, mix)
    if not balance["balanced"]:
        raise ValueError("E1 case set is not balanced across buckets")
    return chosen


def default_system_configs(
    *, retriever_id: str = "keyword-overlap"
) -> tuple[SystemConfig, SystemConfig, SystemConfig]:
    return (
        SystemConfig(
            "baseline-llm",
            "fixture-1",
            SystemFamily.BASELINE_LLM,
            "baseline-llm-adapter",
            "1",
            "fixture-generator",
            None,
            PROMPT_TEMPLATE_VERSION,
        ),
        SystemConfig(
            "rag-llm",
            "fixture-1",
            SystemFamily.RAG_LLM,
            "rag-llm-adapter",
            "1",
            "fixture-generator",
            retriever_id,
            PROMPT_TEMPLATE_VERSION,
        ),
        SystemConfig(
            "vera-rap",
            "rap-001..010",
            SystemFamily.VERA_RAP,
            "vera-rap-experiment-adapter",
            "1",
            None,
            None,
            None,
        ),
    )


def build_e1_config(
    pairs: Sequence[BenchmarkCasePair],
    system_configs: Sequence[SystemConfig],
    *,
    evaluation_timestamp: datetime,
    repetitions: int = 2,
    experiment_id: str = "e1-deterministic-pilot",
    random_seed: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> E1ExperimentConfig:
    manifest = build_manifest([x.case for x in pairs], created_at=evaluation_timestamp)
    return E1ExperimentConfig(
        experiment_id,
        EXPERIMENT_VERSION,
        manifest.fingerprint,
        tuple(system_configs),
        tuple(x.case.case_id for x in pairs),
        repetitions,
        evaluation_timestamp,
        random_seed,
        {"case_set_balance": case_set_balance(pairs), **dict(metadata or {})},
    )


def build_e1_manifest(
    config: E1ExperimentConfig,
    *,
    created_at: datetime,
    metadata: Mapping[str, Any] | None = None,
) -> E1ExperimentManifest:
    return E1ExperimentManifest(
        EXPERIMENT_NAME,
        config.experiment_version,
        BENCHMARK_VERSION,
        config.benchmark_manifest_fingerprint,
        config.system_configs,
        config.case_ids,
        METRIC_NAMES,
        created_at,
        {
            "experiment_id": config.experiment_id,
            "config_fingerprint": config.fingerprint,
            **dict(metadata or {}),
        },
    )


def build_default_systems(
    configs: Sequence[SystemConfig],
    *,
    baseline_generator: StructuredGenerator,
    rag_generator: StructuredGenerator,
    retriever: Retriever | None = None,
    retrieved_at: datetime,
) -> tuple[ExperimentSystem, ...]:
    """Instantiate one adapter per config family with injected generators."""
    by_family = {config.system_family: config for config in configs}
    systems: list[ExperimentSystem] = []
    if SystemFamily.BASELINE_LLM in by_family:
        systems.append(
            BaselineLLMAdapter(by_family[SystemFamily.BASELINE_LLM], baseline_generator)
        )
    if SystemFamily.RAG_LLM in by_family:
        systems.append(
            RAGLLMAdapter(
                by_family[SystemFamily.RAG_LLM],
                retriever or KeywordOverlapRetriever(retrieved_at=retrieved_at),
                rag_generator,
            )
        )
    if SystemFamily.VERA_RAP in by_family:
        systems.append(VeraRapExperimentSystem(by_family[SystemFamily.VERA_RAP]))
    return tuple(systems)


__all__ = [
    "E1_MIX",
    "E1_TARGET_SHARE",
    "FixtureGenerator",
    "build_default_systems",
    "build_e1_case_set",
    "build_e1_config",
    "build_e1_manifest",
    "case_set_balance",
    "default_system_configs",
]
