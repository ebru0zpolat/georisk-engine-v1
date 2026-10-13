"""Data source registry, validation rules, and API catalog."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.core.data_source_registry import (
    DATA_SOURCE_REGISTRY,
    GEE_S5P_NO2_DATASET,
    GEE_VIIRS_NTL_DATASET,
    get_data_source,
    list_data_sources,
)
from app.connectors.gee import GeeConnector
from app.main import app


def test_registry_has_nine_sources() -> None:
    assert len(DATA_SOURCE_REGISTRY) == 9


def test_list_data_sources_production_tier() -> None:
    production = list_data_sources(tier="production")
    assert len(production) == 3
    ids = {e.id for e in production}
    assert ids == {"oras5_ocean", "gee_viirs_ntl", "gee_s5p_no2"}


def test_get_data_source_unknown_returns_none() -> None:
    assert get_data_source("nonexistent") is None


def test_gee_connector_uses_registry_dataset_ids() -> None:
    assert GeeConnector.VIIRS_DATASET == GEE_VIIRS_NTL_DATASET
    assert GeeConnector.S5P_NO2_DATASET == GEE_S5P_NO2_DATASET


def test_data_sources_api_lists_all() -> None:
    client = TestClient(app)
    r = client.get("/v1/data-sources")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 9
    assert len(data["sources"]) == 9
    assert data["package_doc"] == "docs/georisk_data_source_loi_package.html"
    assert data["validation_package_doc"] == "docs/GeoRisk_DataSource_Validation_Package.docx"


def test_data_sources_api_filters_audit_tier() -> None:
    client = TestClient(app)
    r = client.get("/v1/data-sources", params={"tier": "audit"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 4
    assert all(s["tier"] == "audit" for s in data["sources"])
