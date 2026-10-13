"""Extreme-heat hazard module — highest market-coverage peril (§2.4)."""

from __future__ import annotations

from datetime import date

import pytest

from app.geo.raster_access import RasterAccess, RasterMockFixtures
from app.hazards.base import HazardModule
from app.hazards.extreme_heat import (
    EXTREME_HEAT_HAZARD_ID,
    EXTREME_HEAT_METHODOLOGY_VERSION,
    ExtremeHeatHazardModule,
)


def test_extreme_heat_module_satisfies_protocol() -> None:
    assert isinstance(ExtremeHeatHazardModule(), HazardModule)


def test_extreme_heat_intensity_rises_with_temperature() -> None:
    cool = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(
            era5_temperature={(36.85, 30.75, "2024-07-15"): 12.0},
        ),
    )
    hot = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(
            era5_temperature={(36.85, 30.75, "2024-07-15"): 38.0},
        ),
    )
    vdate = date(2024, 7, 15)
    cool_r = ExtremeHeatHazardModule(raster=cool).evaluate(
        latitude=36.85, longitude=30.75, valuation_date=vdate
    )
    hot_r = ExtremeHeatHazardModule(raster=hot).evaluate(
        latitude=36.85, longitude=30.75, valuation_date=vdate
    )
    assert hot_r.intensity > cool_r.intensity
    assert hot_r.score_0_100 > cool_r.score_0_100


def test_extreme_heat_result_contract_fields() -> None:
    result = ExtremeHeatHazardModule().evaluate(
        latitude=41.01,
        longitude=28.97,
        valuation_date=date(2021, 7, 1),
    )
    assert result.hazard_id == EXTREME_HEAT_HAZARD_ID
    assert result.methodology_version == EXTREME_HEAT_METHODOLOGY_VERSION
    assert 0.0 <= result.intensity <= 1.0
    assert 0 <= result.score_0_100 <= 100
    assert set(result.subtypes) == {"chronic_heat_stress", "acute_heatwave"}
    assert result.valuation_date == date(2021, 7, 1)
    assert "era5_temperature" in result.data_versions
    assert result.metadata["assessment_date"] == "2021-07-01"


def test_extreme_heat_rejects_lookahead_assessment_date() -> None:
    mod = ExtremeHeatHazardModule()
    with pytest.raises(ValueError, match="lookahead"):
        mod.evaluate(
            latitude=36.85,
            longitude=30.75,
            valuation_date=date(2020, 1, 1),
            parameters={"assessment_date": "2021-07-01"},
        )


def test_acute_heatwave_subtype_stronger_when_hot() -> None:
    mild = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(
            era5_temperature={(10.0, 10.0, "2022-08-01"): 24.0},
        ),
    )
    extreme = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(
            era5_temperature={(10.0, 10.0, "2022-08-01"): 40.0},
        ),
    )
    vdate = date(2022, 8, 1)
    m = ExtremeHeatHazardModule(raster=mild).evaluate(
        latitude=10.0, longitude=10.0, valuation_date=vdate
    )
    e = ExtremeHeatHazardModule(raster=extreme).evaluate(
        latitude=10.0, longitude=10.0, valuation_date=vdate
    )
    assert e.subtypes["acute_heatwave"] > m.subtypes["acute_heatwave"]
