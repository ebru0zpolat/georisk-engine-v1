"""WP-2: public health stays liveness-only; chain verification is per organisation.

``GET /v1/audit-chain/verify`` reads the caller's own chain from the database
store. The organisation is taken from the authenticated principal; nothing in
the request can point it at another organisation.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa

from app.core.config import settings
from app.db.session import get_session_factory
from app.services.api_key_service import create_api_key
from app.storage.audit_trail_store import PostgresAuditTrailStore

_CHAIN_KEYS = {"audit_chain", "tip_hash", "records", "chain", "record_hash"}


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        found = set(obj)
        for value in obj.values():
            found |= _keys(value)
        return found
    if isinstance(obj, list):
        return set().union(*(_keys(v) for v in obj)) if obj else set()
    return set()


@pytest.mark.parametrize("path", ["/v1/health", "/health"])
def test_public_health_carries_no_audit_chain_information(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert not (_keys(response.json()) & _CHAIN_KEYS)


@pytest.fixture
def _require_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_key_required", True)


def _org() -> str:
    return f"org-{uuid4().hex[:8]}"


def _key(organisation: str, scopes: list[str]) -> dict[str, str]:
    async def _run() -> str:
        async with get_session_factory()() as session:
            raw, _ = await create_api_key(session, organisation_id=organisation, scopes=scopes)
            await session.commit()
            return raw

    return {"Authorization": f"Bearer {asyncio.run(_run())}"}


def _append(organisation: str, eal: float):
    store = PostgresAuditTrailStore(get_session_factory())
    return asyncio.run(
        store.append(
            organisation_id=organisation,
            methodology_version="eal-v0.1",
            valuation_date=date(2026, 1, 1),
            data_versions={"hazard": "v1"},
            parameters={"currency": "EUR"},
            inputs={"value": 1_000_000},
            outputs={"eal": eal},
            timestamp=datetime(2026, 10, 9, tzinfo=timezone.utc),
        )
    )


def _corrupt(record_id: str) -> None:
    async def _run() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                sa.text("UPDATE audit_trail_records SET record_hash = :h WHERE record_id = :rid"),
                {"h": uuid4().hex * 2, "rid": record_id},
            )
            await session.commit()

    asyncio.run(_run())


@pytest.mark.usefixtures("_require_api_key")
def test_verify_requires_a_key_and_the_evidence_scope(client):
    assert client.get("/v1/audit-chain/verify").status_code == 401
    response = client.get("/v1/audit-chain/verify", headers=_key(_org(), ["risk:read"]))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.usefixtures("_require_api_key")
def test_verify_reports_only_the_callers_organisation(client):
    org_a, org_b = _org(), _org()
    _append(org_a, 1.0)
    b1 = _append(org_b, 7.0)
    a2 = _append(org_a, 2.0)
    _corrupt(b1.record_id)

    headers = _key(org_a, ["evidence:read"])
    body = client.get("/v1/audit-chain/verify", headers=headers).json()
    assert body["organisation_id"] == org_a
    assert body["chain"] == "intact"
    assert body["records"] == 2
    assert body["tip_hash"] == a2.record_hash

    # A request cannot redirect verification to another organisation.
    redirected = client.get(f"/v1/audit-chain/verify?organisation_id={org_b}", headers=headers).json()
    assert redirected["organisation_id"] == org_a
    assert redirected["chain"] == "intact"

    body_b = client.get("/v1/audit-chain/verify", headers=_key(org_b, ["evidence:read"])).json()
    assert body_b["organisation_id"] == org_b
    assert body_b["chain"] == "broken"
    assert body_b["reason"] == "AUDIT_CHAIN_HASH_MISMATCH"
    assert body_b["tip_hash"] is None


@pytest.mark.usefixtures("_require_api_key")
def test_empty_chain_is_reported_as_empty_with_limits(client):
    body = client.get("/v1/audit-chain/verify", headers=_key(_org(), ["evidence:read"])).json()
    assert body["chain"] == "empty"
    assert body["records"] == 0
    assert "AUDIT_CHAIN_EMPTY" in body["limits"]


@pytest.mark.usefixtures("_require_api_key")
def test_intact_chain_carries_no_limits(client):
    org = _org()
    _append(org, 1.0)
    body = client.get("/v1/audit-chain/verify", headers=_key(org, ["evidence:read"])).json()
    assert body["chain"] == "intact"
    assert body["limits"] == []


def test_verify_refuses_without_a_database(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "database_url", None)
    response = client.get("/v1/audit-chain/verify")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUDIT_STORE_UNAVAILABLE"
