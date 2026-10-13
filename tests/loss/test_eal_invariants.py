"""Property tests for expected-loss v0.3 invariants (not example fixtures)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.loss.damage_curves import load_catalogue
from app.loss.expected_loss import (
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    _eal_for_intensities,
    attribution_shares,
)
from app.services.audit_trail import reset_audit_trail_for_tests


@pytest.fixture(autouse=True)
def _isolate_trail(tmp_path: Path) -> None:
    reset_audit_trail_for_tests(tmp_path / "trail.jsonl")


def _asset(*, fragility: float = 1.0, adaptation: float = 0.0) -> ExpectedLossAssetInput:
    return ExpectedLossAssetInput(
        asset_id="inv-1",
        asset_value=1_000_000.0,
        building_type="hotel",
        use_class="tourism",
        fragility_factor=fragility,
        adaptation_capacity_factor=adaptation,
    )


def test_attribution_shares_sum_to_one_when_intensity_sum_positive() -> None:
    cases = [
        {"flood": 0.4, "extreme_heat": 0.6},
        {"flood": 1.0},
        {"flood": 0.1, "extreme_heat": 0.2, "storm": 0.3},
        {"flood": 0.0, "extreme_heat": 0.5},
    ]
    for intensities in cases:
        shares = attribution_shares(intensities)
        assert shares
        assert sum(shares.values()) == pytest.approx(1.0, abs=1e-12)


def test_zero_intensity_sum_yields_no_shares_and_zero_eal() -> None:
    intensities = {"flood": 0.0, "extreme_heat": 0.0}
    assert attribution_shares(intensities) == {}
    eal, per_loss, _, _, combo = _eal_for_intensities(
        asset=_asset(),
        intensities=intensities,
        catalogue=load_catalogue(),
    )
    assert eal == 0.0
    assert combo == 0.0
    assert all(v == 0.0 for v in per_loss.values())


def test_adding_zero_intensity_hazard_never_changes_eal() -> None:
    catalogue = load_catalogue()
    asset = _asset()
    base = {"flood": 0.55, "extreme_heat": 0.40}
    with_zero = {**base, "storm": 0.0}
    eal_a, _, _, _, _ = _eal_for_intensities(
        asset=asset, intensities=base, catalogue=catalogue
    )
    eal_b, _, _, _, _ = _eal_for_intensities(
        asset=asset, intensities=with_zero, catalogue=catalogue
    )
    assert eal_a == eal_b


@pytest.mark.parametrize(
    "base",
    [
        {"flood": 0.2},
        {"flood": 0.3, "extreme_heat": 0.1},
        {"flood": 0.0, "extreme_heat": 0.4},
        {"flood": 0.5, "extreme_heat": 0.5, "storm": 0.1},
    ],
)
def test_increasing_any_single_hazard_never_decreases_eal(base: dict[str, float]) -> None:
    catalogue = load_catalogue()
    asset = _asset()
    base_eal, _, _, _, _ = _eal_for_intensities(
        asset=asset, intensities=base, catalogue=catalogue
    )
    for hid in base:
        bumped = dict(base)
        bumped[hid] = min(1.0, base[hid] + 0.15)
        if bumped[hid] == base[hid]:
            continue
        new_eal, _, _, _, _ = _eal_for_intensities(
            asset=asset, intensities=bumped, catalogue=catalogue
        )
        assert new_eal >= base_eal, (
            f"increasing {hid} from {base[hid]} to {bumped[hid]} "
            f"decreased EAL {base_eal} → {new_eal}"
        )


@pytest.mark.parametrize(
    "intensities,fragility",
    [
        ({"flood": 1.0, "extreme_heat": 1.0, "storm": 1.0}, 2.0),
        ({"flood": 0.9, "extreme_heat": 0.9}, 1.5),
        ({"flood": 0.55, "extreme_heat": 0.4}, 1.0),
        ({"flood": 0.0, "extreme_heat": 0.0}, 2.0),
    ],
)
def test_eal_never_exceeds_asset_value(
    intensities: dict[str, float], fragility: float
) -> None:
    asset = _asset(fragility=fragility)
    eal, _, _, _, _ = _eal_for_intensities(
        asset=asset,
        intensities=intensities,
        catalogue=load_catalogue(),
    )
    assert eal <= asset.asset_value


def test_hazard_scenario_model_rejects_empty_maps() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        HazardScenarioIntensities(
            current={},
            horizon_2030={"flood": 0.1},
            horizon_2050={"flood": 0.2},
        )
