"""NDVI / soil-moisture proxies for ``agriculture`` sector.

Soil moisture uses ``sample_era5_soil_moisture`` from ``app.geo.interfaces``.
NDVI remains a deterministic greenness proxy until a GEE vegetation collection
is attached to ``GeeConnector``.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Protocol

from app.core.sector_registry import AGRICULTURE_SECTOR_ID
from app.geo.interfaces import RasterTile, sample_era5_soil_moisture
from app.schemas.risk import RiskScoreRequest


class _SoilRaster(Protocol):
    def era5_soil_moisture(self, lat: float, lon: float, date: str) -> RasterTile: ...


def attach_agriculture_proxies_to_gee_dict(
    gee_raw: dict,
    payload: RiskScoreRequest,
    *,
    raster: _SoilRaster | None = None,
) -> dict:
    """Return a copy of GEE ``current`` dict with optional ``ndvi_mean`` / ``soil_moisture_proxy``."""
    out = dict(gee_raw)
    if payload.sector != AGRICULTURE_SECTOR_ID:
        out.setdefault("ndvi_mean", None)
        out.setdefault("soil_moisture_proxy", None)
        return out

    seed = (
        f"{payload.latitude:.6f}|{payload.longitude:.6f}|"
        f"{payload.radius_km:.3f}|{payload.asset_name}|ag_surface_v1"
    )
    digest = hashlib.sha256(seed.encode()).digest()
    ndvi = 0.32 + (digest[0] % 56) / 200.0
    out["ndvi_mean"] = round(ndvi, 4)

    day = (payload.end_date or payload.start_date or date(2024, 7, 15)).isoformat()
    if raster is not None:
        soil = raster.era5_soil_moisture(payload.latitude, payload.longitude, day).value
    else:
        soil = sample_era5_soil_moisture(payload.latitude, payload.longitude, day).value
    out["soil_moisture_proxy"] = round(max(0.0, min(1.0, float(soil))), 4)
    return out
