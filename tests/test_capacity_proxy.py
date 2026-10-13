"""Tests for thermal proxy capacity scaling."""

from __future__ import annotations

import pytest

from app.scoring.capacity_proxy import (
    DEFAULT_BASELINE_TEMP_C,
    DEFAULT_STANDBY_FLOOR_C,
    estimate_capacity,
    format_capacity_pct_precise,
    format_estimated_production_capacity,
)


def test_estimate_capacity_below_standby_is_zero() -> None:
    assert estimate_capacity(14.9) == 0.0


def test_estimate_capacity_at_standby_is_zero() -> None:
    assert estimate_capacity(DEFAULT_STANDBY_FLOOR_C) == 0.0


def test_estimate_capacity_at_baseline_is_hundred() -> None:
    assert estimate_capacity(DEFAULT_BASELINE_TEMP_C) == 100.0


def test_estimate_capacity_akcansa_example() -> None:
    """Akçansa Çanakkale örneği (~19.25 °C) doğrusal formül ile hesaplanır."""
    kko = estimate_capacity(19.25)
    expected = round(((19.25 - DEFAULT_STANDBY_FLOOR_C) / (DEFAULT_BASELINE_TEMP_C - DEFAULT_STANDBY_FLOOR_C)) * 100, 2)
    assert kko == expected
    assert kko == pytest.approx(83.17, rel=1e-3)


def test_estimate_capacity_caps_above_baseline() -> None:
    assert estimate_capacity(25.0) == 100.0


def test_estimate_capacity_invalid_range_raises() -> None:
    with pytest.raises(ValueError):
        estimate_capacity(20.0, baseline_temp=14.0, standby_floor_c=15.0)


def test_format_estimated_production_capacity() -> None:
    pct = estimate_capacity(19.25)
    assert format_estimated_production_capacity(pct) == f"≈{pct:.1f}%"
    assert format_estimated_production_capacity(100.0) == "≈100.0%"


def test_format_capacity_pct_precise_preserves_small_spread() -> None:
    limak = estimate_capacity(20.06)
    cimsa = estimate_capacity(20.11)
    assert limak == 99.02
    assert cimsa == 100.0
    assert format_capacity_pct_precise(limak) == "99.02%"
    assert format_capacity_pct_precise(cimsa) == "100.00%"
    assert format_capacity_pct_precise(estimate_capacity(19.25)) == "83.17%"
