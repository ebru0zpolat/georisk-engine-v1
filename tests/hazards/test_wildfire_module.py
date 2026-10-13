"""Wildfire hazard module — Mediterranean / Türkiye tourism-coast peril."""

from __future__ import annotations

from datetime import date

import pytest

from app.geo.interfaces import RasterTile
from app.geo.raster_access import RasterAccess, RasterMockFixtures
from app.hazards.base import HazardModule
from app.hazards.wildfire import (
    WILDFIRE_FIRE_DANGER_DATA_VERSION,
    WILDFIRE_HAZARD_ID,
    WILDFIRE_METHODOLOGY_VERSION,
    WILDFIRE_PROXY_DATA_VERSION,
    WildfireHazardModule,
    fwi_proxy_from_temperature_c,
)

_LAT, _LON = 36.79, 31.30  # Manavgat west corridor
_DAY = "2021-07-01"


class _FWI:
    def __init__(self, value: float) -> None:
        self._value = value

    def fire_danger_index(self, lat: float, lon: float, date: str) -> RasterTile:
        return RasterTile(source="CEMS-FWI-TEST", lat=lat, lon=lon, value=self._value,
                          unit="fwi", data_snapshot_id="test")


def test_wildfire_module_satisfies_hazard_module_protocol() -> None:
    assert isinstance(WildfireHazardModule(), HazardModule)


def test_temperature_proxy_is_monotonic_and_bounded() -> None:
    assert fwi_proxy_from_temperature_c(10.0) == 0.0
    assert fwi_proxy_from_temperature_c(15.0) == 0.0
    assert 0.0 < fwi_proxy_from_temperature_c(25.0) < fwi_proxy_from_temperature_c(35.0)
    assert fwi_proxy_from_temperature_c(80.0) == 60.0


def test_fire_danger_source_drives_intensity_and_is_labelled() -> None:
    vdate = date(2021, 7, 1)
    low = WildfireHazardModule(fire_danger=_FWI(5.0)).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    high = WildfireHazardModule(fire_danger=_FWI(55.0)).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    assert high.intensity > low.intensity
    assert high.data_versions == {"fire_danger": WILDFIRE_FIRE_DANGER_DATA_VERSION}
    assert high.metadata["fwi_basis"] == "fire_danger_index"
    assert high.subtypes["direct_flame"] > low.subtypes["direct_flame"]
    assert set(high.subtypes) == {"ember_attack", "direct_flame"}


def test_temperature_proxy_path_is_labelled_as_proxy() -> None:
    hot = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(
        era5_temperature={(_LAT, _LON, _DAY): 38.0}))
    cool = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(
        era5_temperature={(_LAT, _LON, _DAY): 12.0}))
    vdate = date(2021, 7, 1)
    hot_r = WildfireHazardModule(raster=hot).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    cool_r = WildfireHazardModule(raster=cool).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    assert hot_r.intensity > cool_r.intensity
    assert cool_r.intensity == 0.0
    assert hot_r.data_versions == {"fire_danger": WILDFIRE_PROXY_DATA_VERSION}
    assert hot_r.metadata["fwi_basis"] == "temperature_proxy_no_fuel_wind_humidity"
    assert hot_r.metadata["hazard_class"] == "climate"


def test_wildfire_result_contract_fields() -> None:
    result = WildfireHazardModule(fire_danger=_FWI(30.0)).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=date(2019, 12, 31))
    assert result.hazard_id == WILDFIRE_HAZARD_ID
    assert result.methodology_version == WILDFIRE_METHODOLOGY_VERSION
    assert 0.0 <= result.intensity <= 1.0
    assert 0 <= result.score_0_100 <= 100
    for value in result.subtypes.values():
        assert 0.0 <= value <= 1.0
    assert result.metadata["input_cutoff"] == "2019-12-31"


def test_wildfire_rejects_lookahead_assessment_date() -> None:
    with pytest.raises(ValueError, match="lookahead"):
        WildfireHazardModule(fire_danger=_FWI(30.0)).evaluate(
            latitude=_LAT, longitude=_LON, valuation_date=date(2021, 7, 1),
            parameters={"assessment_date": "2021-07-02"})
