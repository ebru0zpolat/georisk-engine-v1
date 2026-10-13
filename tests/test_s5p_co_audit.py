"""Tests for scripts/s5p_co_audit.py."""

from __future__ import annotations

import pytest


def test_fetch_co_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.s5p_co_audit import fetch_co_l3_mean_mol_m2

    out = fetch_co_l3_mean_mol_m2(
        40.0,
        32.7,
        start_date="2026-01-01",
        end_date="2026-05-02",
    )
    assert out["status"] == "SUCCESS"
    assert out["co_mean_mol_m2"] == 0.00003
