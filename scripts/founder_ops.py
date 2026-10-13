#!/usr/bin/env python3
"""Local read-only CLI for Founder-Autonomous Operations Phase 1."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from app.automation.digest import generate_digest
from app.automation.models import DigestInput, EvidenceRecord, ReadinessSnapshot
from app.automation.policy import load_policy
from app.automation.reconciliation import reconcile

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-policy")
    validate.add_argument("--policy", default="config/automation-policy.yml")
    recon = sub.add_parser("reconcile")
    recon.add_argument("--policy", default="config/automation-policy.yml")
    recon.add_argument("--roadmap", default="docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md")
    recon.add_argument("--evidence", action="append", default=[])
    recon.add_argument("--readiness", help="read-only readiness snapshot JSON")
    recon.add_argument("--output")
    digest = sub.add_parser("digest")
    digest.add_argument("input")
    digest.add_argument("--policy", default="config/automation-policy.yml")
    digest.add_argument("--output")
    args = parser.parse_args()
    policy = load_policy(ROOT / args.policy)
    if args.command == "validate-policy":
        print(f"valid policy: {len(policy['workflows'])} workflows")
        return 0
    if args.command == "reconcile":
        evidence = [(item, EvidenceRecord.model_validate_json((ROOT / item).read_text())) for item in args.evidence]
        readiness = (
            ReadinessSnapshot.model_validate_json((ROOT / args.readiness).read_text())
            if args.readiness else ReadinessSnapshot()
        )
        report = reconcile(
            policy=policy, roadmap_path=ROOT / args.roadmap, evidence=evidence,
            commit_sha=_git("rev-parse", "HEAD"), git_dirty=bool(_git("status", "--porcelain")),
            readiness=readiness,
        )
        rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    else:
        rendered = generate_digest(DigestInput.model_validate_json((ROOT / args.input).read_text()), policy)
    if args.output:
        (ROOT / args.output).write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
