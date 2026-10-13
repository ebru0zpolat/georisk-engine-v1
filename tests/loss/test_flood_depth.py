"""Tests for the elevation → depth → JRC damage bridge."""

from __future__ import annotations

import pytest

from app.loss.depth_damage_curves import load_depth_damage_catalogue
from app.loss.flood_depth import (
    DEFAULT_REFERENCE_LEVEL_M,
    flood_damage_fraction,
    inundation_depth_m,
)

_FIXTURE = "jrc_depth_damage_fixture_v0.1.json"


def test_depth_positive_when_below_reference():
    assert inundation_depth_m(ground_elevation_m=-2.0, reference_level_m=1.0) == 3.0


def test_depth_zero_when_above_reference():
    assert inundation_depth_m(ground_elevation_m=4.0, reference_level_m=1.0) == 0.0
    assert inundation_depth_m(ground_elevation_m=1.0, reference_level_m=1.0) == 0.0


def test_lower_ground_gives_more_damage():
    cat = load_depth_damage_catalogue(_FIXTURE)
    _, deep_ratio, _ = flood_damage_fraction(
        ground_elevation_m=-3.0, building_type="office", catalogue=cat, reference_level_m=2.0
    )
    _, shallow_ratio, _ = flood_damage_fraction(
        ground_elevation_m=1.0, building_type="office", catalogue=cat, reference_level_m=2.0
    )
    assert deep_ratio > shallow_ratio


def test_dry_asset_zero_damage():
    cat = load_depth_damage_catalogue(_FIXTURE)
    depth, ratio, _ = flood_damage_fraction(
        ground_elevation_m=10.0, building_type="office", catalogue=cat, reference_level_m=1.0
    )
    assert depth == 0.0
    assert ratio == 0.0


def test_composition_selects_occupancy_curve():
    cat = load_depth_damage_catalogue(_FIXTURE)
    _, _, curve = flood_damage_fraction(
        ground_elevation_m=-1.0, building_type="apartment", catalogue=cat
    )
    assert curve.occupancy == "residential"


def test_default_reference_level_is_labelled_placeholder():
    # Guardrail: the default is the synthetic placeholder, not a real flood level.
    assert DEFAULT_REFERENCE_LEVEL_M == 1.0
