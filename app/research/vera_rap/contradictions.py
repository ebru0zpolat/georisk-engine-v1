"""First-class contradiction artifacts for isolated VERA-RAP research."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .claims import EpistemicState
from .evidence import (
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
    TransformationNode,
)


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(
            f"{type(self).__name__} cannot be coerced to a string implicitly"
        )

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as an implicit boolean")


class ContradictionType(_StrictEnum):
    DIRECT_VALUE_CONFLICT = "DIRECT_VALUE_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    UNIT_OR_REPRESENTATION_CONFLICT = "UNIT_OR_REPRESENTATION_CONFLICT"
    METHOD_CONFLICT = "METHOD_CONFLICT"
    PROVENANCE_CONFLICT = "PROVENANCE_CONFLICT"
    CLAIM_CONFLICT = "CLAIM_CONFLICT"
    CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
    TRANSFORMATION_CONFLICT = "TRANSFORMATION_CONFLICT"
    UNKNOWN_CONFLICT = "UNKNOWN_CONFLICT"


class ContradictionStatus(_StrictEnum):
    DETECTED = "DETECTED"
    UNRESOLVED = "UNRESOLVED"
    RESOLUTION_PENDING = "RESOLUTION_PENDING"
    RESOLVED = "RESOLVED"
    IRRESOLVABLE = "IRRESOLVABLE"
    REJECTED = "REJECTED"


class ResolutionRequirementType(_StrictEnum):
    INDEPENDENT_EVIDENCE_REQUIRED = "INDEPENDENT_EVIDENCE_REQUIRED"
    SOURCE_PROVENANCE_REQUIRED = "SOURCE_PROVENANCE_REQUIRED"
    TEMPORAL_ALIGNMENT_REQUIRED = "TEMPORAL_ALIGNMENT_REQUIRED"
    SCOPE_ALIGNMENT_REQUIRED = "SCOPE_ALIGNMENT_REQUIRED"
    UNIT_NORMALIZATION_REQUIRED = "UNIT_NORMALIZATION_REQUIRED"
    METHOD_COMPARISON_REQUIRED = "METHOD_COMPARISON_REQUIRED"
    CONSTRAINT_REEVALUATION_REQUIRED = "CONSTRAINT_REEVALUATION_REQUIRED"
    TRANSFORMATION_VERIFICATION_REQUIRED = "TRANSFORMATION_VERIFICATION_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    ADDITIONAL_OBSERVATION_REQUIRED = "ADDITIONAL_OBSERVATION_REQUIRED"


_TERMINAL = frozenset(
    {
        ContradictionStatus.RESOLVED,
        ContradictionStatus.IRRESOLVABLE,
        ContradictionStatus.REJECTED,
    }
)
_TOKEN = object()


def _items(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")
    result = tuple(value)
    for item in result:
        _required_text(item, f"{name} item")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(result))


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class ResolutionRequirement:
    requirement_id: str
    requirement_type: ResolutionRequirementType
    subject_ids: tuple[str, ...]
    parameters: Mapping[str, Any]
    mandatory: bool
    description: str

    def __post_init__(self) -> None:
        _required_text(self.requirement_id, "requirement_id")
        _required_text(self.description, "description")
        if not isinstance(self.requirement_type, ResolutionRequirementType):
            raise ValueError("requirement_type must be a ResolutionRequirementType")
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be a boolean")
        object.__setattr__(self, "subject_ids", _items(self.subject_ids, "subject_ids"))
        frozen = _freeze_json(self.parameters, "parameters")
        if not isinstance(frozen, Mapping):
            raise ValueError("parameters must be an object")
        object.__setattr__(self, "parameters", frozen)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type.value,
            "subject_ids": list(self.subject_ids),
            "parameters": _plain_json(self.parameters),
            "mandatory": self.mandatory,
            "description": self.description,
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> ResolutionRequirement:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("resolution requirement fields do not match schema")
        return cls(
            **{
                **value,
                "requirement_type": ResolutionRequirementType(
                    value["requirement_type"]
                ),
            }
        )

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ResolutionRequirement:
        try:
            return cls.from_dict(json.loads(serialized))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized resolution requirement is malformed") from exc


@dataclass(frozen=True, slots=True)
class ContradictionResolutionResult:
    target_status: ContradictionStatus
    satisfied_requirement_ids: tuple[str, ...]
    unsatisfied_requirement_ids: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    rejected_evidence_ids: tuple[str, ...]
    superseded_claim_ids: tuple[str, ...]
    retained_claim_ids: tuple[str, ...]
    resolver_id: str
    resolver_version: str
    resolved_at: datetime
    resolution_basis: str
    notes_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target_status, ContradictionStatus)
            or self.target_status not in _TERMINAL
        ):
            raise ValueError(
                "resolution target_status must be a terminal ContradictionStatus"
            )
        for name in ("resolver_id", "resolver_version", "resolution_basis"):
            _required_text(getattr(self, name), name)
        _timestamp(self.resolved_at, "resolved_at")
        for name in (
            "satisfied_requirement_ids",
            "unsatisfied_requirement_ids",
            "supporting_evidence_ids",
            "rejected_evidence_ids",
            "superseded_claim_ids",
            "retained_claim_ids",
        ):
            object.__setattr__(self, name, _items(getattr(self, name), name))
        if set(self.satisfied_requirement_ids) & set(self.unsatisfied_requirement_ids):
            raise ValueError("a requirement cannot be both satisfied and unsatisfied")
        if set(self.supporting_evidence_ids) & set(self.rejected_evidence_ids):
            raise ValueError("evidence cannot be both supporting and rejected")
        if set(self.superseded_claim_ids) & set(self.retained_claim_ids):
            raise ValueError("claims cannot be both superseded and retained")
        frozen = _freeze_json(self.notes_metadata, "notes_metadata")
        if frozen is not None and not isinstance(frozen, Mapping):
            raise ValueError("notes_metadata must be an object or null")
        object.__setattr__(self, "notes_metadata", frozen)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "target_status": self.target_status.value,
            "satisfied_requirement_ids": list(self.satisfied_requirement_ids),
            "unsatisfied_requirement_ids": list(self.unsatisfied_requirement_ids),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "rejected_evidence_ids": list(self.rejected_evidence_ids),
            "superseded_claim_ids": list(self.superseded_claim_ids),
            "retained_claim_ids": list(self.retained_claim_ids),
            "resolver_id": self.resolver_id,
            "resolver_version": self.resolver_version,
            "resolved_at": _iso(self.resolved_at),
            "resolution_basis": self.resolution_basis,
            "notes_metadata": _plain_json(self.notes_metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> ContradictionResolutionResult:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("resolution result fields do not match schema")
        return cls(
            **{
                **value,
                "target_status": ContradictionStatus(value["target_status"]),
                "resolved_at": _parse_timestamp(value["resolved_at"], "resolved_at"),
            }
        )

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ContradictionResolutionResult:
        try:
            return cls.from_dict(json.loads(serialized))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized resolution result is malformed") from exc


@dataclass(frozen=True, slots=True, init=False)
class ContradictionObject:
    contradiction_id: str
    contradiction_type: ContradictionType
    status: ContradictionStatus
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    constraint_ids: tuple[str, ...]
    transformation_ids: tuple[str, ...]
    detected_at: datetime
    scope: Any
    conflict_dimensions: tuple[str, ...]
    resolution_requirements: tuple[ResolutionRequirement, ...]
    resolution_history: tuple[ContradictionResolutionResult, ...]
    metadata: Mapping[str, Any] | None

    def __init__(
        self,
        contradiction_id: str,
        contradiction_type: ContradictionType,
        status: ContradictionStatus,
        evidence_ids: tuple[str, ...] = (),
        claim_ids: tuple[str, ...] = (),
        constraint_ids: tuple[str, ...] = (),
        transformation_ids: tuple[str, ...] = (),
        *,
        detected_at: datetime,
        scope: Any = None,
        conflict_dimensions: tuple[str, ...] = (),
        resolution_requirements: tuple[ResolutionRequirement, ...] = (),
        resolution_history: tuple[ContradictionResolutionResult, ...] = (),
        metadata: Mapping[str, Any] | None = None,
        _resolution_token: object | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            object.__setattr__(self, item.name, values[item.name])
        self._validate(_resolution_token)

    def _validate(self, token: object | None) -> None:
        _required_text(self.contradiction_id, "contradiction_id")
        if not isinstance(self.contradiction_type, ContradictionType) or not isinstance(
            self.status, ContradictionStatus
        ):
            raise ValueError("contradiction type and status must be enum members")
        if self.status in _TERMINAL and token is not _TOKEN:
            raise ValueError(
                "terminal contradiction status must be earned by resolution"
            )
        _timestamp(self.detected_at, "detected_at")
        for name in (
            "evidence_ids",
            "claim_ids",
            "constraint_ids",
            "transformation_ids",
            "conflict_dimensions",
        ):
            object.__setattr__(self, name, _items(getattr(self, name), name))
        if not (
            self.evidence_ids
            or self.claim_ids
            or self.constraint_ids
            or self.transformation_ids
        ):
            raise ValueError("a contradiction must reference an epistemic object")
        for name in ("scope", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        requirements = tuple(
            sorted(
                tuple(self.resolution_requirements),
                key=lambda item: item.requirement_id,
            )
        )
        if any(
            not isinstance(item, ResolutionRequirement) for item in requirements
        ) or len({item.requirement_id for item in requirements}) != len(requirements):
            raise ValueError("resolution requirements are malformed or duplicated")
        object.__setattr__(self, "resolution_requirements", requirements)
        history = tuple(self.resolution_history)
        if any(not isinstance(item, ContradictionResolutionResult) for item in history):
            raise ValueError("resolution history is malformed")
        object.__setattr__(self, "resolution_history", history)
        if self.status in _TERMINAL and (
            not history or history[-1].target_status is not self.status
        ):
            raise ValueError("terminal status requires matching resolution history")
        if self.status in _TERMINAL:
            final = history[-1]
            requirement_ids = {
                item.requirement_id for item in self.resolution_requirements
            }
            accounted = set(final.satisfied_requirement_ids) | set(
                final.unsatisfied_requirement_ids
            )
            if accounted != requirement_ids:
                raise ValueError("resolution history does not account for requirements")
            mandatory = {
                item.requirement_id
                for item in self.resolution_requirements
                if item.mandatory
            }
            if final.target_status is ContradictionStatus.RESOLVED and (
                not mandatory.issubset(final.satisfied_requirement_ids)
                or not final.supporting_evidence_ids
            ):
                raise ValueError(
                    "RESOLVED history requires mandatory satisfaction and evidence"
                )
            if (
                final.target_status is ContradictionStatus.IRRESOLVABLE
                and not final.unsatisfied_requirement_ids
            ):
                raise ValueError("IRRESOLVABLE history requires exhausted requirements")

    def with_resolution(
        self, result: ContradictionResolutionResult, graph: EvidenceGraph
    ) -> ContradictionObject:
        if not isinstance(result, ContradictionResolutionResult) or not isinstance(
            graph, EvidenceGraph
        ):
            raise ValueError("resolution requires typed result and EvidenceGraph")
        requirement_ids = {item.requirement_id for item in self.resolution_requirements}
        accounted = set(result.satisfied_requirement_ids) | set(
            result.unsatisfied_requirement_ids
        )
        if accounted != requirement_ids:
            raise ValueError("resolution must account for every defined requirement")
        mandatory = {
            item.requirement_id
            for item in self.resolution_requirements
            if item.mandatory
        }
        if result.target_status is ContradictionStatus.RESOLVED:
            if not mandatory.issubset(result.satisfied_requirement_ids):
                raise ValueError(
                    "RESOLVED requires every mandatory requirement satisfied"
                )
            if not result.supporting_evidence_ids:
                raise ValueError("RESOLVED requires explicit resolution evidence")
        if (
            result.target_status is ContradictionStatus.IRRESOLVABLE
            and not result.unsatisfied_requirement_ids
        ):
            raise ValueError(
                "IRRESOLVABLE requires an exhausted unsatisfied requirement"
            )
        for evidence_id in result.supporting_evidence_ids:
            node = graph.nodes.get(evidence_id)
            if (
                not isinstance(node, EvidenceNode)
                or node.evidence.verification_status is not VerificationStatus.VERIFIED
                or node.evidence.is_stale(at=result.resolved_at)
            ):
                raise ValueError("resolution evidence must be admissible and current")
        return ContradictionObject(
            self.contradiction_id,
            self.contradiction_type,
            result.target_status,
            self.evidence_ids,
            self.claim_ids,
            self.constraint_ids,
            self.transformation_ids,
            detected_at=self.detected_at,
            scope=self.scope,
            conflict_dimensions=self.conflict_dimensions,
            resolution_requirements=self.resolution_requirements,
            resolution_history=(*self.resolution_history, result),
            metadata=self.metadata,
            _resolution_token=_TOKEN,
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "contradiction_type": self.contradiction_type.value,
            "status": self.status.value,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "constraint_ids": list(self.constraint_ids),
            "transformation_ids": list(self.transformation_ids),
            "detected_at": _iso(self.detected_at),
            "scope": _plain_json(self.scope),
            "conflict_dimensions": list(self.conflict_dimensions),
            "resolution_requirements": [
                item.canonical_dict() for item in self.resolution_requirements
            ],
            "resolution_history": [
                item.canonical_dict() for item in self.resolution_history
            ],
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ContradictionObject:
        try:
            value = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized contradiction must be valid JSON") from exc
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("contradiction fields do not match schema")
        status = ContradictionStatus(value["status"])
        history = tuple(
            ContradictionResolutionResult.from_dict(item)
            for item in value["resolution_history"]
        )
        return cls(
            **{
                **value,
                "contradiction_type": ContradictionType(value["contradiction_type"]),
                "status": status,
                "detected_at": _parse_timestamp(value["detected_at"], "detected_at"),
                "resolution_requirements": tuple(
                    ResolutionRequirement.from_dict(item)
                    for item in value["resolution_requirements"]
                ),
                "resolution_history": history,
                "_resolution_token": _TOKEN if status in _TERMINAL else None,
            }
        )


def _contradiction_id(
    kind: ContradictionType, references: tuple[str, ...], dimensions: tuple[str, ...]
) -> str:
    digest = hashlib.sha256(
        _canonical(
            {
                "type": kind.value,
                "references": list(sorted(references)),
                "dimensions": list(sorted(dimensions)),
            }
        ).encode()
    ).hexdigest()
    return f"contradiction-{digest}"


def _requirement(
    kind: ResolutionRequirementType, subjects: tuple[str, ...]
) -> ResolutionRequirement:
    return ResolutionRequirement(
        f"requirement-{kind.value.lower()}",
        kind,
        subjects,
        {},
        True,
        "Explicit resolution input required",
    )


def _artifact(
    kind: ContradictionType,
    *,
    at: datetime,
    evidence: tuple[str, ...] = (),
    claims: tuple[str, ...] = (),
    constraints: tuple[str, ...] = (),
    transformations: tuple[str, ...] = (),
    dimensions: tuple[str, ...],
    requirements: tuple[ResolutionRequirement, ...] = (),
    scope: Any = None,
) -> ContradictionObject:
    references = (*evidence, *claims, *constraints, *transformations)
    return ContradictionObject(
        _contradiction_id(kind, references, dimensions),
        kind,
        ContradictionStatus.UNRESOLVED,
        evidence,
        claims,
        constraints,
        transformations,
        detected_at=at,
        scope=scope,
        conflict_dimensions=dimensions,
        resolution_requirements=requirements,
    )


def _overlap(first: EvidenceNode, second: EvidenceNode) -> bool:
    a, b = first.evidence, second.evidence
    a_start, b_start = a.valid_from or a.observed_at, b.valid_from or b.observed_at
    a_end, b_end = a.valid_until or a.observed_at, b.valid_until or b.observed_at
    return bool(
        a_start
        and b_start
        and a_end
        and b_end
        and max(a_start, b_start) <= min(a_end, b_end)
    )


def find_contradictions(
    graph: EvidenceGraph, *, at: datetime, value_tolerance: float = 0.0
) -> tuple[ContradictionObject, ...]:
    _timestamp(at, "at")
    if (
        isinstance(value_tolerance, bool)
        or not isinstance(value_tolerance, (int, float))
        or not math.isfinite(value_tolerance)
        or value_tolerance < 0
    ):
        raise ValueError("value_tolerance must be a finite non-negative number")
    found: dict[str, ContradictionObject] = {}
    for edge in graph.edges:
        if edge.edge_type in {EdgeType.CONTRADICTS, EdgeType.INVALIDATES}:
            item = _artifact(
                ContradictionType.CLAIM_CONFLICT,
                at=at,
                evidence=(edge.source_id,),
                claims=(edge.target_id,),
                dimensions=(edge.edge_type.value.lower(),),
            )
            found[item.contradiction_id] = item
        elif edge.edge_type is EdgeType.REQUIRES:
            node = graph.nodes[edge.target_id]
            if (
                isinstance(node, ConstraintNode)
                and node.status is ConstraintStatus.VIOLATED
            ):
                item = _artifact(
                    ContradictionType.CONSTRAINT_CONFLICT,
                    at=at,
                    claims=(edge.source_id,),
                    constraints=(edge.target_id,),
                    dimensions=("violated_constraint",),
                    requirements=(
                        _requirement(
                            ResolutionRequirementType.CONSTRAINT_REEVALUATION_REQUIRED,
                            (edge.target_id,),
                        ),
                    ),
                )
                found[item.contradiction_id] = item
    for node in graph.nodes.values():
        if (
            isinstance(node, ClaimNode)
            and node.claim.epistemic_state is EpistemicState.CONTRADICTED
        ):
            item = _artifact(
                ContradictionType.CLAIM_CONFLICT,
                at=at,
                evidence=node.claim.contradicting_evidence_ids,
                claims=(node.node_id,),
                dimensions=("claim_state",),
            )
            found[item.contradiction_id] = item
    evidence_nodes = [
        node for node in graph.nodes.values() if isinstance(node, EvidenceNode)
    ]
    for index, first in enumerate(evidence_nodes):
        for second in evidence_nodes[index + 1 :]:
            a, b = first.evidence, second.evidence
            pair = (first.node_id, second.node_id)
            if a.content_hash == b.content_hash and a.source_id != b.source_id:
                item = _artifact(
                    ContradictionType.PROVENANCE_CONFLICT,
                    at=at,
                    evidence=pair,
                    dimensions=("source_id", "content_hash"),
                    requirements=(
                        _requirement(
                            ResolutionRequirementType.SOURCE_PROVENANCE_REQUIRED, pair
                        ),
                    ),
                )
                found[item.contradiction_id] = item
            if a.spatial_scope != b.spatial_scope or a.jurisdiction != b.jurisdiction:
                continue
            if a.evidence_type != b.evidence_type:
                continue
            if not _overlap(first, second):
                continue
            if a.unit != b.unit:
                item = _artifact(
                    ContradictionType.UNIT_OR_REPRESENTATION_CONFLICT,
                    at=at,
                    evidence=pair,
                    dimensions=("unit",),
                    requirements=(
                        _requirement(
                            ResolutionRequirementType.UNIT_NORMALIZATION_REQUIRED, pair
                        ),
                    ),
                    scope=a.spatial_scope,
                )
                found[item.contradiction_id] = item
                continue
            av = (
                a.measurement.get("value")
                if isinstance(a.measurement, Mapping)
                else None
            )
            bv = (
                b.measurement.get("value")
                if isinstance(b.measurement, Mapping)
                else None
            )
            am = (
                a.measurement.get("method")
                if isinstance(a.measurement, Mapping)
                else None
            )
            bm = (
                b.measurement.get("method")
                if isinstance(b.measurement, Mapping)
                else None
            )
            a_semantics = (
                (a.measurement.get("subject"), a.measurement.get("property"))
                if isinstance(a.measurement, Mapping)
                else None
            )
            b_semantics = (
                (b.measurement.get("subject"), b.measurement.get("property"))
                if isinstance(b.measurement, Mapping)
                else None
            )
            if a_semantics != b_semantics:
                continue
            if am is not None and bm is not None and am != bm:
                item = _artifact(
                    ContradictionType.METHOD_CONFLICT,
                    at=at,
                    evidence=pair,
                    dimensions=("method",),
                    requirements=(
                        _requirement(
                            ResolutionRequirementType.METHOD_COMPARISON_REQUIRED, pair
                        ),
                    ),
                    scope=a.spatial_scope,
                )
                found[item.contradiction_id] = item
            elif (
                isinstance(av, (int, float))
                and not isinstance(av, bool)
                and isinstance(bv, (int, float))
                and not isinstance(bv, bool)
                and abs(av - bv) > value_tolerance
            ):
                item = _artifact(
                    ContradictionType.DIRECT_VALUE_CONFLICT,
                    at=at,
                    evidence=pair,
                    dimensions=("measurement.value",),
                    requirements=(
                        _requirement(
                            ResolutionRequirementType.INDEPENDENT_EVIDENCE_REQUIRED,
                            pair,
                        ),
                    ),
                    scope=a.spatial_scope,
                )
                found[item.contradiction_id] = item
    # Multiple incompatible transformation producers are explicit method lineage conflicts.
    for target in graph.nodes:
        producers = tuple(
            sorted(
                edge.source_id
                for edge in graph.edges
                if edge.target_id == target
                and edge.edge_type is EdgeType.DERIVES
                and isinstance(graph.nodes[edge.source_id], TransformationNode)
            )
        )
        signatures = {(graph.nodes[item].transformation_type, graph.nodes[item].version) for item in producers}  # type: ignore[union-attr]
        if len(signatures) > 1:
            item = _artifact(
                ContradictionType.TRANSFORMATION_CONFLICT,
                at=at,
                transformations=producers,
                dimensions=("transformation_type", "version"),
                requirements=(
                    _requirement(
                        ResolutionRequirementType.TRANSFORMATION_VERIFICATION_REQUIRED,
                        producers,
                    ),
                ),
            )
            found[item.contradiction_id] = item
    return tuple(found[item] for item in sorted(found))


def evaluate_resolution(
    contradiction: ContradictionObject,
    result: ContradictionResolutionResult,
    graph: EvidenceGraph,
) -> ContradictionObject:
    return contradiction.with_resolution(result, graph)


def has_unresolved_contradiction(
    contradictions: tuple[ContradictionObject, ...],
) -> bool:
    return any(
        item.status
        in {
            ContradictionStatus.DETECTED,
            ContradictionStatus.UNRESOLVED,
            ContradictionStatus.RESOLUTION_PENDING,
        }
        for item in contradictions
    )
