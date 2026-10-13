"""Tests for the İsdemir marine-context validation script.

Covers the offline evidence record (checksums, artifacts) and the live-mode
credential guard. Live ORAS5 fetching itself is exercised by the connector
tests with synthetic stores; this module must never require network or secrets.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pytest

from app.core.config import settings

# Importing the script must not load .env.local (only direct CLI runs do).
from scripts.validate_isdemir_marine import (  # noqa: E402
    _nearest_ocean_cell,
    _series_quality,
    build_record,
    expected_fixture_grid_index,
    main,
)


def _payload_kwargs() -> dict:
    return {
        "live": False,
        "payload": _payload(),
        "generated_at": datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc),
    }


def _payload():
    return _v1_payload()


def _v1_payload():
    from app.connectors.cds_oras5 import Oras5PointRequest

    # Locked v1 declaration point (36.725833, 36.186111) — tests are bound to
    # this exact coordinate, not the rounded 36.7333/36.2.
    return Oras5PointRequest(latitude=36.725833, longitude=36.186111)


def test_offline_record_has_checksums_and_stub_features() -> None:
    record = build_record(**_payload_kwargs())
    assert record["mode"] == "offline"
    assert record["validation_id"].startswith("ISD-MARINE-")
    assert record["features"] == {
        "sst_trend_c_per_decade": 0.21,
        "sst_anomaly_zscore": 1.4,
        "sea_level_trend_mm_per_year": 3.1,
        "ocean_variability_index": 0.58,
    }
    assert record["verified_live_grid_index"] is None
    assert record["verified_live_ocean_neighbour"] is None
    assert record["live_fixture_match"] is None
    assert record["run_status"] == "offline_stub"
    assert record["gate_failures"] == []
    assert record["expected_fixture_grid_index"] == _v1_fixture()
    assert record["expected_fixture_ocean_neighbour"] == _V1_OCEAN_NEIGHBOUR
    # Declaration SHA-256 carried verbatim (v1 file untouched, external).
    assert record["declaration"] == {
        "id": "isdemir-v1",
        "point": {"latitude": 36.725833, "longitude": 36.186111},
        "sha256": _V1_DECLARATION_SHA256,
        "note": "immutable v1 declaration (external file, not in repo); sha256 carried verbatim",
    }
    # Canonical gate split is present in every record.
    assert record["evidence_classification"]["real_asset_declaration"] == "passed"
    assert record["evidence_classification"]["fixture_coordinate_selection"] == "passed"
    assert record["evidence_classification"]["actual_oras5_grid_selection"] == "pending"
    assert record["evidence_classification"]["production_eligible"] is False
    for key in ("features_sha256", "record_sha256"):
        digest = record["checksums"][key]
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)
    # Record checksum is self-consistent: it is computed over the record with
    # the record_sha256 field blanked (self-referential by design).
    import hashlib

    without_self = dict(record)
    without_self["checksums"] = {**record["checksums"], "record_sha256": ""}
    recomputed = hashlib.sha256(
        json.dumps(without_self, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert recomputed == record["checksums"]["record_sha256"]


def test_live_record_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", None)
    kwargs = _payload_kwargs()
    kwargs["live"] = True
    with pytest.raises(SystemExit, match="CDSAPI_KEY"):
        build_record(**kwargs)


_V1_DECLARATION_SHA256 = "8bc533c23f77067e0c232df20d360bf5c0876c9a9c10555c12f353ad69579579"

_V1_OCEAN_NEIGHBOUR = {
    "selected_latitude_index": 507,
    "selected_longitude_index": 864,
    "selected_cell": {"latitude": 36.75, "longitude": 36.0},
    "snap_distance_km": 16.8005,
}


def _v1_fixture() -> dict:
    return {
        "selected_latitude_index": 507,
        "selected_longitude_index": 865,
        "selected_cell": {"latitude": 36.75, "longitude": 36.25},
        "snap_distance_km": 6.2955,
    }


def test_expected_fixture_grid_index_locked_to_v1_point() -> None:
    """Fixture pre-declaration for the locked v1 point (36.725833, 36.186111).

    The fixture is a regular-grid expectation — NOT NEMO tripolar proof. The
    v1 coordinate rounds to grid indices (507, 865) → cell (36.75, 36.25),
    snap 6.2955 km. A live record reads the store-array indices as
    ``verified_live_grid_index`` and never forces them onto this fixture.
    """
    sel = expected_fixture_grid_index(36.725833, 36.186111)
    assert sel == _v1_fixture()

    # The offline record carries the same fixture (pre-declared before any
    # live fetch) — bound to the exact v1 coordinate, plus the pre-declared
    # ocean neighbour (under the 20 km ocean-snap limit).
    record = build_record(**_payload_kwargs())
    assert record["expected_fixture_grid_index"] == _v1_fixture()
    assert record["expected_fixture_ocean_neighbour"] == _V1_OCEAN_NEIGHBOUR
    assert _V1_OCEAN_NEIGHBOUR["snap_distance_km"] < 20.0


def test_legacy_isdemir_coordinate_is_not_predeclared() -> None:
    """(36.7333, 36.2) is NOT the v1 declaration.

    Both coordinates round to the same geometric cell (507, 865) →
    (36.75, 36.25), but the declaration binds the exact v1 coordinate
    (36.725833, 36.186111); the legacy coordinate yields a different snap
    distance and must never be treated as pre-declared.
    """
    legacy = expected_fixture_grid_index(36.7333, 36.2)
    v1 = expected_fixture_grid_index(36.725833, 36.186111)
    # Same geometric cell after rounding…
    assert legacy["selected_latitude_index"] == v1["selected_latitude_index"] == 507
    assert legacy["selected_longitude_index"] == v1["selected_longitude_index"] == 865
    assert legacy["selected_cell"] == v1["selected_cell"]
    # …but a different declaration: the fixture dicts are not equal.
    assert legacy != v1
    assert legacy["snap_distance_km"] != v1["snap_distance_km"]

    # Every record declares only the exact v1 coordinate.
    record = build_record(**_payload_kwargs())
    assert (record["request"]["latitude"], record["request"]["longitude"]) == (
        36.725833,
        36.186111,
    )
    assert record["declaration"]["point"] == {"latitude": 36.725833, "longitude": 36.186111}


def test_live_match_is_controlled_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Matching store values → run_status=passed (happy path of the contract).

    The fixture values are aligned to what the synthetic store verifies (the
    analytic fixture correctness for the real v1 point is pinned separately);
    this test exercises the full live plumbing: verified_* fields, comparison
    result, declaration carry, classification, and finite features.
    """
    import numpy as np
    import pandas as pd
    import xarray as xr

    import scripts.validate_isdemir_marine as script

    from app.connectors.cds_oras5 import CDSOras5Connector

    times = pd.date_range("1995-01-01", periods=36, freq="MS")
    # 0.25° grid so the nearest cell (36.75, 36.25) is 6.3 km away — inside
    # the 20 km ocean-snap limit (a 0.5° grid would trip the limit by design).
    lats = np.arange(36.0, 37.25, 0.25)
    lons = np.arange(36.0, 37.25, 0.25)
    sst = (18.0 + 0.05 * np.arange(36))[:, None, None] + np.zeros((36, len(lats), len(lons)))
    ds = xr.Dataset(
        {
            "sosstsst": (("time", "latitude", "longitude"), sst),
            "sossheig": (("time", "latitude", "longitude"), np.zeros((36, len(lats), len(lons)))),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://match")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "uid:apikey")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))

    # Align the fixture with what this store will verify: nearest cell is
    # (lat 36.75, lon 36.25) = indices (3, 1) on this 0.25° store.
    snap = round(script._haversine_km(36.725833, 36.186111, 36.75, 36.25), 4)
    assert snap < 20.0
    fixture = {
        "selected_latitude_index": 3,
        "selected_longitude_index": 1,
        "selected_cell": {"latitude": 36.75, "longitude": 36.25},
        "snap_distance_km": snap,
    }
    monkeypatch.setattr(script, "expected_fixture_grid_index", lambda lat, lon: fixture)
    monkeypatch.setattr(script, "_EXPECTED_OCEAN_NEIGHBOUR", dict(fixture))

    kwargs = _payload_kwargs()
    kwargs["live"] = True
    record = build_record(**kwargs)

    assert record["run_status"] == "passed"
    assert record["gate_failures"] == []
    assert record["live_fixture_match"]["grid_index"] is True
    assert record["live_fixture_match"]["ocean_neighbour"] is True
    assert record["live_fixture_match"]["ocean_snap_max_km"] <= record["live_fixture_match"]["ocean_snap_limit_km"]
    assert record["verified_live_grid_index"]
    assert record["verified_live_ocean_neighbour"]
    assert record["declaration"]["sha256"] == _V1_DECLARATION_SHA256
    # A passing live run adds evidence but does NOT close the open gate.
    assert record["evidence_classification"]["actual_oras5_grid_selection"] == "pending"
    assert all(np.isfinite(v) for v in record["features"].values())


def test_live_mismatch_is_controlled_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture mismatch / ocean snap > 20 km → run_status=failed, observed kept.

    A synthetic store on a different (0.5°) grid can never match the v1
    fixture (507, 865) or the 20 km ocean-snap limit, so the record must be a
    controlled fail: observed values preserved, production_eligible=false,
    open gate failure record.
    """
    import numpy as np
    import pandas as pd
    import xarray as xr

    from app.connectors.cds_oras5 import CDSOras5Connector

    times = pd.date_range("1995-01-01", periods=36, freq="MS")
    lats = np.arange(36.0, 38.0, 0.5)
    lons = np.arange(36.0, 38.0, 0.5)
    sst = (18.0 + 0.05 * np.arange(36))[:, None, None] + np.zeros((36, len(lats), len(lons)))
    ds = xr.Dataset(
        {
            "sosstsst": (("time", "latitude", "longitude"), sst),
            "sossheig": (("time", "latitude", "longitude"), np.zeros((36, len(lats), len(lons)))),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://wrong-grid")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "uid:apikey")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))

    kwargs = _payload_kwargs()
    kwargs["live"] = True
    record = build_record(**kwargs)

    assert record["run_status"] == "failed"
    assert record["gate_failures"]
    assert any("grid" in f for f in record["gate_failures"])
    # Observed values preserved (never overwritten by the fixture).
    assert record["verified_live_grid_index"]
    assert record["verified_live_ocean_neighbour"]
    assert record["live_fixture_match"]["grid_index"] is False
    assert record["live_fixture_match"]["ocean_neighbour"] is False
    assert record["evidence_classification"]["production_eligible"] is False
    assert record["declaration"]["sha256"] == _V1_DECLARATION_SHA256


def _quality_series():
    import numpy as np
    import pandas as pd

    times = pd.date_range("1991-01-01", periods=36, freq="MS")
    return pd.Series(15.0 + 0.05 * np.arange(36), index=times)


def test_series_quality_retention_and_loss_pathway() -> None:
    from datetime import date

    sst = _quality_series()
    q = _series_quality(sst, date(1991, 1, 1), date(1993, 12, 31), kind="sst")
    assert q["expected_months"] == 36
    assert q["available"] == 36
    assert q["retention"] == 1.0
    assert q["loss_pathway"] == "missing_months_dropped; empty series yields zero features"

    # One dropped month → retention 35/36, still explicitly reported.
    dropped = sst.drop(index=sst.index[17])
    qd = _series_quality(dropped, date(1991, 1, 1), date(1993, 12, 31), kind="sst")
    assert qd["available"] == 35
    assert qd["retention"] == pytest.approx(35 / 36, abs=1e-4)


def test_series_quality_homogeneity_flags_jumps() -> None:
    from datetime import date

    jumpy = _quality_series().copy()
    jumpy.iloc[20] = 30.0
    q = _series_quality(jumpy, date(1991, 1, 1), date(1993, 12, 31), kind="sst")
    assert q["homogeneity"]["jump_count_gt_3sigma"] >= 1
    assert q["homogeneity"]["max_jump"] > 10
    assert q["scaling"]["unit_range_sane"] is True


def test_series_quality_empty_series() -> None:
    from datetime import date

    import pandas as pd

    empty = pd.Series(dtype=float)
    q = _series_quality(empty, date(1991, 1, 1), date(1993, 12, 31), kind="sst")
    assert q["available"] == 0
    assert q["retention"] == 0.0
    assert q["scaling"]["unit_range_sane"] is None
    assert q["homogeneity"]["max_jump"] == 0.0


def test_nearest_ocean_cell_skips_land_masked_cells() -> None:
    """Mask-aware selection: land-masked nearest cell is skipped.

    At the locked v1 point (36.725833, 36.186111) the raw nearest cell
    (36.75, 36.25) is land in ORAS5; the nearest valid cell is (36.75, 36.0)
    — 16.8005 km away.
    """
    import numpy as np
    import pandas as pd
    import xarray as xr

    times = pd.date_range("1995-01-01", periods=3, freq="MS")
    lats = np.arange(36.0, 37.5, 0.25)
    lons = np.arange(36.0, 37.5, 0.25)
    data = np.full((3, len(lats), len(lons)), np.nan)
    data[:, 3, 0] = 18.0  # (lat 36.75, lon 36.0) — the ocean cell
    data[:, 2, 3] = 18.5  # (lat 36.5, lon 36.75) — valid but farther
    ds = xr.Dataset(
        {"sosstsst": (("time", "latitude", "longitude"), data)},
        coords={"time": times, "latitude": lats, "longitude": lons},
    )

    out = _nearest_ocean_cell(ds, "sosstsst", 36.725833, 36.186111)
    assert out is not None
    lat_idx, lon_idx, lat, lon, snap = out
    assert (lat_idx, lon_idx) == (3, 0)
    assert (lat, lon) == (36.75, 36.0)
    assert snap == pytest.approx(16.8005, abs=1e-3)


def test_nearest_ocean_cell_returns_none_when_fully_masked() -> None:
    import numpy as np
    import pandas as pd
    import xarray as xr

    times = pd.date_range("1995-01-01", periods=3, freq="MS")
    ds = xr.Dataset(
        {"sosstsst": (("time", "latitude", "longitude"), np.full((3, 4, 4), np.nan))},
        coords={
            "time": times,
            "latitude": np.arange(36.0, 37.0, 0.25),
            "longitude": np.arange(36.0, 37.0, 0.25),
        },
    )
    assert _nearest_ocean_cell(ds, "sosstsst", 36.7333, 36.2) is None


def test_main_writes_json_and_markdown_artifacts(tmp_path) -> None:
    generated_at = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
    old_argv = sys.argv
    sys.argv = [
        "validate_isdemir_marine.py",
        "--out-dir",
        str(tmp_path),
        "--generated-at",
        generated_at.isoformat(),
    ]
    try:
        paths = main()
    finally:
        sys.argv = old_argv

    assert len(paths) == 2
    assert all(p.exists() for p in paths)
    json_path = next(p for p in paths if p.suffix == ".json")
    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["mode"] == "offline"
    assert record["checksums"]["record_sha256"]
