#!/usr/bin/env python3
"""Fetch GeoRisk score, Markdown report, and optional PDF to an output directory."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# Allow running from DeerFlow sandbox when repo client is on PYTHONPATH
try:
    from georisk_mcp.client import GeoRiskClient, build_report_body, build_score_body
except ImportError:
    repo_root = Path(__file__).resolve().parents[5]
    mcp_src = repo_root / "integrations" / "deerflow" / "mcp_server"
    sys.path.insert(0, str(mcp_src))
    from georisk_mcp.client import GeoRiskClient, build_report_body, build_score_body


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GeoRisk bundle for VC memo workflow")
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--radius-km", type=float, default=10.0)
    parser.add_argument("--sector", default="industrial")
    parser.add_argument(
        "--no-industrial-verification",
        action="store_true",
        help="Omit industrial verification on score and report",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()

    include_iv = not args.no_industrial_verification
    score_body = build_score_body(
        asset_name=args.asset_name,
        latitude=args.latitude,
        longitude=args.longitude,
        radius_km=args.radius_km,
        sector=args.sector,
        include_industrial_verification_ref=include_iv,
    )
    report_body = build_report_body(
        asset_name=args.asset_name,
        latitude=args.latitude,
        longitude=args.longitude,
        radius_km=args.radius_km,
        sector=args.sector,
        include_industrial_verification_ref=include_iv,
    )

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    with GeoRiskClient() as client:
        score = client.score(score_body)
        (out / "score.json").write_text(json.dumps(score, indent=2), encoding="utf-8")
        md = client.report_markdown(report_body)
        (out / "report.md").write_text(md, encoding="utf-8")
        if not args.skip_pdf:
            b64 = client.report_pdf_base64(report_body)
            (out / "report.pdf").write_bytes(base64.b64decode(b64))

    print(json.dumps({"output_dir": str(out.resolve()), "audit_id": score.get("audit_id")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
