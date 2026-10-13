#!/usr/bin/env python3
"""Vendor real AHN ground elevations into a sealed elevation snapshot.

AHN (Actueel Hoogtebestand Nederland) is the authoritative Dutch elevation model
— high-resolution DTM referenced to NAP — published via PDOK (Public Domain).
Because AHN is served as raster coverages (WCS GeoTIFF), point elevations are
extracted in a networked step (PDOK AHN viewer / WCS / OGC API) and handed here
as a **normalized CSV**, then sealed with provenance. Consistent with the JRC
vendor pattern: no value is invented, and sealing needs no egress.

Normalized CSV schema (header required):
    latitude,longitude,elevation_m
    52.37822,4.88347,-1.85
    ...
Optional column ``asset_id`` is preserved if present. Elevations are metres
w.r.t. NAP (same datum the flood reference level uses).

Usage:
    PYTHONPATH=. python scripts/vendor_ahn_elevation.py --from-csv ahn.csv \
        [--snapshot-id ahn-elevation-amsterdam-v1]
    # → data/nl_pilot/snapshots/hazard/<id>.json  (+ .provenance.json)

Where to get the data: PDOK AHN (https://www.pdok.nl) — AHN WCS
`service.pdok.nl/rws/ahn/wcs/v1_0` GetCoverage, the AHN viewer, or the OGC API.
Sample each asset coordinate, write the CSV above, then run this.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SNAP_DIR = _ROOT / "data" / "nl_pilot" / "snapshots" / "hazard"

AHN_AUTHORITY = "AHN (Actueel Hoogtebestand Nederland) via PDOK"
AHN_LICENSE = "Public Domain (PDOK / Kadaster)"
AHN_DATUM = "NAP (orthometric, metres)"
AHN_METHOD_VERSION = "ahn-dtm-nap-v1.0"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"latitude", "longitude", "elevation_m"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")
        points: list[dict] = []
        for i, row in enumerate(reader, start=2):
            try:
                pt = {
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "elevation_m": float(row["elevation_m"]),
                    "datum": AHN_DATUM,
                    "method_version": AHN_METHOD_VERSION,
                }
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"CSV row {i} invalid: {exc}") from exc
            if row.get("asset_id"):
                pt["asset_id"] = row["asset_id"].strip()
            points.append(pt)
    if not points:
        raise SystemExit("CSV had no data rows")
    return points


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", required=True, help="Normalized AHN CSV (see schema).")
    parser.add_argument("--snapshot-id", default="ahn-elevation-amsterdam-v1")
    args = parser.parse_args()

    points = _read_csv(Path(args.from_csv))
    _SNAP_DIR.mkdir(parents=True, exist_ok=True)

    derived = {
        "snapshot_id": args.snapshot_id,
        "schema_version": "ahn-elevation-v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "crs": "EPSG:4326",
        "synthetic": False,
        "source": {
            "authority": AHN_AUTHORITY,
            "license": AHN_LICENSE,
            "datum": AHN_DATUM,
            "method_version": AHN_METHOD_VERSION,
        },
        "points": points,
    }
    out_path = _SNAP_DIR / f"{args.snapshot_id}.json"
    raw = json.dumps(derived, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")
    out_path.write_bytes(raw)

    provenance = {
        "snapshot_id": args.snapshot_id,
        "authority": AHN_AUTHORITY,
        "license": AHN_LICENSE,
        "datum": AHN_DATUM,
        "vendored_at": datetime.now(timezone.utc).isoformat(),
        "vendored_from_csv": str(Path(args.from_csv).resolve()),
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "point_count": len(points),
    }
    (_SNAP_DIR / f"{args.snapshot_id}.provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8"
    )

    print(f"Sealed real AHN elevation snapshot → {out_path.relative_to(_ROOT)}")
    print(f"  points        : {len(points)}")
    print(f"  artifact_sha256: {provenance['artifact_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
