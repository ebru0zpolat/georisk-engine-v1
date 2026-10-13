from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ScenarioModel(StrEnum):
    CMIP6 = "CMIP6"


class ScenarioPathway(StrEnum):
    SSP1_2_6 = "SSP1-2.6"
    SSP2_4_5 = "SSP2-4.5"
    SSP5_8_5 = "SSP5-8.5"


class ScenarioHazard(StrEnum):
    FLOOD = "flood"
    DROUGHT = "drought"
    WILDFIRE = "wildfire"
    HEAT = "heat"
    STORM_SURGE = "storm_surge"
    CYCLONE = "cyclone"


class ScenarioRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"


class ScenarioConfig(BaseModel):
    model: ScenarioModel = ScenarioModel.CMIP6
    pathway: ScenarioPathway
    target_year: int = Field(..., ge=2030, le=2100)
    hazards: list[ScenarioHazard] = Field(..., min_length=1, max_length=12)

    @field_validator("hazards")
    @classmethod
    def unique_hazards(cls, hazards: list[ScenarioHazard]) -> list[ScenarioHazard]:
        seen: set[ScenarioHazard] = set()
        ordered: list[ScenarioHazard] = []
        for h in hazards:
            if h not in seen:
                seen.add(h)
                ordered.append(h)
        return ordered


class ScenarioParameters(BaseModel):
    return_period: list[int] = Field(
        default_factory=lambda: [10, 50, 100],
        min_length=1,
        max_length=10,
    )
    spatial_resolution: str = Field(
        default="100m",
        description='Requested downscaled grid label (e.g. "100m", "1km").',
    )

    @field_validator("return_period")
    @classmethod
    def positive_return_periods(cls, values: list[int]) -> list[int]:
        for v in values:
            if v < 1:
                raise ValueError("return_period values must be positive integers")
        return sorted(set(values))


class ScenarioMetadata(BaseModel):
    client_context: str | None = None
    workflow_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ScenarioRunRequest(BaseModel):
    """Scenario-Lab run body (Layer 2). ``asset_id`` = GeoRisk ``audit_id`` from Core."""

    asset_id: UUID
    scenario_config: ScenarioConfig
    parameters: ScenarioParameters = Field(default_factory=ScenarioParameters)
    metadata: ScenarioMetadata = Field(default_factory=ScenarioMetadata)
    data_snapshot_id: str | None = Field(
        default=None,
        description="Optional; must match Core snapshot when provided.",
    )
    asset_geometry_hash: str | None = Field(
        default=None,
        description="Optional; must match computed geometry hash when provided.",
    )


# --- Response contract (agentic / DeerFlow consumer) ---


class HazardResultDetail(BaseModel):
    severity_index: float = Field(..., ge=0.0, le=1.0)
    affected_fraction: float = Field(..., ge=0.0, le=1.0)
    return_periods: dict[str, float] = Field(
        ...,
        description='Exceedance-style intensities keyed as "10y", "50y", "100y".',
    )


class ScenarioShocks(BaseModel):
    correlated_events: list[str]
    systemic_risk_score: float = Field(..., ge=0.0, le=1.0)


class ImpactPathStep(BaseModel):
    tier: str
    target: str
    loss: float = Field(..., ge=0.0, le=1.0)


class ScenarioPropagation(BaseModel):
    node: str
    impact_path: list[ImpactPathStep]


class ScenarioAuditContext(BaseModel):
    linked_audit_ids: list[str]
    disclaimer: str


class ScenarioScoringSummary(BaseModel):
    """Deterministic scenario-adjusted score (hazard-only SSP uplift).

    Identical output when:
    asset_id + asset_geometry_hash + data_snapshot_id + model_version + scenario
    + horizon + coefficient_table_version + coefficient_table_hash match.
    """

    asset_id: str
    asset_geometry_hash: str
    model_version: str
    data_snapshot_id: str
    coefficient_table_version: str
    coefficient_table_hash: str
    baseline_score: int
    scenario: str
    horizon: int
    hazard_score: int
    exposure_score: int
    vulnerability_score: int
    hazard_multiplier: float = Field(
        description="Weighted effective multiplier (equal-mean across drivers).",
    )
    hazard_multiplier_type: str = "weighted_effective"
    hazard_driver_multipliers: dict[str, float] = Field(default_factory=dict)
    raw_adjusted_hazard: float
    adjusted_hazard_score: int
    raw_scenario_score: float
    scenario_score: int
    scenario_delta_points: int
    scenario_delta_pct: float | None = None
    scenario_delta_cap_applied: bool = False
    confidence: str
    confidence_reasons: list[str] = Field(default_factory=list)
    drivers: list[str]
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "hazard": 0.55,
            "exposure": 0.25,
            "vulnerability": 0.20,
        }
    )


class ScenarioRunResponse(BaseModel):
    scenario_id: str
    status: ScenarioRunStatus
    scenario_scoring: ScenarioScoringSummary
    hazard_results: dict[str, HazardResultDetail]
    shocks: ScenarioShocks
    propagation: ScenarioPropagation
    audit_context: ScenarioAuditContext
