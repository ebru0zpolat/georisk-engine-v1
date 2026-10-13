#!/usr/bin/env python3
"""Vendor authentic JRC depth-damage curves into a sealed catalogue.

The JRC *Global flood depth-damage functions* database (Huizinga, de Moel,
Szewczyk, 2017; EUR 28552 EN, JRC105688) is openly published and
redistributable. Because the raw report ships as an Excel workbook, this script
takes a **normalized CSV** — one authentic (depth_m, damage_ratio) row per
occupancy×continent — and seals it into a versioned catalogue with provenance.
No values are invented; the CSV must come from the JRC source.

Normalized CSV schema (header required), one row per depth sample:
    continent,occupancy,depth_m,damage_ratio
    Europe,residential,0.0,0.00
    Europe,residential,0.5,0.25
    ...
`continent` may be `*` for a global default. `occupancy` is one of
residential / commercial / industrial / agriculture / infrastructure / transport.

Usage:
    PYTHONPATH=. python scripts/vendor_jrc_depth_damage.py --from-csv path/to/jrc.csv
    # → app/loss/curves/jrc_global_depth_damage_v1.0.json  (+ .provenance.json)

Where to get the data: JRC Publications Office EUR 28552 EN (Huizinga et al.,
2017) and its supplementary depth-damage database. Convert the relevant sheet to
the CSV schema above, then run this.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.depth_damage_curves import DepthDamageCurve, DepthDamagePoint  # noqa: E402

_CURVES_DIR = _ROOT / "app" / "loss" / "curves"
CATALOGUE_ID = "jrc_global_depth_damage"
CATALOGUE_VERSION = "1.0"
JRC_SOURCE = (
    "JRC Global flood depth-damage functions — Huizinga, de Moel, Szewczyk (2017), "
    "EUR 28552 EN, JRC105688. Openly published, redistributable."
)
JRC_LICENSE = "European Commission reuse policy (Decision 2011/833/EU), attribution required"


def _read_csv(path: Path) -> dict[tuple[str, str], list[DepthDamagePoint]]:
    grouped: dict[tuple[str, str], list[DepthDamagePoint]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"continent", "occupancy", "depth_m", "damage_ratio"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")
        for i, row in enumerate(reader, start=2):
            key = (row["continent"].strip().lower(), row["occupancy"].strip().lower())
            try:
                grouped[key].append(
                    DepthDamagePoint(
                        depth_m=float(row["depth_m"]),
                        damage_ratio=float(row["damage_ratio"]),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"CSV row {i} invalid: {exc}") from exc
    if not grouped:
        raise SystemExit("CSV had no data rows")
    return grouped


def _build_curves(grouped: dict[tuple[str, str], list[DepthDamagePoint]]) -> list[dict]:
    curves: list[dict] = []
    for (continent, occupancy), points in sorted(grouped.items()):
        pts = sorted(points, key=lambda p: p.depth_m)
        # Validate shape by constructing the model (raises on non-monotonic / <2 points).
        DepthDamageCurve(
            curve_id=f"jrc_{occupancy}_{continent}_flood".replace("*", "global"),
            occupancy=occupancy,
            continent=continent,
            hazard_id="flood",
            points=pts,
            source=JRC_SOURCE,
            synthetic=False,
            version=CATALOGUE_VERSION,
        )
        curves.append(
            {
                "curve_id": f"jrc_{occupancy}_{continent}_flood".replace("*", "global"),
                "occupancy": occupancy,
                "continent": continent,
                "hazard_id": "flood",
                "points": [{"depth_m": p.depth_m, "damage_ratio": p.damage_ratio} for p in pts],
            }
        )
    return curves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", required=True, help="Normalized JRC CSV (see schema).")
    args = parser.parse_args()

    grouped = _read_csv(Path(args.from_csv))
    curves = _build_curves(grouped)

    catalogue = {
        "catalogue_id": CATALOGUE_ID,
        "version": CATALOGUE_VERSION,
        "source": JRC_SOURCE,
        "synthetic": False,
        "populated": True,
        "methodology_note": (
            "Authentic JRC depth-damage curves vendored from the JRC 2017 database. "
            "depth_m -> damage_ratio, monotonic. Applying to an asset requires a real "
            "inundation depth (AHN elevation + return-period reference level)."
        ),
        "curves": curves,
    }
    out_path = _CURVES_DIR / f"{CATALOGUE_ID}_v{CATALOGUE_VERSION}.json"
    raw = json.dumps(catalogue, indent=2, ensure_ascii=True).encode("utf-8")
    out_path.write_bytes(raw)

    provenance = {
        "catalogue_id": CATALOGUE_ID,
        "version": CATALOGUE_VERSION,
        "source": JRC_SOURCE,
        "license": JRC_LICENSE,
        "vendored_at": datetime.now(timezone.utc).isoformat(),
        "vendored_from_csv": str(Path(args.from_csv).resolve()),
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "curve_count": len(curves),
        "occupancies": sorted({c["occupancy"] for c in curves}),
        "continents": sorted({c["continent"] for c in curves}),
    }
    (_CURVES_DIR / f"{CATALOGUE_ID}_v{CATALOGUE_VERSION}.provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    print(f"Sealed authentic JRC catalogue → {out_path.relative_to(_ROOT)}")
    print(f"  curves        : {len(curves)}")
    print(f"  occupancies   : {provenance['occupancies']}")
    print(f"  artifact_sha256: {provenance['artifact_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
