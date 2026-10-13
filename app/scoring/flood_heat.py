"""Flood and heat hazard scoring via ``app.geo.interfaces`` raster samples.

- **Heat:** ERA5 temperature (°C) → 0–100 exposure score.
- **Flood:** MERIT DEM elevation proxy (lower = wetter exposure) until HydroSAT
  extent layers are wired.

When CDS credentials are absent, interfaces use mock fixtures (deterministic CI).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.geo.interfaces import RasterTile, sample_elevation, sample_era5_temperature
from app.schemas.risk import RiskScoreRequest


class _HazardRaster(Protocol):
    def elevation_at(self, lat: float, lon: float) -> RasterTile: ...

    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile: ...


def _assessment_date(request: RiskScoreRequest) -> str:
    if request.end_date is not None:
        return request.end_date.isoformat()
    if request.start_date is not None:
        return request.start_date.isoformat()
    return date(2024, 7, 15).isoformat()


def compute_flood_score(request: RiskScoreRequest, *, raster: _HazardRaster | None = None) -> int:
    """Flood hazard 0–100 from elevation proxy (low elevation → higher score)."""
    if raster is not None:
        elev = raster.elevation_at(request.latitude, request.longitude).value
    else:
        elev = sample_elevation(request.latitude, request.longitude).value
    raw = 95.0 - (float(elev) / 500.0) * 80.0
    return max(0, min(100, int(round(raw))))


def compute_heat_score(request: RiskScoreRequest, *, raster: _HazardRaster | None = None) -> int:
    """Heat hazard 0–100 from ERA5 temperature (°C)."""
    day = _assessment_date(request)
    if raster is not None:
        temp_c = raster.era5_temperature(request.latitude, request.longitude, day).value
    else:
        temp_c = sample_era5_temperature(request.latitude, request.longitude, day).value
    raw = (float(temp_c) - 5.0) * (100.0 / 35.0)
    return max(0, min(100, int(round(raw))))
