#!/usr/bin/env python3
"""Vendor an authentic return-period flood-hazard map into a sealed catalogue.

Per-cell water levels by return period, from a real flood-hazard source (e.g. NL
LIWO, or a Country-Pack flood-extent product), in the SAME datum as the elevation
the engine uses (NAP for the NL pilot). Hand them here as a normalized CSV and
they are sealed with a SHA-256 provenance sidecar. No value is invented; the CSV
must come from the cited source.

Normalized CSV schema (header required):
    lat,lon,return_period_years,water_level_m
    52.38,4.88,100,1.62
    52.37,4.92,100,1.41

Each row's cell id is derived from lat/lon at the map's cell size, so many raw
points collapse onto the grid; a duplicate (cell, return_period) is rejected.

Usage:
    PYTHONPATH=. python scripts/vendor_flood_hazard_map.py --from-csv f.csv \
        --source "NL LIWO overstromingsdiepte, <ref/DOI>" \
        [--datum NAP] [--cell-size 0.01] [--version 1.0]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.flood_hazard_map import FloodHazardMap, ReturnPeriodWaterLevel  # noqa: E402

_CURVES_DIR = _ROOT / "app" / "loss" / "curves"
MAP_ID = "flood_hazard_map"


def _cell_id(lat: float, lon: float, size: float) -> str:
    la = round(round(lat / size) * size, 6)
    lo = round(round(lon / size) * size, 6)
    return f"{la + 0.0:g},{lo + 0.0:g}"


def _read_csv(path: Path, *, cell_size: float) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"lat", "lon", "return_period_years", "water_level_m"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")
        rows: list[dict] = []
        for i, row in enumerate(reader, start=2):
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
                lvl = ReturnPeriodWaterLevel(
                    cell_id=_cell_id(lat, lon, cell_size),
                    return_period_years=int(row["return_period_years"]),
                    water_level_m=float(row["water_level_m"]),
                )
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"CSV row {i} invalid: {exc}") from exc
            rows.append({
                "cell_id": lvl.cell_id,
                "return_period_years": lvl.return_period_years,
                "water_level_m": lvl.water_level_m,
            })
    if not rows:
        raise SystemExit("CSV had no data rows")
    # Fail-closed on a duplicate (cell, return_period): a lookup must be single-valued.
    seen: set[tuple[str, int]] = set()
    for r in rows:
        key = (r["cell_id"], r["return_period_years"])
        if key in seen:
            raise SystemExit(
                f"duplicate (cell, return_period) {key} after gridding at "
                f"cell_size={cell_size}; deduplicate the source rows"
            )
        seen.add(key)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", required=True)
    parser.add_argument("--source", required=True, help="Full citation of the flood-hazard source.")
    parser.add_argument("--datum", default="NAP", help="Elevation datum shared with AHN/DEM.")
    parser.add_argument("--cell-size", type=float, default=0.01, help="Grid cell size in degrees.")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()

    if args.cell_size <= 0:
        raise SystemExit("--cell-size must be positive")
    levels = _read_csv(Path(args.from_csv), cell_size=args.cell_size)

    fhm = {
        "map_id": MAP_ID,
        "version": args.version,
        "source": args.source,
        "datum": args.datum,
        "cell_size_deg": args.cell_size,
        "synthetic": False,
        "populated": True,
        "methodology_note": (
            "Authentic per-cell return-period water levels vendored from the cited "
            "flood-hazard source. inundation_depth = max(0, water_level - ground_elevation), "
            "both in the stated datum; fed to the JRC depth-damage curves."
        ),
        "levels": levels,
    }
    # Validate the whole map before sealing (rejects duplicates, non-finite, etc.).
    FloodHazardMap(**fhm)

    out_path = _CURVES_DIR / f"{MAP_ID}_v{args.version}.json"
    raw = json.dumps(fhm, indent=2, ensure_ascii=True).encode("utf-8")
    out_path.write_bytes(raw)
    (_CURVES_DIR / f"{MAP_ID}_v{args.version}.provenance.json").write_text(
        json.dumps(
            {
                "map_id": MAP_ID,
                "version": args.version,
                "source": args.source,
                "datum": args.datum,
                "cell_size_deg": args.cell_size,
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "cell_count": len({lvl["cell_id"] for lvl in levels}),
                "level_count": len(levels),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    display = out_path.relative_to(_ROOT) if out_path.is_relative_to(_ROOT) else out_path
    print(f"Sealed flood-hazard map → {display}")
    print(f"  source: {args.source}   datum: {args.datum}   cells: "
          f"{len({lvl['cell_id'] for lvl in levels})}   levels: {len(levels)}")
    print(f"  artifact_sha256: {hashlib.sha256(raw).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
