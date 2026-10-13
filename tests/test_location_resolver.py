from __future__ import annotations

import pytest

from app.core.exceptions import GeoRiskApiError
from app.services.location_resolver import LocationResolver


def test_resolve_coordinates_comma() -> None:
    loc = LocationResolver().resolve("36.85, 30.75")
    assert loc.resolution_method == "coordinates"
    assert loc.latitude == pytest.approx(36.85)
    assert loc.longitude == pytest.approx(30.75)


def test_resolve_demo_asset_id() -> None:
    loc = LocationResolver().resolve("coastal_industrial_med")
    assert loc.resolution_method == "demo_asset"
    assert loc.latitude == pytest.approx(36.85)


def test_resolve_address_alias() -> None:
    loc = LocationResolver().resolve("houston ship channel")
    assert loc.resolution_method == "address_alias"
    assert loc.latitude == pytest.approx(29.7356)


def test_resolve_unknown_raises() -> None:
    with pytest.raises(GeoRiskApiError) as exc:
        LocationResolver().resolve("not-a-real-place-xyz-123")
    assert exc.value.status_code == 422
    assert exc.value.code == "location_unresolved"
