"""Wildfire hazard module (Mediterranean / Türkiye tourism-coast peril).

Country-agnostic core module. The intensity driver is a **fire-danger index**
(Canadian FWI scale, as published by Copernicus CEMS / EFFIS) sampled at the
asset for the assessment day. Until a fire-danger raster is wired, the module
derives a labelled **temperature proxy** from ERA5 (hot days → higher danger);
that proxy carries no fuel, wind, humidity or drought term and is stamped as
such in ``data_versions`` so it can never be mistaken for a real FWI field.

Subtypes split the composite into the two ways a building is lost to a
wildland fire: direct flame contact at the wildland–urban interface, and ember
attack (the dominant ignition path for structures in Mediterranean fires).

``valuation_date`` selects the assessment day (no lookahead).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.geo.interfaces import RasterTile, sample_era5_temperature
from app.hazards.base import HazardModuleResult, score_to_intensity

WILDFIRE_HAZARD_ID = "wildfire"
WILDFIRE_METHODOLOGY_VERSION = "wildfire-hazard-v0.1"
WILDFIRE_FIRE_DANGER_DATA_VERSION = "fire-danger-index-v0.1"
WILDFIRE_PROXY_DATA_VERSION = "era5-temperature-fwi-proxy-v0.1"

#: FWI at or above this value maps to the maximum score (EFFIS "very extreme").
FWI_SATURATION = 60.0


class _FireDangerRaster(Protocol):
    def fire_danger_index(self, lat: float, lon: float, date: str) -> RasterTile: ...


class _TemperatureRaster(Protocol):
    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile: ...


def fwi_proxy_from_temperature_c(temp_c: float) -> float:
    """Temperature-only FWI proxy: 0 at ≤15 °C, rising 2.5 FWI per °C, capped at saturation."""
    return max(0.0, min(FWI_SATURATION, (float(temp_c) - 15.0) * 2.5))


def _score_from_fwi(fwi: float) -> int:
    raw = (max(0.0, float(fwi)) / FWI_SATURATION) * 100.0
    return max(0, min(100, int(round(raw))))


def _subtype_intensities(fwi: float, composite_intensity: float) -> dict[str, float]:
    """Ember attack dominates from moderate danger; direct flame needs high danger."""
    ember_weight = 1.0 if fwi >= 20.0 else 0.6
    if fwi >= 50.0:
        flame_weight = 1.0
    elif fwi >= 35.0:
        flame_weight = 0.7
    elif fwi >= 20.0:
        flame_weight = 0.4
    else:
        flame_weight = 0.15
    return {
        "ember_attack": round(min(1.0, composite_intensity * ember_weight), 6),
        "direct_flame": round(min(1.0, composite_intensity * flame_weight), 6),
    }


class WildfireHazardModule:
    """Core wildfire hazard module — satisfies ``HazardModule``."""

    hazard_id: str = WILDFIRE_HAZARD_ID
    methodology_version: str = WILDFIRE_METHODOLOGY_VERSION

    def __init__(
        self,
        *,
        fire_danger: _FireDangerRaster | None = None,
        raster: _TemperatureRaster | None = None,
    ) -> None:
        self._fire_danger = fire_danger
        self._raster = raster

    def _fwi(self, latitude: float, longitude: float, day: str) -> tuple[float, str, dict[str, Any]]:
        if self._fire_danger is not None:
            tile = self._fire_danger.fire_danger_index(latitude, longitude, day)
            return float(tile.value), WILDFIRE_FIRE_DANGER_DATA_VERSION, {
                "fire_danger_source": tile.source,
                "fwi_basis": "fire_danger_index",
            }
        if self._raster is not None:
            temp_c = float(self._raster.era5_temperature(latitude, longitude, day).value)
        else:
            temp_c = float(sample_era5_temperature(latitude, longitude, day).value)
        return fwi_proxy_from_temperature_c(temp_c), WILDFIRE_PROXY_DATA_VERSION, {
            "temperature_c": temp_c,
            "fwi_basis": "temperature_proxy_no_fuel_wind_humidity",
        }

    def evaluate(
        self,
        *,
        latitude: float,
        longitude: float,
        valuation_date: date,
        parameters: dict[str, Any] | None = None,
    ) -> HazardModuleResult:
        params = parameters or {}
        day = str(params.get("assessment_date") or valuation_date.isoformat())
        if day > valuation_date.isoformat():
            raise ValueError(
                f"assessment_date {day} is after valuation_date "
                f"{valuation_date.isoformat()} (lookahead forbidden)."
            )
        fwi, data_version, detail = self._fwi(latitude, longitude, day)
        score = _score_from_fwi(fwi)
        intensity = score_to_intensity(score)
        return HazardModuleResult(
            hazard_id=self.hazard_id,
            intensity=intensity,
            score_0_100=score,
            subtypes=_subtype_intensities(fwi, intensity),
            data_versions={"fire_danger": data_version},
            methodology_version=self.methodology_version,
            valuation_date=valuation_date,
            latitude=latitude,
            longitude=longitude,
            metadata={
                "fwi": round(fwi, 4),
                "assessment_date": day,
                "input_cutoff": valuation_date.isoformat(),
                "hazard_class": "climate",
                **detail,
            },
        )


__all__ = [
    "FWI_SATURATION",
    "WILDFIRE_FIRE_DANGER_DATA_VERSION",
    "WILDFIRE_HAZARD_ID",
    "WILDFIRE_METHODOLOGY_VERSION",
    "WILDFIRE_PROXY_DATA_VERSION",
    "WildfireHazardModule",
    "fwi_proxy_from_temperature_c",
]
