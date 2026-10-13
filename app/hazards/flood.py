"""Flood hazard module (highest market coverage — §2.4).

Country-agnostic core module. Uses elevation as a pluvial/fluvial exposure proxy
until HydroSAT / pack-local flood layers are wired. Coastal subtype is a distance-
independent stub driven by low-elevation bands (pack may replace later).

Respects ``valuation_date`` for lineage (no future-dated inputs in this stub).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.geo.interfaces import RasterTile, classify_elevation_band, sample_elevation
from app.hazards.base import HazardModuleResult, score_to_intensity

FLOOD_HAZARD_ID = "flood"
FLOOD_METHODOLOGY_VERSION = "flood-hazard-v0.1"
FLOOD_DATA_VERSION = "merit-dem-proxy-v0.1"


class _ElevationRaster(Protocol):
    def elevation_at(self, lat: float, lon: float) -> RasterTile: ...


def _elevation_m(
    latitude: float,
    longitude: float,
    *,
    raster: _ElevationRaster | None,
) -> float:
    if raster is not None:
        return float(raster.elevation_at(latitude, longitude).value)
    return float(sample_elevation(latitude, longitude).value)


def _composite_score_from_elevation(elevation_m: float) -> int:
    """Lower elevation → higher flood score (0–100). Same curve as legacy flood_heat."""
    raw = 95.0 - (elevation_m / 500.0) * 80.0
    return max(0, min(100, int(round(raw))))


def _subtype_intensities(elevation_m: float, composite_intensity: float) -> dict[str, float]:
    """Split composite into fluvial / pluvial / coastal proxies (sum not required)."""
    band = classify_elevation_band(elevation_m)
    # Coastal: strongest in 0–2m / 2–5m bands.
    coastal_weight = {
        "0-2m": 1.0,
        "2-5m": 0.7,
        "5-10m": 0.25,
        ">10m": 0.05,
    }[band.value]
    coastal = round(min(1.0, composite_intensity * coastal_weight), 6)
    # Pluvial: moderate everywhere; slightly higher at mid elevations (urban runoff proxy).
    pluvial = round(min(1.0, composite_intensity * (0.85 if band.value != ">10m" else 0.55)), 6)
    # Fluvial: elevated in low-lying corridors.
    fluvial = round(min(1.0, composite_intensity * (0.95 if elevation_m < 10 else 0.4)), 6)
    return {"fluvial": fluvial, "pluvial": pluvial, "coastal": coastal}


class FloodHazardModule:
    """Core flood hazard module — satisfies ``HazardModule``."""

    hazard_id: str = FLOOD_HAZARD_ID
    methodology_version: str = FLOOD_METHODOLOGY_VERSION

    def __init__(self, *, raster: _ElevationRaster | None = None) -> None:
        self._raster = raster

    def evaluate(
        self,
        *,
        latitude: float,
        longitude: float,
        valuation_date: date,
        parameters: dict[str, Any] | None = None,
    ) -> HazardModuleResult:
        _ = parameters  # reserved for pack overrides (defence standards, return periods)
        elevation_m = _elevation_m(latitude, longitude, raster=self._raster)
        score = _composite_score_from_elevation(elevation_m)
        intensity = score_to_intensity(score)
        subtypes = _subtype_intensities(elevation_m, intensity)
        return HazardModuleResult(
            hazard_id=self.hazard_id,
            intensity=intensity,
            score_0_100=score,
            subtypes=subtypes,
            data_versions={"elevation": FLOOD_DATA_VERSION},
            methodology_version=self.methodology_version,
            valuation_date=valuation_date,
            latitude=latitude,
            longitude=longitude,
            metadata={
                "elevation_m": elevation_m,
                "elevation_band": classify_elevation_band(elevation_m).value,
                # valuation_date recorded for audit / no-lookahead contract
                "input_cutoff": valuation_date.isoformat(),
            },
        )


__all__ = [
    "FLOOD_DATA_VERSION",
    "FLOOD_HAZARD_ID",
    "FLOOD_METHODOLOGY_VERSION",
    "FloodHazardModule",
]
