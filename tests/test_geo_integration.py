"""GEO-192 — end-to-end integration across geometry, spatial index, and raster access."""

from __future__ import annotations

import importlib

import pytest

from app.geo.flows import coastal_exposure_score, sea_level_z_score
from app.geo.geometry_registry import GeometryRegistry
from app.geo.interfaces import ElevationBand, GeoLookupResult
from app.geo.raster_access import RasterAccess
from app.geo.spatial_index import SpatialIndex
from app.scoring.scenario_score import compute_scenario_score

COASTAL_LOW = {"type": "Point", "coordinates": [30.750, 36.850]}
COASTAL_HIGH = {"type": "Point", "coordinates": [30.745, 36.845]}
INLAND = {"type": "Point", "coordinates": [32.854, 39.925]}

ELEVATION_FIXTURES = {
    (36.850, 30.750): 1.2,
    (36.845, 30.745): 7.5,
    (39.925, 32.854): 850.0,
}


def _feature(geometry: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": {}}


@pytest.fixture
def geo_stack() -> tuple[GeometryRegistry, SpatialIndex, RasterAccess]:
    registry = GeometryRegistry()
    raster = RasterAccess(
        elevation_lookup=lambda lat, lon: ELEVATION_FIXTURES.get((round(lat, 3), round(lon, 3)), 0.0),
        use_mock=True,
    )
    index = SpatialIndex(registry, raster)
    registry.register("coastal-low", _feature(COASTAL_LOW))
    registry.register("coastal-high", _feature(COASTAL_HIGH))
    registry.register("inland-ankara", _feature(INLAND))
    return registry, index, raster


def test_scenario_1_register_hash_matches_scenario_scoring(
    geo_stack: tuple[GeometryRegistry, SpatialIndex, RasterAccess],
) -> None:
    """Register geometry → derive hash → scenario scoring uses the same anchor."""

    registry, _, _ = geo_stack
    lon, lat = COASTAL_LOW["coordinates"]
    registered = registry.register(
        "scenario-anchor",
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"label": "integration"},
        },
    )

    scored = compute_scenario_score(
        asset_id="scenario-anchor",
        model_version="integration-v1",
        data_snapshot_id="2026-01-01T00:00:00+00:00",
        baseline_score=42,
        components={"ocean": 55, "pollution": 40, "land": 35, "industrial": 50, "agriculture": 30, "sensitivity": 25},
        pathway="SSP2-4.5",
        horizon=2050,
        hazards=["sea_level_rise"],
        latitude=lat,
        longitude=lon,
        geometry_hash_verified=True,
    )

    assert scored.asset_geometry_hash == registered.asset_geometry_hash
    assert scored.asset_geometry_hash == registry.hash_for("scenario-anchor")


def test_scenario_2_coastal_lookup_populates_geo_lookup_result(
    geo_stack: tuple[GeometryRegistry, SpatialIndex, RasterAccess],
) -> None:
    """Register coastal asset → lookup returns populated GeoLookupResult."""

    registry, index, _ = geo_stack
    lookup = index.lookup("coastal-low")

    assert isinstance(lookup, GeoLookupResult)
    assert lookup.asset_id == "coastal-low"
    assert lookup.distance_to_coast_km < 10.0
    assert lookup.elevation_band is ElevationBand.BAND_0_2M
    assert lookup.coastal_zone == "med-antalya"
    assert lookup.asset_geometry_hash == registry.hash_for("coastal-low")


def test_scenario_3_elevation_to_coastal_exposure_score(
    geo_stack: tuple[GeometryRegistry, SpatialIndex, RasterAccess],
) -> None:
    """Raster elevation → elevation band → coastal exposure score (GEO-8 flow)."""

    _, index, raster = geo_stack
    lat, lon = COASTAL_LOW["coordinates"][1], COASTAL_LOW["coordinates"][0]
    tile = raster.elevation_at(lat, lon)
    band = index.elevation_band("coastal-low")
    distance_km = index.distance_to_coast("coastal-low")

    assert tile.source == "MERIT_DEM"
    assert band is ElevationBand.BAND_0_2M
    score = coastal_exposure_score(elevation_band=band, distance_to_coast_km=distance_km)
    assert score >= 75


def test_scenario_4_lookup_to_sea_level_z_score(
    geo_stack: tuple[GeometryRegistry, SpatialIndex, RasterAccess],
) -> None:
    """Asset lookup → PSMSL anomaly → Z-score input (GEO-7 flow)."""

    _, index, raster = geo_stack
    lookup = index.lookup("coastal-low")
    anomaly = raster.sea_level_anomaly(lookup.coastal_zone, "2024-01-01")

    z_score = sea_level_z_score(anomaly.value, [0.030, 0.032, 0.031, 0.029, 0.033])

    assert anomaly.source == "PSMSL"
    assert anomaly.data_snapshot_id
    assert lookup.asset_geometry_hash
    assert z_score != 0.0


def test_interfaces_importable_without_circular_imports() -> None:
    """All public contracts load from app.geo.interfaces in one import."""

    interfaces = importlib.import_module("app.geo.interfaces")
    for name in (
        "AssetGeometry",
        "ElevationBand",
        "GeoLookupResult",
        "GeometryAuditEvent",
        "RasterTile",
        "classify_elevation_band",
        "derive_geometry_hash",
        "derive_point_geometry_hash",
        "round_coordinates",
    ):
        assert hasattr(interfaces, name), f"missing export: {name}"

    # Concrete modules must not pull interfaces through a cycle at import time.
    importlib.import_module("app.geo.geometry_registry")
    importlib.import_module("app.geo.spatial_index")
    importlib.import_module("app.geo.raster_access")
