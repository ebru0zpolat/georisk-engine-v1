"""WP-1 identity & tenancy: API-key auth, scopes, organisation isolation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.db.models import OrganisationModel
from app.db.session import get_session_factory
from app.services.api_key_service import create_api_key, revoke_api_key
from app.storage.api_key_repository import ApiKeyRepository


@pytest.fixture(autouse=True)
def _require_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_key_required", True)


def _create_key(organisation: str, scopes: list[str], *, ttl_days: int | None = None) -> tuple[str, str]:
    async def _run() -> tuple[str, str]:
        factory = get_session_factory()
        async with factory() as session:
            raw, record = await create_api_key(
                session, organisation_id=organisation, scopes=scopes, ttl_days=ttl_days
            )
            await session.commit()
            return raw, record.id

    return asyncio.run(_run())


def test_create_key_provisions_organisation_row():
    async def _run() -> OrganisationModel | None:
        factory = get_session_factory()
        async with factory() as session:
            await create_api_key(session, organisation_id="org-provisioned", scopes=["cases:read"])
            await session.commit()
            return await session.get(OrganisationModel, "org-provisioned")

    org = asyncio.run(_run())
    assert org is not None
    assert org.id == "org-provisioned"


def _expire_key(key_id: str) -> None:
    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as session:
            record = await ApiKeyRepository(session).get(key_id)
            assert record is not None
            record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

    asyncio.run(_run())


def _revoke(key_id: str) -> None:
    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as session:
            assert await revoke_api_key(session, key_id=key_id)
            await session.commit()

    asyncio.run(_run())


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def test_missing_key_returns_401_envelope(client):
    response = client.get("/v1/cases")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_invalid_key_returns_401(client):
    response = client.get("/v1/cases", headers=_bearer("grk_totally-not-a-real-key"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_x_api_key_header_accepted(client):
    raw, _ = _create_key("org-x", ["cases:read"])
    response = client.get("/v1/cases", headers={"X-API-Key": raw})
    assert response.status_code == 200


def test_valid_key_without_scope_returns_403(client):
    raw, _ = _create_key("org-scope", ["risk:read"])
    response = client.get("/v1/cases", headers=_bearer(raw))
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_valid_key_with_scope_is_allowed(client):
    raw, _ = _create_key("org-ok", ["cases:read"])
    response = client.get("/v1/cases", headers=_bearer(raw))
    assert response.status_code == 200
    assert "cases" in response.json()


def test_expired_key_returns_401(client):
    raw, key_id = _create_key("org-exp", ["cases:read"])
    _expire_key(key_id)
    response = client.get("/v1/cases", headers=_bearer(raw))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_revoked_key_returns_401(client):
    raw, key_id = _create_key("org-rev", ["cases:read"])
    _revoke(key_id)
    response = client.get("/v1/cases", headers=_bearer(raw))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_health_and_release_manifest_stay_open(client):
    assert client.get("/v1/health").status_code == 200
    assert client.get("/v1/release-manifest").status_code == 200


def test_cases_write_scope_enforced(client):
    raw, _ = _create_key("org-w", ["cases:read"])
    payload = {"title": "scope check", "asset_name": "asset"}
    response = client.post("/v1/cases", json=payload, headers=_bearer(raw))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_cases_are_isolated_by_organisation(client):
    raw_a, _ = _create_key("org-a", ["cases:read", "cases:write"])
    raw_b, _ = _create_key("org-b", ["cases:read", "cases:write"])

    created = client.post(
        "/v1/cases",
        json={"title": "A only", "asset_name": "asset-a"},
        headers=_bearer(raw_a),
    )
    assert created.status_code == 201, created.json()

    cases_b = client.get("/v1/cases", headers=_bearer(raw_b)).json()["cases"]
    assert [c["title"] for c in cases_b] == []

    cases_a = client.get("/v1/cases", headers=_bearer(raw_a)).json()["cases"]
    assert [c["title"] for c in cases_a] == ["A only"]

    case_id = created.json()["id"]
    cross = client.get(f"/v1/cases/{case_id}", headers=_bearer(raw_b))
    assert cross.status_code == 404


def test_ownership_column_is_named_organisation_id():
    """INV-12: one name for the owning organisation across models and principal."""
    from dataclasses import fields

    from app.core.security import Principal
    from app.db.models import ApiKeyModel, CaseModel

    for model in (ApiKeyModel, CaseModel):
        columns = set(model.__table__.columns.keys())
        assert "organisation_id" in columns
        assert "tenant_id" not in columns
    principal_fields = {f.name for f in fields(Principal)}
    assert "organisation_id" in principal_fields
    assert "tenant_id" not in principal_fields


@pytest.mark.parametrize("app_env", ["production", "demo"])
def test_deployed_runtimes_ignore_api_key_required_false(monkeypatch, app_env):
    """INV-02: a deployed runtime cannot be switched to anonymous access.

    Demo routes write to the shared audit trail and snapshot store, so
    APP_ENV=demo is not an isolated sandbox and must not open them.
    """
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "api_key_required", False)
    assert settings.auth_required is True


@pytest.mark.parametrize("app_env", ["local", "dev", "test"])
def test_local_runtimes_default_to_open_gate(monkeypatch, app_env):
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "api_key_required", None)
    assert settings.auth_required is False


def test_demo_runtime_rejects_anonymous_demo_and_case_routes(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "demo")
    monkeypatch.setattr(settings, "api_key_required", None)
    for path in ("/v1/demo/run?asset_id=coastal_industrial_med", "/v1/cases"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert client.get("/v1/health").status_code == 200


def test_write_scope_implies_read_in_the_same_family():
    from app.core.security import Principal

    writer = Principal(organisation_id="o", scopes=frozenset({"portfolio:write"}))
    assert writer.has_scope("portfolio:read")
    assert not writer.has_scope("reports:read")
    reader = Principal(organisation_id="o", scopes=frozenset({"portfolio:read"}))
    assert not reader.has_scope("portfolio:write")


def test_coarse_risk_read_scope_reaches_post_scoring(client):
    raw, _ = _create_key("org-risk", ["risk:read"])
    response = client.post(
        "/v1/risk/score",
        json={"asset_name": "a", "latitude": 41.02, "longitude": 29.01, "preset_id": "industrial_v1"},
        headers=_bearer(raw),
    )
    assert response.status_code not in (401, 403)


def test_successful_auth_persists_last_used_at(client):
    raw, key_id = _create_key("org-used", ["cases:read"])
    assert client.get("/v1/cases", headers=_bearer(raw)).status_code == 200

    async def _run():
        async with get_session_factory()() as session:
            return await ApiKeyRepository(session).get(key_id)

    assert asyncio.run(_run()).last_used_at is not None


def test_async_batch_task_is_invisible_to_another_organisation(client):
    raw_a, _ = _create_key("org-batch-a", ["risk:read"])
    raw_b, _ = _create_key("org-batch-b", ["risk:read"])
    accepted = client.post(
        "/v1/risk/batch/async",
        json={"preset_id": "industrial_v1", "assets": [{"id": "A1", "lat": 41.0, "lon": 29.0}]},
        headers=_bearer(raw_a),
    )
    assert accepted.status_code == 202, accepted.content
    status_path = accepted.json()["status_path"]
    assert client.get(status_path, headers=_bearer(raw_a)).status_code == 200
    other = client.get(status_path, headers=_bearer(raw_b))
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "NOT_FOUND"
