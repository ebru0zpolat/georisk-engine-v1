"""Strict scenario loading and deterministic artifact materialization (RAP-010).

Scenario files hold structured data only. `load_benchmark_cases()` enforces an
exact schema; `materialize_case()` turns a case's `initial_artifacts` into real
RAP-001..RAP-006 objects for systems that reason over VERA-RAP artifacts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.research.vera_rap import (
    ClaimNode,
    ClaimObject,
    CognitiveState,
    CognitiveTransition,
    ConstraintNode,
    ConstraintStatus,
    ContradictionObject,
    ContradictionResolutionResult,
    ContradictionStatus,
    ContradictionType,
    EdgeType,
    EpistemicState,
    EvidenceGraph,
    EvidenceNode,
    EvidenceObject,
    GraphEdge,
    PropagationRule,
    PropagationRuleType,
    Provenance,
    RequirementType,
    ResolutionRequirement,
    ResolutionRequirementType,
    ThresholdMetric,
    ThresholdOperator,
    TransformationNode,
    TransitionRequirement,
    Uncertainty,
    UncertaintyThreshold,
    UncertaintyType,
    VerificationStatus,
    evaluate_resolution,
)
from app.research.vera_rap.evidence import _parse_timestamp, _plain_json

from .models import BenchmarkCase, ReferenceOutcome

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
_DOCUMENT_KEYS = frozenset({"case", "reference"})


@dataclass(frozen=True, slots=True)
class BenchmarkCasePair:
    case: BenchmarkCase
    reference: ReferenceOutcome

    def __post_init__(self) -> None:
        if self.case.case_id != self.reference.case_id:
            raise ValueError("case and reference describe different case IDs")


def _read_documents(path: Path) -> list[tuple[Path, Any]]:
    if path.is_dir():
        files = sorted(x for x in path.iterdir() if x.suffix == ".json")
    elif path.is_file():
        files = [path]
    else:
        raise ValueError(f"scenario path does not exist: {path}")
    documents: list[tuple[Path, Any]] = []
    for file in files:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file.name} is not valid JSON") from exc
        if not isinstance(payload, list):
            raise ValueError(f"{file.name} must contain a list of case documents")
        documents.extend((file, item) for item in payload)
    return documents


def load_benchmark_cases(
    path: str | Path = SCENARIO_DIR,
) -> tuple[BenchmarkCasePair, ...]:
    """Load cases with an exact schema, rejecting duplicates; ordered by case ID."""
    pairs: dict[str, BenchmarkCasePair] = {}
    for file, document in _read_documents(Path(path)):
        if not isinstance(document, dict) or set(document) != _DOCUMENT_KEYS:
            raise ValueError(
                f"{file.name}: each document needs exactly 'case' and 'reference'"
            )
        try:
            pair = BenchmarkCasePair(
                BenchmarkCase.from_dict(document["case"]),
                ReferenceOutcome.from_dict(document["reference"]),
            )
        except ValueError as exc:
            raise ValueError(f"{file.name}: {exc}") from exc
        if pair.case.case_id in pairs:
            raise ValueError(f"duplicate case ID: {pair.case.case_id}")
        _validate_artifacts(pair.case)
        pairs[pair.case.case_id] = pair
    return tuple(pairs[key] for key in sorted(pairs))


_ARTIFACT_KEYS = frozenset(
    {
        "evaluation_time",
        "evidence",
        "claims",
        "constraints",
        "transformations",
        "transitions",
        "contradictions",
        "uncertainty",
        "follow_up",
    }
)


def _validate_artifacts(case: BenchmarkCase) -> None:
    artifacts = case.initial_artifacts
    unknown = set(artifacts) - _ARTIFACT_KEYS
    if unknown or "evaluation_time" not in artifacts or "evidence" not in artifacts:
        raise ValueError(f"{case.case_id}: initial_artifacts schema is malformed")
    _parse_timestamp(artifacts["evaluation_time"], "evaluation_time")
    for key in (
        "evidence",
        "claims",
        "constraints",
        "transformations",
        "transitions",
        "contradictions",
    ):
        items = artifacts.get(key, ())
        if not isinstance(items, tuple):
            raise ValueError(f"{case.case_id}: {key} must be a list")
        ids = [x.get(_ID_FIELD[key]) if isinstance(x, Mapping) else None for x in items]
        if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(
            set(ids)
        ):
            raise ValueError(f"{case.case_id}: {key} entries need unique string IDs")


_ID_FIELD = {
    "evidence": "evidence_id",
    "claims": "claim_id",
    "constraints": "constraint_id",
    "transformations": "transformation_id",
    "transitions": "transition_id",
    "contradictions": "contradiction_id",
}


def content_fingerprint(content: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _plain_json(content),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class MaterializedCase:
    """Real VERA-RAP artifacts built from a case; nothing here is executable."""

    case_id: str
    at: datetime
    graph: EvidenceGraph
    transitions: tuple[CognitiveTransition, ...]
    contradictions: tuple[ContradictionObject, ...]
    propagation_rules: tuple[PropagationRule, ...]
    thresholds: tuple[UncertaintyThreshold, ...]
    corrupted_evidence_ids: tuple[str, ...]
    follow_up_evidence: tuple[EvidenceObject, ...]
    target: Mapping[str, Any]


def _evidence(item: Mapping[str, Any], at: datetime) -> tuple[EvidenceObject, bool]:
    content = item.get("content", {})
    computed = content_fingerprint(content)
    declared = item.get("content_hash", computed)
    corrupted = declared != computed
    status = (
        VerificationStatus.REJECTED
        if corrupted
        else VerificationStatus(item.get("verification_status", "VERIFIED"))
    )
    retrieved = _parse_timestamp(
        item.get("retrieved_at", "2026-01-01T00:00:00Z"), "retrieved_at"
    )
    valid_until = _parse_timestamp(
        item.get("valid_until"), "valid_until", optional=True
    )
    confidence = item.get("confidence")
    uncertainty = (
        None if confidence is None else Uncertainty("declared", confidence=confidence)
    )
    digest = declared if isinstance(declared, str) and len(declared) == 64 else computed
    evidence = EvidenceObject(
        item["evidence_id"],
        item.get("evidence_type", "synthetic"),
        item["source_id"],
        item.get("source_uri"),
        digest,
        retrieved,
        retrieved,
        None,
        valid_until,
        None,
        item.get("spatial_scope"),
        item.get("measurement"),
        item.get("unit"),
        uncertainty,
        "research-only",
        status,
        provenance=Provenance(
            item["source_id"],
            item.get("retrieval_mechanism", "benchmark-fixture"),
            digest,
            tuple(item.get("transformation_ids", ())),
            tuple(item.get("upstream_evidence_ids", ())),
        ),
        metadata={"benchmark_content": _plain_json(content), "corrupted": corrupted},
    )
    del at
    return evidence, corrupted


def _claim(item: Mapping[str, Any]) -> ClaimObject:
    confidence = item.get("confidence")
    return ClaimObject(
        item["claim_id"],
        item["predicate"],
        item.get("subject"),
        item.get("value"),
        item.get("unit"),
        EpistemicState(item.get("epistemic_state", "INFERRED")),
        tuple(item.get("supporting_evidence_ids", ())),
        tuple(item.get("contradicting_evidence_ids", ())),
        tuple(item.get("parent_claim_ids", ())),
        constraints=tuple(item.get("constraint_ids", ())),
        uncertainty=(
            None
            if confidence is None
            else Uncertainty("declared", confidence=confidence)
        ),
        created_at=_parse_timestamp(
            item.get("created_at", "2026-01-01T00:00:00Z"), "created_at"
        ),
        derivation_method=item.get("derivation_method", "benchmark-fixture"),
    )


def _state(item: Mapping[str, Any]) -> CognitiveState:
    return CognitiveState(
        item["state_id"],
        item.get("state_type", "STATE"),
        item.get("level"),
        tuple(item.get("claim_ids", ())),
        tuple(item.get("evidence_ids", ())),
    )


def _transition(item: Mapping[str, Any]) -> CognitiveTransition:
    return CognitiveTransition(
        item["transition_id"],
        item.get("transition_type", "benchmark_transition"),
        _state(item["source_state"]),
        _state(item["target_state"]),
        tuple(
            TransitionRequirement(
                x["requirement_id"],
                RequirementType(x["requirement_type"]),
                x["subject_id"],
                x.get("parameters", {}),
                x.get("mandatory", True),
                x.get("description", "benchmark gate"),
            )
            for x in item.get("requirements", ())
        ),
        item.get("evaluator_id", "benchmark-evaluator"),
        item.get("evaluator_version", "1"),
    )


def _contradiction(
    item: Mapping[str, Any], graph: EvidenceGraph, at: datetime
) -> ContradictionObject:
    requirements = tuple(
        ResolutionRequirement(
            x["requirement_id"],
            ResolutionRequirementType(x["requirement_type"]),
            tuple(x.get("subject_ids", ())),
            x.get("parameters", {}),
            x.get("mandatory", True),
            x.get("description", "benchmark resolution requirement"),
        )
        for x in item.get("resolution_requirements", ())
    )
    artifact = ContradictionObject(
        item["contradiction_id"],
        ContradictionType(item.get("contradiction_type", "DIRECT_VALUE_CONFLICT")),
        ContradictionStatus(item.get("status", "UNRESOLVED")),
        tuple(item.get("evidence_ids", ())),
        tuple(item.get("claim_ids", ())),
        detected_at=_parse_timestamp(
            item.get("detected_at", "2026-01-01T00:00:00Z"), "detected_at"
        ),
        conflict_dimensions=tuple(
            item.get("conflict_dimensions", ("measurement.value",))
        ),
        resolution_requirements=requirements,
    )
    resolution = item.get("resolution")
    if resolution is None:
        return artifact
    result = ContradictionResolutionResult(
        ContradictionStatus(resolution["target_status"]),
        tuple(resolution.get("satisfied_requirement_ids", ())),
        tuple(resolution.get("unsatisfied_requirement_ids", ())),
        tuple(resolution.get("supporting_evidence_ids", ())),
        tuple(resolution.get("rejected_evidence_ids", ())),
        tuple(resolution.get("superseded_claim_ids", ())),
        tuple(resolution.get("retained_claim_ids", ())),
        resolution.get("resolver_id", "benchmark-resolver"),
        resolution.get("resolver_version", "1"),
        at,
        resolution.get("resolution_basis", "benchmark fixture"),
    )
    return evaluate_resolution(artifact, result, graph)


def _rule(item: Mapping[str, Any]) -> PropagationRule:
    return PropagationRule(
        item["rule_id"],
        PropagationRuleType(item["rule_type"]),
        item.get("version", "1"),
        tuple(item["input_subject_ids"]),
        item["target_subject_id"],
        item.get("parameters", {}),
        tuple(item.get("assumptions", ())),
        item.get("description", "benchmark propagation rule"),
    )


def _threshold(item: Mapping[str, Any]) -> UncertaintyThreshold:
    return UncertaintyThreshold(
        item["threshold_id"],
        ThresholdMetric(item["metric"]),
        ThresholdOperator(item.get("operator", "GREATER_THAN_OR_EQUAL")),
        item.get("value"),
        item.get("unit"),
        tuple(UncertaintyType(x) for x in item.get("component_types", ())),
        item.get("mandatory", True),
        item.get("description", "benchmark threshold"),
    )


def materialize_case(case: BenchmarkCase) -> MaterializedCase:
    """Build immutable RAP artifacts from structured case data."""
    artifacts = case.initial_artifacts
    at = _parse_timestamp(artifacts["evaluation_time"], "evaluation_time")
    nodes: list[Any] = []
    edges: list[GraphEdge] = []
    corrupted: list[str] = []
    for item in artifacts.get("evidence", ()):
        evidence, is_corrupted = _evidence(item, at)
        nodes.append(EvidenceNode(evidence))
        if is_corrupted:
            corrupted.append(evidence.evidence_id)
    for item in artifacts.get("constraints", ()):
        nodes.append(
            ConstraintNode(
                item["constraint_id"],
                item.get("constraint_type", "benchmark_constraint"),
                item.get("description", "benchmark constraint"),
                item.get("required", True),
                ConstraintStatus(item.get("status", "SATISFIED")),
            )
        )
    for item in artifacts.get("transformations", ()):
        nodes.append(
            TransformationNode(
                item["transformation_id"],
                item["transformation_type"],
                item.get("version", "1"),
                {},
                {},
            )
        )
        for evidence_id in item.get("input_evidence_ids", ()):
            edges.append(
                GraphEdge(evidence_id, item["transformation_id"], EdgeType.TRANSFORMS)
            )
        for claim_id in item.get("output_claim_ids", ()):
            edges.append(
                GraphEdge(item["transformation_id"], claim_id, EdgeType.DERIVES)
            )
    for item in artifacts.get("claims", ()):
        claim = _claim(item)
        nodes.append(ClaimNode(claim))
        edges.extend(
            GraphEdge(x, claim.claim_id, EdgeType.SUPPORTS)
            for x in claim.supporting_evidence_ids
        )
        edges.extend(
            GraphEdge(x, claim.claim_id, EdgeType.CONTRADICTS)
            for x in claim.contradicting_evidence_ids
        )
        edges.extend(
            GraphEdge(x, claim.claim_id, EdgeType.DERIVES)
            for x in claim.parent_claim_ids
        )
        edges.extend(
            GraphEdge(claim.claim_id, x, EdgeType.REQUIRES)
            for x in item.get("constraint_ids", ())
        )
    graph = EvidenceGraph(tuple(nodes), tuple(edges))
    uncertainty = artifacts.get("uncertainty") or {}
    follow_up = artifacts.get("follow_up") or {}
    return MaterializedCase(
        case.case_id,
        at,
        graph,
        tuple(_transition(x) for x in artifacts.get("transitions", ())),
        tuple(
            _contradiction(x, graph, at) for x in artifacts.get("contradictions", ())
        ),
        tuple(_rule(x) for x in uncertainty.get("rules", ())),
        tuple(_threshold(x) for x in uncertainty.get("thresholds", ())),
        tuple(sorted(corrupted)),
        tuple(_evidence(x, at)[0] for x in follow_up.get("evidence", ())),
        case.target,
    )
