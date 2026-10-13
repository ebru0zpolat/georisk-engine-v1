"""Sektörel operasyonel doğrulama özeti — Streamlit.

Çalıştırma (repo kökünden)::

    streamlit run dashboard/streamlit_app.py

Varsayılan olarak ``reports/output/*.md`` raporlarından tabloyu doldurur; yoksa yerleşik örnek veri kullanılır.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root = str(_REPO_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)

import pandas as pd
import streamlit as st

from dashboard.audit_loader import default_demo_dataframe, load_audit_dataframe
_DEFAULT_OUTPUT = _REPO_ROOT / "reports" / "output"


def _resolve_dataframe() -> tuple[pd.DataFrame, str]:
    df = load_audit_dataframe(_DEFAULT_OUTPUT)
    if df.empty:
        return default_demo_dataframe(), "Örnek veri (henüz `reports/output/` içinde ayrıştırılabilir rapor yok)."
    return df, f"Kaynak: `{_DEFAULT_OUTPUT.relative_to(_REPO_ROOT)}/*.md`"


df, source_note = _resolve_dataframe()

st.set_page_config(page_title="Sektörel Şeffaflık Endeksi", layout="wide")
st.title("🛡️ 2026 Bahar Dönemi: Çimento Sektörü Operasyonel Doğrulama")
st.caption(source_note)
st.markdown("---")

col1, col2, col3 = st.columns(3)
col1.metric("Denetlenen Tesis", len(df))
col2.metric("Sektör Isı Ortalaması", f"{df['Isı (°C)'].mean():.2f} °C")
sealed_pct = (
    100.0
    if len(df) > 0 and (df["Durum"].astype(str).str.contains("Mühürlendi")).all()
    else (
        100.0
        * (df["Durum"].astype(str).str.contains("Mühürlendi")).sum()
        / max(len(df), 1)
    )
)
col3.metric("Uyum Oranı", f"{sealed_pct:.0f}%")

st.subheader("📊 Sektörel Karşılaştırma Matrisi")
st.dataframe(df, use_container_width=True)

st.subheader("🔥 Termal ve ☁️ Emisyon Dağılımı")
chart_df = df.set_index("Tesis")[["Isı (°C)", "NO2 (mol/m²)"]]
st.bar_chart(chart_df)

st.info(
    "Not: Veriler Google Earth Engine üzerinden türetilen uydu proxy özetleridir. "
    "Detaylı metodoloji için `docs/turkiye/cco-audit-methodology.md` ve ilgili tesiste özel notlara bakınız."
)
