"""Verified Cognitive Transition gate for isolated VERA-RAP research."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping

from .claims import ClaimObject, EpistemicState
from .evidence import (
    EvidenceObject,
    Provenance,
    VerificationStatus,
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)
from .evidence_graph import (
    ClaimNode,
    ConstraintNode,
    ConstraintStatus,
    EdgeType,
    EvidenceGraph,
    EvidenceNode,
    GraphEdge,
    TransformationNode,
)


class RequirementType(Enum):
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    SUPPORT_COMPLETE = "SUPPORT_COMPLETE"
    CLAIM_STATE = "CLAIM_STATE"
    CONSTRAINT_SATISFIED = "CONSTRAINT_SATISFIED"
    MAX_UNCERTAINTY = "MAX_UNCERTAINTY"
    NO_UNRESOLVED_CONTRADICTION = "NO_UNRESOLVED_CONTRADICTION"
    NO_INVALIDATION = "NO_INVALIDATION"
    TRANSFORMATION_PRESENT = "TRANSFORMATION_PRESENT"
    DEPENDENCY_PRESENT = "DEPENDENCY_PRESENT"

    def __str__(self) -> str:
        raise TypeError("RequirementType cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("RequirementType cannot be used as an implicit boolean")


class TransitionStatus(Enum):
    ALLOWED = "ALLOWED"
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    BLOCKED_UNVERIFIED_EVIDENCE = "BLOCKED_UNVERIFIED_EVIDENCE"
    BLOCKED_STALE_EVIDENCE = "BLOCKED_STALE_EVIDENCE"
    BLOCKED_REJECTED_EVIDENCE = "BLOCKED_REJECTED_EVIDENCE"
    BLOCKED_CONTRADICTION = "BLOCKED_CONTRADICTION"
    BLOCKED_UNCERTAINTY = "BLOCKED_UNCERTAINTY"
    BLOCKED_CONSTRAINT = "BLOCKED_CONSTRAINT"
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    BLOCKED_CLAIM_STATE = "BLOCKED_CLAIM_STATE"
    BLOCKED_INVALIDATION = "BLOCKED_INVALIDATION"
    BLOCKED_TRANSFORMATION = "BLOCKED_TRANSFORMATION"
    BLOCKED_GRAPH_INCOMPLETE = "BLOCKED_GRAPH_INCOMPLETE"

    def __str__(self) -> str:
        raise TypeError("TransitionStatus cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("TransitionStatus cannot be used as an implicit boolean")


_STATUS_PRIORITY = (
    TransitionStatus.BLOCKED_GRAPH_INCOMPLETE,
    TransitionStatus.BLOCKED_MISSING_EVIDENCE,
    TransitionStatus.BLOCKED_UNVERIFIED_EVIDENCE,
    TransitionStatus.BLOCKED_STALE_EVIDENCE,
    TransitionStatus.BLOCKED_REJECTED_EVIDENCE,
    TransitionStatus.BLOCKED_CONTRADICTION,
    TransitionStatus.BLOCKED_INVALIDATION,
    TransitionStatus.BLOCKED_CONSTRAINT,
    TransitionStatus.BLOCKED_UNCERTAINTY,
    TransitionStatus.BLOCKED_CLAIM_STATE,
    TransitionStatus.BLOCKED_TRANSFORMATION,
    TransitionStatus.BLOCKED_DEPENDENCY,
)
_EVALUATION_TOKEN = object()


def _ids(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")
    result = tuple(value)
    for item in result:
        _required_text(item, f"{name} item")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(result))


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class CognitiveState:
    state_id: str
    state_type: str
    level: int | None
    claim_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    scope: Any = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _required_text(self.state_id, "state_id")
        _required_text(self.state_type, "state_type")
        if self.level is not None and (
            isinstance(self.level, bool) or not isinstance(self.level, int)
        ):
            raise ValueError("level must be an integer or null")
        for name in ("claim_ids", "evidence_ids"):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        for name in ("scope", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object or null")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "state_type": self.state_type,
            "level": self.level,
            "claim_ids": list(self.claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "scope": _plain_json(self.scope),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, payload: object) -> CognitiveState:
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError("cognitive state fields do not match canonical schema")
        return cls(**payload)

    @classmethod
    def from_canonical_json(cls, serialized: str) -> CognitiveState:
        try:
            return cls.from_dict(json.loads(serialized))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized cognitive state is malformed") from exc


@dataclass(frozen=True, slots=True)
class TransitionRequirement:
    requirement_id: str
    requirement_type: RequirementType
    subject_id: str
    parameters: Mapping[str, Any]
    mandatory: bool
    description: str

    def __post_init__(self) -> None:
        _required_text(self.requirement_id, "requirement_id")
        _required_text(self.subject_id, "subject_id")
        _required_text(self.description, "description")
        if not isinstance(self.requirement_type, RequirementType):
            raise ValueError("requirement_type must be a RequirementType enum member")
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be a boolean")
        frozen = _freeze_json(self.parameters, "parameters")
        if not isinstance(frozen, Mapping):
            raise ValueError("parameters must be an object")
        object.__setattr__(self, "parameters", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type.value,
            "subject_id": self.subject_id,
            "parameters": _plain_json(self.parameters),
            "mandatory": self.mandatory,
            "description": self.description,
        }

    def canonical_json(self) -> str:
        return _canonical(self.to_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, payload: object) -> TransitionRequirement:
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError(
                "transition requirement fields do not match canonical schema"
            )
        return cls(
            **{
                **payload,
                "requirement_type": RequirementType(payload["requirement_type"]),
            }
        )

    @classmethod
    def from_canonical_json(cls, serialized: str) -> TransitionRequirement:
        try:
            return cls.from_dict(json.loads(serialized))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized transition requirement is malformed") from exc


@dataclass(frozen=True, slots=True)
class CognitiveTransition:
    transition_id: str
    transition_type: str
    source_state: CognitiveState
    target_state: CognitiveState
    requirements: tuple[TransitionRequirement, ...]
    evaluator_id: str
    evaluator_version: str
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "transition_id",
            "transition_type",
            "evaluator_id",
            "evaluator_version",
        ):
            _required_text(getattr(self, name), name)
        if not isinstance(self.source_state, CognitiveState) or not isinstance(
            self.target_state, CognitiveState
        ):
            raise ValueError(
                "source_state and target_state must be CognitiveState objects"
            )
        requirements = tuple(self.requirements)
        if any(not isinstance(item, TransitionRequirement) for item in requirements):
            raise ValueError("requirements must contain TransitionRequirement objects")
        ids = [item.requirement_id for item in requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement IDs must be unique")
        if not requirements or not any(item.mandatory for item in requirements):
            raise ValueError("a transition requires at least one mandatory requirement")
        object.__setattr__(
            self,
            "requirements",
            tuple(sorted(requirements, key=lambda item: item.requirement_id)),
        )
        metadata = _freeze_json(self.metadata, "metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        object.__setattr__(self, "metadata", metadata)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "transition_type": self.transition_type,
            "source_state": self.source_state.canonical_dict(),
            "target_state": self.target_state.canonical_dict(),
            "requirements": [item.to_dict() for item in self.requirements],
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_canonical_json(cls, serialized: str) -> CognitiveTransition:
        try:
            payload = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized transition must be valid JSON") from exc
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError("transition fields do not match canonical schema")
        return cls(
            **{
                **payload,
                "source_state": CognitiveState.from_dict(payload["source_state"]),
                "target_state": CognitiveState.from_dict(payload["target_state"]),
                "requirements": tuple(
                    TransitionRequirement.from_dict(item)
                    for item in payload["requirements"]
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class RequirementEvaluation:
    requirement_id: str
    requirement_type: RequirementType
    passed: bool
    subject_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    observed_value: Any
    required_value: Any
    failure_status: TransitionStatus | None
    mandatory: bool

    def __post_init__(self) -> None:
        _required_text(self.requirement_id, "requirement_id")
        _required_text(self.subject_id, "subject_id")
        _required_text(self.reason, "reason")
        if (
            not isinstance(self.requirement_type, RequirementType)
            or not isinstance(self.passed, bool)
            or not isinstance(self.mandatory, bool)
        ):
            raise ValueError("requirement evaluation has invalid typed fields")
        if self.passed != (self.failure_status is None):
            raise ValueError("passed and failure_status are inconsistent")
        if self.failure_status is TransitionStatus.ALLOWED:
            raise ValueError("ALLOWED is not a requirement failure status")
        for name in ("evidence_ids", "claim_ids"):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        for name in ("observed_value", "required_value"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type.value,
            "passed": self.passed,
            "subject_id": self.subject_id,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "observed_value": _plain_json(self.observed_value),
            "required_value": _plain_json(self.required_value),
            "failure_status": (
                None if self.failure_status is None else self.failure_status.value
            ),
            "mandatory": self.mandatory,
        }

    def canonical_json(self) -> str:
        return _canonical(self.to_dict())

    @classmethod
    def from_dict(cls, payload: object) -> RequirementEvaluation:
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError(
                "requirement evaluation fields do not match canonical schema"
            )
        status = (
            None
            if payload["failure_status"] is None
            else TransitionStatus(payload["failure_status"])
        )
        return cls(
            **{
                **payload,
                "requirement_type": RequirementType(payload["requirement_type"]),
                "failure_status": status,
            }
        )

    @classmethod
    def from_canonical_json(cls, serialized: str) -> RequirementEvaluation:
        try:
            return cls.from_dict(json.loads(serialized))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized requirement evaluation is malformed") from exc


@dataclass(frozen=True, slots=True, init=False)
class TransitionEvaluation:
    transition_id: str
    transition_fingerprint: str
    transition_definition: CognitiveTransition
    status: TransitionStatus
    allowed: bool
    evaluated_at: datetime
    source_state: CognitiveState
    target_state: CognitiveState
    requirement_results: tuple[RequirementEvaluation, ...]
    blocking_requirements: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    graph_fingerprint: str
    evaluator_id: str
    evaluator_version: str

    def __init__(
        self,
        transition_id: str,
        transition_fingerprint: str,
        transition_definition: CognitiveTransition,
        status: TransitionStatus,
        allowed: bool,
        evaluated_at: datetime,
        source_state: CognitiveState,
        target_state: CognitiveState,
        requirement_results: tuple[RequirementEvaluation, ...],
        blocking_requirements: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        claim_ids: tuple[str, ...],
        graph_fingerprint: str,
        evaluator_id: str,
        evaluator_version: str,
        *,
        _evaluation_token: object | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            object.__setattr__(self, item.name, values[item.name])
        self._validate(_evaluation_token)

    def _validate(self, token: object | None) -> None:
        for name in (
            "transition_id",
            "transition_fingerprint",
            "graph_fingerprint",
            "evaluator_id",
            "evaluator_version",
        ):
            _required_text(getattr(self, name), name)
        if not isinstance(self.status, TransitionStatus) or not isinstance(
            self.allowed, bool
        ):
            raise ValueError("transition evaluation has invalid status fields")
        _timestamp(self.evaluated_at, "evaluated_at")
        if not isinstance(self.source_state, CognitiveState) or not isinstance(
            self.target_state, CognitiveState
        ):
            raise ValueError("evaluation states must be CognitiveState objects")
        if not isinstance(self.transition_definition, CognitiveTransition):
            raise ValueError("transition_definition must be a CognitiveTransition")
        definition = self.transition_definition
        if (
            self.transition_id != definition.transition_id
            or self.transition_fingerprint != definition.fingerprint
            or self.source_state != definition.source_state
            or self.target_state != definition.target_state
            or self.evaluator_id != definition.evaluator_id
            or self.evaluator_version != definition.evaluator_version
        ):
            raise ValueError("transition evaluation does not match its definition")
        results = tuple(
            sorted(
                tuple(self.requirement_results), key=lambda item: item.requirement_id
            )
        )
        if any(not isinstance(item, RequirementEvaluation) for item in results):
            raise ValueError("requirement_results are malformed")
        if not results:
            raise ValueError("transition evaluation requires requirement results")
        if len({item.requirement_id for item in results}) != len(results):
            raise ValueError("requirement result IDs must be unique")
        object.__setattr__(self, "requirement_results", results)
        requirements = definition.requirements
        if len(requirements) != len(results) or any(
            requirement.requirement_id != result.requirement_id
            or requirement.requirement_type is not result.requirement_type
            or requirement.subject_id != result.subject_id
            or requirement.mandatory is not result.mandatory
            for requirement, result in zip(requirements, results)
        ):
            raise ValueError(
                "requirement results do not match the transition definition"
            )
        for name in ("blocking_requirements", "evidence_ids", "claim_ids"):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        failed_ids = tuple(
            sorted(
                item.requirement_id
                for item in results
                if item.mandatory and not item.passed
            )
        )
        if self.blocking_requirements != failed_ids:
            raise ValueError(
                "blocking requirements do not match failed requirement results"
            )
        failures = {
            item.failure_status
            for item in results
            if item.mandatory and not item.passed
        }
        expected = (
            TransitionStatus.ALLOWED
            if not failures
            else next(item for item in _STATUS_PRIORITY if item in failures)
        )
        if self.status is not expected or self.allowed is not (
            self.status is TransitionStatus.ALLOWED
        ):
            raise ValueError(
                "transition status is inconsistent with requirement results"
            )
        if self.status is TransitionStatus.ALLOWED and token is not _EVALUATION_TOKEN:
            raise ValueError("ALLOWED transition status must be earned by evaluation")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "transition_fingerprint": self.transition_fingerprint,
            "transition_definition": self.transition_definition.canonical_dict(),
            "status": self.status.value,
            "allowed": self.allowed,
            "evaluated_at": _iso(self.evaluated_at),
            "source_state": self.source_state.canonical_dict(),
            "target_state": self.target_state.canonical_dict(),
            "requirement_results": [
                item.to_dict() for item in self.requirement_results
            ],
            "blocking_requirements": list(self.blocking_requirements),
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "graph_fingerprint": self.graph_fingerprint,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_canonical_json(cls, serialized: str) -> TransitionEvaluation:
        try:
            payload = json.loads(serialized)
            status = TransitionStatus(payload["status"])
            definition = CognitiveTransition.from_canonical_json(
                _canonical(payload["transition_definition"])
            )
            results = tuple(
                RequirementEvaluation.from_dict(item)
                for item in payload["requirement_results"]
            )
            token = _EVALUATION_TOKEN if status is TransitionStatus.ALLOWED else None
            return cls(
                **{
                    **payload,
                    "status": status,
                    "transition_definition": definition,
                    "evaluated_at": _parse_timestamp(
                        payload["evaluated_at"], "evaluated_at"
                    ),
                    "source_state": CognitiveState.from_dict(payload["source_state"]),
                    "target_state": CognitiveState.from_dict(payload["target_state"]),
                    "requirement_results": results,
                    "_evaluation_token": token,
                }
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized transition evaluation is malformed") from exc


def _result(
    requirement: TransitionRequirement,
    passed: bool,
    reason: str,
    status: TransitionStatus | None,
    *,
    evidence_ids: tuple[str, ...] = (),
    claim_ids: tuple[str, ...] = (),
    observed: Any = None,
    required: Any = None,
) -> RequirementEvaluation:
    return RequirementEvaluation(
        requirement.requirement_id,
        requirement.requirement_type,
        passed,
        requirement.subject_id,
        reason,
        evidence_ids,
        claim_ids,
        observed,
        required,
        status,
        requirement.mandatory,
    )


def _evaluate_requirement(
    requirement: TransitionRequirement, graph: EvidenceGraph, at: datetime
) -> RequirementEvaluation:
    node = graph.nodes.get(requirement.subject_id)
    kind = requirement.requirement_type
    params = requirement.parameters
    if kind is RequirementType.EVIDENCE_VERIFIED:
        if not isinstance(node, EvidenceNode):
            return _result(
                requirement,
                False,
                "evidence_missing",
                TransitionStatus.BLOCKED_MISSING_EVIDENCE,
                required="VERIFIED",
            )
        evidence = node.evidence
        if evidence.is_stale(at=at):
            status = TransitionStatus.BLOCKED_STALE_EVIDENCE
        elif evidence.verification_status is VerificationStatus.UNVERIFIED:
            status = TransitionStatus.BLOCKED_UNVERIFIED_EVIDENCE
        elif evidence.verification_status is VerificationStatus.REJECTED:
            status = TransitionStatus.BLOCKED_REJECTED_EVIDENCE
        elif evidence.verification_status is VerificationStatus.CONTRADICTED:
            status = TransitionStatus.BLOCKED_CONTRADICTION
        else:
            status = None
        return _result(
            requirement,
            status is None,
            "verified" if status is None else "evidence_inadmissible",
            status,
            evidence_ids=(node.node_id,),
            observed=evidence.verification_status.value,
            required="VERIFIED",
        )
    if kind is RequirementType.SUPPORT_COMPLETE:
        if not isinstance(node, ClaimNode):
            return _result(
                requirement,
                False,
                "claim_or_graph_dependency_missing",
                TransitionStatus.BLOCKED_GRAPH_INCOMPLETE,
                claim_ids=(requirement.subject_id,),
            )
        complete = graph.is_support_complete(requirement.subject_id, at=at)
        status = None
        if not complete.complete:
            if complete.unresolved_dependencies:
                status = TransitionStatus.BLOCKED_GRAPH_INCOMPLETE
            elif complete.stale_evidence_ids:
                status = TransitionStatus.BLOCKED_STALE_EVIDENCE
            elif complete.rejected_evidence_ids:
                status = TransitionStatus.BLOCKED_REJECTED_EVIDENCE
            elif complete.unverified_evidence_ids:
                status = TransitionStatus.BLOCKED_UNVERIFIED_EVIDENCE
            elif complete.contradicted_dependencies:
                status = TransitionStatus.BLOCKED_CONTRADICTION
            elif complete.missing_constraints or complete.failed_constraints:
                status = TransitionStatus.BLOCKED_CONSTRAINT
            else:
                status = TransitionStatus.BLOCKED_GRAPH_INCOMPLETE
        evidence_ids = tuple(
            sorted(
                set(complete.supporting_evidence_ids)
                | set(complete.stale_evidence_ids)
                | set(complete.unverified_evidence_ids)
                | set(complete.rejected_evidence_ids)
                | set(complete.contradicted_dependencies)
            )
        )
        return _result(
            requirement,
            complete.complete,
            "support_complete" if complete.complete else "support_incomplete",
            status,
            evidence_ids=evidence_ids,
            claim_ids=(requirement.subject_id,),
            observed=complete.complete,
            required=True,
        )
    if kind is RequirementType.CLAIM_STATE:
        allowed_states = params.get("allowed_states")
        if not isinstance(allowed_states, tuple) or not allowed_states:
            return _result(
                requirement,
                False,
                "allowed_states_missing",
                TransitionStatus.BLOCKED_CLAIM_STATE,
            )
        if not isinstance(node, ClaimNode):
            return _result(
                requirement,
                False,
                "claim_missing",
                TransitionStatus.BLOCKED_CLAIM_STATE,
                required=list(allowed_states),
            )
        passed = node.claim.epistemic_state.value in allowed_states
        return _result(
            requirement,
            passed,
            "claim_state_matches" if passed else "claim_state_mismatch",
            None if passed else TransitionStatus.BLOCKED_CLAIM_STATE,
            claim_ids=(node.node_id,),
            observed=node.claim.epistemic_state.value,
            required=list(allowed_states),
        )
    if kind is RequirementType.CONSTRAINT_SATISFIED:
        passed = (
            isinstance(node, ConstraintNode)
            and node.required
            and node.status is ConstraintStatus.SATISFIED
        )
        observed = node.status.value if isinstance(node, ConstraintNode) else None
        return _result(
            requirement,
            passed,
            "constraint_satisfied" if passed else "constraint_not_satisfied",
            None if passed else TransitionStatus.BLOCKED_CONSTRAINT,
            observed=observed,
            required="SATISFIED",
        )
    if kind is RequirementType.MAX_UNCERTAINTY:
        uncertainty = (
            node.evidence.uncertainty
            if isinstance(node, EvidenceNode)
            else node.claim.uncertainty if isinstance(node, ClaimNode) else None
        )
        metric = params.get("metric")
        threshold = params.get("threshold")
        observed: float | None = None
        passed = False
        if (
            uncertainty is not None
            and isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and math.isfinite(threshold)
        ):
            if metric == "minimum_confidence" and uncertainty.confidence is not None:
                observed, passed = (
                    uncertainty.confidence,
                    uncertainty.confidence >= threshold,
                )
            elif (
                metric == "maximum_width"
                and uncertainty.lower is not None
                and uncertainty.upper is not None
            ):
                observed = uncertainty.upper - uncertainty.lower
                passed = observed <= threshold
        return _result(
            requirement,
            passed,
            (
                "uncertainty_within_limit"
                if passed
                else "uncertainty_missing_or_exceeds_limit"
            ),
            None if passed else TransitionStatus.BLOCKED_UNCERTAINTY,
            evidence_ids=(node.node_id,) if isinstance(node, EvidenceNode) else (),
            claim_ids=(node.node_id,) if isinstance(node, ClaimNode) else (),
            observed=observed,
            required={"metric": metric, "threshold": threshold},
        )
    if kind in {
        RequirementType.NO_UNRESOLVED_CONTRADICTION,
        RequirementType.NO_INVALIDATION,
    }:
        if not isinstance(node, ClaimNode):
            status = (
                TransitionStatus.BLOCKED_CONTRADICTION
                if kind is RequirementType.NO_UNRESOLVED_CONTRADICTION
                else TransitionStatus.BLOCKED_INVALIDATION
            )
            return _result(requirement, False, "claim_missing", status)
        wanted = (
            EdgeType.CONTRADICTS
            if kind is RequirementType.NO_UNRESOLVED_CONTRADICTION
            else EdgeType.INVALIDATES
        )
        evidence_found: set[str] = set()
        visited_claims: set[str] = set()

        def collect(current_id: str) -> None:
            if current_id in visited_claims:
                return
            visited_claims.add(current_id)
            for edge in graph.edges:
                if edge.target_id == current_id and edge.edge_type is wanted:
                    evidence_found.add(edge.source_id)
                if (
                    edge.target_id == current_id
                    and edge.edge_type is EdgeType.DERIVES
                    and isinstance(graph.nodes[edge.source_id], ClaimNode)
                ):
                    collect(edge.source_id)

        collect(node.node_id)
        evidence_ids = tuple(sorted(evidence_found))
        passed = not evidence_ids
        status = (
            TransitionStatus.BLOCKED_CONTRADICTION
            if wanted is EdgeType.CONTRADICTS
            else TransitionStatus.BLOCKED_INVALIDATION
        )
        return _result(
            requirement,
            passed,
            "branch_absent" if passed else "unresolved_branch_present",
            None if passed else status,
            evidence_ids=evidence_ids,
            claim_ids=(node.node_id,),
            observed=list(evidence_ids),
            required=[],
        )
    if kind is RequirementType.TRANSFORMATION_PRESENT:
        transformation_type, version = params.get("transformation_type"), params.get(
            "version"
        )
        transformations = (
            graph.explain(requirement.subject_id).transformations
            if isinstance(node, ClaimNode)
            else ()
        )
        matched = tuple(
            item
            for item in transformations
            if isinstance(graph.nodes[item], TransformationNode)
            and graph.nodes[item].transformation_type == transformation_type
            and graph.nodes[item].version == version
        )
        passed = bool(matched)
        return _result(
            requirement,
            passed,
            (
                "transformation_present"
                if passed
                else "transformation_missing_or_mismatched"
            ),
            None if passed else TransitionStatus.BLOCKED_TRANSFORMATION,
            claim_ids=(requirement.subject_id,) if isinstance(node, ClaimNode) else (),
            observed=list(matched),
            required={"transformation_type": transformation_type, "version": version},
        )
    source, target, edge_name = (
        params.get("source_id"),
        params.get("target_id"),
        params.get("edge_type"),
    )
    passed = (
        isinstance(source, str)
        and isinstance(target, str)
        and isinstance(edge_name, str)
        and any(
            edge.source_id == source
            and edge.target_id == target
            and edge.edge_type.value == edge_name
            for edge in graph.edges
        )
    )
    return _result(
        requirement,
        passed,
        "dependency_present" if passed else "dependency_missing",
        None if passed else TransitionStatus.BLOCKED_DEPENDENCY,
        observed=passed,
        required={"source_id": source, "target_id": target, "edge_type": edge_name},
    )


def evaluate_transition(
    transition: CognitiveTransition, graph: EvidenceGraph, *, at: datetime
) -> TransitionEvaluation:
    if not isinstance(transition, CognitiveTransition) or not isinstance(
        graph, EvidenceGraph
    ):
        raise ValueError("transition and graph must use VERA-RAP research types")
    _timestamp(at, "at")
    results = tuple(
        _evaluate_requirement(item, graph, at) for item in transition.requirements
    )
    blockers = tuple(
        item
        for item, result in zip(transition.requirements, results)
        if item.mandatory and not result.passed
    )
    blocking_statuses = {
        result.failure_status
        for item, result in zip(transition.requirements, results)
        if item.mandatory and not result.passed
    }
    status = (
        TransitionStatus.ALLOWED
        if not blocking_statuses
        else next(item for item in _STATUS_PRIORITY if item in blocking_statuses)
    )
    evidence_ids = tuple(
        sorted(
            set(transition.source_state.evidence_ids)
            | set(transition.target_state.evidence_ids)
            | {item for result in results for item in result.evidence_ids}
        )
    )
    claim_ids = tuple(
        sorted(
            set(transition.source_state.claim_ids)
            | set(transition.target_state.claim_ids)
            | {item for result in results for item in result.claim_ids}
        )
    )
    return TransitionEvaluation(
        transition.transition_id,
        transition.fingerprint,
        transition,
        status,
        status is TransitionStatus.ALLOWED,
        at,
        transition.source_state,
        transition.target_state,
        results,
        tuple(item.requirement_id for item in blockers),
        evidence_ids,
        claim_ids,
        graph.fingerprint,
        transition.evaluator_id,
        transition.evaluator_version,
        _evaluation_token=_EVALUATION_TOKEN,
    )


@dataclass(frozen=True, slots=True)
class ControlledDemonstrator:
    graph: EvidenceGraph
    transitions: tuple[CognitiveTransition, ...]


def build_controlled_demonstrator() -> ControlledDemonstrator:
    """Build a synthetic Observation→Hazard→Vulnerability→Materiality fixture."""
    digest = "d" * 64
    evidence = EvidenceObject(
        "E1",
        "synthetic",
        "synthetic-source",
        "urn:vera-rap:synthetic:E1",
        digest,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        None,
        None,
        None,
        None,
        {"synthetic": True},
        None,
        None,
        "research-only",
        VerificationStatus.VERIFIED,
        provenance=Provenance("synthetic-source", "controlled-fixture", digest),
    )
    claims = (
        ClaimObject(
            "C1",
            "represents",
            "observation",
            "physical_state",
            None,
            EpistemicState.OBSERVED,
            ("E1",),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            derivation_method="synthetic",
        ),
        ClaimObject(
            "C2",
            "abstracts",
            "physical_state",
            "hazard",
            None,
            EpistemicState.INFERRED,
            parent_claim_ids=("C1",),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            derivation_method="synthetic",
        ),
        ClaimObject(
            "C3",
            "abstracts",
            "hazard",
            "vulnerability",
            None,
            EpistemicState.INFERRED,
            parent_claim_ids=("C2",),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            derivation_method="synthetic",
        ),
        ClaimObject(
            "C4",
            "abstracts",
            "vulnerability",
            "materiality",
            None,
            EpistemicState.INFERRED,
            parent_claim_ids=("C3",),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            derivation_method="synthetic",
        ),
    )
    constraint = ConstraintNode(
        "K1",
        "synthetic_integrity",
        "Synthetic demonstrator integrity",
        True,
        ConstraintStatus.SATISFIED,
    )
    graph = EvidenceGraph(
        (EvidenceNode(evidence), *(ClaimNode(item) for item in claims), constraint),
        (
            GraphEdge("E1", "C1", EdgeType.SUPPORTS),
            GraphEdge("C1", "C2", EdgeType.DERIVES),
            GraphEdge("C2", "C3", EdgeType.DERIVES),
            GraphEdge("C3", "C4", EdgeType.DERIVES),
            *(GraphEdge(item.claim_id, "K1", EdgeType.REQUIRES) for item in claims[1:]),
        ),
    )
    state_names = ("OBSERVATION", "HAZARD", "VULNERABILITY", "MATERIALITY")
    states = tuple(
        CognitiveState(f"S{index}", name, index, (claims[index - 1].claim_id,))
        for index, name in enumerate(state_names, 1)
    )
    transitions = tuple(
        CognitiveTransition(
            f"T{index}",
            "synthetic_abstraction",
            states[index - 1],
            states[index],
            (
                TransitionRequirement(
                    f"R{index}-support",
                    RequirementType.SUPPORT_COMPLETE,
                    claims[index].claim_id,
                    {},
                    True,
                    "Current support must be complete",
                ),
                TransitionRequirement(
                    f"R{index}-constraint",
                    RequirementType.CONSTRAINT_SATISFIED,
                    "K1",
                    {},
                    True,
                    "Synthetic constraint must be satisfied",
                ),
            ),
            "controlled-demonstrator",
            "1",
        )
        for index in range(1, 4)
    )
    return ControlledDemonstrator(graph, transitions)
