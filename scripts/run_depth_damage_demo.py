#!/usr/bin/env python3
"""Depth-damage flood demo: real elevation → depth → JRC curve → damage.

Composes the P0 elevation snapshot with the P1 JRC depth-damage engine over the
real Amsterdam BAG assets. Every non-real term is labelled:

  * elevation  — REAL when sourced from a sealed AHN/DEM snapshot (or the
    SYNTHETIC fixture with --fixture)
  * reference flood level — SYNTHETIC placeholder (real: return-period maps)
  * JRC curve — REAL when vendored (--jrc), else SYNTHETIC-FIXTURE
  * asset value — SYNTHETIC-INDICATIVE (floor area × €/m²)

Usage:
    PYTHONPATH=. python scripts/run_depth_damage_demo.py --fixture
    PYTHONPATH=. python scripts/run_depth_damage_demo.py \
        --ahn data/nl_pilot/snapshots/hazard/ahn-elevation-amsterdam-v1.json \
        --jrc app/loss/curves/jrc_global_depth_damage_v1.0.json \
        --reference-level 1.5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.depth_damage_curves import (  # noqa: E402
    load_depth_damage_catalogue,
    load_depth_damage_from_path,
)
from app.loss.flood_depth import (  # noqa: E402
    DEFAULT_REFERENCE_LEVEL_M,
    REFERENCE_LEVEL_BASIS,
    flood_damage_fraction,
)
from app.nl_pilot.hazard_fixture import synthetic_fixture_snapshot  # noqa: E402
from app.nl_pilot.hazard_snapshot import (  # noqa: E402
    HazardSnapshotMissing,
    SealedHazardSnapshot,
    load_sealed_hazard_snapshot,
)
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402
from app.nl_pilot.real_five_layer import real_asset_to_universal  # noqa: E402

_FIXTURE_CURVES = "jrc_depth_damage_fixture_v0.1.json"


def _ahn_lookup(path: Path, precision: int = 5) -> dict[tuple[float, float], float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[float, float], float] = {}
    for p in data.get("points", []):
        out[(round(float(p["latitude"]), precision), round(float(p["longitude"]), precision))] = float(
            p["elevation_m"]
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", action="store_true", help="Use synthetic-labelled elevation fixture.")
    ap.add_argument("--ahn", help="Sealed AHN elevation snapshot JSON (real elevation source).")
    ap.add_argument("--jrc", help="Vendored real JRC catalogue JSON (else synthetic fixture).")
    ap.add_argument("--reference-level", type=float, default=DEFAULT_REFERENCE_LEVEL_M)
    args = ap.parse_args()

    assets = load_pilot_assets(_ROOT)

    # Elevation source.
    ahn = _ahn_lookup(Path(args.ahn)) if args.ahn else None
    elev_label = "REAL — AHN (PDOK, NAP)" if ahn else None
    snapshot = None
    if ahn is None:
        if args.fixture:
            snapshot = SealedHazardSnapshot.from_derived_dict(
                synthetic_fixture_snapshot(assets), artifact_sha256="fixture"
            )
            elev_label = "SYNTHETIC FIXTURE — not real"
        else:
            try:
                snapshot = load_sealed_hazard_snapshot(_ROOT)
                elev_label = "REAL — sealed Copernicus DEM / ERA5 snapshot"
            except HazardSnapshotMissing as exc:
                print(str(exc), file=sys.stderr)
                print("\nOr: --fixture (synthetic), or --ahn <sealed AHN file>.", file=sys.stderr)
                return 2

    # JRC curves.
    catalogue = load_depth_damage_from_path(args.jrc) if args.jrc else load_depth_damage_catalogue(_FIXTURE_CURVES)
    jrc_label = (
        f"REAL — {catalogue.methodology_artifact_id}" if not catalogue.synthetic
        else "SYNTHETIC-FIXTURE — JRC-shaped, not JRC values"
    )

    print("=" * 82)
    print("Depth-damage flood demo — real elevation → depth → JRC curve → damage")
    print("-" * 82)
    print(f"  elevation      : {elev_label}")
    print(f"  reference level: SYNTHETIC ({REFERENCE_LEVEL_BASIS}) = {args.reference_level:.2f} m NAP")
    print(f"  JRC curves     : {jrc_label}")
    print("-" * 82)
    print(f"{'asset_id':<16}{'occ':<12}{'elev_m':>8}{'depth_m':>9}{'damage%':>9}{'value_€':>13}{'loss_€':>13}")

    total_val = total_loss = 0.0
    for asset in assets:
        universal, prov = real_asset_to_universal(asset)
        lat, lon = round(universal.latitude, 5), round(universal.longitude, 5)
        if ahn is not None:
            if (lat, lon) not in ahn:
                print(f"{asset.asset_id:<16}  (no AHN elevation for point — excluded)")
                continue
            elev = ahn[(lat, lon)]
        else:
            elev = snapshot.elevation_at(lat, lon).value
        depth, ratio, curve = flood_damage_fraction(
            ground_elevation_m=elev,
            building_type=prov["building_type"],
            catalogue=catalogue,
            reference_level_m=args.reference_level,
            continent="europe",
        )
        value = prov["asset_value_eur"]
        loss = round(value * ratio, 2)
        total_val += value
        total_loss += loss
        print(
            f"{asset.asset_id:<16}{curve.occupancy:<12}{elev:>8.2f}{depth:>9.2f}"
            f"{ratio * 100:>8.1f}%{value:>13,.0f}{loss:>13,.0f}"
        )

    print("-" * 82)
    pct = (total_loss / total_val * 100) if total_val else 0.0
    print(f"  Portfolio: value €{total_val:,.0f}   modelled flood loss €{total_loss:,.0f}   ({pct:.1f}% of value)")
    print("  NOTE: single-scenario damage at one reference level — NOT an annualised EAL.")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
