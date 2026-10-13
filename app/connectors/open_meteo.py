"""Open-Meteo real-data connector — ERA5 reanalysis + Copernicus DEM.

Keyless, licensed public climate/elevation sources feeding the **real** hazard
layer of the five-layer pipeline. No credentials required.

Sources
-------
- **Extreme heat:** ERA5 daily ``temperature_2m_max`` via the Open-Meteo
  Archive API (``archive-api.open-meteo.com``). ERA5 is the ECMWF/Copernicus
  reanalysis — genuine observed-reanalysis temperature, not a stub.
- **Flood exposure:** Copernicus DEM GLO-90 orthometric ground elevation via
  the Open-Meteo Elevation API (``api.open-meteo.com/v1/elevation``). A real
  low-elevation exposure proxy (the NL Country Pack refines this with AHN's
  high-resolution DTM referenced to NAP).

Architecture (mirrors ``app/nl_pilot/bag_connector.py``)
-------------------------------------------------------
    live fetch → raw bytes → SHA-256 sealed snapshot → provenance manifest →
    deterministic replay from snapshot (CI / offline never hits the network).

Fail-closed
-----------
Network / HTTP / empty-result failures raise. There is **no synthetic
fallback** in this module — a missing real snapshot fails closed downstream
(see ``app/nl_pilot/hazard_snapshot.py``). The SHA-256-seeded ``StubHazard``
path is a separate, explicitly-labelled artefact (STUBS.md #16a); this
connector never emits seeded values.

Egress note
-----------
Both hosts are external climate APIs. In a locked-down egress environment they
are blocked (403 at the proxy); capture must run where the allowlist admits
``archive-api.open-meteo.com`` and ``api.open-meteo.com``. Runtime replay from
a sealed snapshot needs no network.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Endpoints, licensing, versions
# ---------------------------------------------------------------------------

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

OPEN_METEO_LICENSE_ID = "CC-BY-4.0"
OPEN_METEO_LICENSE_NAME = "Open-Meteo data (CC-BY 4.0); ERA5 © Copernicus/ECMWF"
OPEN_METEO_LICENSE_URL = "https://open-meteo.com/en/license"

ERA5_AUTHORITY = "ECMWF / Copernicus Climate Change Service (via Open-Meteo)"
COPERNICUS_DEM_AUTHORITY = "Copernicus DEM GLO-90 (via Open-Meteo Elevation API)"

# Derivation methodology stamps (bump minor when the derivation formula changes).
HEAT_CLIMATOLOGY_METHOD_VERSION = "open-meteo-era5-heat-climatology-v0.1"
ELEVATION_METHOD_VERSION = "open-meteo-copernicus-dem-elevation-v0.1"

# Chronic/acute heatwave threshold used for the "hot day" frequency metric (°C).
HOT_DAY_THRESHOLD_C = 30.0


# ---------------------------------------------------------------------------
# Raw fetch result (preserves exact response bytes for sealing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawFetchResult:
    source_url: str
    raw_bytes: bytes
    content_type: str
    retrieved_at: str  # ISO 8601 UTC
    http_status: int

    def validate(self) -> None:
        if self.http_status != 200:
            raise RuntimeError(f"HTTP {self.http_status} for {self.source_url}")
        if not self.raw_bytes:
            raise RuntimeError(f"Empty response body for {self.source_url}")


def _http_get(url: str, params: dict[str, Any]) -> RawFetchResult:
    """GET JSON from an Open-Meteo endpoint, preserving raw bytes.

    Raises ``RuntimeError`` on network / HTTP / empty-body failure (fail-closed).
    """
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (fixed hosts)
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "application/json")
            http_status = resp.status
    except Exception as exc:  # noqa: BLE001 — re-raised as fail-closed
        raise RuntimeError(f"Open-Meteo fetch failed from {full_url}: {exc}") from exc

    result = RawFetchResult(
        source_url=full_url,
        raw_bytes=raw,
        content_type=content_type,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        http_status=http_status,
    )
    result.validate()
    return result


# ---------------------------------------------------------------------------
# Live fetch — one point per call (unambiguous per-point provenance)
# ---------------------------------------------------------------------------


def fetch_era5_tmax(
    latitude: float,
    longitude: float,
    *,
    start_date: str,
    end_date: str,
) -> RawFetchResult:
    """Fetch ERA5 daily maximum 2 m temperature for one point over a window."""
    return _http_get(
        OPEN_METEO_ARCHIVE_URL,
        {
            "latitude": f"{latitude:.5f}",
            "longitude": f"{longitude:.5f}",
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max",
            "timezone": "UTC",
        },
    )


def fetch_dem_elevation(latitude: float, longitude: float) -> RawFetchResult:
    """Fetch Copernicus DEM GLO-90 orthometric ground elevation for one point."""
    return _http_get(
        OPEN_METEO_ELEVATION_URL,
        {"latitude": f"{latitude:.5f}", "longitude": f"{longitude:.5f}"},
    )


# ---------------------------------------------------------------------------
# Pure derivations (no I/O) — operate on parsed payloads
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolation percentile on an already-sorted list."""
    if not sorted_values:
        raise ValueError("percentile of empty series")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


@dataclass(frozen=True)
class HeatPointStat:
    """Real heat-hazard climatology derived from ERA5 daily Tmax."""

    latitude: float
    longitude: float
    p95_tmax_c: float
    record_tmax_c: float
    mean_annual_hot_days: float  # days/yr with Tmax >= HOT_DAY_THRESHOLD_C
    sample_days: int
    first_date: str
    last_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "p95_tmax_c": round(self.p95_tmax_c, 4),
            "record_tmax_c": round(self.record_tmax_c, 4),
            "mean_annual_hot_days": round(self.mean_annual_hot_days, 4),
            "sample_days": self.sample_days,
            "first_date": self.first_date,
            "last_date": self.last_date,
            "hot_day_threshold_c": HOT_DAY_THRESHOLD_C,
            "method_version": HEAT_CLIMATOLOGY_METHOD_VERSION,
        }


def heat_climatology_from_archive(payload: dict[str, Any]) -> HeatPointStat:
    """Derive a real heat climatology from an ERA5 archive payload.

    The 95th-percentile daily Tmax is the acute-heat intensity driver (fed to
    ``ExtremeHeatHazardModule`` unchanged); hot-day frequency is retained as
    corroborating evidence. Both are genuine observed-reanalysis statistics.
    """
    lat = float(payload.get("latitude"))
    lon = float(payload.get("longitude"))
    daily = payload.get("daily") or {}
    times = list(daily.get("time") or [])
    raw_tmax = list(daily.get("temperature_2m_max") or [])
    pairs = [
        (t, float(v))
        for t, v in zip(times, raw_tmax)
        if v is not None
    ]
    if not pairs:
        raise ValueError("ERA5 archive payload has no temperature_2m_max samples")
    values = sorted(v for _, v in pairs)
    dates = [t for t, _ in pairs]
    p95 = _percentile(values, 95.0)
    record = values[-1]
    hot_days = sum(1 for v in values if v >= HOT_DAY_THRESHOLD_C)
    span_days = len(pairs)
    years = max(span_days / 365.25, 1e-9)
    return HeatPointStat(
        latitude=lat,
        longitude=lon,
        p95_tmax_c=p95,
        record_tmax_c=record,
        mean_annual_hot_days=hot_days / years,
        sample_days=span_days,
        first_date=min(dates),
        last_date=max(dates),
    )


@dataclass(frozen=True)
class ElevationPoint:
    """Real orthometric ground elevation from Copernicus DEM GLO-90."""

    latitude: float
    longitude: float
    elevation_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation_m": round(self.elevation_m, 3),
            "datum": "orthometric (EGM2008 geoid)",
            "method_version": ELEVATION_METHOD_VERSION,
        }


def elevation_from_payload(
    payload: dict[str, Any],
    *,
    latitude: float,
    longitude: float,
) -> ElevationPoint:
    """Parse the Open-Meteo elevation payload for one requested point."""
    elevations = payload.get("elevation")
    if not isinstance(elevations, list) or not elevations:
        raise ValueError("Open-Meteo elevation payload missing 'elevation' array")
    value = elevations[0]
    if value is None:
        raise ValueError("Open-Meteo elevation payload returned null elevation")
    return ElevationPoint(
        latitude=float(latitude),
        longitude=float(longitude),
        elevation_m=float(value),
    )


__all__ = [
    "COPERNICUS_DEM_AUTHORITY",
    "ELEVATION_METHOD_VERSION",
    "ERA5_AUTHORITY",
    "HEAT_CLIMATOLOGY_METHOD_VERSION",
    "HOT_DAY_THRESHOLD_C",
    "OPEN_METEO_ARCHIVE_URL",
    "OPEN_METEO_ELEVATION_URL",
    "OPEN_METEO_LICENSE_ID",
    "OPEN_METEO_LICENSE_NAME",
    "OPEN_METEO_LICENSE_URL",
    "ElevationPoint",
    "HeatPointStat",
    "RawFetchResult",
    "elevation_from_payload",
    "fetch_dem_elevation",
    "fetch_era5_tmax",
    "heat_climatology_from_archive",
]
