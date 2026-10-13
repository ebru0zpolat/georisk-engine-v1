#!/usr/bin/env python3
"""Run the Amsterdam real-hazard five-layer demo and print the evidence bundle.

Modes
-----
default    Load the SEALED REAL hazard snapshot and run real EAL. Fails closed
           with capture instructions if it has not been captured yet.
--fixture  Use a SYNTHETIC-LABELLED fixture snapshot so the full pipeline runs
           offline now (proves wiring + output shape; numbers are labelled
           synthetic, never presented as real).

Usage:
    PYTHONPATH=. python scripts/run_real_hazard_demo.py [--fixture] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.nl_pilot.hazard_fixture import synthetic_fixture_snapshot  # noqa: E402
from app.nl_pilot.hazard_snapshot import (  # noqa: E402
    HazardSnapshotMissing,
    SealedHazardSnapshot,
    load_sealed_hazard_snapshot,
)
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402
from app.nl_pilot.real_five_layer import run_real_five_layer  # noqa: E402
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402


def _print_human(bundle: dict) -> None:
    hl = bundle["honesty_labels"]
    tot = bundle["portfolio_totals"]
    print("=" * 78)
    print(f"GeoRisk Engine — real hazard → EAL five-layer  |  {bundle['portfolio_id']}")
    print(f"Valuation date: {bundle['valuation_date']}   Assets: {bundle['asset_count']}")
    print("-" * 78)
    print(f"  Hazard layer   : {hl['hazard_layer']}")
    print(f"  Exposure (where): {hl['exposure_location']}")
    print(f"  Snapshot kind  : {hl['snapshot_kind']}")
    print(f"  Asset value    : {hl['asset_value']}")
    print(f"  Damage curves  : {hl['damage_curves']}")
    print("-" * 78)
    header = (
        f"{'asset_id':<16}{'type':<11}{'elev_m':>7}{'p95°C':>7}"
        f"{'flood':>7}{'heat':>7}{'value_€':>13}{'EAL_€':>12}{'EAL%':>7}"
    )
    print(header)
    for r in bundle["assets"]:
        h = r["hazard"]
        print(
            f"{r['asset_id']:<16}{r['building_type']:<11}"
            f"{(h['elevation_m'] if h['elevation_m'] is not None else 0):>7.1f}"
            f"{(h['p95_tmax_c'] or 0):>7.1f}"
            f"{h['flood_intensity']:>7.2f}{h['extreme_heat_intensity']:>7.2f}"
            f"{r['asset_value_eur']:>13,.0f}{r['eal_absolute']:>12,.0f}"
            f"{r['eal_pct_of_value']:>7.2f}"
        )
    print("-" * 78)
    print(
        f"  Portfolio: value €{tot['total_indicative_value_eur']:,.0f}   "
        f"EAL €{tot['total_eal_absolute_eur']:,.0f}   "
        f"weighted {tot['weighted_eal_pct_of_value']:.2f}% of value"
    )
    prov = bundle["data_provenance"]["hazard_snapshot"]
    print(
        f"  Hazard snapshot: {prov['snapshot_id']}  "
        f"sha256={prov['artifact_sha256'][:16]}…  synthetic={prov['synthetic']}"
    )
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true", help="Use synthetic-labelled fixture.")
    parser.add_argument("--json", action="store_true", help="Emit the raw evidence bundle JSON.")
    args = parser.parse_args()

    assets = load_pilot_assets(_ROOT)

    if args.fixture:
        derived = synthetic_fixture_snapshot(assets)
        snapshot = SealedHazardSnapshot.from_derived_dict(derived, artifact_sha256="fixture")
    else:
        try:
            snapshot = load_sealed_hazard_snapshot(_ROOT)
        except HazardSnapshotMissing as exc:
            print(str(exc), file=sys.stderr)
            print(
                "\nTo see the pipeline run now with labelled synthetic data:\n"
                "  PYTHONPATH=. python scripts/run_real_hazard_demo.py --fixture",
                file=sys.stderr,
            )
            return 2

    bundle = run_real_five_layer(snapshot=snapshot, assets=assets, trail=AppendOnlyAuditTrail())
    if args.json:
        print(json.dumps(bundle, indent=2, ensure_ascii=False))
    else:
        _print_human(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
