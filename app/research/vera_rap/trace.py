"""Machine-verifiable Cognitive Trace for isolated VERA-RAP research (RAP-009).

VERA-RAP Cognitive Trace records externally verifiable reasoning artifacts, not
private chain-of-thought. A trace is an immutable DAG of typed events, each
bound by fingerprint to the exact artifact versions it describes. It stores no
model thoughts, prompts, scratchpads, or free-form deliberation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any

from .evidence import (
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as boolean")


class TraceEventType(_StrictEnum):
    EVIDENCE_REGISTERED = "EVIDENCE_REGISTERED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    EVIDENCE_BECAME_STALE = "EVIDENCE_BECAME_STALE"
    CLAIM_DECLARED = "CLAIM_DECLARED"
    CLAIM_EVALUATED = "CLAIM_EVALUATED"
    GRAPH_VALIDATED = "GRAPH_VALIDATED"
    SUPPORT_EVALUATED = "SUPPORT_EVALUATED"
    TRANSITION_EVALUATED = "TRANSITION_EVALUATED"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    CONTRADICTION_EVALUATED = "CONTRADICTION_EVALUATED"
    UNCERTAINTY_PROPAGATED = "UNCERTAINTY_PROPAGATED"
    UNCERTAINTY_GATE_EVALUATED = "UNCERTAINTY_GATE_EVALUATED"
    ABSTRACTION_PROPOSED = "ABSTRACTION_PROPOSED"
    ABSTRACTION_VERIFIED = "ABSTRACTION_VERIFIED"
    ABSTRACTION_BLOCKED = "ABSTRACTION_BLOCKED"
    ABSTRACTION_SUPERSEDED = "ABSTRACTION_SUPERSEDED"
    BLOCKERS_IDENTIFIED = "BLOCKERS_IDENTIFIED"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_EXECUTION_RECORDED = "PLAN_EXECUTION_RECORDED"
    REPLAN_CREATED = "REPLAN_CREATED"
    PLANNER_ABSTAINED = "PLANNER_ABSTAINED"
    TRACE_CHECKPOINT = "TRACE_CHECKPOINT"


class ArtifactType(_StrictEnum):
    EVIDENCE = "EVIDENCE"
    CLAIM = "CLAIM"
    CLAIM_EVALUATION = "CLAIM_EVALUATION"
    EVIDENCE_GRAPH = "EVIDENCE_GRAPH"
    SUPPORT_RESULT = "SUPPORT_RESULT"
    TRANSITION = "TRANSITION"
    TRANSITION_EVALUATION = "TRANSITION_EVALUATION"
    CONTRADICTION = "CONTRADICTION"
    CONTRADICTION_RESOLUTION = "CONTRADICTION_RESOLUTION"
    UNCERTAINTY_PROFILE = "UNCERTAINTY_PROFILE"
    UNCERTAINTY_PROPAGATION = "UNCERTAINTY_PROPAGATION"
    UNCERTAINTY_GATE = "UNCERTAINTY_GATE"
    ABSTRACTION = "ABSTRACTION"
    ABSTRACTION_GRAPH = "ABSTRACTION_GRAPH"
    ABSTRACTION_VERIFICATION = "ABSTRACTION_VERIFICATION"
    PLANNING_TARGET = "PLANNING_TARGET"
    BLOCKER = "BLOCKER"
    PLAN = "PLAN"
    PLAN_EXECUTION = "PLAN_EXECUTION"


# Keys that would carry private reasoning; rejected anywhere in trace data.
PRIVATE_REASONING_KEYS = frozenset(
    {
        "chain_of_thought",
        "internal_reasoning",
        "scratchpad",
        "reasoning",
        "thoughts",
        "thought",
        "deliberation",
        "rationale_text",
        "prompt",
        "completion",
        "response",
        "model_output",
        "llm_reasoning",
    }
)

# Event types that need a specific predecessor type somewhere upstream.
REQUIRED_PREDECESSORS: dict[TraceEventType, frozenset[TraceEventType]] = {
    TraceEventType.EVIDENCE_VERIFIED: frozenset({TraceEventType.EVIDENCE_REGISTERED}),
    TraceEventType.EVIDENCE_REJECTED: frozenset({TraceEventType.EVIDENCE_REGISTERED}),
    TraceEventType.EVIDENCE_BECAME_STALE: frozenset(
        {TraceEventType.EVIDENCE_REGISTERED}
    ),
    TraceEventType.CLAIM_EVALUATED: frozenset({TraceEventType.CLAIM_DECLARED}),
    TraceEventType.SUPPORT_EVALUATED: frozenset({TraceEventType.CLAIM_DECLARED}),
    TraceEventType.TRANSITION_EVALUATED: frozenset(
        {
            TraceEventType.SUPPORT_EVALUATED,
            TraceEventType.EVIDENCE_REGISTERED,
            TraceEventType.CLAIM_DECLARED,
        }
    ),
    TraceEventType.CONTRADICTION_EVALUATED: frozenset(
        {TraceEventType.CONTRADICTION_DETECTED}
    ),
    TraceEventType.UNCERTAINTY_GATE_EVALUATED: frozenset(
        {TraceEventType.UNCERTAINTY_PROPAGATED}
    ),
    TraceEventType.ABSTRACTION_VERIFIED: frozenset(
        {TraceEventType.ABSTRACTION_PROPOSED}
    ),
    TraceEventType.ABSTRACTION_BLOCKED: frozenset(
        {TraceEventType.ABSTRACTION_PROPOSED}
    ),
    TraceEventType.ABSTRACTION_SUPERSEDED: frozenset(
        {TraceEventType.ABSTRACTION_PROPOSED}
    ),
    TraceEventType.PLAN_CREATED: frozenset({TraceEventType.BLOCKERS_IDENTIFIED}),
    TraceEventType.PLANNER_ABSTAINED: frozenset({TraceEventType.BLOCKERS_IDENTIFIED}),
    TraceEventType.PLAN_EXECUTION_RECORDED: frozenset(
        {TraceEventType.PLAN_CREATED, TraceEventType.REPLAN_CREATED}
    ),
    TraceEventType.REPLAN_CREATED: frozenset({TraceEventType.PLAN_EXECUTION_RECORDED}),
}

# Events that record a subject's explicit epistemic outcome.
OUTCOME_EVENTS = frozenset(
    {
        TraceEventType.EVIDENCE_VERIFIED,
        TraceEventType.EVIDENCE_REJECTED,
        TraceEventType.EVIDENCE_BECAME_STALE,
        TraceEventType.CLAIM_EVALUATED,
        TraceEventType.SUPPORT_EVALUATED,
        TraceEventType.TRANSITION_EVALUATED,
        TraceEventType.CONTRADICTION_DETECTED,
        TraceEventType.CONTRADICTION_EVALUATED,
        TraceEventType.UNCERTAINTY_GATE_EVALUATED,
        TraceEventType.ABSTRACTION_VERIFIED,
        TraceEventType.ABSTRACTION_BLOCKED,
        TraceEventType.ABSTRACTION_SUPERSEDED,
        TraceEventType.PLAN_CREATED,
        TraceEventType.REPLAN_CREATED,
        TraceEventType.PLANNER_ABSTAINED,
    }
)
PLANNING_EVENTS = frozenset(
    {
        TraceEventType.BLOCKERS_IDENTIFIED,
        TraceEventType.PLAN_CREATED,
        TraceEventType.PLAN_EXECUTION_RECORDED,
        TraceEventType.REPLAN_CREATED,
        TraceEventType.PLANNER_ABSTAINED,
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


def _digest(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{_sha(_canonical(payload))}"


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


def _reject_private_reasoning(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in PRIVATE_REASONING_KEYS:
                raise ValueError(
                    f"{path}.{key} would store private reasoning; traces record "
                    "artifacts and reason codes only"
                )
            _reject_private_reasoning(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_private_reasoning(item, f"{path}[]")


def _data(value: object, name: str, *, optional: bool) -> Any:
    frozen = _freeze_json(value, name)
    if frozen is None:
        if optional:
            return None
        raise ValueError(f"{name} must be an object")
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{name} must be an object")
    _reject_private_reasoning(frozen, name)
    return frozen


def _fingerprint_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _load(serialized: str) -> Any:
    if not isinstance(serialized, str):
        raise ValueError("serialized payload must be text")
    try:
        return json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("serialized payload must be valid JSON") from exc


def _expect_fields(cls: type, value: object, label: str) -> dict[str, Any]:
    expected = {item.name for item in fields(cls)}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields do not match the canonical schema")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Fingerprint-bound reference to one exact artifact version."""

    artifact_id: str
    artifact_type: ArtifactType
    fingerprint: str
    schema_version: str
    created_at: datetime | None
    module: str
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "schema_version", "module"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.artifact_type, ArtifactType):
            raise ValueError("artifact_type must be an ArtifactType")
        _fingerprint_text(self.fingerprint, "fingerprint")
        if self.created_at is not None:
            _timestamp(self.created_at, "created_at")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type.value,
            "fingerprint": self.fingerprint,
            "schema_version": self.schema_version,
            "created_at": _iso(self.created_at),
            "module": self.module,
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def reference_fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> ArtifactReference:
        payload = _expect_fields(cls, value, "artifact reference")
        try:
            return cls(
                payload["artifact_id"],
                ArtifactType(payload["artifact_type"]),
                payload["fingerprint"],
                payload["schema_version"],
                _parse_timestamp(payload["created_at"], "created_at", optional=True),
                payload["module"],
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("artifact reference payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ArtifactReference:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One typed, fingerprint-bound cognitive event; never prose."""

    event_type: TraceEventType
    subject_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    input_event_ids: tuple[str, ...]
    occurred_at: datetime
    actor_id: str
    actor_version: str
    details: Mapping[str, Any] | None
    artifact_fingerprints: Mapping[str, str]
    metadata: Mapping[str, Any] | None = None
    event_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, TraceEventType):
            raise ValueError("event_type must be a TraceEventType")
        for name in ("actor_id", "actor_version"):
            _required_text(getattr(self, name), name)
        _timestamp(self.occurred_at, "occurred_at")
        object.__setattr__(
            self,
            "subject_ids",
            _strings(self.subject_ids, "subject_ids", allow_empty=False),
        )
        object.__setattr__(
            self, "artifact_ids", _strings(self.artifact_ids, "artifact_ids")
        )
        object.__setattr__(
            self, "input_event_ids", _strings(self.input_event_ids, "input_event_ids")
        )
        object.__setattr__(
            self, "details", _data(self.details, "details", optional=True)
        )
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        bindings = _freeze_json(self.artifact_fingerprints, "artifact_fingerprints")
        if not isinstance(bindings, Mapping) or set(bindings) != set(self.artifact_ids):
            raise ValueError(
                "every referenced artifact must be bound to exactly one fingerprint"
            )
        for artifact_id, digest in bindings.items():
            _fingerprint_text(digest, f"artifact_fingerprints[{artifact_id}]")
        object.__setattr__(self, "artifact_fingerprints", bindings)
        object.__setattr__(self, "event_id", _digest("event", self._content_dict()))
        if self.event_id in self.input_event_ids:
            raise ValueError("an event cannot be its own input")

    def _content_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "subject_ids": list(self.subject_ids),
            "artifact_ids": list(self.artifact_ids),
            "input_event_ids": list(self.input_event_ids),
            "occurred_at": _iso(self.occurred_at),
            "actor_id": self.actor_id,
            "actor_version": self.actor_version,
            "details": _plain_json(self.details),
            "artifact_fingerprints": _plain_json(self.artifact_fingerprints),
            "metadata": _plain_json(self.metadata),
        }

    @property
    def outcome(self) -> str | None:
        value = None if self.details is None else self.details.get("outcome")
        return value if isinstance(value, str) else None

    @property
    def blocking(self) -> bool:
        return bool(self.details) and self.details.get("blocking") is True

    def canonical_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> TraceEvent:
        payload = _expect_fields(cls, value, "trace event")
        try:
            result = cls(
                TraceEventType(payload["event_type"]),
                tuple(payload["subject_ids"]),
                tuple(payload["artifact_ids"]),
                tuple(payload["input_event_ids"]),
                _parse_timestamp(payload["occurred_at"], "occurred_at"),
                payload["actor_id"],
                payload["actor_version"],
                payload["details"],
                payload["artifact_fingerprints"],
                payload["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("trace event payload is malformed") from exc
        if result.event_id != payload["event_id"]:
            raise ValueError("event_id does not match event content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> TraceEvent:
        return cls.from_dict(_load(serialized))


def _check_dag(
    events: tuple[TraceEvent, ...],
) -> tuple[dict[str, int], list[str], list[str]]:
    """Return (depth by event id, missing input ids, chronology errors); raise on cycles."""
    by_id = {x.event_id: x for x in events}
    missing: set[str] = set()
    chronology: set[str] = set()
    depth: dict[str, int] = {}
    active: set[str] = set()

    def visit(event_id: str) -> int:
        if event_id in depth:
            return depth[event_id]
        if event_id in active:
            raise ValueError(f"trace events form a cycle at {event_id}")
        active.add(event_id)
        event = by_id[event_id]
        level = 0
        for input_id in event.input_event_ids:
            parent = by_id.get(input_id)
            if parent is None:
                missing.add(input_id)
                continue
            if parent.occurred_at > event.occurred_at:
                chronology.add(f"{event_id} precedes input {input_id}")
            level = max(level, 1 + visit(input_id))
        active.remove(event_id)
        depth[event_id] = level
        return level

    for event_id in sorted(by_id):
        visit(event_id)
    return depth, sorted(missing), sorted(chronology)


def _upstream(events: Mapping[str, TraceEvent], start: set[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(start)
    while stack:
        current = stack.pop()
        for input_id in events[current].input_event_ids if current in events else ():
            if input_id not in seen:
                seen.add(input_id)
                stack.append(input_id)
    return seen


def _downstream(events: Mapping[str, TraceEvent], start: set[str]) -> set[str]:
    children: dict[str, set[str]] = {}
    for event in events.values():
        for input_id in event.input_event_ids:
            children.setdefault(input_id, set()).add(event.event_id)
    seen: set[str] = set()
    stack = list(start)
    while stack:
        current = stack.pop()
        for child in children.get(current, ()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


@dataclass(frozen=True, slots=True)
class TraceExplanation:
    """Machine-readable lineage for one subject; no generated prose."""

    subject_id: str
    related_event_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    upstream_event_ids: tuple[str, ...]
    downstream_event_ids: tuple[str, ...]
    current_epistemic_outcome: Mapping[str, Any] | None
    current_planning_outcome: Mapping[str, Any] | None
    blocking_event_ids: tuple[str, ...]
    planning_event_ids: tuple[str, ...]
    event_types: Mapping[str, str]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "related_event_ids": list(self.related_event_ids),
            "artifact_ids": list(self.artifact_ids),
            "upstream_event_ids": list(self.upstream_event_ids),
            "downstream_event_ids": list(self.downstream_event_ids),
            "current_epistemic_outcome": _plain_json(self.current_epistemic_outcome),
            "current_planning_outcome": _plain_json(self.current_planning_outcome),
            "blocking_event_ids": list(self.blocking_event_ids),
            "planning_event_ids": list(self.planning_event_ids),
            "event_types": _plain_json(self.event_types),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class TraceCompleteness:
    """Counts a future benchmark can consume; ratios are explicit fractions."""

    evidence_reference_coverage: Mapping[str, Any]
    claim_evaluation_coverage: Mapping[str, Any]
    transition_evaluation_coverage: Mapping[str, Any]
    uncertainty_trace_coverage: Mapping[str, Any]
    abstraction_trace_coverage: Mapping[str, Any]
    planning_trace_coverage: Mapping[str, Any]
    unresolved_reference_count: int
    event_counts: Mapping[str, int]
    artifact_counts: Mapping[str, int]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            item.name: _plain_json(getattr(self, item.name)) for item in fields(self)
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())


def _coverage(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": None if denominator == 0 else numerator / denominator,
    }


@dataclass(frozen=True, slots=True, init=False)
class CognitiveTrace:
    """Immutable, fingerprint-bound DAG of explicit cognitive events."""

    root_subject_ids: tuple[str, ...]
    events: tuple[TraceEvent, ...]
    artifacts: tuple[ArtifactReference, ...]
    started_at: datetime
    ended_at: datetime | None
    trace_version: str
    metadata: Mapping[str, Any] | None
    parent_trace_id: str | None
    parent_trace_fingerprint: str | None
    trace_id: str

    def __init__(
        self,
        root_subject_ids: tuple[str, ...],
        events: tuple[TraceEvent, ...],
        artifacts: tuple[ArtifactReference, ...],
        started_at: datetime,
        ended_at: datetime | None = None,
        trace_version: str = "1",
        metadata: Mapping[str, Any] | None = None,
        parent_trace_id: str | None = None,
        parent_trace_fingerprint: str | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            if item.name != "trace_id":
                object.__setattr__(self, item.name, values[item.name])
        object.__setattr__(
            self,
            "root_subject_ids",
            _strings(self.root_subject_ids, "root_subject_ids", allow_empty=False),
        )
        _required_text(self.trace_version, "trace_version")
        _timestamp(self.started_at, "started_at")
        if self.ended_at is not None:
            _timestamp(self.ended_at, "ended_at")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at cannot precede started_at")
        if (self.parent_trace_id is None) != (self.parent_trace_fingerprint is None):
            raise ValueError("parent linkage must bind both trace ID and fingerprint")
        if self.parent_trace_id is not None:
            _required_text(self.parent_trace_id, "parent_trace_id")
            _fingerprint_text(self.parent_trace_fingerprint, "parent_trace_fingerprint")
        object.__setattr__(
            self, "metadata", _data(self.metadata, "metadata", optional=True)
        )
        artifacts = tuple(self.artifacts)
        if any(not isinstance(x, ArtifactReference) for x in artifacts):
            raise ValueError("artifacts must contain ArtifactReference objects")
        by_artifact: dict[str, ArtifactReference] = {}
        for reference in artifacts:
            existing = by_artifact.get(reference.artifact_id)
            if existing is not None and existing.fingerprint != reference.fingerprint:
                raise ValueError(
                    f"artifact {reference.artifact_id} is referenced with two fingerprints"
                )
            by_artifact[reference.artifact_id] = reference
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(by_artifact.values(), key=lambda x: x.artifact_id)),
        )
        events = tuple(self.events)
        if any(not isinstance(x, TraceEvent) for x in events):
            raise ValueError("events must contain TraceEvent objects")
        by_event = {x.event_id: x for x in events}
        if len(by_event) != len(events):
            raise ValueError("duplicate trace event identity")
        for event in events:
            if event.occurred_at < self.started_at:
                raise ValueError("event precedes the trace start")
            if self.ended_at is not None and event.occurred_at > self.ended_at:
                raise ValueError("event follows the trace end")
            for artifact_id, digest in event.artifact_fingerprints.items():
                reference = by_artifact.get(artifact_id)
                if reference is None:
                    raise ValueError(
                        f"event references unlisted artifact {artifact_id}"
                    )
                if reference.fingerprint != digest:
                    raise ValueError(
                        f"event binds artifact {artifact_id} to a different version"
                    )
        _, missing, chronology = _check_dag(tuple(by_event.values()))
        if missing:
            raise ValueError(
                f"trace references missing input events: {', '.join(missing)}"
            )
        if chronology:
            raise ValueError(f"trace chronology violated: {'; '.join(chronology)}")
        object.__setattr__(
            self,
            "events",
            tuple(sorted(events, key=lambda x: (_iso(x.occurred_at), x.event_id))),
        )
        object.__setattr__(self, "trace_id", _digest("trace", self._content_dict()))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "root_subject_ids": list(self.root_subject_ids),
            "events": [x.canonical_dict() for x in self.events],
            "artifacts": [x.canonical_dict() for x in self.artifacts],
            "started_at": _iso(self.started_at),
            "ended_at": _iso(self.ended_at),
            "trace_version": self.trace_version,
            "metadata": _plain_json(self.metadata),
            "parent_trace_id": self.parent_trace_id,
            "parent_trace_fingerprint": self.parent_trace_fingerprint,
        }

    # -- identity and serialization ---------------------------------------- #

    def canonical_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> CognitiveTrace:
        payload = _expect_fields(cls, value, "cognitive trace")
        try:
            result = cls(
                tuple(payload["root_subject_ids"]),
                tuple(TraceEvent.from_dict(x) for x in payload["events"]),
                tuple(ArtifactReference.from_dict(x) for x in payload["artifacts"]),
                _parse_timestamp(payload["started_at"], "started_at"),
                _parse_timestamp(payload["ended_at"], "ended_at", optional=True),
                payload["trace_version"],
                payload["metadata"],
                payload["parent_trace_id"],
                payload["parent_trace_fingerprint"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("cognitive trace payload is malformed") from exc
        if result.trace_id != payload["trace_id"]:
            raise ValueError("trace_id does not match trace content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> CognitiveTrace:
        result = cls.from_dict(_load(serialized))
        if result.canonical_json() != serialized:
            raise ValueError("cognitive trace JSON is not canonical")
        return result

    # -- immutable extension ----------------------------------------------- #

    def append_event(
        self, event: TraceEvent, artifacts: tuple[ArtifactReference, ...] = ()
    ) -> CognitiveTrace:
        """Return a new trace; this trace is left unchanged."""
        if not isinstance(event, TraceEvent):
            raise ValueError("event must be a TraceEvent")
        return CognitiveTrace(
            self.root_subject_ids,
            (*self.events, event),
            (*self.artifacts, *artifacts),
            self.started_at,
            self.ended_at,
            self.trace_version,
            self.metadata,
            self.parent_trace_id,
            self.parent_trace_fingerprint,
        )

    def with_artifacts(
        self, artifacts: tuple[ArtifactReference, ...]
    ) -> CognitiveTrace:
        return CognitiveTrace(
            self.root_subject_ids,
            self.events,
            (*self.artifacts, *artifacts),
            self.started_at,
            self.ended_at,
            self.trace_version,
            self.metadata,
            self.parent_trace_id,
            self.parent_trace_fingerprint,
        )

    def ended(self, at: datetime) -> CognitiveTrace:
        return CognitiveTrace(
            self.root_subject_ids,
            self.events,
            self.artifacts,
            self.started_at,
            at,
            self.trace_version,
            self.metadata,
            self.parent_trace_id,
            self.parent_trace_fingerprint,
        )

    def successor(
        self,
        root_subject_ids: tuple[str, ...],
        started_at: datetime,
        *,
        trace_version: str | None = None,
    ) -> CognitiveTrace:
        """Start a new episode that descends, fingerprint-bound, from this trace."""
        return CognitiveTrace(
            root_subject_ids,
            (),
            (),
            started_at,
            None,
            trace_version or self.trace_version,
            None,
            self.trace_id,
            self.fingerprint,
        )

    # -- lookup ------------------------------------------------------------ #

    @property
    def event_map(self) -> dict[str, TraceEvent]:
        return {x.event_id: x for x in self.events}

    @property
    def artifact_map(self) -> dict[str, ArtifactReference]:
        return {x.artifact_id: x for x in self.artifacts}

    def events_for(self, subject_id: str) -> tuple[TraceEvent, ...]:
        return tuple(x for x in self.events if subject_id in x.subject_ids)

    def latest_outcome(
        self, subject_id: str, *, planning: bool = False
    ) -> TraceEvent | None:
        """Latest explicit outcome event for a subject by time, depth, then ID.

        Epistemic outcomes (evaluations, verdicts) and planning outcomes (plans,
        replans, abstentions) are resolved separately so a plan never masks a verdict.
        """
        depth, _, _ = _check_dag(self.events)
        kinds = (
            (OUTCOME_EVENTS & PLANNING_EVENTS)
            if planning
            else (OUTCOME_EVENTS - PLANNING_EVENTS)
        )
        candidates = [
            x
            for x in self.events_for(subject_id)
            if x.event_type in kinds and x.outcome is not None
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda x: (_iso(x.occurred_at), depth[x.event_id], x.event_id),
        )

    def explain(self, subject_id: str) -> TraceExplanation:
        _required_text(subject_id, "subject_id")
        events = self.event_map
        related = {x.event_id for x in self.events_for(subject_id)}
        upstream = _upstream(events, related) - related
        downstream = _downstream(events, related) - related
        involved = related | upstream | downstream
        artifact_ids = sorted({a for e in involved for a in events[e].artifact_ids})

        def summary(latest: TraceEvent | None) -> dict[str, Any] | None:
            if latest is None:
                return None
            return {
                "event_id": latest.event_id,
                "event_type": latest.event_type.value,
                "outcome": latest.outcome,
                "occurred_at": _iso(latest.occurred_at),
                "artifact_ids": list(latest.artifact_ids),
            }

        return TraceExplanation(
            subject_id,
            tuple(sorted(related)),
            tuple(artifact_ids),
            tuple(sorted(upstream)),
            tuple(sorted(downstream)),
            summary(self.latest_outcome(subject_id)),
            summary(self.latest_outcome(subject_id, planning=True)),
            tuple(sorted(e for e in involved if events[e].blocking)),
            tuple(
                sorted(e for e in involved if events[e].event_type in PLANNING_EVENTS)
            ),
            {e: events[e].event_type.value for e in sorted(involved)},
        )

    def completeness(self, unresolved_reference_count: int = 0) -> TraceCompleteness:
        kinds = {x.event_type for x in self.events}
        by_type: dict[ArtifactType, list[ArtifactReference]] = {}
        for reference in self.artifacts:
            by_type.setdefault(reference.artifact_type, []).append(reference)
        referenced = {a for e in self.events for a in e.artifact_ids}

        def subjects(kind: TraceEventType) -> set[str]:
            return {
                s for e in self.events if e.event_type is kind for s in e.subject_ids
            }

        evidence = [x.artifact_id for x in by_type.get(ArtifactType.EVIDENCE, [])]
        declared, evaluated = subjects(TraceEventType.CLAIM_DECLARED), subjects(
            TraceEventType.CLAIM_EVALUATED
        )
        transitions = [x.artifact_id for x in by_type.get(ArtifactType.TRANSITION, [])]
        evaluated_transitions = {
            a
            for e in self.events
            if e.event_type is TraceEventType.TRANSITION_EVALUATED
            for a in e.artifact_ids
        }
        profiles = [
            x.artifact_id for x in by_type.get(ArtifactType.UNCERTAINTY_PROFILE, [])
        ]
        traced_profiles = {
            a
            for e in self.events
            if e.event_type
            in {
                TraceEventType.UNCERTAINTY_PROPAGATED,
                TraceEventType.UNCERTAINTY_GATE_EVALUATED,
            }
            for a in e.artifact_ids
        }
        proposed = subjects(TraceEventType.ABSTRACTION_PROPOSED)
        decided = (
            subjects(TraceEventType.ABSTRACTION_VERIFIED)
            | subjects(TraceEventType.ABSTRACTION_BLOCKED)
            | subjects(TraceEventType.ABSTRACTION_SUPERSEDED)
        )
        blockers = [
            x for x in self.events if x.event_type is TraceEventType.BLOCKERS_IDENTIFIED
        ]
        downstream = _downstream(self.event_map, {x.event_id for x in blockers})
        planned = sum(
            1
            for x in blockers
            if any(
                self.event_map[d].event_type
                in {
                    TraceEventType.PLAN_CREATED,
                    TraceEventType.REPLAN_CREATED,
                    TraceEventType.PLANNER_ABSTAINED,
                }
                for d in _downstream(self.event_map, {x.event_id})
            )
        )
        del downstream
        return TraceCompleteness(
            _coverage(sum(1 for a in evidence if a in referenced), len(evidence)),
            _coverage(len(declared & evaluated), len(declared)),
            _coverage(
                sum(1 for a in transitions if a in evaluated_transitions),
                len(transitions),
            ),
            _coverage(sum(1 for a in profiles if a in traced_profiles), len(profiles)),
            _coverage(len(proposed & decided), len(proposed)),
            _coverage(planned, len(blockers)),
            unresolved_reference_count,
            {
                k.value: sum(1 for x in self.events if x.event_type is k)
                for k in sorted(kinds, key=lambda k: k.value)
            },
            {
                k.value: len(v)
                for k, v in sorted(by_type.items(), key=lambda kv: kv[0].value)
            },
        )


# --------------------------------------------------------------------------- #
# Artifact references and registry
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = "vera-rap-trace/1"


def _hash_plain(value: Any) -> str:
    return _sha(_canonical({"payload": _plain_json(value)}))


def reference_for(artifact: object) -> ArtifactReference:
    """Build a fingerprint-bound reference for any RAP-001..RAP-008 artifact."""
    from .abstraction import AbstractionGraph, AbstractionNode, AbstractionVerification
    from .claims import ClaimEvaluationResult, ClaimObject
    from .contradictions import ContradictionObject, ContradictionResolutionResult
    from .evidence import EvidenceObject
    from .evidence_graph import EvidenceGraph, SupportCompletenessResult
    from .planner import (
        EpistemicBlocker,
        EvidencePlan,
        PlanExecutionResult,
        PlanningTarget,
    )
    from .transitions import CognitiveTransition, TransitionEvaluation
    from .uncertainty import (
        UncertaintyGateResult,
        UncertaintyProfile,
        UncertaintyPropagationResult,
    )

    def make(
        artifact_id: str,
        kind: ArtifactType,
        digest: str,
        created_at: datetime | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactReference:
        return ArtifactReference(
            artifact_id,
            kind,
            digest,
            SCHEMA_VERSION,
            created_at,
            type(artifact).__module__,
            metadata,
        )

    if isinstance(artifact, EvidenceObject):
        digest = artifact.fingerprint
        return make(
            f"{artifact.evidence_id}@{digest[:12]}",
            ArtifactType.EVIDENCE,
            digest,
            artifact.retrieved_at,
            {
                "evidence_id": artifact.evidence_id,
                "verification_status": artifact.verification_status.value,
                "provenance_fingerprint": _hash_plain(artifact.provenance.to_dict()),
            },
        )
    if isinstance(artifact, ClaimObject):
        return make(
            f"{artifact.claim_id}@v{len(artifact.evaluation_history)}",
            ArtifactType.CLAIM,
            artifact.fingerprint,
            artifact.created_at,
            {
                "claim_id": artifact.claim_id,
                "epistemic_state": artifact.epistemic_state.value,
            },
        )
    if isinstance(artifact, ClaimEvaluationResult):
        digest = _hash_plain(artifact.to_dict())
        return make(
            f"claim-evaluation@{digest[:12]}",
            ArtifactType.CLAIM_EVALUATION,
            digest,
            artifact.evaluated_at,
            {"target_state": artifact.target_state.value},
        )
    if isinstance(artifact, EvidenceGraph):
        digest = artifact.fingerprint
        return make(
            f"evidence-graph@{digest[:12]}", ArtifactType.EVIDENCE_GRAPH, digest, None
        )
    if isinstance(artifact, SupportCompletenessResult):
        payload = {
            item.name: (
                _iso(getattr(artifact, item.name))
                if item.name == "evaluated_at"
                else _plain_json(getattr(artifact, item.name))
            )
            for item in fields(artifact)
        }
        digest = _hash_plain(payload)
        return make(
            f"support:{artifact.claim_id}@{digest[:12]}",
            ArtifactType.SUPPORT_RESULT,
            digest,
            artifact.evaluated_at,
            {"claim_id": artifact.claim_id, "complete": artifact.complete},
        )
    if isinstance(artifact, CognitiveTransition):
        return make(
            artifact.transition_id, ArtifactType.TRANSITION, artifact.fingerprint, None
        )
    if isinstance(artifact, TransitionEvaluation):
        digest = artifact.fingerprint
        return make(
            f"{artifact.transition_id}:evaluation@{digest[:12]}",
            ArtifactType.TRANSITION_EVALUATION,
            digest,
            artifact.evaluated_at,
            {"transition_id": artifact.transition_id, "status": artifact.status.value},
        )
    if isinstance(artifact, ContradictionObject):
        return make(
            f"{artifact.contradiction_id}@v{len(artifact.resolution_history)}",
            ArtifactType.CONTRADICTION,
            artifact.fingerprint,
            artifact.detected_at,
            {
                "contradiction_id": artifact.contradiction_id,
                "status": artifact.status.value,
            },
        )
    if isinstance(artifact, ContradictionResolutionResult):
        digest = artifact.fingerprint
        return make(
            f"resolution@{digest[:12]}",
            ArtifactType.CONTRADICTION_RESOLUTION,
            digest,
            artifact.resolved_at,
            {"target_status": artifact.target_status.value},
        )
    if isinstance(artifact, UncertaintyProfile):
        # RAP-006 reuses declared profile IDs across evaluation instants, so the
        # reference is versioned by fingerprint like every other result artifact.
        digest = artifact.fingerprint
        return make(
            f"{artifact.profile_id}@{digest[:12]}",
            ArtifactType.UNCERTAINTY_PROFILE,
            digest,
            artifact.created_at,
            {"profile_id": artifact.profile_id, "subject_id": artifact.subject_id},
        )
    if isinstance(artifact, UncertaintyPropagationResult):
        digest = artifact.fingerprint
        return make(
            f"propagation:{artifact.target_subject_id}@{digest[:12]}",
            ArtifactType.UNCERTAINTY_PROPAGATION,
            digest,
            artifact.evaluated_at,
        )
    if isinstance(artifact, UncertaintyGateResult):
        digest = _hash_plain(artifact.canonical_dict())
        return make(
            f"gate:{artifact.threshold_id}@{digest[:12]}",
            ArtifactType.UNCERTAINTY_GATE,
            digest,
            None,
            {"threshold_id": artifact.threshold_id, "passed": artifact.passed},
        )
    if isinstance(artifact, AbstractionNode):
        return make(
            f"{artifact.abstraction_id}@v{len(artifact.verification_history)}",
            ArtifactType.ABSTRACTION,
            artifact.fingerprint,
            artifact.created_at,
            {
                "abstraction_id": artifact.abstraction_id,
                "status": artifact.status.value,
            },
        )
    if isinstance(artifact, AbstractionGraph):
        digest = artifact.fingerprint
        return make(
            f"abstraction-graph@{digest[:12]}",
            ArtifactType.ABSTRACTION_GRAPH,
            digest,
            None,
        )
    if isinstance(artifact, AbstractionVerification):
        digest = artifact.fingerprint
        return make(
            f"{artifact.abstraction_id}:verification@{digest[:12]}",
            ArtifactType.ABSTRACTION_VERIFICATION,
            digest,
            artifact.evaluated_at,
            {
                "abstraction_id": artifact.abstraction_id,
                "status": artifact.status.value,
            },
        )
    if isinstance(artifact, PlanningTarget):
        return make(
            f"target:{artifact.target_id}",
            ArtifactType.PLANNING_TARGET,
            artifact.fingerprint,
            None,
            {
                "target_id": artifact.target_id,
                "target_type": artifact.target_type.value,
            },
        )
    if isinstance(artifact, EpistemicBlocker):
        return make(
            artifact.blocker_id,
            ArtifactType.BLOCKER,
            artifact.fingerprint,
            artifact.detected_at,
            {
                "blocker_type": artifact.blocker_type.value,
                "severity": artifact.severity.value,
            },
        )
    if isinstance(artifact, EvidencePlan):
        return make(
            artifact.plan_id,
            ArtifactType.PLAN,
            artifact.fingerprint,
            artifact.created_at,
            {"status": artifact.status.value, "terminal": artifact.terminal},
        )
    if isinstance(artifact, PlanExecutionResult):
        digest = artifact.fingerprint
        return make(
            f"execution:{artifact.plan_id}@{digest[:12]}",
            ArtifactType.PLAN_EXECUTION,
            digest,
            artifact.executed_at,
            {"plan_id": artifact.plan_id},
        )
    raise ValueError(f"unsupported artifact type: {type(artifact).__name__}")


class ArtifactRegistry:
    """Deterministic in-memory identity map used only for trace verification."""

    __slots__ = ("_references",)

    def __init__(self, references: tuple[ArtifactReference, ...] = ()) -> None:
        object.__setattr__(self, "_references", {})
        for reference in references:
            self.register(reference)

    def register(self, reference: ArtifactReference) -> ArtifactReference:
        if not isinstance(reference, ArtifactReference):
            raise ValueError("registry accepts ArtifactReference objects only")
        existing = self._references.get(reference.artifact_id)
        if existing is not None and existing.fingerprint != reference.fingerprint:
            raise ValueError(
                f"artifact {reference.artifact_id} already registered with a different fingerprint"
            )
        self._references[reference.artifact_id] = reference
        return reference

    def register_artifact(self, artifact: object) -> ArtifactReference:
        return self.register(reference_for(artifact))

    def resolve(self, artifact_id: str) -> ArtifactReference | None:
        return self._references.get(artifact_id)

    def verify(self, artifact_id: str, fingerprint: str) -> bool:
        reference = self._references.get(artifact_id)
        return reference is not None and reference.fingerprint == fingerprint

    def references(self) -> tuple[ArtifactReference, ...]:
        return tuple(sorted(self._references.values(), key=lambda x: x.artifact_id))

    def __contains__(self, artifact_id: object) -> bool:
        return artifact_id in self._references

    def __len__(self) -> int:
        return len(self._references)


# --------------------------------------------------------------------------- #
# Validation and replay
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TraceValidationResult:
    valid: bool
    missing_artifacts: tuple[str, ...]
    missing_events: tuple[str, ...]
    fingerprint_mismatches: tuple[str, ...]
    cycles: tuple[str, ...]
    chronology_errors: tuple[str, ...]
    orphan_events: tuple[str, ...]
    unresolved_references: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.valid, bool):
            raise ValueError("valid must be boolean")
        for item in fields(self):
            if item.name != "valid":
                object.__setattr__(
                    self, item.name, _strings(getattr(self, item.name), item.name)
                )
        problems = any(
            getattr(self, name)
            for name in (
                "missing_artifacts",
                "missing_events",
                "fingerprint_mismatches",
                "cycles",
                "chronology_errors",
                "unresolved_references",
            )
        )
        if self.valid is problems:
            raise ValueError("valid flag disagrees with recorded problems")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            item.name: (
                getattr(self, item.name)
                if item.name == "valid"
                else list(getattr(self, item.name))
            )
            for item in fields(self)
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> TraceValidationResult:
        payload = _expect_fields(cls, value, "trace validation result")
        try:
            return cls(
                **{k: (v if k == "valid" else tuple(v)) for k, v in payload.items()}
            )
        except TypeError as exc:
            raise ValueError("trace validation payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> TraceValidationResult:
        return cls.from_dict(_load(serialized))


def _predecessor_errors(trace: CognitiveTrace) -> list[str]:
    events = trace.event_map
    errors: list[str] = []
    for event in trace.events:
        required = REQUIRED_PREDECESSORS.get(event.event_type)
        if not required:
            continue
        upstream_types = {
            events[x].event_type for x in _upstream(events, {event.event_id})
        }
        if not upstream_types & required:
            errors.append(
                f"{event.event_id}:{event.event_type.value} lacks predecessor "
                + "|".join(sorted(x.value for x in required))
            )
    return sorted(errors)


def validate_trace(
    trace: CognitiveTrace, artifact_registry: ArtifactRegistry | None = None
) -> TraceValidationResult:
    """Deterministic structural and identity validation; no scientific recomputation."""
    if not isinstance(trace, CognitiveTrace):
        raise ValueError("validate_trace requires a CognitiveTrace")
    missing_artifacts: set[str] = set()
    mismatches: set[str] = set()
    warnings: set[str] = set()
    cycles: list[str] = []
    try:
        _, missing_events, chronology = _check_dag(trace.events)
    except ValueError as exc:
        cycles, missing_events, chronology = [str(exc)], [], []
    for event in trace.events:
        for artifact_id, digest in event.artifact_fingerprints.items():
            listed = trace.artifact_map.get(artifact_id)
            if listed is None:
                missing_artifacts.add(artifact_id)
            elif listed.fingerprint != digest:
                mismatches.add(f"{artifact_id}:{event.event_id}")
            if artifact_registry is not None:
                registered = artifact_registry.resolve(artifact_id)
                if registered is None:
                    missing_artifacts.add(artifact_id)
                elif registered.fingerprint != digest:
                    mismatches.add(artifact_id)
    if artifact_registry is not None:
        for reference in trace.artifacts:
            registered = artifact_registry.resolve(reference.artifact_id)
            if (
                registered is not None
                and registered.fingerprint != reference.fingerprint
            ):
                mismatches.add(reference.artifact_id)
    orphans = tuple(
        sorted(
            x.event_id
            for x in trace.events
            if not x.input_event_ids and x.event_type in REQUIRED_PREDECESSORS
        )
    )
    unresolved = tuple(_predecessor_errors(trace))
    referenced = {a for e in trace.events for a in e.artifact_ids}
    for reference in trace.artifacts:
        if reference.artifact_id not in referenced:
            warnings.add(
                f"artifact {reference.artifact_id} is listed but never referenced"
            )
    problems = bool(
        missing_artifacts
        or missing_events
        or mismatches
        or cycles
        or chronology
        or unresolved
    )
    return TraceValidationResult(
        not problems,
        tuple(sorted(missing_artifacts)),
        tuple(missing_events),
        tuple(sorted(mismatches)),
        tuple(cycles),
        tuple(chronology),
        orphans,
        unresolved,
        tuple(sorted(warnings)),
    )


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Outcome of walking the event DAG against a registry; no recomputation."""

    trace_id: str
    trace_fingerprint: str
    valid: bool
    replayed_event_ids: tuple[str, ...]
    halted_at_event_id: str | None
    validation: TraceValidationResult
    subject_outcomes: Mapping[str, Any]
    event_type_errors: tuple[str, ...]

    def __post_init__(self) -> None:
        _required_text(self.trace_id, "trace_id")
        _fingerprint_text(self.trace_fingerprint, "trace_fingerprint")
        if not isinstance(self.valid, bool) or not isinstance(
            self.validation, TraceValidationResult
        ):
            raise ValueError("replay result fields are invalid")
        object.__setattr__(self, "replayed_event_ids", tuple(self.replayed_event_ids))
        for item in self.replayed_event_ids:
            _required_text(item, "replayed_event_ids item")
        if self.halted_at_event_id is not None:
            _required_text(self.halted_at_event_id, "halted_at_event_id")
        object.__setattr__(
            self,
            "event_type_errors",
            _strings(self.event_type_errors, "event_type_errors"),
        )
        object.__setattr__(
            self,
            "subject_outcomes",
            _data(self.subject_outcomes, "subject_outcomes", optional=False),
        )
        if self.valid is not (self.validation.valid and not self.event_type_errors):
            raise ValueError("replay validity disagrees with its findings")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "trace_fingerprint": self.trace_fingerprint,
            "valid": self.valid,
            "replayed_event_ids": list(self.replayed_event_ids),
            "halted_at_event_id": self.halted_at_event_id,
            "validation": self.validation.canonical_dict(),
            "subject_outcomes": _plain_json(self.subject_outcomes),
            "event_type_errors": list(self.event_type_errors),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return _sha(self.canonical_json())

    @classmethod
    def from_dict(cls, value: object) -> ReplayResult:
        payload = _expect_fields(cls, value, "replay result")
        try:
            return cls(
                payload["trace_id"],
                payload["trace_fingerprint"],
                payload["valid"],
                tuple(payload["replayed_event_ids"]),
                payload["halted_at_event_id"],
                TraceValidationResult.from_dict(payload["validation"]),
                payload["subject_outcomes"],
                tuple(payload["event_type_errors"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("replay result payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ReplayResult:
        return cls.from_dict(_load(serialized))


_EXPECTED_ARTIFACT_TYPES: dict[TraceEventType, frozenset[ArtifactType]] = {
    TraceEventType.EVIDENCE_REGISTERED: frozenset({ArtifactType.EVIDENCE}),
    TraceEventType.EVIDENCE_VERIFIED: frozenset({ArtifactType.EVIDENCE}),
    TraceEventType.EVIDENCE_REJECTED: frozenset({ArtifactType.EVIDENCE}),
    TraceEventType.EVIDENCE_BECAME_STALE: frozenset({ArtifactType.EVIDENCE}),
    TraceEventType.CLAIM_DECLARED: frozenset({ArtifactType.CLAIM}),
    TraceEventType.CLAIM_EVALUATED: frozenset(
        {ArtifactType.CLAIM, ArtifactType.CLAIM_EVALUATION}
    ),
    TraceEventType.GRAPH_VALIDATED: frozenset({ArtifactType.EVIDENCE_GRAPH}),
    TraceEventType.SUPPORT_EVALUATED: frozenset({ArtifactType.SUPPORT_RESULT}),
    TraceEventType.TRANSITION_EVALUATED: frozenset(
        {ArtifactType.TRANSITION, ArtifactType.TRANSITION_EVALUATION}
    ),
    TraceEventType.CONTRADICTION_DETECTED: frozenset({ArtifactType.CONTRADICTION}),
    TraceEventType.CONTRADICTION_EVALUATED: frozenset(
        {ArtifactType.CONTRADICTION, ArtifactType.CONTRADICTION_RESOLUTION}
    ),
    TraceEventType.UNCERTAINTY_PROPAGATED: frozenset(
        {ArtifactType.UNCERTAINTY_PROPAGATION, ArtifactType.UNCERTAINTY_PROFILE}
    ),
    TraceEventType.UNCERTAINTY_GATE_EVALUATED: frozenset(
        {ArtifactType.UNCERTAINTY_GATE}
    ),
    TraceEventType.ABSTRACTION_PROPOSED: frozenset({ArtifactType.ABSTRACTION}),
    TraceEventType.ABSTRACTION_VERIFIED: frozenset(
        {ArtifactType.ABSTRACTION_VERIFICATION}
    ),
    TraceEventType.ABSTRACTION_BLOCKED: frozenset(
        {ArtifactType.ABSTRACTION_VERIFICATION}
    ),
    TraceEventType.ABSTRACTION_SUPERSEDED: frozenset({ArtifactType.ABSTRACTION}),
    TraceEventType.BLOCKERS_IDENTIFIED: frozenset({ArtifactType.PLANNING_TARGET}),
    TraceEventType.PLAN_CREATED: frozenset({ArtifactType.PLAN}),
    TraceEventType.PLAN_EXECUTION_RECORDED: frozenset({ArtifactType.PLAN_EXECUTION}),
    TraceEventType.REPLAN_CREATED: frozenset({ArtifactType.PLAN}),
    TraceEventType.PLANNER_ABSTAINED: frozenset({ArtifactType.PLAN}),
}


def replay_trace(
    trace: CognitiveTrace, artifact_registry: ArtifactRegistry
) -> ReplayResult:
    """Walk the DAG in topological order checking identity and consistency."""
    if not isinstance(trace, CognitiveTrace) or not isinstance(
        artifact_registry, ArtifactRegistry
    ):
        raise ValueError("replay requires a CognitiveTrace and an ArtifactRegistry")
    validation = validate_trace(trace, artifact_registry)
    errors: set[str] = set()
    replayed: list[str] = []
    halted: str | None = None
    try:
        depth, _, _ = _check_dag(trace.events)
    except ValueError:
        depth = {}
    order = sorted(
        trace.events,
        key=lambda x: (depth.get(x.event_id, 0), _iso(x.occurred_at), x.event_id),
    )
    for event in order:
        required_types = _EXPECTED_ARTIFACT_TYPES.get(event.event_type, frozenset())
        present = {
            trace.artifact_map[a].artifact_type
            for a in event.artifact_ids
            if a in trace.artifact_map
        }
        if required_types and not (present & required_types):
            errors.add(
                f"{event.event_id}:{event.event_type.value} lacks an artifact of type "
                + "|".join(sorted(x.value for x in required_types))
            )
        if event.event_type in OUTCOME_EVENTS and event.outcome is None:
            errors.add(
                f"{event.event_id}:{event.event_type.value} records no outcome code"
            )
        bound = all(
            artifact_registry.verify(a, d)
            for a, d in event.artifact_fingerprints.items()
        )
        if not bound and halted is None:
            halted = event.event_id
            break
        replayed.append(event.event_id)
    outcomes: dict[str, Any] = {}
    for subject in sorted({s for e in trace.events for s in e.subject_ids}):
        latest = trace.latest_outcome(subject)
        planning = trace.latest_outcome(subject, planning=True)
        if latest is not None or planning is not None:
            outcomes[subject] = {
                "outcome": None if latest is None else latest.outcome,
                "event_id": None if latest is None else latest.event_id,
                "planning_outcome": None if planning is None else planning.outcome,
                "planning_event_id": None if planning is None else planning.event_id,
            }
    error_tuple = tuple(sorted(errors))
    return ReplayResult(
        trace.trace_id,
        trace.fingerprint,
        validation.valid and not error_tuple,
        tuple(replayed),
        halted,
        validation,
        outcomes,
        error_tuple,
    )


# --------------------------------------------------------------------------- #
# Builder that consumes existing RAP artifacts without mutating them
# --------------------------------------------------------------------------- #


def _requirement_summary(evaluation: Any) -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": x.requirement_id,
            "requirement_type": x.requirement_type.value,
            "subject_id": x.subject_id,
            "mandatory": x.mandatory,
            "passed": x.passed,
            "failure_status": (
                None if x.failure_status is None else x.failure_status.value
            ),
            "reason": x.reason,
        }
        for x in evaluation.requirement_results
    ]


class CognitiveTraceBuilder:
    """Deterministic builder; every event is derived from an explicit artifact."""

    def __init__(
        self,
        root_subject_ids: tuple[str, ...],
        *,
        started_at: datetime,
        actor_id: str,
        actor_version: str,
        trace_version: str = "1",
        parent: CognitiveTrace | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.root_subject_ids = tuple(root_subject_ids)
        self.started_at = _timestamp(started_at, "started_at")
        self.actor_id = _required_text(actor_id, "actor_id")
        self.actor_version = _required_text(actor_version, "actor_version")
        self.trace_version = trace_version
        self.metadata = metadata
        self.parent = parent
        self.registry = ArtifactRegistry()
        self.events: dict[str, TraceEvent] = {}
        self.latest: dict[str, str] = {}

    # -- core ---------------------------------------------------------------- #

    def inputs_for(self, *subjects: str) -> tuple[str, ...]:
        return tuple(sorted({self.latest[s] for s in subjects if s in self.latest}))

    def event(
        self,
        kind: TraceEventType,
        subjects: tuple[str, ...],
        artifacts: tuple[object, ...],
        *,
        at: datetime,
        details: Mapping[str, Any] | None = None,
        inputs: tuple[str, ...] = (),
        depends_on_subjects: tuple[str, ...] = (),
    ) -> TraceEvent:
        references = tuple(self.registry.register_artifact(a) for a in artifacts)
        input_ids = set(inputs) | set(self.inputs_for(*subjects, *depends_on_subjects))
        event = TraceEvent(
            kind,
            subjects,
            tuple(r.artifact_id for r in references),
            tuple(input_ids),
            at,
            self.actor_id,
            self.actor_version,
            details,
            {r.artifact_id: r.fingerprint for r in references},
        )
        self.events[event.event_id] = event
        for subject in subjects:
            self.latest[subject] = event.event_id
        return event

    def build(self, *, ended_at: datetime | None = None) -> CognitiveTrace:
        return CognitiveTrace(
            self.root_subject_ids,
            tuple(self.events.values()),
            self.registry.references(),
            self.started_at,
            ended_at,
            self.trace_version,
            self.metadata,
            None if self.parent is None else self.parent.trace_id,
            None if self.parent is None else self.parent.fingerprint,
        )

    # -- RAP-001 evidence ---------------------------------------------------- #

    def register_evidence(
        self, evidence: Any, *, at: datetime | None = None
    ) -> TraceEvent:
        when = at or evidence.retrieved_at
        status = evidence.verification_status.value
        registered = self.event(
            TraceEventType.EVIDENCE_REGISTERED,
            (evidence.evidence_id,),
            (evidence,),
            at=when,
            details={
                "verification_status": status,
                "provenance_fingerprint": _hash_plain(evidence.provenance.to_dict()),
                "content_hash": evidence.content_hash,
                "source_id": evidence.source_id,
            },
        )
        follow = {
            "VERIFIED": TraceEventType.EVIDENCE_VERIFIED,
            "REJECTED": TraceEventType.EVIDENCE_REJECTED,
        }.get(status)
        if follow is None:
            return registered
        return self.event(
            follow,
            (evidence.evidence_id,),
            (evidence,),
            at=when,
            details={"outcome": status, "blocking": status == "REJECTED"},
            inputs=(registered.event_id,),
        )

    def evaluate_staleness(self, evidence: Any, *, at: datetime) -> TraceEvent | None:
        if not evidence.is_stale(at=at):
            return None
        return self.event(
            TraceEventType.EVIDENCE_BECAME_STALE,
            (evidence.evidence_id,),
            (evidence,),
            at=at,
            details={
                "outcome": "STALE",
                "blocking": True,
                "valid_until": _iso(evidence.valid_until),
                "evaluated_at": _iso(at),
            },
        )

    # -- RAP-002 claims ------------------------------------------------------ #

    def declare_claim(self, claim: Any, *, at: datetime | None = None) -> TraceEvent:
        return self.event(
            TraceEventType.CLAIM_DECLARED,
            (claim.claim_id,),
            (claim,),
            at=at or claim.created_at,
            details={
                "epistemic_state": claim.epistemic_state.value,
                "predicate": claim.predicate,
                "supporting_evidence_ids": list(claim.supporting_evidence_ids),
                "parent_claim_ids": list(claim.parent_claim_ids),
                "derivation_method": claim.derivation_method,
            },
            depends_on_subjects=(
                *claim.supporting_evidence_ids,
                *claim.parent_claim_ids,
            ),
        )

    def evaluate_claim(self, claim: Any, *, graph: Any = None) -> TraceEvent:
        if not claim.evaluation_history:
            raise ValueError("claim evaluation requires an evaluation record")
        result = claim.evaluation_history[-1]
        evidence: list[object] = []
        if graph is not None:
            for evidence_id in result.supporting_evidence_ids:
                node = graph.nodes.get(evidence_id)
                if node is not None and hasattr(node, "evidence"):
                    evidence.append(node.evidence)
        return self.event(
            TraceEventType.CLAIM_EVALUATED,
            (claim.claim_id,),
            (claim, result, *evidence),
            at=result.evaluated_at,
            details={
                "outcome": result.target_state.value,
                "evaluator_id": result.evaluator_id,
                "evaluator_version": result.evaluator_version,
                "supporting_evidence_ids": list(result.supporting_evidence_ids),
                "contradicting_evidence_ids": list(result.contradicting_evidence_ids),
                "failed_requirements": list(result.failed_requirements),
                "conditions": list(result.conditions),
                "assumptions": list(result.assumptions),
            },
            depends_on_subjects=(
                *result.supporting_evidence_ids,
                *result.contradicting_evidence_ids,
            ),
        )

    # -- RAP-003 graph and support ------------------------------------------- #

    def validate_graph(self, graph: Any, *, at: datetime) -> TraceEvent:
        result = graph.validate_consistency()
        return self.event(
            TraceEventType.GRAPH_VALIDATED,
            tuple(sorted(graph.nodes)),
            (graph,),
            at=at,
            details={
                "outcome": "VALID" if result.valid else "INVALID",
                "blocking": not result.valid,
                "missing_nodes": list(result.missing_nodes),
                "missing_edges": list(result.missing_edges),
                "inconsistent_references": list(result.inconsistent_references),
                "warnings": list(result.warnings),
            },
        )

    def evaluate_support(self, result: Any, graph: Any) -> TraceEvent:
        return self.event(
            TraceEventType.SUPPORT_EVALUATED,
            (result.claim_id,),
            (result, graph),
            at=result.evaluated_at,
            details={
                "outcome": (
                    "SUPPORT_COMPLETE" if result.complete else "SUPPORT_INCOMPLETE"
                ),
                "blocking": not result.complete,
                "supporting_evidence_ids": list(result.supporting_evidence_ids),
                "stale_evidence_ids": list(result.stale_evidence_ids),
                "unverified_evidence_ids": list(result.unverified_evidence_ids),
                "rejected_evidence_ids": list(result.rejected_evidence_ids),
                "contradicted_dependencies": list(result.contradicted_dependencies),
                "missing_constraints": list(result.missing_constraints),
                "failed_constraints": list(result.failed_constraints),
                "upstream_claim_issues": list(result.upstream_claim_issues),
                "unresolved_dependencies": list(result.unresolved_dependencies),
                "reasons": list(result.reasons),
            },
            depends_on_subjects=(
                *result.supporting_evidence_ids,
                *result.stale_evidence_ids,
                *result.unverified_evidence_ids,
                *result.rejected_evidence_ids,
                *result.contradicted_dependencies,
                *result.upstream_claim_issues,
            ),
        )

    # -- RAP-004 transitions ------------------------------------------------- #

    def evaluate_transition(self, evaluation: Any, graph: Any) -> TraceEvent:
        return self.event(
            TraceEventType.TRANSITION_EVALUATED,
            (evaluation.transition_id,),
            (evaluation.transition_definition, evaluation, graph),
            at=evaluation.evaluated_at,
            details={
                "outcome": evaluation.status.value,
                "blocking": not evaluation.allowed,
                "transition_fingerprint": evaluation.transition_fingerprint,
                "evaluation_fingerprint": evaluation.fingerprint,
                "graph_fingerprint": evaluation.graph_fingerprint,
                "mandatory_requirement_results": [
                    x for x in _requirement_summary(evaluation) if x["mandatory"]
                ],
                "optional_requirement_results": [
                    x for x in _requirement_summary(evaluation) if not x["mandatory"]
                ],
                "blocking_requirements": list(evaluation.blocking_requirements),
                "source_state_id": evaluation.source_state.state_id,
                "target_state_id": evaluation.target_state.state_id,
            },
            depends_on_subjects=(*evaluation.claim_ids, *evaluation.evidence_ids),
        )

    # -- RAP-005 contradictions ---------------------------------------------- #

    def detect_contradiction(
        self, contradiction: Any, *, at: datetime | None = None
    ) -> TraceEvent:
        return self.event(
            TraceEventType.CONTRADICTION_DETECTED,
            (
                contradiction.contradiction_id,
                *contradiction.claim_ids,
                *contradiction.evidence_ids,
            ),
            (contradiction,),
            at=at or contradiction.detected_at,
            details={
                "outcome": contradiction.status.value,
                "blocking": True,
                "contradiction_type": contradiction.contradiction_type.value,
                "conflict_dimensions": list(contradiction.conflict_dimensions),
                "conflicting_evidence_ids": list(contradiction.evidence_ids),
                "conflicting_claim_ids": list(contradiction.claim_ids),
                "resolution_requirements": [
                    {
                        "requirement_id": x.requirement_id,
                        "requirement_type": x.requirement_type.value,
                        "mandatory": x.mandatory,
                        "subject_ids": list(x.subject_ids),
                    }
                    for x in contradiction.resolution_requirements
                ],
            },
        )

    def evaluate_contradiction(self, contradiction: Any) -> TraceEvent:
        if not contradiction.resolution_history:
            raise ValueError("contradiction evaluation requires a resolution result")
        result = contradiction.resolution_history[-1]
        terminal = result.target_status.value
        return self.event(
            TraceEventType.CONTRADICTION_EVALUATED,
            (
                contradiction.contradiction_id,
                *contradiction.claim_ids,
                *contradiction.evidence_ids,
            ),
            (contradiction, result),
            at=result.resolved_at,
            details={
                "outcome": terminal,
                "blocking": terminal != "RESOLVED",
                "resolver_id": result.resolver_id,
                "resolver_version": result.resolver_version,
                "resolution_basis": result.resolution_basis,
                "satisfied_requirement_ids": list(result.satisfied_requirement_ids),
                "unsatisfied_requirement_ids": list(result.unsatisfied_requirement_ids),
                "supporting_evidence_ids": list(result.supporting_evidence_ids),
                "rejected_evidence_ids": list(result.rejected_evidence_ids),
                "superseded_claim_ids": list(result.superseded_claim_ids),
                "retained_claim_ids": list(result.retained_claim_ids),
            },
            depends_on_subjects=(
                *result.supporting_evidence_ids,
                *result.rejected_evidence_ids,
            ),
        )

    # -- RAP-006 uncertainty ------------------------------------------------- #

    def propagate_uncertainty(self, result: Any) -> TraceEvent:
        return self.event(
            TraceEventType.UNCERTAINTY_PROPAGATED,
            (result.target_subject_id,),
            (result, result.output_profile, *result.input_profiles),
            at=result.evaluated_at,
            details={
                "propagation_rule_id": result.propagation_rule_id,
                "propagation_rule_version": result.propagation_rule_version,
                "input_profile_fingerprints": {
                    x.profile_id: x.fingerprint for x in result.input_profiles
                },
                "output_profile_fingerprint": result.output_profile.fingerprint,
                "effective_confidence": result.output_profile.effective_confidence,
                "unresolved_components": list(
                    result.output_profile.unresolved_components
                ),
                "warnings": list(result.warnings),
                "assumptions": list(result.assumptions),
            },
            depends_on_subjects=tuple(result.source_subject_ids),
        )

    def evaluate_gate(self, gate: Any, profile: Any, *, at: datetime) -> TraceEvent:
        return self.event(
            TraceEventType.UNCERTAINTY_GATE_EVALUATED,
            (profile.subject_id,),
            (gate, profile),
            at=at,
            details={
                "outcome": "GATE_PASSED" if gate.passed else "GATE_FAILED",
                "blocking": not gate.passed,
                "threshold_id": gate.threshold_id,
                "observed_value": _plain_json(gate.observed_value),
                "required_value": _plain_json(gate.required_value),
                "blocking_components": list(gate.blocking_components),
                "reason": gate.reason,
            },
        )

    # -- RAP-007 abstractions ------------------------------------------------ #

    def propose_abstraction(
        self, node: Any, *, abstraction_graph: Any = None
    ) -> TraceEvent:
        artifacts: tuple[object, ...] = (
            (node,) if abstraction_graph is None else (node, abstraction_graph)
        )
        return self.event(
            TraceEventType.ABSTRACTION_PROPOSED,
            (node.abstraction_id,),
            artifacts,
            at=node.created_at,
            details={
                "abstraction_level": node.abstraction_level.name,
                "concept_type": node.concept_type,
                "status": node.status.value,
                "claim_ids": list(node.claim_ids),
                "source_abstraction_ids": list(node.source_abstraction_ids),
            },
            depends_on_subjects=(*node.claim_ids, *node.source_abstraction_ids),
        )

    def verify_abstraction(
        self, verification: Any, *, node: Any = None, evidence_graph: Any = None
    ) -> TraceEvent:
        status = verification.status.value
        kind = (
            TraceEventType.ABSTRACTION_VERIFIED
            if status == "VERIFIED"
            else TraceEventType.ABSTRACTION_BLOCKED
        )
        artifacts: list[object] = [verification]
        if node is not None:
            artifacts.append(node)
        if evidence_graph is not None:
            artifacts.append(evidence_graph)
        return self.event(
            kind,
            (verification.abstraction_id,),
            tuple(artifacts),
            at=verification.evaluated_at,
            details={
                "outcome": status,
                "blocking": status != "VERIFIED",
                "support_completeness": [
                    list(x) for x in verification.support_completeness
                ],
                "transition_evaluation_ids": list(
                    verification.transition_evaluation_ids
                ),
                "contradiction_ids": list(verification.contradiction_ids),
                "uncertainty_gate_results": [
                    x.canonical_dict() for x in verification.uncertainty_gate_results
                ],
                "failed_requirements": [
                    x.value for x in verification.failed_requirements
                ],
                "graph_fingerprint": verification.graph_fingerprint,
                "verifier_id": verification.verifier_id,
                "verifier_version": verification.verifier_version,
            },
            depends_on_subjects=(
                *verification.claim_ids,
                *verification.source_abstraction_ids,
                *verification.transition_evaluation_ids,
                *verification.contradiction_ids,
            ),
        )

    def supersede_abstraction(self, node: Any, *, at: datetime) -> TraceEvent:
        return self.event(
            TraceEventType.ABSTRACTION_SUPERSEDED,
            (node.abstraction_id,),
            (node,),
            at=at,
            details={"outcome": "SUPERSEDED", "superseded_by": node.superseded_by},
        )

    # -- RAP-008 planning ---------------------------------------------------- #

    @staticmethod
    def _target_subjects(target: Any) -> tuple[str, ...]:
        return tuple(
            sorted(
                {target.target_id}
                | {
                    x
                    for x in (
                        target.claim_id,
                        target.transition_id,
                        target.abstraction_id,
                    )
                    if x
                }
            )
        )

    def identify_blockers(
        self, target: Any, blockers: tuple[Any, ...], *, at: datetime
    ) -> TraceEvent:
        return self.event(
            TraceEventType.BLOCKERS_IDENTIFIED,
            self._target_subjects(target),
            (target, *blockers),
            at=at,
            details={
                "outcome": (
                    "BLOCKED" if any(x.blocking for x in blockers) else "ADMISSIBLE"
                ),
                "blocking": any(x.blocking for x in blockers),
                "blocker_types": {x.blocker_id: x.blocker_type.value for x in blockers},
                "blocker_severities": {
                    x.blocker_id: x.severity.value for x in blockers
                },
                "blocker_subjects": {x.blocker_id: x.subject_id for x in blockers},
                "caused_by": {
                    x.blocker_id: list(x.caused_by) for x in blockers if x.caused_by
                },
            },
            depends_on_subjects=tuple(x.subject_id for x in blockers),
        )

    def record_plan(self, plan: Any, *, inputs: tuple[str, ...] = ()) -> TraceEvent:
        status = plan.status.value
        if status == "ABSTAINED":
            kind = TraceEventType.PLANNER_ABSTAINED
        elif plan.previous_plan_id is not None:
            kind = TraceEventType.REPLAN_CREATED
        else:
            kind = TraceEventType.PLAN_CREATED
        return self.event(
            kind,
            self._target_subjects(plan.target),
            (plan,),
            at=plan.created_at,
            details={
                "outcome": status,
                "blocking": plan.terminal and status == "ABSTAINED",
                "terminal": plan.terminal,
                "abstain_reason": plan.abstain_reason,
                "previous_plan_id": plan.previous_plan_id,
                "no_progress_count": plan.no_progress_count,
                "blocker_ids": [x.blocker_id for x in plan.blockers],
                "action_types": {
                    x.action_id: x.action_type.value for x in plan.actions
                },
                "action_blockers": {
                    x.action_id: list(x.addresses_blocker_ids) for x in plan.actions
                },
                "action_preconditions": {
                    x.action_id: list(x.preconditions) for x in plan.actions
                },
                "graph_fingerprint": plan.graph_fingerprint,
            },
            inputs=inputs,
        )

    def record_execution(
        self, result: Any, plan: Any, *, inputs: tuple[str, ...] = ()
    ) -> TraceEvent:
        if result.plan_id != plan.plan_id:
            raise ValueError("execution result does not belong to the plan")
        return self.event(
            TraceEventType.PLAN_EXECUTION_RECORDED,
            self._target_subjects(plan.target),
            (result, plan),
            at=result.executed_at,
            details={
                "executor_id": result.executor_id,
                "executor_version": result.executor_version,
                "completed_action_ids": list(result.completed_action_ids),
                "failed_action_ids": list(result.failed_action_ids),
                "new_evidence_ids": list(result.new_evidence_ids),
                "new_claim_ids": list(result.new_claim_ids),
                "new_transition_evaluation_ids": list(
                    result.new_transition_evaluation_ids
                ),
                "new_contradiction_ids": list(result.new_contradiction_ids),
                "new_uncertainty_profile_ids": list(result.new_uncertainty_profile_ids),
                "new_abstraction_verification_ids": list(
                    result.new_abstraction_verification_ids
                ),
            },
            inputs=inputs,
        )

    # -- checkpoints --------------------------------------------------------- #

    def checkpoint(
        self,
        *,
        at: datetime,
        evidence_graph: Any = None,
        abstraction_graph: Any = None,
        plan: Any = None,
        admissible_state: Mapping[str, str] | None = None,
    ) -> TraceEvent:
        artifacts = tuple(
            x for x in (evidence_graph, abstraction_graph, plan) if x is not None
        )
        return self.event(
            TraceEventType.TRACE_CHECKPOINT,
            self.root_subject_ids,
            artifacts,
            at=at,
            details={
                "evidence_graph_fingerprint": (
                    None if evidence_graph is None else evidence_graph.fingerprint
                ),
                "abstraction_graph_fingerprint": (
                    None if abstraction_graph is None else abstraction_graph.fingerprint
                ),
                "plan_fingerprint": None if plan is None else plan.fingerprint,
                "admissible_state": dict(admissible_state or {}),
            },
            inputs=self.inputs_for(*self.latest),
        )
