"""Tests for scripts/landsat_thermal_audit.py"""

from __future__ import annotations

import pytest


def test_fetch_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.landsat_thermal_audit import fetch_operational_thermal_metrics

    out = fetch_operational_thermal_metrics(
        38.745, 30.485, start_date="2026-01-01", end_date="2026-05-02"
    )
    assert out["status"] == "SUCCESS"
    assert out["celsius"] == 35.2


def test_fetch_missing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_USE_MOCK", raising=False)
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)
    from scripts.landsat_thermal_audit import fetch_operational_thermal_metrics

    out = fetch_operational_thermal_metrics(
        38.745, 30.485, start_date="2026-01-01", end_date="2026-05-02"
    )
    assert out["status"] == "ERROR"
    assert "GEE_PROJECT" in (out.get("detail") or "")
