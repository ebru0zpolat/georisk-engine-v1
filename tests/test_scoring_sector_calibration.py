"""Sector-specific component calibration (agriculture weights)."""

from __future__ import annotations

from app.core.sector_registry import (
    AGRICULTURE_SECTOR_ID,
    DEFAULT_SECTOR_ID,
    IRON_STEEL_SECTOR_ID,
)
from app.schemas.risk import RiskScoreRequest
from app.scoring.risk_score import calibrate_component_vector, compute_component_scores


def test_calibrate_unknown_sector_is_identity() -> None:
    base = [55, 44, 33, 22, 66, 77]
    assert calibrate_component_vector(base, "unregistered_mining") == base


def test_calibrate_agriculture_shifts_emphasis() -> None:
    base = [90, 10, 20, 80, 30, 40]
    out = calibrate_component_vector(base, AGRICULTURE_SECTOR_ID)
    assert out != base
    assert out[2] >= base[2]  # land emphasis
    assert out[0] <= base[0]  # industrial de-emphasis
    assert all(0 <= v <= 100 for v in out)


def test_calibrate_preserves_mean_for_registered_profile() -> None:
    base = [10, 20, 30, 40, 50, 60]
    out = calibrate_component_vector(base, AGRICULTURE_SECTOR_ID)
    assert abs(sum(out) / 6 - sum(base) / 6) < 0.6


def test_compute_scores_differs_by_sector_same_geo() -> None:
    common = dict(
        asset_name="Same",
        latitude=40.0,
        longitude=29.0,
        radius_km=10.0,
    )
    ind = RiskScoreRequest(sector=DEFAULT_SECTOR_ID, **common)
    ag = RiskScoreRequest(sector=AGRICULTURE_SECTOR_ID, **common)
    c_ind = compute_component_scores(ind)
    c_ag = compute_component_scores(ag)
    assert c_ind != c_ag


def test_calibrate_iron_steel_shifts_emphasis() -> None:
    base = [40, 40, 50, 60, 70, 30]
    out = calibrate_component_vector(base, IRON_STEEL_SECTOR_ID)
    assert out != base
    assert out[0] >= base[0]  # industrial emphasis
    assert out[4] <= base[4]  # agriculture de-emphasis
    assert all(0 <= v <= 100 for v in out)


def test_compute_scores_iron_steel_differs_from_industrial() -> None:
    common = dict(asset_name="Mill", latitude=41.28, longitude=36.33, radius_km=12.0)
    ind = RiskScoreRequest(sector=DEFAULT_SECTOR_ID, **common)
    steel = RiskScoreRequest(sector=IRON_STEEL_SECTOR_ID, **common)
    assert compute_component_scores(ind) != compute_component_scores(steel)
