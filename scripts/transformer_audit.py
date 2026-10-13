#!/usr/bin/env python3
"""Trafo Primary Audit: NO₂ / CO / VIIRS (+ termal bağlam) → mühürlü Markdown.

Çimento ``audit_dashboard.py`` ile aynı disiplinde ikinci dikey; çıktılar
``docs/turkiye/transformers/sealed_reports/`` altında tutulur. Repo HEAD özeti
rapora yazılır (iç mühür; kriptografik imza değildir).

Örnek::

    AUDIT_USE_MOCK=true python scripts/transformer_audit.py --all
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

from dotenv import load_dotenv

from scripts.transformer_facilities import load_primary_audit_facilities
from scripts.transformer_s5p_signals import fetch_primary_audit_signals

_SEALED_DIR = _REPO_ROOT / "docs" / "turkiye" / "transformers" / "sealed_reports"
_TEMPLATE = (
    _REPO_ROOT
    / "docs"
    / "turkiye"
    / "transformers"
    / "templates"
    / "sealed_primary_audit_report.md"
)


def _utc_stamp_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()[:40]
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _fmt_float(v: float | None, nd: int = 6) -> str:
    if v is None:
        return "—"
    return f"{float(v):.{nd}f}"


def _render_sealed_markdown(
    *,
    facility: dict[str, object],
    sig: dict[str, object],
    start_date: str,
    end_date: str,
    seal_git_commit: str,
    ring_buffer_m: float,
) -> str:
    body = _TEMPLATE.read_text(encoding="utf-8")
    fid = str(facility["id"])
    name_tr = str(facility["name_tr"])
    tier = str(facility.get("audit_tier") or "Primary")
    notes = str(facility.get("notes_tr") or "—")

    wm = (os.getenv("GEORISK_REPORT_WATERMARK") or "").strip()
    watermark_label = wm if wm else "— (yerel üretim; alıcı filigranı atanmadı — bkz. .env.example)"

    repl = {
        "{{facility_name_tr}}": name_tr,
        "{{facility_id}}": fid,
        "{{audit_tier}}": tier,
        "{{facility_notes_tr}}": notes,
        "{{start_date}}": start_date,
        "{{end_date}}": end_date,
        "{{seal_git_commit}}": seal_git_commit,
        "{{generated_utc}}": _utc_iso(),
        "{{ring_buffer_m}}": str(int(ring_buffer_m)),
        "{{no2_aoi_mol_m2}}": _fmt_float(sig.get("no2_aoi_mol_m2") if isinstance(sig.get("no2_aoi_mol_m2"), (int, float)) else None),
        "{{no2_ring_mol_m2}}": _fmt_float(sig.get("no2_ring_mol_m2") if isinstance(sig.get("no2_ring_mol_m2"), (int, float)) else None),
        "{{no2_residual_mol_m2}}": _fmt_float(sig.get("no2_residual_mol_m2") if isinstance(sig.get("no2_residual_mol_m2"), (int, float)) else None),
        "{{co_aoi_mol_m2}}": _fmt_float(sig.get("co_aoi_mol_m2") if isinstance(sig.get("co_aoi_mol_m2"), (int, float)) else None, nd=8),
        "{{co_ring_mol_m2}}": _fmt_float(sig.get("co_ring_mol_m2") if isinstance(sig.get("co_ring_mol_m2"), (int, float)) else None, nd=8),
        "{{co_residual_mol_m2}}": _fmt_float(sig.get("co_residual_mol_m2") if isinstance(sig.get("co_residual_mol_m2"), (int, float)) else None, nd=8),
        "{{ntl_aoi_avg_rad}}": _fmt_float(sig.get("ntl_aoi_avg_rad") if isinstance(sig.get("ntl_aoi_avg_rad"), (int, float)) else None, nd=2),
        "{{ntl_ring_avg_rad}}": _fmt_float(sig.get("ntl_ring_avg_rad") if isinstance(sig.get("ntl_ring_avg_rad"), (int, float)) else None, nd=2),
        "{{ntl_residual_avg_rad}}": _fmt_float(sig.get("ntl_residual_avg_rad") if isinstance(sig.get("ntl_residual_avg_rad"), (int, float)) else None, nd=2),
        "{{ntl_cf_cvg_aoi_mean}}": _fmt_float(
            sig.get("ntl_cf_cvg_aoi_mean") if isinstance(sig.get("ntl_cf_cvg_aoi_mean"), (int, float)) else None,
            nd=2,
        ),
        "{{ntl_cf_cvg_ring_mean}}": _fmt_float(
            sig.get("ntl_cf_cvg_ring_mean") if isinstance(sig.get("ntl_cf_cvg_ring_mean"), (int, float)) else None,
            nd=2,
        ),
        "{{thermal_celsius}}": _fmt_float(sig.get("thermal_celsius") if isinstance(sig.get("thermal_celsius"), (int, float)) else None, nd=2),
        "{{thermal_img_id}}": str(sig.get("thermal_img_id") or "—"),
        "{{bundle_status}}": str(sig.get("status") or "UNKNOWN"),
        "{{bundle_detail}}": str(sig.get("detail") or "—"),
        "{{watermark_label}}": watermark_label,
    }
    for k, v in repl.items():
        body = body.replace(k, v)
    front: dict[str, object] = {
        "kind": "georisk_transformer_primary_audit",
        "facility_id": fid,
        "facility_name_tr": name_tr,
        "audit_tier": tier,
        "start_date": start_date,
        "end_date": end_date,
        "seal_git_commit": seal_git_commit,
        "generated_utc": _utc_iso(),
        "ring_buffer_m": ring_buffer_m,
        "bundle_status": sig.get("status"),
        "bundle_detail": sig.get("detail"),
        "no2_aoi_mol_m2": sig.get("no2_aoi_mol_m2"),
        "no2_ring_mol_m2": sig.get("no2_ring_mol_m2"),
        "no2_residual_mol_m2": sig.get("no2_residual_mol_m2"),
        "co_aoi_mol_m2": sig.get("co_aoi_mol_m2"),
        "co_ring_mol_m2": sig.get("co_ring_mol_m2"),
        "co_residual_mol_m2": sig.get("co_residual_mol_m2"),
        "ntl_aoi_avg_rad": sig.get("ntl_aoi_avg_rad"),
        "ntl_ring_avg_rad": sig.get("ntl_ring_avg_rad"),
        "ntl_residual_avg_rad": sig.get("ntl_residual_avg_rad"),
        "ntl_cf_cvg_aoi_mean": sig.get("ntl_cf_cvg_aoi_mean"),
        "ntl_cf_cvg_ring_mean": sig.get("ntl_cf_cvg_ring_mean"),
        "thermal_celsius": sig.get("thermal_celsius"),
        "thermal_img_id": sig.get("thermal_img_id"),
        "report_watermark": wm or None,
    }
    yml = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{yml}\n---\n\n{body}"


def run_primary_audit_for_facility(
    facility: dict[str, object],
    *,
    start_date: str,
    end_date: str,
    ring_buffer_m: float = 8000.0,
    out_dir: Path | None = None,
) -> Path:
    geom = facility["geometry"]
    if not isinstance(geom, dict):
        raise TypeError("facility.geometry must be a GeoJSON dict")
    sig = fetch_primary_audit_signals(
        geom,
        start_date=start_date,
        end_date=end_date,
        ring_buffer_m=ring_buffer_m,
    )
    seal = _git_head()
    text = _render_sealed_markdown(
        facility=facility,
        sig=sig,
        start_date=start_date,
        end_date=end_date,
        seal_git_commit=seal,
        ring_buffer_m=ring_buffer_m,
    )
    dest = out_dir or _SEALED_DIR
    dest.mkdir(parents=True, exist_ok=True)
    slug = str(facility["id"]).strip().lower()
    path = dest / f"{slug}_{_utc_stamp_yyyymmdd()}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Trafo Primary Audit → sealed Markdown under docs/turkiye/transformers/sealed_reports/.",
    )
    parser.add_argument(
        "--facility",
        help="Facility id from primary_audit_facilities.geojson (e.g. astor_enerji_ankara).",
    )
    parser.add_argument("--all", action="store_true", help="Run for every Primary facility in GeoJSON.")
    parser.add_argument("--list", action="store_true", dest="list_facilities", help="Print facility ids and exit.")
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default="2026-05-02", help="Exclusive end for EE filterDate.")
    parser.add_argument("--ring-buffer-m", type=float, default=8000.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override sealed report directory (default: docs/turkiye/transformers/sealed_reports).",
    )
    args = parser.parse_args()

    if args.list_facilities:
        for f in load_primary_audit_facilities():
            print(f["id"], "-", f["name_tr"])
        return

    if not args.all and not args.facility:
        parser.error("Specify --facility ID or --all")

    facilities = load_primary_audit_facilities()
    if args.all:
        targets = facilities
    else:
        fid = args.facility.strip().lower()
        targets = [f for f in facilities if str(f["id"]).lower() == fid]
        if not targets:
            print(f"[FAIL] Unknown facility id: {args.facility}", file=sys.stderr)
            sys.exit(1)

    for fac in targets:
        out = run_primary_audit_for_facility(
            fac,
            start_date=args.start_date,
            end_date=args.end_date,
            ring_buffer_m=args.ring_buffer_m,
            out_dir=args.output_dir,
        )
        print(f"[OK] Sealed report: {out.resolve()}")


if __name__ == "__main__":
    main()
