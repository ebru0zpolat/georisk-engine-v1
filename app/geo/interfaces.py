"""Public contracts for the geospatial service layer.

Downstream modules must import from this module only — not from
``geometry_registry``, ``spatial_index``, or ``raster_access`` directly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

__all__ = [
    "AssetGeometry",
    "ElevationBand",
    "GeoLookupResult",
    "GeometryAuditEvent",
    "RasterTile",
    "classify_elevation_band",
    "derive_geometry_hash",
    "derive_point_geometry_hash",
    "round_coordinates",
    "sample_elevation",
    "sample_era5_soil_moisture",
    "sample_era5_temperature",
]


class ElevationBand(str, Enum):
    BAND_0_2M = "0-2m"
    BAND_2_5M = "2-5m"
    BAND_5_10M = "5-10m"
    ABOVE_10M = ">10m"


def classify_elevation_band(elevation_m: float) -> ElevationBand:
    if elevation_m < 2:
        return ElevationBand.BAND_0_2M
    if elevation_m < 5:
        return ElevationBand.BAND_2_5M
    if elevation_m < 10:
        return ElevationBand.BAND_5_10M
    return ElevationBand.ABOVE_10M


@dataclass(frozen=True)
class AssetGeometry:
    asset_id: str
    geojson: dict[str, Any]
    asset_geometry_hash: str
    registered_at: datetime
    version: int


@dataclass(frozen=True)
class GeometryAuditEvent:
    event: str
    asset_id: str
    asset_geometry_hash: str
    version: int
    timestamp: datetime


@dataclass(frozen=True)
class RasterTile:
    source: str
    lat: float
    lon: float
    value: float
    unit: str
    data_snapshot_id: str


@dataclass(frozen=True)
class GeoLookupResult:
    """Spatial lookup bundle for coastal exposure and sea-level workflows."""

    asset_id: str
    distance_to_coast_km: float
    elevation_band: ElevationBand
    coastal_zone: str
    asset_geometry_hash: str


def round_coordinates(geometry: dict[str, Any], *, precision: int = 6) -> dict[str, Any]:
    """Recursively round coordinate values in a GeoJSON geometry dict."""

    def _round_value(value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            return round(value, precision)
        if isinstance(value, list):
            return [_round_value(item) for item in value]
        return value

    rounded = dict(geometry)
    if "coordinates" in rounded:
        rounded["coordinates"] = _round_value(rounded["coordinates"])
    return rounded


def derive_geometry_hash(geojson: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash for a GeoJSON geometry or Feature."""

    geometry = geojson.get("geometry", geojson)
    geometry = round_coordinates(geometry, precision=6)
    canonical = json.dumps(geometry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_point_geometry_hash(*, latitude: float, longitude: float) -> str:
    """Canonical point-asset hash (GEO-189) for lat/lng scoring paths."""

    return derive_geometry_hash(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {},
        }
    )


def _default_raster_access(*, use_mock: bool | None = None):
    """Lazy concrete accessor — importers must use the sample_* helpers below."""
    from app.core.config import settings
    from app.geo.raster_access import RasterAccess

    if use_mock is None:
        use_mock = not bool(settings.copernicus_cds_api_key)
    return RasterAccess(use_mock=use_mock)


def sample_elevation(lat: float, lon: float, *, use_mock: bool | None = None) -> RasterTile:
    return _default_raster_access(use_mock=use_mock).elevation_at(lat, lon)


def sample_era5_temperature(
    lat: float, lon: float, date: str, *, use_mock: bool | None = None
) -> RasterTile:
    return _default_raster_access(use_mock=use_mock).era5_temperature(lat, lon, date)


def sample_era5_soil_moisture(
    lat: float, lon: float, date: str, *, use_mock: bool | None = None
) -> RasterTile:
    return _default_raster_access(use_mock=use_mock).era5_soil_moisture(lat, lon, date)
