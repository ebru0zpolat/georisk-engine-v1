"""Humid-heat file adapters (WO-C05, slice 2).

Reads sealed CMIP6 daily and ERA5 hourly NetCDF files into the aligned arrays that
:mod:`engine.climate.humid_heat` computes on. Spec: ``docs/specs/humid-heat-indicator-v1.md``
§3 (inputs) and §6 (cells).

The CLIM-03 contract of ``engine/climate/cmip6_heat_adapter.py`` holds unchanged and is
reused, not copied: per-file SHA-256, the versioned model licence allowlist, deterministic
historical+SSP merge with overlap refusal, identity from manifest or global attributes,
1-D grids only, nearest cell inside the domain and its Voronoi cell only. Those refusals
raise :class:`Cmip6AdapterError` as they do for the heat adapter; refusals specific to this
indicator raise :class:`HumidHeatError` with a registered code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import xarray as xr

from engine.climate import humid_heat as hh
from engine.climate.cmip6_heat_adapter import (
    SUPPORTED_CALENDARS,
    Cmip6AdapterError,
    _attr_first,
    _load_licence_allowlist,
    _load_manifest,
    _SourceFile,
)
from engine.climate.humid_heat import DailySeries, GridCell, HumidHeatError

ADAPTER_VERSION = "humid-heat-adapter-v0.2"

CMIP6_SUBDAILY = ("tas", "huss", "ps")  # table 3hr (decision D1)
CMIP6_FIXED = ("sftlf", "orog")
CMIP6_UNITS: dict[str, frozenset[str]] = {
    "tas": frozenset({"K"}),
    "huss": frozenset({"1", "kg kg-1", "kg/kg", "kg kg**-1"}),
    "ps": frozenset({"Pa"}),
    "sftlf": frozenset({"%"}),
    "orog": frozenset({"m"}),
}
ERA5_HOURLY = ("t2m", "d2m", "sp")
ERA5_FIXED = ("lsm",)
ERA5_UNITS: dict[str, frozenset[str]] = {
    "t2m": frozenset({"K"}),
    "d2m": frozenset({"K"}),
    "sp": frozenset({"Pa"}),
    "lsm": frozenset({"(0 - 1)", "1", "0-1"}),
}
IDENTITY_KEYS = ("domain", "dataset_id", "model_id", "member_id", "scenario_id", "licence")


# -- shared helpers ----------------------------------------------------------


def _open_rows(
    manifest: Mapping[str, Any], key: str, allowed: Sequence[str], engine: str
) -> dict[str, list[tuple[_SourceFile, Mapping[str, Any]]]]:
    rows = manifest.get(key) or []
    if not isinstance(rows, list):
        raise Cmip6AdapterError(f"Manifest {key!r} must be a list.")
    base = manifest.get("__manifest_dir__")
    out: dict[str, list[tuple[_SourceFile, Mapping[str, Any]]]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("path") or not row.get("variable"):
            raise Cmip6AdapterError(f"Each {key!r} entry needs 'path' and 'variable'.")
        var = str(row["variable"])
        if var not in allowed:
            raise HumidHeatError(hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE, f"unexpected variable {var!r} in {key!r}")
        path = Path(row["path"])
        if base and not path.is_absolute():
            path = Path(base) / path
        src = _SourceFile(path, str(row.get("sha256", "")), engine=engine)
        if var not in src.dataset.variables:
            src.dataset.close()
            raise HumidHeatError(hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE, f"{path.name} does not contain {var!r}")
        out.setdefault(var, []).append((src, row))
    return out


def _check_units(var: str, ds: xr.Dataset, table: Mapping[str, frozenset[str]]) -> None:
    units = str(ds[var].attrs.get("units", "")).strip()
    if units not in table[var]:
        raise HumidHeatError(hh.HUMID_HEAT_UNIT_MISMATCH, f"{var} units {units!r} not in {sorted(table[var])}")


def _time_name(ds: xr.Dataset) -> str:
    for name in ("time", "valid_time"):
        if name in ds.coords or name in ds.variables:
            return name
    raise Cmip6AdapterError("Unsupported dataset: missing time coordinate.")


def _calendar(ds: xr.Dataset, tname: str) -> str:
    cal = ds[tname].encoding.get("calendar") or ds[tname].attrs.get("calendar")
    if cal is None:
        first = np.asarray(ds[tname].values).reshape(-1)[0]
        cal = getattr(first, "calendar", "standard")
    return str(cal).lower()


def _merge_time(datasets: list[xr.Dataset], var: str) -> xr.Dataset:
    """Deterministic CLIM-03 merge: sort by first timestamp, refuse overlap or duplicates."""
    tname = _time_name(datasets[0])
    ordered = sorted(datasets, key=lambda ds: ds[tname].values[0])
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if not earlier[tname].values[-1] < later[tname].values[0]:
            raise Cmip6AdapterError(f"Refusing merge of {var}: time overlap or duplicate timestamps.")
    if len(ordered) == 1:
        return ordered[0]
    return xr.concat(ordered, dim=tname, combine_attrs="drop_conflicts")


def _spatial_names(ds: xr.Dataset) -> tuple[str, str]:
    names = set(ds.coords) | set(ds.variables)
    lat = next((n for n in ("lat", "latitude") if n in names), None)
    lon = next((n for n in ("lon", "longitude") if n in names), None)
    if lat is None or lon is None or ds[lat].ndim != 1 or ds[lon].ndim != 1:
        raise Cmip6AdapterError("Need 1-D lat/latitude and lon/longitude axes (curvilinear grids refused).")
    return lat, lon


def _cell_index(axis: np.ndarray, value: float, name: str) -> int:
    """Nearest index, inside the domain and inside that point's Voronoi cell (no edge snap)."""
    lo, hi = float(np.min(axis)), float(np.max(axis))
    if value < lo or value > hi:
        raise Cmip6AdapterError(f"{name} {value} outside data domain [{lo}, {hi}]; refusing silent snap.")
    idx = int(np.argmin(np.abs(axis - value)))
    if axis.size > 1:
        steps = []
        if idx > 0:
            steps.append(abs(float(axis[idx] - axis[idx - 1])))
        if idx < axis.size - 1:
            steps.append(abs(float(axis[idx + 1] - axis[idx])))
        if abs(value - float(axis[idx])) > min(steps) / 2.0 + 1e-9:
            raise Cmip6AdapterError(f"{name} {value} outside the cell of nearest grid point {float(axis[idx])}.")
    return idx


def _grid_lon(lon: float, axis: np.ndarray) -> float:
    return lon % 360.0 if float(np.min(axis)) >= 0.0 and lon < 0.0 else lon


# Coordinates of one model's files can differ by floating-point noise (MPI-ESM1-2-LR fx vs 3hr latitudes: 1e-14°).
# Anything beyond this is a different grid.
GRID_COORD_TOLERANCE_DEG = 1e-6


def _same_axis(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= GRID_COORD_TOLERANCE_DEG))


def _same_grid(datasets: Mapping[str, xr.Dataset]) -> tuple[str, str, np.ndarray, np.ndarray]:
    first = next(iter(datasets.values()))
    lat_n, lon_n = _spatial_names(first)
    lat, lon = np.asarray(first[lat_n].values, float), np.asarray(first[lon_n].values, float)
    for var, ds in datasets.items():
        la, lo = _spatial_names(ds)
        if not (_same_axis(np.asarray(ds[la].values, float), lat) and _same_axis(np.asarray(ds[lo].values, float), lon)):
            raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, f"{var} is on a different grid")
    return lat_n, lon_n, lat, lon


def _point(ds: xr.Dataset, var: str, lat_n: str, lon_n: str, i: int, j: int) -> np.ndarray:
    da = ds[var].isel({lat_n: i, lon_n: j})
    return np.asarray(da.values, dtype=np.float64).reshape(-1)


def _licence_entry(allowlist: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    return allowlist.get("models", {}).get(key)


# -- CMIP6 -------------------------------------------------------------------


class Cmip6HumidHeatSource:
    """One CMIP6 series (model, member, scenario): 3-hourly tas, huss, ps; fixed sftlf, orog."""

    def __init__(
        self,
        manifest: str | Path | Mapping[str, Any],
        *,
        engine: str = "netcdf4",
        licence_allowlist: Mapping[str, Any] | None = None,
    ) -> None:
        self.manifest = _load_manifest(manifest)
        if isinstance(manifest, (str, Path)):
            self.manifest.setdefault("__manifest_dir__", str(Path(manifest).parent))
        self._allowlist = _load_licence_allowlist(licence_allowlist)
        self._opened: list[_SourceFile] = []
        try:
            daily = _open_rows(self.manifest, "files", CMIP6_SUBDAILY, engine)
            fixed = _open_rows(self.manifest, "fixed", CMIP6_FIXED, engine)
            for group in (daily, fixed):
                for pairs in group.values():
                    self._opened.extend(src for src, _ in pairs)
            missing = [v for v in CMIP6_SUBDAILY if v not in daily] + [v for v in CMIP6_FIXED if v not in fixed]
            if missing:
                raise HumidHeatError(hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE, f"missing {missing}")
            if any(len(fixed[v]) != 1 for v in CMIP6_FIXED):
                raise HumidHeatError(hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE, "exactly one file per fixed field")
            self._check_identity_consistent()
            self.daily = {v: _merge_time([s.dataset for s, _ in daily[v]], v) for v in CMIP6_SUBDAILY}
            self.fixed = {v: fixed[v][0][0].dataset for v in CMIP6_FIXED}
            for v, ds in {**self.daily, **self.fixed}.items():
                _check_units(v, ds, CMIP6_UNITS)
            self._lat_n, self._lon_n, self._lat, self._lon = _same_grid({**self.daily, **self.fixed})
            self._tname = _time_name(self.daily["tas"])
            self.calendar = self._check_time_axes()
            self._day_years, self.sample_hours = self._day_layout()
            self.identity = self._resolve_identity()
            self.licence_verified = self._licence_gate()
            self.file_records = [
                {"file_name": s.path.name, "file_sha256": s.sha256, "variable": str(r["variable"])}
                for group in (daily, fixed)
                for pairs in group.values()
                for s, r in pairs
            ]
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        for src in self._opened:
            src.dataset.close()
        self._opened = []

    def __enter__(self) -> Cmip6HumidHeatSource:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _check_identity_consistent(self) -> None:
        idents = set()
        for src in self._opened:
            a = dict(src.dataset.attrs)
            idents.add((_attr_first(a, "source_id", "model_id", "source"), _attr_first(a, "variant_label", "member_id")))
        if len(idents) > 1:
            raise Cmip6AdapterError(f"Refusing: model/member identity differs across files: {sorted(map(str, idents))}.")

    def _check_time_axes(self) -> str:
        ref = self.daily["tas"]
        cal = _calendar(ref, self._tname)
        if cal not in SUPPORTED_CALENDARS:
            raise HumidHeatError(hh.HUMID_HEAT_UNIT_MISMATCH, f"unsupported calendar {cal!r}")
        ref_t = np.asarray(ref[self._tname].values)
        for v, ds in self.daily.items():
            if _calendar(ds, _time_name(ds)) != cal:
                raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, f"{v} calendar differs")
            t = np.asarray(ds[_time_name(ds)].values)
            if t.shape != ref_t.shape or not all(a == b for a, b in zip(t, ref_t, strict=True)):
                raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, f"{v} time axis differs from tas")
        return cal

    def _day_layout(self) -> tuple[np.ndarray, tuple[int, ...]]:
        """Whole UTC days of 8 samples on whole hours, the same hours every day; returns (year per day, hours).

        CMIP6 3hr point series run 03:00 .. 00:00 (e.g. MPI-ESM1-2-LR ``199001010300-201001010000``), so the
        first and the last UTC day of a series are partial. Only those two edge days may be partial; they are
        trimmed and the trimmed sample count is kept for the record. A partial day anywhere else refuses.
        """
        t = self.daily["tas"][self._tname].dt
        years = np.asarray(t.year.values, dtype=np.int64)
        doy = np.asarray(t.dayofyear.values, dtype=np.int64)
        hours = np.asarray(t.hour.values, dtype=np.int64)
        if (np.asarray(t.minute.values) != 0).any() or (np.asarray(t.second.values) != 0).any():
            raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, "sub-daily times are not on whole hours")
        n = hh.CMIP6_SAMPLES_PER_DAY
        key = years * 1000 + doy
        starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
        lengths = np.diff(np.r_[starts, key.size])
        first = 1 if lengths.size and lengths[0] < n else 0
        last = lengths.size - 1 if lengths.size and lengths[-1] < n else lengths.size
        if last <= first:
            raise HumidHeatError(hh.HUMID_HEAT_WINDOW_INCOMPLETE, f"no whole day of {n} samples")
        if (lengths[first:last] != n).any():
            raise HumidHeatError(hh.HUMID_HEAT_WINDOW_INCOMPLETE, f"a UTC day inside the series does not hold exactly {n} samples")
        lo = int(starts[first])
        hi = int(starts[last]) if last < lengths.size else int(key.size)
        self._keep = slice(lo, hi)
        self.edge_samples_trimmed = int(key.size - (hi - lo))
        hour_rows = hours[lo:hi].reshape(-1, n)
        if (hour_rows != hour_rows[0]).any() or (np.diff(hour_rows[0]) <= 0).any():
            raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, "sample hours differ between days")
        return years[lo:hi:n], tuple(int(h) for h in hour_rows[0])

    def _resolve_identity(self) -> dict[str, str]:
        attrs = dict(self.daily["tas"].attrs)
        found = {
            "domain": self.manifest.get("domain") or _attr_first(attrs, "domain"),
            "dataset_id": self.manifest.get("dataset_id") or _attr_first(attrs, "dataset_id", "tracking_id"),
            "model_id": self.manifest.get("model_id") or _attr_first(attrs, "source_id", "model_id"),
            "member_id": self.manifest.get("member_id") or _attr_first(attrs, "variant_label", "member_id"),
            "scenario_id": self.manifest.get("scenario_id") or self._scenario_from_files(),
            "licence": self.manifest.get("licence") or _attr_first(attrs, "license", "licence"),
        }
        missing = [k for k in IDENTITY_KEYS if not found.get(k)]
        if missing:
            raise Cmip6AdapterError(f"Missing required climate identity fields {missing}.")
        return {k: str(found[k]) for k in IDENTITY_KEYS}

    def _scenario_from_files(self) -> str | None:
        """The one non-historical experiment among the opened files (merge drops conflicting attrs)."""
        exps = {_attr_first(dict(src.dataset.attrs), "experiment_id") for src in self._opened}
        future = sorted(e for e in exps if e and e != "historical")
        if len(future) > 1:
            raise Cmip6AdapterError(f"Refusing: more than one scenario in one series: {future}.")
        return future[0] if future else None

    def _licence_gate(self) -> bool:
        entry = _licence_entry(self._allowlist, self.identity["model_id"])
        if entry is None or not entry.get("commercial_use", False):
            raise Cmip6AdapterError(
                f"Model {self.identity['model_id']!r} not cleared for commercial use in "
                f"{self._allowlist['allowlist_version']}; refusing."
            )
        return self._allowlist.get("verified") is True

    def series(self, lat: float, lon: float) -> tuple[DailySeries, GridCell]:
        i = _cell_index(self._lat, lat, "latitude")
        j = _cell_index(self._lon, _grid_lon(lon, self._lon), "longitude")
        orog = float(_point(self.fixed["orog"], "orog", self._lat_n, self._lon_n, i, j)[0])
        land = float(_point(self.fixed["sftlf"], "sftlf", self._lat_n, self._lon_n, i, j)[0]) / 100.0
        cell = GridCell(
            lat=float(self._lat[i]),
            lon=float(self._lon[j]),
            land_fraction=land,
            resolution_deg=_resolution(self._lat, self._lon),
            orog_m=orog,
        )
        cell.check(lat, lon)  # §6 spatial gate precedes any computation (INV-03)
        tas, huss, ps = (_point(self.daily[v], v, self._lat_n, self._lon_n, i, j)[self._keep] for v in CMIP6_SUBDAILY)
        tw, adjusted, max_excess = hh.daily_max_tw(tas, huss, ps, hh.CMIP6_SAMPLES_PER_DAY)
        series = DailySeries(
            years=self._day_years,
            tw_c=tw,
            calendar=self.calendar,
            identity=self.identity,
            pressure_source="ps",
            files=tuple(self.file_records),
            licence_verified=self.licence_verified,
            saturation_adjusted=adjusted,
            saturation_max_excess_k=max_excess,
            sample_hours=self.sample_hours,
            edge_samples_trimmed=self.edge_samples_trimmed,
        )
        return series, cell


def _resolution(lat: np.ndarray, lon: np.ndarray) -> float:
    steps = [abs(float(np.diff(a).mean())) for a in (lat, lon) if a.size > 1]
    return round(max(steps), 4) if steps else 0.0


# -- ERA5 --------------------------------------------------------------------

_ERA5_LICENCE_PATH = Path(__file__).with_name("era5_licence_v1.json")


def _fill(template: str | None, accessed: str) -> str | None:
    return template.replace("{accessed}", accessed) if template else None


def _load_era5_licence() -> dict[str, Any]:
    return json.loads(_ERA5_LICENCE_PATH.read_text(encoding="utf-8"))



class Era5HumidHeatSource:
    """ERA5 hourly t2m, d2m, sp and the land–sea mask, for the baseline and §5 error."""

    ERA5_LICENCE_KEY = "ERA5"

    def __init__(
        self,
        manifest: str | Path | Mapping[str, Any],
        *,
        engine: str = "netcdf4",
        licence_allowlist: Mapping[str, Any] | None = None,
    ) -> None:
        self.manifest = _load_manifest(manifest)
        if isinstance(manifest, (str, Path)):
            self.manifest.setdefault("__manifest_dir__", str(Path(manifest).parent))
        self._opened: list[_SourceFile] = []
        try:
            hourly = _open_rows(self.manifest, "files", ERA5_HOURLY, engine)
            fixed = _open_rows(self.manifest, "fixed", ERA5_FIXED, engine)
            for group in (hourly, fixed):
                for pairs in group.values():
                    self._opened.extend(src for src, _ in pairs)
            missing = [v for v in ERA5_HOURLY if v not in hourly] + [v for v in ERA5_FIXED if v not in fixed]
            if missing:
                raise HumidHeatError(hh.HUMID_HEAT_VARIABLE_SET_INCOMPLETE, f"missing {missing}")
            self.hourly = {v: _merge_time([s.dataset for s, _ in hourly[v]], v) for v in ERA5_HOURLY}
            self.fixed = {"lsm": fixed["lsm"][0][0].dataset}
            for v, ds in {**self.hourly, **self.fixed}.items():
                _check_units(v, ds, ERA5_UNITS)
            self._lat_n, self._lon_n, self._lat, self._lon = _same_grid({**self.hourly, **self.fixed})
            self._days, self._years = self._day_layout()
            allowlist = licence_allowlist if licence_allowlist is not None else _load_era5_licence()
            entry = _licence_entry(allowlist, self.ERA5_LICENCE_KEY)
            # An unverified record does not refuse the source; it is carried as SOURCE_LICENCE_UNVERIFIED.
            self.licence_verified = bool(allowlist.get("verified") is True and entry and entry.get("commercial_use"))
            accessed = self.manifest.get("accessed_on")
            if not accessed or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(accessed)):
                raise Cmip6AdapterError("ERA5 manifest needs 'accessed_on' (YYYY-MM-DD), the download date the citation requires.")
            entry = entry or {}
            self.licence_record = {
                "allowlist_version": allowlist.get("allowlist_version"),
                "verified": allowlist.get("verified") is True,
                "licence": entry.get("licence"),
                "accessed_on": str(accessed),
                "doi": entry.get("doi"),
                "catalogue_citation": _fill(entry.get("catalogue_citation"), str(accessed)),
                "data_citation": _fill(entry.get("data_citation"), str(accessed)),
                "attribution": entry.get("attribution"),
            }
            self.file_records = [
                {"file_name": s.path.name, "file_sha256": s.sha256, "variable": str(r["variable"])}
                for group in (hourly, fixed)
                for pairs in group.values()
                for s, r in pairs
            ]
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        for src in self._opened:
            src.dataset.close()
        self._opened = []

    def __enter__(self) -> Era5HumidHeatSource:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _day_layout(self) -> tuple[int, np.ndarray]:
        ref = self.hourly["t2m"]
        tname = _time_name(ref)
        times = np.asarray(ref[tname].values).astype("datetime64[h]")
        for v, ds in self.hourly.items():
            other = np.asarray(ds[_time_name(ds)].values).astype("datetime64[h]")
            if other.shape != times.shape or not np.array_equal(other, times):
                raise HumidHeatError(hh.HUMID_HEAT_GRID_MISMATCH, f"{v} time axis differs from t2m")
        if times.size == 0 or times.size % 24:
            raise HumidHeatError(hh.HUMID_HEAT_WINDOW_INCOMPLETE, "hourly series is not whole UTC days")
        expected = times[0].astype("datetime64[D]").astype("datetime64[h]") + np.arange(times.size)
        if not np.array_equal(times, expected):
            raise HumidHeatError(hh.HUMID_HEAT_WINDOW_INCOMPLETE, "hourly series has a gap, duplicate or offset hour")
        days = times.size // 24
        day_starts = times[::24].astype("datetime64[D]")
        years = day_starts.astype("datetime64[Y]").astype(np.int64) + 1970
        return days, years

    def series(
        self, lat: float, lon: float, sample_hours: tuple[int, ...]
    ) -> tuple[DailySeries, GridCell, np.ndarray]:
        """Returns (series of true daily-max Tw, cell, daily max at the model's sample hours)."""
        i = _cell_index(self._lat, lat, "latitude")
        j = _cell_index(self._lon, _grid_lon(lon, self._lon), "longitude")
        land = float(_point(self.fixed["lsm"], "lsm", self._lat_n, self._lon_n, i, j)[0])
        cell = GridCell(
            lat=float(self._lat[i]), lon=float(self._lon[j]), land_fraction=land,
            resolution_deg=_resolution(self._lat, self._lon),
        )
        cell.check(lat, lon)  # §6 spatial gate precedes any computation (INV-03)
        t, d, p = (
            _point(self.hourly[v], v, self._lat_n, self._lon_n, i, j).reshape(self._days, 24) for v in ERA5_HOURLY
        )
        true_max, sampled, adjusted = hh.era5_daily_tw(t, d, p, sample_hours)
        series = DailySeries(
            years=self._years, tw_c=true_max, calendar="standard", identity={"dataset_id": "ERA5"},
            pressure_source="sp", files=tuple(self.file_records), licence_verified=self.licence_verified,
            saturation_adjusted=adjusted, sample_hours=tuple(range(24)),
        )
        return series, cell, sampled


# -- one asset ----------------------------------------------------------------


def assess_asset(
    cmip6: Cmip6HumidHeatSource,
    era5: Era5HumidHeatSource,
    *,
    lat: float,
    lon: float,
    baseline: tuple[int, int] = (1991, 2020),
    horizons: Sequence[tuple[int, int]] = ((2021, 2040), (2041, 2060)),
    thresholds_c: Sequence[float] | None = None,
) -> dict[str, Any]:
    """The §11 record for one asset: both cells pass the §6 gate, then :func:`humid_heat.assess`."""
    model, model_cell = cmip6.series(lat, lon)
    obs, obs_cell, sampled = era5.series(lat, lon, model.sample_hours)
    obs_info = obs_cell.check(lat, lon)
    record = hh.assess(
        asset_lat=lat, asset_lon=lon, model_cell=model_cell, model=model, era5=obs,
        era5_sampled_c=sampled, baseline=baseline, horizons=horizons, thresholds_c=thresholds_c,
    )
    record["adapter_version"] = ADAPTER_VERSION
    record["era5_cell"] = obs_info
    record["era5_files"] = [dict(f) for f in obs.files]
    record["era5_licence"] = dict(era5.licence_record)
    return record


__all__ = ["ADAPTER_VERSION", "Cmip6HumidHeatSource", "Era5HumidHeatSource", "assess_asset"]
