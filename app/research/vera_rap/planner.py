"""Adaptive Evidence Planner for isolated VERA-RAP research (RAP-008).

Plan to resolve evidence deficits, not plan to generate an answer. The planner
reads explicit epistemic blockers derived from RAP-003..RAP-007 artifacts and
proposes evidence or verification actions. It never grants permission: it
cannot mark a claim SUPPORTED, a transition ALLOWED, a contradiction RESOLVED,
or an abstraction VERIFIED, and it performs no retrieval or execution.
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

from .abstraction import (
    AbstractionFailure,
    AbstractionGraph,
    AbstractionStatus,
    AbstractionVerification,
)
from .claims import EpistemicState
from .contradictions import ContradictionObject, ContradictionStatus
from .evidence import (
    VerificationStatus,
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)
from .evidence_graph import ClaimNode, EvidenceGraph, EvidenceNode
from .transitions import (
    RequirementEvaluation,
    RequirementType,
    TransitionEvaluation,
    TransitionStatus,
)
from .uncertainty import UncertaintyGateResult, UncertaintyProfile


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as boolean")


class PlanningTargetType(_StrictEnum):
    CLAIM_SUPPORT = "CLAIM_SUPPORT"
    TRANSITION_PERMISSION = "TRANSITION_PERMISSION"
    CONTRADICTION_RESOLUTION = "CONTRADICTION_RESOLUTION"
    UNCERTAINTY_REDUCTION = "UNCERTAINTY_REDUCTION"
    ABSTRACTION_VERIFICATION = "ABSTRACTION_VERIFICATION"


class BlockerType(_StrictEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNVERIFIED_EVIDENCE = "UNVERIFIED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    REJECTED_EVIDENCE = "REJECTED_EVIDENCE"
    SUPPORT_INCOMPLETE = "SUPPORT_INCOMPLETE"
    UNRESOLVED_CONTRADICTION = "UNRESOLVED_CONTRADICTION"
    CONTRADICTION_RESOLUTION_PENDING = "CONTRADICTION_RESOLUTION_PENDING"
    EXCESSIVE_UNCERTAINTY = "EXCESSIVE_UNCERTAINTY"
    MISSING_UNCERTAINTY = "MISSING_UNCERTAINTY"
    CONSTRAINT_UNRESOLVED = "CONSTRAINT_UNRESOLVED"
    CONSTRAINT_VIOLATED = "CONSTRAINT_VIOLATED"
    MISSING_TRANSFORMATION = "MISSING_TRANSFORMATION"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    INVALID_CLAIM_STATE = "INVALID_CLAIM_STATE"
    TRANSITION_BLOCKED = "TRANSITION_BLOCKED"
    ABSTRACTION_BLOCKED = "ABSTRACTION_BLOCKED"
    LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"
    NO_ADMISSIBLE_RESOLUTION_PATH = "NO_ADMISSIBLE_RESOLUTION_PATH"


class BlockerSeverity(_StrictEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"
    TERMINAL = "TERMINAL"


class EvidenceActionType(_StrictEnum):
    RETRIEVE_EVIDENCE = "RETRIEVE_EVIDENCE"
    REQUEST_INDEPENDENT_EVIDENCE = "REQUEST_INDEPENDENT_EVIDENCE"
    REFRESH_STALE_EVIDENCE = "REFRESH_STALE_EVIDENCE"
    VERIFY_EVIDENCE = "VERIFY_EVIDENCE"
    REVERIFY_PROVENANCE = "REVERIFY_PROVENANCE"
    NORMALIZE_UNIT = "NORMALIZE_UNIT"
    VERIFY_TRANSFORMATION = "VERIFY_TRANSFORMATION"
    ADD_TRANSFORMATION = "ADD_TRANSFORMATION"
    RECONCILE_SCOPE = "RECONCILE_SCOPE"
    RECONCILE_TIME_WINDOW = "RECONCILE_TIME_WINDOW"
    REEVALUATE_CONSTRAINT = "REEVALUATE_CONSTRAINT"
    REQUEST_HUMAN_REVIEW = "REQUEST_HUMAN_REVIEW"
    REDUCE_UNCERTAINTY = "REDUCE_UNCERTAINTY"
    RESOLVE_CONTRADICTION_REQUIREMENT = "RESOLVE_CONTRADICTION_REQUIREMENT"
    RECOMPUTE_SUPPORT = "RECOMPUTE_SUPPORT"
    REEVALUATE_TRANSITION = "REEVALUATE_TRANSITION"
    REEVALUATE_ABSTRACTION = "REEVALUATE_ABSTRACTION"
    ABSTAIN = "ABSTAIN"


class PlanStatus(_StrictEnum):
    READY = "READY"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"


# Documented, fixed action priority. Lower comes first; never insertion order.
_ACTION_PRIORITY: dict[EvidenceActionType, int] = {
    EvidenceActionType.RETRIEVE_EVIDENCE: 1,
    EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE: 1,
    EvidenceActionType.ADD_TRANSFORMATION: 1,
    EvidenceActionType.REVERIFY_PROVENANCE: 1,
    EvidenceActionType.NORMALIZE_UNIT: 1,
    EvidenceActionType.RECONCILE_SCOPE: 1,
    EvidenceActionType.RECONCILE_TIME_WINDOW: 1,
    EvidenceActionType.REFRESH_STALE_EVIDENCE: 2,
    EvidenceActionType.VERIFY_EVIDENCE: 3,
    EvidenceActionType.VERIFY_TRANSFORMATION: 3,
    EvidenceActionType.REQUEST_HUMAN_REVIEW: 4,
    EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT: 4,
    EvidenceActionType.REDUCE_UNCERTAINTY: 5,
    EvidenceActionType.REEVALUATE_CONSTRAINT: 6,
    EvidenceActionType.RECOMPUTE_SUPPORT: 7,
    EvidenceActionType.REEVALUATE_TRANSITION: 8,
    EvidenceActionType.REEVALUATE_ABSTRACTION: 9,
    EvidenceActionType.ABSTAIN: 10,
}
_EVIDENCE_ACTIONS = frozenset(
    {
        EvidenceActionType.RETRIEVE_EVIDENCE,
        EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        EvidenceActionType.REFRESH_STALE_EVIDENCE,
    }
)
_REEVALUATION_ACTIONS = frozenset(
    {
        EvidenceActionType.RECOMPUTE_SUPPORT,
        EvidenceActionType.REEVALUATE_TRANSITION,
        EvidenceActionType.REEVALUATE_ABSTRACTION,
    }
)
# Which action types can affect which blocker type (admissibility table).
_ADMISSIBLE_ACTIONS: dict[BlockerType, frozenset[EvidenceActionType]] = {
    BlockerType.MISSING_EVIDENCE: frozenset(
        {
            EvidenceActionType.RETRIEVE_EVIDENCE,
            EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        }
    ),
    BlockerType.UNVERIFIED_EVIDENCE: frozenset(
        {EvidenceActionType.VERIFY_EVIDENCE, EvidenceActionType.REVERIFY_PROVENANCE}
    ),
    BlockerType.STALE_EVIDENCE: frozenset({EvidenceActionType.REFRESH_STALE_EVIDENCE}),
    BlockerType.REJECTED_EVIDENCE: frozenset(
        {EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE}
    ),
    BlockerType.SUPPORT_INCOMPLETE: frozenset({EvidenceActionType.RECOMPUTE_SUPPORT}),
    BlockerType.UNRESOLVED_CONTRADICTION: frozenset(
        {
            EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
            EvidenceActionType.REVERIFY_PROVENANCE,
            EvidenceActionType.NORMALIZE_UNIT,
            EvidenceActionType.VERIFY_TRANSFORMATION,
            EvidenceActionType.RECONCILE_SCOPE,
            EvidenceActionType.RECONCILE_TIME_WINDOW,
            EvidenceActionType.REEVALUATE_CONSTRAINT,
            EvidenceActionType.REQUEST_HUMAN_REVIEW,
            EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT,
        }
    ),
    BlockerType.CONTRADICTION_RESOLUTION_PENDING: frozenset(
        {EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT}
    ),
    BlockerType.EXCESSIVE_UNCERTAINTY: frozenset(
        {
            EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
            EvidenceActionType.REFRESH_STALE_EVIDENCE,
            EvidenceActionType.VERIFY_TRANSFORMATION,
            EvidenceActionType.REDUCE_UNCERTAINTY,
        }
    ),
    BlockerType.MISSING_UNCERTAINTY: frozenset(
        {
            EvidenceActionType.RETRIEVE_EVIDENCE,
            EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        }
    ),
    BlockerType.CONSTRAINT_UNRESOLVED: frozenset(
        {EvidenceActionType.REEVALUATE_CONSTRAINT}
    ),
    BlockerType.CONSTRAINT_VIOLATED: frozenset(
        {EvidenceActionType.REEVALUATE_CONSTRAINT}
    ),
    BlockerType.MISSING_TRANSFORMATION: frozenset(
        {
            EvidenceActionType.ADD_TRANSFORMATION,
            EvidenceActionType.VERIFY_TRANSFORMATION,
        }
    ),
    BlockerType.MISSING_DEPENDENCY: frozenset(
        {
            EvidenceActionType.RETRIEVE_EVIDENCE,
            EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
        }
    ),
    BlockerType.INVALID_CLAIM_STATE: frozenset({EvidenceActionType.RECOMPUTE_SUPPORT}),
    BlockerType.TRANSITION_BLOCKED: frozenset(
        {EvidenceActionType.REEVALUATE_TRANSITION}
    ),
    BlockerType.ABSTRACTION_BLOCKED: frozenset(
        {EvidenceActionType.REEVALUATE_ABSTRACTION}
    ),
    BlockerType.LINEAGE_INCOMPLETE: frozenset(
        {EvidenceActionType.RETRIEVE_EVIDENCE, EvidenceActionType.RECOMPUTE_SUPPORT}
    ),
    BlockerType.NO_ADMISSIBLE_RESOLUTION_PATH: frozenset({EvidenceActionType.ABSTAIN}),
}
# Parameters that would imply direct status mutation or gate bypass.
_FORBIDDEN_PARAMETERS = frozenset(
    {
        "set_status",
        "mark_valid",
        "mark_supported",
        "mark_resolved",
        "force",
        "override",
        "ignore_staleness",
        "use_anyway",
        "bypass",
        "model_confidence",
    }
)
_ACTIVE_CONTRADICTION = frozenset(
    {ContradictionStatus.DETECTED, ContradictionStatus.UNRESOLVED}
)
_TOKEN = object()
NO_ADMISSIBLE_RESOLUTION_PATH = "NO_ADMISSIBLE_RESOLUTION_PATH"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(payload).encode()).hexdigest()}"


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


def _number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number or null")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number or null")
    return float(value)


def _mapping(value: object, name: str, *, optional: bool = False) -> Any:
    frozen = _freeze_json(value, name)
    if frozen is None and optional:
        return None
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{name} must be an object")
    forbidden = _FORBIDDEN_PARAMETERS & set(frozen)
    if forbidden:
        raise ValueError(
            f"{name} implies status mutation: {', '.join(sorted(forbidden))}"
        )
    return frozen


@dataclass(frozen=True, slots=True)
class PlanningTarget:
    """What the planner is trying to make attainable; never a result."""

    target_id: str
    target_type: PlanningTargetType
    claim_id: str | None = None
    transition_id: str | None = None
    abstraction_id: str | None = None
    desired_state: str = "ADMISSIBLE"
    scope: Any = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _required_text(self.target_id, "target_id")
        _required_text(self.desired_state, "desired_state")
        if not isinstance(self.target_type, PlanningTargetType):
            raise ValueError("target_type must be a PlanningTargetType")
        for name in ("claim_id", "transition_id", "abstraction_id"):
            if getattr(self, name) is not None:
                _required_text(getattr(self, name), name)
        needs = {
            PlanningTargetType.CLAIM_SUPPORT: "claim_id",
            PlanningTargetType.TRANSITION_PERMISSION: "transition_id",
            PlanningTargetType.ABSTRACTION_VERIFICATION: "abstraction_id",
            PlanningTargetType.UNCERTAINTY_REDUCTION: "claim_id",
        }
        required = needs.get(self.target_type)
        if required and getattr(self, required) is None:
            raise ValueError(f"{self.target_type.value} target requires {required}")
        object.__setattr__(self, "scope", _freeze_json(self.scope, "scope"))
        object.__setattr__(
            self, "metadata", _mapping(self.metadata, "metadata", optional=True)
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type.value,
            "claim_id": self.claim_id,
            "transition_id": self.transition_id,
            "abstraction_id": self.abstraction_id,
            "desired_state": self.desired_state,
            "scope": _plain_json(self.scope),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> PlanningTarget:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("planning target fields do not match schema")
        try:
            return cls(
                **{**value, "target_type": PlanningTargetType(value["target_type"])}
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("planning target payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> PlanningTarget:
        return cls.from_dict(_load(serialized))


def _load(serialized: str) -> Any:
    if not isinstance(serialized, str):
        raise ValueError("serialized payload must be text")
    try:
        return json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("serialized payload must be valid JSON") from exc


@dataclass(frozen=True, slots=True)
class EpistemicBlocker:
    """One explicit, machine-readable reason the target is not admissible."""

    blocker_type: BlockerType
    subject_id: str
    source_artifact_id: str | None
    severity: BlockerSeverity
    resolvable: bool
    requirements: tuple[str, ...]
    details: Mapping[str, Any]
    detected_at: datetime
    caused_by: tuple[str, ...] = ()
    blocker_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.blocker_type, BlockerType) or not isinstance(
            self.severity, BlockerSeverity
        ):
            raise ValueError("blocker type and severity must be enum members")
        _required_text(self.subject_id, "subject_id")
        if self.source_artifact_id is not None:
            _required_text(self.source_artifact_id, "source_artifact_id")
        if not isinstance(self.resolvable, bool):
            raise ValueError("resolvable must be boolean")
        if self.severity is BlockerSeverity.TERMINAL and self.resolvable:
            raise ValueError("a TERMINAL blocker cannot be resolvable")
        object.__setattr__(
            self, "requirements", _strings(self.requirements, "requirements")
        )
        object.__setattr__(self, "caused_by", _strings(self.caused_by, "caused_by"))
        object.__setattr__(self, "details", _mapping(self.details, "details"))
        _timestamp(self.detected_at, "detected_at")
        # Identity excludes detection time and the artifact it was found through,
        # so one underlying fact is one blocker however many symptoms expose it.
        object.__setattr__(
            self,
            "blocker_id",
            _digest(
                "blocker",
                {
                    "blocker_type": self.blocker_type.value,
                    "subject_id": self.subject_id,
                    "requirements": list(self.requirements),
                },
            ),
        )
        if self.blocker_id in self.caused_by:
            raise ValueError("a blocker cannot cause itself")

    @property
    def blocking(self) -> bool:
        return self.severity in {BlockerSeverity.BLOCKING, BlockerSeverity.TERMINAL}

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "blocker_type": self.blocker_type.value,
            "subject_id": self.subject_id,
            "source_artifact_id": self.source_artifact_id,
            "severity": self.severity.value,
            "resolvable": self.resolvable,
            "requirements": list(self.requirements),
            "details": _plain_json(self.details),
            "detected_at": _iso(self.detected_at),
            "caused_by": list(self.caused_by),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> EpistemicBlocker:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("epistemic blocker fields do not match schema")
        try:
            result = cls(
                BlockerType(value["blocker_type"]),
                value["subject_id"],
                value["source_artifact_id"],
                BlockerSeverity(value["severity"]),
                value["resolvable"],
                tuple(value["requirements"]),
                value["details"],
                _parse_timestamp(value["detected_at"], "detected_at"),
                tuple(value["caused_by"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("epistemic blocker payload is malformed") from exc
        if result.blocker_id != value["blocker_id"]:
            raise ValueError("blocker_id does not match blocker content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EpistemicBlocker:
        return cls.from_dict(_load(serialized))


@dataclass(frozen=True, slots=True)
class EvidenceAction:
    """A proposed evidence or verification action; a plan is not evidence."""

    action_type: EvidenceActionType
    subject_ids: tuple[str, ...]
    addresses_blocker_ids: tuple[str, ...]
    parameters: Mapping[str, Any]
    preconditions: tuple[str, ...]
    expected_effect: str
    estimated_cost: float | None
    estimated_information_gain: float | None
    mandatory: bool
    metadata: Mapping[str, Any] | None = None
    action_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, EvidenceActionType):
            raise ValueError("action_type must be an EvidenceActionType")
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be boolean")
        _required_text(self.expected_effect, "expected_effect")
        object.__setattr__(
            self,
            "subject_ids",
            _strings(self.subject_ids, "subject_ids", allow_empty=False),
        )
        object.__setattr__(
            self,
            "addresses_blocker_ids",
            _strings(
                self.addresses_blocker_ids, "addresses_blocker_ids", allow_empty=False
            ),
        )
        object.__setattr__(
            self, "preconditions", _strings(self.preconditions, "preconditions")
        )
        object.__setattr__(self, "parameters", _mapping(self.parameters, "parameters"))
        object.__setattr__(
            self, "metadata", _mapping(self.metadata, "metadata", optional=True)
        )
        object.__setattr__(
            self, "estimated_cost", _number(self.estimated_cost, "estimated_cost")
        )
        gain = _number(self.estimated_information_gain, "estimated_information_gain")
        if gain is not None and gain > 1:
            raise ValueError("estimated_information_gain must be within [0, 1]")
        object.__setattr__(self, "estimated_information_gain", gain)
        object.__setattr__(
            self,
            "action_id",
            _digest(
                "action",
                {
                    "action_type": self.action_type.value,
                    "subject_ids": list(self.subject_ids),
                    "parameters": _plain_json(self.parameters),
                },
            ),
        )
        if self.action_id in self.preconditions:
            raise ValueError("an action cannot be its own precondition")

    @property
    def priority(self) -> int:
        return _ACTION_PRIORITY[self.action_type]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "subject_ids": list(self.subject_ids),
            "addresses_blocker_ids": list(self.addresses_blocker_ids),
            "parameters": _plain_json(self.parameters),
            "preconditions": list(self.preconditions),
            "expected_effect": self.expected_effect,
            "estimated_cost": self.estimated_cost,
            "estimated_information_gain": self.estimated_information_gain,
            "mandatory": self.mandatory,
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> EvidenceAction:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("evidence action fields do not match schema")
        try:
            result = cls(
                EvidenceActionType(value["action_type"]),
                tuple(value["subject_ids"]),
                tuple(value["addresses_blocker_ids"]),
                value["parameters"],
                tuple(value["preconditions"]),
                value["expected_effect"],
                value["estimated_cost"],
                value["estimated_information_gain"],
                value["mandatory"],
                value["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("evidence action payload is malformed") from exc
        if result.action_id != value["action_id"]:
            raise ValueError("action_id does not match action content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EvidenceAction:
        return cls.from_dict(_load(serialized))


def _action_depth(actions: Mapping[str, EvidenceAction]) -> dict[str, int]:
    depth: dict[str, int] = {}
    active: set[str] = set()

    def visit(action_id: str) -> int:
        if action_id in depth:
            return depth[action_id]
        if action_id in active:
            raise ValueError("action preconditions form a cycle")
        active.add(action_id)
        items = actions[action_id].preconditions
        depth[action_id] = 0 if not items else 1 + max(visit(x) for x in items)
        active.remove(action_id)
        return depth[action_id]

    for action_id in sorted(actions):
        visit(action_id)
    return depth


def _derive_status(
    blockers: tuple[EpistemicBlocker, ...],
    actions: tuple[EvidenceAction, ...],
    no_progress_count: int,
    completed: bool,
) -> PlanStatus:
    blocking = [x for x in blockers if x.blocking]
    if any(x.severity is BlockerSeverity.TERMINAL for x in blockers) or any(
        x.action_type is EvidenceActionType.ABSTAIN for x in actions
    ):
        return PlanStatus.ABSTAINED
    if completed:
        return PlanStatus.COMPLETED
    mandatory = [x for x in actions if x.mandatory]
    if not blocking or not mandatory or no_progress_count > 0:
        return PlanStatus.BLOCKED
    types = {x.action_type for x in mandatory}
    if EvidenceActionType.REQUEST_HUMAN_REVIEW in types:
        return PlanStatus.WAITING_FOR_REVIEW
    if types & _EVIDENCE_ACTIONS:
        return PlanStatus.WAITING_FOR_EVIDENCE
    return PlanStatus.READY


@dataclass(frozen=True, slots=True, init=False)
class EvidencePlan:
    """Immutable, deterministic plan; explains which action addresses which blocker."""

    target: PlanningTarget
    blockers: tuple[EpistemicBlocker, ...]
    actions: tuple[EvidenceAction, ...]
    terminal: bool
    abstain_reason: str | None
    status: PlanStatus
    planner_id: str
    planner_version: str
    created_at: datetime
    graph_fingerprint: str | None
    previous_plan_id: str | None
    no_progress_count: int
    metadata: Mapping[str, Any] | None
    plan_id: str

    def __init__(
        self,
        target: PlanningTarget,
        blockers: tuple[EpistemicBlocker, ...],
        actions: tuple[EvidenceAction, ...],
        terminal: bool,
        abstain_reason: str | None,
        status: PlanStatus,
        planner_id: str,
        planner_version: str,
        created_at: datetime,
        graph_fingerprint: str | None = None,
        previous_plan_id: str | None = None,
        no_progress_count: int = 0,
        metadata: Mapping[str, Any] | None = None,
        *,
        _token: object | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            if item.name != "plan_id":
                object.__setattr__(self, item.name, values[item.name])
        if not isinstance(self.target, PlanningTarget):
            raise ValueError("target must be a PlanningTarget")
        if not isinstance(self.status, PlanStatus) or not isinstance(
            self.terminal, bool
        ):
            raise ValueError("plan status and terminal flag are invalid")
        for name in ("planner_id", "planner_version"):
            _required_text(getattr(self, name), name)
        for name in ("graph_fingerprint", "previous_plan_id", "abstain_reason"):
            if getattr(self, name) is not None:
                _required_text(getattr(self, name), name)
        if (
            isinstance(self.no_progress_count, bool)
            or not isinstance(self.no_progress_count, int)
            or self.no_progress_count < 0
        ):
            raise ValueError("no_progress_count must be a non-negative integer")
        _timestamp(self.created_at, "created_at")
        blockers = tuple(self.blockers)
        if any(not isinstance(x, EpistemicBlocker) for x in blockers):
            raise ValueError("blockers must contain EpistemicBlocker objects")
        blocker_ids = {x.blocker_id for x in blockers}
        if len(blocker_ids) != len(blockers):
            raise ValueError("duplicate blocker identity")
        for blocker in blockers:
            if not set(blocker.caused_by).issubset(blocker_ids):
                raise ValueError("blocker cause references an unknown blocker")
        order = tuple(BlockerType)
        object.__setattr__(
            self,
            "blockers",
            tuple(
                sorted(
                    blockers, key=lambda x: (order.index(x.blocker_type), x.blocker_id)
                )
            ),
        )
        actions = tuple(self.actions)
        if any(not isinstance(x, EvidenceAction) for x in actions):
            raise ValueError("actions must contain EvidenceAction objects")
        action_map = {x.action_id: x for x in actions}
        if len(action_map) != len(actions):
            raise ValueError("duplicate action identity")
        for action in actions:
            if not set(action.addresses_blocker_ids).issubset(blocker_ids):
                raise ValueError("action addresses an unknown blocker")
            if not set(action.preconditions).issubset(action_map):
                raise ValueError("action precondition references an unknown action")
        depth = _action_depth(action_map)
        object.__setattr__(
            self,
            "actions",
            tuple(
                sorted(
                    actions, key=lambda x: (x.priority, depth[x.action_id], x.action_id)
                )
            ),
        )
        object.__setattr__(
            self, "metadata", _mapping(self.metadata, "metadata", optional=True)
        )
        expected = _derive_status(
            self.blockers, self.actions, self.no_progress_count, _token is _TOKEN
        )
        if self.status is not expected:
            raise ValueError("plan status is inconsistent with blockers and actions")
        if self.status is PlanStatus.COMPLETED and (
            any(x.blocking for x in blockers) or actions
        ):
            raise ValueError("COMPLETED requires a re-evaluated admissible target")
        if self.terminal is not (
            self.status in {PlanStatus.COMPLETED, PlanStatus.ABSTAINED}
        ):
            raise ValueError("terminal flag disagrees with plan status")
        if (self.abstain_reason is not None) is not (
            self.status is PlanStatus.ABSTAINED
        ):
            raise ValueError("abstain_reason is present exactly when the plan abstains")
        object.__setattr__(self, "plan_id", _digest("plan", self._content_dict()))

    def _content_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.canonical_dict(),
            "blockers": [x.canonical_dict() for x in self.blockers],
            "actions": [x.canonical_dict() for x in self.actions],
            "terminal": self.terminal,
            "abstain_reason": self.abstain_reason,
            "status": self.status.value,
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
            "created_at": _iso(self.created_at),
            "graph_fingerprint": self.graph_fingerprint,
            "previous_plan_id": self.previous_plan_id,
            "no_progress_count": self.no_progress_count,
            "metadata": _plain_json(self.metadata),
        }

    @property
    def blocking_blockers(self) -> tuple[EpistemicBlocker, ...]:
        return tuple(x for x in self.blockers if x.blocking)

    @property
    def mandatory_actions(self) -> tuple[EvidenceAction, ...]:
        return tuple(x for x in self.actions if x.mandatory)

    def actions_for(self, blocker_id: str) -> tuple[EvidenceAction, ...]:
        return tuple(x for x in self.actions if blocker_id in x.addresses_blocker_ids)

    def canonical_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, **self._content_dict()}

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> EvidencePlan:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("evidence plan fields do not match schema")
        try:
            status = PlanStatus(value["status"])
            result = cls(
                PlanningTarget.from_dict(value["target"]),
                tuple(EpistemicBlocker.from_dict(x) for x in value["blockers"]),
                tuple(EvidenceAction.from_dict(x) for x in value["actions"]),
                value["terminal"],
                value["abstain_reason"],
                status,
                value["planner_id"],
                value["planner_version"],
                _parse_timestamp(value["created_at"], "created_at"),
                value["graph_fingerprint"],
                value["previous_plan_id"],
                value["no_progress_count"],
                value["metadata"],
                _token=_TOKEN if status is PlanStatus.COMPLETED else None,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("evidence plan payload is malformed") from exc
        if result.plan_id != value["plan_id"]:
            raise ValueError("plan_id does not match plan content")
        return result

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EvidencePlan:
        result = cls.from_dict(_load(serialized))
        if result.canonical_json() != serialized:
            raise ValueError("evidence plan JSON is not canonical")
        return result


@dataclass(frozen=True, slots=True)
class PlanExecutionResult:
    """Externally supplied facts about what happened; it mutates nothing."""

    plan_id: str
    completed_action_ids: tuple[str, ...]
    failed_action_ids: tuple[str, ...]
    new_evidence_ids: tuple[str, ...]
    new_claim_ids: tuple[str, ...]
    new_transition_evaluation_ids: tuple[str, ...]
    new_contradiction_ids: tuple[str, ...]
    new_uncertainty_profile_ids: tuple[str, ...]
    new_abstraction_verification_ids: tuple[str, ...]
    executed_at: datetime
    executor_id: str
    executor_version: str
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("plan_id", "executor_id", "executor_version"):
            _required_text(getattr(self, name), name)
        for item in fields(self):
            if item.name.endswith("_ids"):
                object.__setattr__(
                    self, item.name, _strings(getattr(self, item.name), item.name)
                )
        if set(self.completed_action_ids) & set(self.failed_action_ids):
            raise ValueError("an action cannot be both completed and failed")
        _timestamp(self.executed_at, "executed_at")
        object.__setattr__(
            self, "metadata", _mapping(self.metadata, "metadata", optional=True)
        )

    @property
    def produced_artifacts(self) -> bool:
        return any(
            getattr(self, item.name)
            for item in fields(self)
            if item.name.startswith("new_")
        )

    def canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "executed_at":
                payload[item.name] = _iso(value)
            elif item.name == "metadata":
                payload[item.name] = _plain_json(value)
            elif isinstance(value, tuple):
                payload[item.name] = list(value)
            else:
                payload[item.name] = value
        return payload

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> PlanExecutionResult:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("plan execution result fields do not match schema")
        try:
            return cls(
                **{
                    **{
                        k: tuple(v) if isinstance(v, list) else v
                        for k, v in value.items()
                    },
                    "executed_at": _parse_timestamp(
                        value["executed_at"], "executed_at"
                    ),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("plan execution result payload is malformed") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> PlanExecutionResult:
        return cls.from_dict(_load(serialized))


# --------------------------------------------------------------------------- #
# Blocker extraction (reuses RAP-003..RAP-007 logic; never re-implements it)
# --------------------------------------------------------------------------- #

_SEVERITY_ORDER = (
    BlockerSeverity.INFO,
    BlockerSeverity.WARNING,
    BlockerSeverity.BLOCKING,
    BlockerSeverity.TERMINAL,
)


def _latest(items: tuple[Any, ...], key: str, stamp: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        current = result.get(getattr(item, key))
        if current is None or getattr(item, stamp) >= getattr(current, stamp):
            result[getattr(item, key)] = item
    return result


class _Extractor:
    def __init__(
        self,
        graph: EvidenceGraph,
        at: datetime,
        evaluations: tuple[TransitionEvaluation, ...],
        contradictions: tuple[ContradictionObject, ...],
        profiles: tuple[UncertaintyProfile, ...],
        gates: tuple[UncertaintyGateResult, ...],
        verifications: tuple[AbstractionVerification, ...],
        abstraction_graph: AbstractionGraph | None,
    ) -> None:
        self.graph = graph
        self.at = at
        self.evaluations = _latest(evaluations, "transition_id", "evaluated_at")
        self.contradictions = tuple(
            sorted(contradictions, key=lambda x: x.contradiction_id)
        )
        self.profiles = {x.profile_id: x for x in profiles}
        self.gates = {x.threshold_id: x for x in gates}
        self.verifications = _latest(verifications, "abstraction_id", "evaluated_at")
        self.abstraction_graph = abstraction_graph
        self.blockers: dict[str, EpistemicBlocker] = {}
        self.visited: set[str] = set()

    def add(
        self,
        kind: BlockerType,
        subject: str,
        source: str | None,
        *,
        severity: BlockerSeverity = BlockerSeverity.BLOCKING,
        resolvable: bool = True,
        requirements: tuple[str, ...] = (),
        details: Mapping[str, Any] | None = None,
        caused_by: tuple[str, ...] = (),
    ) -> str:
        item = EpistemicBlocker(
            kind,
            subject,
            source,
            severity,
            resolvable,
            requirements,
            details or {},
            self.at,
            caused_by,
        )
        existing = self.blockers.get(item.blocker_id)
        if existing is not None:
            stronger = max((existing.severity, severity), key=_SEVERITY_ORDER.index)
            item = EpistemicBlocker(
                kind,
                subject,
                existing.source_artifact_id,
                stronger,
                existing.resolvable and resolvable,
                requirements,
                existing.details,
                self.at,
                tuple(set(existing.caused_by) | set(caused_by)),
            )
        self.blockers[item.blocker_id] = item
        return item.blocker_id

    # -- evidence and contradictions -------------------------------------- #

    def evidence(
        self,
        evidence_id: str,
        source: str | None,
        severity: BlockerSeverity,
        claim_id: str | None,
    ) -> tuple[str, ...]:
        node = self.graph.nodes.get(evidence_id)
        details = {"claim_id": claim_id}
        if not isinstance(node, EvidenceNode):
            return (
                self.add(
                    BlockerType.MISSING_EVIDENCE,
                    evidence_id,
                    source,
                    severity=severity,
                    details=details,
                ),
            )
        item = node.evidence
        if item.is_stale(at=self.at):
            return (
                self.add(
                    BlockerType.STALE_EVIDENCE,
                    evidence_id,
                    source,
                    severity=severity,
                    details={**details, "valid_until": _iso(item.valid_until)},
                ),
            )
        status = item.verification_status
        if status is VerificationStatus.UNVERIFIED:
            return (
                self.add(
                    BlockerType.UNVERIFIED_EVIDENCE,
                    evidence_id,
                    source,
                    severity=severity,
                    details=details,
                ),
            )
        if status is VerificationStatus.REJECTED:
            return (
                self.add(
                    BlockerType.REJECTED_EVIDENCE,
                    evidence_id,
                    source,
                    severity=severity,
                    details=details,
                ),
            )
        if status is VerificationStatus.CONTRADICTED:
            return self.contradiction(claim_id, evidence_id, source, severity)
        return ()

    def artifact(
        self, item: ContradictionObject, severity: BlockerSeverity
    ) -> tuple[str, ...]:
        subject = (
            item.claim_ids[0]
            if item.claim_ids
            else item.evidence_ids[0] if item.evidence_ids else item.contradiction_id
        )
        details = {
            "contradiction_id": item.contradiction_id,
            "contradiction_type": item.contradiction_type.value,
            "status": item.status.value,
            "evidence_ids": list(item.evidence_ids),
            "claim_ids": list(item.claim_ids),
            "requirement_types": {
                x.requirement_id: x.requirement_type.value
                for x in item.resolution_requirements
            },
            "mandatory_requirements": [
                x.requirement_id for x in item.resolution_requirements if x.mandatory
            ],
        }
        requirements = tuple(x.requirement_id for x in item.resolution_requirements)
        if item.status in _ACTIVE_CONTRADICTION:
            return (
                self.add(
                    BlockerType.UNRESOLVED_CONTRADICTION,
                    subject,
                    item.contradiction_id,
                    severity=severity,
                    requirements=requirements,
                    details=details,
                ),
            )
        if item.status is ContradictionStatus.RESOLUTION_PENDING:
            return (
                self.add(
                    BlockerType.CONTRADICTION_RESOLUTION_PENDING,
                    subject,
                    item.contradiction_id,
                    severity=severity,
                    requirements=requirements,
                    details=details,
                ),
            )
        if item.status is ContradictionStatus.IRRESOLVABLE:
            return (
                self.add(
                    BlockerType.NO_ADMISSIBLE_RESOLUTION_PATH,
                    subject,
                    item.contradiction_id,
                    severity=BlockerSeverity.TERMINAL,
                    resolvable=False,
                    details={**details, "reason": "contradiction is IRRESOLVABLE"},
                ),
            )
        return ()

    def contradiction(
        self,
        claim_id: str | None,
        evidence_id: str | None,
        source: str | None,
        severity: BlockerSeverity,
    ) -> tuple[str, ...]:
        matching = tuple(
            x
            for x in self.contradictions
            if (claim_id is not None and claim_id in x.claim_ids)
            or (evidence_id is not None and evidence_id in x.evidence_ids)
        )
        found: list[str] = []
        for item in matching:
            found.extend(self.artifact(item, severity))
        if matching:
            return tuple(found)
        subject = claim_id or evidence_id or "unknown"
        return (
            self.add(
                BlockerType.UNRESOLVED_CONTRADICTION,
                subject,
                source,
                severity=severity,
                details={
                    "artifact": None,
                    "claim_id": claim_id,
                    "evidence_id": evidence_id,
                },
            ),
        )

    # -- claims ----------------------------------------------------------- #

    def support(
        self, claim_id: str, source: str | None, severity: BlockerSeverity
    ) -> tuple[str, ...]:
        node = self.graph.nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            return (
                self.add(
                    BlockerType.MISSING_DEPENDENCY,
                    claim_id,
                    source,
                    severity=severity,
                    details={"expected": "ClaimNode"},
                ),
            )
        result = self.graph.is_support_complete(claim_id, at=self.at)
        if result.complete:
            return ()
        causes: list[str] = []
        for evidence_id in (
            *result.stale_evidence_ids,
            *result.unverified_evidence_ids,
            *result.rejected_evidence_ids,
        ):
            causes.extend(self.evidence(evidence_id, source, severity, claim_id))
        for evidence_id in result.contradicted_dependencies:
            causes.extend(self.contradiction(claim_id, evidence_id, source, severity))
        for token in result.unresolved_dependencies:
            causes.append(
                self.add(
                    BlockerType.MISSING_DEPENDENCY,
                    token,
                    source,
                    severity=severity,
                    details={"claim_id": claim_id},
                )
            )
        for constraint_id in result.missing_constraints:
            causes.append(
                self.add(
                    BlockerType.CONSTRAINT_UNRESOLVED,
                    constraint_id,
                    source,
                    severity=severity,
                    details={"claim_id": claim_id},
                )
            )
        for constraint_id in result.failed_constraints:
            causes.append(
                self.add(
                    BlockerType.CONSTRAINT_VIOLATED,
                    constraint_id,
                    source,
                    severity=severity,
                    details={"claim_id": claim_id},
                )
            )
        return (
            self.add(
                BlockerType.SUPPORT_INCOMPLETE,
                claim_id,
                source,
                severity=severity,
                details={"reasons": list(result.reasons)},
                caused_by=tuple(set(causes)),
            ),
        )

    def claim_uncertainty_causes(
        self, claim_id: str, source: str | None, severity: BlockerSeverity
    ) -> tuple[str, ...]:
        node = self.graph.nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            return ()
        causes: list[str] = []
        for evidence_id in node.claim.supporting_evidence_ids:
            causes.extend(self.evidence(evidence_id, source, severity, claim_id))
        return tuple(set(causes))

    # -- transitions ------------------------------------------------------ #

    def requirement(
        self, transition_id: str, result: RequirementEvaluation, source: str
    ) -> tuple[str, ...]:
        severity = (
            BlockerSeverity.BLOCKING if result.mandatory else BlockerSeverity.WARNING
        )
        kind, subject = result.requirement_type, result.subject_id
        if kind is RequirementType.EVIDENCE_VERIFIED:
            return self.evidence(subject, source, severity, None)
        if kind is RequirementType.SUPPORT_COMPLETE:
            return self.support(subject, source, severity)
        if kind is RequirementType.CLAIM_STATE:
            causes = self.support(subject, source, severity)
            return (
                self.add(
                    BlockerType.INVALID_CLAIM_STATE,
                    subject,
                    source,
                    severity=severity,
                    details={
                        "observed": _plain_json(result.observed_value),
                        "required": _plain_json(result.required_value),
                    },
                    caused_by=causes,
                ),
            )
        if kind is RequirementType.CONSTRAINT_SATISFIED:
            violated = result.observed_value == "VIOLATED"
            return (
                self.add(
                    (
                        BlockerType.CONSTRAINT_VIOLATED
                        if violated
                        else BlockerType.CONSTRAINT_UNRESOLVED
                    ),
                    subject,
                    source,
                    severity=severity,
                    details={"observed": _plain_json(result.observed_value)},
                ),
            )
        if kind is RequirementType.MAX_UNCERTAINTY:
            details = {
                "observed": _plain_json(result.observed_value),
                "required": _plain_json(result.required_value),
            }
            if result.observed_value is None:
                return (
                    self.add(
                        BlockerType.MISSING_UNCERTAINTY,
                        subject,
                        source,
                        severity=severity,
                        details=details,
                    ),
                )
            causes = self.claim_uncertainty_causes(subject, source, severity)
            return (
                self.add(
                    BlockerType.EXCESSIVE_UNCERTAINTY,
                    subject,
                    source,
                    severity=severity,
                    details=details,
                    caused_by=causes,
                ),
            )
        if kind in {
            RequirementType.NO_UNRESOLVED_CONTRADICTION,
            RequirementType.NO_INVALIDATION,
        }:
            branches = (
                result.observed_value
                if isinstance(result.observed_value, tuple)
                else ()
            )
            found: list[str] = []
            for evidence_id in branches or (None,):
                found.extend(self.contradiction(subject, evidence_id, source, severity))
            return tuple(found)
        if kind is RequirementType.TRANSFORMATION_PRESENT:
            return (
                self.add(
                    BlockerType.MISSING_TRANSFORMATION,
                    subject,
                    source,
                    severity=severity,
                    details={"required": _plain_json(result.required_value)},
                ),
            )
        required = (
            result.required_value if isinstance(result.required_value, Mapping) else {}
        )
        token = f"{required.get('source_id')}-{required.get('edge_type')}->{required.get('target_id')}"
        return (
            self.add(
                BlockerType.MISSING_DEPENDENCY,
                token,
                source,
                severity=severity,
                details={
                    "required": _plain_json(result.required_value),
                    "claim_id": subject,
                },
            ),
        )

    def transition(
        self, transition_id: str, severity: BlockerSeverity = BlockerSeverity.BLOCKING
    ) -> tuple[str, ...]:
        evaluation = self.evaluations.get(transition_id)
        if evaluation is None:
            return (
                self.add(
                    BlockerType.TRANSITION_BLOCKED,
                    transition_id,
                    None,
                    severity=severity,
                    details={"evaluation": None},
                ),
            )
        if evaluation.status is TransitionStatus.ALLOWED:
            return ()
        source = evaluation.fingerprint
        causes: list[str] = []
        for result in evaluation.requirement_results:
            if not result.passed:
                causes.extend(self.requirement(transition_id, result, source))
        blocking_causes = tuple(
            x
            for x in set(causes)
            if self.blockers[x].severity is not BlockerSeverity.WARNING
        )
        return (
            self.add(
                BlockerType.TRANSITION_BLOCKED,
                transition_id,
                source,
                severity=severity,
                details={
                    "status": evaluation.status.value,
                    "blocking_requirements": list(evaluation.blocking_requirements),
                    "claim_ids": list(evaluation.claim_ids),
                },
                caused_by=blocking_causes,
            ),
        )

    # -- abstractions ----------------------------------------------------- #

    def abstraction(self, abstraction_id: str) -> tuple[str, ...]:
        if abstraction_id in self.visited:
            return ()
        self.visited.add(abstraction_id)
        verification = self.verifications.get(abstraction_id)
        if verification is None:
            return (
                self.add(
                    BlockerType.ABSTRACTION_BLOCKED,
                    abstraction_id,
                    None,
                    details={"verification": None},
                ),
            )
        if verification.status is AbstractionStatus.VERIFIED:
            return ()
        source = verification.fingerprint
        graph = self.abstraction_graph
        node = graph.nodes.get(abstraction_id) if graph is not None else None
        failures = set(verification.failed_requirements)
        causes: list[str] = []
        if AbstractionFailure.SUPPORT_INCOMPLETE in failures:
            for claim_id, complete in verification.support_completeness:
                if not complete:
                    causes.extend(
                        self.support(claim_id, source, BlockerSeverity.BLOCKING)
                    )
        if AbstractionFailure.MISSING_CLAIM in failures:
            missing = [
                x
                for x in verification.claim_ids
                if not isinstance(self.graph.nodes.get(x), ClaimNode)
            ]
            for claim_id in missing:
                causes.append(
                    self.add(
                        BlockerType.MISSING_DEPENDENCY,
                        claim_id,
                        source,
                        details={"expected": "ClaimNode"},
                    )
                )
            if not missing:
                causes.append(
                    self.add(
                        BlockerType.MISSING_DEPENDENCY,
                        abstraction_id,
                        source,
                        details={
                            "expected": "member claim with rule-required predicate"
                        },
                    )
                )
        if AbstractionFailure.TRANSITION_BLOCKED in failures:
            transition_ids = (
                tuple(
                    edge.transition_id
                    for edge in graph.edges
                    if edge.target_abstraction_id == abstraction_id and edge.required
                )
                if graph is not None
                else ()
            )
            for transition_id in transition_ids:
                causes.extend(self.transition(transition_id))
            if not transition_ids:
                causes.append(
                    self.add(
                        BlockerType.TRANSITION_BLOCKED,
                        abstraction_id,
                        source,
                        details={"evaluation": None, "abstraction_graph": None},
                    )
                )
        if AbstractionFailure.MISSING_UPSTREAM_ABSTRACTION in failures:
            for upstream_id in verification.source_abstraction_ids:
                upstream = graph.nodes.get(upstream_id) if graph is not None else None
                if (
                    upstream is not None
                    and upstream.status is AbstractionStatus.VERIFIED
                ):
                    continue
                causes.extend(self.abstraction(upstream_id))
        if AbstractionFailure.UNRESOLVED_CONTRADICTION in failures:
            for item in self.contradictions:
                if item.contradiction_id in verification.contradiction_ids:
                    causes.extend(self.artifact(item, BlockerSeverity.BLOCKING))
        if AbstractionFailure.UNCERTAINTY_GATE_FAILED in failures:
            for gate in verification.uncertainty_gate_results:
                if not gate.passed:
                    causes.append(self.gate(gate, source))
            profile_id = node.uncertainty_profile_id if node is not None else None
            if (
                node is not None
                and profile_id is not None
                and profile_id not in self.profiles
            ):
                causes.append(
                    self.add(
                        BlockerType.MISSING_UNCERTAINTY,
                        profile_id,
                        source,
                        details={
                            "expected": "UncertaintyProfile",
                            "abstraction_id": abstraction_id,
                        },
                    )
                )
            if not any(
                not gate.passed for gate in verification.uncertainty_gate_results
            ) and (node is None or profile_id is None or profile_id in self.profiles):
                causes.append(
                    self.add(
                        BlockerType.MISSING_UNCERTAINTY,
                        abstraction_id,
                        source,
                        details={
                            "expected": "UncertaintyGateResult for every rule threshold"
                        },
                    )
                )
        if AbstractionFailure.LINEAGE_INCOMPLETE in failures:
            tokens: tuple[str, ...] = ()
            if graph is not None and node is not None:
                tokens = graph.explain(
                    abstraction_id, self.graph, self.contradictions
                ).unresolved_dependencies
            token_causes = tuple(
                self.add(
                    BlockerType.MISSING_DEPENDENCY,
                    token,
                    source,
                    details={"abstraction_id": abstraction_id},
                )
                for token in tokens
            )
            causes.append(
                self.add(
                    BlockerType.LINEAGE_INCOMPLETE,
                    abstraction_id,
                    source,
                    details={"unresolved_dependencies": list(tokens)},
                    caused_by=token_causes,
                )
            )
        for failure in (
            AbstractionFailure.INVALID_LEVEL_TRANSITION,
            AbstractionFailure.CONSTRAINT_FAILED,
        ):
            if failure in failures:
                causes.append(
                    self.add(
                        BlockerType.NO_ADMISSIBLE_RESOLUTION_PATH,
                        abstraction_id,
                        source,
                        severity=BlockerSeverity.TERMINAL,
                        resolvable=False,
                        details={"reason": f"{failure.value} is a definition failure"},
                    )
                )
        return (
            self.add(
                BlockerType.ABSTRACTION_BLOCKED,
                abstraction_id,
                source,
                details={
                    "failed_requirements": [
                        x.value for x in verification.failed_requirements
                    ]
                },
                caused_by=tuple(set(causes)),
            ),
        )

    def gate(self, gate: UncertaintyGateResult, source: str | None) -> str:
        details = {
            "threshold_id": gate.threshold_id,
            "observed": _plain_json(gate.observed_value),
            "required": _plain_json(gate.required_value),
            "blocking_components": list(gate.blocking_components),
        }
        kind = (
            BlockerType.MISSING_UNCERTAINTY
            if gate.observed_value is None
            else BlockerType.EXCESSIVE_UNCERTAINTY
        )
        return self.add(kind, gate.threshold_id, source, details=details)

    # -- dispatch --------------------------------------------------------- #

    def run(self, target: PlanningTarget) -> bool:
        """Populate blockers; return whether the target is currently admissible."""
        kind = target.target_type
        if kind is PlanningTargetType.TRANSITION_PERMISSION:
            self.transition(target.transition_id or "")
            evaluation = self.evaluations.get(target.transition_id or "")
            return (
                evaluation is not None and evaluation.status is TransitionStatus.ALLOWED
            )
        if kind is PlanningTargetType.ABSTRACTION_VERIFICATION:
            self.abstraction(target.abstraction_id or "")
            verification = self.verifications.get(target.abstraction_id or "")
            return (
                verification is not None
                and verification.status is AbstractionStatus.VERIFIED
            )
        if kind is PlanningTargetType.CLAIM_SUPPORT:
            claim_id = target.claim_id or ""
            causes = self.support(claim_id, None, BlockerSeverity.BLOCKING)
            node = self.graph.nodes.get(claim_id)
            if not isinstance(node, ClaimNode):
                return False
            for edge in self.graph.edges:
                if edge.target_id == claim_id and edge.edge_type.value in {
                    "CONTRADICTS",
                    "INVALIDATES",
                }:
                    self.contradiction(
                        claim_id, edge.source_id, None, BlockerSeverity.BLOCKING
                    )
            wanted = {x.value for x in EpistemicState}
            state_ok = True
            if (
                target.desired_state in wanted
                and node.claim.epistemic_state.value != target.desired_state
            ):
                state_ok = False
                self.add(
                    BlockerType.INVALID_CLAIM_STATE,
                    claim_id,
                    None,
                    details={
                        "observed": node.claim.epistemic_state.value,
                        "required": target.desired_state,
                    },
                    caused_by=causes,
                )
            if node.claim.uncertainty is None:
                self.add(
                    BlockerType.MISSING_UNCERTAINTY,
                    claim_id,
                    None,
                    severity=BlockerSeverity.INFO,
                    details={"observed": None},
                )
            return (
                not causes
                and state_ok
                and not any(x.blocking for x in self.blockers.values())
            )
        if kind is PlanningTargetType.CONTRADICTION_RESOLUTION:
            artifact = next(
                (
                    x
                    for x in self.contradictions
                    if x.contradiction_id == target.target_id
                ),
                None,
            )
            if artifact is None:
                self.add(
                    BlockerType.MISSING_DEPENDENCY,
                    target.target_id,
                    None,
                    details={"expected": "ContradictionObject"},
                )
                return False
            self.artifact(artifact, BlockerSeverity.BLOCKING)
            return artifact.status is ContradictionStatus.RESOLVED
        claim_id = target.claim_id or ""
        failing = [x for x in self.gates.values() if not x.passed]
        for gate in sorted(failing, key=lambda x: x.threshold_id):
            blocker_id = self.gate(gate, None)
            causes = self.claim_uncertainty_causes(
                claim_id, None, BlockerSeverity.BLOCKING
            )
            if causes:
                self.blockers[blocker_id] = EpistemicBlocker(
                    self.blockers[blocker_id].blocker_type,
                    gate.threshold_id,
                    None,
                    BlockerSeverity.BLOCKING,
                    True,
                    (),
                    self.blockers[blocker_id].details,
                    self.at,
                    causes,
                )
        if not self.gates:
            self.add(
                BlockerType.MISSING_UNCERTAINTY,
                claim_id,
                None,
                details={"expected": "UncertaintyGateResult"},
            )
            return False
        return not failing


def _extract(
    target: PlanningTarget,
    evidence_graph: EvidenceGraph,
    transition_evaluations: tuple[TransitionEvaluation, ...],
    contradiction_artifacts: tuple[ContradictionObject, ...],
    uncertainty_profiles: tuple[UncertaintyProfile, ...],
    uncertainty_gate_results: tuple[UncertaintyGateResult, ...],
    abstraction_verifications: tuple[AbstractionVerification, ...],
    abstraction_graph: AbstractionGraph | None,
    at: datetime,
) -> tuple[tuple[EpistemicBlocker, ...], bool]:
    if not isinstance(target, PlanningTarget) or not isinstance(
        evidence_graph, EvidenceGraph
    ):
        raise ValueError(
            "blocker extraction requires a PlanningTarget and EvidenceGraph"
        )
    _timestamp(at, "at")
    checks = (
        (transition_evaluations, TransitionEvaluation),
        (contradiction_artifacts, ContradictionObject),
        (uncertainty_profiles, UncertaintyProfile),
        (uncertainty_gate_results, UncertaintyGateResult),
        (abstraction_verifications, AbstractionVerification),
    )
    for items, expected in checks:
        if any(not isinstance(x, expected) for x in items):
            raise ValueError(f"artifacts must be {expected.__name__} objects")
    if abstraction_graph is not None and not isinstance(
        abstraction_graph, AbstractionGraph
    ):
        raise ValueError("abstraction_graph must be an AbstractionGraph")
    extractor = _Extractor(
        evidence_graph,
        at,
        tuple(transition_evaluations),
        tuple(contradiction_artifacts),
        tuple(uncertainty_profiles),
        tuple(uncertainty_gate_results),
        tuple(abstraction_verifications),
        abstraction_graph,
    )
    admissible = extractor.run(target)
    order = tuple(BlockerType)
    blockers = tuple(
        sorted(
            extractor.blockers.values(),
            key=lambda x: (order.index(x.blocker_type), x.blocker_id),
        )
    )
    return blockers, admissible and not any(x.blocking for x in blockers)


def identify_blockers(
    *,
    target: PlanningTarget,
    evidence_graph: EvidenceGraph,
    transition_evaluations: tuple[TransitionEvaluation, ...] = (),
    contradiction_artifacts: tuple[ContradictionObject, ...] = (),
    uncertainty_profiles: tuple[UncertaintyProfile, ...] = (),
    uncertainty_gate_results: tuple[UncertaintyGateResult, ...] = (),
    abstraction_verifications: tuple[AbstractionVerification, ...] = (),
    abstraction_graph: AbstractionGraph | None = None,
    at: datetime,
) -> tuple[EpistemicBlocker, ...]:
    """Deterministically derive every explicit blocker for the target."""
    return _extract(
        target,
        evidence_graph,
        transition_evaluations,
        contradiction_artifacts,
        uncertainty_profiles,
        uncertainty_gate_results,
        abstraction_verifications,
        abstraction_graph,
        at,
    )[0]


# --------------------------------------------------------------------------- #
# Action admissibility and minimum epistemic planning
# --------------------------------------------------------------------------- #

_REQUIREMENT_ACTIONS: dict[str, EvidenceActionType] = {
    "INDEPENDENT_EVIDENCE_REQUIRED": EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
    "ADDITIONAL_OBSERVATION_REQUIRED": EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
    "SOURCE_PROVENANCE_REQUIRED": EvidenceActionType.REVERIFY_PROVENANCE,
    "TEMPORAL_ALIGNMENT_REQUIRED": EvidenceActionType.RECONCILE_TIME_WINDOW,
    "SCOPE_ALIGNMENT_REQUIRED": EvidenceActionType.RECONCILE_SCOPE,
    "UNIT_NORMALIZATION_REQUIRED": EvidenceActionType.NORMALIZE_UNIT,
    "METHOD_COMPARISON_REQUIRED": EvidenceActionType.REQUEST_HUMAN_REVIEW,
    "CONSTRAINT_REEVALUATION_REQUIRED": EvidenceActionType.REEVALUATE_CONSTRAINT,
    "TRANSFORMATION_VERIFICATION_REQUIRED": EvidenceActionType.VERIFY_TRANSFORMATION,
    "HUMAN_REVIEW_REQUIRED": EvidenceActionType.REQUEST_HUMAN_REVIEW,
}
_SYMPTOM_CHAIN: dict[BlockerType, EvidenceActionType] = {
    BlockerType.SUPPORT_INCOMPLETE: EvidenceActionType.RECOMPUTE_SUPPORT,
    BlockerType.INVALID_CLAIM_STATE: EvidenceActionType.RECOMPUTE_SUPPORT,
    BlockerType.TRANSITION_BLOCKED: EvidenceActionType.REEVALUATE_TRANSITION,
    BlockerType.ABSTRACTION_BLOCKED: EvidenceActionType.REEVALUATE_ABSTRACTION,
    BlockerType.LINEAGE_INCOMPLETE: EvidenceActionType.REEVALUATE_ABSTRACTION,
}
_EVIDENCE_BLOCKERS = frozenset(
    {
        BlockerType.MISSING_EVIDENCE,
        BlockerType.UNVERIFIED_EVIDENCE,
        BlockerType.STALE_EVIDENCE,
        BlockerType.REJECTED_EVIDENCE,
        BlockerType.MISSING_DEPENDENCY,
        BlockerType.MISSING_TRANSFORMATION,
    }
)
_SELECTABLE = _EVIDENCE_BLOCKERS | {
    BlockerType.MISSING_UNCERTAINTY,
    BlockerType.CONSTRAINT_UNRESOLVED,
    BlockerType.CONSTRAINT_VIOLATED,
}
_SUBJECT_MUST_EXIST = frozenset(
    {
        EvidenceActionType.VERIFY_EVIDENCE,
        EvidenceActionType.REVERIFY_PROVENANCE,
        EvidenceActionType.REFRESH_STALE_EVIDENCE,
        EvidenceActionType.REEVALUATE_CONSTRAINT,
        EvidenceActionType.VERIFY_TRANSFORMATION,
        EvidenceActionType.RECOMPUTE_SUPPORT,
    }
)


def is_action_admissible(
    action: EvidenceAction,
    blockers: tuple[EpistemicBlocker, ...],
    evidence_graph: EvidenceGraph,
    *,
    at: datetime,
) -> tuple[bool, str]:
    """Explicit admissibility check; returns (admissible, reason)."""
    _timestamp(at, "at")
    by_id = {x.blocker_id: x for x in blockers}
    for blocker_id in action.addresses_blocker_ids:
        blocker = by_id.get(blocker_id)
        if blocker is None:
            return False, "action addresses a blocker that does not exist"
        if action.action_type not in _ADMISSIBLE_ACTIONS[blocker.blocker_type]:
            return (
                False,
                f"{action.action_type.value} cannot affect {blocker.blocker_type.value}",
            )
        if (
            blocker.blocker_type is BlockerType.UNRESOLVED_CONTRADICTION
            and action.action_type
            is EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT
            and blocker.requirements
            and not action.preconditions
        ):
            return (
                False,
                "automatic contradiction resolution without satisfied requirements",
            )
    if action.action_type in _SUBJECT_MUST_EXIST:
        for subject in action.subject_ids:
            node = evidence_graph.nodes.get(subject)
            if node is None:
                return False, f"subject {subject} does not exist in the evidence graph"
            if (
                action.action_type is EvidenceActionType.VERIFY_EVIDENCE
                and isinstance(node, EvidenceNode)
                and node.evidence.is_stale(at=at)
            ):
                return False, "stale evidence cannot be verified as if it were current"
    if action.action_type is EvidenceActionType.ADD_TRANSFORMATION and not (
        action.parameters.get("transformation_type")
        and action.parameters.get("version")
    ):
        return False, "transformation semantics (type and version) are unavailable"
    if action.action_type is EvidenceActionType.REDUCE_UNCERTAINTY and not (
        action.parameters.get("independence_declared") is True or action.preconditions
    ):
        return (
            False,
            "uncertainty reduction assumes independence that is not established",
        )
    return True, "admissible"


class _Builder:
    def __init__(self) -> None:
        self.actions: dict[tuple[str, tuple[str, ...], str], EvidenceAction] = {}

    def add(
        self,
        kind: EvidenceActionType,
        subjects: tuple[str, ...],
        blocker_ids: tuple[str, ...],
        effect: str,
        *,
        parameters: Mapping[str, Any] | None = None,
        mandatory: bool = True,
        preconditions: tuple[str, ...] = (),
        cost: float | None = None,
        gain: float | None = None,
    ) -> EvidenceAction:
        params = dict(parameters or {})
        key = (
            kind.value,
            tuple(sorted(subjects)),
            _canonical(_plain_json(_freeze_json(params, "p"))),
        )
        existing = self.actions.get(key)
        if existing is not None:
            blocker_ids = tuple(set(existing.addresses_blocker_ids) | set(blocker_ids))
            preconditions = tuple(set(existing.preconditions) | set(preconditions))
            mandatory = existing.mandatory or mandatory
        item = EvidenceAction(
            kind,
            subjects,
            blocker_ids,
            params,
            preconditions,
            effect,
            cost,
            gain,
            mandatory,
        )
        self.actions[key] = item
        return item

    def mandatory_ids(self, *, below: int) -> tuple[str, ...]:
        return tuple(
            sorted(
                x.action_id
                for x in self.actions.values()
                if x.mandatory and x.priority < below
            )
        )

    def ids_for(self, blocker_ids: tuple[str, ...]) -> tuple[str, ...]:
        wanted = set(blocker_ids)
        return tuple(
            sorted(
                x.action_id
                for x in self.actions.values()
                if x.mandatory and wanted & set(x.addresses_blocker_ids)
            )
        )


def _default_actions(
    blocker: EpistemicBlocker,
    costs: Mapping[str, float],
    gains: Mapping[str, float],
) -> tuple[EvidenceAction, ...]:
    """Default admissible fixes for a root blocker (no caller candidates)."""
    kind, subject, details = blocker.blocker_type, blocker.subject_id, blocker.details

    def make(
        action: EvidenceActionType, effect: str, params: Mapping[str, Any] | None = None
    ) -> EvidenceAction:
        return EvidenceAction(
            action,
            (subject,),
            (blocker.blocker_id,),
            dict(params or {}),
            (),
            effect,
            costs.get(action.value),
            gains.get(action.value),
            blocker.blocking,
        )

    if kind is BlockerType.MISSING_EVIDENCE:
        if details.get("independence_required") is True:
            return (
                make(
                    EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
                    "independent evidence object registered for the subject",
                ),
            )
        return (
            make(
                EvidenceActionType.RETRIEVE_EVIDENCE,
                "evidence object registered in the graph with provenance",
            ),
        )
    if kind is BlockerType.UNVERIFIED_EVIDENCE:
        return (
            make(
                EvidenceActionType.VERIFY_EVIDENCE,
                "evidence verification_status becomes VERIFIED",
            ),
        )
    if kind is BlockerType.STALE_EVIDENCE:
        return (
            make(
                EvidenceActionType.REFRESH_STALE_EVIDENCE,
                "re-retrieved evidence valid at the evaluation instant",
            ),
        )
    if kind is BlockerType.REJECTED_EVIDENCE:
        return (
            make(
                EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
                "independent evidence replaces rejected evidence",
            ),
        )
    if kind is BlockerType.MISSING_UNCERTAINTY:
        return (
            make(
                EvidenceActionType.RETRIEVE_EVIDENCE,
                "explicit uncertainty declaration obtained",
                {"required": "explicit uncertainty"},
            ),
        )
    if kind in {BlockerType.CONSTRAINT_UNRESOLVED, BlockerType.CONSTRAINT_VIOLATED}:
        return (
            make(
                EvidenceActionType.REEVALUATE_CONSTRAINT,
                "constraint re-evaluated and its status recorded",
            ),
        )
    if kind is BlockerType.MISSING_TRANSFORMATION:
        required = (
            details.get("required")
            if isinstance(details.get("required"), Mapping)
            else {}
        )
        return (
            make(
                EvidenceActionType.ADD_TRANSFORMATION,
                "transformation node declared with explicit lineage",
                {
                    "transformation_type": required.get("transformation_type"),
                    "version": required.get("version"),
                },
            ),
        )
    if kind is BlockerType.MISSING_DEPENDENCY:
        return (
            make(
                EvidenceActionType.RETRIEVE_EVIDENCE,
                "missing dependency recorded explicitly in the graph",
                {"dependency": subject},
            ),
        )
    return ()


def _select(
    blocker: EpistemicBlocker,
    defaults: tuple[EvidenceAction, ...],
    candidates: tuple[EvidenceAction, ...],
    blockers: tuple[EpistemicBlocker, ...],
    graph: EvidenceGraph,
    root_ids: set[str],
    at: datetime,
) -> EvidenceAction | None:
    pool = [
        x
        for x in (*defaults, *candidates)
        if blocker.blocker_id in x.addresses_blocker_ids
        and is_action_admissible(x, blockers, graph, at=at)[0]
    ]
    if not pool:
        return None
    priced = any(x.estimated_cost is not None for x in pool)

    def key(x: EvidenceAction) -> tuple[int, float, int, float, str]:
        coverage = len(set(x.addresses_blocker_ids) & root_ids)
        cost = (
            (x.estimated_cost if x.estimated_cost is not None else math.inf)
            if priced
            else 0.0
        )
        gain = (
            x.estimated_information_gain
            if x.estimated_information_gain is not None
            else -1.0
        )
        return (-coverage, cost, x.priority, -gain, x.action_id)

    return min(pool, key=key)


def _build(
    target: PlanningTarget,
    blockers: tuple[EpistemicBlocker, ...],
    admissible: bool,
    *,
    graph: EvidenceGraph,
    at: datetime,
    planner_id: str,
    planner_version: str,
    candidates: tuple[EvidenceAction, ...],
    costs: Mapping[str, float],
    gains: Mapping[str, float],
    previous_plan_id: str | None,
    no_progress_count: int,
    history: tuple[str, ...],
    abstain: str | None,
) -> EvidencePlan:
    metadata = {"plan_history": list(history)} if history else None
    terminal_ids = tuple(
        sorted(x.blocker_id for x in blockers if x.severity is BlockerSeverity.TERMINAL)
    )
    if abstain is not None and not terminal_ids:
        marker = EpistemicBlocker(
            BlockerType.NO_ADMISSIBLE_RESOLUTION_PATH,
            target.target_id,
            previous_plan_id,
            BlockerSeverity.TERMINAL,
            False,
            (),
            {"reason": abstain},
            at,
        )
        blockers = (*blockers, marker)
        terminal_ids = (marker.blocker_id,)
    if terminal_ids:
        action = EvidenceAction(
            EvidenceActionType.ABSTAIN,
            (target.target_id,),
            terminal_ids,
            {},
            (),
            "no admissible resolution path; planning stops without granting permission",
            None,
            None,
            True,
        )
        return EvidencePlan(
            target,
            blockers,
            (action,),
            True,
            abstain or NO_ADMISSIBLE_RESOLUTION_PATH,
            PlanStatus.ABSTAINED,
            planner_id,
            planner_version,
            at,
            graph.fingerprint,
            previous_plan_id,
            no_progress_count,
            metadata,
        )
    if admissible:
        return EvidencePlan(
            target,
            blockers,
            (),
            True,
            None,
            PlanStatus.COMPLETED,
            planner_id,
            planner_version,
            at,
            graph.fingerprint,
            previous_plan_id,
            no_progress_count,
            metadata,
            _token=_TOKEN,
        )
    builder = _Builder()
    blocking = [x for x in blockers if x.blocking and x.resolvable]
    roots = [x for x in blocking if x.blocker_type not in _SYMPTOM_CHAIN]
    root_ids = {x.blocker_id for x in roots}
    covered: set[str] = set()
    evidence_fixed: dict[tuple[str, ...], list[str]] = {}
    claim_scope = tuple(
        sorted(
            {
                claim_id
                for x in blockers
                if x.blocker_type is BlockerType.TRANSITION_BLOCKED
                for claim_id in (x.details.get("claim_ids") or ())
                if isinstance(graph.nodes.get(claim_id), ClaimNode)
            }
            | ({target.claim_id} if target.claim_id else set())
        )
    )
    for blocker in roots:
        if blocker.blocker_id in covered:
            continue
        kind = blocker.blocker_type
        if kind in _SELECTABLE:
            chosen = _select(
                blocker,
                _default_actions(blocker, costs, gains),
                candidates,
                blockers,
                graph,
                root_ids,
                at,
            )
            if chosen is None:
                continue
            builder.add(
                chosen.action_type,
                chosen.subject_ids,
                chosen.addresses_blocker_ids,
                chosen.expected_effect,
                parameters=chosen.parameters,
                mandatory=chosen.mandatory or blocker.blocking,
                cost=chosen.estimated_cost,
                gain=chosen.estimated_information_gain,
            )
            covered.update(set(chosen.addresses_blocker_ids) & root_ids)
            if kind in _EVIDENCE_BLOCKERS:
                claim = blocker.details.get("claim_id")
                scope = (claim,) if claim else claim_scope
                if scope:
                    evidence_fixed.setdefault(scope, []).append(blocker.blocker_id)
            continue
        if kind in {
            BlockerType.UNRESOLVED_CONTRADICTION,
            BlockerType.CONTRADICTION_RESOLUTION_PENDING,
        }:
            details = blocker.details
            types = details.get("requirement_types") or {}
            mandatory = set(details.get("mandatory_requirements") or ())
            contradiction_id = (
                details.get("contradiction_id")
                or blocker.source_artifact_id
                or blocker.subject_id
            )
            prerequisites: list[str] = []
            for requirement_id in blocker.requirements:
                action_type = _REQUIREMENT_ACTIONS.get(
                    types.get(requirement_id, ""),
                    EvidenceActionType.REQUEST_HUMAN_REVIEW,
                )
                item = builder.add(
                    action_type,
                    (blocker.subject_id,),
                    (blocker.blocker_id,),
                    f"RAP-005 resolution requirement {requirement_id} satisfied by admissible input",
                    parameters={
                        "contradiction_id": contradiction_id,
                        "requirement_id": requirement_id,
                    },
                    mandatory=requirement_id in mandatory,
                    cost=costs.get(action_type.value),
                    gain=gains.get(action_type.value),
                )
                prerequisites.append(item.action_id)
            if (
                not blocker.requirements
                and kind is BlockerType.UNRESOLVED_CONTRADICTION
            ):
                item = builder.add(
                    EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
                    (blocker.subject_id,),
                    (blocker.blocker_id,),
                    "admissible independent evidence available for contradiction resolution",
                    parameters={"contradiction_id": contradiction_id},
                    cost=costs.get("REQUEST_INDEPENDENT_EVIDENCE"),
                    gain=gains.get("REQUEST_INDEPENDENT_EVIDENCE"),
                )
                prerequisites.append(item.action_id)
            builder.add(
                EvidenceActionType.RESOLVE_CONTRADICTION_REQUIREMENT,
                (blocker.subject_id,),
                (blocker.blocker_id,),
                "ContradictionResolutionResult recorded through evaluate_resolution; RESOLVED is earned, not set",
                parameters={"contradiction_id": contradiction_id},
                preconditions=tuple(sorted(prerequisites)),
            )
            covered.add(blocker.blocker_id)
            continue
        if kind is BlockerType.EXCESSIVE_UNCERTAINTY:
            prerequisites = list(builder.ids_for(blocker.caused_by))
            if not blocker.caused_by:
                item = builder.add(
                    EvidenceActionType.REQUEST_INDEPENDENT_EVIDENCE,
                    (blocker.subject_id,),
                    (blocker.blocker_id,),
                    "independent VERIFIED evidence enabling an explicit reduction rule",
                    parameters={"purpose": "independent_evidence_reduction"},
                    cost=costs.get("REQUEST_INDEPENDENT_EVIDENCE"),
                    gain=gains.get("REQUEST_INDEPENDENT_EVIDENCE"),
                )
                prerequisites.append(item.action_id)
            builder.add(
                EvidenceActionType.REDUCE_UNCERTAINTY,
                (blocker.subject_id,),
                (blocker.blocker_id,),
                "UncertaintyPropagationResult from an explicit reproducible RAP-006 rule",
                parameters={"rule_type": "INDEPENDENT_EVIDENCE_REDUCTION"},
                preconditions=tuple(sorted(prerequisites)),
            )
            covered.add(blocker.blocker_id)
    # Root causes that were caused by other blockers still need their fix first.
    for blocker in roots:
        if blocker.blocker_id not in covered and blocker.caused_by:
            covered.add(blocker.blocker_id)
    for scope, blocker_ids in sorted(evidence_fixed.items()):
        claims = tuple(x for x in scope if isinstance(graph.nodes.get(x), ClaimNode))
        if claims:
            builder.add(
                EvidenceActionType.RECOMPUTE_SUPPORT,
                claims,
                tuple(blocker_ids),
                "support completeness recomputed by EvidenceGraph.is_support_complete",
                preconditions=builder.ids_for(tuple(blocker_ids)),
            )
    for blocker in sorted(blocking, key=lambda x: (x.blocker_type.value, x.blocker_id)):
        chain = _SYMPTOM_CHAIN.get(blocker.blocker_type)
        if chain is None:
            continue
        if chain is EvidenceActionType.RECOMPUTE_SUPPORT and not isinstance(
            graph.nodes.get(blocker.subject_id), ClaimNode
        ):
            continue
        effect = {
            EvidenceActionType.RECOMPUTE_SUPPORT: "support completeness recomputed by EvidenceGraph.is_support_complete",
            EvidenceActionType.REEVALUATE_TRANSITION: "TransitionEvaluation re-earned by evaluate_transition",
            EvidenceActionType.REEVALUATE_ABSTRACTION: "AbstractionVerification re-earned by verify_abstraction",
        }[chain]
        builder.add(
            chain,
            (blocker.subject_id,),
            (blocker.blocker_id,),
            effect,
            preconditions=builder.mandatory_ids(below=_ACTION_PRIORITY[chain]),
        )
    if (
        target.target_type is PlanningTargetType.CLAIM_SUPPORT
        and target.claim_id
        and isinstance(graph.nodes.get(target.claim_id), ClaimNode)
    ):
        related = tuple(x.blocker_id for x in blocking)
        if related:
            builder.add(
                EvidenceActionType.RECOMPUTE_SUPPORT,
                (target.claim_id,),
                related,
                "support completeness recomputed by EvidenceGraph.is_support_complete",
                preconditions=builder.mandatory_ids(below=7),
            )
    review_needed = any(
        x.mandatory and x.action_type is EvidenceActionType.REQUEST_HUMAN_REVIEW
        for x in builder.actions.values()
    )
    if review_needed and (target.metadata or {}).get("human_review_available") is False:
        return _build(
            target,
            blockers,
            False,
            graph=graph,
            at=at,
            planner_id=planner_id,
            planner_version=planner_version,
            candidates=candidates,
            costs=costs,
            gains=gains,
            previous_plan_id=previous_plan_id,
            no_progress_count=no_progress_count,
            history=history,
            abstain="HUMAN_REVIEW_UNAVAILABLE",
        )
    actions = tuple(builder.actions.values())
    uncovered = [
        x
        for x in blocking
        if x.blocker_id not in covered
        and not any(x.blocker_id in a.addresses_blocker_ids for a in actions)
    ]
    if blocking and (
        not actions or uncovered and not any(a.mandatory for a in actions)
    ):
        return _build(
            target,
            blockers,
            False,
            graph=graph,
            at=at,
            planner_id=planner_id,
            planner_version=planner_version,
            candidates=candidates,
            costs=costs,
            gains=gains,
            previous_plan_id=previous_plan_id,
            no_progress_count=no_progress_count,
            history=history,
            abstain=NO_ADMISSIBLE_RESOLUTION_PATH,
        )
    status = _derive_status(blockers, actions, no_progress_count, False)
    return EvidencePlan(
        target,
        blockers,
        actions,
        False,
        None,
        status,
        planner_id,
        planner_version,
        at,
        graph.fingerprint,
        previous_plan_id,
        no_progress_count,
        metadata,
    )


def plan_evidence(
    target: PlanningTarget,
    *,
    evidence_graph: EvidenceGraph,
    at: datetime,
    planner_id: str,
    planner_version: str,
    transition_evaluations: tuple[TransitionEvaluation, ...] = (),
    contradiction_artifacts: tuple[ContradictionObject, ...] = (),
    uncertainty_profiles: tuple[UncertaintyProfile, ...] = (),
    uncertainty_gate_results: tuple[UncertaintyGateResult, ...] = (),
    abstraction_verifications: tuple[AbstractionVerification, ...] = (),
    abstraction_graph: AbstractionGraph | None = None,
    candidate_actions: tuple[EvidenceAction, ...] = (),
    action_costs: Mapping[str, float] | None = None,
    information_gains: Mapping[str, float] | None = None,
    previous_plan: EvidencePlan | None = None,
    no_progress_count: int = 0,
) -> EvidencePlan:
    """Build the minimum epistemic plan for a target; never mutates any artifact."""
    _required_text(planner_id, "planner_id")
    _required_text(planner_version, "planner_version")
    if any(not isinstance(x, EvidenceAction) for x in candidate_actions):
        raise ValueError("candidate_actions must contain EvidenceAction objects")
    blockers, admissible = _extract(
        target,
        evidence_graph,
        transition_evaluations,
        contradiction_artifacts,
        uncertainty_profiles,
        uncertainty_gate_results,
        abstraction_verifications,
        abstraction_graph,
        at,
    )
    history: tuple[str, ...] = ()
    if previous_plan is not None:
        earlier = (previous_plan.metadata or {}).get("plan_history") or ()
        history = (*earlier, previous_plan.plan_id)
    return _build(
        target,
        blockers,
        admissible,
        graph=evidence_graph,
        at=at,
        planner_id=planner_id,
        planner_version=planner_version,
        candidates=tuple(candidate_actions),
        costs=dict(action_costs or {}),
        gains=dict(information_gains or {}),
        previous_plan_id=None if previous_plan is None else previous_plan.plan_id,
        no_progress_count=no_progress_count,
        history=history,
        abstain=None,
    )


def replan(
    previous_plan: EvidencePlan,
    execution_result: PlanExecutionResult,
    *,
    evidence_graph: EvidenceGraph,
    at: datetime,
    transition_evaluations: tuple[TransitionEvaluation, ...] = (),
    contradiction_artifacts: tuple[ContradictionObject, ...] = (),
    uncertainty_profiles: tuple[UncertaintyProfile, ...] = (),
    uncertainty_gate_results: tuple[UncertaintyGateResult, ...] = (),
    abstraction_verifications: tuple[AbstractionVerification, ...] = (),
    abstraction_graph: AbstractionGraph | None = None,
    candidate_actions: tuple[EvidenceAction, ...] = (),
    action_costs: Mapping[str, float] | None = None,
    information_gains: Mapping[str, float] | None = None,
    planner_id: str | None = None,
    planner_version: str | None = None,
) -> EvidencePlan:
    """Replan from current artifacts; the previous plan is preserved unchanged."""
    if not isinstance(previous_plan, EvidencePlan) or not isinstance(
        execution_result, PlanExecutionResult
    ):
        raise ValueError(
            "replanning requires an EvidencePlan and a PlanExecutionResult"
        )
    if execution_result.plan_id != previous_plan.plan_id:
        raise ValueError("execution result does not belong to the previous plan")
    if previous_plan.terminal:
        raise ValueError("a terminal plan cannot be replanned")
    _timestamp(at, "at")
    if at < previous_plan.created_at:
        raise ValueError("replanning cannot precede the previous plan")
    candidate = plan_evidence(
        previous_plan.target,
        evidence_graph=evidence_graph,
        at=at,
        planner_id=planner_id or previous_plan.planner_id,
        planner_version=planner_version or previous_plan.planner_version,
        transition_evaluations=transition_evaluations,
        contradiction_artifacts=contradiction_artifacts,
        uncertainty_profiles=uncertainty_profiles,
        uncertainty_gate_results=uncertainty_gate_results,
        abstraction_verifications=abstraction_verifications,
        abstraction_graph=abstraction_graph,
        candidate_actions=candidate_actions,
        action_costs=action_costs,
        information_gains=information_gains,
        previous_plan=previous_plan,
    )
    same_blockers = {x.blocker_id for x in candidate.blockers} == {
        x.blocker_id for x in previous_plan.blockers
    }
    same_actions = {x.action_id for x in candidate.actions} == {
        x.action_id for x in previous_plan.actions
    }
    same_graph = candidate.graph_fingerprint == previous_plan.graph_fingerprint
    progress = (
        candidate.terminal
        or execution_result.produced_artifacts
        or not same_blockers
        or not same_actions
        or not same_graph
    )
    if progress:
        return candidate
    count = previous_plan.no_progress_count + 1
    return (
        plan_evidence(
            previous_plan.target,
            evidence_graph=evidence_graph,
            at=at,
            planner_id=candidate.planner_id,
            planner_version=candidate.planner_version,
            transition_evaluations=transition_evaluations,
            contradiction_artifacts=contradiction_artifacts,
            uncertainty_profiles=uncertainty_profiles,
            uncertainty_gate_results=uncertainty_gate_results,
            abstraction_verifications=abstraction_verifications,
            abstraction_graph=abstraction_graph,
            candidate_actions=candidate_actions,
            action_costs=action_costs,
            information_gains=information_gains,
            previous_plan=previous_plan,
            no_progress_count=count,
        )
        if count < 2
        else _build(
            previous_plan.target,
            candidate.blockers,
            False,
            graph=evidence_graph,
            at=at,
            planner_id=candidate.planner_id,
            planner_version=candidate.planner_version,
            candidates=tuple(candidate_actions),
            costs=dict(action_costs or {}),
            gains=dict(information_gains or {}),
            previous_plan_id=previous_plan.plan_id,
            no_progress_count=count,
            history=tuple((candidate.metadata or {}).get("plan_history") or ()),
            abstain=NO_ADMISSIBLE_RESOLUTION_PATH,
        )
    )
