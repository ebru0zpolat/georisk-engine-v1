"""Acceptance: EAL must recompute exactly from the file-backed audit trail alone."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loss.expected_loss import (
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
    recompute_eal_from_trail_record,
)
from app.services.audit_trail import (
    AppendOnlyAuditTrail,
    reset_audit_trail_for_tests,
)


@pytest.fixture()
def file_trail(tmp_path: Path) -> AppendOnlyAuditTrail:
    path = tmp_path / "expected_loss.jsonl"
    return reset_audit_trail_for_tests(path)


def _sample_asset() -> ExpectedLossAssetInput:
    return ExpectedLossAssetInput(
        asset_id="asset-antalya-001",
        asset_value=2_500_000.0,
        building_type="hotel",
        use_class="tourism",
        fragility_factor=1.0,
        adaptation_capacity_factor=0.1,
        insurance_coverage=1_000_000.0,
    )


def _sample_hazards(*, as_of: date | None = date(2024, 6, 1)) -> HazardScenarioIntensities:
    return HazardScenarioIntensities(
        current={"flood": 0.55, "extreme_heat": 0.40},
        horizon_2030={"flood": 0.62, "extreme_heat": 0.48},
        horizon_2050={"flood": 0.74, "extreme_heat": 0.60},
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
        as_of=as_of,
    )


def test_compute_writes_file_backed_trail_before_return(file_trail: AppendOnlyAuditTrail) -> None:
    assert file_trail.path is not None
    assert not file_trail.path.exists()

    result = compute_expected_loss(
        asset=_sample_asset(),
        hazards=_sample_hazards(),
        valuation_date=date(2024, 12, 31),
        trail=file_trail,
        timestamp=datetime(2024, 12, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert file_trail.path.is_file()
    assert result.audit_record_id
    stored = file_trail.get(result.audit_record_id)
    assert stored is not None
    assert file_trail.verify_chain()
    # File must contain the record (not memory-only).
    lines = file_trail.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert result.audit_record_id in lines[0]


def test_recompute_eal_from_trail_exact_equality(file_trail: AppendOnlyAuditTrail) -> None:
    result = compute_expected_loss(
        asset=_sample_asset(),
        hazards=_sample_hazards(),
        valuation_date=date(2024, 12, 31),
        trail=file_trail,
        timestamp=datetime(2024, 12, 31, 12, 0, tzinfo=timezone.utc),
    )
    record = file_trail.get(result.audit_record_id)
    assert record is not None

    # Reload from disk into a fresh store — memory must not be required.
    reloaded = AppendOnlyAuditTrail(path=file_trail.path)
    disk_record = reloaded.get(result.audit_record_id)
    assert disk_record is not None

    recomputed = recompute_eal_from_trail_record(disk_record)
    assert recomputed["eal_absolute"] == result.eal_absolute
    assert recomputed["eal_pct_of_value"] == result.eal_pct_of_value
    assert recomputed["eal_by_hazard"] == result.eal_by_hazard
    assert recomputed["mdr_by_hazard"] == result.mdr_by_hazard
    assert recomputed["curve_ids_by_hazard"] == result.curve_ids_by_hazard
    assert recomputed["scenario_eal"] == result.scenario_eal
    assert recomputed["risk_score"] == result.risk_score
    assert recomputed["collateral_sensitivity"] == result.collateral_sensitivity
    assert recomputed["insurability"] == result.insurability


def test_scenario_deltas_use_hazard_horizon_outputs(file_trail: AppendOnlyAuditTrail) -> None:
    hazards = _sample_hazards()
    result = compute_expected_loss(
        asset=_sample_asset(),
        hazards=hazards,
        valuation_date=date(2024, 12, 31),
        trail=file_trail,
    )
    assert result.scenario_eal["2030"] != result.eal_absolute
    assert result.scenario_eal["2050"] > result.scenario_eal["2030"]
    # Stronger 2050 intensities from hazard outputs → higher EAL than current.
    assert result.scenario_eal["2050"] > result.eal_absolute


def test_rejects_lookahead_hazard_as_of(file_trail: AppendOnlyAuditTrail) -> None:
    with pytest.raises(ValueError, match="look ahead"):
        compute_expected_loss(
            asset=_sample_asset(),
            hazards=_sample_hazards(as_of=date(2026, 1, 1)),
            valuation_date=date(2024, 12, 31),
            trail=file_trail,
        )


def test_eal_pct_and_per_hazard_present(file_trail: AppendOnlyAuditTrail) -> None:
    result = compute_expected_loss(
        asset=_sample_asset(),
        hazards=_sample_hazards(),
        valuation_date=date(2024, 12, 31),
        trail=file_trail,
    )
    assert result.eal_absolute > 0
    assert result.eal_pct_of_value == pytest.approx(
        (result.eal_absolute / 2_500_000.0) * 100.0, rel=0, abs=1e-6
    )
    assert set(result.eal_by_hazard) == {"flood", "extreme_heat"}
    assert all(cid.startswith("stub_") for cid in result.curve_ids_by_hazard.values())
