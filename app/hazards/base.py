"""Country-agnostic hazard module contract for the five-layer Hazard layer.

Modules live in ``georisk-core``; country-specific thresholds/data belong in packs.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class HazardModuleResult(BaseModel):
    """Single-hazard intensity suitable for aggregation into ``HazardResult``."""

    hazard_id: str
    intensity: float = Field(..., ge=0.0, le=1.0, description="Normalised hazard intensity.")
    score_0_100: int = Field(..., ge=0, le=100)
    subtypes: dict[str, float] = Field(
        default_factory=dict,
        description="Optional subtype intensities in [0, 1] (e.g. fluvial / pluvial / coastal).",
    )
    data_versions: dict[str, str] = Field(default_factory=dict)
    methodology_version: str
    valuation_date: date
    latitude: float
    longitude: float
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class HazardModule(Protocol):
    """Pluggable hazard module — one physical peril per implementation."""

    hazard_id: str
    methodology_version: str

    def evaluate(
        self,
        *,
        latitude: float,
        longitude: float,
        valuation_date: date,
        parameters: dict[str, Any] | None = None,
    ) -> HazardModuleResult: ...


def score_to_intensity(score_0_100: int | float) -> float:
    return round(max(0.0, min(1.0, float(score_0_100) / 100.0)), 6)


def intensity_to_score(intensity: float) -> int:
    return max(0, min(100, int(round(float(intensity) * 100.0))))


__all__ = [
    "HazardModule",
    "HazardModuleResult",
    "intensity_to_score",
    "score_to_intensity",
]
