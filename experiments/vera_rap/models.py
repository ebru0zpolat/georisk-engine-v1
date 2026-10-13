"""Experiment E1 data models (RAP-011).

Immutable, strictly serialized, fingerprint-bound records for system
configurations, baseline outputs, retrieval artifacts, determinism summaries,
metric comparisons, experiment runs, and manifests. Scoring stays behaviour
based: a baseline is never penalized for lacking VERA-RAP internals, only for
observable epistemic violations.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any

from app.research.vera_rap.evidence import (
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)
from benchmarks.vera_rap import (
    BenchmarkRunResult,
    ExpectedPermission,
    SystemCaseResult,
    SystemOutcome,
)
from benchmarks.vera_rap.models import WITHHOLDING_OUTCOMES

EXPERIMENT_NAME = "VERA-RAP Experiment E1"
EXPERIMENT_VERSION = "0.1.0"
SCHEMA_VERSION = "vera-rap-e1/1"


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as boolean")


class SystemFamily(_StrictEnum):
    BASELINE_LLM = "BASELINE_LLM"
    RAG_LLM = "RAG_LLM"
    VERA_RAP = "VERA_RAP"


class MetricAvailability(_StrictEnum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExperimentFailureType(_StrictEnum):
    PARSING_FAILURE = "PARSING_FAILURE"
    INVALID_CITATION = "INVALID_CITATION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    CONSTRAINT_BYPASS = "CONSTRAINT_BYPASS"
    CONTRADICTION_BYPASS = "CONTRADICTION_BYPASS"
    STALE_EVIDENCE_USE = "STALE_EVIDENCE_USE"
    UNCERTAINTY_BYPASS = "UNCERTAINTY_BYPASS"
    INVALID_TRANSFORMATION_USE = "INVALID_TRANSFORMATION_USE"
    NONDETERMINISTIC_OUTPUT = "NONDETERMINISTIC_OUTPUT"
    SYSTEM_ERROR = "SYSTEM_ERROR"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strings(value: object, name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")
    result = tuple(value)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    for item in result:
        _required_text(item, f"{name} item")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} contains duplicates")
    return tuple(sorted(result))


def _finite(value: object, name: str, *, optional: bool = False) -> float | None:
    if value is None and optional:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _count(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _data(value: object, name: str, *, optional: bool) -> Any:
    frozen = _freeze_json(value, name)
    if frozen is None:
        if optional:
            return None
        raise ValueError(f"{name} must be an object")
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{name} must be an object")
    return frozen


def _load(serialized: str) -> Any:
    if not isinstance(serialized, str):
        raise ValueError("serialized payload must be text")
    try:
        return json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("serialized payload must be valid JSON") from exc


def _expect(cls: type, value: object, label: str) -> dict[str, Any]:
    expected = {item.name for item in fields(cls)}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{label} fields do not match the canonical schema")
    return dict(value)


def _text_or_none(value: object, name: str) -> str | None:
    if value is None:
        return None
    _required_text(value, name)
    return value  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# System configuration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SystemConfig:
    system_id: str
    system_version: str
    system_family: SystemFamily
    adapter_id: str
    adapter_version: str
    model_name: str | None = None
    retriever_id: str | None = None
    prompt_template_version: str | None = None
    metadata: Mapping[str, Any] | None = None
    case_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        for name in ("system_id", "system_version", "adapter_id", "adapter_version"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.system_family, SystemFamily):
            raise ValueError("system_family must be a SystemFamily")
        for name in ("model_name", "retriever_id", "prompt_template_version"):
            _text_or_none(getattr(self, name), name)
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        # Recorded for future live providers; nothing in RAP-011 enforces it.
        object.__setattr__(
            self,
            "case_timeout_seconds",
            _finite(self.case_timeout_seconds, "case_timeout_seconds", optional=True),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "system_version": self.system_version,
            "system_family": self.system_family.value,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_name": self.model_name,
            "retriever_id": self.retriever_id,
            "prompt_template_version": self.prompt_template_version,
            "metadata": _plain_json(self.metadata),
            "case_timeout_seconds": self.case_timeout_seconds,
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> SystemConfig:
        payload = _expect(cls, value, "system config")
        try:
            return cls(
                **{**payload, "system_family": SystemFamily(payload["system_family"])}
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("system config payload is malformed") from exc


# --------------------------------------------------------------------------- #
# Baseline output normalization
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class BaselineSystemOutput:
    """Structured, observable output of a baseline; raw text is audit-only."""

    case_id: str
    claimed_outcome: SystemOutcome
    material_claims: tuple[str, ...]
    abstained: bool
    cited_evidence_ids: tuple[str, ...]
    provenance_refs: Mapping[str, Any]
    reported_blockers: tuple[str, ...]
    reported_contradictions: Mapping[str, Any]
    reported_uncertainty: Mapping[str, Any]
    reported_constraints: Mapping[str, Any]
    proposed_actions: tuple[str, ...]
    metadata: Mapping[str, Any] | None = None
    raw_response: str | None = None
    initial_outcome: SystemOutcome | None = None

    def __post_init__(self) -> None:
        _required_text(self.case_id, "case_id")
        if not isinstance(self.claimed_outcome, SystemOutcome):
            raise ValueError("claimed_outcome must be a SystemOutcome")
        if self.initial_outcome is not None and not isinstance(
            self.initial_outcome, SystemOutcome
        ):
            raise ValueError("initial_outcome must be a SystemOutcome or null")
        if not isinstance(self.abstained, bool):
            raise ValueError("abstained must be boolean")
        if self.abstained is not (self.claimed_outcome is SystemOutcome.ABSTAINED):
            raise ValueError("abstained flag disagrees with claimed_outcome")
        for name in (
            "material_claims",
            "cited_evidence_ids",
            "reported_blockers",
            "proposed_actions",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if self.claimed_outcome in WITHHOLDING_OUTCOMES and self.material_claims:
            raise ValueError("a withholding outcome cannot carry material claims")
        for name in (
            "provenance_refs",
            "reported_contradictions",
            "reported_uncertainty",
            "reported_constraints",
        ):
            object.__setattr__(
                self, name, _data(getattr(self, name), name, optional=False)
            )
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        if self.raw_response is not None and not isinstance(self.raw_response, str):
            raise ValueError("raw_response must be text or null")

    def to_system_case_result(
        self, system_id: str, system_version: str
    ) -> SystemCaseResult:
        """Project onto the RAP-010 result shape without inventing artifacts."""
        return SystemCaseResult(
            self.case_id,
            system_id,
            system_version,
            self.claimed_outcome,
            self.material_claims,
            {},
            {},
            self.abstained,
            (),
            (),
            None,
            {
                "proposed_actions": list(self.proposed_actions),
                **dict(self.metadata or {}),
            },
            {claim: list(self.cited_evidence_ids) for claim in self.material_claims},
            self.provenance_refs,
            self.reported_contradictions,
            self.reported_uncertainty,
            self.reported_constraints,
            (),
            self.reported_blockers,
            (),
            self.initial_outcome,
        )

    @property
    def raw_response_sha256(self) -> str | None:
        return None if self.raw_response is None else _sha(self.raw_response)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "claimed_outcome": self.claimed_outcome.value,
            "material_claims": list(self.material_claims),
            "abstained": self.abstained,
            "cited_evidence_ids": list(self.cited_evidence_ids),
            "provenance_refs": _plain_json(self.provenance_refs),
            "reported_blockers": list(self.reported_blockers),
            "reported_contradictions": _plain_json(self.reported_contradictions),
            "reported_uncertainty": _plain_json(self.reported_uncertainty),
            "reported_constraints": _plain_json(self.reported_constraints),
            "proposed_actions": list(self.proposed_actions),
            "metadata": _plain_json(self.metadata),
            "raw_response": self.raw_response,
            "initial_outcome": (
                None if self.initial_outcome is None else self.initial_outcome.value
            ),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    def audit_dict(self) -> dict[str, Any]:
        """Fingerprint-safe view: raw text replaced by its SHA-256 hash."""
        return {
            **self.canonical_dict(),
            "raw_response": None,
            "raw_response_sha256": self.raw_response_sha256,
        }

    @classmethod
    def from_dict(cls, value: object) -> BaselineSystemOutput:
        payload = _expect(cls, value, "baseline system output")
        try:
            return cls(
                **{
                    **{
                        k: (tuple(v) if isinstance(v, list) else v)
                        for k, v in payload.items()
                    },
                    "claimed_outcome": SystemOutcome(payload["claimed_outcome"]),
                    "initial_outcome": (
                        None
                        if payload["initial_outcome"] is None
                        else SystemOutcome(payload["initial_outcome"])
                    ),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("baseline system output payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class ParsingFailureResult:
    """A response that could not be structurally normalized; not an abstention."""

    case_id: str
    system_id: str
    system_version: str
    reason_code: str
    raw_response: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("case_id", "system_id", "system_version", "reason_code"):
            _required_text(getattr(self, name), name)
        if self.raw_response is not None and not isinstance(self.raw_response, str):
            raise ValueError("raw_response must be text or null")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "system_id": self.system_id,
            "system_version": self.system_version,
            "reason_code": self.reason_code,
            "raw_response": self.raw_response,
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> ParsingFailureResult:
        payload = _expect(cls, value, "parsing failure result")
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError("parsing failure payload is malformed") from exc


class ParsingFailure(ValueError):
    """Raised by adapters when a response cannot be normalized."""

    def __init__(self, result: ParsingFailureResult) -> None:
        super().__init__(f"{result.case_id}: {result.reason_code}")
        self.result = result


# --------------------------------------------------------------------------- #
# Retrieval artifacts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    document_id: str
    source_id: str
    content: Mapping[str, Any]
    retrieved_at: datetime
    observed_at: datetime | None = None
    valid_until: datetime | None = None
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("document_id", "source_id"):
            _required_text(getattr(self, name), name)
        object.__setattr__(
            self, "content", _data(self.content, "content", optional=False)
        )
        _timestamp(self.retrieved_at, "retrieved_at")
        for name in ("observed_at", "valid_until"):
            if getattr(self, name) is not None:
                _timestamp(getattr(self, name), name)
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "content": _plain_json(self.content),
            "retrieved_at": _iso(self.retrieved_at),
            "observed_at": _iso(self.observed_at),
            "valid_until": _iso(self.valid_until),
            "metadata": _plain_json(self.metadata),
        }

    @property
    def text(self) -> str:
        return _canonical(
            _plain_json(self.content)
            if isinstance(self.content, Mapping)
            else {"value": self.content}
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    @classmethod
    def from_dict(cls, value: object) -> RetrievalDocument:
        payload = _expect(cls, value, "retrieval document")
        try:
            result = cls(
                payload["document_id"],
                payload["source_id"],
                payload["content"],
                _parse_timestamp(payload["retrieved_at"], "retrieved_at"),
                _parse_timestamp(payload["observed_at"], "observed_at", optional=True),
                _parse_timestamp(payload["valid_until"], "valid_until", optional=True),
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("retrieval document payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("document fingerprint does not match content")
        return result


@dataclass(frozen=True, slots=True)
class RetrievalCorpus:
    corpus_id: str
    documents: tuple[RetrievalDocument, ...]
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _required_text(self.corpus_id, "corpus_id")
        documents = tuple(sorted(self.documents, key=lambda x: x.document_id))
        if any(not isinstance(x, RetrievalDocument) for x in documents):
            raise ValueError("documents must contain RetrievalDocument objects")
        if len({x.document_id for x in documents}) != len(documents):
            raise ValueError("duplicate document ID in corpus")
        object.__setattr__(self, "documents", documents)
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "documents": [x.canonical_dict() for x in self.documents],
            "metadata": _plain_json(self.metadata),
        }

    @property
    def fingerprint(self) -> str:
        return _sha(_canonical(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    query: str
    documents: tuple[RetrievalDocument, ...]
    retriever_id: str
    retriever_version: str
    retrieved_at: datetime
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("query", "retriever_id", "retriever_version"):
            _required_text(getattr(self, name), name)
        documents = tuple(self.documents)
        if any(not isinstance(x, RetrievalDocument) for x in documents):
            raise ValueError("documents must contain RetrievalDocument objects")
        if len({x.document_id for x in documents}) != len(documents):
            raise ValueError("duplicate document ID in retrieved context")
        object.__setattr__(self, "documents", documents)
        _timestamp(self.retrieved_at, "retrieved_at")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "documents": [x.canonical_dict() for x in self.documents],
            "retriever_id": self.retriever_id,
            "retriever_version": self.retriever_version,
            "retrieved_at": _iso(self.retrieved_at),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())


# --------------------------------------------------------------------------- #
# Experiment configuration, results, comparisons
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class E1ExperimentConfig:
    experiment_id: str
    experiment_version: str
    benchmark_manifest_fingerprint: str
    system_configs: tuple[SystemConfig, ...]
    case_ids: tuple[str, ...]
    repetitions: int
    evaluation_timestamp: datetime
    random_seed: int | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "experiment_id",
            "experiment_version",
            "benchmark_manifest_fingerprint",
        ):
            _required_text(getattr(self, name), name)
        configs = tuple(sorted(self.system_configs, key=lambda x: x.system_id))
        if not configs or any(not isinstance(x, SystemConfig) for x in configs):
            raise ValueError("system_configs must contain at least one SystemConfig")
        if len({x.system_id for x in configs}) != len(configs):
            raise ValueError("duplicate system ID in experiment config")
        object.__setattr__(self, "system_configs", configs)
        object.__setattr__(
            self, "case_ids", _strings(self.case_ids, "case_ids", allow_empty=False)
        )
        _count(self.repetitions, "repetitions", minimum=1)
        _timestamp(self.evaluation_timestamp, "evaluation_timestamp")
        if self.random_seed is not None:
            _count(self.random_seed, "random_seed")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "experiment_version": self.experiment_version,
            "benchmark_manifest_fingerprint": self.benchmark_manifest_fingerprint,
            "system_configs": [x.canonical_dict() for x in self.system_configs],
            "case_ids": list(self.case_ids),
            "repetitions": self.repetitions,
            "evaluation_timestamp": _iso(self.evaluation_timestamp),
            "random_seed": self.random_seed,
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> E1ExperimentConfig:
        payload = _expect(cls, value, "experiment config")
        try:
            return cls(
                payload["experiment_id"],
                payload["experiment_version"],
                payload["benchmark_manifest_fingerprint"],
                tuple(SystemConfig.from_dict(x) for x in payload["system_configs"]),
                tuple(payload["case_ids"]),
                payload["repetitions"],
                _parse_timestamp(
                    payload["evaluation_timestamp"], "evaluation_timestamp"
                ),
                payload["random_seed"],
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("experiment config payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class DeterminismSummary:
    repetitions: int
    scored_case_ids: tuple[str, ...]
    identical_case_output_rate: Mapping[str, Any]
    identical_benchmark_fingerprint_rate: Mapping[str, Any]
    case_output_fingerprints: Mapping[str, Any]
    run_fingerprints: tuple[str, ...]
    parsing_failure_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _count(self.repetitions, "repetitions", minimum=1)
        object.__setattr__(
            self, "scored_case_ids", _strings(self.scored_case_ids, "scored_case_ids")
        )
        object.__setattr__(
            self,
            "parsing_failure_case_ids",
            _strings(self.parsing_failure_case_ids, "parsing_failure_case_ids"),
        )
        for name in (
            "identical_case_output_rate",
            "identical_benchmark_fingerprint_rate",
            "case_output_fingerprints",
        ):
            object.__setattr__(
                self, name, _data(getattr(self, name), name, optional=False)
            )
        object.__setattr__(self, "run_fingerprints", tuple(self.run_fingerprints))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "repetitions": self.repetitions,
            "scored_case_ids": list(self.scored_case_ids),
            "identical_case_output_rate": _plain_json(self.identical_case_output_rate),
            "identical_benchmark_fingerprint_rate": _plain_json(
                self.identical_benchmark_fingerprint_rate
            ),
            "case_output_fingerprints": _plain_json(self.case_output_fingerprints),
            "run_fingerprints": list(self.run_fingerprints),
            "parsing_failure_case_ids": list(self.parsing_failure_case_ids),
        }

    @classmethod
    def from_dict(cls, value: object) -> DeterminismSummary:
        payload = _expect(cls, value, "determinism summary")
        try:
            return cls(
                **{
                    k: (tuple(v) if isinstance(v, list) else v)
                    for k, v in payload.items()
                }
            )
        except TypeError as exc:
            raise ValueError("determinism summary payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class SystemExperimentResult:
    system_config: SystemConfig
    benchmark_run_result: BenchmarkRunResult
    repetition_runs: tuple[BenchmarkRunResult, ...]
    raw_case_outputs: tuple[Mapping[str, Any], ...]
    parsing_failures: tuple[ParsingFailureResult, ...]
    determinism_summary: DeterminismSummary
    case_failures: tuple[ExperimentCaseFailure, ...] = ()
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        failures = tuple(
            sorted(
                self.case_failures,
                key=lambda x: (x.case_id, x.failure_type.value, x.reason),
            )
        )
        if any(not isinstance(x, ExperimentCaseFailure) for x in failures):
            raise ValueError("case_failures must contain ExperimentCaseFailure objects")
        object.__setattr__(self, "case_failures", failures)
        if not isinstance(self.system_config, SystemConfig) or not isinstance(
            self.benchmark_run_result, BenchmarkRunResult
        ):
            raise ValueError("system experiment result has invalid typed fields")
        runs = tuple(self.repetition_runs)
        if not runs or any(not isinstance(x, BenchmarkRunResult) for x in runs):
            raise ValueError("repetition_runs must contain BenchmarkRunResult objects")
        if runs[0].fingerprint != self.benchmark_run_result.fingerprint:
            raise ValueError("benchmark_run_result must be the first repetition")
        object.__setattr__(self, "repetition_runs", runs)
        object.__setattr__(
            self,
            "raw_case_outputs",
            tuple(
                _data(x, "raw_case_outputs item", optional=False)
                for x in self.raw_case_outputs
            ),
        )
        failures = tuple(
            sorted(self.parsing_failures, key=lambda x: (x.case_id, x.fingerprint))
        )
        if any(not isinstance(x, ParsingFailureResult) for x in failures):
            raise ValueError(
                "parsing_failures must contain ParsingFailureResult objects"
            )
        object.__setattr__(self, "parsing_failures", failures)
        if not isinstance(self.determinism_summary, DeterminismSummary):
            raise ValueError("determinism_summary must be a DeterminismSummary")
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "system_config": self.system_config.canonical_dict(),
            "benchmark_run_result": self.benchmark_run_result.canonical_dict(),
            "repetition_runs": [x.canonical_dict() for x in self.repetition_runs],
            "raw_case_outputs": [_plain_json(x) for x in self.raw_case_outputs],
            "parsing_failures": [x.canonical_dict() for x in self.parsing_failures],
            "determinism_summary": self.determinism_summary.canonical_dict(),
            "case_failures": [x.canonical_dict() for x in self.case_failures],
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    @classmethod
    def from_dict(cls, value: object) -> SystemExperimentResult:
        payload = _expect(cls, value, "system experiment result")
        try:
            result = cls(
                SystemConfig.from_dict(payload["system_config"]),
                BenchmarkRunResult.from_dict(payload["benchmark_run_result"]),
                tuple(
                    BenchmarkRunResult.from_dict(x) for x in payload["repetition_runs"]
                ),
                tuple(payload["raw_case_outputs"]),
                tuple(
                    ParsingFailureResult.from_dict(x)
                    for x in payload["parsing_failures"]
                ),
                DeterminismSummary.from_dict(payload["determinism_summary"]),
                tuple(
                    ExperimentCaseFailure.from_dict(x) for x in payload["case_failures"]
                ),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("system experiment result payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError(
                "system experiment result fingerprint does not match content"
            )
        return result


@dataclass(frozen=True, slots=True)
class MetricSystemValue:
    system_id: str
    availability: MetricAvailability
    value: float | None
    numerator: int
    denominator: int
    passed: bool | None
    note: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.system_id, "system_id")
        if not isinstance(self.availability, MetricAvailability):
            raise ValueError("availability must be a MetricAvailability")
        object.__setattr__(self, "value", _finite(self.value, "value", optional=True))
        _count(self.numerator, "numerator")
        _count(self.denominator, "denominator")
        if (
            self.availability is not MetricAvailability.AVAILABLE
            and self.value is not None
        ):
            raise ValueError("unavailable or inapplicable metrics carry no value")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise ValueError("passed must be boolean or null")
        _text_or_none(self.note, "note")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "availability": self.availability.value,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "passed": self.passed,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, value: object) -> MetricSystemValue:
        payload = _expect(cls, value, "metric system value")
        try:
            return cls(
                **{
                    **payload,
                    "availability": MetricAvailability(payload["availability"]),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("metric system value payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class PairwiseDelta:
    system_a: str
    system_b: str
    absolute_delta: float
    relative_improvement: float | None
    direction: str

    def __post_init__(self) -> None:
        for name in ("system_a", "system_b", "direction"):
            _required_text(getattr(self, name), name)
        object.__setattr__(
            self, "absolute_delta", _finite(self.absolute_delta, "absolute_delta")
        )
        object.__setattr__(
            self,
            "relative_improvement",
            _finite(self.relative_improvement, "relative_improvement", optional=True),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "system_a": self.system_a,
            "system_b": self.system_b,
            "absolute_delta": self.absolute_delta,
            "relative_improvement": self.relative_improvement,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, value: object) -> PairwiseDelta:
        payload = _expect(cls, value, "pairwise delta")
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError("pairwise delta payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    metric_name: str
    lower_is_better: bool
    primary: bool
    system_values: tuple[MetricSystemValue, ...]
    rank_order: tuple[str, ...]
    best_system_ids: tuple[str, ...]
    ties: tuple[tuple[str, ...], ...]
    pairwise_deltas: tuple[PairwiseDelta, ...]
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        _required_text(self.metric_name, "metric_name")
        if not isinstance(self.lower_is_better, bool) or not isinstance(
            self.primary, bool
        ):
            raise ValueError("lower_is_better and primary must be boolean")
        values = tuple(sorted(self.system_values, key=lambda x: x.system_id))
        if any(not isinstance(x, MetricSystemValue) for x in values) or len(
            {x.system_id for x in values}
        ) != len(values):
            raise ValueError("system_values must be unique MetricSystemValue objects")
        object.__setattr__(self, "system_values", values)
        object.__setattr__(self, "rank_order", tuple(self.rank_order))
        object.__setattr__(
            self, "best_system_ids", _strings(self.best_system_ids, "best_system_ids")
        )
        object.__setattr__(self, "ties", tuple(tuple(sorted(x)) for x in self.ties))
        deltas = tuple(self.pairwise_deltas)
        if any(not isinstance(x, PairwiseDelta) for x in deltas):
            raise ValueError("pairwise_deltas must contain PairwiseDelta objects")
        object.__setattr__(self, "pairwise_deltas", deltas)
        object.__setattr__(
            self, "details", _data(self.details, "details", optional=False)
        )
        known = {x.system_id for x in values}
        if not set(self.rank_order) <= known or not set(self.best_system_ids) <= known:
            raise ValueError("rank order references unknown systems")

    def value_for(self, system_id: str) -> MetricSystemValue:
        for item in self.system_values:
            if item.system_id == system_id:
                return item
        raise KeyError(system_id)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "lower_is_better": self.lower_is_better,
            "primary": self.primary,
            "system_values": [x.canonical_dict() for x in self.system_values],
            "rank_order": list(self.rank_order),
            "best_system_ids": list(self.best_system_ids),
            "ties": [list(x) for x in self.ties],
            "pairwise_deltas": [x.canonical_dict() for x in self.pairwise_deltas],
            "details": _plain_json(self.details),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> ComparisonResult:
        payload = _expect(cls, value, "comparison result")
        try:
            return cls(
                payload["metric_name"],
                payload["lower_is_better"],
                payload["primary"],
                tuple(MetricSystemValue.from_dict(x) for x in payload["system_values"]),
                tuple(payload["rank_order"]),
                tuple(payload["best_system_ids"]),
                tuple(tuple(x) for x in payload["ties"]),
                tuple(PairwiseDelta.from_dict(x) for x in payload["pairwise_deltas"]),
                payload["details"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("comparison result payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class E1RunResult:
    experiment_id: str
    experiment_version: str
    benchmark_manifest_fingerprint: str
    config_fingerprint: str
    system_runs: tuple[SystemExperimentResult, ...]
    comparisons: tuple[ComparisonResult, ...]
    started_at: datetime
    completed_at: datetime
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "experiment_id",
            "experiment_version",
            "benchmark_manifest_fingerprint",
            "config_fingerprint",
        ):
            _required_text(getattr(self, name), name)
        runs = tuple(sorted(self.system_runs, key=lambda x: x.system_config.system_id))
        if not runs or any(not isinstance(x, SystemExperimentResult) for x in runs):
            raise ValueError("system_runs must contain SystemExperimentResult objects")
        object.__setattr__(self, "system_runs", runs)
        comparisons = tuple(sorted(self.comparisons, key=lambda x: x.metric_name))
        if any(not isinstance(x, ComparisonResult) for x in comparisons):
            raise ValueError("comparisons must contain ComparisonResult objects")
        if len({x.metric_name for x in comparisons}) != len(comparisons):
            raise ValueError("duplicate comparison metric")
        object.__setattr__(self, "comparisons", comparisons)
        _timestamp(self.started_at, "started_at")
        _timestamp(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "experiment_version": self.experiment_version,
            "benchmark_manifest_fingerprint": self.benchmark_manifest_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "system_runs": [x.canonical_dict() for x in self.system_runs],
            "comparisons": [x.canonical_dict() for x in self.comparisons],
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "metadata": _plain_json(self.metadata),
        }

    def comparison(self, metric_name: str) -> ComparisonResult:
        for item in self.comparisons:
            if item.metric_name == metric_name:
                return item
        raise KeyError(metric_name)

    def system_run(self, system_id: str) -> SystemExperimentResult:
        for item in self.system_runs:
            if item.system_config.system_id == system_id:
                return item
        raise KeyError(system_id)

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> E1RunResult:
        payload = _expect(cls, value, "E1 run result")
        try:
            result = cls(
                payload["experiment_id"],
                payload["experiment_version"],
                payload["benchmark_manifest_fingerprint"],
                payload["config_fingerprint"],
                tuple(
                    SystemExperimentResult.from_dict(x) for x in payload["system_runs"]
                ),
                tuple(ComparisonResult.from_dict(x) for x in payload["comparisons"]),
                _parse_timestamp(payload["started_at"], "started_at"),
                _parse_timestamp(payload["completed_at"], "completed_at"),
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("E1 run result payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("E1 run fingerprint does not match content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> E1RunResult:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class E1ExperimentManifest:
    experiment_name: str
    version: str
    benchmark_version: str
    benchmark_manifest_fingerprint: str
    systems: tuple[SystemConfig, ...]
    case_ids: tuple[str, ...]
    metrics: tuple[str, ...]
    created_at: datetime
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "experiment_name",
            "version",
            "benchmark_version",
            "benchmark_manifest_fingerprint",
        ):
            _required_text(getattr(self, name), name)
        systems = tuple(sorted(self.systems, key=lambda x: x.system_id))
        if not systems or any(not isinstance(x, SystemConfig) for x in systems):
            raise ValueError("systems must contain SystemConfig objects")
        object.__setattr__(self, "systems", systems)
        object.__setattr__(
            self, "case_ids", _strings(self.case_ids, "case_ids", allow_empty=False)
        )
        object.__setattr__(
            self, "metrics", _strings(self.metrics, "metrics", allow_empty=False)
        )
        _timestamp(self.created_at, "created_at")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "version": self.version,
            "benchmark_version": self.benchmark_version,
            "benchmark_manifest_fingerprint": self.benchmark_manifest_fingerprint,
            "systems": [x.canonical_dict() for x in self.systems],
            "case_ids": list(self.case_ids),
            "metrics": list(self.metrics),
            "created_at": _iso(self.created_at),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> E1ExperimentManifest:
        payload = _expect(cls, value, "E1 manifest")
        try:
            result = cls(
                payload["experiment_name"],
                payload["version"],
                payload["benchmark_version"],
                payload["benchmark_manifest_fingerprint"],
                tuple(SystemConfig.from_dict(x) for x in payload["systems"]),
                tuple(payload["case_ids"]),
                tuple(payload["metrics"]),
                _parse_timestamp(payload["created_at"], "created_at"),
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("E1 manifest payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("E1 manifest fingerprint does not match content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> E1ExperimentManifest:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class ExperimentCaseFailure:
    """Structured record of why a system failed a case; never fabricated output."""

    case_id: str
    system_id: str
    failure_type: ExperimentFailureType
    reason: str
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("case_id", "system_id", "reason"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.failure_type, ExperimentFailureType):
            raise ValueError("failure_type must be an ExperimentFailureType")
        object.__setattr__(
            self, "details", _data(self.details, "details", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "system_id": self.system_id,
            "failure_type": self.failure_type.value,
            "reason": self.reason,
            "details": _plain_json(self.details),
        }

    @classmethod
    def from_dict(cls, value: object) -> ExperimentCaseFailure:
        payload = _expect(cls, value, "experiment case failure")
        try:
            return cls(
                **{
                    **payload,
                    "failure_type": ExperimentFailureType(payload["failure_type"]),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("experiment case failure payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class CaseComparison:
    """One case across systems: outcomes, claims, violations, UCR contribution."""

    case_id: str
    scenario_type: str
    expected_permission: ExpectedPermission
    system_outcomes: Mapping[str, Any]
    material_claims: Mapping[str, Any]
    abstained: Mapping[str, Any]
    violations: Mapping[str, Any]
    ucr_contribution: Mapping[str, Any]
    failures: tuple[ExperimentCaseFailure, ...]

    def __post_init__(self) -> None:
        for name in ("case_id", "scenario_type"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.expected_permission, ExpectedPermission):
            raise ValueError("expected_permission must be an ExpectedPermission")
        for name in (
            "system_outcomes",
            "material_claims",
            "abstained",
            "violations",
            "ucr_contribution",
        ):
            object.__setattr__(
                self, name, _data(getattr(self, name), name, optional=False)
            )
        failures = tuple(
            sorted(
                self.failures,
                key=lambda x: (x.system_id, x.failure_type.value, x.reason),
            )
        )
        if any(not isinstance(x, ExperimentCaseFailure) for x in failures):
            raise ValueError("failures must contain ExperimentCaseFailure objects")
        object.__setattr__(self, "failures", failures)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario_type": self.scenario_type,
            "expected_permission": self.expected_permission.value,
            "system_outcomes": _plain_json(self.system_outcomes),
            "material_claims": _plain_json(self.material_claims),
            "abstained": _plain_json(self.abstained),
            "violations": _plain_json(self.violations),
            "ucr_contribution": _plain_json(self.ucr_contribution),
            "failures": [x.canonical_dict() for x in self.failures],
        }

    @classmethod
    def from_dict(cls, value: object) -> CaseComparison:
        payload = _expect(cls, value, "case comparison")
        try:
            return cls(
                payload["case_id"],
                payload["scenario_type"],
                ExpectedPermission(payload["expected_permission"]),
                payload["system_outcomes"],
                payload["material_claims"],
                payload["abstained"],
                payload["violations"],
                payload["ucr_contribution"],
                tuple(ExperimentCaseFailure.from_dict(x) for x in payload["failures"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("case comparison payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class E1ComparisonReport:
    """Machine-readable comparison; no prose, no winner, no significance claims."""

    experiment_manifest: E1ExperimentManifest
    system_summary: Mapping[str, Any]
    metric_comparisons: tuple[ComparisonResult, ...]
    case_level_differences: tuple[CaseComparison, ...]
    primary_metric_summary: Mapping[str, Any]
    limitations: tuple[str, ...]
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_manifest, E1ExperimentManifest):
            raise ValueError("experiment_manifest must be an E1ExperimentManifest")
        comparisons = tuple(
            sorted(self.metric_comparisons, key=lambda x: x.metric_name)
        )
        if any(not isinstance(x, ComparisonResult) for x in comparisons):
            raise ValueError("metric_comparisons must contain ComparisonResult objects")
        object.__setattr__(self, "metric_comparisons", comparisons)
        cases = tuple(sorted(self.case_level_differences, key=lambda x: x.case_id))
        if any(not isinstance(x, CaseComparison) for x in cases):
            raise ValueError(
                "case_level_differences must contain CaseComparison objects"
            )
        object.__setattr__(self, "case_level_differences", cases)
        for name in ("system_summary", "primary_metric_summary"):
            object.__setattr__(
                self, name, _data(getattr(self, name), name, optional=False)
            )
        object.__setattr__(self, "limitations", tuple(self.limitations))
        for item in self.limitations:
            _required_text(item, "limitations item")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "experiment_manifest": self.experiment_manifest.canonical_dict(),
            "system_summary": _plain_json(self.system_summary),
            "metric_comparisons": [x.canonical_dict() for x in self.metric_comparisons],
            "case_level_differences": [
                x.canonical_dict() for x in self.case_level_differences
            ],
            "primary_metric_summary": _plain_json(self.primary_metric_summary),
            "limitations": list(self.limitations),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> E1ComparisonReport:
        payload = _expect(cls, value, "E1 comparison report")
        try:
            result = cls(
                E1ExperimentManifest.from_dict(payload["experiment_manifest"]),
                payload["system_summary"],
                tuple(
                    ComparisonResult.from_dict(x) for x in payload["metric_comparisons"]
                ),
                tuple(
                    CaseComparison.from_dict(x)
                    for x in payload["case_level_differences"]
                ),
                payload["primary_metric_summary"],
                tuple(payload["limitations"]),
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("E1 comparison report payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("E1 comparison report fingerprint does not match content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> E1ComparisonReport:
        return cls.from_dict(_load(serialized))
