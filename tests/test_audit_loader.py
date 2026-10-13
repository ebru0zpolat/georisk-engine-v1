"""Tests for dashboard/audit_loader parsing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard.audit_loader import (
    load_audit_dataframe,
    load_geo_audit_dataframe,
    parse_audit_markdown,
    parse_audit_markdown_geo,
)


def test_parse_audit_markdown_ok() -> None:
    text = """
## B. Analiz çıktıları
- **Tesis:** Örnek Çimento A.Ş.
- **Gözlemlenen maksimum ısı:** 21.5 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 0.000040 mol/m²
## D. CCO mührü
"""
    row = parse_audit_markdown(text, source_label="x.md")
    assert row is not None
    assert row["Tesis"] == "Örnek Çimento A.Ş."
    assert row["Isı (°C)"] == 21.5
    assert row["NO2 (mol/m²)"] == 4e-5
    assert "Mühürlendi" in str(row["Durum"])


def test_parse_audit_markdown_missing_returns_none() -> None:
    assert parse_audit_markdown("# Boş", source_label="y.md") is None


def test_parse_audit_markdown_geo_extracts_coords() -> None:
    text = """
## A. Denetim parametreleri
- **Tesis:** Test Fabrika
- **AOI (İnceleme Alanı):** 38.745°N, 30.485°E (500 m buffer)
## B. Analiz çıktıları
- **Gözlemlenen maksimum ısı:** 22.0 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 0.000050 mol/m²
## D. CCO mührü
"""
    row = parse_audit_markdown_geo(text, source_label="t.md")
    assert row is not None
    assert row["lat"] == 38.745
    assert row["lon"] == 30.485
    assert row["Isı (°C)"] == 22.0


def test_parse_audit_markdown_geo_without_aoi_returns_none() -> None:
    text = """
- **Tesis:** X
- **Gözlemlenen maksimum ısı:** 10.0 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 1e-05 mol/m²
"""
    assert parse_audit_markdown_geo(text, source_label="x.md") is None


def test_load_geo_audit_dataframe_includes_rapor_column(tmp_path: Path) -> None:
    body = """## A.
- **Tesis:** Fabrika Z
- **AOI (İnceleme Alanı):** 40.0°N, 29.0°E (500 m)
## B.
- **Gözlemlenen maksimum ısı:** 15.0 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 0.00002 mol/m²
## D. CCO mührü
"""
    (tmp_path / "fabrika_z_20260501.md").write_text(body, encoding="utf-8")
    df = load_geo_audit_dataframe(tmp_path)
    assert len(df) == 1
    assert df.iloc[0]["lat"] == 40.0
    assert df.iloc[0]["lon"] == 29.0
    assert "Rapor" in df.columns
    assert df.iloc[0]["Rapor"] == "fabrika_z_20260501.md"


def test_load_audit_dataframe_from_tmp(tmp_path: Path) -> None:
    body = """# R
## B.
- **Tesis:** Fabrika X
- **Gözlemlenen maksimum ısı:** 10.0 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 1e-05 mol/m²
## D. CCO mührü
"""
    (tmp_path / "fabrika_x_20260501.md").write_text(body, encoding="utf-8")
    df = load_audit_dataframe(tmp_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["Tesis"] == "Fabrika X"
