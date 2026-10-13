#!/usr/bin/env python3
"""Flood-source qualification demo — the fail-closed gate before v0.4 default.

Runs the source-qualification gate over the flood-hazard map + a bound evidence
pack, and prints the six controls and the verdict. Offline, the only map available
is the labelled SYNTHETIC fixture, so the gate returns **NOT QUALIFIED** — the
honest state: every other control can pass, but a synthetic source can never be
qualified. Vendor a real map + seal a real pack to reach QUALIFIED.

This gate is a prerequisite for — but does NOT perform — promoting v0.4 flood to
default; that is a separate decision after this gate closes and exact-head review.

Usage:
    PYTHONPATH=. python scripts/run_flood_source_qualification_demo.py \
        [--map F.json] [--pack P.json]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.flood_hazard_map import _CURVES_DIR  # noqa: E402
from app.loss.flood_source_qualification import (  # noqa: E402
    FloodMapLicence,
    FloodSourceEvidencePack,
    RequiredPoint,
    evaluate_flood_source_qualification,
    load_evidence_pack,
)

_FIXTURE_MAP = _CURVES_DIR / "flood_hazard_map_fixture_v0.1.json"


def _illustrative_pack(map_path: Path) -> FloodSourceEvidencePack:
    """A pack bound to the given map (fixture), with everything else in order —
    so the demo isolates the ONE failing control: a synthetic source."""
    sha = hashlib.sha256(map_path.read_bytes()).hexdigest()
    return FloodSourceEvidencePack(
        source_id="nl_liwo_flood_hazard",
        map_artifact=map_path.name,
        map_artifact_sha256=sha,
        datum="NAP",
        licence=FloodMapLicence(
            licensor="Rijkswaterstaat / LIWO", use_rights="public-with-attribution",
            attribution="Bron: LIWO, Rijkswaterstaat", valid_from=date(2026, 1, 1),
        ),
        methodology="ILLUSTRATIVE — NL LIWO overstromingsdiepte, <ref/DOI>",
        required_points=[RequiredPoint(lat=52.3782, lon=4.8835, label="pilot-cluster"),
                         RequiredPoint(lat=52.3698, lon=4.9247, label="pilot-outlier")],
        required_return_periods=[100],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", help="Sealed flood-hazard map JSON (else the labelled fixture).")
    ap.add_argument("--pack", help="Sealed evidence pack JSON (else an illustrative pack).")
    args = ap.parse_args()

    map_path = Path(args.map) if args.map else _FIXTURE_MAP
    pack = load_evidence_pack(args.pack) if args.pack else _illustrative_pack(map_path)
    verdict = evaluate_flood_source_qualification(
        pack=pack, map_path=map_path, as_of=date.today()
    )

    print("=" * 82)
    print("  Flood-source qualification gate — sealed evidence pack")
    print("-" * 82)
    print(f"  source_id : {verdict.source_id}")
    print(f"  map       : {map_path.name}")
    print(f"  pack_sha256: {verdict.pack_sha256[:32]}…")
    print("-" * 82)
    checks = [
        ("real source (not a synthetic fixture)", verdict.real_source_ok),
        ("evidence pack bound to map by SHA-256", verdict.artifact_bound_ok),
        ("licence on file + in effect", verdict.licence_ok),
        ("datum matches (NAP)", verdict.datum_ok),
        ("covers required points × return periods", verdict.coverage_ok),
        ("methodology cited", verdict.methodology_ok),
    ]
    for name, ok in checks:
        print(f"    {'✓' if ok else '✗'} {name}")
    print("-" * 82)
    print(f"  VERDICT: {'QUALIFIED' if verdict.qualified else 'NOT QUALIFIED'}")
    for r in verdict.reasons:
        print(f"    → {r}")
    if not verdict.qualified:
        print("-" * 82)
        print("  Honest offline state. Vendor a real map (scripts/vendor_flood_hazard_map.py)")
        print("  and seal a real pack (scripts/build_flood_evidence_pack.py) to reach QUALIFIED.")
        print("  Only then is a v0.4-default change eligible — in a separate PR, after review.")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
