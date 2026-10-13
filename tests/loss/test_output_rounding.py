"""Property: output rounding is cents-only — intermediates stay full precision."""

from __future__ import annotations

from datetime import date

import pytest

from app.loss.damage_curves import load_catalogue
from app.loss.expected_loss import (
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    _compute_core_v0_3,
    _eal_for_intensities_v0_3,
    combined_mdr,
)


@pytest.mark.parametrize(
    "intensities,fragility,adaptation",
    [
        ({"flood": 0.42, "extreme_heat": 0.55}, 1.0, 0.2),
        ({"flood": 0.85, "extreme_heat": 0.80}, 1.8, 0.0),
        ({"flood": 0.1}, 1.0, 0.0),
        ({"flood": 0.33, "extreme_heat": 0.33, "storm": 0.33}, 1.2, 0.1),
        ({"flood": 0.0, "extreme_heat": 0.7}, 0.9, 0.0),
        ({"flood": 1.0, "extreme_heat": 1.0}, 2.0, 0.0),
    ],
)
def test_output_rounding_differs_from_full_precision_by_less_than_half_cent(
    intensities: dict[str, float],
    fragility: float,
    adaptation: float,
) -> None:
    """With vs without output rounding: |ΔEAL| < 0.005 (cents rounding only)."""
    asset = ExpectedLossAssetInput(
        asset_id="round-prop",
        asset_value=1_000_000.0,
        building_type="hotel",
        use_class="tourism",
        fragility_factor=fragility,
        adaptation_capacity_factor=adaptation,
    )
    catalogue = load_catalogue()
    rounded, _, _, _, _ = _eal_for_intensities_v0_3(
        asset=asset,
        intensities=intensities,
        catalogue=catalogue,
        apply_output_rounding=True,
    )
    full, _, _, _, _ = _eal_for_intensities_v0_3(
        asset=asset,
        intensities=intensities,
        catalogue=catalogue,
        apply_output_rounding=False,
    )
    assert abs(rounded - full) < 0.005


def test_compute_core_scenario_eals_respect_cents_rounding_bound() -> None:
    asset = ExpectedLossAssetInput(
        asset_id="round-core",
        asset_value=2_500_000.0,
        building_type="office",
        use_class="commercial",
        fragility_factor=1.4,
        adaptation_capacity_factor=0.05,
    )
    hazards = HazardScenarioIntensities(
        current={"flood": 0.61, "extreme_heat": 0.44},
        horizon_2030={"flood": 0.58, "extreme_heat": 0.40},
        horizon_2050={"flood": 0.70, "extreme_heat": 0.50},
    )
    catalogue = load_catalogue()
    rounded = _compute_core_v0_3(
        asset=asset,
        hazards=hazards,
        valuation_date=date(2024, 12, 31),
        catalogue=catalogue,
        apply_output_rounding=True,
    )
    full = _compute_core_v0_3(
        asset=asset,
        hazards=hazards,
        valuation_date=date(2024, 12, 31),
        catalogue=catalogue,
        apply_output_rounding=False,
    )
    assert abs(rounded["eal_absolute"] - full["eal_absolute"]) < 0.005
    assert abs(rounded["scenario_eal"]["2030"] - full["scenario_eal"]["2030"]) < 0.005
    assert abs(rounded["scenario_eal"]["2050"] - full["scenario_eal"]["2050"]) < 0.005


def test_combined_mdr_preserves_full_precision() -> None:
    """combined_mdr must not pre-round (round(..., 6) would be an intermediate bug)."""
    mdrs = {"flood": 0.123456789, "extreme_heat": 0.234567891}
    survival = (1.0 - 0.123456789) * (1.0 - 0.234567891)
    expected = max(0.0, min(1.0, 1.0 - survival))
    got = combined_mdr(mdrs)
    assert got == expected
    # Fixture must be one where 6-decimal intermediate rounding would diverge.
    assert round(expected, 6) != expected
