"""Flood hazard module — highest market-coverage peril (§2.4)."""

from __future__ import annotations

from datetime import date

from app.geo.raster_access import RasterAccess, RasterMockFixtures
from app.hazards.base import HazardModule
from app.hazards.flood import (
    FLOOD_HAZARD_ID,
    FLOOD_METHODOLOGY_VERSION,
    FloodHazardModule,
)


def test_flood_module_satisfies_hazard_module_protocol() -> None:
    assert isinstance(FloodHazardModule(), HazardModule)


def test_flood_intensity_higher_at_low_elevation() -> None:
    low = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(elevation={(36.85, 30.75): 5.0}))
    high = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(elevation={(36.85, 30.75): 800.0}))
    vdate = date(2021, 7, 1)
    low_r = FloodHazardModule(raster=low).evaluate(
        latitude=36.85, longitude=30.75, valuation_date=vdate
    )
    high_r = FloodHazardModule(raster=high).evaluate(
        latitude=36.85, longitude=30.75, valuation_date=vdate
    )
    assert low_r.intensity > high_r.intensity
    assert low_r.score_0_100 > high_r.score_0_100


def test_flood_result_contract_fields() -> None:
    result = FloodHazardModule().evaluate(
        latitude=41.01,
        longitude=28.97,
        valuation_date=date(2019, 12, 31),
    )
    assert result.hazard_id == FLOOD_HAZARD_ID
    assert result.methodology_version == FLOOD_METHODOLOGY_VERSION
    assert 0.0 <= result.intensity <= 1.0
    assert 0 <= result.score_0_100 <= 100
    assert set(result.subtypes) == {"fluvial", "pluvial", "coastal"}
    for value in result.subtypes.values():
        assert 0.0 <= value <= 1.0
    assert result.valuation_date == date(2019, 12, 31)
    assert "elevation" in result.data_versions
    assert result.metadata["input_cutoff"] == "2019-12-31"


def test_flood_coastal_subtype_stronger_near_sea_level() -> None:
    coastal = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(elevation={(0.0, 0.0): 1.0}))
    inland = RasterAccess(use_mock=True, fixtures=RasterMockFixtures(elevation={(0.0, 0.0): 50.0}))
    vdate = date(2020, 1, 1)
    c = FloodHazardModule(raster=coastal).evaluate(
        latitude=0.0, longitude=0.0, valuation_date=vdate
    )
    i = FloodHazardModule(raster=inland).evaluate(
        latitude=0.0, longitude=0.0, valuation_date=vdate
    )
    assert c.subtypes["coastal"] > i.subtypes["coastal"]
