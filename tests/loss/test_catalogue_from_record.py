"""Replay must use the record's catalogue — never the current default."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loss.damage_curves import load_catalogue, load_catalogue_from_path
from app.loss.expected_loss import (
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
    recompute_eal_from_trail_record,
)
from app.services.audit_trail import reset_audit_trail_for_tests


def test_replay_uses_record_catalogue_even_if_default_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trail = reset_audit_trail_for_tests(tmp_path / "trail.jsonl")
    cat_a = load_catalogue()
    result = compute_expected_loss(
        asset=ExpectedLossAssetInput(
            asset_id="cat-a",
            asset_value=1_000_000.0,
            building_type="hotel",
            use_class="tourism",
        ),
        hazards=HazardScenarioIntensities(
            current={"flood": 0.4},
            horizon_2030={"flood": 0.5},
            horizon_2050={"flood": 0.6},
        ),
        valuation_date=date(2024, 12, 31),
        trail=trail,
        timestamp=datetime(2024, 12, 31, 12, 0, tzinfo=timezone.utc),
        catalogue=cat_a,
    )
    record = trail.get(result.audit_record_id)
    assert record is not None
    assert record.parameters["catalogue_id"] == cat_a.catalogue_id
    assert record.parameters["catalogue_version"] == cat_a.version

    # Point the default loader at a missing file so silent default use would fail.
    monkeypatch.setattr(
        "app.loss.expected_loss.load_catalogue",
        lambda filename="x": (_ for _ in ()).throw(RuntimeError("default catalogue must not be used")),
    )

    recomputed = recompute_eal_from_trail_record(record)
    assert recomputed["eal_absolute"] == result.eal_absolute
    assert recomputed["catalogue_id"] == cat_a.catalogue_id
    assert recomputed["catalogue_version"] == cat_a.version


def test_replay_missing_catalogue_params_raises(tmp_path: Path) -> None:
    trail = reset_audit_trail_for_tests(tmp_path / "trail.jsonl")
    result = compute_expected_loss(
        asset=ExpectedLossAssetInput(
            asset_id="x",
            asset_value=1000.0,
            building_type="office",
            use_class="commercial",
        ),
        hazards=HazardScenarioIntensities(
            current={"flood": 0.2},
            horizon_2030={"flood": 0.3},
            horizon_2050={"flood": 0.4},
        ),
        valuation_date=date(2024, 12, 31),
        trail=trail,
        catalogue=load_catalogue_from_path(
            Path("app/loss/curves/stub_global_mdr_v0.1.json")
        ),
    )
    record = trail.get(result.audit_record_id)
    assert record is not None
    record.parameters.pop("catalogue_id", None)
    with pytest.raises(ValueError, match="catalogue_id"):
        recompute_eal_from_trail_record(record)
