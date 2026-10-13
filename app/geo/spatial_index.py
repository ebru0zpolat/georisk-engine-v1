"""Spatial queries over registered asset geometries (GEO-190)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from shapely.geometry import LineString, Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from app.geo.geometry_registry import GeometryRegistry
from app.geo.interfaces import ElevationBand, GeoLookupResult, classify_elevation_band
from app.geo.raster_access import ElevationProvider


@dataclass(frozen=True)
class CoastlineSegment:
    zone_id: str
    geometry: LineString


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometres (WGS84 spherical approximation)."""

    r_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geojson_to_geometry(geojson: dict[str, Any]) -> BaseGeometry:
    geometry = geojson.get("geometry", geojson)
    return shape(geometry)


def _representative_point(geometry: BaseGeometry) -> Point:
    if geometry.geom_type == "Point":
        return geometry
    return geometry.representative_point()


class SpatialIndex:
    """In-process spatial index (shapely + STRtree). PostGIS wiring deferred."""

    def __init__(
        self,
        geometry_registry: GeometryRegistry,
        raster_access: ElevationProvider,
        coastline_segments: list[CoastlineSegment] | None = None,
    ) -> None:
        self._registry = geometry_registry
        self._raster = raster_access
        self._coastline_segments = coastline_segments or _default_coastline_segments()
        self._rebuild_index()

    def refresh(self) -> None:
        """Rebuild spatial tree after registry mutations."""

        self._rebuild_index()

    def assets_within(self, polygon: dict[str, Any]) -> list[str]:
        self._ensure_index()
        query = shape(polygon.get("geometry", polygon))
        if query.geom_type == "Polygon" and query.is_empty:
            return []
        hits: list[str] = []
        for asset_id, geom in self._asset_geometries.items():
            if query.intersects(geom):
                hits.append(asset_id)
        return sorted(hits)

    def distance_to_coast(self, asset_id: str) -> float:
        self._ensure_index()
        point = self._asset_point(asset_id)
        return self._distance_point_to_coast_km(point)

    def elevation_band(self, asset_id: str) -> ElevationBand:
        self._ensure_index()
        point = self._asset_point(asset_id)
        tile = self._raster.elevation_at(point.y, point.x)
        return classify_elevation_band(tile.value)

    def coastal_zone(self, asset_id: str) -> str:
        self._ensure_index()
        point = self._asset_point(asset_id)
        return self._coastal_zone_for_point(point)

    def lookup(self, asset_id: str) -> GeoLookupResult:
        """Return the full spatial lookup bundle for a registered asset."""

        self._ensure_index()
        record = self._registry.get(asset_id)
        return GeoLookupResult(
            asset_id=asset_id,
            distance_to_coast_km=self.distance_to_coast(asset_id),
            elevation_band=self.elevation_band(asset_id),
            coastal_zone=self.coastal_zone(asset_id),
            asset_geometry_hash=record.asset_geometry_hash,
        )

    def _ensure_index(self) -> None:
        if set(self._registry.list_asset_ids()) != set(self._asset_geometries.keys()):
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._asset_geometries: dict[str, BaseGeometry] = {}
        for asset_id in self._registry.list_asset_ids():
            record = self._registry.get(asset_id)
            self._asset_geometries[asset_id] = _geojson_to_geometry(record.geojson)
        if self._asset_geometries:
            self._tree = STRtree(list(self._asset_geometries.values()))
        else:
            self._tree = None

    def _asset_point(self, asset_id: str) -> Point:
        record = self._registry.get(asset_id)
        geom = _geojson_to_geometry(record.geojson)
        self._asset_geometries[asset_id] = geom
        return _representative_point(geom)

    def _distance_point_to_coast_km(self, point: Point) -> float:
        if not self._coastline_segments:
            return float("inf")
        best = float("inf")
        for segment in self._coastline_segments:
            nearest_asset, nearest_coast = nearest_points(point, segment.geometry)
            dist = haversine_km(
                nearest_asset.x,
                nearest_asset.y,
                nearest_coast.x,
                nearest_coast.y,
            )
            best = min(best, dist)
        return best

    def _coastal_zone_for_point(self, point: Point) -> str:
        if not self._coastline_segments:
            lat_bucket = int(round(point.y * 2))
            lon_bucket = int(round(point.x * 2))
            return f"inland-{lat_bucket}-{lon_bucket}"

        best_zone = "inland"
        best_dist = float("inf")
        for segment in self._coastline_segments:
            nearest_asset, nearest_coast = nearest_points(point, segment.geometry)
            dist = haversine_km(
                nearest_asset.x,
                nearest_asset.y,
                nearest_coast.x,
                nearest_coast.y,
            )
            if dist < best_dist:
                best_dist = dist
                best_zone = segment.zone_id

        if best_dist > 50.0:
            lat_bucket = int(round(point.y * 2))
            lon_bucket = int(round(point.x * 2))
            return f"inland-{lat_bucket}-{lon_bucket}"
        return best_zone


def _default_coastline_segments() -> list[CoastlineSegment]:
    """Simplified eastern Mediterranean coastline for CI golden fixtures."""

    return [
        CoastlineSegment(
            zone_id="med-antalya",
            geometry=LineString([(30.0, 36.80), (31.0, 36.82), (32.0, 36.85), (33.0, 36.88)]),
        ),
        CoastlineSegment(
            zone_id="med-mersin",
            geometry=LineString([(33.5, 36.75), (34.5, 36.70), (35.5, 36.65)]),
        ),
    ]
