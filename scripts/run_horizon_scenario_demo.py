#!/usr/bin/env python3
"""Forward-horizon EAL demo: current / 2030 / 2050 over the real Amsterdam assets.

Lights up the scenario_eal output (currently disabled without a scenario source,
STUBS #16b) by projecting current hazard intensities with a horizon-scenario
uplift catalogue. Everything non-real is labelled: hazard snapshot (fixture
unless captured), and the scenario factors (fixture unless vendored).

Usage:
    PYTHONPATH=. python scripts/run_horizon_scenario_demo.py [--scenario-catalogue F.json]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.expected_loss import (  # noqa: E402
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.loss.horizon_scenarios import (  # noqa: E402
    load_horizon_scenario_catalogue,
    load_horizon_scenario_from_path,
)
from app.hazards.extreme_heat import ExtremeHeatHazardModule  # noqa: E402
from app.hazards.flood import FloodHazardModule  # noqa: E402
from app.nl_pilot.hazard_fixture import synthetic_fixture_snapshot  # noqa: E402
from app.nl_pilot.hazard_snapshot import SealedHazardSnapshot  # noqa: E402
from app.nl_pilot.real_assets import load_pilot_assets  # noqa: E402
from app.nl_pilot.real_five_layer import real_asset_to_universal  # noqa: E402
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402
from app.services.five_layer_pipeline import _vulnerability_layer  # noqa: E402

_FIXTURE = "horizon_scenario_fixture_v0.1.json"
_VDATE = date(2025, 1, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario-catalogue", help="Vendored real catalogue JSON (else fixture).")
    args = ap.parse_args()

    assets = load_pilot_assets(_ROOT)
    snap = SealedHazardSnapshot.from_derived_dict(
        synthetic_fixture_snapshot(assets), artifact_sha256="fixture"
    )
    cat = (
        load_horizon_scenario_from_path(args.scenario_catalogue)
        if args.scenario_catalogue
        else load_horizon_scenario_catalogue(_FIXTURE)
    )
    trail = AppendOnlyAuditTrail()

    print("=" * 84)
    print("Forward-horizon EAL — current / 2030 / 2050 (real Amsterdam assets)")
    print(f"  hazard: {'SYNTHETIC FIXTURE' if snap.synthetic else 'sealed real'}   "
          f"scenario: {cat.scenario} ({'SYNTHETIC-FIXTURE' if cat.synthetic else 'REAL'})")
    print("-" * 84)
    print(f"{'asset_id':<16}{'EAL_now':>13}{'EAL_2030':>13}{'EAL_2050':>13}{'Δ2050 %':>10}")

    tot_now = tot_50 = 0.0
    for a in assets:
        u, prov = real_asset_to_universal(a)
        lat, lon = round(u.latitude, 5), round(u.longitude, 5)
        flood = FloodHazardModule(raster=snap).evaluate(latitude=lat, longitude=lon, valuation_date=_VDATE)
        heat = ExtremeHeatHazardModule(raster=snap).evaluate(latitude=lat, longitude=lon, valuation_date=_VDATE)
        current = {"flood": flood.intensity, "extreme_heat": heat.intensity}
        h30, h50 = cat.build_horizon_maps(current)
        vuln = _vulnerability_layer(u)
        res = compute_expected_loss(
            asset=ExpectedLossAssetInput(
                asset_id=u.asset_id, asset_value=u.asset_value, building_type=u.building_type,
                use_class=u.use_class, fragility_factor=vuln.fragility_factor,
                adaptation_capacity_factor=vuln.adaptation_capacity_factor),
            hazards=HazardScenarioIntensities(
                current=current, horizon_2030=h30, horizon_2050=h50,
                # Stamp lineage so the audit record identifies which scenario
                # catalogue + hazard snapshot produced the horizon maps.
                data_versions={
                    "horizon_scenario": cat.methodology_artifact_id,
                    "horizon_scenario_name": cat.scenario,
                    "hazard_snapshot": snap.snapshot_id,
                    "hazard_snapshot_sha256": snap.artifact_sha256,
                },
            ),
            valuation_date=_VDATE, trail=trail,
        )
        now, e30, e50 = res.eal_absolute, res.scenario_eal["2030"], res.scenario_eal["2050"]
        delta = ((e50 - now) / now * 100.0) if now else 0.0
        tot_now += now
        tot_50 += e50
        print(f"{a.asset_id:<16}{now:>13,.0f}{e30:>13,.0f}{e50:>13,.0f}{delta:>9.1f}%")

    print("-" * 84)
    g = ((tot_50 - tot_now) / tot_now * 100.0) if tot_now else 0.0
    print(f"  Portfolio EAL: now €{tot_now:,.0f} → 2050 €{tot_50:,.0f}  (+{g:.1f}%)")
    print("  Horizon deltas come from versioned scenario uplift factors — labelled")
    print("  synthetic here; vendor CMIP6/CORDEX/KNMI'23 factors for real projections.")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
