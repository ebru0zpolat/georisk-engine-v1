"""Tests for the JRC-family depth-damage curve engine."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.loss.depth_damage_curves import (
    DepthDamageCatalogue,
    DepthDamageCurve,
    damage_ratio_at_depth,
    load_depth_damage_catalogue,
    load_depth_damage_from_path,
    occupancy_for_building_type,
    select_depth_curve,
)

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = "jrc_depth_damage_fixture_v0.1.json"


def _curve(points, occupancy="residential"):
    return DepthDamageCurve(
        curve_id="t",
        occupancy=occupancy,
        points=[{"depth_m": d, "damage_ratio": r} for d, r in points],
        source="test",
        synthetic=True,
        version="0",
    )


# ---- interpolation ----

def test_exact_points_and_linear_midpoint():
    c = _curve([(0.0, 0.0), (1.0, 0.4), (2.0, 0.6)])
    assert c.damage_ratio_at_depth(0.0) == 0.0
    assert c.damage_ratio_at_depth(1.0) == pytest.approx(0.4)
    assert c.damage_ratio_at_depth(0.5) == pytest.approx(0.2)
    assert c.damage_ratio_at_depth(1.5) == pytest.approx(0.5)


def test_clamps_below_and_above():
    c = _curve([(0.5, 0.1), (3.0, 0.9)])
    assert c.damage_ratio_at_depth(-2.0) == 0.1   # below first point
    assert c.damage_ratio_at_depth(0.0) == 0.1
    assert c.damage_ratio_at_depth(99.0) == 0.9   # above last point


def test_monotonic_increasing_over_depth():
    c = _curve([(0.0, 0.0), (0.5, 0.25), (1.0, 0.4), (2.0, 0.6), (6.0, 1.0)])
    prev = -1.0
    for d in [0, 0.3, 0.7, 1.2, 3.0, 5.5, 8.0]:
        v = c.damage_ratio_at_depth(d)
        assert v >= prev
        assert 0.0 <= v <= 1.0
        prev = v


# ---- validation ----

def test_rejects_non_monotonic_damage():
    with pytest.raises(ValueError):
        _curve([(0.0, 0.0), (1.0, 0.5), (2.0, 0.3)])


def test_rejects_non_increasing_depths():
    with pytest.raises(ValueError):
        _curve([(1.0, 0.1), (1.0, 0.2)])
    with pytest.raises(ValueError):
        _curve([(2.0, 0.1), (1.0, 0.2)])


def test_rejects_too_few_points():
    with pytest.raises(ValueError):
        _curve([(0.0, 0.0)])


# ---- occupancy mapping ----

def test_occupancy_mapping():
    assert occupancy_for_building_type("retail") == "commercial"
    assert occupancy_for_building_type("apartment") == "residential"
    assert occupancy_for_building_type("industrial") == "industrial"
    assert occupancy_for_building_type("weird") == "commercial"


# ---- fixture catalogue + selection + fail-closed ----

def test_fixture_catalogue_is_labelled_synthetic_but_usable():
    cat = load_depth_damage_catalogue(_FIXTURE)
    assert cat.synthetic is True
    assert cat.populated is True
    ratio, curve = damage_ratio_at_depth(building_type="office", depth_m=1.0, catalogue=cat)
    assert curve.occupancy == "commercial"
    assert 0.0 < ratio < 1.0


def test_select_fail_closed_when_unpopulated():
    cat = DepthDamageCatalogue(
        catalogue_id="jrc_global_depth_damage",
        version="1.0",
        source="pending",
        synthetic=False,
        populated=False,
        curves=[_curve([(0.0, 0.0), (1.0, 0.5)])],
    )
    with pytest.raises(ValueError, match="UNPOPULATED_FAIL_CLOSED"):
        select_depth_curve(building_type="office", catalogue=cat)


def test_continent_specific_curve_preferred():
    cat = DepthDamageCatalogue(
        catalogue_id="c", version="1", source="s", synthetic=False, populated=True,
        curves=[
            DepthDamageCurve(curve_id="glob", occupancy="residential", continent="*",
                             points=[{"depth_m": 0, "damage_ratio": 0}, {"depth_m": 1, "damage_ratio": 0.3}],
                             source="s", synthetic=False, version="1"),
            DepthDamageCurve(curve_id="eu", occupancy="residential", continent="europe",
                             points=[{"depth_m": 0, "damage_ratio": 0}, {"depth_m": 1, "damage_ratio": 0.5}],
                             source="s", synthetic=False, version="1"),
        ],
    )
    curve = select_depth_curve(building_type="apartment", continent="Europe", catalogue=cat)
    assert curve.curve_id == "eu"


# ---- vendor script round-trip ----

def _load_vendor_module():
    spec = importlib.util.spec_from_file_location(
        "vendor_jrc", _ROOT / "scripts" / "vendor_jrc_depth_damage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendor_csv_builds_real_catalogue(tmp_path):
    vendor = _load_vendor_module()
    csv_path = tmp_path / "jrc.csv"
    csv_path.write_text(
        "continent,occupancy,depth_m,damage_ratio\n"
        "Europe,residential,0.0,0.00\n"
        "Europe,residential,1.0,0.40\n"
        "Europe,residential,6.0,1.00\n"
        "Europe,commercial,0.0,0.00\n"
        "Europe,commercial,1.0,0.30\n"
        "Europe,commercial,6.0,1.00\n",
        encoding="utf-8",
    )
    grouped = vendor._read_csv(csv_path)
    curves = vendor._build_curves(grouped)
    catalogue = {
        "catalogue_id": vendor.CATALOGUE_ID,
        "version": vendor.CATALOGUE_VERSION,
        "source": vendor.JRC_SOURCE,
        "synthetic": False,
        "populated": True,
        "curves": curves,
    }
    out = tmp_path / "cat.json"
    out.write_text(json.dumps(catalogue), encoding="utf-8")

    cat = load_depth_damage_from_path(out)
    assert cat.synthetic is False and cat.populated is True
    ratio, curve = damage_ratio_at_depth(
        building_type="office", depth_m=1.0, continent="europe", catalogue=cat
    )
    assert curve.occupancy == "commercial"
    assert ratio == pytest.approx(0.30)
