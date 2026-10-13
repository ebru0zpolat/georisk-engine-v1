from __future__ import annotations

from dataclasses import dataclass

from app.geo.interfaces import derive_point_geometry_hash
from app.scoring.scenario_coefficients import (
    coefficient_table_hash,
    coefficient_table_version,
    hazard_driver_multipliers,
    weighted_effective_multiplier,
)
from app.scoring.scenario_confidence import DataQualityInputs, derive_confidence
from app.scoring.scenario_pipeline import (
    MAX_SCORE,
    SCENARIO_DELTA_CAP_POINTS,
    WEIGHT_EXPOSURE,
    WEIGHT_HAZARD,
    WEIGHT_VULNERABILITY,
    apply_cap_pipeline as _apply_cap_pipeline_dict,
)

# IPCC-style v1 weights: hazard modulated by SSP; exposure & vulnerability fixed per snapshot.

HAZARD_COMPONENT_KEYS = ("ocean", "pollution", "land")
EXPOSURE_COMPONENT_KEYS = ("industrial",)
VULNERABILITY_COMPONENT_KEYS = ("agriculture", "sensitivity")

from app.scoring.scenario_constants import HAZARD_DRIVER_LABELS, HAZARD_MULTIPLIER_TYPE


@dataclass(frozen=True)
class HevScores:
    hazard: int
    exposure: int
    vulnerability: int


@dataclass(frozen=True)
class CapPipelineResult:
    raw_adjusted_hazard: float
    adjusted_hazard_score: int
    raw_scenario_score: float
    raw_delta_points: float
    capped_delta_points: int
    scenario_score: int
    scenario_delta_cap_applied: bool
    final_score_cap_applied: bool


@dataclass(frozen=True)
class ScenarioScoreResult:
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
    hazard_multiplier: float
    hazard_multiplier_type: str
    hazard_driver_multipliers: dict[str, float]
    raw_adjusted_hazard: float
    adjusted_hazard_score: int
    raw_scenario_score: float
    scenario_score: int
    scenario_delta_points: int
    scenario_delta_pct: float | None
    scenario_delta_cap_applied: bool
    confidence: str
    confidence_reasons: list[str]
    drivers: list[str]


def _mean(keys: tuple[str, ...], components: dict[str, int]) -> int:
    vals = [components.get(k, 0) for k in keys]
    if not vals:
        return 0
    return round(sum(vals) / len(vals))


def hev_from_components(components: dict[str, int]) -> HevScores:
    return HevScores(
        hazard=_mean(HAZARD_COMPONENT_KEYS, components),
        exposure=_mean(EXPOSURE_COMPONENT_KEYS, components),
        vulnerability=_mean(VULNERABILITY_COMPONENT_KEYS, components),
    )


def weighted_final_score_raw(hev: HevScores, hazard_value: int) -> float:
    return (
        WEIGHT_HAZARD * hazard_value
        + WEIGHT_EXPOSURE * hev.exposure
        + WEIGHT_VULNERABILITY * hev.vulnerability
    )


def apply_cap_pipeline(
    *,
    baseline_score: int,
    hev: HevScores,
    weighted_multiplier: float,
) -> CapPipelineResult:
    """GEO-150 cap semantics (4 testable steps)."""
    caps = _apply_cap_pipeline_dict(
        hazard_score=hev.hazard,
        exposure_score=hev.exposure,
        vulnerability_score=hev.vulnerability,
        baseline_score=baseline_score,
        effective_multiplier=weighted_multiplier,
    )
    return CapPipelineResult(
        raw_adjusted_hazard=float(caps["raw_adjusted_hazard"]),
        adjusted_hazard_score=int(caps["adjusted_hazard_score"]),
        raw_scenario_score=float(caps["raw_scenario_score"]),
        raw_delta_points=float(caps["raw_delta_points"]),
        capped_delta_points=int(caps["capped_delta_points"]),
        scenario_score=int(caps["scenario_score"]),
        scenario_delta_cap_applied=bool(caps["scenario_delta_cap_applied"]),
        final_score_cap_applied=bool(caps["final_score_cap_applied"]),
    )


def scenario_delta_pct(baseline_score: int, delta_points: int) -> float | None:
    if baseline_score <= 0:
        return None
    return round((delta_points / baseline_score) * 100, 1)


def compute_scenario_score(
    *,
    asset_id: str,
    model_version: str,
    data_snapshot_id: str,
    baseline_score: int,
    components: dict[str, int],
    pathway: str,
    horizon: int,
    hazards: list[str],
    latitude: float = 0.0,
    longitude: float = 0.0,
    radius_km: float = 10.0,
    sector: str = "industrial",
    uses_connector_fallback: bool = False,
    geometry_hash_verified: bool = True,
) -> ScenarioScoreResult:
    geometry_hash = derive_point_geometry_hash(latitude=latitude, longitude=longitude)
    hev = hev_from_components(components)
    driver_mults = hazard_driver_multipliers(hazards, pathway, horizon)
    multiplier = weighted_effective_multiplier(driver_mults)

    caps = apply_cap_pipeline(
        baseline_score=baseline_score,
        hev=hev,
        weighted_multiplier=multiplier,
    )

    delta_points = caps.scenario_score - baseline_score
    delta_pct = scenario_delta_pct(baseline_score, delta_points)

    confidence, confidence_reasons = derive_confidence(
        DataQualityInputs(
            baseline_score=baseline_score,
            component_count=len(components),
            uses_connector_fallback=uses_connector_fallback,
            geometry_hash_verified=geometry_hash_verified,
        )
    )

    drivers = list(driver_mults.keys())[:3]
    if not drivers:
        drivers = ["climate_hazard_blend"]

    return ScenarioScoreResult(
        asset_id=asset_id,
        asset_geometry_hash=geometry_hash,
        model_version=model_version,
        data_snapshot_id=data_snapshot_id,
        coefficient_table_version=coefficient_table_version(),
        coefficient_table_hash=coefficient_table_hash(),
        baseline_score=baseline_score,
        scenario=pathway,
        horizon=horizon,
        hazard_score=hev.hazard,
        exposure_score=hev.exposure,
        vulnerability_score=hev.vulnerability,
        hazard_multiplier=multiplier,
        hazard_multiplier_type=HAZARD_MULTIPLIER_TYPE,
        hazard_driver_multipliers=driver_mults,
        raw_adjusted_hazard=round(caps.raw_adjusted_hazard, 4),
        adjusted_hazard_score=caps.adjusted_hazard_score,
        raw_scenario_score=round(caps.raw_scenario_score, 4),
        scenario_score=caps.scenario_score,
        scenario_delta_points=delta_points,
        scenario_delta_pct=delta_pct,
        scenario_delta_cap_applied=caps.scenario_delta_cap_applied,
        confidence=confidence,
        confidence_reasons=confidence_reasons,
        drivers=drivers,
    )
