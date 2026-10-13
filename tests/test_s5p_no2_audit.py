"""Tests for scripts/s5p_no2_audit.py."""

from __future__ import annotations

import pytest


def test_fetch_no2_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.s5p_no2_audit import fetch_no2_l3_mean_mol_m2

    out = fetch_no2_l3_mean_mol_m2(
        38.745, 30.485, start_date="2026-01-01", end_date="2026-05-02"
    )
    assert out["status"] == "SUCCESS"
    assert out["no2_mean_mol_m2"] == 0.00014


def test_fetch_no2_region_geojson_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    from scripts.s5p_no2_audit import fetch_no2_l3_mean_mol_m2

    geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [32.0, 39.0],
                [32.01, 39.0],
                [32.01, 39.01],
                [32.0, 39.01],
                [32.0, 39.0],
            ]
        ],
    }
    out = fetch_no2_l3_mean_mol_m2(
        region_geojson=geom,
        start_date="2026-01-01",
        end_date="2026-05-02",
    )
    assert out["status"] == "SUCCESS"
    assert out["no2_mean_mol_m2"] == 0.00014


def test_fetch_no2_missing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_USE_MOCK", raising=False)
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)
    from scripts.s5p_no2_audit import fetch_no2_l3_mean_mol_m2

    out = fetch_no2_l3_mean_mol_m2(
        38.745, 30.485, start_date="2026-01-01", end_date="2026-05-02"
    )
    assert out["status"] == "ERROR"
