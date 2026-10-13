"""Health endpoint deployment provenance (``git_sha``)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app


def test_health_returns_unknown_git_sha_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "git_sha", "unknown")
    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "georisk-engine"
    assert body["git_sha"] == "unknown"
    assert body["app_env"] in {"local", "dev", "test", "demo", "production"}
    assert "connector_stubs_permitted" in body
    # Do not leak unrelated deploy/env metadata.
    assert "railway" not in {k.lower() for k in body}
    assert "project" not in {k.lower() for k in body}


def test_health_returns_configured_git_sha(monkeypatch) -> None:
    monkeypatch.setattr(settings, "git_sha", "d1e7c3fabc1234567890")
    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "georisk-engine"
    assert body["git_sha"] == "d1e7c3fabc1234567890"
    assert "app_env" in body
    assert "connector_stubs_permitted" in body


def test_settings_prefers_explicit_git_sha_over_railway(monkeypatch) -> None:
    monkeypatch.setenv("GIT_SHA", "explicit-sha-111")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "railway-sha-222")
    cfg = Settings(_env_file=None)
    assert cfg.git_sha == "explicit-sha-111"


def test_settings_falls_back_to_railway_git_commit_sha(monkeypatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "railway-sha-333")
    cfg = Settings(_env_file=None)
    assert cfg.git_sha == "railway-sha-333"


def test_settings_git_sha_unknown_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.git_sha == "unknown"
