"""Downstream scoring flows composed from geo layer primitives (GEO-192 / GEO-7 / GEO-8)."""

from __future__ import annotations

from app.geo.interfaces import ElevationBand
from app.scoring.baseline import compare_to_baseline


def coastal_exposure_score(
    *,
    elevation_band: ElevationBand,
    distance_to_coast_km: float,
) -> int:
    """Derive a 0–100 coastal exposure component from elevation band and coast distance."""

    if distance_to_coast_km > 50.0:
        return 15
    if elevation_band is ElevationBand.BAND_0_2M:
        return 90 if distance_to_coast_km < 5.0 else 75
    if elevation_band is ElevationBand.BAND_2_5M:
        return 65
    if elevation_band is ElevationBand.BAND_5_10M:
        return 45
    return 20


def sea_level_z_score(anomaly_m: float, baseline_history_m: list[float]) -> float:
    """Z-score of a PSMSL anomaly against a historical baseline window (GEO-7 input)."""

    return compare_to_baseline([anomaly_m], baseline_history_m)["z_score"]
