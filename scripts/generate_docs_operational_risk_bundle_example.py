"""Write a committed example: Çimsa Afyon operational template + industrial verification.

Output: ``docs/turkiye/examples/cimsa_afyon_20260501_operational_plus_risk_bundle.md``

Operational body uses the same numeric placeholders as ``AUDIT_USE_MOCK=true`` audit
scripts (no Earth Engine). The GeoRisk block uses a **fixed** ``audit_id`` so the file
stays stable across regenerations; live API calls produce a new UUID each time.

Usage::

    PYTHONPATH=. python scripts/generate_docs_operational_risk_bundle_example.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.reports.markdown import format_industrial_verification_markdown
from app.services.industrial_verification_ref import build_industrial_verification_ref
from scripts.report_engine import render_cimsa_afyon_report

# Deterministic doc sample (not a real production audit id).
_EXAMPLE_AUDIT_ID = "aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee"
_LAT = 38.745
_LON = 30.485

_BRIDGE_TR = """
---

## E. GeoRisk API — industrial verification (aynı ``audit_id``)

Bu bölüm, üstteki **operasyonel termal + NO₂ doğrulama raporu** (A–D) ile aynı AOI koordinatlarında üretilebilecek **climate-risk** yanıtındaki ``industrial_verification`` özetidir. ``linked_audit_id``, o isteğin ``audit_id`` alanı ile aynıdır; böylece operasyonel mühür / Primary Audit hatları ile çapraz referans tek kayıt altında toplanır.

**Uçlar:** ``POST /v1/reports/risk`` (rapor uçlarında bu blok varsayılan olarak açıktır) veya ``POST /v1/risk/score`` + ``include_industrial_verification_ref: true``.

*Not:* Aşağıdaki ``linked_audit_id`` değeri bu örnek dosyada **dokümantasyon tutarlılığı** için sabitlenmiştir; canlı çağrıda her seferinde yeni bir UUID üretilir.
""".strip()


def compose_cimsa_operational_plus_risk_bundle_markdown() -> str:
    operational = render_cimsa_afyon_report(
        celsius=35.2,
        img_id="LC08_L2SP_MOCK_EXAMPLE",
        no2_mean_mol_m2=0.00014,
        append_methodology_footer=True,
    )
    iv = build_industrial_verification_ref(
        audit_id=_EXAMPLE_AUDIT_ID,
        latitude=_LAT,
        longitude=_LON,
    )
    industrial_md = format_industrial_verification_markdown(
        iv,
        linked_audit_note=(
            "(aynı istekteki climate-risk yanıtının ``audit_id`` alanı ile aynıdır; "
            "bu örnek dosyada değer dokümantasyon için sabitlenmiştir.)"
        ),
    )
    return f"{operational.rstrip()}\n\n{_BRIDGE_TR}\n\n{industrial_md.strip()}\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate docs/turkiye/examples/cimsa_afyon_* operational+risk bundle.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print composed Markdown instead of writing the default path.",
    )
    args = parser.parse_args()
    text = compose_cimsa_operational_plus_risk_bundle_markdown()
    if args.stdout:
        print(text, end="")
        return
    out = (
        _REPO_ROOT
        / "docs"
        / "turkiye"
        / "examples"
        / "cimsa_afyon_20260501_operational_plus_risk_bundle.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out.resolve())


if __name__ == "__main__":
    main()
