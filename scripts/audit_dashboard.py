#!/usr/bin/env python3
"""CCO operasyonel doğrulama merkezi: PyDeck harita, tooltip ve mühürlü rapor indirme.

Çalıştırma (repo kökünden)::

    streamlit run scripts/audit_dashboard.py

Harita: isteğe bağlı ``MAPBOX_API_KEY`` / ``MAPBOX_API_TOKEN``; yoksa Carto Positron.
Veri ayrıştırma: ``dashboard.audit_loader.load_geo_audit_dataframe``.

**Public Whitepaper:** ``docs/turkiye/whitepaper-operational-verification-public.md`` ikinci sekmede gösterilir.

**Trafo Primary Audit (ESG Watch):** üçüncü sekme — ``docs/turkiye/transformers/sealed_reports/*.md`` ve AOI haritası
(``primary_audit_facilities.geojson``). Üretim: ``python scripts/transformer_audit.py --all``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

import pandas as pd
import pydeck as pdk
import streamlit as st

from app.scoring.capacity_proxy import (
    estimate_capacity,
    format_capacity_pct_precise,
)
from dashboard.audit_loader import load_geo_audit_dataframe
from dashboard.transformer_sealed_loader import (
    load_transformer_sealed_dataframe,
    sealed_report_paths,
)
from scripts.transformer_facilities import centroid_lat_lon, load_primary_audit_facilities

REPORT_DIR = _REPO_ROOT / "reports" / "output"
_SEALED_TRANSFORMER_DIR = _REPO_ROOT / "docs" / "turkiye" / "transformers" / "sealed_reports"
_PUBLIC_WHITEPAPER = (
    _REPO_ROOT / "docs" / "turkiye" / "whitepaper-operational-verification-public.md"
)

_CARTO_LIGHT = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"


def _map_style_and_keys() -> tuple[str, dict[str, str]]:
    token = (os.getenv("MAPBOX_API_KEY") or os.getenv("MAPBOX_API_TOKEN") or "").strip()
    if token:
        return "mapbox://styles/mapbox/light-v9", {"mapbox": token}
    return _CARTO_LIGHT, {}


st.set_page_config(
    page_title="Jeo-Denetim Merkezi",
    layout="wide",
    page_icon="🛡️",
)
st.title("🛡️ CCO Operasyonel Doğrulama ve Raporlama Merkezi (Çimento + Trafo)")

tab_panel, tab_whitepaper, tab_transformer = st.tabs(
    ["Çimento: Operasyonel panel", "Public Whitepaper", "Trafo: Primary Audit (ESG Watch)"]
)

with tab_whitepaper:
    st.caption(
        "Kamuya açık metodoloji özeti · Tam feragat ve maske politikası: "
        "`docs/turkiye/cco-audit-methodology.md`"
    )
    if _PUBLIC_WHITEPAPER.is_file():
        body = _PUBLIC_WHITEPAPER.read_text(encoding="utf-8")
        st.markdown(body)
        st.download_button(
            label="📥 Whitepaper (.md) indir",
            data=body.encode("utf-8"),
            file_name="GeoRisk_Operational_Verification_Whitepaper_Public.md",
            mime="text/markdown",
            key="download_public_whitepaper",
        )
    else:
        st.error(f"Dosya bulunamadı: {_PUBLIC_WHITEPAPER.relative_to(_REPO_ROOT)}")

with tab_transformer:
    st.caption(
        "Primary Audit tesileri: `docs/turkiye/transformers/primary_audit_facilities.geojson` · "
        "Metodoloji: `docs/turkiye/transformers/transformer-audit-methodology.md`"
    )
    fac_list = load_primary_audit_facilities()
    fac_map_rows = []
    for fac in fac_list:
        lat, lon = centroid_lat_lon(fac["geometry"])
        fac_map_rows.append(
            {
                "Tesis": fac["name_tr"],
                "Kimlik": fac["id"],
                "lat": lat,
                "lon": lon,
            }
        )
    fac_df = pd.DataFrame(fac_map_rows)
    if not fac_df.empty:
        st.subheader("📍 Primary Audit AOI (merkez)")
        vs = pdk.ViewState(
            latitude=float(fac_df["lat"].mean()),
            longitude=float(fac_df["lon"].mean()),
            zoom=6.2,
            pitch=35,
        )
        layer_t = pdk.Layer(
            "ScatterplotLayer",
            fac_df,
            get_position=["lon", "lat"],
            get_color=[20, 140, 80, 200],
            get_radius=12000,
            pickable=True,
        )
        map_style, api_keys = _map_style_and_keys()
        st.pydeck_chart(
            pdk.Deck(
                map_style=map_style,
                initial_view_state=vs,
                layers=[layer_t],
                tooltip={"html": "<b>{Tesis}</b><br/>{Kimlik}", "style": {"color": "white"}},
                api_keys=api_keys,
            )
        )

    sealed_df = load_transformer_sealed_dataframe(_SEALED_TRANSFORMER_DIR)
    st.divider()
    st.subheader("📋 Mühürlü trafo raporları (YAML + tablo)")
    if sealed_df.empty:
        st.warning(
            "Henüz mühürlü rapor yok. Repo kökünden: "
            "`AUDIT_USE_MOCK=true python scripts/transformer_audit.py --all`"
        )
    else:
        show = sealed_df.drop(columns=["_dosya"], errors="ignore")
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("📥 Sealed export")
        paths = sealed_report_paths(_SEALED_TRANSFORMER_DIR)
        cols = st.columns(min(3, max(1, len(paths))))
        for i, md_path in enumerate(paths):
            with cols[i % len(cols)]:
                st.caption(md_path.name)
                st.download_button(
                    label="Markdown indir",
                    data=md_path.read_bytes(),
                    file_name=md_path.name,
                    mime="text/markdown",
                    key=f"tr_md_{i}",
                )

with tab_panel:
    df = load_geo_audit_dataframe(REPORT_DIR)

    if not df.empty:
        df = df.copy()
        df["Dosya_Adi"] = df["Rapor"].astype(str)
        df["Dosya_Yolu"] = df["Dosya_Adi"].apply(lambda n: str((REPORT_DIR / n).resolve()))
        _kap_pct = df["Isı (°C)"].astype(float).map(estimate_capacity)
        df["_kap_pct"] = _kap_pct
        df["Tahmini Üretim Kapasitesi"] = _kap_pct.map(format_capacity_pct_precise)

        st.success("Otomatik veri okuma aktif.")

        deck_df = df.rename(
            columns={
                "Isı (°C)": "Isi",
                "NO2 (mol/m²)": "NO2",
                "Tahmini Üretim Kapasitesi": "Kapasite_pct",
            }
        )

        st.subheader("📍 Sektörel İzleme ve Tooltip Katmanı")

        view_state = pdk.ViewState(
            latitude=float(deck_df["lat"].mean()),
            longitude=float(deck_df["lon"].mean()),
            zoom=5.5,
            pitch=40,
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            deck_df,
            get_position=["lon", "lat"],
            get_color=[200, 30, 0, 160],
            get_radius=15000,
            pickable=True,
        )

        tooltip = {
            "html": (
                "<b>{Tesis}</b><br/>Isı: {Isi} °C<br/>NO2: {NO2}<br/>"
                "<b>Kapasite (proxy):</b> {Kapasite_pct}"
            ),
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }

        map_style, api_keys = _map_style_and_keys()
        if not api_keys.get("mapbox"):
            st.caption(
                "Harita: Carto Positron (varsayılan). Mapbox Light için `MAPBOX_API_KEY` tanımlayın."
            )

        st.pydeck_chart(
            pdk.Deck(
                map_style=map_style,
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip,
                api_keys=api_keys,
            )
        )

        st.divider()

        st.subheader("📥 Mühürlü Rapor Export Merkezi")
        cols_dl = st.columns(len(df))
        for i, (_, row) in enumerate(df.iterrows()):
            md_path = REPORT_DIR / row["Dosya_Adi"]
            with cols_dl[i]:
                st.info(f"**{row['Tesis']}**")
                if not md_path.is_file():
                    st.warning("Markdown dosyası bulunamadı.")
                    continue
                md_bytes = md_path.read_bytes()
                pdf_path = md_path.with_suffix(".pdf")
                if pdf_path.is_file():
                    st.download_button(
                        label="📄 PDF indir",
                        data=pdf_path.read_bytes(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        key=f"pdf_{i}",
                    )
                st.download_button(
                    label="📄 Markdown indir",
                    data=md_bytes,
                    file_name=md_path.name,
                    mime="text/markdown",
                    key=f"md_{i}",
                )

        st.divider()

        col_table, col_chart = st.columns([1, 1])
        with col_table:
            st.subheader("📋 Detaylı Veri Matrisi")
            hide = {"lat", "lon", "Dosya_Yolu", "Rapor", "_kap_pct"}
            show = df.drop(columns=[c for c in hide if c in df.columns], errors="ignore")
            st.caption(
                "Tahmini Üretim Kapasitesi: Landsat termal proxy doğrusal ölçeği; **iki ondalık yüzde puanı** "
                "(`estimate_capacity`). Gerçek kapasite / tonaj saha verisi gerektirir."
            )
            st.dataframe(show, use_container_width=True, hide_index=True)
        with col_chart:
            st.subheader("🔥 Termal özeti")
            st.bar_chart(df.set_index("Tesis")[["Isı (°C)"]])
            st.subheader("📈 Tahmini kapasite (proxy)")
            st.bar_chart(df.set_index("Tesis")["_kap_pct"])

    else:
        st.error("Görüntülenecek mühürlü rapor bulunamadı.")
        rel = REPORT_DIR.relative_to(_REPO_ROOT)
        st.caption(f"Beklenen kaynak: `{rel}/*.md` (AOI °N/°E + termal/NO₂ satırları).")

st.sidebar.caption(
    "Tahmini Üretim Kapasitesi: doğrusal proxy; gösterim **iki ondalık yüzde puanı**. "
    "Yatırım tavsiyesi değildir — `app/scoring/capacity_proxy.py`."
)
st.sidebar.divider()
st.sidebar.subheader("Due diligence (NDA)")
st.sidebar.caption(
    "Market Alpha ve Institutional müşteriler: formül içermeyen teknik özet "
    "`docs/turkiye/due-diligence/` (NDA + kontrat kapsamında)."
)
st.sidebar.caption(
    "İç mülkiyet çerçevesi: `docs/turkiye/proprietary-thermal-capacity-proxy.md` "
    "(patent hukuku için bağımsız danışman)."
)
st.sidebar.divider()
st.sidebar.info(
    "İpucu: Haritada nesneye tıklayınca özet görünür; PDF yalnız kardeş `.pdf` varsa sunulur."
)
st.sidebar.write(f"Kaynak: `{REPORT_DIR.relative_to(_REPO_ROOT)}/*.md`")
st.sidebar.divider()
st.sidebar.caption(
    "Trafo: üçüncü sekme — mühürlü raporlar "
    f"`{_SEALED_TRANSFORMER_DIR.relative_to(_REPO_ROOT)}/*.md` · "
    "`AUDIT_USE_MOCK=true python scripts/transformer_audit.py --all`"
)
