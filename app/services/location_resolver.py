from __future__ import annotations

import re
from typing import Literal

import httpx

from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.sector_registry import DEFAULT_SECTOR_ID
from app.schemas.preview import ResolvedLocation
from app.services.demo_service import DemoService

_COORD_PAIR = re.compile(
    r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)
_COORD_LABEL = re.compile(
    r"(-?\d{1,2}(?:\.\d+)?)\s*°?\s*[Nn]?\s*[,;\s]\s*"
    r"(-?\d{1,3}(?:\.\d+)?)\s*°?\s*[EeWw]?\s*"
)

# Curated aliases for landing-page hints and smoke tests (no external geocoder).
_ADDRESS_ALIASES: dict[str, tuple[float, float, str]] = {
    "houston": (29.7356, -95.0835, "Houston Ship Channel (indicative)"),
    "houston ship channel": (29.7356, -95.0835, "Houston Ship Channel (indicative)"),
    "houston refineries": (29.7604, -95.3698, "Houston refineries (indicative)"),
    "istanbul": (41.0082, 28.9784, "Istanbul (indicative)"),
    "ankara": (39.9334, 32.8597, "Ankara (indicative)"),
    "afyon": (38.7507, 30.5567, "Afyonkarahisar (indicative)"),
}

ResolutionMethod = Literal["coordinates", "demo_asset", "address_alias", "geocoder"]


class LocationResolver:
    def __init__(self, demo: DemoService | None = None) -> None:
        self._demo = demo or DemoService()

    def resolve(
        self,
        location: str,
        *,
        asset_name: str | None = None,
        radius_km: float = 10.0,
        sector: str = DEFAULT_SECTOR_ID,
    ) -> ResolvedLocation:
        raw = location.strip()
        if not raw:
            raise GeoRiskApiError(
                "location_empty",
                "Location is required (coordinates, address, or demo asset id).",
                status_code=422,
            )

        coords = self._parse_coordinates(raw)
        if coords is not None:
            lat, lon = coords
            return ResolvedLocation(
                latitude=lat,
                longitude=lon,
                radius_km=radius_km,
                asset_name=asset_name or f"Location {lat:.4f}, {lon:.4f}",
                sector=sector,
                resolution_method="coordinates",
                resolution_detail=raw,
            )

        preset = self._demo.get_preset_asset(raw)
        if preset is None:
            slug = raw.lower().replace(" ", "_")
            preset = self._demo.get_preset_asset(slug)
        if preset is not None:
            return ResolvedLocation(
                latitude=preset["latitude"],
                longitude=preset["longitude"],
                radius_km=preset.get("radius_km", radius_km),
                asset_name=asset_name or preset["name"],
                sector=preset.get("sector", sector),
                resolution_method="demo_asset",
                resolution_detail=preset["id"],
            )

        alias_key = raw.lower().strip()
        if alias_key in _ADDRESS_ALIASES:
            lat, lon, label = _ADDRESS_ALIASES[alias_key]
            return ResolvedLocation(
                latitude=lat,
                longitude=lon,
                radius_km=radius_km,
                asset_name=asset_name or label,
                sector=sector,
                resolution_method="address_alias",
                resolution_detail=alias_key,
            )

        if settings.georisk_geocoder == "nominatim":
            geocoded = self._nominatim_geocode(raw)
            if geocoded is not None:
                lat, lon, display = geocoded
                return ResolvedLocation(
                    latitude=lat,
                    longitude=lon,
                    radius_km=radius_km,
                    asset_name=asset_name or display,
                    sector=sector,
                    resolution_method="geocoder",
                    resolution_detail="nominatim",
                )

        raise GeoRiskApiError(
            "location_unresolved",
            (
                "Could not resolve location. Use lat,lon (e.g. 36.85,30.75), "
                "a demo asset id (coastal_industrial_med), a known city alias, "
                "or set GEORISK_GEOCODER=nominatim for free-text addresses."
            ),
            status_code=422,
        )

    @staticmethod
    def _parse_coordinates(text: str) -> tuple[float, float] | None:
        m = _COORD_PAIR.match(text)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = _COORD_LABEL.search(text)
        if m:
            return float(m.group(1)), float(m.group(2))
        return None

    @staticmethod
    def _nominatim_geocode(query: str) -> tuple[float, float, str] | None:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": settings.georisk_geocoder_user_agent}
        try:
            with httpx.Client(timeout=settings.georisk_geocoder_timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not data:
            return None
        first = data[0]
        return float(first["lat"]), float(first["lon"]), str(first.get("display_name", query))
