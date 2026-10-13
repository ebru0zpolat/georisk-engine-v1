"""ETCCDI heat indices: WSDI (primary) and TX90p (diagnostic).

Definitions (ETCCDI / Climdex):
- Calendar-day 90th percentile of TX from a baseline period, using a 5-day
  window centred on each calendar day.
- **TX90p**: percentage of days with TX > that percentile.
- **WSDI**: annual count of days belonging to spells of ≥6 consecutive days
  with TX > that percentile (spells do not span years).

Phase 1 does **not** use fixed absolute thresholds (e.g. TX > 35 °C).
"""

from __future__ import annotations

import numpy as np

MIN_SPELL_DAYS = 6
PERCENTILE = 90.0
WINDOW_HALF_WIDTH = 2  # 5-day window = centre ± 2


def _day_of_year_noleap(month: int, day: int) -> int:
    """1..365 day-of-year ignoring leap day (ETCCDI-style for noleap / 365_day)."""
    mdays = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if month == 2 and day == 29:
        return 60  # map leap day onto day-60 bucket for threshold lookup
    return int(sum(mdays[:month]) + day)


def calendar_day_keys(years: np.ndarray, months: np.ndarray, days: np.ndarray) -> np.ndarray:
    out = np.empty(len(years), dtype=np.int16)
    for i in range(len(years)):
        out[i] = _day_of_year_noleap(int(months[i]), int(days[i]))
    return out


def baseline_tx90_by_doy(
    tx_c: np.ndarray,
    doy: np.ndarray,
    in_baseline: np.ndarray,
) -> np.ndarray:
    """Return length-365 array of calendar-day 90th percentiles (°C)."""
    if tx_c.shape != doy.shape or tx_c.shape != in_baseline.shape:
        raise ValueError("tx_c, doy, and in_baseline must share shape.")
    if not np.isfinite(tx_c[in_baseline]).all():
        raise ValueError("Baseline period contains non-finite TX values.")

    thresholds = np.full(365, np.nan, dtype=float)
    base_tx = tx_c[in_baseline]
    base_doy = doy[in_baseline]
    for d in range(1, 366):
        window = [((d - 1 + k - WINDOW_HALF_WIDTH) % 365) + 1 for k in range(5)]
        mask = np.isin(base_doy, window)
        sample = base_tx[mask]
        if sample.size == 0:
            raise ValueError(f"No baseline samples for calendar-day window around DOY {d}.")
        thresholds[d - 1] = float(np.percentile(sample, PERCENTILE))
    if not np.isfinite(thresholds).all():
        raise ValueError("Non-finite TX90 baseline thresholds.")
    return thresholds


def _exceedance(tx_c: np.ndarray, doy: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    thr = thresholds[doy - 1]
    return tx_c > thr


def annual_tx90p(
    tx_c: np.ndarray,
    years: np.ndarray,
    doy: np.ndarray,
    thresholds: np.ndarray,
) -> dict[int, float]:
    """TX90p (%) per year."""
    exc = _exceedance(tx_c, doy, thresholds)
    out: dict[int, float] = {}
    for y in sorted(set(int(v) for v in years)):
        m = years == y
        n = int(m.sum())
        if n == 0:
            continue
        out[y] = float(100.0 * exc[m].sum() / n)
    return out


def annual_wsdi(
    tx_c: np.ndarray,
    years: np.ndarray,
    doy: np.ndarray,
    thresholds: np.ndarray,
    *,
    min_spell: int = MIN_SPELL_DAYS,
) -> dict[int, float]:
    """WSDI (days) per year — spells do not span years."""
    exc = _exceedance(tx_c, doy, thresholds)
    out: dict[int, float] = {}
    for y in sorted(set(int(v) for v in years)):
        m = years == y
        flags = np.asarray(exc[m], dtype=bool)
        count = 0
        run = 0
        for flag in flags:
            if flag:
                run += 1
            else:
                if run >= min_spell:
                    count += run
                run = 0
        if run >= min_spell:
            count += run
        out[y] = float(count)
    return out


def mean_dict(values: dict[int, float], start_year: int, end_year: int) -> float:
    selected = [values[y] for y in range(start_year, end_year + 1) if y in values]
    if not selected:
        raise ValueError(f"No annual index values in {start_year}-{end_year}.")
    return float(np.mean(selected))


__all__ = [
    "MIN_SPELL_DAYS",
    "PERCENTILE",
    "annual_tx90p",
    "annual_wsdi",
    "baseline_tx90_by_doy",
    "calendar_day_keys",
    "mean_dict",
]
