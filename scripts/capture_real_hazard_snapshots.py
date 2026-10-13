#!/usr/bin/env python3
"""Capture real hazard snapshots for the Amsterdam pilot (one networked step).

Fetches, for each sealed pilot asset coordinate:
  * ERA5 daily max 2 m temperature (Open-Meteo Archive API) → heat climatology
  * Copernicus DEM GLO-90 ground elevation (Open-Meteo Elevation API)

then seals a derived snapshot + SHA-256 provenance manifest under
``data/nl_pilot/``. After this runs once (in an environment whose egress
allowlist admits ``archive-api.open-meteo.com`` and ``api.open-meteo.com``),
the five-layer pipeline replays real EAL deterministically, offline, forever.

Usage:
    PYTHONPATH=. python scripts/capture_real_hazard_snapshots.py \
        [--start 2015-01-01] [--end 2024-12-31] [--snapshot-id hazard-amsterdam-v1]

Egress-blocked environments fail with a clear message naming the two hosts to
allowlist — never a synthetic fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.connectors.open_meteo import (  # noqa: E402
    COPERNICUS_DEM_AUTHORITY,
    ELEVATION_METHOD_VERSION,
    ERA5_AUTHORITY,
    HEAT_CLIMATOLOGY_METHOD_VERSION,
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_ELEVATION_URL,
    OPEN_METEO_LICENSE_ID,
    OPEN_METEO_LICENSE_NAME,
    OPEN_METEO_LICENSE_URL,
    elevation_from_payload,
    fetch_dem_elevation,
    fetch_era5_tmax,
    heat_climatology_from_archive,
)
from app.nl_pilot.hazard_snapshot import (  # noqa: E402
    DEFAULT_SNAPSHOT_ID,
    build_derived_snapshot,
    seal_snapshot_to_disk,
)
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2015-01-01", help="ERA5 window start (UTC).")
    parser.add_argument("--end", default="2024-12-31", help="ERA5 window end (UTC, < valuation).")
    parser.add_argument("--snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    args = parser.parse_args()

    assets = load_pilot_assets(_ROOT)
    print(f"Capturing real hazard data for {len(assets)} sealed pilot assets…")

    heat_points: list[dict] = []
    elevation_points: list[dict] = []
    try:
        for a in assets:
            lat, lon = float(a.coordinates_y), float(a.coordinates_x)
            archive = json.loads(
                fetch_era5_tmax(lat, lon, start_date=args.start, end_date=args.end).raw_bytes
            )
            heat_points.append(heat_climatology_from_archive(archive).to_dict())

            elev_raw = json.loads(fetch_dem_elevation(lat, lon).raw_bytes)
            elevation_points.append(
                elevation_from_payload(elev_raw, latitude=lat, longitude=lon).to_dict()
            )
            print(
                f"  {a.asset_id}  lat={lat:.5f} lon={lon:.5f}  "
                f"p95Tmax={heat_points[-1]['p95_tmax_c']}°C  "
                f"elev={elevation_points[-1]['elevation_m']} m"
            )
    except RuntimeError as exc:
        print("\nCAPTURE FAILED (fail-closed — no synthetic fallback):", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print(
            "\nThis environment's egress policy is blocking the climate APIs.\n"
            "Allowlist these two hosts, then re-run:\n"
            "  - archive-api.open-meteo.com   (ERA5 daily Tmax)\n"
            "  - api.open-meteo.com           (Copernicus DEM elevation)\n",
            file=sys.stderr,
        )
        return 2

    heat_source = {
        "authority": ERA5_AUTHORITY,
        "source_url_template": (
            f"{OPEN_METEO_ARCHIVE_URL}?latitude=..&longitude=..&"
            f"start_date={args.start}&end_date={args.end}&daily=temperature_2m_max"
        ),
        "window": {"start_date": args.start, "end_date": args.end},
        "variable": "temperature_2m_max",
        "method_version": HEAT_CLIMATOLOGY_METHOD_VERSION,
        "license_id": OPEN_METEO_LICENSE_ID,
        "license_name": OPEN_METEO_LICENSE_NAME,
        "license_url": OPEN_METEO_LICENSE_URL,
    }
    elevation_source = {
        "authority": COPERNICUS_DEM_AUTHORITY,
        "source_url_template": f"{OPEN_METEO_ELEVATION_URL}?latitude=..&longitude=..",
        "dataset": "Copernicus DEM GLO-90",
        "method_version": ELEVATION_METHOD_VERSION,
        "license_id": OPEN_METEO_LICENSE_ID,
        "license_name": OPEN_METEO_LICENSE_NAME,
        "license_url": OPEN_METEO_LICENSE_URL,
    }

    derived = build_derived_snapshot(
        snapshot_id=args.snapshot_id,
        heat_source=heat_source,
        heat_points=heat_points,
        elevation_source=elevation_source,
        elevation_points=elevation_points,
        synthetic=False,
    )
    manifest = seal_snapshot_to_disk(derived, project_root=_ROOT, snapshot_id=args.snapshot_id)
    entry = manifest["sources"][args.snapshot_id]
    print("\nSealed real hazard snapshot:")
    print(f"  path          : {entry['snapshot_path']}")
    print(f"  artifact_sha256: {entry['artifact_sha256']}")
    print(f"  points        : {len(elevation_points)}")
    print("\nNow run the real five-layer demo:")
    print("  PYTHONPATH=. python scripts/run_real_hazard_demo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
