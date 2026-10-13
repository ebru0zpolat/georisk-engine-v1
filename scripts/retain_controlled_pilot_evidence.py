"""Retain a controlled-pilot smoke evidence file in durable, immutable storage.

Thin entrypoint over ``app.ops.retention.S3ObjectLockRetention`` so the
controlled-pilot workflow calls tested Python rather than inline shell.  The
adapter itself verifies bucket versioning, Object Lock, COMPLIANCE mode and the
retain-until horizon; anything it cannot establish is a failure here.

    PYTHONPATH=. python scripts/retain_controlled_pilot_evidence.py \
        --evidence controlled-pilot-evidence.json \
        --bucket "$EVIDENCE_BUCKET" --retain-days "$RETENTION_DAYS"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ops.retention import S3ObjectLockRetention  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="Evidence JSON path")
    parser.add_argument("--bucket", required=True, help="Object-lock bucket")
    parser.add_argument("--region", default=None, help="AWS region")
    parser.add_argument(
        "--retain-days",
        type=int,
        default=S3ObjectLockRetention.MIN_RETENTION_DAYS,
        help="Compliance retention horizon in days",
    )
    parser.add_argument("--prefix", default="controlled-pilot")
    args = parser.parse_args(argv)

    payload = Path(args.evidence).read_text(encoding="utf-8")
    record = json.loads(payload)
    evidence_id = record.get("verification_id")
    if not evidence_id:
        print("evidence has no verification_id", file=sys.stderr)
        return 1

    store = S3ObjectLockRetention.from_botocore(
        args.bucket,
        region=args.region,
        prefix=args.prefix,
        retain_days=args.retain_days,
    )
    result = store.write(
        evidence_id,
        payload,
        {"git-sha": str(record.get("release_commit_sha", ""))},
    )
    if not result.success:
        # The error names the control that failed; it carries no credential.
        print(f"RETENTION FAILED: {result.error}", file=sys.stderr)
        return 1

    if not store.verify_checksum(evidence_id):
        print("RETENTION FAILED: stored checksum does not verify", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "evidence_id": result.evidence_id,
                "content_sha256": result.content_sha256,
                "retention_status": result.retention_status,
                "storage": f"s3://{args.bucket}/{args.prefix}/{evidence_id}.json",
                "retention_days": args.retain_days,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
