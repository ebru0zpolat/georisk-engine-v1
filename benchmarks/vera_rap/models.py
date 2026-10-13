"""EvidenceBoundBench data models (RAP-010).

Immutable, strictly serialized, fingerprint-bound records for benchmark cases,
reference outcomes, system results, metrics, evaluations, runs and manifests.
The benchmark scores epistemic admissibility, never answer correctness alone.
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
from app.research.vera_rap.trace import (
    ArtifactReference,
    CognitiveTrace,
    TraceValidationResult,
)

BENCHMARK_NAME = "EvidenceBoundBench"
BENCHMARK_VERSION = "0.1.0"
SCHEMA_VERSION = "evidenceboundbench/1"


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as boolean")


class BenchmarkScenarioType(_StrictEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    EXCESSIVE_UNCERTAINTY = "EXCESSIVE_UNCERTAINTY"
    CORRUPTED_SOURCE = "CORRUPTED_SOURCE"
    INVALID_TRANSFORMATION = "INVALID_TRANSFORMATION"
    UNSUPPORTED_INFERENCE = "UNSUPPORTED_INFERENCE"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    REPLANNING_REQUIRED = "REPLANNING_REQUIRED"
    VALID_EVIDENCE_COMPLETE = "VALID_EVIDENCE_COMPLETE"


class ExpectedPermission(_StrictEnum):
    EXPECTED_ALLOW = "EXPECTED_ALLOW"
    EXPECTED_BLOCK = "EXPECTED_BLOCK"
    EXPECTED_ABSTAIN = "EXPECTED_ABSTAIN"
    EXPECTED_REPLAN = "EXPECTED_REPLAN"
    EXPECTED_CONTRADICTION_PENDING = "EXPECTED_CONTRADICTION_PENDING"


class SystemOutcome(_StrictEnum):
    """Observable epistemic action a system took; independent of answer text."""

    CONCLUDED = "CONCLUDED"
    BLOCKED = "BLOCKED"
    ABSTAINED = "ABSTAINED"
    REPLANNED = "REPLANNED"
    CONTRADICTION_PENDING = "CONTRADICTION_PENDING"


# Which observable outcomes satisfy which expected permission.
ADMISSIBLE_OUTCOMES: dict[ExpectedPermission, frozenset[SystemOutcome]] = {
    ExpectedPermission.EXPECTED_ALLOW: frozenset({SystemOutcome.CONCLUDED}),
    ExpectedPermission.EXPECTED_BLOCK: frozenset(
        {SystemOutcome.BLOCKED, SystemOutcome.ABSTAINED, SystemOutcome.REPLANNED}
    ),
    ExpectedPermission.EXPECTED_ABSTAIN: frozenset({SystemOutcome.ABSTAINED}),
    ExpectedPermission.EXPECTED_REPLAN: frozenset({SystemOutcome.REPLANNED}),
    ExpectedPermission.EXPECTED_CONTRADICTION_PENDING: frozenset(
        {
            SystemOutcome.CONTRADICTION_PENDING,
            SystemOutcome.BLOCKED,
            SystemOutcome.REPLANNED,
        }
    ),
}
WITHHOLDING_OUTCOMES = frozenset(
    {
        SystemOutcome.BLOCKED,
        SystemOutcome.ABSTAINED,
        SystemOutcome.REPLANNED,
        SystemOutcome.CONTRADICTION_PENDING,
    }
)


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


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
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
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields do not match the canonical schema")
    return value


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One deterministic epistemic scenario; structure, never executable code."""

    case_id: str
    scenario_type: BenchmarkScenarioType
    description: str
    initial_artifacts: Mapping[str, Any]
    target: Mapping[str, Any]
    expected_permissions: tuple[ExpectedPermission, ...]
    expected_blockers: tuple[str, ...]
    expected_abstention: bool
    expected_trace_properties: Mapping[str, Any]
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _required_text(self.case_id, "case_id")
        _required_text(self.description, "description")
        if not isinstance(self.scenario_type, BenchmarkScenarioType):
            raise ValueError("scenario_type must be a BenchmarkScenarioType")
        permissions = tuple(self.expected_permissions)
        if not permissions or any(
            not isinstance(x, ExpectedPermission) for x in permissions
        ):
            raise ValueError(
                "expected_permissions must name at least one ExpectedPermission"
            )
        if len(set(permissions)) != len(permissions):
            raise ValueError("expected_permissions contains duplicates")
        object.__setattr__(
            self,
            "expected_permissions",
            tuple(sorted(permissions, key=lambda x: x.value)),
        )
        if not isinstance(self.expected_abstention, bool):
            raise ValueError("expected_abstention must be boolean")
        object.__setattr__(
            self,
            "expected_blockers",
            _strings(self.expected_blockers, "expected_blockers"),
        )
        object.__setattr__(
            self,
            "initial_artifacts",
            _data(self.initial_artifacts, "initial_artifacts", optional=False),
        )
        object.__setattr__(self, "target", _data(self.target, "target", optional=False))
        object.__setattr__(
            self,
            "expected_trace_properties",
            _data(
                self.expected_trace_properties,
                "expected_trace_properties",
                optional=False,
            ),
        )
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        if "target_type" not in self.target:
            raise ValueError("target must declare target_type")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario_type": self.scenario_type.value,
            "description": self.description,
            "initial_artifacts": _plain_json(self.initial_artifacts),
            "target": _plain_json(self.target),
            "expected_permissions": [x.value for x in self.expected_permissions],
            "expected_blockers": list(self.expected_blockers),
            "expected_abstention": self.expected_abstention,
            "expected_trace_properties": _plain_json(self.expected_trace_properties),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> BenchmarkCase:
        payload = _expect(cls, value, "benchmark case")
        try:
            return cls(
                payload["case_id"],
                BenchmarkScenarioType(payload["scenario_type"]),
                payload["description"],
                payload["initial_artifacts"],
                payload["target"],
                tuple(ExpectedPermission(x) for x in payload["expected_permissions"]),
                tuple(payload["expected_blockers"]),
                payload["expected_abstention"],
                payload["expected_trace_properties"],
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("benchmark case payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> BenchmarkCase:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class ReferenceOutcome:
    """Benchmark ground truth for one case; never derived from system output."""

    case_id: str
    expected_permission: ExpectedPermission
    allowed_claim_ids: tuple[str, ...]
    forbidden_claim_ids: tuple[str, ...]
    required_blocker_types: tuple[str, ...]
    required_abstention: bool
    required_replanning: bool
    required_trace_events: tuple[str, ...]
    required_provenance_refs: tuple[str, ...]
    required_constraint_behavior: str
    required_evidence_ids: tuple[str, ...] = ()
    admissible_evidence_ids: tuple[str, ...] = ()
    expected_contradiction_ids: tuple[str, ...] = ()
    uncertainty_expectation: Mapping[str, Any] | None = None
    max_plans_before_progress: int = 1
    progress_expected_after_execution: bool = False

    def __post_init__(self) -> None:
        _required_text(self.case_id, "case_id")
        if not isinstance(self.expected_permission, ExpectedPermission):
            raise ValueError("expected_permission must be an ExpectedPermission")
        for name in (
            "required_abstention",
            "required_replanning",
            "progress_expected_after_execution",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")
        if self.required_constraint_behavior not in {"BLOCK", "NONE"}:
            raise ValueError("required_constraint_behavior must be BLOCK or NONE")
        for name in (
            "allowed_claim_ids",
            "forbidden_claim_ids",
            "required_blocker_types",
            "required_trace_events",
            "required_provenance_refs",
            "required_evidence_ids",
            "admissible_evidence_ids",
            "expected_contradiction_ids",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if set(self.allowed_claim_ids) & set(self.forbidden_claim_ids):
            raise ValueError("a claim cannot be both allowed and forbidden")
        if not set(self.admissible_evidence_ids).issubset(self.required_evidence_ids):
            raise ValueError(
                "admissible evidence must be a subset of required evidence"
            )
        object.__setattr__(
            self,
            "uncertainty_expectation",
            _data(
                self.uncertainty_expectation, "uncertainty_expectation", optional=True
            ),
        )
        _count(self.max_plans_before_progress, "max_plans_before_progress")

    def canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, ExpectedPermission):
                payload[item.name] = value.value
            elif isinstance(value, tuple):
                payload[item.name] = list(value)
            elif isinstance(value, Mapping):
                payload[item.name] = _plain_json(value)
            else:
                payload[item.name] = value
        return payload

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> ReferenceOutcome:
        payload = _expect(cls, value, "reference outcome")
        try:
            return cls(
                **{
                    **{
                        k: (tuple(v) if isinstance(v, list) else v)
                        for k, v in payload.items()
                    },
                    "expected_permission": ExpectedPermission(
                        payload["expected_permission"]
                    ),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("reference outcome payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ReferenceOutcome:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class SystemCaseResult:
    """Observable epistemic behavior of any system on one case; VERA-RAP optional."""

    case_id: str
    system_id: str
    system_version: str
    claimed_outcome: SystemOutcome
    claim_ids: tuple[str, ...]
    transition_statuses: Mapping[str, str]
    abstraction_statuses: Mapping[str, str]
    abstained: bool
    plan_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    trace: CognitiveTrace | None
    execution_metadata: Mapping[str, Any]
    evidence_references: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    contradiction_handling: Mapping[str, Any] = field(default_factory=dict)
    uncertainty_report: Mapping[str, Any] = field(default_factory=dict)
    constraint_report: Mapping[str, Any] = field(default_factory=dict)
    plans: tuple[Mapping[str, Any], ...] = ()
    blocker_types: tuple[str, ...] = ()
    registry_references: tuple[ArtifactReference, ...] = ()
    initial_outcome: SystemOutcome | None = None

    def __post_init__(self) -> None:
        if self.initial_outcome is not None and not isinstance(
            self.initial_outcome, SystemOutcome
        ):
            raise ValueError("initial_outcome must be a SystemOutcome or null")
        for name in ("case_id", "system_id", "system_version"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.claimed_outcome, SystemOutcome):
            raise ValueError("claimed_outcome must be a SystemOutcome")
        if not isinstance(self.abstained, bool):
            raise ValueError("abstained must be boolean")
        if self.abstained is not (self.claimed_outcome is SystemOutcome.ABSTAINED):
            raise ValueError("abstained flag disagrees with claimed_outcome")
        if self.claimed_outcome is not SystemOutcome.CONCLUDED and self.claim_ids:
            raise ValueError("a withholding outcome cannot emit material claims")
        for name in ("claim_ids", "plan_ids", "blocker_ids", "blocker_types"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        for name in (
            "transition_statuses",
            "abstraction_statuses",
            "execution_metadata",
            "evidence_references",
            "provenance",
            "contradiction_handling",
            "uncertainty_report",
            "constraint_report",
        ):
            object.__setattr__(
                self, name, _data(getattr(self, name), name, optional=False)
            )
        plans = tuple(_data(x, "plans item", optional=False) for x in self.plans)
        object.__setattr__(self, "plans", plans)
        if self.trace is not None and not isinstance(self.trace, CognitiveTrace):
            raise ValueError("trace must be a CognitiveTrace or null")
        refs = tuple(self.registry_references)
        if any(not isinstance(x, ArtifactReference) for x in refs):
            raise ValueError(
                "registry_references must contain ArtifactReference objects"
            )
        object.__setattr__(
            self,
            "registry_references",
            tuple(sorted(refs, key=lambda x: x.artifact_id)),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "system_id": self.system_id,
            "system_version": self.system_version,
            "claimed_outcome": self.claimed_outcome.value,
            "claim_ids": list(self.claim_ids),
            "transition_statuses": _plain_json(self.transition_statuses),
            "abstraction_statuses": _plain_json(self.abstraction_statuses),
            "abstained": self.abstained,
            "plan_ids": list(self.plan_ids),
            "blocker_ids": list(self.blocker_ids),
            "trace": None if self.trace is None else self.trace.canonical_dict(),
            "execution_metadata": _plain_json(self.execution_metadata),
            "evidence_references": _plain_json(self.evidence_references),
            "provenance": _plain_json(self.provenance),
            "contradiction_handling": _plain_json(self.contradiction_handling),
            "uncertainty_report": _plain_json(self.uncertainty_report),
            "constraint_report": _plain_json(self.constraint_report),
            "plans": [_plain_json(x) for x in self.plans],
            "blocker_types": list(self.blocker_types),
            "registry_references": [
                x.canonical_dict() for x in self.registry_references
            ],
            "initial_outcome": (
                None if self.initial_outcome is None else self.initial_outcome.value
            ),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @property
    def decision_outcome(self) -> SystemOutcome:
        """The first epistemic action taken; later progress is scored separately."""
        return (
            self.claimed_outcome
            if self.initial_outcome is None
            else self.initial_outcome
        )

    @classmethod
    def from_dict(cls, value: object) -> SystemCaseResult:
        payload = _expect(cls, value, "system case result")
        try:
            return cls(
                payload["case_id"],
                payload["system_id"],
                payload["system_version"],
                SystemOutcome(payload["claimed_outcome"]),
                tuple(payload["claim_ids"]),
                payload["transition_statuses"],
                payload["abstraction_statuses"],
                payload["abstained"],
                tuple(payload["plan_ids"]),
                tuple(payload["blocker_ids"]),
                (
                    None
                    if payload["trace"] is None
                    else CognitiveTrace.from_dict(payload["trace"])
                ),
                payload["execution_metadata"],
                payload["evidence_references"],
                payload["provenance"],
                payload["contradiction_handling"],
                payload["uncertainty_report"],
                payload["constraint_report"],
                tuple(payload["plans"]),
                tuple(payload["blocker_types"]),
                tuple(
                    ArtifactReference.from_dict(x)
                    for x in payload["registry_references"]
                ),
                (
                    None
                    if payload["initial_outcome"] is None
                    else SystemOutcome(payload["initial_outcome"])
                ),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("system case result payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> SystemCaseResult:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class MetricResult:
    """A metric with its evidence: numerator, denominator, and case list."""

    metric_name: str
    value: float | None
    numerator: int
    denominator: int
    passed: bool | None
    details: Mapping[str, Any]
    case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _required_text(self.metric_name, "metric_name")
        object.__setattr__(self, "value", _finite(self.value, "value", optional=True))
        _count(self.numerator, "numerator")
        _count(self.denominator, "denominator")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise ValueError("passed must be boolean or null")
        object.__setattr__(
            self, "details", _data(self.details, "details", optional=False)
        )
        object.__setattr__(self, "case_ids", _strings(self.case_ids, "case_ids"))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "passed": self.passed,
            "details": _plain_json(self.details),
            "case_ids": list(self.case_ids),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> MetricResult:
        payload = _expect(cls, value, "metric result")
        try:
            return cls(**{**payload, "case_ids": tuple(payload["case_ids"])})
        except (KeyError, TypeError) as exc:
            raise ValueError("metric result payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    metric_results: tuple[MetricResult, ...]
    violations: tuple[str, ...]
    passed: bool
    trace_validation_result: TraceValidationResult | None
    notes: tuple[str, ...]
    admissible_action: bool
    claimed_outcome: SystemOutcome
    expected_permission: ExpectedPermission

    def __post_init__(self) -> None:
        _required_text(self.case_id, "case_id")
        results = tuple(sorted(self.metric_results, key=lambda x: x.metric_name))
        if any(not isinstance(x, MetricResult) for x in results):
            raise ValueError("metric_results must contain MetricResult objects")
        if len({x.metric_name for x in results}) != len(results):
            raise ValueError("duplicate metric name in case evaluation")
        object.__setattr__(self, "metric_results", results)
        object.__setattr__(self, "violations", _strings(self.violations, "violations"))
        object.__setattr__(self, "notes", _strings(self.notes, "notes"))
        for name in ("passed", "admissible_action"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")
        if self.passed is bool(self.violations):
            raise ValueError("passed flag disagrees with violations")
        if self.trace_validation_result is not None and not isinstance(
            self.trace_validation_result, TraceValidationResult
        ):
            raise ValueError(
                "trace_validation_result must be a TraceValidationResult or null"
            )
        if not isinstance(self.claimed_outcome, SystemOutcome) or not isinstance(
            self.expected_permission, ExpectedPermission
        ):
            raise ValueError("outcome and permission must be enum members")

    def metric(self, name: str) -> MetricResult:
        for item in self.metric_results:
            if item.metric_name == name:
                return item
        raise KeyError(name)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "metric_results": [x.canonical_dict() for x in self.metric_results],
            "violations": list(self.violations),
            "passed": self.passed,
            "trace_validation_result": (
                None
                if self.trace_validation_result is None
                else self.trace_validation_result.canonical_dict()
            ),
            "notes": list(self.notes),
            "admissible_action": self.admissible_action,
            "claimed_outcome": self.claimed_outcome.value,
            "expected_permission": self.expected_permission.value,
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> CaseEvaluation:
        payload = _expect(cls, value, "case evaluation")
        try:
            return cls(
                payload["case_id"],
                tuple(MetricResult.from_dict(x) for x in payload["metric_results"]),
                tuple(payload["violations"]),
                payload["passed"],
                (
                    None
                    if payload["trace_validation_result"] is None
                    else TraceValidationResult.from_dict(
                        payload["trace_validation_result"]
                    )
                ),
                tuple(payload["notes"]),
                payload["admissible_action"],
                SystemOutcome(payload["claimed_outcome"]),
                ExpectedPermission(payload["expected_permission"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("case evaluation payload is malformed") from exc


@dataclass(frozen=True, slots=True)
class BenchmarkRunResult:
    benchmark_version: str
    system_id: str
    system_version: str
    case_results: tuple[CaseEvaluation, ...]
    aggregate_metrics: tuple[MetricResult, ...]
    started_at: datetime
    completed_at: datetime
    manifest_fingerprint: str
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "benchmark_version",
            "system_id",
            "system_version",
            "manifest_fingerprint",
        ):
            _required_text(getattr(self, name), name)
        _timestamp(self.started_at, "started_at")
        _timestamp(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        cases = tuple(sorted(self.case_results, key=lambda x: x.case_id))
        if any(not isinstance(x, CaseEvaluation) for x in cases):
            raise ValueError("case_results must contain CaseEvaluation objects")
        if len({x.case_id for x in cases}) != len(cases):
            raise ValueError("duplicate case ID in run result")
        object.__setattr__(self, "case_results", cases)
        metrics = tuple(sorted(self.aggregate_metrics, key=lambda x: x.metric_name))
        if any(not isinstance(x, MetricResult) for x in metrics):
            raise ValueError("aggregate_metrics must contain MetricResult objects")
        if len({x.metric_name for x in metrics}) != len(metrics):
            raise ValueError("duplicate aggregate metric name")
        object.__setattr__(self, "aggregate_metrics", metrics)
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "benchmark_version": self.benchmark_version,
            "system_id": self.system_id,
            "system_version": self.system_version,
            "case_results": [x.canonical_dict() for x in self.case_results],
            "aggregate_metrics": [x.canonical_dict() for x in self.aggregate_metrics],
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "manifest_fingerprint": self.manifest_fingerprint,
            "metadata": _plain_json(self.metadata),
        }

    def metric(self, name: str) -> MetricResult:
        for item in self.aggregate_metrics:
            if item.metric_name == name:
                return item
        raise KeyError(name)

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> BenchmarkRunResult:
        payload = _expect(cls, value, "benchmark run result")
        try:
            result = cls(
                payload["benchmark_version"],
                payload["system_id"],
                payload["system_version"],
                tuple(CaseEvaluation.from_dict(x) for x in payload["case_results"]),
                tuple(MetricResult.from_dict(x) for x in payload["aggregate_metrics"]),
                _parse_timestamp(payload["started_at"], "started_at"),
                _parse_timestamp(payload["completed_at"], "completed_at"),
                payload["manifest_fingerprint"],
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("benchmark run result payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("run fingerprint does not match content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> BenchmarkRunResult:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class EvidenceBoundBenchManifest:
    benchmark_name: str
    version: str
    case_ids: tuple[str, ...]
    metric_names: tuple[str, ...]
    schema_version: str
    created_at: datetime
    metadata: Mapping[str, Any] | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("benchmark_name", "version", "schema_version"):
            _required_text(getattr(self, name), name)
        object.__setattr__(
            self, "case_ids", _strings(self.case_ids, "case_ids", allow_empty=False)
        )
        object.__setattr__(
            self,
            "metric_names",
            _strings(self.metric_names, "metric_names", allow_empty=False),
        )
        _timestamp(self.created_at, "created_at")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(self, "fingerprint", _sha(_canonical(self._content_dict())))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "version": self.version,
            "case_ids": list(self.case_ids),
            "metric_names": list(self.metric_names),
            "schema_version": self.schema_version,
            "created_at": _iso(self.created_at),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> EvidenceBoundBenchManifest:
        payload = _expect(cls, value, "benchmark manifest")
        try:
            result = cls(
                payload["benchmark_name"],
                payload["version"],
                tuple(payload["case_ids"]),
                tuple(payload["metric_names"]),
                payload["schema_version"],
                _parse_timestamp(payload["created_at"], "created_at"),
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("benchmark manifest payload is malformed") from exc
        if result.fingerprint != payload["fingerprint"]:
            raise ValueError("manifest fingerprint does not match content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EvidenceBoundBenchManifest:
        return cls.from_dict(_load(serialized))


class BenchmarkSystem:
    """Minimal system-under-test protocol; any system may implement it."""

    system_id: str
    system_version: str

    def evaluate_case(
        self, case: BenchmarkCase
    ) -> SystemCaseResult:  # pragma: no cover
        raise NotImplementedError
