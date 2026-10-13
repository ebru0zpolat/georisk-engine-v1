"""Tests for expected-loss-v0.4 (opt-in hybrid depth/intensity)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

from app.loss.depth_damage_curves import load_depth_damage_catalogue
from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_V0_4,
    EXPECTED_LOSS_METHODOLOGY_VERSION,
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
    recompute_eal_from_trail_record,
)
from app.services.audit_trail import AppendOnlyAuditTrail

_ROOT = Path(__file__).resolve().parents[2]
_POWER = str(_ROOT / "app/loss/curves/stub_global_mdr_v0.1.json")
_DEPTH = str(_ROOT / "app/loss/curves/jrc_depth_damage_fixture_v0.1.json")


def _asset():
    return ExpectedLossAssetInput(
        asset_id="A1", asset_value=1_000_000.0, building_type="office",
        use_class="commercial", fragility_factor=0.6, adaptation_capacity_factor=0.0,
    )


def _hazards():
    return HazardScenarioIntensities(current={"flood": 0.9, "extreme_heat": 0.5})


def _run_v04(depth: float, trail):
    return compute_expected_loss(
        asset=_asset(), hazards=_hazards(), valuation_date=date(2025, 1, 1), trail=trail,
        methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4,
        depths={"flood": depth}, depth_catalogue=load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json"),
    )


def test_v04_prices_flood_from_depth_curve():
    res = _run_v04(3.0, AppendOnlyAuditTrail())
    assert res.methodology_version == EXPECTED_LOSS_METHODOLOGY_V0_4
    # commercial fixture curve at 3.0 m = 0.65; heat still via the power curve.
    assert res.mdr_by_hazard["flood"] == pytest.approx(0.65)
    assert res.curve_ids_by_hazard["flood"] == "fixture_commercial_flood"
    assert res.curve_ids_by_hazard["extreme_heat"].startswith("stub_mdr_")
    assert res.eal_absolute > 0


def test_v04_replay_parity():
    trail = AppendOnlyAuditTrail()
    res = _run_v04(3.0, trail)
    replay = recompute_eal_from_trail_record(trail.get(res.audit_record_id))
    assert replay["eal_absolute"] == res.eal_absolute
    assert replay["mdr_by_hazard"]["flood"] == pytest.approx(0.65)


def test_v04_independent_verifier_agreement():
    sys.path.insert(0, str(_ROOT / "tests"))
    from verification.independent_eal import eal_from_trail

    trail = AppendOnlyAuditTrail()
    res = _run_v04(3.0, trail)
    rec = trail.get(res.audit_record_id).model_dump(mode="json")
    indep = eal_from_trail(rec, _POWER, _DEPTH)
    assert round(indep["eal_absolute"], 2) == round(res.eal_absolute, 2)


def test_v04_dry_asset_zero_flood_mdr():
    res = _run_v04(0.0, AppendOnlyAuditTrail())
    assert res.mdr_by_hazard["flood"] == 0.0  # depth 0 → JRC damage 0


def test_v04_requires_depths_and_catalogue():
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    with pytest.raises(ValueError, match="requires a non-empty depths"):
        compute_expected_loss(
            asset=_asset(), hazards=_hazards(), valuation_date=date(2025, 1, 1),
            trail=AppendOnlyAuditTrail(), methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4,
            depths=None, depth_catalogue=cat,
        )
    with pytest.raises(ValueError, match="requires a depth_catalogue"):
        compute_expected_loss(
            asset=_asset(), hazards=_hazards(), valuation_date=date(2025, 1, 1),
            trail=AppendOnlyAuditTrail(), methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4,
            depths={"flood": 1.0}, depth_catalogue=None,
        )


def test_v03_default_unchanged_and_stamped():
    res = compute_expected_loss(
        asset=_asset(), hazards=_hazards(), valuation_date=date(2025, 1, 1),
        trail=AppendOnlyAuditTrail(),
    )
    assert res.methodology_version == EXPECTED_LOSS_METHODOLOGY_VERSION == "expected-loss-v0.3"
    # Default path never touches depth curves.
    assert res.curve_ids_by_hazard["flood"].startswith("stub_mdr_")


def test_v04_non_depth_hazard_matches_power_curve():
    """Heat (no depth) keeps its v0.3 power-curve MDR under v0.4."""
    v04 = _run_v04(3.0, AppendOnlyAuditTrail())
    v03 = compute_expected_loss(
        asset=_asset(), hazards=_hazards(), valuation_date=date(2025, 1, 1),
        trail=AppendOnlyAuditTrail(),
    )
    assert v04.mdr_by_hazard["extreme_heat"] == pytest.approx(v03.mdr_by_hazard["extreme_heat"])
