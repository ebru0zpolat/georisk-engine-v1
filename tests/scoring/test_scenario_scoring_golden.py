"""Merge-blocking golden fixtures (GEO-150)."""

from __future__ import annotations

from app.scoring.scenario_coefficients import coefficient_table_hash, coefficient_table_version
from app.scoring.scenario_score import (
    apply_cap_pipeline,
    compute_scenario_score,
    hev_from_components,
    scenario_delta_pct,
)

_COMPONENTS_60 = {k: 60 for k in ("industrial", "pollution", "land", "ocean", "agriculture", "sensitivity")}
_COMPONENTS_90 = {k: 90 for k in _COMPONENTS_60}


def _base_kwargs(**overrides: object) -> dict:
    base = dict(
        asset_id="golden-asset",
        model_version="v1.0.3",
        data_snapshot_id="hazard_layers_2026_05",
        baseline_score=60,
        components=dict(_COMPONENTS_60),
        pathway="SSP5-8.5",
        horizon=2050,
        hazards=["flood", "drought", "wildfire"],
        latitude=36.85,
        longitude=30.75,
        radius_km=10.0,
        sector="industrial",
        uses_connector_fallback=False,
        geometry_hash_verified=True,
    )
    base.update(overrides)
    return base


def test_g002_ssp585_2050_all_sixty() -> None:
    """G-002: all=60, SSP5-8.5, 2050 → score=72, delta=12, pct=20%."""
    result = compute_scenario_score(**_base_kwargs())
    assert result.scenario_score == 72
    assert result.scenario_delta_points == 12
    assert result.scenario_delta_pct == 20.0
    assert result.hazard_multiplier_type == "weighted_effective"
    assert result.hazard_driver_multipliers == {
        "pluvial_flood": 1.3,
        "drought_stress": 1.35,
        "wildfire": 1.45,
    }
    assert abs(result.hazard_multiplier - 1.3667) < 0.001
    assert result.coefficient_table_version == "scenario_coefficients_v1.0"
    assert len(result.coefficient_table_hash) == 64
    assert result.asset_geometry_hash


def test_g003_saturation_no_overflow() -> None:
    """G-003: baseline=90, mult=1.90 → raw_score=95.5, adjusted_hazard capped at 100."""
    result = compute_scenario_score(
        **_base_kwargs(
            baseline_score=90,
            components=dict(_COMPONENTS_90),
            horizon=2100,
            hazards=["heat"],
        )
    )
    assert result.hazard_driver_multipliers["heat_stress"] == 1.9
    assert result.adjusted_hazard_score == 100
    assert result.raw_adjusted_hazard == 171.0
    assert result.raw_scenario_score == 95.5
    assert result.scenario_score <= 100


def test_g004_baseline_zero_delta_pct_null() -> None:
    """G-004: baseline=0 → scenario_delta_pct is null."""
    result = compute_scenario_score(**_base_kwargs(baseline_score=0))
    assert result.scenario_delta_pct is None
    assert scenario_delta_pct(0, result.scenario_delta_points) is None


def test_g005_multi_hazard_weighted_multiplier() -> None:
    """G-005: weighted effective = equal mean of driver multipliers."""
    result = compute_scenario_score(**_base_kwargs())
    drivers = result.hazard_driver_multipliers
    expected = round(sum(drivers.values()) / len(drivers), 4)
    assert result.hazard_multiplier == expected
    assert result.hazard_multiplier_type == "weighted_effective"


def test_g006_thousand_run_determinism() -> None:
    """G-006: 1000 identical runs → identical output."""
    kwargs = _base_kwargs()
    first = compute_scenario_score(**kwargs)
    for _ in range(999):
        assert compute_scenario_score(**kwargs) == first


def test_g007_coefficient_table_hash_in_response() -> None:
    """G-007: response exposes coefficient_table_hash matching manifest."""
    result = compute_scenario_score(**_base_kwargs())
    assert result.coefficient_table_hash == coefficient_table_hash()
    assert result.coefficient_table_version == coefficient_table_version()


def test_cap_pipeline_four_steps() -> None:
    """Cap semantics: adjusted_hazard min(raw,100); delta clamp; final min(base+delta,100)."""
    hev = hev_from_components(dict(_COMPONENTS_90))
    caps = apply_cap_pipeline(baseline_score=90, hev=hev, weighted_multiplier=1.9)
    assert caps.adjusted_hazard_score == 100
    assert caps.raw_adjusted_hazard == 171.0
    assert caps.raw_scenario_score == 95.5
