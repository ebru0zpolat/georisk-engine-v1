"""Flood/heat scores from RasterAccess (mock ERA5 / MERIT)."""

from __future__ import annotations

from app.geo.raster_access import RasterAccess, RasterMockFixtures
from app.schemas.risk import RiskScoreRequest
from app.scoring.flood_heat import compute_flood_score, compute_heat_score


def test_heat_score_rises_with_temperature() -> None:
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
    req = RiskScoreRequest(
        asset_name="T",
        latitude=36.85,
        longitude=30.75,
        end_date=__import__("datetime").date(2024, 7, 15),
    )
    assert compute_heat_score(req, raster=hot) > compute_heat_score(req, raster=cool)


def test_flood_score_higher_at_low_elevation() -> None:
    low = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(elevation={(36.85, 30.75): 5.0}),
    )
    high = RasterAccess(
        use_mock=True,
        fixtures=RasterMockFixtures(elevation={(36.85, 30.75): 800.0}),
    )
    req = RiskScoreRequest(asset_name="F", latitude=36.85, longitude=30.75)
    assert compute_flood_score(req, raster=low) > compute_flood_score(req, raster=high)
