"""GEO-189 — geometry registry and deterministic asset_geometry_hash."""

from __future__ import annotations

import pytest

from app.geo.exceptions import GeometryAlreadyRegisteredError, GeometryNotFoundError
from app.geo.geometry_registry import GeometryRegistry
from app.geo.interfaces import derive_geometry_hash, round_coordinates

_POINT_FEATURE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [30.750123456789, 36.850987654321]},
    "properties": {"name": "demo"},
}

_POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [30.0, 36.0],
            [30.1, 36.0],
            [30.1, 36.1],
            [30.0, 36.1],
            [30.0, 36.0],
        ]
    ],
}

_MULTIPOLYGON_GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[30.0, 36.0], [30.1, 36.0], [30.1, 36.1], [30.0, 36.1], [30.0, 36.0]]],
        [[[30.2, 36.2], [30.3, 36.2], [30.3, 36.3], [30.2, 36.3], [30.2, 36.2]]],
    ],
}


def test_derive_geometry_hash_stable_for_same_geometry() -> None:
    h1 = derive_geometry_hash(_POINT_FEATURE)
    h2 = derive_geometry_hash(_POINT_FEATURE)
    assert h1 == h2
    assert len(h1) == 64


def test_derive_geometry_hash_differs_on_coordinate_change_at_six_dp() -> None:
    base = {
        "type": "Point",
        "coordinates": [30.750123, 36.850987],
    }
    shifted = {
        "type": "Point",
        "coordinates": [30.750124, 36.850987],
    }
    assert derive_geometry_hash(base) != derive_geometry_hash(shifted)


def test_round_coordinates_recurses_polygon_and_multipolygon() -> None:
    rounded_poly = round_coordinates(_POLYGON_GEOJSON, precision=6)
    assert rounded_poly["coordinates"][0][0] == [30.0, 36.0]

    noisy = {
        "type": "Polygon",
        "coordinates": [
            [
                [30.0000004, 36.0000004],
                [30.1000004, 36.0000004],
                [30.1000004, 36.1000004],
                [30.0000004, 36.1000004],
                [30.0000004, 36.0000004],
            ]
        ],
    }
    rounded_noisy = round_coordinates(noisy, precision=6)
    assert derive_geometry_hash(noisy) == derive_geometry_hash(rounded_noisy)


def test_feature_geometry_unwrapped_for_hash() -> None:
    geometry_only = _POINT_FEATURE["geometry"]
    assert derive_geometry_hash(_POINT_FEATURE) == derive_geometry_hash(geometry_only)


def test_registry_register_and_hash_for() -> None:
    registry = GeometryRegistry()
    asset = registry.register("asset-001", _POINT_FEATURE)
    assert asset.version == 1
    assert asset.asset_geometry_hash == derive_geometry_hash(_POINT_FEATURE)
    assert registry.hash_for("asset-001") == asset.asset_geometry_hash


def test_registry_update_increments_version_and_changes_hash() -> None:
    registry = GeometryRegistry()
    registry.register("asset-001", _POINT_FEATURE)
    updated_geom = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [30.751, 36.851]},
    }
    updated = registry.update("asset-001", updated_geom)
    assert updated.version == 2
    assert updated.asset_geometry_hash != derive_geometry_hash(_POINT_FEATURE)


def test_registry_get_and_hash_for_raise_geometry_not_found() -> None:
    registry = GeometryRegistry()
    with pytest.raises(GeometryNotFoundError):
        registry.get("missing")
    with pytest.raises(GeometryNotFoundError):
        registry.hash_for("missing")


def test_registry_register_duplicate_raises() -> None:
    registry = GeometryRegistry()
    registry.register("asset-001", _POINT_FEATURE)
    with pytest.raises(GeometryAlreadyRegisteredError):
        registry.register("asset-001", _POLYGON_GEOJSON)


def test_registry_audit_log_on_register_and_update() -> None:
    registry = GeometryRegistry()
    first = registry.register("asset-001", _POINT_FEATURE)
    registry.update("asset-001", _MULTIPOLYGON_GEOJSON)
    assert len(registry.audit_log) == 2
    assert registry.audit_log[0].event == "geometry_registered"
    assert registry.audit_log[0].asset_id == "asset-001"
    assert registry.audit_log[0].asset_geometry_hash == first.asset_geometry_hash
    assert registry.audit_log[0].version == 1
    assert registry.audit_log[1].version == 2


def test_public_imports_do_not_require_geometry_registry() -> None:
    from app.geo import AssetGeometry, derive_geometry_hash as public_hash

    assert public_hash(_POINT_FEATURE)
    assert AssetGeometry.__dataclass_fields__["asset_geometry_hash"].name == "asset_geometry_hash"
