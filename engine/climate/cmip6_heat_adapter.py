"""CLIM-03: deterministic CDS CMIP6 ``tasmax`` adapter (fail-closed).

Module path: ``engine/climate/cmip6_heat_adapter.py``

Approved Phase 1 contract:
- Source: Copernicus CDS **CMIP6** (historical + SSP experiments)
- Primary indicator: **WSDI** (ETCCDI); diagnostic: **TX90p**
- Baseline climatology: **1991–2020** (requires historical+SSP merge, since
  CMIP6 historical ends 2014 and SSP experiments start 2015)
- Scenario set: SSP2-4.5 **and** SSP5-8.5 (one adapter instance per scenario
  series; the manifest binds historical + one SSP per model/member)
- SHA-256 file integrity: **mandatory per file**
- Licence: versioned **model allowlist** + commercial-use gate; production
  allowlist must be ``verified: true`` (free-text ``licence`` strings alone
  are insufficient)
- Calendar: cftime-safe (standard/gregorian/proleptic_gregorian/noleap/365_day)
- Window completeness: baseline and horizon years must have **complete daily
  coverage** — a single date inside the window is not enough
- Nearest-neighbour only inside the grid domain (no silent edge snap)
- Identity (domain / dataset / model / member / scenario / licence) from
  manifest and/or NetCDF global attributes — never hard-coded

Does **not** invent climate horizons or fall back to stubs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import xarray as xr

from engine.climate.indices_etccdi import (
    MIN_SPELL_DAYS,
    annual_tx90p,
    annual_wsdi,
    baseline_tx90_by_doy,
    calendar_day_keys,
    mean_dict,
)

SUPPORTED_VARIABLE = "tasmax"
SUPPORTED_UNITS = ("K", "Kelvin", "celsius", "Celsius", "C", "degC", "degree_Celsius")
SUPPORTED_CALENDARS = ("standard", "gregorian", "proleptic_gregorian", "noleap", "365_day")
ADAPTER_VERSION = "cmip6-heat-adapter-v0.3"

# Approved Phase 1 baseline (Decision Record): WMO 1991–2020.
DEFAULT_BASELINE_START = 1991
DEFAULT_BASELINE_END = 2020

# Approved Phase 1 scenario set. One adapter instance carries one SSP series;
# the Decision Record requires both to be produced for the pilot.
APPROVED_SCENARIOS = ("ssp245", "ssp585")

_IDENTITY_KEYS = ("domain", "dataset_id", "model_id", "member_id", "scenario_id", "licence")

_ALLOWLIST_PATH = Path(__file__).with_name("cmip6_model_licences_v1.json")


class Cmip6AdapterError(ValueError):
    """Fail-closed climate adapter error (unsupported or corrupt input)."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _norm_unit(units: str) -> str:
    return units.strip()


def _is_kelvin(units: str) -> bool:
    return _norm_unit(units) in {"K", "Kelvin"}


def _is_celsius(units: str) -> bool:
    return _norm_unit(units) in {"celsius", "Celsius", "C", "degC", "degree_Celsius"}


def _load_manifest(manifest: str | Path | Mapping[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        return {}
    if isinstance(manifest, Mapping):
        return dict(manifest)
    path = Path(manifest)
    if not path.is_file():
        raise Cmip6AdapterError(f"Manifest not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise Cmip6AdapterError(f"Manifest could not be parsed: {path} ({exc})") from exc
    if not isinstance(raw, dict):
        raise Cmip6AdapterError(f"Manifest must be a JSON object: {path}")
    return raw


def _load_licence_allowlist(
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        allowlist = dict(override)
    else:
        try:
            allowlist = json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise Cmip6AdapterError(
                f"Model licence allowlist unreadable: {_ALLOWLIST_PATH} ({exc})"
            ) from exc
    if "allowlist_version" not in allowlist or "models" not in allowlist:
        raise Cmip6AdapterError(
            "Licence allowlist must carry 'allowlist_version' and 'models'."
        )
    # Production allowlist (loaded from disk) must be licence-gate closed.
    # Test overrides may omit `verified` or set it explicitly for negative cases.
    if override is None and allowlist.get("verified") is not True:
        raise Cmip6AdapterError(
            f"Licence allowlist {allowlist.get('allowlist_version')!r} is not "
            "verified (licence-gate open); refusing to proceed."
        )
    return allowlist


def _attr_first(attrs: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in attrs and attrs[key] is not None and str(attrs[key]).strip():
            return str(attrs[key]).strip()
    return None


def _expected_days_in_year(year: int, calendar: str) -> int:
    cal = calendar.lower()
    if cal in {"noleap", "365_day"}:
        return 365
    leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    return 366 if leap else 365


class _SourceFile:
    """One validated NetCDF member of the merged series."""

    def __init__(self, path: Path, sha256: str, *, engine: str) -> None:
        self.path = path
        if not path.is_file():
            raise Cmip6AdapterError(f"Climate file not found: {path}")
        if not sha256 or not str(sha256).strip():
            raise Cmip6AdapterError(
                f"CLIM-03 requires a SHA-256 for every climate file (missing for {path.name})."
            )
        self.sha256 = _sha256_file(path)
        if self.sha256.lower() != str(sha256).strip().lower():
            raise Cmip6AdapterError(
                f"Climate file checksum mismatch for {path.name}: "
                f"expected {str(sha256).strip().lower()}, got {self.sha256.lower()}."
            )
        try:
            time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
            self.dataset = xr.open_dataset(path, engine=engine, decode_times=time_coder)
        except Exception as exc:  # noqa: BLE001
            raise Cmip6AdapterError(
                f"Climate file could not be opened or is corrupt: {path} ({exc})"
            ) from exc


class Cmip6HeatAdapter:
    """Read/validate CMIP6 ``tasmax`` (historical + SSP) and compute WSDI + TX90p."""

    SUPPORTED_VARIABLE = SUPPORTED_VARIABLE
    SUPPORTED_UNITS = SUPPORTED_UNITS
    SUPPORTED_CALENDARS = SUPPORTED_CALENDARS

    def __init__(
        self,
        file_path: str | Path | None = None,
        *,
        expected_sha256: str | None = None,
        manifest: str | Path | Mapping[str, Any] | None = None,
        engine: str = "netcdf4",
        licence_allowlist: Mapping[str, Any] | None = None,
    ) -> None:
        self.manifest = _load_manifest(manifest)
        self._allowlist = _load_licence_allowlist(licence_allowlist)

        files_spec = self.manifest.get("files")
        sources: list[tuple[Path, str, str | None]] = []
        if files_spec:
            if not isinstance(files_spec, list) or not files_spec:
                raise Cmip6AdapterError("Manifest 'files' must be a non-empty list.")
            base_dir = None
            manifest_path = self.manifest.get("__manifest_dir__")
            if manifest_path:
                base_dir = Path(manifest_path)
            for row in files_spec:
                if not isinstance(row, Mapping):
                    raise Cmip6AdapterError("Each manifest file entry must be an object.")
                raw_path = row.get("path")
                if not raw_path:
                    raise Cmip6AdapterError("Manifest file entry missing 'path'.")
                p = Path(raw_path)
                if base_dir is not None and not p.is_absolute():
                    p = base_dir / p
                sources.append((p, str(row.get("sha256", "")), row.get("experiment_id")))
        else:
            if file_path is None:
                raise Cmip6AdapterError(
                    "Provide file_path (+ expected_sha256) or a manifest with 'files'."
                )
            checksum = (expected_sha256 or self.manifest.get("sha256") or "").strip()
            sources.append((Path(file_path), checksum, None))

        opened: list[_SourceFile] = []
        try:
            for path, sha, _exp in sources:
                opened.append(_SourceFile(path, sha, engine=engine))
            self._files = opened
            self.file_records = [
                {
                    "file_name": src.path.name,
                    "file_sha256": src.sha256,
                    "experiment_id": exp
                    or _attr_first(dict(src.dataset.attrs), "experiment_id", "experiment"),
                }
                for src, (_p, _s, exp) in zip(opened, sources, strict=True)
            ]
            self.dataset = self._merge_and_validate([src.dataset for src in opened])
            self._lat_name, self._lon_name = self._resolve_spatial_names()
            self._validate_variable_and_calendar()
            self.identity = self._resolve_identity()
            self._enforce_licence_gate()
        except Exception:
            for src in opened:
                src.dataset.close()
            raise

    # -- lifecycle -----------------------------------------------------------

    def __enter__(self) -> Cmip6HeatAdapter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        for src in getattr(self, "_files", []):
            src.dataset.close()
        self._files = []
        self.dataset = None  # type: ignore[assignment]

    # -- provenance ----------------------------------------------------------

    def provenance(self) -> dict[str, Any]:
        """Machine-readable stamps — identity from file/manifest only."""
        return {
            "adapter_version": ADAPTER_VERSION,
            "variable": SUPPORTED_VARIABLE,
            "primary_indicator": "WSDI",
            "diagnostic_indicator": "TX90p",
            "spatial_method": "nearest_neighbor_in_domain",
            "bias_corrected": False,
            "files": list(self.file_records),
            "licence_allowlist_version": self._allowlist["allowlist_version"],
            **self.identity,
        }

    # -- merge & validation --------------------------------------------------

    def _merge_and_validate(self, datasets: list[xr.Dataset]) -> xr.Dataset:
        for ds in datasets:
            if SUPPORTED_VARIABLE not in ds.variables:
                raise Cmip6AdapterError(
                    f"Unsupported dataset: variable {SUPPORTED_VARIABLE!r} not found."
                )
            if "time" not in ds.coords and "time" not in ds.variables:
                raise Cmip6AdapterError("Unsupported dataset: missing time coordinate.")

        if len(datasets) == 1:
            return datasets[0]

        # Deterministic merge: same model/member/units/calendar; sort by first
        # timestamp; forbid overlap and duplicates.
        def _ident(ds: xr.Dataset) -> tuple[str | None, str | None]:
            a = dict(ds.attrs)
            return (
                _attr_first(a, "source_id", "model_id", "source"),
                _attr_first(a, "variant_label", "member_id", "realization"),
            )

        idents = {_ident(ds) for ds in datasets}
        if len(idents) > 1:
            raise Cmip6AdapterError(
                f"Refusing merge: model/member identity differs across files: {sorted(idents)}."
            )

        units_set = {str(ds[SUPPORTED_VARIABLE].attrs.get("units", "")) for ds in datasets}
        if len(units_set) > 1:
            raise Cmip6AdapterError(
                f"Refusing merge: unit mismatch across files: {sorted(units_set)}."
            )
        calendars = {self._calendar_of(ds) for ds in datasets}
        if len(calendars) > 1:
            raise Cmip6AdapterError(
                f"Refusing merge: calendar mismatch across files: {sorted(calendars)}."
            )

        ordered = sorted(datasets, key=lambda ds: ds.time.values[0])
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if not (earlier.time.values[-1] < later.time.values[0]):
                raise Cmip6AdapterError(
                    "Refusing merge: time overlap or duplicate timestamps between "
                    f"{earlier.attrs.get('experiment_id', '?')} and "
                    f"{later.attrs.get('experiment_id', '?')} files."
                )
        merged = xr.concat(ordered, dim="time", combine_attrs="drop_conflicts")
        return merged

    @staticmethod
    def _calendar_of(ds: xr.Dataset) -> str:
        cal = (
            ds.time.encoding.get("calendar")
            or ds.time.attrs.get("calendar")
        )
        if cal is None:
            first = np.asarray(ds.time.values).reshape(-1)[0]
            cal = getattr(first, "calendar", "standard")
        return str(cal).lower()

    def _resolve_spatial_names(self) -> tuple[str, str]:
        names = set(self.dataset.coords) | set(self.dataset.variables)
        lat = next((n for n in ("lat", "latitude") if n in names), None)
        lon = next((n for n in ("lon", "longitude") if n in names), None)
        if lat is None or lon is None:
            raise Cmip6AdapterError(
                "Unsupported spatial axes: need 1-D lat/latitude and lon/longitude "
                f"(found coords/vars: {sorted(names)})."
            )
        lat_da = self.dataset[lat]
        lon_da = self.dataset[lon]
        if getattr(lat_da, "ndim", 0) != 1 or getattr(lon_da, "ndim", 0) != 1:
            raise Cmip6AdapterError(
                "CLIM-03 Phase 1 rejects 2-D/curvilinear lat/lon grids "
                "(fails closed; nearest-neighbour on 1-D axes only)."
            )
        return lat, lon

    def _validate_variable_and_calendar(self) -> None:
        da = self.dataset[SUPPORTED_VARIABLE]
        units = da.attrs.get("units")
        if units is None or _norm_unit(str(units)) not in SUPPORTED_UNITS:
            raise Cmip6AdapterError(
                f"Unsupported units: {units!r}. Expected one of {list(SUPPORTED_UNITS)}."
            )
        self._calendar = self._calendar_of(self.dataset)
        if self._calendar not in SUPPORTED_CALENDARS:
            raise Cmip6AdapterError(
                f"Unsupported calendar: {self._calendar!r}. "
                f"Expected one of {list(SUPPORTED_CALENDARS)}."
            )

    def _resolve_identity(self) -> dict[str, str]:
        attrs = dict(self.dataset.attrs)
        merged = {
            "domain": self.manifest.get("domain")
            or _attr_first(attrs, "domain", "realm_domain"),
            "dataset_id": self.manifest.get("dataset_id")
            or _attr_first(attrs, "dataset_id", "tracking_id", "id", "title"),
            "model_id": self.manifest.get("model_id")
            or _attr_first(attrs, "model_id", "source_id", "source"),
            "member_id": self.manifest.get("member_id")
            or _attr_first(attrs, "member_id", "variant_label", "realization"),
            "scenario_id": self.manifest.get("scenario_id")
            or _attr_first(attrs, "scenario_id", "experiment_id", "experiment"),
            "licence": self.manifest.get("licence")
            or self.manifest.get("license")
            or _attr_first(attrs, "licence", "license", "licence_type"),
        }
        missing = [k for k in _IDENTITY_KEYS if not merged.get(k)]
        if missing:
            raise Cmip6AdapterError(
                "Missing required climate identity fields "
                f"{missing}; supply via manifest and/or NetCDF global attributes "
                "(do not hard-code in the adapter)."
            )
        return {k: str(merged[k]) for k in _IDENTITY_KEYS}

    def _enforce_licence_gate(self) -> None:
        """Versioned model allowlist + commercial-use check (fail closed)."""
        model = self.identity["model_id"]
        entry = self._allowlist.get("models", {}).get(model)
        if entry is None:
            raise Cmip6AdapterError(
                f"Model {model!r} is not in licence allowlist "
                f"{self._allowlist['allowlist_version']}; commercial use unverified — "
                "refusing to proceed."
            )
        if not entry.get("commercial_use", False):
            raise Cmip6AdapterError(
                f"Model {model!r} licence ({entry.get('licence')!r}) does not permit "
                "commercial use per allowlist "
                f"{self._allowlist['allowlist_version']}; refusing to proceed."
            )

    # -- spatial gates ---------------------------------------------------------

    def _assert_in_domain(self, lat: float, lon: float) -> None:
        """Fail if the query is outside the grid domain (no silent edge snap)."""
        lat_vals = np.asarray(self.dataset[self._lat_name].values, dtype=float)
        lon_vals = np.asarray(self.dataset[self._lon_name].values, dtype=float)
        lat_min, lat_max = float(np.min(lat_vals)), float(np.max(lat_vals))
        lon_min, lon_max = float(np.min(lon_vals)), float(np.max(lon_vals))
        if lat < lat_min or lat > lat_max or lon < lon_min or lon > lon_max:
            raise Cmip6AdapterError(
                f"Coordinates ({lat}, {lon}) outside data domain "
                f"lat[{lat_min}, {lat_max}] lon[{lon_min}, {lon_max}]; "
                "refusing silent nearest-edge snap."
            )

        lat_idx = int(np.argmin(np.abs(lat_vals - lat)))
        lon_idx = int(np.argmin(np.abs(lon_vals - lon)))

        def _half_step(axis: np.ndarray, idx: int) -> float:
            if axis.size == 1:
                return 0.5
            if idx == 0:
                return abs(float(axis[1] - axis[0])) / 2.0
            if idx == axis.size - 1:
                return abs(float(axis[-1] - axis[-2])) / 2.0
            return min(
                abs(float(axis[idx] - axis[idx - 1])) / 2.0,
                abs(float(axis[idx + 1] - axis[idx])) / 2.0,
            )

        if abs(lat - float(lat_vals[lat_idx])) > _half_step(lat_vals, lat_idx) + 1e-9:
            raise Cmip6AdapterError(
                f"Latitude {lat} is outside the Voronoi cell of nearest grid latitude "
                f"{float(lat_vals[lat_idx])}; refusing silent snap."
            )
        if abs(lon - float(lon_vals[lon_idx])) > _half_step(lon_vals, lon_idx) + 1e-9:
            raise Cmip6AdapterError(
                f"Longitude {lon} is outside the Voronoi cell of nearest grid longitude "
                f"{float(lon_vals[lon_idx])}; refusing silent snap."
            )

    def _tasmax_celsius_point(self, lat: float, lon: float) -> xr.DataArray:
        if self.dataset is None:
            raise Cmip6AdapterError("Adapter is closed.")
        self._assert_in_domain(lat, lon)
        da = self.dataset[SUPPORTED_VARIABLE]
        try:
            da_point = da.sel(
                {self._lat_name: lat, self._lon_name: lon},
                method="nearest",
            )
        except Exception as exc:  # noqa: BLE001
            raise Cmip6AdapterError(
                f"Nearest-cell selection failed for ({lat}, {lon}): {exc}"
            ) from exc

        units = str(da.attrs.get("units", ""))
        if _is_kelvin(units):
            return da_point - 273.15
        if _is_celsius(units):
            return da_point
        raise Cmip6AdapterError(f"Unsupported units at read time: {units!r}.")

    # -- completeness ----------------------------------------------------------

    def _assert_years_complete(
        self,
        years: np.ndarray,
        start_year: int,
        end_year: int,
        *,
        label: str,
    ) -> None:
        """Every year in [start_year, end_year] must have full daily coverage."""
        counts: dict[int, int] = {}
        for y in years:
            yi = int(y)
            counts[yi] = counts.get(yi, 0) + 1
        for y in range(start_year, end_year + 1):
            expected = _expected_days_in_year(y, self._calendar)
            present = counts.get(y, 0)
            if present < expected:
                raise Cmip6AdapterError(
                    f"{label} year {y} incomplete: {present}/{expected} daily steps "
                    "present; refusing partial-coverage computation."
                )
            if present > expected:
                raise Cmip6AdapterError(
                    f"{label} year {y} has duplicate timestamps: "
                    f"{present}/{expected}; refusing."
                )

    @staticmethod
    def _reject_non_finite(values: np.ndarray, *, context: str) -> None:
        if values.size == 0:
            raise Cmip6AdapterError(f"Empty array ({context}).")
        if not np.isfinite(values).all():
            raise Cmip6AdapterError(
                f"Non-finite values (NaN/±inf) detected ({context}); refusing to compute."
            )

    # -- indices ---------------------------------------------------------------

    def get_heat_indices(
        self,
        lat: float,
        lon: float,
        start_year: int,
        end_year: int,
        *,
        baseline_start: int | None = None,
        baseline_end: int | None = None,
    ) -> dict[str, Any]:
        """Mean WSDI (days) and TX90p (%) over the horizon window.

        Baseline percentiles default to **1991–2020** (Decision Record) or
        manifest overrides. Both windows require complete daily coverage.
        """
        if start_year > end_year:
            raise Cmip6AdapterError(
                f"Invalid window: start_year ({start_year}) > end_year ({end_year})."
            )
        if not np.isfinite(lat) or not np.isfinite(lon):
            raise Cmip6AdapterError(f"Non-finite coordinates: lat={lat}, lon={lon}.")

        b_start = int(
            baseline_start
            if baseline_start is not None
            else self.manifest.get("baseline_start", DEFAULT_BASELINE_START)
        )
        b_end = int(
            baseline_end
            if baseline_end is not None
            else self.manifest.get("baseline_end", DEFAULT_BASELINE_END)
        )
        if b_start > b_end:
            raise Cmip6AdapterError(f"Invalid baseline window: {b_start}-{b_end}.")

        da_c = self._tasmax_celsius_point(lat, lon)

        # cftime-safe date parts (works for numpy datetime64 and cftime).
        time = da_c["time"]
        years = np.asarray(time.dt.year.values, dtype=int)
        months = np.asarray(time.dt.month.values, dtype=int)
        days = np.asarray(time.dt.day.values, dtype=int)
        if years.size == 0:
            raise Cmip6AdapterError("Time axis is empty.")

        self._assert_years_complete(years, b_start, b_end, label="Baseline")
        self._assert_years_complete(years, start_year, end_year, label="Horizon")

        doy = calendar_day_keys(years, months, days)
        tx = np.asarray(da_c.values, dtype=float).reshape(-1)
        self._reject_non_finite(tx, context=f"full series at ({lat}, {lon})")

        in_baseline = (years >= b_start) & (years <= b_end)
        try:
            thresholds = baseline_tx90_by_doy(tx, doy, in_baseline)
            wsdi = annual_wsdi(tx, years, doy, thresholds, min_spell=MIN_SPELL_DAYS)
            tx90p = annual_tx90p(tx, years, doy, thresholds)
            wsdi_mean = mean_dict(wsdi, start_year, end_year)
            tx90p_mean = mean_dict(tx90p, start_year, end_year)
        except ValueError as exc:
            raise Cmip6AdapterError(str(exc)) from exc

        self._reject_non_finite(
            np.array([wsdi_mean, tx90p_mean], dtype=float),
            context="index means",
        )

        return {
            "wsdi_mean_annual_days": wsdi_mean,
            "tx90p_mean_annual_pct": tx90p_mean,
            "baseline_start": b_start,
            "baseline_end": b_end,
            "horizon_start": start_year,
            "horizon_end": end_year,
            "primary_indicator": "WSDI",
            "diagnostic_indicator": "TX90p",
            "provenance": self.provenance(),
        }


# Back-compat error alias for earlier CLIM-03 imports.
CordexAdapterError = Cmip6AdapterError


__all__ = [
    "ADAPTER_VERSION",
    "APPROVED_SCENARIOS",
    "DEFAULT_BASELINE_END",
    "DEFAULT_BASELINE_START",
    "SUPPORTED_CALENDARS",
    "SUPPORTED_UNITS",
    "SUPPORTED_VARIABLE",
    "Cmip6AdapterError",
    "Cmip6HeatAdapter",
    "CordexAdapterError",
]
