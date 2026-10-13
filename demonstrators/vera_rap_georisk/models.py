"""Immutable, research-only inputs and outputs for the flood demonstrator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from app.research.vera_rap import CognitiveTrace


class GeoRiskEvidenceType(str, Enum):
    ASSET_LOCATION = "ASSET_LOCATION"
    GROUND_ELEVATION = "GROUND_ELEVATION"
    FLOOD_DEPTH = "FLOOD_DEPTH"
    FLOOD_EXTENT = "FLOOD_EXTENT"
    RETURN_PERIOD = "RETURN_PERIOD"
    CLIMATE_SCENARIO = "CLIMATE_SCENARIO"
    SOURCE_PROVENANCE = "SOURCE_PROVENANCE"
    CRS_TRANSFORMATION = "CRS_TRANSFORMATION"
    TEMPORAL_VALIDITY = "TEMPORAL_VALIDITY"
    REGULATORY_CONSTRAINT = "REGULATORY_CONSTRAINT"
    MODEL_ASSUMPTION = "MODEL_ASSUMPTION"


class DemonstratorOutcome(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONDITIONALLY_SUPPORTED = "CONDITIONALLY_SUPPORTED"
    BLOCKED = "BLOCKED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    ABSTAINED = "ABSTAINED"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True, slots=True)
class DemonstratorAsset:
    asset_id: str
    asset_type: str
    location: str
    jurisdiction: str
    coordinates: tuple[float, float]
    elevation_reference: str
    criticality: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "coordinates", tuple(self.coordinates))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DemonstratorQuestion:
    question_id: str
    asset_id: str
    hazard_type: str
    target_claim: str
    evaluation_time: datetime
    materiality_threshold: Mapping[str, Any]
    required_evidence_types: tuple[GeoRiskEvidenceType, ...]
    constraints: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            self.hazard_type != "FLOOD"
            or self.target_claim != "MATERIAL_FLOOD_EXPOSURE"
        ):
            raise ValueError("RAP-012 is restricted to MATERIAL_FLOOD_EXPOSURE/FLOOD")
        if self.evaluation_time.tzinfo is None:
            raise ValueError("evaluation_time must be timezone-aware")
        object.__setattr__(
            self, "required_evidence_types", tuple(self.required_evidence_types)
        )
        object.__setattr__(
            self, "materiality_threshold", _freeze(dict(self.materiality_threshold))
        )
        object.__setattr__(self, "constraints", _freeze(dict(self.constraints)))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DemonstratorRunResult:
    run_id: str
    asset: DemonstratorAsset
    question: DemonstratorQuestion
    evidence_objects: tuple[Any, ...]
    claims: tuple[Any, ...]
    evidence_graph_fingerprint: str
    transition_evaluations: tuple[Any, ...]
    contradictions: tuple[Any, ...]
    uncertainty_profiles: tuple[Any, ...]
    abstraction_verifications: tuple[Any, ...]
    plans: tuple[Any, ...]
    trace: CognitiveTrace
    final_outcome: DemonstratorOutcome
    created_at: datetime
    blockers: tuple[str, ...]
    fingerprint: str


def fingerprint(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
