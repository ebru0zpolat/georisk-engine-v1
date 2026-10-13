"""Deterministic dependency DAG for VERA-RAP research evidence and claims."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .claims import ClaimObject
from .evidence import (
    EvidenceObject,
    VerificationStatus,
    _freeze_json,
    _plain_json,
    _required_text,
    _timestamp,
)


class NodeType(Enum):
    EVIDENCE = "EVIDENCE"
    CLAIM = "CLAIM"
    CONSTRAINT = "CONSTRAINT"
    TRANSFORMATION = "TRANSFORMATION"

    def __str__(self) -> str:
        raise TypeError("NodeType cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("NodeType cannot be used as an implicit boolean")


class EdgeType(Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVES = "DERIVES"
    TRANSFORMS = "TRANSFORMS"
    REQUIRES = "REQUIRES"
    INVALIDATES = "INVALIDATES"

    def __str__(self) -> str:
        raise TypeError("EdgeType cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("EdgeType cannot be used as an implicit boolean")


class ConstraintStatus(Enum):
    UNRESOLVED = "UNRESOLVED"
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"

    def __str__(self) -> str:
        raise TypeError("ConstraintStatus cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("ConstraintStatus cannot be used as an implicit boolean")


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    evidence: EvidenceObject
    node_id: str = field(init=False)
    node_type: NodeType = field(default=NodeType.EVIDENCE, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, EvidenceObject):
            raise ValueError("evidence must be an EvidenceObject")
        object.__setattr__(self, "node_id", self.evidence.evidence_id)


@dataclass(frozen=True, slots=True)
class ClaimNode:
    claim: ClaimObject
    node_id: str = field(init=False)
    node_type: NodeType = field(default=NodeType.CLAIM, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.claim, ClaimObject):
            raise ValueError("claim must be a ClaimObject")
        object.__setattr__(self, "node_id", self.claim.claim_id)


@dataclass(frozen=True, slots=True)
class ConstraintNode:
    constraint_id: str
    constraint_type: str
    description: str
    required: bool
    status: ConstraintStatus
    metadata: Mapping[str, Any] | None = None
    node_id: str = field(init=False)
    node_type: NodeType = field(default=NodeType.CONSTRAINT, init=False)

    def __post_init__(self) -> None:
        for name in ("constraint_id", "constraint_type", "description"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")
        if not isinstance(self.status, ConstraintStatus):
            raise ValueError("status must be a ConstraintStatus enum member")
        frozen = _freeze_json(self.metadata, "metadata")
        if frozen is not None and not isinstance(frozen, Mapping):
            raise ValueError("metadata must be an object or null")
        object.__setattr__(self, "metadata", frozen)
        object.__setattr__(self, "node_id", self.constraint_id)


@dataclass(frozen=True, slots=True)
class TransformationNode:
    transformation_id: str
    transformation_type: str
    version: str
    input_schema: Any
    output_schema: Any
    metadata: Mapping[str, Any] | None = None
    node_id: str = field(init=False)
    node_type: NodeType = field(default=NodeType.TRANSFORMATION, init=False)

    def __post_init__(self) -> None:
        for name in ("transformation_id", "transformation_type", "version"):
            _required_text(getattr(self, name), name)
        for name in ("input_schema", "output_schema", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        object.__setattr__(self, "node_id", self.transformation_id)


GraphNode = EvidenceNode | ClaimNode | ConstraintNode | TransformationNode


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType

    def __post_init__(self) -> None:
        _required_text(self.source_id, "source_id")
        _required_text(self.target_id, "target_id")
        if self.source_id == self.target_id:
            raise ValueError("graph edges cannot be self-loops")
        if not isinstance(self.edge_type, EdgeType):
            raise ValueError("edge_type must be an EdgeType enum member")


@dataclass(frozen=True, slots=True)
class GraphValidationResult:
    valid: bool
    missing_nodes: tuple[str, ...]
    missing_edges: tuple[str, ...]
    inconsistent_references: tuple[str, ...]
    cycles: tuple[str, ...]
    invalid_edges: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SupportCompletenessResult:
    complete: bool
    claim_id: str
    evaluated_at: datetime
    supporting_evidence_ids: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]
    stale_evidence_ids: tuple[str, ...]
    unverified_evidence_ids: tuple[str, ...]
    rejected_evidence_ids: tuple[str, ...]
    contradicted_dependencies: tuple[str, ...]
    missing_constraints: tuple[str, ...]
    failed_constraints: tuple[str, ...]
    upstream_claim_issues: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimLineage:
    claim_id: str
    direct_support: tuple[str, ...]
    direct_contradictions: tuple[str, ...]
    parent_claims: tuple[str, ...]
    constraints: tuple[str, ...]
    transformations: tuple[str, ...]
    upstream_evidence: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]


_VALID_EDGE_TYPES: dict[EdgeType, frozenset[tuple[NodeType, NodeType]]] = {
    EdgeType.SUPPORTS: frozenset({(NodeType.EVIDENCE, NodeType.CLAIM)}),
    EdgeType.CONTRADICTS: frozenset({(NodeType.EVIDENCE, NodeType.CLAIM)}),
    EdgeType.DERIVES: frozenset(
        {
            (NodeType.CLAIM, NodeType.CLAIM),
            (NodeType.TRANSFORMATION, NodeType.EVIDENCE),
            (NodeType.TRANSFORMATION, NodeType.CLAIM),
        }
    ),
    EdgeType.TRANSFORMS: frozenset({(NodeType.EVIDENCE, NodeType.TRANSFORMATION)}),
    EdgeType.REQUIRES: frozenset({(NodeType.CLAIM, NodeType.CONSTRAINT)}),
    EdgeType.INVALIDATES: frozenset({(NodeType.EVIDENCE, NodeType.CLAIM)}),
}


class EvidenceGraph:
    """Immutable, in-memory dependency DAG."""

    __slots__ = ("_edges", "_nodes")

    def __init__(
        self, nodes: tuple[GraphNode, ...] = (), edges: tuple[GraphEdge, ...] = ()
    ) -> None:
        node_map: dict[str, GraphNode] = {}
        for node in nodes:
            if not isinstance(
                node, (EvidenceNode, ClaimNode, ConstraintNode, TransformationNode)
            ):
                raise ValueError("nodes must contain graph node objects")
            _required_text(node.node_id, "node_id")
            if node.node_id in node_map:
                raise ValueError(f"duplicate node ID: {node.node_id}")
            node_map[node.node_id] = node
        edge_items = tuple(edges)
        if any(not isinstance(edge, GraphEdge) for edge in edge_items):
            raise ValueError("edges must contain GraphEdge objects")
        if len(edge_items) != len(set(edge_items)):
            raise ValueError("duplicate graph edge")
        for edge in edge_items:
            if edge.source_id not in node_map or edge.target_id not in node_map:
                raise ValueError(
                    f"edge references missing node: {edge.source_id}->{edge.target_id}"
                )
            pair = (
                node_map[edge.source_id].node_type,
                node_map[edge.target_id].node_type,
            )
            if pair not in _VALID_EDGE_TYPES[edge.edge_type]:
                raise ValueError(
                    f"invalid {edge.edge_type.value} source/target combination"
                )
        sorted_edges = tuple(
            sorted(
                edge_items, key=lambda e: (e.source_id, e.target_id, e.edge_type.value)
            )
        )
        cycle = self._find_cycle(tuple(sorted(node_map)), sorted_edges)
        if cycle:
            raise ValueError(f"cycle detected: {' -> '.join(cycle)}")
        object.__setattr__(
            self, "_nodes", MappingProxyType(dict(sorted(node_map.items())))
        )
        object.__setattr__(self, "_edges", sorted_edges)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("EvidenceGraph is immutable")

    @property
    def nodes(self) -> Mapping[str, GraphNode]:
        return self._nodes

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return self._edges

    def with_node(self, node: GraphNode) -> EvidenceGraph:
        return EvidenceGraph((*self._nodes.values(), node), self._edges)

    def with_edge(self, edge: GraphEdge) -> EvidenceGraph:
        return EvidenceGraph(tuple(self._nodes.values()), (*self._edges, edge))

    @staticmethod
    def _find_cycle(
        node_ids: tuple[str, ...], edges: tuple[GraphEdge, ...]
    ) -> tuple[str, ...]:
        adjacency = {node_id: [] for node_id in node_ids}
        for edge in edges:
            adjacency[edge.source_id].append(edge.target_id)
        for targets in adjacency.values():
            targets.sort()
        active: list[str] = []
        active_set: set[str] = set()
        complete: set[str] = set()

        def visit(node_id: str) -> tuple[str, ...]:
            if node_id in active_set:
                index = active.index(node_id)
                return tuple((*active[index:], node_id))
            if node_id in complete:
                return ()
            active.append(node_id)
            active_set.add(node_id)
            for target in adjacency[node_id]:
                found = visit(target)
                if found:
                    return found
            active.pop()
            active_set.remove(node_id)
            complete.add(node_id)
            return ()

        for node_id in node_ids:
            found = visit(node_id)
            if found:
                return found
        return ()

    def _incoming(
        self, target_id: str, edge_type: EdgeType | None = None
    ) -> tuple[GraphEdge, ...]:
        return tuple(
            edge
            for edge in self._edges
            if edge.target_id == target_id
            and (edge_type is None or edge.edge_type is edge_type)
        )

    def _outgoing(
        self, source_id: str, edge_type: EdgeType | None = None
    ) -> tuple[GraphEdge, ...]:
        return tuple(
            edge
            for edge in self._edges
            if edge.source_id == source_id
            and (edge_type is None or edge.edge_type is edge_type)
        )

    def validate_consistency(self) -> GraphValidationResult:
        missing_nodes: set[str] = set()
        missing_edges: set[str] = set()
        inconsistent: set[str] = set()
        warnings: set[str] = set()
        edge_keys = {(e.source_id, e.target_id, e.edge_type) for e in self._edges}
        for node in self._nodes.values():
            if isinstance(node, ClaimNode):
                claim = node.claim
                expected = (
                    *(
                        (item, node.node_id, EdgeType.SUPPORTS)
                        for item in claim.supporting_evidence_ids
                    ),
                    *(
                        (item, node.node_id, EdgeType.CONTRADICTS)
                        for item in claim.contradicting_evidence_ids
                    ),
                    *(
                        (item, node.node_id, EdgeType.DERIVES)
                        for item in claim.parent_claim_ids
                    ),
                )
                for source, target, edge_type in expected:
                    if source not in self._nodes:
                        missing_nodes.add(source)
                        inconsistent.add(f"{target} references missing {source}")
                    elif (source, target, edge_type) not in edge_keys:
                        missing_edges.add(f"{source} -{edge_type.value}-> {target}")
                for edge in self._incoming(node.node_id):
                    if (
                        edge.edge_type is EdgeType.SUPPORTS
                        and edge.source_id not in claim.supporting_evidence_ids
                    ):
                        inconsistent.add(
                            f"unrecorded support edge {edge.source_id}->{node.node_id}"
                        )
                    if (
                        edge.edge_type is EdgeType.CONTRADICTS
                        and edge.source_id not in claim.contradicting_evidence_ids
                    ):
                        inconsistent.add(
                            f"unrecorded contradiction edge {edge.source_id}->{node.node_id}"
                        )
                    if (
                        edge.edge_type is EdgeType.DERIVES
                        and isinstance(self._nodes[edge.source_id], ClaimNode)
                        and edge.source_id not in claim.parent_claim_ids
                    ):
                        inconsistent.add(
                            f"unrecorded parent edge {edge.source_id}->{node.node_id}"
                        )
            elif isinstance(node, TransformationNode):
                if not self._incoming(node.node_id, EdgeType.TRANSFORMS):
                    inconsistent.add(
                        f"transformation {node.node_id} has no explicit input"
                    )
                if not self._outgoing(node.node_id, EdgeType.DERIVES):
                    inconsistent.add(
                        f"transformation {node.node_id} has no explicit output"
                    )
            elif isinstance(node, ConstraintNode) and not node.required:
                warnings.add(f"constraint {node.node_id} is optional")
        valid = not missing_nodes and not missing_edges and not inconsistent
        return GraphValidationResult(
            valid=valid,
            missing_nodes=tuple(sorted(missing_nodes)),
            missing_edges=tuple(sorted(missing_edges)),
            inconsistent_references=tuple(sorted(inconsistent)),
            cycles=(),
            invalid_edges=(),
            warnings=tuple(sorted(warnings)),
        )

    def is_support_complete(
        self, claim_id: str, *, at: datetime
    ) -> SupportCompletenessResult:
        _timestamp(at, "at")
        node = self._nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            raise ValueError(f"unknown claim ID: {claim_id}")
        support: set[str] = set()
        unresolved: set[str] = set()
        stale: set[str] = set()
        unverified: set[str] = set()
        rejected: set[str] = set()
        contradicted: set[str] = set()
        missing_constraints: set[str] = set()
        failed_constraints: set[str] = set()
        upstream_issues: set[str] = set()
        reasons: set[str] = set()
        visiting: set[str] = set()
        inspected_evidence: set[str] = set()

        def inspect_evidence(evidence_id: str, purpose: str) -> None:
            if evidence_id in inspected_evidence:
                return
            inspected_evidence.add(evidence_id)
            evidence_node = self._nodes.get(evidence_id)
            if not isinstance(evidence_node, EvidenceNode):
                unresolved.add(evidence_id)
                return
            evidence = evidence_node.evidence
            if purpose == "support":
                support.add(evidence_id)
            if evidence.is_stale(at=at):
                stale.add(evidence_id)
            elif evidence.verification_status is VerificationStatus.UNVERIFIED:
                unverified.add(evidence_id)
            elif evidence.verification_status in {VerificationStatus.REJECTED}:
                rejected.add(evidence_id)
            elif evidence.verification_status is VerificationStatus.CONTRADICTED:
                contradicted.add(evidence_id)
            for derives_edge in self._incoming(evidence_id, EdgeType.DERIVES):
                transformation = self._nodes[derives_edge.source_id]
                if isinstance(transformation, TransformationNode):
                    inputs = self._incoming(transformation.node_id, EdgeType.TRANSFORMS)
                    if not inputs:
                        unresolved.add(
                            f"transformation {transformation.node_id} has no explicit input"
                        )
                    for input_edge in inputs:
                        inspect_evidence(input_edge.source_id, "lineage")

        def inspect_claim(current_id: str) -> None:
            if current_id in visiting:
                unresolved.add(f"cycle:{current_id}")
                return
            visiting.add(current_id)
            current_node = self._nodes.get(current_id)
            if not isinstance(current_node, ClaimNode):
                unresolved.add(current_id)
                visiting.remove(current_id)
                return
            current = current_node.claim
            support_edges = {
                e.source_id for e in self._incoming(current_id, EdgeType.SUPPORTS)
            }
            parent_edges = {
                e.source_id
                for e in self._incoming(current_id, EdgeType.DERIVES)
                if isinstance(self._nodes[e.source_id], ClaimNode)
            }
            transformation_edges = tuple(
                edge
                for edge in self._incoming(current_id, EdgeType.DERIVES)
                if isinstance(self._nodes[edge.source_id], TransformationNode)
            )
            if (
                not current.supporting_evidence_ids
                and not current.parent_claim_ids
                and not transformation_edges
            ):
                unresolved.add(f"{current_id}:no-supporting-dependency")
            for evidence_id in current.supporting_evidence_ids:
                if evidence_id not in support_edges:
                    unresolved.add(f"missing SUPPORTS {evidence_id}->{current_id}")
                else:
                    inspect_evidence(evidence_id, "support")
            for parent_id in current.parent_claim_ids:
                if parent_id not in parent_edges:
                    unresolved.add(f"missing DERIVES {parent_id}->{current_id}")
                else:
                    before = sum(
                        map(
                            len, (unresolved, stale, unverified, rejected, contradicted)
                        )
                    )
                    inspect_claim(parent_id)
                    after = sum(
                        map(
                            len, (unresolved, stale, unverified, rejected, contradicted)
                        )
                    )
                    if after > before:
                        upstream_issues.add(parent_id)
            for transformation_edge in transformation_edges:
                inputs = self._incoming(
                    transformation_edge.source_id, EdgeType.TRANSFORMS
                )
                if not inputs:
                    unresolved.add(
                        f"transformation {transformation_edge.source_id} has no explicit input"
                    )
                for input_edge in inputs:
                    inspect_evidence(input_edge.source_id, "lineage")
            for edge_type in (EdgeType.CONTRADICTS, EdgeType.INVALIDATES):
                for edge in self._incoming(current_id, edge_type):
                    contradicted.add(edge.source_id)
                    inspect_evidence(edge.source_id, "contradiction")
            for edge in self._outgoing(current_id, EdgeType.REQUIRES):
                constraint = self._nodes[edge.target_id]
                if isinstance(constraint, ConstraintNode) and constraint.required:
                    if constraint.status is ConstraintStatus.UNRESOLVED:
                        missing_constraints.add(constraint.node_id)
                    elif constraint.status is ConstraintStatus.VIOLATED:
                        failed_constraints.add(constraint.node_id)
            visiting.remove(current_id)

        inspect_claim(claim_id)
        validation = self.validate_consistency()
        unresolved.update(validation.missing_edges)
        unresolved.update(validation.inconsistent_references)
        categories = {
            "unresolved dependencies": unresolved,
            "stale evidence": stale,
            "unverified evidence": unverified,
            "rejected evidence": rejected,
            "contradicted dependencies": contradicted,
            "missing constraints": missing_constraints,
            "failed constraints": failed_constraints,
            "upstream claim issues": upstream_issues,
        }
        for label, values in categories.items():
            if values:
                reasons.add(f"{label}: {', '.join(sorted(values))}")
        return SupportCompletenessResult(
            complete=not reasons,
            claim_id=claim_id,
            evaluated_at=at,
            supporting_evidence_ids=tuple(sorted(support)),
            unresolved_dependencies=tuple(sorted(unresolved)),
            stale_evidence_ids=tuple(sorted(stale)),
            unverified_evidence_ids=tuple(sorted(unverified)),
            rejected_evidence_ids=tuple(sorted(rejected)),
            contradicted_dependencies=tuple(sorted(contradicted)),
            missing_constraints=tuple(sorted(missing_constraints)),
            failed_constraints=tuple(sorted(failed_constraints)),
            upstream_claim_issues=tuple(sorted(upstream_issues)),
            reasons=tuple(sorted(reasons)),
        )

    def explain(self, claim_id: str) -> ClaimLineage:
        node = self._nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            raise ValueError(f"unknown claim ID: {claim_id}")
        direct_support = tuple(
            e.source_id for e in self._incoming(claim_id, EdgeType.SUPPORTS)
        )
        contradictions = tuple(
            sorted(
                e.source_id
                for e in self._incoming(claim_id)
                if e.edge_type in {EdgeType.CONTRADICTS, EdgeType.INVALIDATES}
            )
        )
        parents = tuple(
            e.source_id
            for e in self._incoming(claim_id, EdgeType.DERIVES)
            if isinstance(self._nodes[e.source_id], ClaimNode)
        )
        constraints = tuple(
            e.target_id for e in self._outgoing(claim_id, EdgeType.REQUIRES)
        )
        upstream_evidence: set[str] = set()
        transformations: set[str] = set()
        visited: set[str] = set()

        def walk(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            for edge in self._incoming(current):
                source = self._nodes[edge.source_id]
                if isinstance(source, EvidenceNode):
                    upstream_evidence.add(source.node_id)
                    walk(source.node_id)
                elif isinstance(source, TransformationNode):
                    transformations.add(source.node_id)
                    walk(source.node_id)
                elif isinstance(source, ClaimNode):
                    walk(source.node_id)

        walk(claim_id)
        validation = self.validate_consistency()
        unresolved = tuple(
            sorted(
                item
                for item in (
                    *validation.missing_edges,
                    *validation.inconsistent_references,
                )
                if claim_id in item or any(parent in item for parent in parents)
            )
        )
        return ClaimLineage(
            claim_id=claim_id,
            direct_support=direct_support,
            direct_contradictions=contradictions,
            parent_claims=parents,
            constraints=constraints,
            transformations=tuple(sorted(transformations)),
            upstream_evidence=tuple(sorted(upstream_evidence)),
            unresolved_dependencies=unresolved,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "nodes": [self._node_dict(node) for node in self._nodes.values()],
            "edges": [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "edge_type": edge.edge_type.value,
                }
                for edge in self._edges
            ],
        }

    @staticmethod
    def _node_dict(node: GraphNode) -> dict[str, Any]:
        if isinstance(node, EvidenceNode):
            payload = node.evidence.canonical_dict()
        elif isinstance(node, ClaimNode):
            payload = node.claim.canonical_dict()
        elif isinstance(node, ConstraintNode):
            payload = {
                "constraint_id": node.constraint_id,
                "constraint_type": node.constraint_type,
                "description": node.description,
                "required": node.required,
                "status": node.status.value,
                "metadata": _plain_json(node.metadata),
            }
        else:
            payload = {
                "transformation_id": node.transformation_id,
                "transformation_type": node.transformation_type,
                "version": node.version,
                "input_schema": _plain_json(node.input_schema),
                "output_schema": _plain_json(node.output_schema),
                "metadata": _plain_json(node.metadata),
            }
        return {
            "node_id": node.node_id,
            "node_type": node.node_type.value,
            "payload": payload,
        }

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.to_canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EvidenceGraph:
        try:
            payload = json.loads(serialized)
            if not isinstance(payload, dict) or set(payload) != {"nodes", "edges"}:
                raise ValueError("graph fields do not match canonical schema")
            nodes: list[GraphNode] = []
            for item in payload["nodes"]:
                if not isinstance(item, dict) or set(item) != {
                    "node_id",
                    "node_type",
                    "payload",
                }:
                    raise ValueError("malformed graph node")
                node_type = NodeType(item["node_type"])
                body = item["payload"]
                if node_type is NodeType.EVIDENCE:
                    node: GraphNode = EvidenceNode(
                        EvidenceObject.from_canonical_json(json.dumps(body))
                    )
                elif node_type is NodeType.CLAIM:
                    node = ClaimNode(ClaimObject.from_canonical_json(json.dumps(body)))
                elif node_type is NodeType.CONSTRAINT:
                    node = ConstraintNode(
                        **{**body, "status": ConstraintStatus(body["status"])}
                    )
                else:
                    node = TransformationNode(**body)
                if node.node_id != item["node_id"]:
                    raise ValueError(
                        "serialized node ID does not match embedded object"
                    )
                nodes.append(node)
            edges_list: list[GraphEdge] = []
            for item in payload["edges"]:
                if not isinstance(item, dict) or set(item) != {
                    "source_id",
                    "target_id",
                    "edge_type",
                }:
                    raise ValueError("malformed graph edge")
                edges_list.append(
                    GraphEdge(
                        item["source_id"],
                        item["target_id"],
                        EdgeType(item["edge_type"]),
                    )
                )
            edges = tuple(edges_list)
            return cls(tuple(nodes), edges)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized graph is malformed") from exc
