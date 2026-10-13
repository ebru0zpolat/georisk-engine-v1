#!/usr/bin/env python3
"""Run pipeline EAL vs independent verifier; write verification_report.md.

Used by CI job ``verify-eal`` and ``make verify ASSET=<id>``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO = ROOT / "data/portfolios/verification/assets_v1.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from verification.independent_eal import eal_from_trail  # noqa: E402

# Pipeline import — harness only; independent_eal must never use these.
from app.loss.damage_curves import load_catalogue_from_path  # noqa: E402
from app.loss.expected_loss import (  # noqa: E402
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402


def _git_sha() -> str:
    env = os.environ.get("GITHUB_SHA") or os.environ.get("VERIFY_SEED_SHA")
    if env:
        return env.strip()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "local-dev"


def _seed_from_sha(sha: str) -> int:
    return int(hashlib.sha256(sha.encode("utf-8")).hexdigest()[:16], 16)


def load_portfolio(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_pipeline(
    asset_row: dict,
    valuation_date: date,
    trail: AppendOnlyAuditTrail,
    *,
    catalogue,
):
    asset = ExpectedLossAssetInput(
        asset_id=asset_row["asset_id"],
        asset_value=float(asset_row["asset_value"]),
        building_type=asset_row["building_type"],
        use_class=asset_row["use_class"],
        fragility_factor=float(asset_row.get("fragility_factor", 1.0)),
        adaptation_capacity_factor=float(asset_row.get("adaptation_capacity_factor", 0.0)),
        insurance_coverage=asset_row.get("insurance_coverage"),
    )
    hz = asset_row["hazards"]
    hazards = HazardScenarioIntensities(
        current=hz["current"],
        horizon_2030=hz["horizon_2030"],
        horizon_2050=hz["horizon_2050"],
        data_versions=dict(hz.get("data_versions") or {}),
        as_of=date.fromisoformat(hz["as_of"]) if hz.get("as_of") else None,
    )
    result = compute_expected_loss(
        asset=asset,
        hazards=hazards,
        valuation_date=valuation_date,
        trail=trail,
        timestamp=datetime(2024, 12, 31, 12, 0, tzinfo=timezone.utc),
        catalogue=catalogue,
    )
    record = trail.get(result.audit_record_id)
    assert record is not None
    return result, record


def _side_by_side(pipeline_out: dict, independent: dict) -> str:
    lines = [
        "| Field | Pipeline | Independent |",
        "|---|---:|---:|",
        f"| EAL absolute | {pipeline_out.get('eal_absolute')} | {independent.get('eal_absolute')} |",
        f"| EAL % value | {pipeline_out.get('eal_pct_of_value')} | {independent.get('eal_pct_of_value')} |",
        f"| EAL 2030 | {(pipeline_out.get('scenario_eal') or {}).get('2030')} | {independent.get('eal_2030')} |",
        f"| EAL 2050 | {(pipeline_out.get('scenario_eal') or {}).get('2050')} | {independent.get('eal_2050')} |",
    ]
    return "\n".join(lines)


def render_asset_page(
    *,
    asset_row: dict,
    catalogue_path: str,
    catalogue_meta: dict,
    result,
    record,
    independent: dict,
    agree: bool,
) -> str:
    pages: list[str] = []
    pages.append(f"# Asset `{result.asset_id}`")
    pages.append("")
    pages.append(f"- **Valuation date:** {result.valuation_date.isoformat()}")
    pages.append(f"- **Asset value:** {asset_row['asset_value']:,.2f}")
    pages.append(f"- **Building / use:** {asset_row['building_type']} / {asset_row['use_class']}")
    pages.append(
        f"- **Curve catalogue (pipeline = verifier):** `{catalogue_meta.get('catalogue_id')}` "
        f"v{catalogue_meta.get('version')} ({catalogue_meta.get('source')})"
    )
    pages.append(
        f"- **Record catalogue params:** "
        f"`{record.parameters.get('catalogue_id')}` v{record.parameters.get('catalogue_version')}"
    )
    pages.append(f"- **Catalogue path:** `{catalogue_path}`")
    pages.append(f"- **Trail record id:** `{record.record_id}`")
    pages.append(f"- **Trail record hash:** `{record.record_hash}`")
    pages.append(f"- **Agreement:** {'PASS' if agree else 'FAIL'}")
    pages.append("")
    pages.append("## Vulnerability")
    pages.append("")
    pages.append(
        f"`vuln = max(0.05, {asset_row.get('fragility_factor', 1.0)} × "
        f"(1 − {asset_row.get('adaptation_capacity_factor', 0.0)})) "
        f"= {independent['vulnerability']}`"
    )
    pages.append("")
    pages.append("## Current-climate hazard steps")
    pages.append("")
    pages.append(f"- **Combined MDR:** {independent.get('combined_mdr')}")
    pages.append("")
    pages.append(
        "| Hazard | Intensity | Curve id | Exponent | Scale | MDR | "
        "Attribution share (info) | Notional loss |"
    )
    pages.append("|---|---:|---|---:|---:|---:|---:|---:|")
    for step in independent["steps"]:
        share = step.get("attribution_share", step.get("weight"))
        pages.append(
            f"| {step['hazard_id']} | {step['intensity']} | `{step['curve_id']}` | "
            f"{step['exponent']} | {step['scale']} | {step['mdr']} | {share} | "
            f"{step['loss']:,.2f} |"
        )
    pages.append("")
    pages.append("### Per-hazard formulas")
    pages.append("")
    for step in independent["steps"]:
        pages.append(
            f"- **{step['hazard_id']}:** `{step['formula']}` → loss **{step['loss']:,.2f}** "
            f"(curve `{step['curve_id']}`, catalogue v{catalogue_meta.get('version')})"
        )
    pages.append("")
    pages.append("## Results")
    pages.append("")
    pages.append(_side_by_side(record.outputs, independent))
    pages.append("")
    pages.append(
        f"**Independent EAL:** {independent['eal_absolute']:,.2f} "
        f"({independent['eal_pct_of_value']}% of value)"
    )
    pages.append(
        f"**Pipeline EAL:** {result.eal_absolute:,.2f} "
        f"({result.eal_pct_of_value}% of value)"
    )
    pages.append("")
    pages.append("---")
    pages.append("")
    return "\n".join(pages)


def verify_assets(
    *,
    portfolio: dict,
    selected: list[dict],
    report_path: Path,
    trail_path: Path,
) -> int:
    catalogue_path = str(ROOT / portfolio["curve_catalogue_path"])
    catalogue_meta = json.loads(Path(catalogue_path).read_text(encoding="utf-8"))
    catalogue = load_catalogue_from_path(catalogue_path)
    if (
        catalogue.catalogue_id != catalogue_meta.get("catalogue_id")
        or catalogue.version != catalogue_meta.get("version")
    ):
        raise RuntimeError("catalogue path meta mismatch after load")
    valuation_date = date.fromisoformat(portfolio["valuation_date"])
    trail = AppendOnlyAuditTrail(path=trail_path)
    sha = _git_sha()

    header = [
        "# EAL independent verification report",
        "",
        f"- **Generated (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"- **Commit / seed SHA:** `{sha}`",
        f"- **Portfolio:** `{portfolio['portfolio_id']}`",
        f"- **Assets verified:** {len(selected)}",
        f"- **Shared catalogue:** `{catalogue.catalogue_id}` v{catalogue.version}",
        f"- **Methodology:** `tests/verification/METHODOLOGY.md` (v0.3)",
        "",
        "Each page below recomputes Expected Annual Loss from trail inputs and the "
        "curve catalogue using the code-isolated verifier (no shared code with the pipeline). "
        "PASS = reproducibility within cents rounding — not observational validation.",
        "",
        "---",
        "",
    ]
    body: list[str] = []
    failures: list[str] = []

    for row in selected:
        result, record = run_pipeline(row, valuation_date, trail, catalogue=catalogue)
        # Pipeline and verifier must share the same explicit catalogue artefact.
        assert record.parameters.get("catalogue_id") == catalogue.catalogue_id
        assert record.parameters.get("catalogue_version") == catalogue.version
        record_dict = json.loads(record.model_dump_json())
        independent = eal_from_trail(record_dict, catalogue_path)
        assert independent["catalogue_id"] == catalogue.catalogue_id
        assert independent["catalogue_version"] == catalogue.version
        pipe = record.outputs
        agree = (
            independent["eal_absolute"] == pipe["eal_absolute"]
            and independent["eal_pct_of_value"] == pipe["eal_pct_of_value"]
            and independent["eal_2030"] == pipe["scenario_eal"]["2030"]
            and independent["eal_2050"] == pipe["scenario_eal"]["2050"]
        )
        body.append(
            render_asset_page(
                asset_row=row,
                catalogue_path=catalogue_path,
                catalogue_meta=catalogue_meta,
                result=result,
                record=record,
                independent=independent,
                agree=agree,
            )
        )
        if not agree:
            failures.append(
                f"DIVERGENCE asset={row['asset_id']}\n{_side_by_side(pipe, independent)}"
            )

    report_path.write_text("\n".join(header + body), encoding="utf-8")
    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        print(f"Wrote FAIL report to {report_path}", file=sys.stderr)
        return 1
    print(f"OK — {len(selected)} asset(s) verified; report → {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO)
    parser.add_argument("--report", type=Path, default=Path("verification_report.md"))
    parser.add_argument("--trail", type=Path, default=Path("data/audit_trail/verify_eal.jsonl"))
    parser.add_argument("--asset", type=str, default=None, help="Verify a single asset id")
    parser.add_argument("--sample", type=int, default=5, help="Random sample size (CI)")
    parser.add_argument(
        "--seed-from-git",
        action="store_true",
        help="Seed RNG from GITHUB_SHA / git HEAD",
    )
    args = parser.parse_args(argv)

    portfolio = load_portfolio(args.portfolio)
    assets = list(portfolio["assets"])
    by_id = {a["asset_id"]: a for a in assets}

    if args.asset:
        if args.asset not in by_id:
            print(f"Unknown ASSET={args.asset!r}; known: {sorted(by_id)}", file=sys.stderr)
            return 2
        selected = [by_id[args.asset]]
    else:
        n = min(args.sample, len(assets))
        if args.seed_from_git:
            seed = _seed_from_sha(_git_sha())
            rng = random.Random(seed)
            selected = rng.sample(assets, n)
            print(f"seed={seed} sha={_git_sha()} sample={[a['asset_id'] for a in selected]}")
        else:
            selected = assets[:n]

    args.trail.parent.mkdir(parents=True, exist_ok=True)
    if args.trail.exists():
        args.trail.unlink()
    return verify_assets(
        portfolio=portfolio,
        selected=selected,
        report_path=args.report,
        trail_path=args.trail,
    )


if __name__ == "__main__":
    raise SystemExit(main())
