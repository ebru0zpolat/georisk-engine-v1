"""Tests for the real-data hazard → EAL five-layer pipeline.

Covers the Open-Meteo derivations, the sealed-snapshot fail-closed invariants,
the injectable Hazard layer, and the end-to-end run over real BAG assets with a
labelled synthetic fixture snapshot.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.connectors.open_meteo import (
    HOT_DAY_THRESHOLD_C,
    elevation_from_payload,
    heat_climatology_from_archive,
)
from app.hazards.flood import FloodHazardModule
from app.nl_pilot.hazard_fixture import synthetic_fixture_snapshot
from app.nl_pilot.hazard_snapshot import (
    DEFAULT_SNAPSHOT_ID,
    HazardSnapshotHashMismatch,
    HazardSnapshotMissing,
    HazardSnapshotPointMissing,
    SealedHazardSnapshot,
    build_derived_snapshot,
    load_sealed_hazard_snapshot,
    seal_snapshot_to_disk,
)
from app.nl_pilot.real_assets import load_pilot_assets
from app.nl_pilot.real_five_layer import (
    indicative_asset_value_eur,
    map_gebruiksdoel,
    run_real_five_layer,
)
from app.schemas.five_layer import HazardComponent, HazardLayer
from app.schemas.portfolio import UniversalAsset
from app.services.audit_trail import AppendOnlyAuditTrail
from app.services.five_layer_pipeline import run_five_layer


# --------------------------------------------------------------------------
# Open-Meteo derivations
# --------------------------------------------------------------------------


def _archive(tmax: list[float]) -> dict:
    times = [f"2020-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(len(tmax))]
    return {"latitude": 52.37, "longitude": 4.88, "daily": {"time": times, "temperature_2m_max": tmax}}


def test_heat_climatology_basic_bounds():
    stat = heat_climatology_from_archive(_archive([10.0, 20.0, 25.0, 31.0, 35.0]))
    assert stat.p95_tmax_c <= stat.record_tmax_c == 35.0
    assert stat.mean_annual_hot_days > 0  # 31 and 35 exceed the 30°C threshold
    assert stat.sample_days == 5
    assert HOT_DAY_THRESHOLD_C == 30.0


def test_heat_climatology_monotonic_p95():
    cool = heat_climatology_from_archive(_archive([18.0, 20.0, 22.0, 24.0, 26.0]))
    hot = heat_climatology_from_archive(_archive([28.0, 30.0, 32.0, 34.0, 40.0]))
    assert hot.p95_tmax_c > cool.p95_tmax_c


def test_heat_climatology_ignores_nulls_and_empty_raises():
    stat = heat_climatology_from_archive(
        {"latitude": 1, "longitude": 2, "daily": {"time": ["2020-01-01", "2020-01-02"], "temperature_2m_max": [None, 33.0]}}
    )
    assert stat.sample_days == 1
    with pytest.raises(ValueError):
        heat_climatology_from_archive({"latitude": 1, "longitude": 2, "daily": {"time": [], "temperature_2m_max": []}})


def test_elevation_parse_and_null_fail_closed():
    pt = elevation_from_payload({"elevation": [-1.5]}, latitude=52.37, longitude=4.88)
    assert pt.elevation_m == -1.5
    with pytest.raises(ValueError):
        elevation_from_payload({"elevation": [None]}, latitude=1, longitude=2)
    with pytest.raises(ValueError):
        elevation_from_payload({}, latitude=1, longitude=2)


# --------------------------------------------------------------------------
# Sealed snapshot — fail-closed invariants
# --------------------------------------------------------------------------


def _derived_two_points() -> dict:
    return build_derived_snapshot(
        snapshot_id=DEFAULT_SNAPSHOT_ID,
        heat_source={"method_version": "test"},
        heat_points=[
            {"latitude": 52.10000, "longitude": 4.10000, "p95_tmax_c": 28.0},
            {"latitude": 52.20000, "longitude": 4.20000, "p95_tmax_c": 33.0},
        ],
        elevation_source={"method_version": "test"},
        elevation_points=[
            {"latitude": 52.10000, "longitude": 4.10000, "elevation_m": 8.0},
            {"latitude": 52.20000, "longitude": 4.20000, "elevation_m": -2.0},
        ],
        synthetic=True,
    )


def test_snapshot_missing_fail_closed(tmp_path):
    with pytest.raises(HazardSnapshotMissing):
        load_sealed_hazard_snapshot(tmp_path)


def test_snapshot_seal_reload_roundtrip_and_hash_mismatch(tmp_path):
    seal_snapshot_to_disk(_derived_two_points(), project_root=tmp_path)
    snap = load_sealed_hazard_snapshot(tmp_path)
    assert snap.synthetic is True
    assert snap.elevation_at(52.2, 4.2).value == -2.0

    # Tamper with the sealed file → hash mismatch fail-closed.
    snap_file = tmp_path / "data/nl_pilot/snapshots/hazard" / f"{DEFAULT_SNAPSHOT_ID}.json"
    data = json.loads(snap_file.read_text())
    data["elevation"]["points"][0]["elevation_m"] = 999.0
    snap_file.write_text(json.dumps(data, indent=2, sort_keys=True))
    with pytest.raises(HazardSnapshotHashMismatch):
        load_sealed_hazard_snapshot(tmp_path)


def test_snapshot_point_missing_fail_closed():
    snap = SealedHazardSnapshot.from_derived_dict(_derived_two_points())
    with pytest.raises(HazardSnapshotPointMissing):
        snap.elevation_at(0.0, 0.0)
    with pytest.raises(HazardSnapshotPointMissing):
        snap.era5_temperature(0.0, 0.0, "2025-01-01")


def test_flood_lower_elevation_gives_higher_intensity():
    snap = SealedHazardSnapshot.from_derived_dict(_derived_two_points())
    module = FloodHazardModule(raster=snap)
    high = module.evaluate(latitude=52.1, longitude=4.1, valuation_date=date(2025, 1, 1))
    low = module.evaluate(latitude=52.2, longitude=4.2, valuation_date=date(2025, 1, 1))
    assert low.intensity >= high.intensity
    assert low.metadata["elevation_m"] == -2.0


# --------------------------------------------------------------------------
# Injectable hazard layer
# --------------------------------------------------------------------------


def test_run_five_layer_uses_injected_hazard():
    asset = UniversalAsset(
        asset_id="INJ-1",
        latitude=52.37,
        longitude=4.88,
        asset_value=1_000_000.0,
        building_type="office",
        use_class="commercial",
    )
    injected = HazardLayer(
        components=[
            HazardComponent(hazard_id="flood", intensity=0.9),
            HazardComponent(hazard_id="extreme_heat", intensity=0.5),
        ],
        composite_intensity=0.7,
        data_versions={"hazard_basis": "test_injected"},
    )
    result = run_five_layer(
        asset, date(2025, 1, 1), trail=AppendOnlyAuditTrail(), hazard=injected
    )
    assert result.hazard.composite_intensity == 0.7
    assert result.hazard.data_versions["hazard_basis"] == "test_injected"
    assert result.financial.eal_absolute > 0
    assert result.audit_record_id != "pending"


# --------------------------------------------------------------------------
# Mapping helpers
# --------------------------------------------------------------------------


def test_gebruiksdoel_mapping_and_value_basis():
    assert map_gebruiksdoel("winkelfunctie") == ("retail", "commercial_retail")
    assert map_gebruiksdoel("kantoorfunctie")[0] == "office"
    assert map_gebruiksdoel("unknown-doel") == ("office", "unknown")
    assert indicative_asset_value_eur("retail", 100.0) == 350000.0


# --------------------------------------------------------------------------
# End-to-end over real BAG assets (fixture hazard snapshot)
# --------------------------------------------------------------------------


def test_end_to_end_real_assets_fixture_snapshot():
    assets = load_pilot_assets()
    derived = synthetic_fixture_snapshot(assets)
    snapshot = SealedHazardSnapshot.from_derived_dict(derived, artifact_sha256="fixture")

    bundle = run_real_five_layer(
        snapshot=snapshot, assets=assets, trail=AppendOnlyAuditTrail()
    )

    assert bundle["asset_count"] == len(assets) == 5
    assert bundle["honesty_labels"]["snapshot_kind"].startswith("SYNTHETIC")
    assert "REAL" in bundle["honesty_labels"]["hazard_layer"]
    assert bundle["portfolio_totals"]["total_eal_absolute_eur"] > 0

    for row in bundle["assets"]:
        assert row["eal_absolute"] > 0
        assert 0.0 <= row["hazard"]["flood_intensity"] <= 1.0
        assert 0.0 <= row["hazard"]["extreme_heat_intensity"] <= 1.0
        assert row["audit_record_id"] and row["audit_record_id"] != "pending"
        assert row["value_basis"] == "synthetic_indicative_value_eur_per_m2_v0.1"
