"""Run unified audit: Landsat QA_PIXEL-masked ST_B10 + S5P L3 NO₂ → Markdown report."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

from dotenv import load_dotenv

from scripts.landsat_thermal_audit import fetch_operational_thermal_metrics
from scripts.report_engine import write_report
from scripts.s5p_no2_audit import fetch_no2_l3_mean_mol_m2


def _utc_stamp_yyyymmdd() -> str:
    """Return UTC calendar stamp for report filenames (test-hook friendly)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _sanitize_report_slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    return slug.strip("_").lower() or "audit"


def execute_full_audit(
    lat: float,
    lon: float,
    company_name: str,
    *,
    start_date: str = "2026-01-01",
    end_date: str = "2026-05-02",
    buffer_m: float = 500.0,
    no2_buffer_m: float = 2000.0,
    output_dir: Path | None = None,
) -> Path:
    """Fetch Landsat thermal + S5P L3 NO₂ means and render the Markdown template.

    ``end_date`` is exclusive for Earth Engine (default ``2026-05-02`` includes May 1).

    Args ``lat`` / ``lon`` are WGS84 in decimal degrees (same order as CLI).

    Environment:
    - ``GEE_PROJECT`` or ``GEE_PROJECT_ID`` for live EE.
    - ``AUDIT_USE_MOCK=true`` for offline demo values (no RPC).
    """
    load_dotenv()

    metrics = fetch_operational_thermal_metrics(
        lat,
        lon,
        start_date=start_date,
        end_date=end_date,
        buffer_m=buffer_m,
    )

    no2_metrics = fetch_no2_l3_mean_mol_m2(
        lat,
        lon,
        start_date=start_date,
        end_date=end_date,
        buffer_m=no2_buffer_m,
    )

    celsius = metrics.get("celsius")
    if isinstance(celsius, (int, float)):
        celsius = float(celsius)
    else:
        celsius = None

    img_id = metrics.get("img_id")
    if img_id is not None:
        img_id = str(img_id)

    no2_val = no2_metrics.get("no2_mean_mol_m2")
    if isinstance(no2_val, (int, float)):
        no2_val = float(no2_val)
    else:
        no2_val = None

    status_t = metrics.get("status", "UNKNOWN")
    detail_t = metrics.get("detail")
    status_n = no2_metrics.get("status", "UNKNOWN")
    detail_n = no2_metrics.get("detail")

    out_dir = output_dir or (_REPO_ROOT / "reports" / "output")
    slug = _sanitize_report_slug(company_name)
    report_path = out_dir / f"{slug}_{_utc_stamp_yyyymmdd()}.md"

    write_report(
        report_path,
        celsius=celsius,
        img_id=img_id,
        no2_mean_mol_m2=no2_val,
    )

    print("[OK] Audit metrics")
    print(f"     thermal: status={status_t} max_degC={celsius}")
    if detail_t:
        print(f"              detail: {detail_t}")
    print(f"     no2_l3:  status={status_n} mean_mol_m2={no2_val}")
    if detail_n:
        print(f"              detail: {detail_n}")
    print(f"[OK] Report written: {report_path.resolve()}")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Full thermal audit → Markdown report.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--company", required=True, help="Company name for output filename")
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default="2026-05-02", help="Exclusive end for EE filterDate")
    parser.add_argument("--buffer-m", type=float, default=500.0)
    parser.add_argument(
        "--no2-buffer-m",
        type=float,
        default=2000.0,
        help="AOI radius (m) for S5P NO₂ reduceRegion mean.",
    )
    args = parser.parse_args()
    execute_full_audit(
        args.lat,
        args.lon,
        args.company,
        start_date=args.start_date,
        end_date=args.end_date,
        buffer_m=args.buffer_m,
        no2_buffer_m=args.no2_buffer_m,
    )


if __name__ == "__main__":
    main()
