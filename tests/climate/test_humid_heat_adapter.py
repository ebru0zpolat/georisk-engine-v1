"""Humid-heat file adapters (WO-C05): CMIP6 3-hourly and ERA5 hourly.

Every NetCDF file here is synthetic, written to ``tmp_path`` by the test and hashed there;
nothing is committed as a fixture and no value leaves the test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from engine.climate import humid_heat as hh
from engine.climate.cmip6_heat_adapter import Cmip6AdapterError
from engine.climate.humid_heat import HumidHeatError
from engine.climate.humid_heat_adapter import Cmip6HumidHeatSource, Era5HumidHeatSource, assess_asset

MODEL = "MPI-ESM1-2-HR"
ALLOW = {"allowlist_version": "test-v1", "verified": True, "models": {MODEL: {"licence": "CC BY 4.0", "commercial_use": True}}}
ERA5_ALLOW = {"allowlist_version": "test-era5", "verified": True, "models": {"ERA5": {"commercial_use": True}}}
LAT = np.array([24.0, 25.0, 26.0])
LON = np.array([54.0, 55.0, 56.0])
BASE, HOR = (1991, 1992), ((2021, 2022),)
THR = [24.0, 26.0]  # thresholds the synthetic two-year baseline reaches often enough to measure
Q = 0.017
P = 100800.0
TD_FOR_Q = float(hh.dewpoint_c(hh.vapour_pressure_from_q_hpa(Q, P / 100.0)))


def _attrs(experiment: str) -> dict[str, str]:
    return {
        "source_id": MODEL, "variant_label": "r1i1p1f1", "experiment_id": experiment,
        "domain": "global", "dataset_id": "test-cmip6", "license": "CC BY 4.0 (test)",
    }


def _write(tmp: Path, name: str, ds: xr.Dataset) -> dict[str, str]:
    path = tmp / name
    ds.to_netcdf(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _diurnal_t(time: pd.DatetimeIndex) -> np.ndarray:
    """Synthetic temperature (K): seasonal maximum with a diurnal cycle peaking at 12 UTC."""
    doy, hour = time.dayofyear.to_numpy(), time.hour.to_numpy()
    tmax = 273.15 + 36.0 + 6.0 * np.sin(2 * np.pi * (doy - 110) / 365.0)
    return tmax - 5.0 + 5.0 * np.sin(np.pi * (hour - 6) / 12.0).clip(0)


def _subdaily(var: str, start: str, end: str, experiment: str, values, units: str, lon=LON,
              first_time: str = "00:00", last_time: str = "23:59") -> xr.Dataset:
    time = pd.date_range(f"{start}T{first_time}", f"{end}T{last_time}", freq="3h")
    field = np.broadcast_to(values(time)[:, None, None], (time.size, LAT.size, lon.size)).astype("f8")
    return xr.Dataset(
        {var: (("time", "lat", "lon"), field, {"units": units})},
        coords={"time": time, "lat": LAT, "lon": lon}, attrs=_attrs(experiment),
    )


def _fixed(var: str, field: np.ndarray, units: str) -> xr.Dataset:
    return xr.Dataset({var: (("lat", "lon"), field, {"units": units})}, coords={"lat": LAT, "lon": LON},
                      attrs=_attrs("historical"))


def _cmip6_manifest(tmp: Path, *, huss_units: str = "1", overlap: bool = False, huss_lon=LON,
                    drop: str | None = None, first_time: str = "00:00", ssp_first_time: str | None = None) -> dict:
    files = []
    spans = [("1991-01-01", "1992-12-31", "historical"), ("2021-01-01" if not overlap else "1992-06-01", "2022-12-31", "ssp585")]
    columns = {
        "tas": (_diurnal_t, "K", LON),
        "huss": (lambda t: np.full(t.size, Q), huss_units, huss_lon),
        "ps": (lambda t: np.full(t.size, P), "Pa", LON),
    }
    for start, end, exp in spans:
        for var, (fn, units, lon) in columns.items():
            if var != drop:
                ft = ssp_first_time if (ssp_first_time and exp != "historical") else first_time
                ds = _subdaily(var, start, end, exp, fn, units, lon=lon, first_time=ft)
                files.append({**_write(tmp, f"{var}_{exp}.nc", ds), "variable": var})
    land = np.full((3, 3), 80.0)
    land[0, 0] = 20.0  # sea-dominated cell at (24, 54)
    fixed = [
        {**_write(tmp, "sftlf.nc", _fixed("sftlf", land, "%")), "variable": "sftlf"},
        {**_write(tmp, "orog.nc", _fixed("orog", np.zeros((3, 3)), "m")), "variable": "orog"},
    ]
    return {"files": files, "fixed": fixed}


def _era5_manifest(tmp: Path, *, drop_hour: bool = False, end: str = "1992-12-31T23:00",
                   dewpoint_excess_k: float = 0.0) -> dict:
    time = pd.date_range("1991-01-01T00:00", end, freq="h")
    if drop_hour:
        time = time.delete(100)
    t2m = _diurnal_t(time)
    d2m = np.full(time.size, TD_FOR_Q + 273.15)
    if dewpoint_excess_k:  # one coolest hour with d2m just above t2m (encoding-size excess)
        i = int(np.argmin(t2m))
        d2m[i] = t2m[i] + dewpoint_excess_k
    shape = (time.size, LAT.size, LON.size)

    def ds(var: str, values: np.ndarray, units: str) -> xr.Dataset:
        return xr.Dataset({var: (("valid_time", "latitude", "longitude"), np.broadcast_to(values[:, None, None], shape).astype("f8"), {"units": units})},
                          coords={"valid_time": time, "latitude": LAT[::-1], "longitude": LON})

    lsm_field = np.full((3, 3), 0.9)
    lsm = xr.Dataset({"lsm": (("latitude", "longitude"), lsm_field, {"units": "(0 - 1)"})},
                     coords={"latitude": LAT[::-1], "longitude": LON})
    return {
        "files": [
            {**_write(tmp, "t2m.nc", ds("t2m", t2m, "K")), "variable": "t2m"},
            {**_write(tmp, "d2m.nc", ds("d2m", d2m, "K")), "variable": "d2m"},
            {**_write(tmp, "sp.nc", ds("sp", np.full(time.size, P), "Pa")), "variable": "sp"},
        ],
        "fixed": [{**_write(tmp, "lsm.nc", lsm), "variable": "lsm"}],
        "accessed_on": "2026-10-13",
    }


@pytest.fixture()
def sources(tmp_path: Path):
    cm = Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW)
    er = Era5HumidHeatSource(_era5_manifest(tmp_path))
    yield cm, er
    cm.close()
    er.close()


def test_end_to_end_record(sources) -> None:
    cm, er = sources
    rec = assess_asset(cm, er, lat=25.1, lon=55.2, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert rec["pressure_source"] == "ps"
    assert rec["model_id"] == MODEL and rec["scenario_id"] == "ssp585"
    assert {"TwX", "Tw_dmax_p95", "TwD24", "TwD26", "dTwX"} <= set(rec["windows"]["2021-2022"])
    assert abs(rec["baseline_bias_c"]) <= hh.BASELINE_BIAS_LIMIT_C
    assert rec["approx_error"]["temperature"]["hot_days"] >= hh.APPROX_ERROR_MIN_DAYS
    # Synthetic diurnal peak at 12 UTC is a sample hour: sampling loses nothing, counts agree exactly.
    assert rec["approx_error"]["counts"]["TwD26"]["relative_error"] == 0.0
    assert rec["sampling"]["model_sample_hours_utc"] == [0, 3, 6, 9, 12, 15, 18, 21]
    assert rec["sampling"]["saturation_adjusted_samples"] == {"model": 0, "era5": 0}
    assert rec["sampling"]["saturation_tolerance"] == {"era5_k": 0.01, "model_rh_max": 1.10}
    assert hh.HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED in rec["blockers"]
    # The shipped ERA5 licence record is verified (CDS Terms of use, 2026-10-13): no licence blocker.
    assert hh.SOURCE_LICENCE_UNVERIFIED not in rec["blockers"]
    lic = rec["era5_licence"]
    assert (lic["allowlist_version"], lic["verified"], lic["licence"]) == ("era5-licence-v1", True, "CC BY 4.0")
    # CC BY obliges attribution: the citation with the download date and the Copernicus notice travel with the record.
    assert lic["doi"] == "10.24381/cds.adbb2d47"
    assert lic["catalogue_citation"].endswith("(Accessed on 2026-10-13)") and "{accessed}" not in lic["data_citation"]
    assert lic["attribution"].startswith("Generated using or contains modified Copernicus Climate Change Service information")
    assert len(rec["files"]) == 8 and all(len(f["file_sha256"]) == 64 for f in rec["files"])
    assert rec["era5_cell"]["cell_land_fraction"] == 0.9


def test_verified_licences_leave_only_the_recomputation_blocker(tmp_path: Path) -> None:
    with Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW) as cm, \
            Era5HumidHeatSource(_era5_manifest(tmp_path), licence_allowlist=ERA5_ALLOW) as er:
        rec = assess_asset(cm, er, lat=25.0, lon=55.0, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert rec["blockers"] == [hh.HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED]


def test_sample_times_off_the_hour_refuse(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, first_time="01:30"), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_GRID_MISMATCH


def test_sample_hours_changing_between_days_refuse(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, ssp_first_time="01:00"), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_GRID_MISMATCH


def _cmip6_point_layout_manifest(tmp: Path, *, drop_inner_sample: bool = False) -> dict:
    """Real CMIP6 3hr point series run 03:00 .. 00:00 (MPI-ESM1-2-LR/HR file names, e.g. 201001010300-201501010000)."""
    files = []
    for var, fn, units in [("tas", _diurnal_t, "K"), ("huss", lambda t: np.full(t.size, Q), "1"),
                           ("ps", lambda t: np.full(t.size, P), "Pa")]:
        ds = _subdaily(var, "1990-12-31", "1993-01-01", "historical", fn, units, first_time="03:00", last_time="00:00")
        if drop_inner_sample:
            ds = ds.drop_isel(time=100)
        files.append({**_write(tmp, f"{var}_pt.nc", ds), "variable": var})
    return {"files": files, "fixed": _cmip6_manifest(tmp)["fixed"], "scenario_id": "historical"}


def test_point_series_edge_days_are_trimmed_and_counted(tmp_path: Path) -> None:
    """A 03:00..00:00 series leaves a partial first and last day; only those are trimmed, and counted."""
    with Cmip6HumidHeatSource(_cmip6_point_layout_manifest(tmp_path), licence_allowlist=ALLOW) as cm:
        assert cm.sample_hours == (0, 3, 6, 9, 12, 15, 18, 21)
        series, _ = cm.series(25.0, 55.0)
    # 7 samples on 1990-12-31 (03..21) and 1 on 1993-01-01 (00:00) are trimmed; 1991 and 1992 are whole.
    assert series.edge_samples_trimmed == 8
    assert sorted(set(series.years.tolist())) == [1991, 1992]
    assert series.years.size == 365 + 366


def test_partial_day_inside_the_series_refuses(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_point_layout_manifest(tmp_path, drop_inner_sample=True), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_coordinate_noise_between_files_is_one_grid(tmp_path: Path) -> None:
    """MPI-ESM1-2-LR fx and 3hr latitudes differ by 1e-14 degrees; that is the same grid."""
    m = _cmip6_manifest(tmp_path)
    for row in m["fixed"]:
        p = Path(row["path"])
        ds = xr.open_dataset(p).load()
        ds = ds.assign_coords(lat=ds.lat.values + 1e-14)
        p.unlink()
        ds.to_netcdf(p)
        row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    with Cmip6HumidHeatSource(m, licence_allowlist=ALLOW) as cm:
        assert cm.series(25.0, 55.0)[1].land_fraction == 0.8


def test_era5_encoding_excess_is_saturated_and_counted(tmp_path: Path) -> None:
    """Decision D3: d2m above t2m by less than the tolerance is saturation, and the record says how often."""
    with Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW) as cm, \
            Era5HumidHeatSource(_era5_manifest(tmp_path, dewpoint_excess_k=0.0004)) as er:
        rec = assess_asset(cm, er, lat=25.0, lon=55.0, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert rec["sampling"]["saturation_adjusted_samples"]["era5"] == 1


def test_era5_excess_beyond_tolerance_refuses(tmp_path: Path) -> None:
    with Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW) as cm, \
            Era5HumidHeatSource(_era5_manifest(tmp_path, dewpoint_excess_k=0.5)) as er:
        with pytest.raises(HumidHeatError) as err:
            assess_asset(cm, er, lat=25.0, lon=55.0, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert err.value.code == hh.HUMID_HEAT_TW_OUT_OF_BOUNDS


def test_negative_longitude_on_a_0_360_grid(tmp_path: Path) -> None:
    lon360 = np.array([358.0, 359.0, 360.0])
    m = _cmip6_manifest(tmp_path)
    for row in m["files"] + m["fixed"]:
        p = Path(row["path"])
        ds = xr.open_dataset(p).load()
        ds = ds.assign_coords(lon=lon360)
        p.unlink()
        ds.to_netcdf(p)
        row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    with Cmip6HumidHeatSource(m, licence_allowlist=ALLOW) as cm:
        _, cell = cm.series(25.0, -1.0)
    assert cell.lon == 359.0


def test_record_is_deterministic(tmp_path: Path) -> None:
    def run() -> str:
        with Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW) as cm, \
                Era5HumidHeatSource(_era5_manifest(tmp_path)) as er:
            return json.dumps(assess_asset(cm, er, lat=25.0, lon=55.0, baseline=BASE, horizons=HOR, thresholds_c=THR), sort_keys=True)
    assert run() == run()


# -- CLIM-03 contract (reused, unchanged) ------------------------------------


def test_checksum_mismatch_refuses(tmp_path: Path) -> None:
    m = _cmip6_manifest(tmp_path)
    m["files"][0]["sha256"] = "0" * 64
    with pytest.raises(Cmip6AdapterError, match="checksum"):
        Cmip6HumidHeatSource(m, licence_allowlist=ALLOW)


def test_time_overlap_refuses(tmp_path: Path) -> None:
    with pytest.raises(Cmip6AdapterError, match="overlap"):
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, overlap=True), licence_allowlist=ALLOW)


def test_model_without_commercial_licence_refuses(tmp_path: Path) -> None:
    allow = {"allowlist_version": "x", "verified": True, "models": {MODEL: {"commercial_use": False}}}
    with pytest.raises(Cmip6AdapterError, match="commercial"):
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=allow)


def test_outside_domain_refuses(sources) -> None:
    cm, _ = sources
    with pytest.raises(Cmip6AdapterError, match="outside"):
        cm.series(30.0, 55.0)


# -- humid-heat refusals ------------------------------------------------------


@pytest.mark.parametrize("drop", ["huss", "tas", "ps"])
def test_missing_variable_refuses(tmp_path: Path, drop: str) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, drop=drop), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE


def test_relative_humidity_units_refuse(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, huss_units="%"), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_UNIT_MISMATCH


def test_variables_on_different_grids_refuse(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Cmip6HumidHeatSource(_cmip6_manifest(tmp_path, huss_lon=LON + 0.5), licence_allowlist=ALLOW)
    assert err.value.code == hh.HUMID_HEAT_GRID_MISMATCH


def test_sea_cell_refuses(sources) -> None:
    cm, er = sources
    with pytest.raises(HumidHeatError) as err:
        assess_asset(cm, er, lat=24.0, lon=54.0, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert err.value.code == hh.HUMID_HEAT_SEA_CELL


def test_era5_missing_hour_refuses(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Era5HumidHeatSource(_era5_manifest(tmp_path, drop_hour=True))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_spatial_gate_runs_before_any_computation(sources) -> None:
    """INV-03: the cell gate is first; a sea cell never reaches the Tw solver."""
    cm, _ = sources
    with pytest.raises(HumidHeatError) as err:
        cm.series(24.0, 54.0)
    assert err.value.code == hh.HUMID_HEAT_SEA_CELL


def test_era5_series_ending_mid_day_refuses(tmp_path: Path) -> None:
    with pytest.raises(HumidHeatError) as err:
        Era5HumidHeatSource(_era5_manifest(tmp_path, end="1992-12-31T20:00"))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_era5_without_download_date_refuses(tmp_path: Path) -> None:
    m = _era5_manifest(tmp_path)
    del m["accessed_on"]
    with pytest.raises(Cmip6AdapterError, match="accessed_on"):
        Era5HumidHeatSource(m)


def test_unverified_era5_licence_record_is_a_named_blocker(tmp_path: Path) -> None:
    unverified = {**ERA5_ALLOW, "verified": False}
    with Cmip6HumidHeatSource(_cmip6_manifest(tmp_path), licence_allowlist=ALLOW) as cm, \
            Era5HumidHeatSource(_era5_manifest(tmp_path), licence_allowlist=unverified) as er:
        rec = assess_asset(cm, er, lat=25.0, lon=55.0, baseline=BASE, horizons=HOR, thresholds_c=THR)
    assert hh.SOURCE_LICENCE_UNVERIFIED in rec["blockers"]


def test_shipped_era5_record_cites_its_evidence() -> None:
    d = json.loads((Path(hh.__file__).parent / "era5_licence_v1.json").read_text())
    assert d["verified"] is True and d["verified_at"] and d["verified_by"]
    assert d["evidence"]["cds_terms_of_use"]["legal_text_link"].endswith("/licenses/by/4.0/legalcode.en")
    assert d["models"]["ERA5"]["commercial_use"] is True
