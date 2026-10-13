"""Map current vs baseline metrics to risk-style component scores."""

from __future__ import annotations

import numpy as np

from app.schemas.baseline import BaselineComparison


def percent_change(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return ((current - baseline) / baseline) * 100


def compare_to_baseline(
    current_values: list[float],
    baseline_values: list[float],
) -> dict[str, float]:
    current_mean = float(np.mean(current_values)) if current_values else 0.0
    baseline_mean = float(np.mean(baseline_values)) if baseline_values else 0.0

    absolute_change = current_mean - baseline_mean
    pct = percent_change(current_mean, baseline_mean)

    baseline_std = float(np.std(baseline_values)) if baseline_values else 0.0
    z_score = (
        absolute_change / baseline_std
        if baseline_std != 0
        else 0.0
    )

    return {
        "current_mean": current_mean,
        "baseline_mean": baseline_mean,
        "absolute_change": absolute_change,
        "percent_change": pct,
        "z_score": z_score,
    }


def compare_to_baseline_model(
    current_values: list[float],
    baseline_values: list[float],
) -> BaselineComparison:
    """Same as :func:`compare_to_baseline`, wrapped as a :class:`BaselineComparison`."""
    return BaselineComparison.model_validate(
        compare_to_baseline(current_values, baseline_values)
    )


def fractional_change_vs_baseline(current: float, baseline: float, baseline_epsilon: float) -> float:
    """(current − baseline) / max(|baseline|, epsilon), matching GEE feature deviation."""
    return (current - baseline) / max(abs(baseline), baseline_epsilon)


def score_from_relative_increase(relative_change: float) -> int:
    """
    Map fractional change versus baseline to a 0–100 style component score.

    Positive change increases the score (worse exposure in the industrial / pollution proxies).
    """
    r = relative_change
    if r >= 0.5:
        return 85
    if r >= 0.25:
        return 70
    if r >= 0.1:
        return 50
    if r > 0:
        return 30
    return 15


def score_from_percent_change(percent_change_vs_baseline: float) -> int:
    """Same thresholds as :func:`score_from_relative_increase` on percent (not ratio)."""
    return score_from_relative_increase(percent_change_vs_baseline / 100.0)


def score_change(percent_change: float) -> int:
    if percent_change >= 100:
        return 90
    if percent_change >= 50:
        return 75
    if percent_change >= 20:
        return 60
    if percent_change >= 0:
        return 40
    return 25


def score_from_baseline_comparison(comparison: BaselineComparison) -> int:
    """Component score from a :class:`~app.schemas.baseline.BaselineComparison` bundle."""
    return score_from_percent_change(comparison.percent_change)


#: Assumed percent-change std-dev for emission anomalies when no baseline
#: variance sample is available, used to derive an emission z-score proxy.
EMISSION_PERCENT_CHANGE_STD = 15.0

#: |z| at or above this threshold flags an emission anomaly.
EMISSION_ANOMALY_ZSCORE_THRESHOLD = 2.0


def emission_zscore_from_percent_change(percent_change_vs_baseline: float) -> float:
    """Proxy NO2 emission anomaly z-score from percent change vs baseline."""
    return percent_change_vs_baseline / EMISSION_PERCENT_CHANGE_STD


def is_emission_anomaly(z_score: float) -> bool:
    return abs(z_score) >= EMISSION_ANOMALY_ZSCORE_THRESHOLD


def coastal_exposure_score(
    sea_level_trend_mm_per_year: float,
    sst_anomaly_zscore: float,
) -> float:
    """Combine sea level rise rate and SST anomaly into a 0-1 coastal exposure score."""
    sea_level_component = min(max(sea_level_trend_mm_per_year / 10.0, 0.0), 1.0)
    sst_component = min(max(abs(sst_anomaly_zscore) / 3.0, 0.0), 1.0)
    return round(min(1.0, 0.6 * sea_level_component + 0.4 * sst_component), 3)
