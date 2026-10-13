"""Reproduce the humid-heat-v1 real-data measurement of spec §5.1 on an ERA5 sample.

Usage::

    PYTHONPATH=. python scripts/humid_heat_era5_sample_check.py <era5.nc> <expected_sha256>

The input is an ERA5 hourly single-levels NetCDF with t2m, d2m and sp (CDS request in spec §5.1).
The file is not part of the repository; its SHA-256 must match before anything is computed.

Reports: hours with d2m > t2m; per-cell error of the daily CMIP6-style approximation and of
3-hourly sampling against the hourly daily-maximum Tw; and the resulting error in threshold-day
counts. The 3-hourly figures come from the engine's own ERA5 path (``era5_daily_tw``), including
its saturation tolerance (decision D3); the daily figures reproduce the superseded daily pairing.
"""

from __future__ import annotations

import hashlib
import sys

import numpy as np
import xarray as xr

from engine.climate import humid_heat as hh
from engine.climate import humid_heat_adapter as ad

CITIES = {"Dammam": (26.43, 50.10), "Doha": (25.29, 51.53), "Abu Dhabi": (24.45, 54.38), "Dubai": (25.20, 55.27)}


def main(path: str, expected_sha256: str) -> None:
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != expected_sha256.lower():
        raise SystemExit(f"SHA-256 mismatch: {digest}")
    ds = xr.open_dataset(path)
    tname = ad._time_name(ds)
    for v in ad.ERA5_HOURLY:
        ad._check_units(v, ds, ad.ERA5_UNITS)
    lat_n, lon_n = ad._spatial_names(ds)
    times = np.asarray(ds[tname].values).astype("datetime64[h]")
    start = times[0].astype("datetime64[D]").astype("datetime64[h]")
    if not np.array_equal(times, start + np.arange(times.size)) or times.size % 24:
        raise SystemExit("hourly series is not whole contiguous UTC days")

    t, d, p = (ds[v].values.astype("f8") for v in ("t2m", "d2m", "sp"))
    over = d - t
    print(f"sha256 {digest}; {times[0]} .. {times[-1]}; grid {t.shape[1]}x{t.shape[2]}")
    print(f"d2m > t2m: {int((over > 0).sum())} of {over.size} cell-hours; max excess {max(float(over.max()), 0.0):.4f} K")

    nt, ny, nx = t.shape
    hours = (0, 3, 6, 9, 12, 15, 18, 21)
    true_max = np.empty((nt // 24, ny, nx)); sampled = np.empty_like(true_max); adjusted = 0
    for i in range(ny):
        for j in range(nx):
            cell = [a[:, i, j].reshape(-1, 24) for a in (t, d, p)]
            true_max[:, i, j], sampled[:, i, j], n = hh.era5_daily_tw(*cell, hours)
            adjusted += n
    print(f"engine path: {adjusted} hourly samples treated as saturation (tolerance {hh.SATURATION_TOLERANCE_K} K)")
    q, _, _ = hh.saturation_adjust(t, hh.specific_humidity_from_e(hh.saturation_vapour_pressure_hpa(d - hh.KELVIN), p / 100.0), p)
    by_day = lambda a: a.reshape(nt // 24, 24, ny, nx)  # noqa: E731
    estimates = {
        "daily (tasmax + mean huss), superseded": hh.wet_bulb_c(by_day(t).max(axis=1), by_day(q).mean(axis=1), by_day(p).mean(axis=1)),
        "3-hourly (00..21 UTC), engine": sampled,
    }
    hot = true_max >= hh.APPROX_ERROR_HOT_DAY_C
    for name, est in estimates.items():
        diff = est - true_max
        cell_med = np.array([
            np.median(diff[:, i, j][hot[:, i, j]])
            for i in range(ny) for j in range(nx) if hot[:, i, j].sum() >= hh.APPROX_ERROR_MIN_DAYS
        ])
        print(f"\n{name}: hot-day median {np.median(diff[hot]):+.3f} C, p5 {np.percentile(diff[hot], 5):+.3f} C; "
              f"cells failing the {hh.APPROX_ERROR_LIMIT_C} C median gate {int((np.abs(cell_med) > hh.APPROX_ERROR_LIMIT_C).sum())}/{cell_med.size}")
        for thr in (28.0, 31.0):
            tc = (true_max >= thr).sum(axis=0)
            m = tc >= 5
            rel = ((est >= thr).sum(axis=0)[m] - tc[m]) / tc[m]
            print(f"  Tw>={thr:.0f} C count error over {m.sum()} cells: median {np.median(rel):+.0%}, "
                  f"p10 {np.percentile(rel, 10):+.0%}, worst {rel.min():+.0%}, "
                  f"within the ±{hh.COUNT_ERROR_LIMIT:.0%} count gate {int((np.abs(rel) <= hh.COUNT_ERROR_LIMIT).sum())}")
    lat, lon = ds[lat_n].values, ds[lon_n].values
    print()
    for name, (la, lo) in CITIES.items():
        i, j = ad._cell_index(lat, la, "latitude"), ad._cell_index(lon, lo, "longitude")
        parts = ", ".join(f"{k.split(' ')[0]} median {np.median(v[:, i, j] - true_max[:, i, j]):+.2f} C" for k, v in estimates.items())
        print(f"{name} cell ({lat[i]}, {lon[j]}): max Tw {true_max[:, i, j].max():.2f} C; {parts}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
