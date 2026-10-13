"""SYNTHETIC-LABELLED hazard fixtures for offline demos and tests.

These values are **not** real observations. Every fixture snapshot is stamped
``synthetic=True`` and its sources carry ``SYNTHETIC-FIXTURE`` method versions,
so it can never be mistaken for a sealed real capture (which the pipeline labels
"SEALED REAL CAPTURE"). Use only to exercise wiring and output shape when the
real snapshot has not been captured (egress blocked).

To produce a *real* snapshot instead, run
``scripts/capture_real_hazard_snapshots.py`` where egress admits the Open-Meteo
hosts.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.connectors.open_meteo import HOT_DAY_THRESHOLD_C
from app.nl_pilot.hazard_snapshot import build_derived_snapshot
from app.nl_pilot.real_assets import RealAmsterdamAsset

FIXTURE_HEAT_METHOD = "SYNTHETIC-FIXTURE-heat-v0.1"
FIXTURE_ELEVATION_METHOD = "SYNTHETIC-FIXTURE-elevation-v0.1"


def _unit(seed: str) -> float:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)


def _fixture_elevation_m(lat: float, lon: float) -> float:
    # Plausible Amsterdam range [-3, +5] m — SYNTHETIC, deterministic per point.
    return round(-3.0 + _unit(f"elev|{lat:.5f}|{lon:.5f}") * 8.0, 3)


def _fixture_p95_tmax_c(lat: float, lon: float) -> float:
    # Plausible NL summer 95th-pct Tmax range [27, 32] °C — SYNTHETIC.
    return round(27.0 + _unit(f"tmax|{lat:.5f}|{lon:.5f}") * 5.0, 4)


def synthetic_fixture_snapshot(
    assets: list[RealAmsterdamAsset],
    *,
    snapshot_id: str = "hazard-amsterdam-fixture-v1",
) -> dict[str, Any]:
    """Build a labelled synthetic derived snapshot covering the pilot coordinates."""
    heat_points: list[dict[str, Any]] = []
    elevation_points: list[dict[str, Any]] = []
    for a in assets:
        lat, lon = float(a.coordinates_y), float(a.coordinates_x)
        p95 = _fixture_p95_tmax_c(lat, lon)
        heat_points.append(
            {
                "latitude": lat,
                "longitude": lon,
                "p95_tmax_c": p95,
                "record_tmax_c": round(p95 + 4.0, 4),
                "mean_annual_hot_days": round(_unit(f"hd|{lat}|{lon}") * 8.0, 4),
                "sample_days": 3653,
                "first_date": "2015-01-01",
                "last_date": "2024-12-31",
                "hot_day_threshold_c": HOT_DAY_THRESHOLD_C,
                "method_version": FIXTURE_HEAT_METHOD,
            }
        )
        elevation_points.append(
            {
                "latitude": lat,
                "longitude": lon,
                "elevation_m": _fixture_elevation_m(lat, lon),
                "datum": "orthometric (EGM2008 geoid)",
                "method_version": FIXTURE_ELEVATION_METHOD,
            }
        )
    return build_derived_snapshot(
        snapshot_id=snapshot_id,
        heat_source={
            "authority": "SYNTHETIC TEST FIXTURE — not real observations",
            "method_version": FIXTURE_HEAT_METHOD,
        },
        heat_points=heat_points,
        elevation_source={
            "authority": "SYNTHETIC TEST FIXTURE — not real observations",
            "method_version": FIXTURE_ELEVATION_METHOD,
        },
        elevation_points=elevation_points,
        synthetic=True,
    )


__all__ = ["synthetic_fixture_snapshot"]
