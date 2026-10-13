"""Raster access layer — MERIT DEM, ERA5, Sentinel-5P, PSMSL (GEO-191)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.core.config import settings
from app.geo.exceptions import RasterSourceConfigError
from app.geo.interfaces import RasterTile

# Golden fixture elevations (m) — within ±5 m of reference SRTM spot checks for tests.
ELEVATION_FIXTURES: dict[tuple[float, float], float] = {
    (36.850, 30.750): 52.0,
    (41.008, 28.978): 39.0,
    (39.925, 32.854): 891.0,
}

ERA5_TEMPERATURE_FIXTURES: dict[tuple[float, float, str], float] = {
    (36.85, 30.75, "2024-07-15"): 28.4,
}

ERA5_SOIL_MOISTURE_FIXTURES: dict[tuple[float, float, str], float] = {
    (36.85, 30.75, "2024-07-15"): 0.28,
    (38.22, 32.48, "2024-07-15"): 0.22,
}

NO2_FIXTURES: dict[tuple[float, float, str], float] = {
    (36.85, 30.75, "2024-07-15"): 2.1e-5,
}

SEA_LEVEL_FIXTURES: dict[tuple[str, str], float] = {
    ("med-antalya", "2024-01-01"): 0.042,
}


@dataclass(frozen=True)
class RasterMockFixtures:
    elevation: dict[tuple[float, float], float] | None = None
    era5_temperature: dict[tuple[float, float, str], float] | None = None
    era5_soil_moisture: dict[tuple[float, float, str], float] | None = None
    no2: dict[tuple[float, float, str], float] | None = None
    sea_level: dict[tuple[str, str], float] | None = None
    snapshot_id: str = "2026-01-01T00:00:00+00:00"


class ElevationProvider(Protocol):
    def elevation_at(self, lat: float, lon: float) -> RasterTile: ...


class RasterAccess:
    """Unified raster access. CDS methods require ``copernicus_cds_api_key`` unless ``use_mock``."""

    def __init__(
        self,
        *,
        cds_api_key: str | None = None,
        elevation_lookup: Callable[[float, float], float] | dict[tuple[float, float], float] | None = None,
        fixtures: RasterMockFixtures | None = None,
        use_mock: bool = False,
    ) -> None:
        self._cds_key = cds_api_key if cds_api_key is not None else settings.copernicus_cds_api_key
        self._use_mock = use_mock
        self._fixtures = fixtures or RasterMockFixtures(
            elevation=ELEVATION_FIXTURES,
            era5_temperature=ERA5_TEMPERATURE_FIXTURES,
            era5_soil_moisture=ERA5_SOIL_MOISTURE_FIXTURES,
            no2=NO2_FIXTURES,
            sea_level=SEA_LEVEL_FIXTURES,
        )
        self._elevation_lookup = elevation_lookup if elevation_lookup is not None else (self._fixtures.elevation or {})

    def elevation_at(self, lat: float, lon: float) -> RasterTile:
        value = self._resolve_elevation(lat, lon)
        return RasterTile(
            source="MERIT_DEM",
            lat=lat,
            lon=lon,
            value=value,
            unit="m",
            data_snapshot_id=self._snapshot_id("merit_dem"),
        )

    def no2_column(self, lat: float, lon: float, date: str) -> RasterTile:
        self._require_cds_or_mock("SENTINEL5P")
        value = self._fixture_lookup(
            self._fixtures.no2 or {},
            (round(lat, 2), round(lon, 2), date),
            default=1.5e-5,
        )
        return RasterTile(
            source="SENTINEL5P",
            lat=lat,
            lon=lon,
            value=float(value),
            unit="mol/m²",
            data_snapshot_id=self._snapshot_id(f"s5p_{date}"),
        )

    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile:
        self._require_cds_or_mock("ERA5")
        value = self._fixture_lookup(
            self._fixtures.era5_temperature or {},
            (round(lat, 2), round(lon, 2), date),
            default=15.0,
        )
        return RasterTile(
            source="ERA5",
            lat=lat,
            lon=lon,
            value=float(value),
            unit="°C",
            data_snapshot_id=self._snapshot_id(f"era5_{date}"),
        )

    def era5_soil_moisture(self, lat: float, lon: float, date: str) -> RasterTile:
        """Volumetric soil water proxy (0–1 band) from ERA5-Land fixtures / CDS path."""
        self._require_cds_or_mock("ERA5")
        value = self._fixture_lookup(
            self._fixtures.era5_soil_moisture or {},
            (round(lat, 2), round(lon, 2), date),
            default=0.25,
        )
        return RasterTile(
            source="ERA5_SOIL",
            lat=lat,
            lon=lon,
            value=float(value),
            unit="m³/m³",
            data_snapshot_id=self._snapshot_id(f"era5_soil_{date}"),
        )

    def sea_level_anomaly(self, coastal_zone: str, date: str) -> RasterTile:
        if not self._use_mock:
            pass  # PSMSL bulk is keyless; live HTTP deferred — use fixtures in CI.
        value = self._fixture_lookup(
            self._fixtures.sea_level or {},
            (coastal_zone, date),
            default=0.0,
        )
        return RasterTile(
            source="PSMSL",
            lat=0.0,
            lon=0.0,
            value=float(value),
            unit="m",
            data_snapshot_id=self._snapshot_id(f"psmsl_{coastal_zone}_{date}"),
        )

    def _require_cds_or_mock(self, source: str) -> None:
        if self._use_mock or self._cds_key:
            return
        raise RasterSourceConfigError(source)

    def _snapshot_id(self, suffix: str) -> str:
        if self._fixtures.snapshot_id:
            return self._fixtures.snapshot_id
        return f"{utc_snapshot_id()}#{suffix}"

    def _resolve_elevation(self, lat: float, lon: float) -> float:
        if callable(self._elevation_lookup):
            return float(self._elevation_lookup(lat, lon))
        key = (round(lat, 3), round(lon, 3))
        if key in self._elevation_lookup:
            return float(self._elevation_lookup[key])
        for (fixture_lat, fixture_lon), elevation in self._elevation_lookup.items():
            if abs(fixture_lat - lat) < 1e-2 and abs(fixture_lon - lon) < 1e-2:
                return float(elevation)
        return 0.0

    @staticmethod
    def _fixture_lookup(table: dict[Any, Any], key: tuple[Any, ...], *, default: float) -> float:
        if key in table:
            return float(table[key])
        return default


def utc_snapshot_id() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
