"""Tests for the return-period flood-hazard map + reference-level wiring."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from app.loss.depth_damage_curves import load_depth_damage_catalogue
from app.loss.flood_depth import (
    DEFAULT_REFERENCE_LEVEL_M,
    REFERENCE_LEVEL_BASIS,
    ElevationProfile,
    flood_damage_fraction,
    resolve_reference_level,
)
from app.loss.flood_hazard_map import (
    FloodHazardMap,
    ReturnPeriodWaterLevel,
    load_flood_hazard_map,
    load_flood_hazard_map_from_path,
)

_PROJ_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = "flood_hazard_map_fixture_v0.1.json"
_JRC_FIXTURE = "jrc_depth_damage_fixture_v0.1.json"

# One pilot asset (cell 52.38,4.88) and the outlier (cell 52.37,4.92).
_LAT_A, _LON_A = 52.3782, 4.8835
_LAT_B, _LON_B = 52.3698, 4.9247


def _nap_profile(**over) -> ElevationProfile:
    """A labelled synthetic NAP ground elevation, differenceable with the NAP map."""
    base = dict(
        vertical_datum="NAP", units="m", horizontal_crs="EPSG:4326",
        source="SYNTHETIC_NAP_ELEVATION", version="0.1",
        transformation="none_required", resolution="point", synthetic=True,
    )
    base.update(over)
    return ElevationProfile(**base)


def _map(populated=True, synthetic=True):
    return FloodHazardMap(
        map_id="t", version="0", source="s", synthetic=synthetic, populated=populated,
        levels=[
            ReturnPeriodWaterLevel(cell_id="52.38,4.88", return_period_years=10, water_level_m=0.5),
            ReturnPeriodWaterLevel(cell_id="52.38,4.88", return_period_years=100, water_level_m=1.5),
        ],
    )


def test_fixture_loads_labelled_synthetic_and_covers_pilot_cells():
    m = load_flood_hazard_map(_FIXTURE)
    assert m.synthetic is True and m.populated is True and m.datum == "NAP"
    assert m.available_return_periods() == [10, 100, 1000]
    assert m.reference_level_at(_LAT_A, _LON_A, 100) == 1.5   # cell 52.38,4.88
    assert m.reference_level_at(_LAT_B, _LON_B, 100) == 1.3   # cell 52.37,4.92


def test_reference_level_rises_with_return_period():
    m = load_flood_hazard_map(_FIXTURE)
    lvls = [m.reference_level_at(_LAT_A, _LON_A, rp) for rp in (10, 100, 1000)]
    assert lvls == sorted(lvls) and lvls[0] < lvls[-1]


def test_cell_rounding_snaps_nearby_points_to_same_cell():
    m = load_flood_hazard_map(_FIXTURE)
    # All four clustered pilot assets fall in cell 52.38,4.88.
    for lat, lon in ((52.3782, 4.8835), (52.3781, 4.8836), (52.378, 4.8834), (52.3779, 4.8835)):
        assert m.reference_level_at(lat, lon, 100) == 1.5


def test_fail_closed_when_unpopulated():
    with pytest.raises(ValueError, match="UNPOPULATED_FAIL_CLOSED"):
        _map(populated=False).reference_level_at(_LAT_A, _LON_A, 100)


def test_uncovered_cell_fails_closed():
    with pytest.raises(ValueError, match="no water level for cell"):
        _map().reference_level_at(0.0, 0.0, 100)


def test_unknown_return_period_fails_closed():
    with pytest.raises(ValueError, match="no water level for cell"):
        _map().reference_level_at(_LAT_A, _LON_A, 250)


def test_rejects_duplicate_cell_return_period():
    with pytest.raises(ValueError, match="duplicate water level"):
        FloodHazardMap(
            map_id="t", version="0", source="s", synthetic=False, populated=True,
            levels=[
                ReturnPeriodWaterLevel(cell_id="52.38,4.88", return_period_years=100, water_level_m=1.5),
                ReturnPeriodWaterLevel(cell_id="52.38,4.88", return_period_years=100, water_level_m=1.6),
            ],
        )


def test_rejects_non_finite_water_level():
    with pytest.raises(ValueError, match="finite"):
        ReturnPeriodWaterLevel(cell_id="c", return_period_years=100, water_level_m=float("nan"))


# --- provenance (non-synthetic) ----------------------------------------------

def _write_real_map(tmp_path: Path, *, tamper=False, sidecar=True) -> Path:
    obj = {
        "map_id": "flood_hazard_map", "version": "1.0", "source": "NL LIWO test",
        "datum": "NAP", "cell_size_deg": 0.01, "synthetic": False, "populated": True,
        "levels": [{"cell_id": "52.38,4.88", "return_period_years": 100, "water_level_m": 1.62}],
    }
    raw = json.dumps(obj, indent=2, ensure_ascii=True).encode("utf-8")
    p = tmp_path / "flood_hazard_map_v1.0.json"
    p.write_bytes(raw)
    if sidecar:
        digest = hashlib.sha256(raw if not tamper else raw + b" ").hexdigest()
        (tmp_path / "flood_hazard_map_v1.0.provenance.json").write_text(
            json.dumps({"artifact_sha256": digest})
        )
    return p


def test_real_map_verifies_provenance(tmp_path):
    m = load_flood_hazard_map_from_path(_write_real_map(tmp_path))
    assert m.synthetic is False and m.reference_level_at(_LAT_A, _LON_A, 100) == 1.62


def test_real_map_missing_provenance_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="no provenance sidecar"):
        load_flood_hazard_map_from_path(_write_real_map(tmp_path, sidecar=False))


def test_real_map_tampered_provenance_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="does not match its provenance"):
        load_flood_hazard_map_from_path(_write_real_map(tmp_path, tamper=True))


# --- flood_depth wiring ------------------------------------------------------

def test_resolve_reference_level_scalar_default():
    level, basis = resolve_reference_level()
    assert level == DEFAULT_REFERENCE_LEVEL_M and basis == REFERENCE_LEVEL_BASIS


def test_resolve_reference_level_from_map():
    m = load_flood_hazard_map(_FIXTURE)
    level, basis = resolve_reference_level(
        latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
        elevation_profile=_nap_profile(),
    )
    assert level == 1.5 and "flood_hazard_map_fixture-v0.1@T100" == basis


def test_resolve_reference_level_rejects_datum_mismatch():
    # A NAP flood level must never be differenced against an EGM2008 elevation.
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="FLOOD_DATUM_MISMATCH"):
        resolve_reference_level(
            latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
            elevation_profile=_nap_profile(vertical_datum="orthometric (EGM2008 geoid)"),
        )


def test_resolve_reference_level_rejects_missing_profile():
    # Omitting the elevation profile with a map is fail-closed, not an implicit match.
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="FLOOD_DATUM_MISMATCH"):
        resolve_reference_level(
            latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
        )


def test_resolve_reference_level_rejects_unit_mismatch():
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="units"):
        resolve_reference_level(
            latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
            elevation_profile=_nap_profile(units="ft"),
        )


def test_resolve_reference_level_rejects_depth_semantics():
    # An already-computed inundation depth must not be treated as a ground elevation.
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="value semantics"):
        resolve_reference_level(
            latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
            elevation_profile=_nap_profile(value_semantics="inundation_depth"),
        )


def test_resolve_reference_level_rejects_blank_transformation():
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="transformation"):
        resolve_reference_level(
            latitude=_LAT_A, longitude=_LON_A, return_period_years=100, reference_map=m,
            elevation_profile=_nap_profile(transformation="  "),
        )


def test_flood_damage_fraction_uses_map_level():
    cat = load_depth_damage_catalogue(_JRC_FIXTURE)
    ground = -1.0  # 1 m below NAP
    # Scalar path: depth = 1.0 - (-1.0) = 2.0
    d_scalar, _, _ = flood_damage_fraction(
        ground_elevation_m=ground, building_type="residential", catalogue=cat
    )
    # Map path at T100 (water 1.5): depth = 1.5 - (-1.0) = 2.5
    m = load_flood_hazard_map(_FIXTURE)
    d_map, ratio, _ = flood_damage_fraction(
        ground_elevation_m=ground, building_type="residential", catalogue=cat,
        reference_map=m, latitude=_LAT_A, longitude=_LON_A, return_period_years=100,
        elevation_profile=_nap_profile(), data_versions={},
    )
    assert d_scalar == pytest.approx(2.0)
    assert d_map == pytest.approx(2.5) and d_map > d_scalar
    assert 0.0 <= ratio <= 1.0


def test_flood_damage_fraction_rejects_datum_mismatch():
    cat = load_depth_damage_catalogue(_JRC_FIXTURE)
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="FLOOD_DATUM_MISMATCH"):
        flood_damage_fraction(
            ground_elevation_m=-1.0, building_type="residential", catalogue=cat,
            reference_map=m, latitude=_LAT_A, longitude=_LON_A, return_period_years=100,
            elevation_profile=_nap_profile(vertical_datum="orthometric (EGM2008 geoid)"),
            data_versions={},
        )


def test_flood_damage_fraction_requires_provenance_collector():
    # The map path must never run without a collector — that would lose the evidence.
    cat = load_depth_damage_catalogue(_JRC_FIXTURE)
    m = load_flood_hazard_map(_FIXTURE)
    with pytest.raises(ValueError, match="provenance is mandatory"):
        flood_damage_fraction(
            ground_elevation_m=-1.0, building_type="residential", catalogue=cat,
            reference_map=m, latitude=_LAT_A, longitude=_LON_A, return_period_years=100,
            elevation_profile=_nap_profile(),
        )


def test_flood_damage_fraction_stamps_full_provenance_into_data_versions():
    # The audit record must tell a synthetic fixture from a real map and name the
    # map, checksum, cell, return period, datum and elevation source (Codex P1).
    cat = load_depth_damage_catalogue(_JRC_FIXTURE)
    m = load_flood_hazard_map(_FIXTURE)
    data_versions: dict = {}
    flood_damage_fraction(
        ground_elevation_m=-1.0, building_type="residential", catalogue=cat,
        reference_map=m, latitude=_LAT_A, longitude=_LON_A, return_period_years=100,
        elevation_profile=_nap_profile(), data_versions=data_versions,
    )
    assert data_versions["flood_map"] == "flood_hazard_map_fixture-v0.1"
    assert data_versions["flood_map_synthetic"] is True
    assert data_versions["flood_map_source_type"] == "synthetic"
    assert data_versions["flood_map_datum"] == "NAP"
    assert data_versions["flood_cell_id"] == "52.38,4.88"
    assert data_versions["flood_return_period_years"] == 100
    assert len(data_versions["flood_map_sha256"]) == 64  # sealed fixture bytes
    assert data_versions["flood_elevation_source"] == "SYNTHETIC_NAP_ELEVATION"
    assert data_versions["flood_elevation_synthetic"] is True


def test_scalar_path_does_not_stamp_flood_provenance():
    # Without a map there is no flood-map identity to stamp; leave data_versions alone.
    cat = load_depth_damage_catalogue(_JRC_FIXTURE)
    data_versions: dict = {"existing": "kept"}
    flood_damage_fraction(
        ground_elevation_m=-1.0, building_type="residential", catalogue=cat,
        data_versions=data_versions,
    )
    assert data_versions == {"existing": "kept"}


def test_provenance_stamp_reflects_real_map():
    m = FloodHazardMap(
        map_id="flood_hazard_map", version="1.0", source="NL LIWO", datum="NAP",
        synthetic=False, populated=True,
        levels=[ReturnPeriodWaterLevel(cell_id="52.38,4.88", return_period_years=100, water_level_m=1.6)],
    )
    stamp = m.provenance_stamp("52.38,4.88", 100)
    assert stamp["flood_map"] == "flood_hazard_map-v1.0"
    assert stamp["flood_map_synthetic"] is False
    assert stamp["flood_map_source_type"] == "real"
    assert stamp["flood_map_datum"] == "NAP"
    assert stamp["flood_cell_id"] == "52.38,4.88"
    assert stamp["flood_return_period_years"] == 100
    # A map built directly in code was never sealed from bytes.
    assert stamp["flood_map_sha256"] == "unsealed"


def test_loaded_fixture_carries_artifact_checksum():
    m = load_flood_hazard_map(_FIXTURE)
    assert m.artifact_sha256 is not None and len(m.artifact_sha256) == 64


def test_index_serves_lookup_without_scanning_levels():
    # Lookups go through the (cell, return-period) index, not a scan of ``levels``.
    m = _map()
    m.levels.clear()  # if a scan were used this would break the lookup
    assert m.reference_level_at(_LAT_A, _LON_A, 100) == 1.5


# --- vendor ------------------------------------------------------------------

def _load_vendor():
    spec = importlib.util.spec_from_file_location(
        "vendor_fhm", _PROJ_ROOT / "scripts" / "vendor_flood_hazard_map.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendor_grids_points_and_rejects_duplicate_cells(tmp_path):
    vendor = _load_vendor()
    csv_path = tmp_path / "f.csv"
    # Two nearby points at T100 snap to the SAME 0.01-deg cell → duplicate, rejected.
    csv_path.write_text(
        "lat,lon,return_period_years,water_level_m\n"
        "52.3782,4.8835,100,1.6\n52.3781,4.8836,100,1.7\n"
    )
    with pytest.raises(SystemExit, match="duplicate"):
        vendor._read_csv(csv_path, cell_size=0.01)


def test_vendor_reads_valid_points(tmp_path):
    vendor = _load_vendor()
    csv_path = tmp_path / "f.csv"
    csv_path.write_text(
        "lat,lon,return_period_years,water_level_m\n"
        "52.3782,4.8835,100,1.6\n52.3698,4.9247,100,1.4\n"
    )
    rows = vendor._read_csv(csv_path, cell_size=0.01)
    assert {r["cell_id"] for r in rows} == {"52.38,4.88", "52.37,4.92"}
    assert rows[0]["water_level_m"] == 1.6
