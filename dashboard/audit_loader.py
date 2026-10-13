"""Parse operational audit Markdown files under ``reports/output/`` into tabular metrics."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

_TESIS = re.compile(r"- \*\*Tesis:\*\*\s*(.+?)\s*$", re.MULTILINE)
_ISI = re.compile(
    r"- \*\*Gözlemlenen maksimum ısı:\*\*\s*([\d.]+)\s*°C",
    re.IGNORECASE,
)
_NO2 = re.compile(
    r"- \*\*Ortalama NO₂ yoğunluğu \(AOI ortalaması\):\*\*\s*([\d.eE+-]+)\s*mol/m²",
    re.IGNORECASE,
)
_AOI_COORDS = re.compile(
    r"- \*\*AOI[^:]*:\*\*\s*([\d.]+)\s*°?\s*N\s*,\s*([\d.]+)\s*°?\s*E",
    re.IGNORECASE,
)


def parse_audit_markdown(text: str, *, source_label: str) -> dict[str, str | float] | None:
    """Extract Tesis, thermal °C, NO₂ mean from one report body."""
    m_t = _TESIS.search(text)
    m_i = _ISI.search(text)
    m_n = _NO2.search(text)
    if not (m_t and m_i and m_n):
        return None
    tesis = m_t.group(1).strip()
    isi = float(m_i.group(1))
    no2 = float(m_n.group(1))
    sealed = "CCO mührü" in text or "cco mührü" in text.lower()
    durum = "✅ Mühürlendi" if sealed else "—"
    return {
        "Tesis": tesis,
        "Kaynak": source_label,
        "Isı (°C)": isi,
        "NO2 (mol/m²)": no2,
        "Durum": durum,
    }


def load_audit_dataframe(output_dir: Path) -> pd.DataFrame:
    """Build a dataframe from ``*.md`` audit outputs; newest file per stem wins."""
    rows: list[dict[str, str | float]] = []
    if not output_dir.is_dir():
        return pd.DataFrame()

    paths = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    seen: set[str] = set()
    for path in paths:
        stem_key = path.stem.rsplit("_", 1)[0] if "_" in path.stem else path.stem
        if stem_key in seen:
            continue
        body = path.read_text(encoding="utf-8")
        row = parse_audit_markdown(body, source_label=path.name)
        if row:
            rows.append(row)
            seen.add(stem_key)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    display = df.drop(columns=["Kaynak"], errors="ignore")
    return display


def parse_audit_markdown_geo(text: str, *, source_label: str) -> dict[str, str | float] | None:
    """Same as ``parse_audit_markdown`` plus ``lat`` / ``lon`` from the AOI line (°N, °E)."""
    row = parse_audit_markdown(text, source_label=source_label)
    if row is None:
        return None
    m_c = _AOI_COORDS.search(text)
    if not m_c:
        return None
    lat = float(m_c.group(1))
    lon = float(m_c.group(2))
    out = dict(row)
    out["lat"] = lat
    out["lon"] = lon
    return out


def load_geo_audit_dataframe(output_dir: Path) -> pd.DataFrame:
    """Like ``load_audit_dataframe`` but only rows with parsable AOI coordinates (for ``st.map``)."""
    rows: list[dict[str, str | float]] = []
    if not output_dir.is_dir():
        return pd.DataFrame()

    paths = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    seen: set[str] = set()
    for path in paths:
        stem_key = path.stem.rsplit("_", 1)[0] if "_" in path.stem else path.stem
        if stem_key in seen:
            continue
        body = path.read_text(encoding="utf-8")
        row = parse_audit_markdown_geo(body, source_label=path.name)
        if row:
            rows.append(row)
            seen.add(stem_key)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "Kaynak" in df.columns:
        df = df.rename(columns={"Kaynak": "Rapor"})
    return df


def default_demo_dataframe() -> pd.DataFrame:
    """Fallback table when no parsable reports exist (bahar 2026 örnek seti)."""
    return pd.DataFrame(
        {
            "Tesis": ["Çimsa Afyon", "Limak Balıkesir", "Akçansa Çanakkale"],
            "Isı (°C)": [20.11, 20.06, 19.25],
            "NO2 (mol/m²)": [0.000036, 0.000033, 0.000028],
            "Durum": ["✅ Mühürlendi", "✅ Mühürlendi", "✅ Mühürlendi"],
        }
    )
