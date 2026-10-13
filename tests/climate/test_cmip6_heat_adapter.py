"""CLIM-03 Cmip6HeatAdapter — WSDI/TX90p + fail-closed merge/licence/calendar gates."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from engine.climate.cmip6_heat_adapter import (
    APPROVED_SCENARIOS,
    DEFAULT_BASELINE_END,
    DEFAULT_BASELINE_START,
    Cmip6AdapterError,
    Cmip6HeatAdapter,
    _load_licence_allowlist,
)
from engine.climate.indices_etccdi import (
    annual_tx90p,
    annual_wsdi,
    baseline_tx90_by_doy,
    calendar_day_keys,
)

ALLOWED_MODEL = "MPI-ESM1-2-HR"

TEST_ALLOWLIST = {
    "allowlist_version": "test-allowlist-v1",
    "models": {
        ALLOWED_MODEL: {"licence": "CC BY 4.0", "commercial_use": True},
        "NC-Model": {"licence": "CC BY-NC-SA 4.0", "commercial_use": False},
    },
}


def _identity_attrs(model: str = ALLOWED_MODEL, experiment: str = "ssp245") -> dict[str, str]:
    return {
        "domain": "global",
        "dataset_id": "cds-cmip6-tasmax-test-v1",
        "source_id": model,
        "variant_label": "r1i1p1f1",
        "experiment_id": experiment,
        "license": "CC BY 4.0 (test fixture)",
    }


def _series_c(times, hot: bool, boost_from_year: int | None) -> np.ndarray:
    def _doy(t) -> int:
        return int(getattr(t, "dayofyr", None) or t.timetuple().tm_yday)

    doy = np.asarray([_doy(t) for t in times], dtype=float)
    year = np.asarray([int(t.year) for t in times], dtype=int)
    seasonal = 8.0 * np.sin(2 * np.pi * (doy - 80) / 365.0)
    base = (22.0 if hot else 12.0) + seasonal
    if boost_from_year is not None:
        base = base + np.where(year >= boost_from_year, 6.0, 0.0)
    return base


def _write_tasmax_nc(
    path: Path,
    *,
    units: str = "K",
    calendar: str = "standard",
    include_tasmax: bool = True,
    inject_nonfinite: str | None = None,
    lat_1d: bool = True,
    years: tuple[int, int] = (2000, 2002),
    boost_from_year: int | None = 2001,
    with_identity_attrs: bool = True,
    model: str = ALLOWED_MODEL,
    experiment: str = "ssp245",
    drop_last_days: int = 0,
) -> Path:
    lats = np.array([36.9, 51.9], dtype=float)
    lons = np.array([30.7, 4.5], dtype=float)

    if calendar in {"noleap", "365_day"}:
        times = xr.date_range(
            f"{years[0]}-01-01",
            f"{years[1]}-12-31",
            freq="D",
            calendar="noleap",
            use_cftime=True,
        )
    else:
        times = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")

    if drop_last_days:
        times = times[:-drop_last_days]

    n = len(times)
    base_c = np.full((n, len(lats), len(lons)), 10.0, dtype=float)
    base_c[:, 0, 0] = _series_c(times, hot=True, boost_from_year=boost_from_year)
    base_c[:, 1, 1] = _series_c(times, hot=False, boost_from_year=boost_from_year)

    if inject_nonfinite == "nan":
        base_c[10, 0, 0] = np.nan
    elif inject_nonfinite == "inf":
        base_c[10, 0, 0] = np.inf
    elif inject_nonfinite == "-inf":
        base_c[11, 0, 0] = -np.inf

    data = base_c + 273.15 if units in {"K", "Kelvin"} else base_c

    if lat_1d:
        ds_vars: dict = {}
        if include_tasmax:
            ds_vars["tasmax"] = (("time", "lat", "lon"), data)
        ds = xr.Dataset(ds_vars, coords={"time": times, "lat": lats, "lon": lons})
    else:
        lat2 = np.tile(lats.reshape(-1, 1), (1, len(lons)))
        lon2 = np.tile(lons.reshape(1, -1), (len(lats), 1))
        ds = xr.Dataset(
            {"tasmax": (("time", "y", "x"), data)},
            coords={
                "time": times,
                "lat": (("y", "x"), lat2),
                "lon": (("y", "x"), lon2),
            },
        )

    if include_tasmax:
        ds["tasmax"].attrs["units"] = units
    if calendar not in {"noleap", "365_day"}:
        ds.time.encoding["calendar"] = calendar
    if with_identity_attrs:
        ds.attrs.update(_identity_attrs(model=model, experiment=experiment))
    ds.to_netcdf(path, engine="netcdf4")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_for(path: Path, **overrides: object) -> dict:
    body = {
        "sha256": _sha256(path),
        "domain": "global",
        "dataset_id": "cds-cmip6-tasmax-test-v1",
        "model_id": ALLOWED_MODEL,
        "member_id": "r1i1p1f1",
        "scenario_id": "ssp245",
        "licence": "CC BY 4.0 (test fixture)",
        "baseline_start": 2000,
        "baseline_end": 2000,
    }
    body.update(overrides)
    return body


def _adapter(path: Path, manifest: dict, **kw) -> Cmip6HeatAdapter:
    kw.setdefault("licence_allowlist", TEST_ALLOWLIST)
    return Cmip6HeatAdapter(path, manifest=manifest, **kw)


def test_approved_contract_constants() -> None:
    assert (DEFAULT_BASELINE_START, DEFAULT_BASELINE_END) == (1991, 2020)
    assert set(APPROVED_SCENARIOS) == {"ssp245", "ssp585"}


def test_wsdi_and_tx90p_computed(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc", years=(2000, 2002))
    manifest = _manifest_for(path)
    with _adapter(path, manifest) as adapter:
        out = adapter.get_heat_indices(36.9, 30.7, 2001, 2002)
        assert out["primary_indicator"] == "WSDI"
        assert out["diagnostic_indicator"] == "TX90p"
        assert out["wsdi_mean_annual_days"] >= 0
        assert 0 <= out["tx90p_mean_annual_pct"] <= 100
        assert out["tx90p_mean_annual_pct"] > 10.0  # boosted horizon vs baseline
        prov = adapter.provenance()
        assert prov["model_id"] == ALLOWED_MODEL
        assert prov["scenario_id"] == "ssp245"
        assert prov["licence_allowlist_version"] == "test-allowlist-v1"
        assert prov["files"][0]["file_sha256"] == manifest["sha256"]


def test_checksum_mandatory(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc")
    with pytest.raises(Cmip6AdapterError, match="SHA-256"):
        Cmip6HeatAdapter(path, licence_allowlist=TEST_ALLOWLIST)


def test_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc")
    with pytest.raises(Cmip6AdapterError, match="checksum mismatch"):
        _adapter(path, _manifest_for(path, sha256="0" * 64))


def test_outside_domain_no_silent_snap(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc")
    with _adapter(path, _manifest_for(path)) as adapter:
        with pytest.raises(Cmip6AdapterError, match="outside data domain"):
            adapter.get_heat_indices(10.0, 30.7, 2001, 2002)


@pytest.mark.parametrize("kind", ["nan", "inf", "-inf"])
def test_nonfinite_rejected(tmp_path: Path, kind: str) -> None:
    path = _write_tasmax_nc(tmp_path / f"{kind.strip('-')}.nc", inject_nonfinite=kind)
    with _adapter(path, _manifest_for(path)) as adapter:
        with pytest.raises(Cmip6AdapterError, match="Non-finite"):
            adapter.get_heat_indices(36.9, 30.7, 2001, 2002)


def test_missing_identity_fails_closed(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "noid.nc", with_identity_attrs=False)
    with pytest.raises(Cmip6AdapterError, match="identity"):
        Cmip6HeatAdapter(
            path,
            manifest={"sha256": _sha256(path)},
            licence_allowlist=TEST_ALLOWLIST,
        )


def test_identity_from_manifest_not_hardcoded(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc", with_identity_attrs=False)
    manifest = _manifest_for(
        path,
        domain="cmip6-global",
        dataset_id="custom-dataset",
        model_id=ALLOWED_MODEL,
        member_id="r2i1p1f1",
        scenario_id="ssp585",
        licence="CC BY 4.0",
    )
    with _adapter(path, manifest) as adapter:
        prov = adapter.provenance()
        assert prov["domain"] == "cmip6-global"
        assert prov["dataset_id"] == "custom-dataset"
        assert prov["member_id"] == "r2i1p1f1"
        assert prov["scenario_id"] == "ssp585"


def test_licence_gate_unlisted_model_fails(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc", model="Unknown-Model")
    manifest = _manifest_for(path, model_id="Unknown-Model")
    with pytest.raises(Cmip6AdapterError, match="allowlist"):
        _adapter(path, manifest)


def test_licence_gate_non_commercial_fails(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc", model="NC-Model")
    manifest = _manifest_for(path, model_id="NC-Model")
    with pytest.raises(Cmip6AdapterError, match="commercial"):
        _adapter(path, manifest)


def test_committed_allowlist_licence_gate_closed() -> None:
    """Production allowlist must be verified with commercial-use evidence."""
    allowlist = _load_licence_allowlist(None)
    assert allowlist["verified"] is True
    assert allowlist["allowlist_version"] == "cmip6-model-licences-v1"
    assert "evidence" in allowlist
    for model in ("MPI-ESM1-2-HR", "MPI-ESM1-2-LR"):
        entry = allowlist["models"][model]
        assert entry["commercial_use"] is True
        assert entry["licence"] == "CC BY 4.0"
        assert entry.get("evidence_urls")


def test_unverified_production_allowlist_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    path = tmp_path / "cmip6_model_licences_v1.json"
    path.write_text(
        json.dumps(
            {
                "allowlist_version": "cmip6-model-licences-v1",
                "verified": False,
                "models": {
                    ALLOWED_MODEL: {"licence": "CC BY 4.0", "commercial_use": True}
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "engine.climate.cmip6_heat_adapter._ALLOWLIST_PATH", path
    )
    with pytest.raises(Cmip6AdapterError, match="not verified"):
        _load_licence_allowlist(None)


def test_curvilinear_grid_fail_closed(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "curve.nc", lat_1d=False)
    with pytest.raises(Cmip6AdapterError, match="curvilinear|2-D"):
        _adapter(path, _manifest_for(path))


def test_noleap_calendar_cftime(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "noleap.nc", calendar="noleap", years=(2000, 2002))
    with _adapter(path, _manifest_for(path)) as adapter:
        out = adapter.get_heat_indices(36.9, 30.7, 2001, 2002)
        assert out["wsdi_mean_annual_days"] >= 0
        assert 0 <= out["tx90p_mean_annual_pct"] <= 100


def test_incomplete_horizon_year_fails(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "partial.nc", years=(2000, 2002), drop_last_days=30)
    with _adapter(path, _manifest_for(path)) as adapter:
        with pytest.raises(Cmip6AdapterError, match="incomplete"):
            adapter.get_heat_indices(36.9, 30.7, 2001, 2002)


def test_incomplete_baseline_year_fails(tmp_path: Path) -> None:
    path = _write_tasmax_nc(tmp_path / "ok.nc", years=(2000, 2002))
    with _adapter(path, _manifest_for(path)) as adapter:
        with pytest.raises(Cmip6AdapterError, match="Baseline year 1999 incomplete"):
            adapter.get_heat_indices(36.9, 30.7, 2001, 2002, baseline_start=1999, baseline_end=2000)


def test_multifile_historical_plus_ssp_merge(tmp_path: Path) -> None:
    hist = _write_tasmax_nc(
        tmp_path / "hist.nc", years=(2000, 2001), experiment="historical", boost_from_year=None
    )
    ssp = _write_tasmax_nc(
        tmp_path / "ssp.nc", years=(2002, 2003), experiment="ssp245", boost_from_year=2002
    )
    manifest = {
        "files": [
            {"path": str(hist), "sha256": _sha256(hist), "experiment_id": "historical"},
            {"path": str(ssp), "sha256": _sha256(ssp), "experiment_id": "ssp245"},
        ],
        "domain": "global",
        "dataset_id": "cds-cmip6-tasmax-test-v1",
        "model_id": ALLOWED_MODEL,
        "member_id": "r1i1p1f1",
        "scenario_id": "ssp245",
        "licence": "CC BY 4.0 (test fixture)",
        "baseline_start": 2000,
        "baseline_end": 2001,
    }
    with Cmip6HeatAdapter(manifest=manifest, licence_allowlist=TEST_ALLOWLIST) as adapter:
        out = adapter.get_heat_indices(36.9, 30.7, 2002, 2003)
        assert out["wsdi_mean_annual_days"] >= 0
        prov = adapter.provenance()
        exps = {f["experiment_id"] for f in prov["files"]}
        assert exps == {"historical", "ssp245"}


def test_multifile_overlap_fails(tmp_path: Path) -> None:
    a = _write_tasmax_nc(tmp_path / "a.nc", years=(2000, 2001), experiment="historical")
    b = _write_tasmax_nc(tmp_path / "b.nc", years=(2001, 2002), experiment="ssp245")
    manifest = {
        "files": [
            {"path": str(a), "sha256": _sha256(a), "experiment_id": "historical"},
            {"path": str(b), "sha256": _sha256(b), "experiment_id": "ssp245"},
        ],
        "domain": "global",
        "dataset_id": "x",
        "model_id": ALLOWED_MODEL,
        "member_id": "r1i1p1f1",
        "scenario_id": "ssp245",
        "licence": "CC BY 4.0",
    }
    with pytest.raises(Cmip6AdapterError, match="overlap"):
        Cmip6HeatAdapter(manifest=manifest, licence_allowlist=TEST_ALLOWLIST)


def test_multifile_member_mismatch_fails(tmp_path: Path) -> None:
    a = _write_tasmax_nc(tmp_path / "a.nc", years=(2000, 2000), experiment="historical")
    b_path = tmp_path / "b.nc"
    _write_tasmax_nc(b_path, years=(2001, 2001), experiment="ssp245")
    # Rewrite b with a different member.
    ds = xr.open_dataset(b_path)
    ds.attrs["variant_label"] = "r9i1p1f1"
    fixed = tmp_path / "b2.nc"
    ds.to_netcdf(fixed)
    ds.close()
    manifest = {
        "files": [
            {"path": str(a), "sha256": _sha256(a), "experiment_id": "historical"},
            {"path": str(fixed), "sha256": _sha256(fixed), "experiment_id": "ssp245"},
        ],
        "domain": "global",
        "dataset_id": "x",
        "model_id": ALLOWED_MODEL,
        "member_id": "r1i1p1f1",
        "scenario_id": "ssp245",
        "licence": "CC BY 4.0",
    }
    with pytest.raises(Cmip6AdapterError, match="identity differs"):
        Cmip6HeatAdapter(manifest=manifest, licence_allowlist=TEST_ALLOWLIST)


def test_etccdi_helpers_spell_and_pct() -> None:
    years = np.array([2001] * 10)
    doy = np.arange(1, 11, dtype=np.int16)
    tx = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 0], dtype=float)
    thr = np.full(365, 0.5)
    assert annual_wsdi(tx, years, doy, thr)[2001] == 6.0
    assert annual_tx90p(tx, years, doy, thr)[2001] == 60.0


def test_baseline_thresholds_finite() -> None:
    dates = pd.date_range("2000-01-01", "2000-12-31", freq="D")
    years = dates.year.to_numpy()
    months = dates.month.to_numpy()
    days = dates.day.to_numpy()
    doy = calendar_day_keys(years, months, days)
    tx = 10.0 + 5.0 * np.sin(2 * np.pi * (doy - 80) / 365.0)
    thr = baseline_tx90_by_doy(tx, doy, np.ones_like(tx, dtype=bool))
    assert thr.shape == (365,)
    assert np.isfinite(thr).all()
