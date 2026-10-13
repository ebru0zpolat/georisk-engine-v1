"""Typed five-layer pipeline contract (§2.3 / Phase A).

Hazard × Exposure × Vulnerability → Expected Loss → Adaptation Investment → Avoided Loss
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.adaptation import AdaptationOutcome
from app.schemas.portfolio import UniversalAsset

# Bump minor when damage curves / EAL formula change (directive methodology versioning).
METHODOLOGY_VERSION = "five-layer-eal-v0.4"


class HazardComponent(BaseModel):
    hazard_id: str
    intensity: float = Field(..., ge=0.0, le=1.0)
    horizon: Literal["2030", "2050", "2100"] | None = None


class HazardLayer(BaseModel):
    """Layer 1 — multi-hazard intelligence (deterministic stub until connectors pack-wired)."""

    components: list[HazardComponent]
    composite_intensity: float = Field(..., ge=0.0, le=1.0)
    data_versions: dict[str, str] = Field(default_factory=dict)


class ExposureLayer(BaseModel):
    """Layer 2 — geocoded asset exposure."""

    asset_id: str
    asset_value: float
    building_type: str
    use_class: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    ltv: float | None = None


class VulnerabilityLayer(BaseModel):
    """Layer 3 — structure fragility + adaptation capacity."""

    fragility_factor: float = Field(..., ge=0.0, le=1.0)
    adaptation_capacity_factor: float = Field(..., ge=0.0, le=1.0)
    construction_year: int | None = None
    floors: int | None = None
    existing_measures: list[str] = Field(default_factory=list)


class FinancialLayer(BaseModel):
    """Layer 4 — financial translation (EAL and related indicators)."""

    eal_absolute: float = Field(..., ge=0.0)
    eal_pct_of_value: float = Field(..., ge=0.0)
    risk_score: float = Field(..., ge=0.0, le=100.0)
    scenario_deltas: dict[str, float] = Field(
        default_factory=dict,
        description="EAL absolute deltas keyed by horizon (e.g. 2030, 2050).",
    )
    collateral_sensitivity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of collateral value at risk under base EAL.",
    )
    insurability: Literal["insured", "insurable_with_conditions", "protection_gap"]


class AdaptationMeasureResult(BaseModel):
    measure_id: str
    label: str
    cost: float = Field(..., ge=0.0)
    risk_reduction_fraction: float = Field(..., ge=0.0, le=1.0)
    avoided_loss: float = Field(..., ge=0.0)
    residual_eal: float = Field(..., ge=0.0)
    outcome: AdaptationOutcome | None = None


class AdaptationLayer(BaseModel):
    """Layer 5 — adaptation evidence."""

    measures: list[AdaptationMeasureResult]
    recommended_measure_id: str | None = None
    residual_risk_score: float = Field(..., ge=0.0, le=100.0)


class FiveLayerResult(BaseModel):
    """Full pipeline output for one asset, linked to an audit-trail record."""

    methodology_version: str = METHODOLOGY_VERSION
    valuation_date: date
    asset_id: str
    hazard: HazardLayer
    exposure: ExposureLayer
    vulnerability: VulnerabilityLayer
    financial: FinancialLayer
    adaptation: AdaptationLayer
    audit_record_id: str
    computed_at: datetime


class FiveLayerRunRequest(BaseModel):
    """Run the five-layer pipeline for one P0 asset."""

    valuation_date: date
    asset: UniversalAsset
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional analysis parameters recorded in the audit trail.",
    )


class FiveLayerRunResponse(BaseModel):
    result: FiveLayerResult
    #: Persisted run (``runs`` row + sealed audit records); ``None`` on the
    #: local file-trail fallback, where no run row exists.
    run_id: str | None = None


__all__ = [
    "AdaptationLayer",
    "AdaptationMeasureResult",
    "ExposureLayer",
    "FinancialLayer",
    "FiveLayerResult",
    "FiveLayerRunRequest",
    "FiveLayerRunResponse",
    "HazardComponent",
    "HazardLayer",
    "METHODOLOGY_VERSION",
    "VulnerabilityLayer",
]
