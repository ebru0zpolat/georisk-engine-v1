#!/usr/bin/env python3
"""Vendor authentic forward-horizon scenario uplift factors into a catalogue.

Per-hazard 2030/2050 uplift factors for a named climate scenario, from a real
published source (CMIP6/CORDEX-derived SSP pathway, or KNMI'23). Hand them here
as a normalized CSV and they are sealed with provenance. No value is invented;
the CSV must come from the cited source.

Normalized CSV schema (header required):
    hazard_id,horizon,factor
    flood,2030,1.08
    flood,2050,1.20
    extreme_heat,2030,1.15
    extreme_heat,2050,1.35

Usage:
    PYTHONPATH=. python scripts/vendor_horizon_scenarios.py --from-csv f.csv \
        --scenario "SSP2-4.5" --source "CMIP6 multi-model median (...)" \
        [--version 1.0]
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

from app.loss.horizon_scenarios import HORIZONS, HorizonUplift  # noqa: E402

_CURVES_DIR = _ROOT / "app" / "loss" / "curves"
CATALOGUE_ID = "horizon_scenario"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"hazard_id", "horizon", "factor"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")
        rows: list[dict] = []
        for i, row in enumerate(reader, start=2):
            if row["horizon"].strip() not in HORIZONS:
                raise SystemExit(f"CSV row {i}: horizon must be one of {HORIZONS}")
            try:
                # Validate shape via the model.
                u = HorizonUplift(
                    hazard_id=row["hazard_id"].strip().lower(),
                    horizon=row["horizon"].strip(),
                    factor=float(row["factor"]),
                )
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"CSV row {i} invalid: {exc}") from exc
            rows.append({"hazard_id": u.hazard_id, "horizon": u.horizon, "factor": u.factor})
    if not rows:
        raise SystemExit("CSV had no data rows")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-csv", required=True)
    parser.add_argument("--scenario", required=True, help='e.g. "SSP2-4.5" or "KNMI23-Md".')
    parser.add_argument("--source", required=True, help="Full citation of the scenario source.")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()

    uplifts = _read_csv(Path(args.from_csv))
    # Completeness (fail-closed vendoring): every hazard must carry exactly one
    # factor for EACH horizon — otherwise populated=true would lie and only fail
    # later at build_horizon_maps().
    hazards = {u["hazard_id"] for u in uplifts}
    for h in sorted(hazards):
        for horizon in HORIZONS:
            n = sum(1 for u in uplifts if u["hazard_id"] == h and u["horizon"] == horizon)
            if n != 1:
                raise SystemExit(
                    f"hazard {h!r} must have exactly one factor for horizon {horizon}; got {n}"
                )
    catalogue = {
        "catalogue_id": CATALOGUE_ID,
        "version": args.version,
        "scenario": args.scenario,
        "source": args.source,
        "synthetic": False,
        "populated": True,
        "methodology_note": (
            "Authentic per-hazard scenario uplift factors vendored from the cited "
            "source. horizon intensity = clamp(current x factor, 0, 1)."
        ),
        "uplifts": uplifts,
    }
    out_path = _CURVES_DIR / f"{CATALOGUE_ID}_v{args.version}.json"
    raw = json.dumps(catalogue, indent=2, ensure_ascii=True).encode("utf-8")
    out_path.write_bytes(raw)
    (_CURVES_DIR / f"{CATALOGUE_ID}_v{args.version}.provenance.json").write_text(
        json.dumps(
            {
                "catalogue_id": CATALOGUE_ID,
                "version": args.version,
                "scenario": args.scenario,
                "source": args.source,
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "uplift_count": len(uplifts),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    print(f"Sealed horizon scenario catalogue → {out_path.relative_to(_ROOT)}")
    print(f"  scenario: {args.scenario}   uplifts: {len(uplifts)}")
    print(f"  artifact_sha256: {hashlib.sha256(raw).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
