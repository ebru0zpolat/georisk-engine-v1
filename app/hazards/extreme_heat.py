"""Extreme-heat hazard module (highest market coverage — §2.4).

Country-agnostic core module. Uses ERA5 temperature (°C) as the intensity driver
until pack-local heat / UTCI layers are wired. Subtypes capture chronic heat
stress vs acute heatwave proxy bands.

``valuation_date`` selects the assessment day for temperature sampling (no
lookahead beyond that date in this stub).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.geo.interfaces import RasterTile, sample_era5_temperature
from app.hazards.base import HazardModuleResult, score_to_intensity

EXTREME_HEAT_HAZARD_ID = "extreme_heat"
EXTREME_HEAT_METHODOLOGY_VERSION = "extreme-heat-hazard-v0.1"
EXTREME_HEAT_DATA_VERSION = "era5-temperature-proxy-v0.1"


class _TemperatureRaster(Protocol):
    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile: ...


def _temperature_c(
    latitude: float,
    longitude: float,
    day: str,
    *,
    raster: _TemperatureRaster | None,
) -> float:
    if raster is not None:
        return float(raster.era5_temperature(latitude, longitude, day).value)
    return float(sample_era5_temperature(latitude, longitude, day).value)


def _score_from_temperature_c(temp_c: float) -> int:
    """Map °C → 0–100 heat score (same curve as legacy flood_heat)."""
    raw = (float(temp_c) - 5.0) * (100.0 / 35.0)
    return max(0, min(100, int(round(raw))))


def _subtype_intensities(temp_c: float, composite_intensity: float) -> dict[str, float]:
    """Chronic heat stress vs acute heatwave proxies."""
    # Chronic: scales with overall warmth.
    chronic = round(min(1.0, composite_intensity * 0.9), 6)
    # Acute: kicks in harder above ~32°C.
    if temp_c >= 38.0:
        acute_weight = 1.0
    elif temp_c >= 32.0:
        acute_weight = 0.75
    elif temp_c >= 28.0:
        acute_weight = 0.45
    else:
        acute_weight = 0.2
    acute = round(min(1.0, composite_intensity * acute_weight), 6)
    return {"chronic_heat_stress": chronic, "acute_heatwave": acute}


class ExtremeHeatHazardModule:
    """Core extreme-heat hazard module — satisfies ``HazardModule``."""

    hazard_id: str = EXTREME_HEAT_HAZARD_ID
    methodology_version: str = EXTREME_HEAT_METHODOLOGY_VERSION

    def __init__(self, *, raster: _TemperatureRaster | None = None) -> None:
        self._raster = raster

    def evaluate(
        self,
        *,
        latitude: float,
        longitude: float,
        valuation_date: date,
        parameters: dict[str, Any] | None = None,
    ) -> HazardModuleResult:
        params = parameters or {}
        # Optional override for assessment day; default = valuation_date (no lookahead).
        day = str(params.get("assessment_date") or valuation_date.isoformat())
        if day > valuation_date.isoformat():
            raise ValueError(
                f"assessment_date {day} is after valuation_date "
                f"{valuation_date.isoformat()} (lookahead forbidden)."
            )
        temp_c = _temperature_c(latitude, longitude, day, raster=self._raster)
        score = _score_from_temperature_c(temp_c)
        intensity = score_to_intensity(score)
        subtypes = _subtype_intensities(temp_c, intensity)
        return HazardModuleResult(
            hazard_id=self.hazard_id,
            intensity=intensity,
            score_0_100=score,
            subtypes=subtypes,
            data_versions={"era5_temperature": EXTREME_HEAT_DATA_VERSION},
            methodology_version=self.methodology_version,
            valuation_date=valuation_date,
            latitude=latitude,
            longitude=longitude,
            metadata={
                "temperature_c": temp_c,
                "assessment_date": day,
                "input_cutoff": valuation_date.isoformat(),
            },
        )


__all__ = [
    "EXTREME_HEAT_DATA_VERSION",
    "EXTREME_HEAT_HAZARD_ID",
    "EXTREME_HEAT_METHODOLOGY_VERSION",
    "ExtremeHeatHazardModule",
]
