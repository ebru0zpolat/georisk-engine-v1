# Scripts

| Script | Purpose |
|--------|---------|
| `report_engine.py` | Şablona metrikleri basar; varsayılan olarak rapor sonuna metodoloji feragat snippet’i ekler (`--no-methodology-footer` ile kapatılır). PDF (pandoc + TeX): her sayfada üst bilgi metni + PDF’e özel `cco-audit-methodology.md` içeriği **Ek 1: Metodoloji** olarak eklenir (`docs/turkiye/pandoc_operational_report_header.tex`). Mac: `brew install pandoc` + `basictex` veya `tectonic`; istenen motor için `REPORT_ENGINE_PDF_ENGINE=tectonic`. `--no-pdf` ile kapatılır. |
| `landsat_thermal_audit.py` | QA_PIXEL maskeli LC08/LC09 median bileşik → AOI içi max ST_B10 → °C (EE). |
| `s5p_no2_audit.py` | S5P OFFL L3 troposferik NO₂ sütunu → AOI ortalaması (mol/m²). |
| `run_audit.py` | Termal + NO₂ + rapor; çıktı `reports/output/{slug}_{YYYYMMDD}.md`. |
| `run_integrated_audit.py` | **CCO birleşik denetim:** `.env` GEE kimlik ön kontrolü + varsayılan Çimsa Afyon AOI + rapor. |
| `generate_docs_operational_risk_bundle_example.py` | Çimsa Afyon şablonu + **Bölüm E** (`industrial_verification`, sabit örnek `audit_id`) → `docs/turkiye/examples/cimsa_afyon_20260501_operational_plus_risk_bundle.md` (EE yok). |
| `audit_dashboard.py` | CCO merkezi: **PyDeck** + tooltip, export; sekme **Public Whitepaper** (`docs/turkiye/whitepaper-operational-verification-public.md`). **Trafo:** üçüncü sekme — Primary Audit mühürlü raporlar (`docs/turkiye/transformers/sealed_reports/`). Sidebar: NDA due diligence yolu. `streamlit run scripts/audit_dashboard.py` |
| `transformer_audit.py` | Trafo **Primary Audit**: NO₂ / CO / VIIRS + halka arka plan + termal bağlam → mühürlü Markdown (`docs/turkiye/transformers/sealed_reports/`). `AUDIT_USE_MOCK=true python scripts/transformer_audit.py --all` |
| `s5p_co_audit.py` | S5P OFFL L3 CO sütunu → AOI ortalaması (mol/m²), isteğe bağlı ``region_geojson``. |
| `viirs_ntl_audit.py` | VIIRS DNB aylık ``avg_rad`` → AOI ortalaması; isteğe bağlı ``region_geojson``. |
| `transformer_s5p_signals.py` | Primary Audit sinyal demeti (AOI + halka residual, termal). |

Örnek (mock, EE yok):

```bash
AUDIT_USE_MOCK=true python scripts/run_audit.py --lat 38.745 --lon 30.485 --company Cimsa_Afyon
```

Canlı EE için `.env`: `GEE_PROJECT=...` (veya `GEE_PROJECT_ID`) ve `AUDIT_USE_MOCK` kapalı.

Kapalı devre / mühürlü operasyonel endeks / QOR: `docs/turkiye/georisk-sealed-index-closed-loop-publishing.md` · SKDM birincil sektörler: `docs/turkiye/sectors-skdm-primary-priorities.md` · Müşteri filigranı (trafo mühürü): `GEORISK_REPORT_WATERMARK` (`.env.example`).

Sadece şablon doldurma:

```bash
python scripts/report_engine.py --celsius 42.3 --img-id LC08_xxx -o reports/output/cimsa_afyon_report.md
```
