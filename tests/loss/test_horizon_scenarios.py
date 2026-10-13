"""Tests for forward-horizon scenario intensities + scenario_eal wiring."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from app.loss.expected_loss import (
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.loss.horizon_scenarios import (
    HorizonScenarioCatalogue,
    HorizonUplift,
    load_horizon_scenario_catalogue,
    load_horizon_scenario_from_path,
)

_PROJ_ROOT = Path(__file__).resolve().parents[2]
from app.services.audit_trail import AppendOnlyAuditTrail

_FIXTURE = "horizon_scenario_fixture_v0.1.json"


def _cat(populated=True, synthetic=True):
    return HorizonScenarioCatalogue(
        catalogue_id="t", version="0", scenario="S", source="s",
        synthetic=synthetic, populated=populated,
        uplifts=[
            HorizonUplift(hazard_id="flood", horizon="2030", factor=1.1),
            HorizonUplift(hazard_id="flood", horizon="2050", factor=1.5),
        ],
    )


def test_project_multiplies_and_clamps():
    c = _cat()
    assert c.project("flood", 0.4, "2030") == pytest.approx(0.44)
    assert c.project("flood", 0.8, "2050") == 1.0  # 0.8*1.5=1.2 clamped


def test_build_horizon_maps_both():
    h30, h50 = _cat().build_horizon_maps({"flood": 0.4})
    assert h30["flood"] == pytest.approx(0.44)
    assert h50["flood"] == pytest.approx(0.6)


def test_fail_closed_when_unpopulated():
    with pytest.raises(ValueError, match="UNPOPULATED_FAIL_CLOSED"):
        _cat(populated=False).project("flood", 0.4, "2030")


def test_unknown_hazard_or_horizon_raises():
    with pytest.raises(ValueError, match="no uplift factor"):
        _cat().project("extreme_heat", 0.4, "2030")


def test_horizon_validation():
    with pytest.raises(ValueError):
        HorizonUplift(hazard_id="flood", horizon="2100", factor=1.0)


def test_rejects_non_finite_factor():
    with pytest.raises(ValueError, match="finite"):
        HorizonUplift(hazard_id="flood", horizon="2030", factor=float("inf"))


def test_rejects_duplicate_hazard_horizon():
    with pytest.raises(ValueError, match="duplicate uplift"):
        HorizonScenarioCatalogue(
            catalogue_id="t", version="0", scenario="S", source="s",
            synthetic=False, populated=True,
            uplifts=[
                HorizonUplift(hazard_id="flood", horizon="2030", factor=1.1),
                HorizonUplift(hazard_id="Flood", horizon="2030", factor=1.2),  # dup (case)
            ],
        )


def _write_real_catalogue(tmp_path: Path, *, tamper: bool = False, sidecar: bool = True) -> Path:
    obj = {
        "catalogue_id": "horizon_scenario", "version": "1.0", "scenario": "SSP2-4.5",
        "source": "CMIP6 test", "synthetic": False, "populated": True,
        "uplifts": [{"hazard_id": "flood", "horizon": "2030", "factor": 1.1},
                    {"hazard_id": "flood", "horizon": "2050", "factor": 1.3}],
    }
    raw = json.dumps(obj, indent=2, ensure_ascii=True).encode("utf-8")
    cat = tmp_path / "horizon_scenario_v1.0.json"
    cat.write_bytes(raw)
    if sidecar:
        digest = hashlib.sha256(raw if not tamper else raw + b" ").hexdigest()
        (tmp_path / "horizon_scenario_v1.0.provenance.json").write_text(
            json.dumps({"artifact_sha256": digest})
        )
    return cat


def test_real_catalogue_verifies_provenance(tmp_path):
    cat = _write_real_catalogue(tmp_path)
    loaded = load_horizon_scenario_from_path(cat)  # matching sidecar → loads
    assert loaded.synthetic is False


def test_real_catalogue_missing_provenance_fail_closed(tmp_path):
    cat = _write_real_catalogue(tmp_path, sidecar=False)
    with pytest.raises(ValueError, match="no provenance sidecar"):
        load_horizon_scenario_from_path(cat)


def test_real_catalogue_tampered_provenance_fail_closed(tmp_path):
    cat = _write_real_catalogue(tmp_path, tamper=True)
    with pytest.raises(ValueError, match="does not match its provenance"):
        load_horizon_scenario_from_path(cat)


def _load_vendor():
    spec = importlib.util.spec_from_file_location(
        "vendor_hs", _PROJ_ROOT / "scripts" / "vendor_horizon_scenarios.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendor_rejects_incomplete_horizons(tmp_path, monkeypatch):
    vendor = _load_vendor()
    monkeypatch.setattr(vendor, "_CURVES_DIR", tmp_path)
    csv_path = tmp_path / "f.csv"
    csv_path.write_text("hazard_id,horizon,factor\nflood,2030,1.1\n")  # missing 2050
    monkeypatch.setattr(
        "sys.argv",
        ["vendor", "--from-csv", str(csv_path), "--scenario", "S", "--source", "src"],
    )
    with pytest.raises(SystemExit):
        vendor.main()


def test_fixture_loads_and_is_labelled_synthetic():
    cat = load_horizon_scenario_catalogue(_FIXTURE)
    assert cat.synthetic is True and cat.populated is True
    assert cat.project("extreme_heat", 0.5, "2050") == pytest.approx(min(1.0, 0.5 * 1.35))


def test_end_to_end_scenario_eal_monotonic():
    cat = load_horizon_scenario_catalogue(_FIXTURE)
    current = {"flood": 0.5, "extreme_heat": 0.4}
    h30, h50 = cat.build_horizon_maps(current)
    hazards = HazardScenarioIntensities(current=current, horizon_2030=h30, horizon_2050=h50)
    asset = ExpectedLossAssetInput(
        asset_id="A", asset_value=1_000_000.0, building_type="office",
        use_class="commercial", fragility_factor=0.6,
    )
    res = compute_expected_loss(
        asset=asset, hazards=hazards, valuation_date=date(2025, 1, 1),
        trail=AppendOnlyAuditTrail(),
    )
    assert set(res.scenario_eal) == {"2030", "2050"}
    # Uplift factors > 1 → rising intensities → rising EAL across horizons.
    assert res.scenario_eal["2050"] >= res.scenario_eal["2030"] >= res.eal_absolute
