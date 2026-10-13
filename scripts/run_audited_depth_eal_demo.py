#!/usr/bin/env python3
"""Audited depth-EAL demo: real assets → depth → v0.4 EAL → independent verify.

Runs the five real Amsterdam BAG assets through the **audited** expected-loss
engine on methodology `expected-loss-v0.4` (flood priced from a JRC depth curve),
writing a hash-chained trail record per asset, then recomputes each record with
the code-isolated independent verifier and reports agreement.

This is the full loop: real elevation → inundation depth → JRC damage → audited
EAL (trail) → independent recompute. Labels: elevation/JRC are synthetic
fixtures unless real snapshots/catalogues are supplied; reference level is the
labelled synthetic term (STUBS #26).

Usage:
    PYTHONPATH=. python scripts/run_audited_depth_eal_demo.py [--reference-level 1.5]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (str(_ROOT), str(_ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.hazards.extreme_heat import ExtremeHeatHazardModule  # noqa: E402
from app.hazards.flood import FloodHazardModule  # noqa: E402
from app.loss.depth_damage_curves import load_depth_damage_catalogue  # noqa: E402
from app.loss.expected_loss import (  # noqa: E402
    EXPECTED_LOSS_METHODOLOGY_V0_4,
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.loss.flood_depth import REFERENCE_LEVEL_BASIS, inundation_depth_m  # noqa: E402
from app.nl_pilot.hazard_fixture import synthetic_fixture_snapshot  # noqa: E402
from app.nl_pilot.hazard_snapshot import SealedHazardSnapshot  # noqa: E402
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402
from app.nl_pilot.real_five_layer import real_asset_to_universal  # noqa: E402
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402
from app.services.five_layer_pipeline import _vulnerability_layer  # noqa: E402

_POWER = str(_ROOT / "app/loss/curves/stub_global_mdr_v0.2.json")
_DEPTH_FILE = str(_ROOT / "app/loss/curves/jrc_depth_damage_fixture_v0.1.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference-level", type=float, default=1.5)
    args = ap.parse_args()

    from verification.independent_eal import eal_from_trail

    assets = load_pilot_assets(_ROOT)
    snapshot = SealedHazardSnapshot.from_derived_dict(
        synthetic_fixture_snapshot(assets), artifact_sha256="fixture"
    )
    depth_cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    trail = AppendOnlyAuditTrail()
    vdate = date(2025, 1, 1)

    print("=" * 88)
    print("Audited depth-EAL — expected-loss-v0.4 (flood via JRC depth curve) + independent verify")
    print(f"  elevation: SYNTHETIC FIXTURE   reference level: SYNTHETIC ({REFERENCE_LEVEL_BASIS}) "
          f"= {args.reference_level:.2f} m   JRC: SYNTHETIC-FIXTURE")
    print("-" * 88)
    print(f"{'asset_id':<16}{'depth_m':>8}{'flood_mdr':>10}{'heat_mdr':>9}"
          f"{'EAL_€':>13}  {'audit_record':<14}{'verify':>8}")

    total_eal = 0.0
    all_pass = True
    for asset in assets:
        universal, prov = real_asset_to_universal(asset)
        lat, lon = round(universal.latitude, 5), round(universal.longitude, 5)
        elev = snapshot.elevation_at(lat, lon).value
        depth = inundation_depth_m(elev, args.reference_level)
        flood = FloodHazardModule(raster=snapshot).evaluate(
            latitude=lat, longitude=lon, valuation_date=vdate)
        heat = ExtremeHeatHazardModule(raster=snapshot).evaluate(
            latitude=lat, longitude=lon, valuation_date=vdate)
        vuln = _vulnerability_layer(universal)
        asset_in = ExpectedLossAssetInput(
            asset_id=universal.asset_id, asset_value=universal.asset_value,
            building_type=universal.building_type, use_class=universal.use_class,
            fragility_factor=vuln.fragility_factor,
            adaptation_capacity_factor=vuln.adaptation_capacity_factor,
        )
        hazards = HazardScenarioIntensities(
            current={"flood": flood.intensity, "extreme_heat": heat.intensity})
        res = compute_expected_loss(
            asset=asset_in, hazards=hazards, valuation_date=vdate, trail=trail,
            methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4,
            depths={"flood": depth}, depth_catalogue=depth_cat)
        rec = trail.get(res.audit_record_id).model_dump(mode="json")
        indep = eal_from_trail(rec, _POWER, _DEPTH_FILE)
        ok = round(indep["eal_absolute"], 2) == round(res.eal_absolute, 2)
        all_pass = all_pass and ok
        total_eal += res.eal_absolute
        print(f"{asset.asset_id:<16}{depth:>8.2f}{res.mdr_by_hazard['flood']:>10.3f}"
              f"{res.mdr_by_hazard['extreme_heat']:>9.3f}{res.eal_absolute:>13,.0f}  "
              f"{res.audit_record_id[:12]:<14}{'PASS' if ok else 'FAIL':>8}")

    print("-" * 88)
    print(f"  Portfolio audited EAL: €{total_eal:,.0f}   independent verification: "
          f"{'ALL PASS' if all_pass else 'FAILURES'}   trail records: {len(trail)}")
    print("=" * 88)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
