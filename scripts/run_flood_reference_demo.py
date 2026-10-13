#!/usr/bin/env python3
"""Flood reference-level demo: per-asset return-period water levels → depth → JRC.

Two explicit, non-fungible modes — the ingestion *mechanics* are separated from a
real *qualification*, and the qualified mode NEVER falls back to synthetic:

    --mode fixture   (default)
        Labelled SYNTHETIC NAP elevation + labelled SYNTHETIC flood map. Exercises
        the elevation → depth → JRC wiring and the mandatory provenance record.
        Claim: INTEGRATION MECHANICS ONLY — this proves nothing about real risk.

    --mode qualified
        Requires a real, sealed flood-hazard map + evidence pack AND a real, sealed
        NAP elevation source (e.g. AHN). Runs the source-qualification gate
        (``flood_source_qualification``). If any real evidence is missing or the gate
        does not return QUALIFIED, the demo prints NOT_QUALIFIED and exits non-zero.
        There is NO synthetic fallback — absent real evidence is a fail-closed stop.

Closes STUBS #26 only in *shape* (the reference level is now per-asset, per-return-
period, from a provenanced map). STUBS #26 and the v0.4-default gate stay OPEN until
a real LIWO/AHN qualification completes.

Usage:
    PYTHONPATH=. python scripts/run_flood_reference_demo.py [--return-period 100]
    PYTHONPATH=. python scripts/run_flood_reference_demo.py --mode qualified \
        --flood-map real_map.json --evidence-pack pack.json --ahn-elevation ahn.json
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

from app.loss.depth_damage_curves import load_depth_damage_catalogue  # noqa: E402
from app.loss.flood_depth import (  # noqa: E402
    DEFAULT_REFERENCE_LEVEL_M,
    ElevationProfile,
    flood_damage_fraction,
    resolve_reference_level,
)
from app.loss.flood_hazard_map import load_flood_hazard_map  # noqa: E402
from app.loss.flood_source_qualification import (  # noqa: E402
    evaluate_flood_source_qualification,
    load_evidence_pack,
)
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402
from app.nl_pilot.real_five_layer import map_gebruiksdoel  # noqa: E402

_MAP_FIXTURE = "flood_hazard_map_fixture_v0.1.json"
_JRC_FIXTURE = "jrc_depth_damage_fixture_v0.1.json"

# Explicit label for the synthetic elevation. It is NOT AHN and must never be
# described as "representing AHN" — data that does not come from AHN is not AHN.
_SYNTHETIC_ELEVATION_LABEL = (
    "SYNTHETIC_NAP_ELEVATION — integration demonstration only; not AHN evidence"
)


def _synthetic_nap_profile() -> ElevationProfile:
    """A labelled synthetic ground-elevation profile in NAP (never real, never AHN)."""
    return ElevationProfile(
        vertical_datum="NAP", units="m", horizontal_crs="EPSG:4326",
        source="SYNTHETIC_NAP_ELEVATION", version="0.1",
        transformation="none_required", resolution="point", synthetic=True,
    )


def _synthetic_nap_elevation_m(lat: float, lon: float) -> float:
    """Labelled SYNTHETIC ground elevation in NAP. Not real; not AHN."""
    seed = f"synthetic-nap|{lat:.5f}|{lon:.5f}"
    unit = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)
    # Plausible Amsterdam NAP ground range [-2.0, +1.0] m — SYNTHETIC, deterministic.
    return round(-2.0 + unit * 3.0, 3)


def _run_fixture_mode(rp: int) -> int:
    assets = load_pilot_assets(_ROOT)
    fmap = load_flood_hazard_map(_MAP_FIXTURE)
    jrc = load_depth_damage_catalogue(_JRC_FIXTURE)
    profile = _synthetic_nap_profile()

    print("=" * 96)
    print(f"[--mode fixture] INTEGRATION MECHANICS ONLY — proves NO real flood risk (T={rp}yr)")
    print(f"  elevation: {_SYNTHETIC_ELEVATION_LABEL}")
    print(f"  flood-map: {fmap.map_id} ({'SYNTHETIC-FIXTURE' if fmap.synthetic else 'REAL'}, datum {fmap.datum})   "
          f"JRC: {jrc.catalogue_id} ({'SYNTHETIC-FIXTURE' if jrc.synthetic else 'REAL'})")
    print("-" * 96)
    print(f"{'asset_id':<17}{'elev_m':>8}{'ref_lvl_m':>11}{'depth_m':>9}{'damage':>9}   basis")

    last_versions: dict = {}
    for a in assets:
        lat, lon = float(a.coordinates_y), float(a.coordinates_x)
        elev = _synthetic_nap_elevation_m(lat, lon)  # NAP, differenceable with the NAP map
        btype, _ = map_gebruiksdoel(a.gebruiksdoel)
        level, basis = resolve_reference_level(
            latitude=lat, longitude=lon, return_period_years=rp, reference_map=fmap,
            elevation_profile=profile,
        )
        data_versions: dict = {}
        depth, ratio, _curve = flood_damage_fraction(
            ground_elevation_m=elev, building_type=btype, catalogue=jrc,
            reference_map=fmap, latitude=lat, longitude=lon, return_period_years=rp,
            elevation_profile=profile, data_versions=data_versions,
        )
        last_versions = data_versions
        print(f"{a.asset_id:<17}{elev:>8.2f}{level:>11.2f}{depth:>9.2f}{ratio:>9.3f}   {basis}")

    print("-" * 96)
    print("  Reference level is now PER-ASSET, per-return-period, from a provenanced map —")
    print(f"  replacing the single synthetic scalar ({DEFAULT_REFERENCE_LEVEL_M:.1f} m, STUBS #26).")
    print(f"  audited flood provenance stamped into data_versions: {last_versions}")
    print("  STUBS #26 and the v0.4-default gate remain OPEN — run --mode qualified with real,")
    print("  sealed LIWO/AHN evidence to qualify a source; synthetic can never qualify.")
    print("=" * 96)
    return 0


def _not_qualified(reasons: list[str]) -> int:
    print("=" * 96)
    print("[--mode qualified] NOT_QUALIFIED — fail-closed (no synthetic fallback)")
    for r in reasons:
        print(f"  - {r}")
    print("-" * 96)
    print("  A qualified flood run needs BOTH a real, sealed flood-hazard map (+ evidence")
    print("  pack) AND a real, sealed NAP elevation source (e.g. AHN) covering the pilot")
    print("  points. Until then STUBS #26 and the v0.4-default gate stay OPEN.")
    print("=" * 96)
    return 2


def _run_qualified_mode(args: argparse.Namespace, rp: int) -> int:
    reasons: list[str] = []
    if not args.flood_map:
        reasons.append("no real flood-hazard map supplied (--flood-map)")
    if not args.evidence_pack:
        reasons.append("no sealed evidence pack supplied (--evidence-pack)")
    if not args.ahn_elevation:
        reasons.append("no sealed NAP elevation source supplied (--ahn-elevation, e.g. AHN)")
    if reasons:
        return _not_qualified(reasons)

    # Real artifacts were named — verify them through the fail-closed gate.
    try:
        pack = load_evidence_pack(args.evidence_pack)
    except (ValueError, OSError) as exc:
        return _not_qualified([f"evidence pack could not be loaded: {exc}"])

    verdict = evaluate_flood_source_qualification(
        pack=pack, map_path=args.flood_map, as_of=date.today(),
    )
    if not verdict.qualified:
        return _not_qualified(
            ["flood-source qualification gate did NOT return QUALIFIED:"] + verdict.reasons
        )

    # The flood source qualified; the sealed NAP elevation must also verify before we
    # difference the two. (No real AHN loader ships yet — a real one plugs in here.)
    ahn_path = Path(args.ahn_elevation)
    if not ahn_path.exists() or not ahn_path.with_name(ahn_path.stem + ".provenance.json").exists():
        return _not_qualified(
            [f"NAP elevation artifact {ahn_path.name!r} is not present + provenance-sealed"]
        )

    print("=" * 96)
    print("[--mode qualified] flood source QUALIFIED and elevation sealed — proceed to depth.")
    print("  (Wire the sealed AHN-NAP elevation loader here to compute real per-asset depths.)")
    print("=" * 96)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("fixture", "qualified"), default="fixture")
    ap.add_argument("--return-period", type=int, default=100)
    ap.add_argument("--flood-map", help="Real sealed flood-hazard map JSON (qualified mode).")
    ap.add_argument("--evidence-pack", help="Sealed flood-source evidence pack JSON (qualified mode).")
    ap.add_argument("--ahn-elevation", help="Real sealed NAP elevation artifact (qualified mode).")
    args = ap.parse_args()

    if args.mode == "qualified":
        return _run_qualified_mode(args, args.return_period)
    return _run_fixture_mode(args.return_period)


if __name__ == "__main__":
    raise SystemExit(main())
