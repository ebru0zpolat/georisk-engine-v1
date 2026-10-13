"""Earthquake hazard module — geophysical peril, fail-closed without a seismic source."""

from __future__ import annotations

from datetime import date

import pytest

from app.geo.interfaces import RasterTile
from app.hazards.base import HazardModule
from app.hazards.earthquake import (
    EARTHQUAKE_HAZARD_ID,
    EARTHQUAKE_METHODOLOGY_VERSION,
    EARTHQUAKE_SYNTHETIC_DATA_VERSION,
    PGA_SATURATION_G,
    EarthquakeHazardModule,
    SyntheticSeismicSource,
    score_from_pga_g,
)

_LAT, _LON = 36.88, 30.70  # Antalya Kaleiçi


class _PGA:
    def __init__(self, value: float) -> None:
        self._value = value

    def pga_g(self, lat: float, lon: float) -> RasterTile:
        return RasterTile(source="AFAD-TDTH-TEST", lat=lat, lon=lon, value=self._value,
                          unit="g", data_snapshot_id="test")


def test_earthquake_module_satisfies_hazard_module_protocol() -> None:
    assert isinstance(EarthquakeHazardModule(source=SyntheticSeismicSource()), HazardModule)


def test_earthquake_fails_closed_without_a_source() -> None:
    with pytest.raises(ValueError, match="EARTHQUAKE_SOURCE_REQUIRED"):
        EarthquakeHazardModule().evaluate(
            latitude=_LAT, longitude=_LON, valuation_date=date(2021, 7, 1))


def test_score_from_pga_saturates() -> None:
    assert score_from_pga_g(0.0) == 0
    assert score_from_pga_g(PGA_SATURATION_G / 2) == 50
    assert score_from_pga_g(PGA_SATURATION_G) == 100
    assert score_from_pga_g(2.0) == 100


def test_real_source_drives_intensity_and_is_not_labelled_synthetic() -> None:
    vdate = date(2021, 7, 1)
    low = EarthquakeHazardModule(source=_PGA(0.05)).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    high = EarthquakeHazardModule(source=_PGA(0.45)).evaluate(
        latitude=_LAT, longitude=_LON, valuation_date=vdate)
    assert high.intensity > low.intensity
    assert high.metadata["synthetic"] is False
    assert high.metadata["hazard_class"] == "geophysical"
    assert high.metadata["climate_stationary"] is True
    assert high.data_versions["seismic_pga"].startswith("seismic-pga:")
    assert high.subtypes == {"ground_shaking": high.intensity}


def test_synthetic_source_is_deterministic_and_labelled() -> None:
    vdate = date(2021, 7, 1)
    module = EarthquakeHazardModule(source=SyntheticSeismicSource())
    a = module.evaluate(latitude=_LAT, longitude=_LON, valuation_date=vdate)
    b = module.evaluate(latitude=_LAT, longitude=_LON, valuation_date=vdate)
    assert a.intensity == b.intensity
    assert a.metadata["synthetic"] is True
    assert "SYNTHETIC" in a.metadata["seismic_source"]
    assert a.data_versions == {"seismic_pga": EARTHQUAKE_SYNTHETIC_DATA_VERSION}
    assert 0.0 <= a.metadata["pga_g"] <= 0.5


def test_earthquake_result_contract_fields() -> None:
    result = EarthquakeHazardModule(source=_PGA(0.3)).evaluate(
        latitude=41.01, longitude=28.97, valuation_date=date(2019, 12, 31))
    assert result.hazard_id == EARTHQUAKE_HAZARD_ID
    assert result.methodology_version == EARTHQUAKE_METHODOLOGY_VERSION
    assert 0.0 <= result.intensity <= 1.0
    assert result.score_0_100 == 50
    assert result.metadata["return_period_years"] == 475
    assert result.metadata["input_cutoff"] == "2019-12-31"
