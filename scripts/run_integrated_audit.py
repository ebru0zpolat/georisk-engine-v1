#!/usr/bin/env python3
"""CCO birleşik uydu denetimi: .env ön kontrolü + termal + NO₂ raporu.

**Mimari:** Bu dosyada ``ee.Initialize`` veya ham görüntü zinciri **yoktur** — iş mantığı
``scripts/landsat_thermal_audit.py`` (QA_PIXEL maskeli LC08/LC09 median bileşik) ve
``scripts/s5p_no2_audit.py`` (L3 troposferik NO₂ bandı, tarih/filtre) ile ``scripts/run_audit.execute_full_audit``
üzerinden rapora bağlanır. Tek dosyada kopyala‑yapıştır EE örnekleri: tarihsiz koleksiyon,
yanlış NO₂ bandı adı (``NO2_column_number_density`` vs L3 ``tropospheric_…``), QA_PIXEL iddiası
ama maske uygulanmaması ve ``kelvin is None`` riskinden kaçının.

Ön koşul (canlı Earth Engine için):
  - ``GEE_PROJECT`` veya ``GEE_PROJECT_ID`` .env içinde tanımlı olmalıdır.

Yerel / CI denemesi:
  - ``AUDIT_USE_MOCK=true`` → GEE kimliği zorunlu değildir.

Çalıştırma (repo kökünden)::

    python scripts/run_integrated_audit.py

Çıktı: ``reports/output/{slug}_{YYYYMMDD}.md`` — şablonda CCO mührü (Bölüm D) ve
``docs/turkiye/cco-audit-methodology.md`` referansı bulunur; dosya sonuna metodoloji ile hizalı
**otomatik feragat** (snippet) eklenir (`scripts/report_engine.write_report`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

from dotenv import load_dotenv


def require_gee_identity_or_mock() -> None:
    """Exit with stderr guidance unless mock mode or GEE project env is set."""
    load_dotenv()
    mock = os.getenv("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}
    project = (os.getenv("GEE_PROJECT") or os.getenv("GEE_PROJECT_ID") or "").strip()
    if mock:
        return
    if not project:
        print(
            "[FAIL] Canlı Earth Engine için GEE_PROJECT veya GEE_PROJECT_ID .env içinde tanımlı değil.",
            file=sys.stderr,
        )
        print(
            "       Yerel deneme: AUDIT_USE_MOCK=true python scripts/run_integrated_audit.py",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    require_gee_identity_or_mock()

    # Import after dotenv so app/settings patterns stay consistent with other scripts
    from scripts.run_audit import execute_full_audit

    parser = argparse.ArgumentParser(
        description="CCO integrated audit (Landsat thermal + S5P NO₂ → Markdown).",
    )
    parser.add_argument("--lat", type=float, default=38.745)
    parser.add_argument("--lon", type=float, default=30.485)
    parser.add_argument("--company", "--name", default="Cimsa_Afyon", dest="company")
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default="2026-05-02")
    parser.add_argument("--buffer-m", type=float, default=500.0)
    parser.add_argument("--no2-buffer-m", type=float, default=2000.0)
    args = parser.parse_args()

    out = execute_full_audit(
        args.lat,
        args.lon,
        args.company,
        start_date=args.start_date,
        end_date=args.end_date,
        buffer_m=args.buffer_m,
        no2_buffer_m=args.no2_buffer_m,
    )
    print(f"[OK] Integrated audit complete: {out.resolve()}")
    print(
        "[OK] CCO mührü (Bölüm D) ve metodoloji linki rapor gövdesinde: "
        "docs/turkiye/cco-audit-methodology.md"
    )


if __name__ == "__main__":
    main()
