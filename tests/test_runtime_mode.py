"""Production fail-closed control for connector stubs."""

from __future__ import annotations

import pandas as pd
import pytest
from starlette.testclient import TestClient

from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest
from app.connectors.gee import GeeConnector, GeePointRequest
from app.core.config import Settings, settings
from app.core.runtime_mode import (
    ConnectorStubProhibitedError,
    ProductionLiveSourceError,
    assert_production_live_sources,
    allows_connector_stubs,
    connector_data_mode,
    missing_production_live_sources,
    normalize_app_env,
    oras5_uses_stub,
    production_eligible_for_response,
)
from app.main import app


def test_normalize_app_env_aliases_and_fail_closed() -> None:
    assert normalize_app_env("local") == "local"
    assert normalize_app_env("DEV") == "dev"
    assert normalize_app_env("testing") == "test"
    assert normalize_app_env("demo") == "demo"
    assert normalize_app_env("prod") == "production"
    assert normalize_app_env("production") == "production"
    assert normalize_app_env("staging") == "production"
    assert normalize_app_env("") == "local"


def _settings(**kwargs: object) -> Settings:
    """Build Settings without inheriting the suite ``APP_ENV=local`` default."""
    return Settings(_env_file=None, **kwargs)


def _clear_live_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the unconfigured stub branch regardless of ambient credentials.

    Clearing only ``oras5_zarr_url`` leaves the CDS API path live whenever a key
    is present in ``.env`` or the environment, so a stub assertion would not
    exercise the branch it names.
    """
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", None)
    monkeypatch.setattr(settings, "gee_enabled", False)
    monkeypatch.setattr(settings, "gee_project", None)


#: Scorable stand-in for a live CDS retrieval (>= the 24-month feature minimum).
_STUB_SERIES = pd.Series(
    range(36), index=pd.date_range("2020-01-01", periods=36, freq="MS"), dtype=float
)


def test_settings_normalizes_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    cfg = _settings()
    assert cfg.app_env == "production"
    assert cfg.is_production is True
    assert cfg.allows_connector_stubs is False


def test_demo_and_local_permit_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    local = _settings()
    monkeypatch.setenv("APP_ENV", "demo")
    demo = _settings()
    monkeypatch.setenv("APP_ENV", "test")
    test_env = _settings()
    assert allows_connector_stubs(local) is True
    assert allows_connector_stubs(demo) is True
    assert allows_connector_stubs(test_env) is True


def test_production_startup_rejects_missing_zarr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ORAS5_ZARR_URL", raising=False)
    monkeypatch.delenv("GEE_ENABLED", raising=False)
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    cfg = _settings()
    missing = missing_production_live_sources(cfg)
    assert "ORAS5_ZARR_URL" in missing
    assert "GEE_ENABLED" in missing
    assert "GEE_PROJECT" in missing
    with pytest.raises(ProductionLiveSourceError, match="ORAS5_ZARR_URL"):
        assert_production_live_sources(cfg)


def test_production_startup_rejects_arco_without_cds_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "ORAS5_ZARR_URL",
        "https://arco.datastores.ecmwf.int/cadl-arco-geo-001/"
        "arco/reanalysis_oras5/consolidated/geoChunked.zarr",
    )
    monkeypatch.delenv("CDSAPI_KEY", raising=False)
    monkeypatch.delenv("CDS_API_KEY", raising=False)
    monkeypatch.delenv("COPERNICUS_CDS_API_KEY", raising=False)
    monkeypatch.setenv("GEE_ENABLED", "true")
    monkeypatch.setenv("GEE_PROJECT", "demo-project")
    cfg = _settings()
    assert "CDSAPI_KEY" in missing_production_live_sources(cfg)
    with pytest.raises(ProductionLiveSourceError, match="CDSAPI_KEY"):
        assert_production_live_sources(cfg)


def test_production_startup_accepts_complete_live_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ORAS5_ZARR_URL", "memory://synthetic-oras5")
    monkeypatch.setenv("GEE_ENABLED", "true")
    monkeypatch.setenv("GEE_PROJECT", "demo-project")
    cfg = _settings()
    assert missing_production_live_sources(cfg) == []
    assert_production_live_sources(cfg)


def test_demo_startup_allows_missing_live_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "demo")
    cfg = _settings()
    assert missing_production_live_sources(cfg) == []
    assert_production_live_sources(cfg)


def test_oras5_stub_prohibited_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    _clear_live_sources(monkeypatch)
    with pytest.raises(ConnectorStubProhibitedError) as exc_info:
        CDSOras5Connector().fetch_features(
            Oras5PointRequest(latitude=36.85, longitude=30.75)
        )
    assert exc_info.value.code == "CONNECTOR_STUB_PROHIBITED"
    assert exc_info.value.status_code == 503
    assert exc_info.value.details["source"] == "oras5"


def test_oras5_bulk_stub_prohibited_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    _clear_live_sources(monkeypatch)
    with pytest.raises(ConnectorStubProhibitedError):
        CDSOras5Connector().fetch_features_many(
            [Oras5PointRequest(latitude=36.85, longitude=30.75)]
        )


def test_gee_stub_prohibited_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    _clear_live_sources(monkeypatch)
    with pytest.raises(ConnectorStubProhibitedError) as exc_info:
        GeeConnector().fetch_features(
            GeePointRequest(latitude=36.85, longitude=30.75)
        )
    assert exc_info.value.details["source"] == "gee"


def test_oras5_stub_permitted_and_labelled_in_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "demo")
    _clear_live_sources(monkeypatch)
    features = CDSOras5Connector().fetch_features(
        Oras5PointRequest(latitude=36.85, longitude=30.75)
    )
    assert features == CDSOras5Connector._fallback_features()


def test_score_api_labels_stub_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_live_sources(monkeypatch)
    client = TestClient(app)
    r = client.post(
        "/v1/risk/score",
        json={
            "asset_name": "Stub label",
            "latitude": 41.02,
            "longitude": 29.01,
            "preset_id": "industrial_v1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["data_mode"] == "stub"
    assert data["production_eligible"] is False


def test_oras5_features_api_labels_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_live_sources(monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/oras5/features", params={"latitude": 36.85, "longitude": 30.75})
    assert r.status_code == 200
    data = r.json()
    assert data["data_mode"] == "stub"
    assert data["production_eligible"] is False
    assert "sst_trend_c_per_decade" in data


def test_gee_features_api_labels_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_live_sources(monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/gee/features", params={"latitude": 36.85, "longitude": 29.01})
    assert r.status_code == 200
    data = r.json()
    assert data["data_mode"] == "stub"
    assert data["production_eligible"] is False


def test_demo_run_labels_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_live_sources(monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/demo/run", params={"asset_id": "coastal_industrial_med"})
    assert r.status_code == 200
    data = r.json()
    assert data["data_mode"] == "stub"
    assert data["production_eligible"] is False


def test_score_in_production_without_live_sources_is_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.db.session import get_session_factory
    from app.services.api_key_service import create_api_key

    async def _key() -> str:
        async with get_session_factory()() as session:
            raw, _ = await create_api_key(session, organisation_id="org-prod", scopes=["risk:read"])
            await session.commit()
            return raw

    monkeypatch.setattr(settings, "app_env", "production")
    _clear_live_sources(monkeypatch)
    client = TestClient(app)
    r = client.post(
        "/v1/risk/score",
        headers={"Authorization": f"Bearer {asyncio.run(_key())}"},
        json={
            "asset_name": "Prod reject",
            "latitude": 41.02,
            "longitude": 29.01,
            "preset_id": "industrial_v1",
        },
    )
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "CONNECTOR_STUB_PROHIBITED"
    assert body["error"]["details"]["source"] == "oras5"


def test_connector_data_mode_and_eligibility_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_live_sources(monkeypatch)
    assert connector_data_mode(settings) == "stub"
    assert production_eligible_for_response(settings) is False

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://oras5")
    monkeypatch.setattr(settings, "gee_enabled", True)
    monkeypatch.setattr(settings, "gee_project", "demo-project")
    assert connector_data_mode(settings) == "live"
    assert production_eligible_for_response(settings) is False


def test_cds_api_key_without_zarr_is_labelled_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CDS API path is a live read and must not be advertised as a stub."""
    _clear_live_sources(monkeypatch)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "cds-key")
    assert oras5_uses_stub(settings) is False

    monkeypatch.setattr(settings, "gee_enabled", True)
    monkeypatch.setattr(settings, "gee_project", "demo-project")
    assert connector_data_mode(settings) == "live"


def test_oras5_features_api_labels_cds_key_read_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_live_sources(monkeypatch)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "cds-key")
    monkeypatch.setattr(
        CDSOras5Connector,
        "_timeseries_via_cdsapi",
        lambda self, payload: (_STUB_SERIES, _STUB_SERIES),
    )
    client = TestClient(app)
    r = client.get("/v1/oras5/features", params={"latitude": 36.85, "longitude": 30.75})
    assert r.status_code == 200
    assert r.json()["data_mode"] == "live"


def test_health_reports_stub_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "demo")
    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["app_env"] == "demo"
    assert body["connector_stubs_permitted"] is True
