"""stub_global_mdr v0.2.0 ships wildfire and earthquake curves with their hazard modules."""

from __future__ import annotations

from app.adaptation.catalogue import get_default_catalogue
from app.loss.damage_curves import (
    DAMAGE_CURVES_VERSION,
    load_catalogue,
    load_catalogue_by_id_version,
    select_curve,
)
from app.loss.horizon_scenarios import load_horizon_scenario_catalogue

_BUILDING_TYPES = ("hotel", "apartment", "office", "retail", "industrial", "residential")


def test_default_catalogue_is_v0_2_and_synthetic() -> None:
    cat = load_catalogue()
    assert cat.catalogue_id == "stub_global_mdr"
    assert cat.version == "0.2.0"
    assert cat.synthetic is True
    assert DAMAGE_CURVES_VERSION == "stub_global_mdr-v0.2.0"


def test_every_building_type_has_a_specific_wildfire_and_earthquake_curve() -> None:
    for hazard in ("wildfire", "earthquake"):
        for bt in _BUILDING_TYPES:
            curve = select_curve(building_type=bt, use_class="*", hazard_id=hazard)
            assert curve.hazard_id == hazard, (hazard, bt)
            assert curve.building_type == bt, (hazard, bt)
            assert curve.curve_id.startswith("stub_"), curve.curve_id
            assert curve.synthetic is True
        default = select_curve(building_type="warehouse", use_class="*", hazard_id=hazard)
        assert default.hazard_id == hazard
        assert default.building_type == "*"


def test_flood_and_heat_curves_unchanged_from_v0_1_1() -> None:
    old = load_catalogue_by_id_version("stub_global_mdr", "0.1.1")
    new = load_catalogue()
    old_rows = {c.curve_id: (c.exponent, c.scale) for c in old.curves}
    new_rows = {c.curve_id: (c.exponent, c.scale) for c in new.curves}
    for curve_id, params in old_rows.items():
        assert new_rows[curve_id] == params, curve_id


def test_earthquake_more_damaging_than_wildfire_at_same_intensity_for_apartments() -> None:
    quake = select_curve(building_type="apartment", use_class="*", hazard_id="earthquake")
    fire = select_curve(building_type="apartment", use_class="*", hazard_id="wildfire")
    assert quake.mdr(0.8) > fire.mdr(0.8)
    assert quake.mdr(0.0) == 0.0 and fire.mdr(0.0) == 0.0


def test_horizon_fixture_uplifts_wildfire_and_keeps_earthquake_stationary() -> None:
    cat = load_horizon_scenario_catalogue("horizon_scenario_fixture_v0.1.json")
    assert cat.version == "0.2"
    assert cat.project("wildfire", 0.5, "2050") > cat.project("wildfire", 0.5, "2030") > 0.5
    assert cat.project("earthquake", 0.37, "2030") == 0.37
    assert cat.project("earthquake", 0.37, "2050") == 0.37


def test_adaptation_catalogue_addresses_the_new_hazards() -> None:
    by_id = {m.measure_id: m for m in get_default_catalogue()}
    assert by_id["seismic-retrofit-v1"].hazards_addressed == ("earthquake",)
    assert by_id["wildfire-defensible-space-v1"].hazards_addressed == ("wildfire",)
    addressed = {h for m in by_id.values() for h in m.hazards_addressed}
    assert {"flood", "extreme_heat", "wildfire", "earthquake"} <= addressed
