#!/usr/bin/env python3
"""Build + seal a flood-source evidence pack for a vendored real flood-hazard map.

The evidence pack is what the source-qualification gate
(``app.loss.flood_source_qualification``) evaluates: it binds a licence, a datum,
a methodology citation, and the required coverage to the EXACT sealed map artifact
by SHA-256. This script reads a real (non-synthetic, provenance-verified) map,
computes its hash, and writes the sealed pack. It refuses a synthetic map — a
labelled fixture can never be qualified.

Usage:
    PYTHONPATH=. python scripts/build_flood_evidence_pack.py \
        --map app/loss/curves/flood_hazard_map_v1.0.json \
        --source-id nl_liwo_flood_hazard \
        --licensor "Rijkswaterstaat / LIWO" --use-rights public-with-attribution \
        --attribution "Bron: LIWO, Rijkswaterstaat" --valid-from 2026-01-01 \
        --methodology "NL LIWO overstromingsdiepte, <ref/DOI>" \
        --point 52.3782,4.8835,pilot-cluster --point 52.3698,4.9247,pilot-outlier \
        --return-period 100 \
        --out config/flood_evidence/nl_liwo_flood_hazard.pack.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.flood_hazard_map import load_flood_hazard_map_from_path  # noqa: E402
from app.loss.flood_source_qualification import (  # noqa: E402
    FloodMapLicence,
    FloodSourceEvidencePack,
    RequiredPoint,
)


def _point(spec: str) -> RequiredPoint:
    parts = spec.split(",")
    if len(parts) < 2:
        raise SystemExit(f"--point must be lat,lon[,label]; got {spec!r}")
    lat, lon = float(parts[0]), float(parts[1])
    label = parts[2].strip() if len(parts) > 2 else ""
    return RequiredPoint(lat=lat, lon=lon, label=label)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", required=True, help="Path to the sealed real flood-hazard map JSON.")
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--licensor", required=True)
    ap.add_argument("--use-rights", required=True)
    ap.add_argument("--attribution", required=True)
    ap.add_argument("--valid-from", required=True, help="ISO date the licence takes effect.")
    ap.add_argument("--valid-until", help="ISO date the licence expires (optional).")
    ap.add_argument("--methodology", required=True, help="Citation of the flood-hazard source.")
    ap.add_argument("--point", action="append", required=True, help="lat,lon[,label] (repeatable).")
    ap.add_argument("--return-period", action="append", type=int, required=True,
                    help="Required return period in years (repeatable).")
    ap.add_argument("--out", required=True, help="Output path for the sealed pack JSON.")
    args = ap.parse_args()

    map_path = Path(args.map)
    fmap = load_flood_hazard_map_from_path(map_path)  # provenance-verified for a real map
    if fmap.synthetic:
        raise SystemExit(
            f"refusing to build an evidence pack for a SYNTHETIC map ({map_path.name}); "
            "vendor a real flood-hazard map first (scripts/vendor_flood_hazard_map.py)"
        )
    map_sha256 = hashlib.sha256(map_path.read_bytes()).hexdigest()

    pack = FloodSourceEvidencePack(
        source_id=args.source_id,
        map_artifact=map_path.name,
        map_artifact_sha256=map_sha256,
        datum=fmap.datum,
        licence=FloodMapLicence(
            licensor=args.licensor,
            use_rights=args.use_rights,
            attribution=args.attribution,
            valid_from=date.fromisoformat(args.valid_from),
            valid_until=date.fromisoformat(args.valid_until) if args.valid_until else None,
        ),
        methodology=args.methodology,
        required_points=[_point(s) for s in args.point],
        required_return_periods=list(dict.fromkeys(args.return_period)),
        note="Sealed flood-source evidence pack — qualifies the bound map artifact for use.",
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = pack.model_dump(mode="json")
    body["pack_sha256"] = pack.seal_sha256()  # the pack's own seal, for the record
    out_path.write_text(json.dumps(body, indent=2, ensure_ascii=True), encoding="utf-8")

    display = out_path.relative_to(_ROOT) if out_path.is_relative_to(_ROOT) else out_path
    print(f"Sealed flood-source evidence pack → {display}")
    print(f"  source_id: {pack.source_id}   datum: {pack.datum}   "
          f"points: {len(pack.required_points)}   return_periods: {pack.required_return_periods}")
    print(f"  map_artifact_sha256: {map_sha256}")
    print(f"  pack_sha256: {pack.seal_sha256()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
