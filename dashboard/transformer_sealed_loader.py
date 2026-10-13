"""Load trafo Primary Audit sealed Markdown reports (YAML front matter + table)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SEALED_DIR = (
    _REPO_ROOT / "docs" / "turkiye" / "transformers" / "sealed_reports"
)


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.lstrip().startswith("---"):
        return {}, text
    rest = text.lstrip()[3:].lstrip("\n")
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    yml = rest[:end].strip()
    body = rest[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(yml) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        return {}, text
    return meta, body


def load_transformer_sealed_dataframe(sealed_dir: Path | None = None) -> pd.DataFrame:
    """Return one row per ``*.md`` sealed report (excluding ``README.md``)."""
    root = sealed_dir or _DEFAULT_SEALED_DIR
    if not root.is_dir():
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for p in sorted(root.glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        meta, _ = _split_front_matter(p.read_text(encoding="utf-8"))
        if not meta:
            continue
        rows.append(
            {
                "Tesis": meta.get("facility_name_tr"),
                "Kimlik": meta.get("facility_id"),
                "Durum": meta.get("bundle_status"),
                "NO₂ AOI": meta.get("no2_aoi_mol_m2"),
                "NO₂ residual": meta.get("no2_residual_mol_m2"),
                "CO AOI": meta.get("co_aoi_mol_m2"),
                "CO residual": meta.get("co_residual_mol_m2"),
                "VIIRS AOI": meta.get("ntl_aoi_avg_rad"),
                "VIIRS residual": meta.get("ntl_residual_avg_rad"),
                "Termal °C": meta.get("thermal_celsius"),
                "Mühür (git)": (str(meta.get("seal_git_commit") or "")[:12] + "…")
                if meta.get("seal_git_commit")
                else None,
                "Aralik": f"{meta.get('start_date')} → {meta.get('end_date')}",
                "_dosya": p.name,
            }
        )
    return pd.DataFrame(rows)


def sealed_report_paths(sealed_dir: Path | None = None) -> list[Path]:
    root = sealed_dir or _DEFAULT_SEALED_DIR
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.glob("*.md") if p.name.upper() != "README.MD"
    )
