"""Tests for scripts/viirs_ntl_audit.py."""

from __future__ import annotations

import pytest


def test_fetch_viirs_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.viirs_ntl_audit import fetch_viirs_dnb_avg_rad_mean

    out = fetch_viirs_dnb_avg_rad_mean(
        39.65,
        27.88,
        start_date="2026-01-01",
        end_date="2026-05-02",
    )
    assert out["status"] == "SUCCESS"
    assert out["ntl_avg_rad"] == 32.5
    assert out.get("ntl_cf_cvg_mean") == 11.25
