#!/usr/bin/env python3
"""Rehearse the free 20–50 asset analysis pack on the Antalya golden portfolio.

Send gate for the TSKB / Anadolu Sigorta first calls
(``docs/05-commercial/TSKB_ANADOLU_SIGORTA_OUTREACH_PACKET.md`` §0): no outreach unless a
rehearsal record exists in which every analysed demo asset was independently recomputed
from its own audit-trail record and agreed to the cent.

Fail-closed rules:

* the audit trail path is mandatory and must resolve **outside** the repository checkout
  (``--trail`` or ``GEORISK_AUDIT_TRAIL_PATH``); an in-repo path is refused;
* ``--max-assets`` is bounded to the offer band 20–50;
* any asset whose independent recomputation disagrees with the pipeline fails the run;
* the release manifest must say ``decision=demo_only`` and ``production_eligible=false``.

Only the synthetic golden portfolio is ever loaded here — never a customer list.

Usage:
    PYTHONPATH=. python scripts/rehearse_free_analysis_pack.py \\
        --trail /path/outside/repo/audit_trail.jsonl \\
        --record docs/05-commercial/evidence/free_analysis_rehearsal.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_RECORD = ROOT / "docs" / "05-commercial" / "evidence" / "free_analysis_rehearsal.json"
CURVES_PATH = ROOT / "app" / "loss" / "curves" / "stub_global_mdr_v0.2.json"
OFFER_MIN_ASSETS = 20
OFFER_MAX_ASSETS = 50


class RehearsalError(RuntimeError):
    """Raised when a fail-closed rule is violated."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def resolve_trail_path(raw: str | None, *, root: Path = ROOT) -> Path:
    """Return the trail path, refusing an unset value or one inside ``root``."""
    if not raw or not raw.strip():
        raise RehearsalError(
            "audit trail path is required (--trail or GEORISK_AUDIT_TRAIL_PATH) and must be "
            "outside the repository"
        )
    path = Path(raw).expanduser().resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return path
    raise RehearsalError(f"audit trail path {path} resolves inside the repository {root}")


def rehearse(*, trail_path: Path, max_assets: int, root: Path = ROOT) -> dict[str, Any]:
    """Run the demo, recompute every asset independently, and return the record."""
    if not OFFER_MIN_ASSETS <= max_assets <= OFFER_MAX_ASSETS:
        raise RehearsalError(
            f"max_assets={max_assets} outside the offer band {OFFER_MIN_ASSETS}–{OFFER_MAX_ASSETS}"
        )
    trail_path = resolve_trail_path(str(trail_path), root=root)
    trail_path.parent.mkdir(parents=True, exist_ok=True)

    from verification.independent_eal import eal_from_trail

    from app.core.config import settings
    from app.services.audit_trail import reset_audit_trail_for_tests
    from app.services.portfolio_demo import run_golden_antalya_demo
    from app.services.release_manifest import build_release_manifest

    # Bind the process-default trail to the out-of-repo path before any record is written.
    trail = reset_audit_trail_for_tests(trail_path)
    narrative = run_golden_antalya_demo(max_assets=max_assets)
    pack = narrative.model_dump(mode="json")

    verified: list[dict[str, Any]] = []
    failures = 0
    for row in pack["assets"]:
        record = trail.get(row["eal_audit_record_id"])
        if record is None:
            raise RehearsalError(f"missing trail record for {row['asset_id']}")
        payload = record.model_dump(mode="json")
        independent = eal_from_trail(payload, CURVES_PATH)
        agree = round(float(independent["eal_absolute"]), 2) == round(float(row["eal_absolute"]), 2)
        failures += 0 if agree else 1
        verified.append(
            {
                "asset_id": row["asset_id"],
                "eal_absolute": row["eal_absolute"],
                "trail_record_id": payload["record_id"],
                "trail_record_hash": payload["record_hash"],
                "agreement": "PASS" if agree else "FAIL",
            }
        )

    manifest = build_release_manifest(settings)
    manifest_ok = manifest.decision == "demo_only" and manifest.production_eligible is False

    out_dir = trail_path.parent
    pack_path = out_dir / "pack.json"
    pack_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    manifest_path = out_dir / "release_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    analyzed = int(pack["coverage"]["analyzed_count"])
    send_gate = failures == 0 and analyzed >= OFFER_MIN_ASSETS and manifest_ok
    featured = pack.get("verification") or {}

    return {
        "schema_version": "1.0",
        "purpose": "send gate — TSKB / Anadolu Sigorta first-call packet §0",
        "rehearsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_sha": _git_sha(root),
        "portfolio_id": pack["portfolio_id"],
        "portfolio_source": pack["source"],
        "valuation_date": pack["valuation_date"],
        "max_assets": max_assets,
        "coverage": {
            "submitted_count": pack["coverage"]["submitted_count"],
            "analyzed_count": analyzed,
            "excluded_count": pack["coverage"]["excluded_count"],
            "message": pack["coverage"]["message"],
        },
        "methodology": pack["methodology"],
        "calibration_badge": pack["calibration_badge"],
        "independent_verification": {
            "verifier": "tests/verification/independent_eal.py::eal_from_trail",
            "curves": str(CURVES_PATH.relative_to(root)),
            "assets_verified": len(verified),
            "failures": failures,
            "assets": verified,
        },
        "featured_verification": {
            "asset_id": featured.get("asset_id"),
            "agreement": featured.get("agreement"),
            "trail_record_hash": featured.get("trail_record_hash"),
        },
        "release_manifest": {
            "release_version": manifest.release_version,
            "decision": manifest.decision,
            "production_eligible": manifest.production_eligible,
        },
        "artefacts_outside_repo": {
            "trail_path": str(trail_path),
            "trail_sha256": _sha256_file(trail_path),
            "pack_path": str(pack_path),
            "pack_sha256": _sha256_file(pack_path),
            "release_manifest_path": str(manifest_path),
        },
        "trail_outside_repo": True,
        "send_gate_satisfied": send_gate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trail", default=os.environ.get("GEORISK_AUDIT_TRAIL_PATH"))
    parser.add_argument("--max-assets", type=int, default=OFFER_MAX_ASSETS)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args(argv)

    try:
        record = rehearse(trail_path=Path(args.trail) if args.trail else Path(""),
                          max_assets=args.max_assets)
    except RehearsalError as exc:
        print(f"REHEARSAL REFUSED: {exc}", file=sys.stderr)
        return 2

    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    iv = record["independent_verification"]
    print(f"{record['coverage']['message']}  ·  {record['methodology']['document']}  ·  "
          f"{record['calibration_badge']}")
    print(f"independent verification: {iv['assets_verified']} assets, {iv['failures']} failures")
    print(f"release manifest: {record['release_manifest']['decision']}, "
          f"production_eligible={record['release_manifest']['production_eligible']}")
    print(f"trail (outside repo): {record['artefacts_outside_repo']['trail_path']}")
    print(f"record: {args.record}")
    print("SEND GATE:", "SATISFIED" if record["send_gate_satisfied"] else "NOT SATISFIED")
    return 0 if record["send_gate_satisfied"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
