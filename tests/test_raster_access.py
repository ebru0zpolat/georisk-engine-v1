"""GEO-191 — raster access layer."""

from __future__ import annotations

import pytest

from app.geo.exceptions import RasterSourceConfigError
from app.geo.raster_access import ELEVATION_FIXTURES, RasterAccess, RasterMockFixtures

SRTM_REFERENCE = {
    (36.850, 30.750): 54.0,
    (41.008, 28.978): 40.0,
    (39.925, 32.854): 893.0,
}


def test_elevation_at_within_five_meters_of_reference() -> None:
    raster = RasterAccess(use_mock=True)
    for (lat, lon), reference_m in SRTM_REFERENCE.items():
        tile = raster.elevation_at(lat, lon)
        assert abs(tile.value - reference_m) <= 5.0
        assert tile.source == "MERIT_DEM"
        assert tile.data_snapshot_id


def test_era5_temperature_plausible_fixture() -> None:
    raster = RasterAccess(cds_api_key="test-key")
    tile = raster.era5_temperature(36.85, 30.75, "2024-07-15")
    assert 20.0 <= tile.value <= 35.0
    assert tile.unit == "°C"
    assert tile.data_snapshot_id


def test_data_snapshot_id_on_every_raster_tile() -> None:
    raster = RasterAccess(cds_api_key="test-key", use_mock=True)
    assert raster.elevation_at(36.85, 30.75).data_snapshot_id
    assert raster.no2_column(36.85, 30.75, "2024-07-15").data_snapshot_id
    assert raster.era5_temperature(36.85, 30.75, "2024-07-15").data_snapshot_id
    assert raster.sea_level_anomaly("med-antalya", "2024-01-01").data_snapshot_id


def test_raster_source_config_error_on_missing_cds_key() -> None:
    raster = RasterAccess(cds_api_key=None, use_mock=False)
    with pytest.raises(RasterSourceConfigError) as exc:
        raster.era5_temperature(36.85, 30.75, "2024-07-15")
    assert exc.value.source == "ERA5"
    with pytest.raises(RasterSourceConfigError):
        raster.no2_column(36.85, 30.75, "2024-07-15")


def test_mock_mode_without_network_or_cds_key() -> None:
    raster = RasterAccess(use_mock=True)
    tile = raster.no2_column(36.85, 30.75, "2024-07-15")
    assert tile.value > 0
    assert tile.data_snapshot_id


def test_custom_fixtures_override_defaults() -> None:
    fixtures = RasterMockFixtures(
        elevation={(10.0, 20.0): 100.0},
        snapshot_id="2025-06-01T00:00:00+00:00",
    )
    raster = RasterAccess(fixtures=fixtures, elevation_lookup=fixtures.elevation)
    tile = raster.elevation_at(10.0, 20.0)
    assert tile.value == 100.0
    assert tile.data_snapshot_id == "2025-06-01T00:00:00+00:00"
