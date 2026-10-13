"""Humid-heat indicator ``humid-heat-v1`` (WO-C05: method core).

Normative specification: ``docs/specs/humid-heat-indicator-v1.md``. Section
numbers in comments (§n) refer to it. This module implements the method on
already-loaded, aligned arrays; reading and merging CMIP6 / ERA5 files into
those arrays is the adapter slice and keeps the CLIM-03 contract of
``engine/climate/cmip6_heat_adapter.py``.

What this is: a thermodynamic wet-bulb temperature (Tw) and threshold-day
counts over Tw. What it is not: a WBGT, a health or productivity estimate, a
bias-corrected or downscaled value (§2).

Every refusal raises :class:`HumidHeatError` carrying a code from
:data:`BLOCKER_CODES`, or is recorded per indicator in the assessment record.
No refusal is replaced by a fill value.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

METHOD_VERSION = "humid-heat-v1"
ALGORITHM = "bolton1980-eq39-thetae-pseudoadiabat-bisection"

# -- blocker codes (§8). The single definition in this package; WO-08 moves
# them into the repository-wide registry.
HUMID_HEAT_VARIABLE_SET_INCOMPLETE = "HUMID_HEAT_VARIABLE_SET_INCOMPLETE"
HUMID_HEAT_UNIT_MISMATCH = "HUMID_HEAT_UNIT_MISMATCH"
HUMID_HEAT_GRID_MISMATCH = "HUMID_HEAT_GRID_MISMATCH"
HUMID_HEAT_INPUT_NONPHYSICAL = "HUMID_HEAT_INPUT_NONPHYSICAL"
HUMID_HEAT_SEA_CELL = "HUMID_HEAT_SEA_CELL"
HUMID_HEAT_TW_OUT_OF_BOUNDS = "HUMID_HEAT_TW_OUT_OF_BOUNDS"
HUMID_HEAT_WINDOW_INCOMPLETE = "HUMID_HEAT_WINDOW_INCOMPLETE"
HUMID_HEAT_APPROX_ERROR_EXCEEDED = "HUMID_HEAT_APPROX_ERROR_EXCEEDED"
HUMID_HEAT_APPROX_ERROR_UNMEASURED = "HUMID_HEAT_APPROX_ERROR_UNMEASURED"
HUMID_HEAT_MODEL_BASELINE_BIAS = "HUMID_HEAT_MODEL_BASELINE_BIAS"
HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED = "HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED"
SOURCE_LICENCE_UNVERIFIED = "SOURCE_LICENCE_UNVERIFIED"

BLOCKER_CODES = frozenset(
    {
        HUMID_HEAT_VARIABLE_SET_INCOMPLETE,
        HUMID_HEAT_UNIT_MISMATCH,
        HUMID_HEAT_GRID_MISMATCH,
        HUMID_HEAT_INPUT_NONPHYSICAL,
        HUMID_HEAT_SEA_CELL,
        HUMID_HEAT_TW_OUT_OF_BOUNDS,
        HUMID_HEAT_WINDOW_INCOMPLETE,
        HUMID_HEAT_APPROX_ERROR_EXCEEDED,
        HUMID_HEAT_APPROX_ERROR_UNMEASURED,
        HUMID_HEAT_MODEL_BASELINE_BIAS,
        HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED,
        SOURCE_LICENCE_UNVERIFIED,
    }
)

# -- method parameters of humid-heat-v1. Changing any bumps METHOD_VERSION.
EPSILON = 0.622  # Rd / Rv
KELVIN = 273.15
EARTH_RADIUS_KM = 6371.0088
BISECTION_STEPS = 64
LAND_FRACTION_MIN = 0.5  # §6
CMIP6_SAMPLES_PER_DAY = 8  # §3.1, 3-hourly
SATURATION_TOLERANCE_K = 0.01  # §4.4, ERA5: encoding tolerance for Td > T (decision D3)
CMIP6_SATURATION_RH_MAX = 1.10  # §4.4, CMIP6: model supersaturation up to 110 % RH (Bolton) treated as saturation (D4)
APPROX_ERROR_LIMIT_C = 1.0  # §5, sampling error of TwX and Tw_dmax_p95
APPROX_ERROR_HOT_DAY_C = 26.0  # §5
APPROX_ERROR_MIN_DAYS = 30  # §5
COUNT_ERROR_LIMIT = 0.20  # §5, relative error of each threshold-day count (decision D2)
COUNT_ERROR_MIN_TRUE_DAYS = 30  # §5
BASELINE_BIAS_LIMIT_C = 1.0  # §7.4
PERCENTILE = 95.0
REPORT_DECIMALS = 2  # §9

LIMITATIONS = (
    "single model and member per series",
    "not bias-corrected",
    "grid-cell value, not a site or building value",
    "CMIP6 daily maximum Tw is the maximum of 8 three-hourly samples, not of a continuous record",
    "thermodynamic wet-bulb temperature, not WBGT",
)

_THRESHOLDS_PATH = Path(__file__).with_name("humid_heat_thresholds_v1.json")


class HumidHeatError(ValueError):
    """Fail-closed refusal carrying a blocker code."""

    def __init__(self, code: str, message: str) -> None:
        if code not in BLOCKER_CODES:
            raise ValueError(f"unregistered blocker code {code!r}")
        super().__init__(f"{code}: {message}")
        self.code = code


# -- thermodynamics (§4) -----------------------------------------------------


def saturation_vapour_pressure_hpa(t_c: np.ndarray) -> np.ndarray:
    """Bolton (1980) over liquid water; °C in, hPa out (§4.2)."""
    t_c = np.asarray(t_c, dtype=np.float64)
    return 6.112 * np.exp(17.67 * t_c / (t_c + 243.5))


def dewpoint_c(e_hpa: np.ndarray) -> np.ndarray:
    """Inverse of :func:`saturation_vapour_pressure_hpa`."""
    x = np.log(np.asarray(e_hpa, dtype=np.float64) / 6.112)
    return 243.5 * x / (17.67 - x)


def vapour_pressure_from_q_hpa(q: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    """Vapour pressure from specific humidity (§4.1)."""
    q = np.asarray(q, dtype=np.float64)
    return q * np.asarray(p_hpa, dtype=np.float64) / (EPSILON + (1.0 - EPSILON) * q)


def specific_humidity_from_e(e_hpa: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    """Inverse of :func:`vapour_pressure_from_q_hpa`."""
    e = np.asarray(e_hpa, dtype=np.float64)
    return EPSILON * e / (np.asarray(p_hpa, dtype=np.float64) - (1.0 - EPSILON) * e)


def _mixing_ratio_gkg(e_hpa: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    return 1000.0 * EPSILON * e_hpa / (p_hpa - e_hpa)


def _theta_e(t_k: np.ndarray, p_hpa: np.ndarray, e_hpa: np.ndarray, t_l: np.ndarray) -> np.ndarray:
    """Bolton (1980) eq. 39 via θ_DL (eq. 24)."""
    r = _mixing_ratio_gkg(e_hpa, p_hpa)
    theta_dl = t_k * (1000.0 / (p_hpa - e_hpa)) ** 0.2854 * (t_k / t_l) ** (0.00028 * r)
    return theta_dl * np.exp((3.036 / t_l - 0.00178) * r * (1.0 + 0.000448 * r))


def _lcl_temperature_k(t_k: np.ndarray, e_hpa: np.ndarray) -> np.ndarray:
    """Bolton (1980) eq. 22, relative humidity taken against :func:`saturation_vapour_pressure_hpa`.

    At saturation ``T_L = T`` exactly, so saturated air returns ``Tw = T``.
    """
    rh = e_hpa / saturation_vapour_pressure_hpa(t_k - KELVIN)
    return 1.0 / (1.0 / (t_k - 55.0) - np.log(rh) / 2840.0) + 55.0


def _theta_e_of(t_k: np.ndarray, p_hpa: np.ndarray, e_hpa: np.ndarray) -> np.ndarray:
    """θE from (T, p, e): Bolton eq. 39 with T_L from eq. 22, for any state."""
    return _theta_e(t_k, p_hpa, e_hpa, _lcl_temperature_k(t_k, e_hpa))


def _theta_e_saturated(t_k: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    return _theta_e_of(t_k, p_hpa, saturation_vapour_pressure_hpa(t_k - KELVIN))


def wet_bulb_c(t_k: np.ndarray, q: np.ndarray, p_pa: np.ndarray) -> np.ndarray:
    """Thermodynamic wet-bulb temperature in °C (§4.4).

    Tw is the temperature at pressure ``p`` on the pseudo-adiabat that carries
    the parcel's Bolton θE (the quantity Davies-Jones 2008 approximates), found
    by bisection on ``[Td, T]`` with a fixed number of steps — deterministic,
    no convergence branch. Any non-physical input or a result outside
    ``Td ≤ Tw ≤ T`` refuses.
    """
    t_k = np.asarray(t_k, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    p_pa = np.asarray(p_pa, dtype=np.float64)
    t_k, q, p_pa = np.broadcast_arrays(t_k, q, p_pa)
    if not (np.isfinite(t_k).all() and np.isfinite(q).all() and np.isfinite(p_pa).all()):
        raise HumidHeatError(HUMID_HEAT_INPUT_NONPHYSICAL, "non-finite temperature, humidity or pressure")
    if (t_k <= 150.0).any() or (t_k >= 350.0).any():
        raise HumidHeatError(HUMID_HEAT_INPUT_NONPHYSICAL, "temperature outside 150–350 K")
    if (q <= 0.0).any() or (q >= 0.1).any():
        raise HumidHeatError(HUMID_HEAT_INPUT_NONPHYSICAL, "specific humidity outside (0, 0.1) kg/kg")
    if (p_pa <= 30000.0).any() or (p_pa >= 110000.0).any():
        raise HumidHeatError(HUMID_HEAT_INPUT_NONPHYSICAL, "pressure outside 300–1100 hPa")

    p_hpa = p_pa / 100.0
    e = vapour_pressure_from_q_hpa(q, p_hpa)
    td_k = dewpoint_c(e) + KELVIN
    if (td_k > t_k + 1e-9).any():
        raise HumidHeatError(HUMID_HEAT_TW_OUT_OF_BOUNDS, "supersaturated input: dewpoint above temperature")
    td_k = np.minimum(td_k, t_k)

    target = _theta_e_of(t_k, p_hpa, e)
    lo = td_k.copy()
    hi = t_k.copy()
    tol = 1e-9 * target
    if ((_theta_e_saturated(lo, p_hpa) - target) > tol).any() or (
        (_theta_e_saturated(hi, p_hpa) - target) < -tol
    ).any():
        raise HumidHeatError(HUMID_HEAT_TW_OUT_OF_BOUNDS, "θE target not bracketed by [Td, T]")
    for _ in range(BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        above = _theta_e_saturated(mid, p_hpa) > target
        hi = np.where(above, mid, hi)
        lo = np.where(above, lo, mid)
    tw_k = 0.5 * (lo + hi)
    if (tw_k < td_k - 1e-6).any() or (tw_k > t_k + 1e-6).any():
        raise HumidHeatError(HUMID_HEAT_TW_OUT_OF_BOUNDS, "Tw outside [Td, T]")
    return tw_k - KELVIN


# -- saturation tolerance and daily values (§4.4, §4.5) -----------------------


def saturation_adjust(
    t_k: np.ndarray, q: np.ndarray, p_pa: np.ndarray, *, rh_max: float | None = None
) -> tuple[np.ndarray, int, float]:
    """Treat a dewpoint above the temperature as saturation within a stated tolerance; refuse beyond it.

    Default (ERA5, decision D3): ``0 < Td − T ≤ SATURATION_TOLERANCE_K``. With ``rh_max`` (CMIP6, decision D4):
    relative humidity against §4.2 up to ``rh_max``. Returns the humidity to use, the number of samples
    adjusted and the largest excess ``Td − T`` in K; the record reports both.
    """
    t_k = np.asarray(t_k, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    p_hpa = np.asarray(p_pa, dtype=np.float64) / 100.0
    with np.errstate(invalid="ignore", divide="ignore"):
        e = vapour_pressure_from_q_hpa(q, p_hpa)
        excess = dewpoint_c(e) + KELVIN - t_k
        e_sat = saturation_vapour_pressure_hpa(t_k - KELVIN)
    if rh_max is None:
        if (excess > SATURATION_TOLERANCE_K).any():
            raise HumidHeatError(
                HUMID_HEAT_TW_OUT_OF_BOUNDS,
                f"dewpoint above temperature by {float(np.nanmax(excess)):.4f} K (> {SATURATION_TOLERANCE_K} K tolerance)",
            )
    else:
        with np.errstate(invalid="ignore", divide="ignore"):
            rh = e / e_sat
        if (rh > rh_max).any():
            raise HumidHeatError(
                HUMID_HEAT_TW_OUT_OF_BOUNDS,
                f"relative humidity {float(np.nanmax(rh)) * 100:.1f} % above the {rh_max * 100:.0f} % model tolerance",
            )
    adjust = excess > 0.0
    if not adjust.any():
        return q, 0, 0.0
    q_sat = specific_humidity_from_e(e_sat, p_hpa)
    return np.where(adjust, q_sat, q), int(adjust.sum()), round(float(excess[adjust].max()), 4)


def daily_max_tw(
    t_k: np.ndarray, q: np.ndarray, p_pa: np.ndarray, samples_per_day: int = CMIP6_SAMPLES_PER_DAY
) -> tuple[np.ndarray, int, float]:
    """Daily maximum Tw from CMIP6 sub-daily samples ordered by time.

    Returns (Tw °C per day, samples adjusted to saturation, largest excess Td − T in K); model
    supersaturation is tolerated up to ``CMIP6_SATURATION_RH_MAX`` (decision D4).
    """
    arrays = [np.asarray(a, dtype=np.float64).reshape(-1) for a in (t_k, q, p_pa)]
    if len({a.size for a in arrays}) != 1:
        raise HumidHeatError(HUMID_HEAT_GRID_MISMATCH, "sub-daily arrays differ in length")
    if arrays[0].size == 0 or arrays[0].size % samples_per_day:
        raise HumidHeatError(HUMID_HEAT_WINDOW_INCOMPLETE, f"series is not whole days of {samples_per_day} samples")
    t, qq, p = arrays
    qq, adjusted, max_excess = saturation_adjust(t, qq, p, rh_max=CMIP6_SATURATION_RH_MAX)
    tw = wet_bulb_c(t, qq, p).reshape(-1, samples_per_day)
    return tw.max(axis=1), adjusted, max_excess


def _require_hourly(name: str, values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 24:
        raise HumidHeatError(HUMID_HEAT_WINDOW_INCOMPLETE, f"{name} must be (days, 24) hourly")
    if not np.isfinite(arr).all():
        raise HumidHeatError(HUMID_HEAT_WINDOW_INCOMPLETE, f"{name} has a missing hour")
    return arr


def era5_daily_tw(
    t2m_k: np.ndarray, d2m_k: np.ndarray, sp_pa: np.ndarray, sample_hours: Sequence[int]
) -> tuple[np.ndarray, np.ndarray, int]:
    """ERA5 hourly → (true daily max Tw, daily max at the model's sample hours, samples adjusted), °C (§5)."""
    t = _require_hourly("t2m", t2m_k)
    d = _require_hourly("d2m", d2m_k)
    p = _require_hourly("sp", sp_pa)
    if t.shape != d.shape or t.shape != p.shape:
        raise HumidHeatError(HUMID_HEAT_GRID_MISMATCH, "ERA5 hourly arrays differ in shape")
    hours = sorted({int(h) for h in sample_hours})
    if not hours or hours[0] < 0 or hours[-1] > 23:
        raise HumidHeatError(HUMID_HEAT_GRID_MISMATCH, f"sample hours {list(sample_hours)} not within 0–23 UTC")
    q = specific_humidity_from_e(saturation_vapour_pressure_hpa(d - KELVIN), p / 100.0)
    q, adjusted, _ = saturation_adjust(t, q, p)
    tw = wet_bulb_c(t, q, p)
    return tw.max(axis=1), tw[:, hours].max(axis=1), adjusted


# -- windows and indicators (§7) --------------------------------------------


def _days_in_year(year: int, calendar: str) -> int:
    if calendar in {"noleap", "365_day"}:
        return 365
    if calendar not in {"standard", "gregorian", "proleptic_gregorian"}:
        raise HumidHeatError(HUMID_HEAT_UNIT_MISMATCH, f"unsupported calendar {calendar!r}")
    leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
    return 366 if leap else 365


def _window_values(
    years: np.ndarray, tw_c: np.ndarray, window: tuple[int, int], calendar: str
) -> tuple[list[int], np.ndarray, np.ndarray]:
    years = np.asarray(years, dtype=np.int64)
    tw_c = np.asarray(tw_c, dtype=np.float64)
    if years.shape != tw_c.shape:
        raise HumidHeatError(HUMID_HEAT_GRID_MISMATCH, "years and Tw differ in length")
    start, end = window
    if end - start < 1:
        raise HumidHeatError(HUMID_HEAT_WINDOW_INCOMPLETE, "single-year windows are forbidden")
    wanted = list(range(start, end + 1))
    for y in wanted:
        if int((years == y).sum()) != _days_in_year(y, calendar):
            raise HumidHeatError(HUMID_HEAT_WINDOW_INCOMPLETE, f"year {y} incomplete")
    mask = (years >= start) & (years <= end)
    return wanted, years[mask], tw_c[mask]


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    data = json.loads((path or _THRESHOLDS_PATH).read_text(encoding="utf-8"))
    if data.get("method_version") != METHOD_VERSION:
        raise ValueError("threshold file does not belong to this method version")
    return data


def window_indicators(
    years: np.ndarray,
    tw_c: np.ndarray,
    window: tuple[int, int],
    *,
    calendar: str = "standard",
    thresholds_c: Sequence[float] | None = None,
) -> dict[str, float]:
    """``TwX``, ``Tw_dmax_p95`` and ``TwD<t>`` over one complete window (§7.1–7.2)."""
    wanted, yrs, vals = _window_values(years, tw_c, window, calendar)
    if thresholds_c is None:
        thresholds_c = [row["value_c"] for row in load_thresholds()["thresholds"]]
    annual_max = [float(vals[yrs == y].max()) for y in wanted]
    out: dict[str, float] = {
        "TwX": _round(sum(annual_max) / len(annual_max)),
        "Tw_dmax_p95": _round(float(np.percentile(vals, PERCENTILE, method="linear"))),
    }
    for t in thresholds_c:
        counts = [int((vals[yrs == y] >= t).sum()) for y in wanted]
        out[f"TwD{_label(t)}"] = _round(sum(counts) / len(counts))
    return out


def _label(t: float) -> str:
    return str(int(t)) if float(t).is_integer() else str(t).replace(".", "p")


def _round(x: float) -> float:
    return round(float(x), REPORT_DECIMALS)


# -- gates (§5, §6, §7.4) ----------------------------------------------------


def sampling_error(true_max_c: np.ndarray, sampled_c: np.ndarray) -> dict[str, float | int]:
    """Median and 95th percentile of sampled − true daily max Tw on hot days (§5); gates TwX and p95."""
    true_max_c = np.asarray(true_max_c, dtype=np.float64)
    sampled_c = np.asarray(sampled_c, dtype=np.float64)
    hot = true_max_c >= APPROX_ERROR_HOT_DAY_C
    n = int(hot.sum())
    if n < APPROX_ERROR_MIN_DAYS:
        return {"hot_days": n}
    diff = sampled_c[hot] - true_max_c[hot]
    return {
        "hot_days": n,
        "median_c": _round(float(np.median(diff))),
        "p95_c": _round(float(np.percentile(diff, PERCENTILE, method="linear"))),
    }


def count_errors(
    years: np.ndarray,
    true_max_c: np.ndarray,
    sampled_c: np.ndarray,
    window: tuple[int, int],
    *,
    calendar: str = "standard",
    thresholds_c: Sequence[float] | None = None,
) -> dict[str, dict[str, float | int]]:
    """Per threshold: days over the window by the true and the sampled daily maximum (§5, decision D2)."""
    _, yrs, true_vals = _window_values(years, true_max_c, window, calendar)
    _, _, sampled_vals = _window_values(years, sampled_c, window, calendar)
    if thresholds_c is None:
        thresholds_c = [row["value_c"] for row in load_thresholds()["thresholds"]]
    out: dict[str, dict[str, float | int]] = {}
    for t in thresholds_c:
        n_true = int((true_vals >= t).sum())
        entry: dict[str, float | int] = {"true_days": n_true, "sampled_days": int((sampled_vals >= t).sum())}
        if n_true >= COUNT_ERROR_MIN_TRUE_DAYS:
            entry["relative_error"] = _round((entry["sampled_days"] - n_true) / n_true)
        out[f"TwD{_label(t)}"] = entry
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class GridCell:
    lat: float
    lon: float
    land_fraction: float  # 0–1 (CMIP6 sftlf / 100, ERA5 lsm)
    resolution_deg: float
    orog_m: float | None = None

    def check(self, asset_lat: float, asset_lon: float) -> dict[str, float]:
        if not 0.0 <= self.land_fraction <= 1.0:
            raise HumidHeatError(HUMID_HEAT_UNIT_MISMATCH, "land fraction must be in [0, 1]")
        if self.land_fraction < LAND_FRACTION_MIN:
            raise HumidHeatError(
                HUMID_HEAT_SEA_CELL, f"cell land fraction {self.land_fraction:.2f} < {LAND_FRACTION_MIN}"
            )
        return {
            "grid_resolution_deg": self.resolution_deg,
            "cell_distance_km": _round(haversine_km(asset_lat, asset_lon, self.lat, self.lon)),
            "cell_land_fraction": self.land_fraction,
        }


# -- assessment --------------------------------------------------------------


@dataclass(frozen=True)
class DailySeries:
    """One series' aligned daily arrays plus identity (supplied by the adapter)."""

    years: np.ndarray
    tw_c: np.ndarray
    calendar: str
    identity: Mapping[str, Any]
    pressure_source: str
    files: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    licence_verified: bool = False
    saturation_adjusted: int = 0
    saturation_max_excess_k: float = 0.0
    sample_hours: tuple[int, ...] = ()
    edge_samples_trimmed: int = 0


ABSOLUTE_INDICATOR_PREFIXES = ("TwX", "Tw_dmax_p95", "TwD")


def assess(
    *,
    asset_lat: float,
    asset_lon: float,
    model_cell: GridCell,
    model: DailySeries,
    era5: DailySeries,
    era5_sampled_c: np.ndarray,
    baseline: tuple[int, int] = (1991, 2020),
    horizons: Sequence[tuple[int, int]] = ((2021, 2040), (2041, 2060)),
    thresholds_c: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build the §11 record for one asset and one model series.

    ``era5`` carries the true (hourly) daily maximum; ``era5_sampled_c`` the daily maximum at the
    model's sample hours, aligned with ``era5.years``. Gates refuse whole indicators and name the
    blocker; nothing is filled in. A sea cell or an incomplete window raises.
    """
    cell = model_cell.check(asset_lat, asset_lon)
    blockers: list[str] = [HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED]
    for src in (model, era5):
        if not src.licence_verified and SOURCE_LICENCE_UNVERIFIED not in blockers:
            blockers.append(SOURCE_LICENCE_UNVERIFIED)

    kw = {"thresholds_c": thresholds_c}
    era5_base = window_indicators(era5.years, era5.tw_c, baseline, calendar=era5.calendar, **kw)
    era5_sampled_base = window_indicators(era5.years, era5_sampled_c, baseline, calendar=era5.calendar, **kw)
    model_base = window_indicators(model.years, model.tw_c, baseline, calendar=model.calendar, **kw)
    temperature_error = sampling_error(
        _window_values(era5.years, era5.tw_c, baseline, era5.calendar)[2],
        _window_values(era5.years, era5_sampled_c, baseline, era5.calendar)[2],
    )
    counts_error = count_errors(era5.years, era5.tw_c, era5_sampled_c, baseline, calendar=era5.calendar, **kw)
    # Model climate against the observed climate sampled the same way, so sampling does not count as bias.
    bias = _round(model_base["TwX"] - era5_sampled_base["TwX"])

    refused: dict[str, str] = {}

    def gate(key: str) -> str | None:
        if any(key.startswith(p) for p in ABSOLUTE_INDICATOR_PREFIXES) and abs(bias) > BASELINE_BIAS_LIMIT_C:
            return HUMID_HEAT_MODEL_BASELINE_BIAS
        if key.startswith("TwD"):
            entry = counts_error[key]
            if "relative_error" not in entry:
                return HUMID_HEAT_APPROX_ERROR_UNMEASURED
            if abs(entry["relative_error"]) > COUNT_ERROR_LIMIT:
                return HUMID_HEAT_APPROX_ERROR_EXCEEDED
            return None
        if "median_c" not in temperature_error:
            return HUMID_HEAT_APPROX_ERROR_UNMEASURED
        if abs(temperature_error["median_c"]) > APPROX_ERROR_LIMIT_C:
            return HUMID_HEAT_APPROX_ERROR_EXCEEDED
        return None

    windows: dict[str, dict[str, float]] = {}
    for label, values in [(f"{baseline[0]}-{baseline[1]}", model_base)] + [
        (f"{h[0]}-{h[1]}", window_indicators(model.years, model.tw_c, h, calendar=model.calendar, **kw))
        for h in horizons
    ]:
        kept: dict[str, float] = {}
        for key, val in values.items():
            code = gate(key)
            if code:
                refused[f"{label}:{key}"] = code
                if code not in blockers:
                    blockers.append(code)
            else:
                kept[key] = val
        if label != f"{baseline[0]}-{baseline[1]}":
            kept["dTwX"] = _round(values["TwX"] - model_base["TwX"])
        windows[label] = kept

    return {
        "method_version": METHOD_VERSION,
        "algorithm": ALGORITHM,
        **{k: model.identity[k] for k in sorted(model.identity)},
        "files": [dict(f) for f in model.files],
        "pressure_source": model.pressure_source,
        "orog_m": model_cell.orog_m,
        **cell,
        "sampling": {
            "model_sample_hours_utc": list(model.sample_hours),
            "saturation_adjusted_samples": {"model": model.saturation_adjusted, "era5": era5.saturation_adjusted},
            "saturation_max_excess_k": {"model": model.saturation_max_excess_k, "era5": era5.saturation_max_excess_k},
            "saturation_tolerance": {"era5_k": SATURATION_TOLERANCE_K, "model_rh_max": CMIP6_SATURATION_RH_MAX},
            "model_edge_samples_trimmed": model.edge_samples_trimmed,
        },
        "era5_baseline": era5_base,
        "era5_baseline_sampled": era5_sampled_base,
        "windows": windows,
        "approx_error": {"temperature": temperature_error, "counts": counts_error},
        "baseline_bias_c": bias,
        "refused": refused,
        "blockers": blockers,
        "limitations": list(LIMITATIONS),
    }


__all__ = [
    "ALGORITHM",
    "BLOCKER_CODES",
    "DailySeries",
    "GridCell",
    "HumidHeatError",
    "METHOD_VERSION",
    "assess",
    "count_errors",
    "daily_max_tw",
    "era5_daily_tw",
    "load_thresholds",
    "sampling_error",
    "saturation_adjust",
    "wet_bulb_c",
    "window_indicators",
]
