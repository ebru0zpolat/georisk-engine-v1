"""Data source validation rules and API."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.core.data_source_registry import DATA_SOURCE_REGISTRY
from app.core.data_source_registry import get_data_source
from app.core.data_source_validation import delivery_mode_for, validate_all_sources, validate_source
from app.main import app


def test_validate_all_sources_covers_registry() -> None:
    results = validate_all_sources()
    assert len(results) == len(DATA_SOURCE_REGISTRY)
    assert {r.source_id for r in results} == {e.id for e in DATA_SOURCE_REGISTRY}


def test_each_source_has_checks_and_passes_in_ci() -> None:
    for entry in DATA_SOURCE_REGISTRY:
        result = validate_source(entry)
        assert result.checks, f"no checks for {entry.id}"
        assert result.passed, f"validation failed for {entry.id}: {result.checks}"


def test_validation_report_api() -> None:
    client = TestClient(app)
    r = client.get("/v1/data-sources/validation")
    assert r.status_code == 200
    data = r.json()
    assert data["source_count"] == 9
    assert data["passed_count"] == 9
    assert data["package_doc"] == "docs/GeoRisk_DataSource_Validation_Package.docx"
    assert len(data["sources"]) == 9


def test_validation_api_single_source() -> None:
    client = TestClient(app)
    r = client.get("/v1/data-sources/gee_viirs_ntl/validation")
    assert r.status_code == 200
    data = r.json()
    assert data["source_id"] == "gee_viirs_ntl"
    assert data["passed"] is True
    assert any(c["id"] == "viirs_dataset_registered" for c in data["checks"])


def test_validation_api_unknown_source_404() -> None:
    client = TestClient(app)
    r = client.get("/v1/data-sources/unknown_source/validation")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "DATA_SOURCE_NOT_FOUND"


def test_audit_delivery_mode_fallback_without_gee_project(monkeypatch) -> None:
    monkeypatch.delenv("AUDIT_USE_MOCK", raising=False)
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)
    entry = get_data_source("audit_s5p_no2")
    assert entry is not None
    assert delivery_mode_for(entry) == "fallback"


def test_audit_delivery_mode_mock_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    entry = get_data_source("audit_s5p_no2")
    assert entry is not None
    assert delivery_mode_for(entry) == "mock"
