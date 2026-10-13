"""Permanent guard: trail replay dispatches on record.methodology_version.

Create a v0.2 trail record, ship v0.3 as live, replay the v0.2 record → must
reproduce the stored v0.2 numbers exactly. This test must remain for every
future methodology bump (add another frozen version + case, never delete this).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loss.damage_curves import load_catalogue
from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_VERSION,
    EXPECTED_LOSS_METHODOLOGY_V0_2,
    FORMULAS,
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    _compute_core_v0_2,
    _compute_core_v0_3,
    formula_for_version,
    hazard_weights,
    recompute_eal_from_trail_record,
)
from app.services.audit_trail import reset_audit_trail_for_tests


def _diverging_fixture() -> tuple[ExpectedLossAssetInput, HazardScenarioIntensities, date]:
    """Inputs where v0.2 (uncapped sum) and v0.3 (union + hard cap) disagree."""
    asset = ExpectedLossAssetInput(
        asset_id="replay-v02",
        asset_value=1_000_000.0,
        building_type="hotel",
        use_class="tourism",
        fragility_factor=1.8,
        adaptation_capacity_factor=0.0,
    )
    hazards = HazardScenarioIntensities(
        current={"flood": 0.85, "extreme_heat": 0.80},
        horizon_2030={"flood": 0.80, "extreme_heat": 0.75},
        horizon_2050={"flood": 0.90, "extreme_heat": 0.85},
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
        as_of=date(2024, 6, 1),
    )
    return asset, hazards, date(2024, 12, 31)


def test_formulas_registry_has_v0_2_and_latest() -> None:
    assert EXPECTED_LOSS_METHODOLOGY_V0_2 in FORMULAS
    assert EXPECTED_LOSS_METHODOLOGY_VERSION in FORMULAS
    assert EXPECTED_LOSS_METHODOLOGY_VERSION == "expected-loss-v0.3"
    assert formula_for_version(EXPECTED_LOSS_METHODOLOGY_VERSION) is _compute_core_v0_3
    assert formula_for_version(EXPECTED_LOSS_METHODOLOGY_V0_2) is _compute_core_v0_2


def test_unknown_methodology_version_raises_explicit_error() -> None:
    with pytest.raises(ValueError, match="methodology expected-loss-v0.1 not in registry"):
        formula_for_version("expected-loss-v0.1")


def test_v0_2_trail_record_replays_exactly_under_v0_3_codebase(tmp_path: Path) -> None:
    """Permanent: v0.2 numbers survive after v0.3 (and every later bump) ships."""
    trail = reset_audit_trail_for_tests(tmp_path / "trail.jsonl")
    catalogue = load_catalogue()
    asset, hazards, valuation_date = _diverging_fixture()

    v02_core = _compute_core_v0_2(
        asset=asset,
        hazards=hazards,
        valuation_date=valuation_date,
        catalogue=catalogue,
    )
    v03_core = _compute_core_v0_3(
        asset=asset,
        hazards=hazards,
        valuation_date=valuation_date,
        catalogue=catalogue,
    )
    # Fixture must keep the versions observably different — otherwise the test
    # cannot catch silent fallback to the live formula.
    assert v02_core["eal_absolute"] != v03_core["eal_absolute"]
    assert v02_core["eal_absolute"] > asset.asset_value  # v0.2 uncapped
    assert v03_core["eal_absolute"] <= asset.asset_value  # v0.3 hard cap
    # Historical v0.2 live path stored attribution_weights (not attribution_share).
    expected_weights = hazard_weights(hazards.current)
    assert expected_weights
    assert v02_core["attribution_weights"] == expected_weights
    assert "attribution_share" not in v02_core

    record = trail.append(
        methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_2,
        valuation_date=valuation_date,
        data_versions={
            "damage_curves": v02_core["damage_curves_version"],
            **dict(hazards.data_versions or {}),
        },
        parameters={
            "horizons": ["2030", "2050"],
            "catalogue_id": catalogue.catalogue_id,
            "catalogue_version": catalogue.version,
            "catalogue_source": catalogue.source,
        },
        inputs={
            "asset": asset.model_dump(mode="json"),
            "hazards": hazards.model_dump(mode="json"),
        },
        outputs={
            "eal_absolute": v02_core["eal_absolute"],
            "eal_pct_of_value": v02_core["eal_pct_of_value"],
            "eal_by_hazard": v02_core["eal_by_hazard"],
            "mdr_by_hazard": v02_core["mdr_by_hazard"],
            "curve_ids_by_hazard": v02_core["curve_ids_by_hazard"],
            "attribution_weights": expected_weights,
            "scenario_eal": v02_core["scenario_eal"],
            "risk_score": v02_core["risk_score"],
            "collateral_sensitivity": v02_core["collateral_sensitivity"],
            "insurability": v02_core["insurability"],
        },
        timestamp=datetime(2024, 12, 31, 15, 0, tzinfo=timezone.utc),
    )

    recomputed = recompute_eal_from_trail_record(record)
    assert recomputed["methodology_version"] == EXPECTED_LOSS_METHODOLOGY_V0_2
    assert recomputed["eal_absolute"] == record.outputs["eal_absolute"]
    assert recomputed["eal_absolute"] == v02_core["eal_absolute"]
    assert recomputed["eal_pct_of_value"] == record.outputs["eal_pct_of_value"]
    assert recomputed["eal_by_hazard"] == record.outputs["eal_by_hazard"]
    assert recomputed["mdr_by_hazard"] == record.outputs["mdr_by_hazard"]
    assert recomputed["scenario_eal"] == record.outputs["scenario_eal"]
    assert recomputed["risk_score"] == record.outputs["risk_score"]
    assert recomputed["collateral_sensitivity"] == record.outputs["collateral_sensitivity"]
    assert recomputed["insurability"] == record.outputs["insurability"]
    assert recomputed["attribution_weights"] == record.outputs["attribution_weights"]
    assert recomputed["attribution_weights"] == expected_weights
    # Must not silently apply v0.3 naming or formula.
    assert recomputed["eal_absolute"] != v03_core["eal_absolute"]
    assert "combined_mdr" not in recomputed
    assert "attribution_share" not in recomputed


def test_replay_unknown_methodology_on_trail_record(tmp_path: Path) -> None:
    trail = reset_audit_trail_for_tests(tmp_path / "trail.jsonl")
    catalogue = load_catalogue()
    asset, hazards, valuation_date = _diverging_fixture()
    record = trail.append(
        methodology_version="expected-loss-v0.1",
        valuation_date=valuation_date,
        data_versions={"damage_curves": catalogue.methodology_artifact_id},
        parameters={
            "catalogue_id": catalogue.catalogue_id,
            "catalogue_version": catalogue.version,
        },
        inputs={
            "asset": asset.model_dump(mode="json"),
            "hazards": hazards.model_dump(mode="json"),
        },
        outputs={"eal_absolute": 1.0},
    )
    with pytest.raises(ValueError, match="methodology expected-loss-v0.1 not in registry"):
        recompute_eal_from_trail_record(record)
