from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConfidenceLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class DataQualityInputs:
    """Pure inputs for ``derive_confidence`` — no agent / DeerFlow state."""

    baseline_score: int
    component_count: int
    expected_component_count: int = 6
    uses_connector_fallback: bool = False
    data_snapshot_stale: bool = False
    geometry_hash_verified: bool = True


def derive_confidence(inputs: DataQualityInputs) -> tuple[ConfidenceLevel, list[str]]:
    """Deterministic confidence from data-quality inputs only."""
    reasons: list[str] = []

    if inputs.baseline_score <= 0:
        reasons.append("baseline_score_zero_or_missing")
    if inputs.component_count < inputs.expected_component_count:
        reasons.append("incomplete_component_vector")
    if inputs.uses_connector_fallback:
        reasons.append("connector_fallback_features")
    if inputs.data_snapshot_stale:
        reasons.append("data_snapshot_stale")
    if not inputs.geometry_hash_verified:
        reasons.append("geometry_hash_mismatch")

    if "connector_fallback_features" in reasons or "geometry_hash_mismatch" in reasons:
        return "low", reasons
    if "data_snapshot_stale" in reasons or "incomplete_component_vector" in reasons:
        return "medium", reasons if reasons else ["default_medium_quality"]
    if "baseline_score_zero_or_missing" in reasons:
        return "low", reasons
    return "high", reasons if reasons else ["full_component_vector", "snapshot_verified"]
