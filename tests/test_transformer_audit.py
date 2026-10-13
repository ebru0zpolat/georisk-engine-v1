"""Tests for trafo Primary Audit pipeline (mock)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_run_primary_audit_writes_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.transformer_audit import run_primary_audit_for_facility
    from scripts.transformer_facilities import facility_by_id

    fac = facility_by_id("astor_enerji_ankara")
    assert fac is not None
    out = run_primary_audit_for_facility(
        fac,
        start_date="2026-01-01",
        end_date="2026-05-02",
        out_dir=tmp_path,
    )
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "astor_enerji_ankara" in text
    assert "NO₂" in text or "NO2" in text


def test_load_transformer_sealed_dataframe(tmp_path: Path) -> None:
    from dashboard.transformer_sealed_loader import load_transformer_sealed_dataframe

    sample = tmp_path / "astor_enerji_ankara_20990101.md"
    sample.write_text(
        "---\n"
        "facility_id: astor_enerji_ankara\n"
        "facility_name_tr: Astor Test\n"
        "bundle_status: SUCCESS\n"
        "start_date: '2026-01-01'\n"
        "end_date: '2026-05-02'\n"
        "seal_git_commit: deadbeef\n"
        "no2_aoi_mol_m2: 0.1\n"
        "no2_residual_mol_m2: 0.02\n"
        "co_aoi_mol_m2: 0.01\n"
        "co_residual_mol_m2: 0.001\n"
        "ntl_aoi_avg_rad: 10.0\n"
        "ntl_residual_avg_rad: 2.0\n"
        "thermal_celsius: 30.0\n"
        "---\n\n# body\n",
        encoding="utf-8",
    )
    df = load_transformer_sealed_dataframe(tmp_path)
    assert not df.empty
    assert df.iloc[0]["Kimlik"] == "astor_enerji_ankara"
