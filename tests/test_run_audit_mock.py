"""Integration-style test for run_audit with mock thermal metrics."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")


def test_execute_full_audit_writes_report(
    mock_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.run_audit as run_audit_mod

    monkeypatch.setattr(run_audit_mod, "_utc_stamp_yyyymmdd", lambda: "20260501")

    from scripts.run_audit import execute_full_audit

    out = execute_full_audit(
        38.745,
        30.485,
        "Cimsa_Afyon",
        output_dir=tmp_path,
    )
    assert out.exists()
    assert out.name == "cimsa_afyon_20260501.md"
    text = out.read_text(encoding="utf-8")
    assert "Çimsa Afyon" in text
    assert "35.20" in text
    assert "LC08_L2SP_MOCK_EXAMPLE" in text
    assert "0.000140" in text
    assert "cco-audit-methodology.md" in text
    assert "Otomatik eklenen feragat" in text
