"""Verified hierarchical abstraction DAG for VERA-RAP research."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .contradictions import ContradictionObject, ContradictionStatus
from .evidence import (
    _freeze_json,
    _iso,
    _plain_json,
    _required_text,
    _timestamp,
)
from .evidence_graph import ClaimNode, EvidenceGraph
from .transitions import CognitiveTransition, TransitionEvaluation, TransitionStatus
from .uncertainty import UncertaintyGateResult, UncertaintyProfile


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as boolean")


class AbstractionLevel(_StrictEnum):
    OBSERVATION = 0
    PHYSICAL_STATE = 1
    CONDITION = 2
    EXPOSURE = 3
    VULNERABILITY = 4
    IMPACT = 5
    MATERIALITY = 6
    DECISION = 7


class AbstractionStatus(_StrictEnum):
    PROPOSED = "PROPOSED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class AbstractionFailure(_StrictEnum):
    MISSING_CLAIM = "MISSING_CLAIM"
    SUPPORT_INCOMPLETE = "SUPPORT_INCOMPLETE"
    TRANSITION_BLOCKED = "TRANSITION_BLOCKED"
    UNRESOLVED_CONTRADICTION = "UNRESOLVED_CONTRADICTION"
    UNCERTAINTY_GATE_FAILED = "UNCERTAINTY_GATE_FAILED"
    MISSING_UPSTREAM_ABSTRACTION = "MISSING_UPSTREAM_ABSTRACTION"
    INVALID_LEVEL_TRANSITION = "INVALID_LEVEL_TRANSITION"
    CONSTRAINT_FAILED = "CONSTRAINT_FAILED"
    LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"


_TOKEN = object()


def _strings(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")
    result = tuple(value)
    for item in result:
        _required_text(item, f"{name} item")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} contains duplicates")
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
class AbstractionRule:
    rule_id: str
    source_levels: tuple[AbstractionLevel, ...]
    target_level: AbstractionLevel
    required_claim_predicates: tuple[str, ...]
    required_transition_type: str
    uncertainty_threshold_ids: tuple[str, ...]
    allow_level_skip: bool
    version: str
    description: str
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("rule_id", "required_transition_type", "version", "description"):
            _required_text(getattr(self, name), name)
        levels = tuple(sorted(tuple(self.source_levels), key=lambda item: item.value))
        if (
            not levels
            or any(not isinstance(item, AbstractionLevel) for item in levels)
            or not isinstance(self.target_level, AbstractionLevel)
        ):
            raise ValueError("abstraction rule levels are invalid")
        object.__setattr__(self, "source_levels", levels)
        for name in ("required_claim_predicates", "uncertainty_threshold_ids"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if not isinstance(self.allow_level_skip, bool):
            raise ValueError("allow_level_skip must be boolean")
        metadata = _freeze_json(self.metadata, "metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        object.__setattr__(self, "metadata", metadata)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "source_levels": [x.name for x in self.source_levels],
            "target_level": self.target_level.name,
            "required_claim_predicates": list(self.required_claim_predicates),
            "required_transition_type": self.required_transition_type,
            "uncertainty_threshold_ids": list(self.uncertainty_threshold_ids),
            "allow_level_skip": self.allow_level_skip,
            "version": self.version,
            "description": self.description,
            "metadata": _plain_json(self.metadata),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> AbstractionRule:
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("invalid abstraction rule payload")
        try:
            return cls(
                value["rule_id"],
                tuple(AbstractionLevel[x] for x in value["source_levels"]),
                AbstractionLevel[value["target_level"]],
                tuple(value["required_claim_predicates"]),
                value["required_transition_type"],
                tuple(value["uncertainty_threshold_ids"]),
                value["allow_level_skip"],
                value["version"],
                value["description"],
                value["metadata"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid abstraction rule payload") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> AbstractionRule:
        value = json.loads(serialized)
        result = cls.from_dict(value)
        if result.canonical_json() != serialized:
            raise ValueError("abstraction rule JSON is not canonical")
        return result


@dataclass(frozen=True, slots=True)
class AbstractionVerification:
    abstraction_id: str
    status: AbstractionStatus
    evaluated_at: datetime
    source_abstraction_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    transition_evaluation_ids: tuple[str, ...]
    support_completeness: tuple[tuple[str, bool], ...]
    contradiction_ids: tuple[str, ...]
    uncertainty_gate_results: tuple[UncertaintyGateResult, ...]
    failed_requirements: tuple[AbstractionFailure, ...]
    verifier_id: str
    verifier_version: str
    graph_fingerprint: str

    def __post_init__(self) -> None:
        _required_text(self.abstraction_id, "abstraction_id")
        _timestamp(self.evaluated_at, "evaluated_at")
        if self.status not in {AbstractionStatus.VERIFIED, AbstractionStatus.BLOCKED}:
            raise ValueError("verification status must be VERIFIED or BLOCKED")
        for name in ("verifier_id", "verifier_version", "graph_fingerprint"):
            _required_text(getattr(self, name), name)
        for name in (
            "source_abstraction_ids",
            "claim_ids",
            "transition_evaluation_ids",
            "contradiction_ids",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        support = tuple(sorted(tuple(self.support_completeness)))
        if any(not isinstance(a, str) or not isinstance(b, bool) for a, b in support):
            raise ValueError("support completeness records are invalid")
        object.__setattr__(self, "support_completeness", support)
        gates = tuple(
            sorted(tuple(self.uncertainty_gate_results), key=lambda x: x.threshold_id)
        )
        if any(not isinstance(x, UncertaintyGateResult) for x in gates):
            raise ValueError("uncertainty gate results are invalid")
        object.__setattr__(self, "uncertainty_gate_results", gates)
        failures = tuple(sorted(tuple(self.failed_requirements), key=lambda x: x.value))
        if any(not isinstance(x, AbstractionFailure) for x in failures):
            raise ValueError("failed requirements are invalid")
        object.__setattr__(self, "failed_requirements", failures)
        if (self.status is AbstractionStatus.VERIFIED) != (not failures):
            raise ValueError("verification status and blockers disagree")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "abstraction_id": self.abstraction_id,
            "status": self.status.value,
            "evaluated_at": _iso(self.evaluated_at),
            "source_abstraction_ids": list(self.source_abstraction_ids),
            "claim_ids": list(self.claim_ids),
            "transition_evaluation_ids": list(self.transition_evaluation_ids),
            "support_completeness": [[a, b] for a, b in self.support_completeness],
            "contradiction_ids": list(self.contradiction_ids),
            "uncertainty_gate_results": [
                x.canonical_dict() for x in self.uncertainty_gate_results
            ],
            "failed_requirements": [x.value for x in self.failed_requirements],
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "graph_fingerprint": self.graph_fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> AbstractionVerification:
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("invalid abstraction verification payload")
        try:
            return cls(
                value["abstraction_id"],
                AbstractionStatus(value["status"]),
                datetime.fromisoformat(value["evaluated_at"]),
                tuple(value["source_abstraction_ids"]),
                tuple(value["claim_ids"]),
                tuple(value["transition_evaluation_ids"]),
                tuple((x[0], x[1]) for x in value["support_completeness"]),
                tuple(value["contradiction_ids"]),
                tuple(
                    UncertaintyGateResult.from_dict(x)
                    for x in value["uncertainty_gate_results"]
                ),
                tuple(AbstractionFailure(x) for x in value["failed_requirements"]),
                value["verifier_id"],
                value["verifier_version"],
                value["graph_fingerprint"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid abstraction verification payload") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> AbstractionVerification:
        value = json.loads(serialized)
        result = cls.from_dict(value)
        if result.canonical_json() != serialized:
            raise ValueError("abstraction verification JSON is not canonical")
        return result


@dataclass(frozen=True, slots=True, init=False)
class AbstractionNode:
    abstraction_id: str
    abstraction_level: AbstractionLevel
    concept_type: str
    status: AbstractionStatus
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_abstraction_ids: tuple[str, ...]
    scope: Any
    uncertainty_profile_id: str | None
    transition_evaluation_id: str | None
    created_at: datetime
    verification_history: tuple[AbstractionVerification, ...]
    superseded_by: str | None
    metadata: Mapping[str, Any] | None

    def __init__(
        self,
        abstraction_id: str,
        abstraction_level: AbstractionLevel,
        concept_type: str,
        status: AbstractionStatus = AbstractionStatus.PROPOSED,
        claim_ids: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        source_abstraction_ids: tuple[str, ...] = (),
        *,
        scope: Any = None,
        uncertainty_profile_id: str | None = None,
        transition_evaluation_id: str | None = None,
        created_at: datetime,
        verification_history: tuple[AbstractionVerification, ...] = (),
        superseded_by: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        _token: object | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            object.__setattr__(self, item.name, values[item.name])
        for name in ("abstraction_id", "concept_type"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.abstraction_level, AbstractionLevel) or not isinstance(
            self.status, AbstractionStatus
        ):
            raise ValueError("level and status must be enum members")
        if self.status is AbstractionStatus.VERIFIED and _token is not _TOKEN:
            raise ValueError("VERIFIED abstraction must be earned")
        for name in ("claim_ids", "evidence_ids", "source_abstraction_ids"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        for name in (
            "uncertainty_profile_id",
            "transition_evaluation_id",
            "superseded_by",
        ):
            if getattr(self, name) is not None:
                _required_text(getattr(self, name), name)
        _timestamp(self.created_at, "created_at")
        history = tuple(self.verification_history)
        if any(not isinstance(x, AbstractionVerification) for x in history):
            raise ValueError("verification history is invalid")
        object.__setattr__(self, "verification_history", history)
        if self.status is AbstractionStatus.VERIFIED and (
            not history or history[-1].status is not AbstractionStatus.VERIFIED
        ):
            raise ValueError("VERIFIED requires matching history")
        if self.status is AbstractionStatus.VERIFIED and (
            history[-1].abstraction_id != self.abstraction_id
            or history[-1].claim_ids != self.claim_ids
            or history[-1].source_abstraction_ids != self.source_abstraction_ids
        ):
            raise ValueError("VERIFIED history does not bind the declared abstraction")
        for name in ("scope", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be object")

    def with_verification(
        self, verification: AbstractionVerification
    ) -> AbstractionNode:
        if verification.abstraction_id != self.abstraction_id:
            raise ValueError("verification targets another abstraction")
        return AbstractionNode(
            self.abstraction_id,
            self.abstraction_level,
            self.concept_type,
            verification.status,
            self.claim_ids,
            self.evidence_ids,
            self.source_abstraction_ids,
            scope=self.scope,
            uncertainty_profile_id=self.uncertainty_profile_id,
            transition_evaluation_id=self.transition_evaluation_id,
            created_at=self.created_at,
            verification_history=(*self.verification_history, verification),
            superseded_by=self.superseded_by,
            metadata=self.metadata,
            _token=_TOKEN,
        )

    def supersede(self, by: str) -> AbstractionNode:
        _required_text(by, "superseded_by")
        return AbstractionNode(
            self.abstraction_id,
            self.abstraction_level,
            self.concept_type,
            AbstractionStatus.SUPERSEDED,
            self.claim_ids,
            self.evidence_ids,
            self.source_abstraction_ids,
            scope=self.scope,
            uncertainty_profile_id=self.uncertainty_profile_id,
            transition_evaluation_id=self.transition_evaluation_id,
            created_at=self.created_at,
            verification_history=self.verification_history,
            superseded_by=by,
            metadata=self.metadata,
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "abstraction_id": self.abstraction_id,
            "abstraction_level": self.abstraction_level.name,
            "concept_type": self.concept_type,
            "status": self.status.value,
            "claim_ids": list(self.claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "source_abstraction_ids": list(self.source_abstraction_ids),
            "scope": _plain_json(self.scope),
            "uncertainty_profile_id": self.uncertainty_profile_id,
            "transition_evaluation_id": self.transition_evaluation_id,
            "created_at": _iso(self.created_at),
            "verification_history": [
                x.canonical_dict() for x in self.verification_history
            ],
            "superseded_by": self.superseded_by,
            "metadata": _plain_json(self.metadata),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_dict(cls, value: object) -> AbstractionNode:
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("invalid abstraction node payload")
        try:
            history = tuple(
                AbstractionVerification.from_dict(x)
                for x in value["verification_history"]
            )
            status = AbstractionStatus(value["status"])
            return cls(
                value["abstraction_id"],
                AbstractionLevel[value["abstraction_level"]],
                value["concept_type"],
                status,
                tuple(value["claim_ids"]),
                tuple(value["evidence_ids"]),
                tuple(value["source_abstraction_ids"]),
                scope=value["scope"],
                uncertainty_profile_id=value["uncertainty_profile_id"],
                transition_evaluation_id=value["transition_evaluation_id"],
                created_at=datetime.fromisoformat(value["created_at"]),
                verification_history=history,
                superseded_by=value["superseded_by"],
                metadata=value["metadata"],
                _token=_TOKEN if status is AbstractionStatus.VERIFIED else None,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid abstraction node payload") from exc

    @classmethod
    def from_canonical_json(cls, serialized: str) -> AbstractionNode:
        value = json.loads(serialized)
        result = cls.from_dict(value)
        if result.canonical_json() != serialized:
            raise ValueError("abstraction node JSON is not canonical")
        return result


@dataclass(frozen=True, slots=True)
class AbstractionEdge:
    source_abstraction_id: str
    target_abstraction_id: str
    transition_id: str
    required: bool
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("source_abstraction_id", "target_abstraction_id", "transition_id"):
            _required_text(getattr(self, name), name)
        if self.source_abstraction_id == self.target_abstraction_id:
            raise ValueError("self-loop is forbidden")
        if not isinstance(self.required, bool):
            raise ValueError("required must be boolean")
        value = _freeze_json(self.metadata, "metadata")
        if value is not None and not isinstance(value, Mapping):
            raise ValueError("metadata must be object")
        object.__setattr__(self, "metadata", value)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "source_abstraction_id": self.source_abstraction_id,
            "target_abstraction_id": self.target_abstraction_id,
            "transition_id": self.transition_id,
            "required": self.required,
            "metadata": _plain_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: object) -> AbstractionEdge:
        keys = {
            "source_abstraction_id",
            "target_abstraction_id",
            "transition_id",
            "required",
            "metadata",
        }
        if not isinstance(value, dict) or set(value) != keys:
            raise ValueError("invalid abstraction edge payload")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class AbstractionLineage:
    abstraction_id: str
    abstraction_level: AbstractionLevel
    claims: tuple[str, ...]
    direct_evidence: tuple[str, ...]
    upstream_abstractions: tuple[str, ...]
    transitions: tuple[str, ...]
    constraints: tuple[str, ...]
    contradictions: tuple[str, ...]
    uncertainty_profiles: tuple[str, ...]
    transformations: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]


class AbstractionGraph:
    __slots__ = ("nodes", "edges", "rules", "transitions")

    def __init__(
        self,
        nodes: tuple[AbstractionNode, ...],
        edges: tuple[AbstractionEdge, ...],
        rules: tuple[AbstractionRule, ...],
        transitions: tuple[CognitiveTransition, ...],
    ):
        node_map = {x.abstraction_id: x for x in nodes}
        rule_map = {x.rule_id: x for x in rules}
        trans_map = {x.transition_id: x for x in transitions}
        if (
            len(node_map) != len(nodes)
            or len(rule_map) != len(rules)
            or len(trans_map) != len(transitions)
        ):
            raise ValueError("duplicate abstraction graph identity")
        edge_values = tuple(
            sorted(
                tuple(edges),
                key=lambda x: (
                    x.source_abstraction_id,
                    x.target_abstraction_id,
                    x.transition_id,
                ),
            )
        )
        if len(
            set(
                (x.source_abstraction_id, x.target_abstraction_id, x.transition_id)
                for x in edge_values
            )
        ) != len(edge_values):
            raise ValueError("duplicate abstraction edge")
        adjacency = {x: [] for x in node_map}
        for edge in edge_values:
            if (
                edge.source_abstraction_id not in node_map
                or edge.target_abstraction_id not in node_map
            ):
                raise ValueError("abstraction edge references missing node")
            if edge.transition_id not in trans_map:
                raise ValueError("abstraction edge references missing transition")
            source, target = (
                node_map[edge.source_abstraction_id],
                node_map[edge.target_abstraction_id],
            )
            matching = [
                r
                for r in rule_map.values()
                if source.abstraction_level in r.source_levels
                and target.abstraction_level is r.target_level
                and r.required_transition_type
                == trans_map[edge.transition_id].transition_type
            ]
            if len(matching) != 1:
                raise ValueError("no unique abstraction rule permits edge")
            delta = target.abstraction_level.value - source.abstraction_level.value
            if delta <= 0 or (delta > 1 and not matching[0].allow_level_skip):
                raise ValueError("invalid abstraction level transition")
            adjacency[edge.source_abstraction_id].append(edge.target_abstraction_id)
        incoming = {node_id: set() for node_id in node_map}
        for edge in edge_values:
            if edge.required:
                incoming[edge.target_abstraction_id].add(edge.source_abstraction_id)
        for node_id, node in node_map.items():
            if set(node.source_abstraction_ids) != incoming[node_id]:
                raise ValueError("declared sources disagree with required edges")
        active: set[str] = set()
        done: set[str] = set()

        def visit(x: str) -> None:
            if x in active:
                raise ValueError("abstraction cycle detected")
            if x in done:
                return
            active.add(x)
            for y in sorted(adjacency[x]):
                visit(y)
            active.remove(x)
            done.add(x)

        for x in sorted(node_map):
            visit(x)
        object.__setattr__(
            self, "nodes", MappingProxyType(dict(sorted(node_map.items())))
        )
        object.__setattr__(self, "edges", edge_values)
        object.__setattr__(
            self, "rules", MappingProxyType(dict(sorted(rule_map.items())))
        )
        object.__setattr__(
            self, "transitions", MappingProxyType(dict(sorted(trans_map.items())))
        )

    def __setattr__(self, n: str, v: object) -> None:
        raise AttributeError("AbstractionGraph is immutable")

    def with_node(self, node: AbstractionNode) -> AbstractionGraph:
        return AbstractionGraph(
            tuple(
                x if x.abstraction_id != node.abstraction_id else node
                for x in self.nodes.values()
            ),
            self.edges,
            tuple(self.rules.values()),
            tuple(self.transitions.values()),
        )

    def explain(
        self,
        abstraction_id: str,
        evidence_graph: EvidenceGraph | None = None,
        contradictions: tuple[ContradictionObject, ...] = (),
    ) -> AbstractionLineage:
        if abstraction_id not in self.nodes:
            raise ValueError("unknown abstraction")
        root = self.nodes[abstraction_id]
        upstream: set[str] = set()
        transitions: set[str] = set()
        claims = set(root.claim_ids)
        evidence = set(root.evidence_ids)
        profiles = set(filter(None, (root.uncertainty_profile_id,)))
        unresolved: set[str] = set()
        transforms: set[str] = set()
        constraints: set[str] = set()
        seen: set[str] = set()

        def walk(x: str) -> None:
            if x in seen:
                return
            seen.add(x)
            for edge in self.edges:
                if edge.target_abstraction_id == x:
                    upstream.add(edge.source_abstraction_id)
                    transitions.add(edge.transition_id)
                    source = self.nodes[edge.source_abstraction_id]
                    claims.update(source.claim_ids)
                    evidence.update(source.evidence_ids)
                    profiles.update(filter(None, (source.uncertainty_profile_id,)))
                    walk(source.abstraction_id)

        walk(abstraction_id)
        if evidence_graph:
            for claim_id in claims:
                if isinstance(evidence_graph.nodes.get(claim_id), ClaimNode):
                    lineage = evidence_graph.explain(claim_id)
                    evidence.update(lineage.upstream_evidence)
                    transforms.update(lineage.transformations)
                    constraints.update(lineage.constraints)
                    unresolved.update(lineage.unresolved_dependencies)
                else:
                    unresolved.add(claim_id)
        refs = claims | evidence
        contradiction_ids = tuple(
            sorted(
                x.contradiction_id
                for x in contradictions
                if refs & (set(x.claim_ids) | set(x.evidence_ids))
            )
        )
        return AbstractionLineage(
            abstraction_id,
            root.abstraction_level,
            tuple(sorted(claims)),
            tuple(sorted(evidence)),
            tuple(sorted(upstream)),
            tuple(sorted(transitions)),
            tuple(sorted(constraints)),
            contradiction_ids,
            tuple(sorted(profiles)),
            tuple(sorted(transforms)),
            tuple(sorted(unresolved)),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "nodes": [x.canonical_dict() for x in self.nodes.values()],
            "edges": [x.canonical_dict() for x in self.edges],
            "rules": [x.canonical_dict() for x in self.rules.values()],
            "transitions": [x.canonical_dict() for x in self.transitions.values()],
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @classmethod
    def from_canonical_json(cls, serialized: str) -> AbstractionGraph:
        if not isinstance(serialized, str):
            raise ValueError("serialized graph must be text")
        try:
            value = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid abstraction graph JSON") from exc
        if not isinstance(value, dict) or set(value) != {
            "nodes",
            "edges",
            "rules",
            "transitions",
        }:
            raise ValueError("invalid abstraction graph payload")
        try:
            graph = cls(
                tuple(AbstractionNode.from_dict(x) for x in value["nodes"]),
                tuple(AbstractionEdge.from_dict(x) for x in value["edges"]),
                tuple(AbstractionRule.from_dict(x) for x in value["rules"]),
                tuple(
                    CognitiveTransition.from_canonical_json(_canonical(x))
                    for x in value["transitions"]
                ),
            )
        except TypeError as exc:
            raise ValueError("invalid abstraction graph payload") from exc
        if graph.canonical_json() != serialized:
            raise ValueError("abstraction graph JSON is not canonical")
        return graph


def verify_abstraction(
    abstraction: AbstractionNode,
    abstraction_graph: AbstractionGraph,
    evidence_graph: EvidenceGraph,
    transition_evaluations: Mapping[str, TransitionEvaluation],
    uncertainty_profiles: Mapping[str, UncertaintyProfile],
    contradictions: tuple[ContradictionObject, ...],
    uncertainty_gate_results: Mapping[str, UncertaintyGateResult],
    *,
    at: datetime,
    verifier_id: str,
    verifier_version: str,
) -> AbstractionVerification:
    _timestamp(at, "at")
    _required_text(verifier_id, "verifier_id")
    _required_text(verifier_version, "verifier_version")
    failures: set[AbstractionFailure] = set()
    support: list[tuple[str, bool]] = []
    transition_ids: set[str] = set()
    gates: list[UncertaintyGateResult] = []
    for claim_id in abstraction.claim_ids:
        if not isinstance(evidence_graph.nodes.get(claim_id), ClaimNode):
            failures.add(AbstractionFailure.MISSING_CLAIM)
            continue
        result = evidence_graph.is_support_complete(claim_id, at=at)
        support.append((claim_id, result.complete))
        if not result.complete:
            failures.add(AbstractionFailure.SUPPORT_INCOMPLETE)
    incoming = [
        x
        for x in abstraction_graph.edges
        if x.target_abstraction_id == abstraction.abstraction_id and x.required
    ]
    for edge in incoming:
        source = abstraction_graph.nodes[edge.source_abstraction_id]
        if source.status is not AbstractionStatus.VERIFIED:
            failures.add(AbstractionFailure.MISSING_UPSTREAM_ABSTRACTION)
        evaluation = transition_evaluations.get(edge.transition_id)
        definition = abstraction_graph.transitions[edge.transition_id]
        if (
            evaluation is None
            or evaluation.status is not TransitionStatus.ALLOWED
            or evaluation.transition_fingerprint != definition.fingerprint
            or evaluation.graph_fingerprint != evidence_graph.fingerprint
            or set(evaluation.source_state.claim_ids) != set(source.claim_ids)
            or set(evaluation.source_state.evidence_ids) != set(source.evidence_ids)
            or set(evaluation.target_state.claim_ids) != set(abstraction.claim_ids)
            or set(evaluation.target_state.evidence_ids)
            != set(abstraction.evidence_ids)
            or (
                abstraction.transition_evaluation_id is not None
                and abstraction.transition_evaluation_id != edge.transition_id
            )
        ):
            failures.add(AbstractionFailure.TRANSITION_BLOCKED)
        else:
            transition_ids.add(edge.transition_id)
        matching_rule = next(
            rule
            for rule in abstraction_graph.rules.values()
            if source.abstraction_level in rule.source_levels
            and abstraction.abstraction_level is rule.target_level
            and rule.required_transition_type == definition.transition_type
        )
        actual_predicates = {
            evidence_graph.nodes[claim_id].claim.predicate
            for claim_id in abstraction.claim_ids
            if isinstance(evidence_graph.nodes.get(claim_id), ClaimNode)
        }
        if not set(matching_rule.required_claim_predicates).issubset(actual_predicates):
            failures.add(AbstractionFailure.MISSING_CLAIM)
    lineage = abstraction_graph.explain(
        abstraction.abstraction_id, evidence_graph, contradictions
    )
    for item in contradictions:
        if item.contradiction_id in lineage.contradictions and item.status in {
            ContradictionStatus.DETECTED,
            ContradictionStatus.UNRESOLVED,
            ContradictionStatus.RESOLUTION_PENDING,
            ContradictionStatus.IRRESOLVABLE,
        }:
            failures.add(AbstractionFailure.UNRESOLVED_CONTRADICTION)
    if lineage.unresolved_dependencies:
        failures.add(AbstractionFailure.LINEAGE_INCOMPLETE)
    rule_thresholds = {
        tid
        for edge in incoming
        for rule in abstraction_graph.rules.values()
        if abstraction_graph.nodes[edge.source_abstraction_id].abstraction_level
        in rule.source_levels
        and abstraction.abstraction_level is rule.target_level
        for tid in rule.uncertainty_threshold_ids
    }
    if (
        abstraction.uncertainty_profile_id
        and abstraction.uncertainty_profile_id not in uncertainty_profiles
    ):
        failures.add(AbstractionFailure.UNCERTAINTY_GATE_FAILED)
    if rule_thresholds and not abstraction.uncertainty_profile_id:
        failures.add(AbstractionFailure.UNCERTAINTY_GATE_FAILED)
    for threshold_id in sorted(rule_thresholds):
        gate = uncertainty_gate_results.get(threshold_id)
        if gate is None or not gate.passed:
            failures.add(AbstractionFailure.UNCERTAINTY_GATE_FAILED)
        if gate:
            gates.append(gate)
    status = AbstractionStatus.VERIFIED if not failures else AbstractionStatus.BLOCKED
    return AbstractionVerification(
        abstraction.abstraction_id,
        status,
        at,
        abstraction.source_abstraction_ids,
        abstraction.claim_ids,
        tuple(transition_ids),
        tuple(support),
        lineage.contradictions,
        tuple(gates),
        tuple(failures),
        verifier_id,
        verifier_version,
        evidence_graph.fingerprint,
    )
