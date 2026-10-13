"""GEO-190 — spatial index (shapely in-process; PostGIS migration separate)."""

from __future__ import annotations

import pytest

from app.geo.geometry_registry import GeometryRegistry
from app.geo.interfaces import ElevationBand
from app.geo.raster_access import RasterAccess
from app.geo.spatial_index import SpatialIndex

# Golden fixture coordinates (eastern Mediterranean / Türkiye test AOI)
COASTAL_LOW = {"type": "Point", "coordinates": [30.750, 36.850]}
COASTAL_HIGH = {"type": "Point", "coordinates": [30.745, 36.845]}
INLAND = {"type": "Point", "coordinates": [32.854, 39.925]}

ELEVATIONS = {
    (36.850, 30.750): 1.2,
    (36.845, 30.745): 7.5,
    (39.925, 32.854): 850.0,
}


def _feature(geometry: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": {}}


@pytest.fixture
def spatial_stack() -> tuple[GeometryRegistry, SpatialIndex]:
    registry = GeometryRegistry()
    raster = RasterAccess(
        elevation_lookup=lambda lat, lon: ELEVATIONS.get((round(lat, 3), round(lon, 3)), 0.0)
    )
    index = SpatialIndex(registry, raster)
    registry.register("coastal-low", _feature(COASTAL_LOW))
    registry.register("coastal-high", _feature(COASTAL_HIGH))
    registry.register("inland-ankara", _feature(INLAND))
    registry.register("outside-query", _feature({"type": "Point", "coordinates": [28.0, 41.0]}))
    return registry, index


def test_distance_to_coast_golden_fixtures(spatial_stack: tuple[GeometryRegistry, SpatialIndex]) -> None:
    _, index = spatial_stack
    coastal_low_km = index.distance_to_coast("coastal-low")
    coastal_high_km = index.distance_to_coast("coastal-high")
    inland_km = index.distance_to_coast("inland-ankara")

    assert coastal_low_km < 10.0
    assert coastal_high_km < 15.0
    assert inland_km > 100.0
    assert coastal_low_km < inland_km


def test_elevation_band_golden_fixtures(spatial_stack: tuple[GeometryRegistry, SpatialIndex]) -> None:
    _, index = spatial_stack
    assert index.elevation_band("coastal-low") == ElevationBand.BAND_0_2M
    assert index.elevation_band("coastal-high") == ElevationBand.BAND_5_10M
    assert index.elevation_band("inland-ankara") == ElevationBand.ABOVE_10M


def test_coastal_zone_deterministic_for_known_coordinates(
    spatial_stack: tuple[GeometryRegistry, SpatialIndex],
) -> None:
    _, index = spatial_stack
    zone_low = index.coastal_zone("coastal-low")
    zone_high = index.coastal_zone("coastal-high")
    zone_inland = index.coastal_zone("inland-ankara")

    assert zone_low == "med-antalya"
    assert zone_high == "med-antalya"
    assert zone_inland.startswith("inland-")
    assert index.coastal_zone("coastal-low") == zone_low


def test_assets_within_returns_correct_subset(spatial_stack: tuple[GeometryRegistry, SpatialIndex]) -> None:
    _, index = spatial_stack
    query_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [30.0, 36.0],
                [33.0, 36.0],
                [33.0, 40.0],
                [30.0, 40.0],
                [30.0, 36.0],
            ]
        ],
    }
    hits = index.assets_within(query_polygon)
    assert hits == ["coastal-high", "coastal-low", "inland-ankara"]
    assert "outside-query" not in hits


def test_elevation_band_uses_raster_access_not_inline_elevation(
    spatial_stack: tuple[GeometryRegistry, SpatialIndex],
) -> None:
    registry, _ = spatial_stack
    calls: list[tuple[float, float]] = []

    class TrackingRaster(RasterAccess):
        def elevation_at(self, lat: float, lon: float):
            calls.append((lat, lon))
            return super().elevation_at(lat, lon)

    index = SpatialIndex(registry, TrackingRaster(elevation_lookup=ELEVATIONS))
    index.elevation_band("coastal-low")
    assert len(calls) == 1
