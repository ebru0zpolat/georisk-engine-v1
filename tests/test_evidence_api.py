"""WP-3: evidence API — retrieve, verify and export one audit record.

Covers the plan's acceptance list: the ``audit_id`` returned by a portfolio run
works on all three endpoints; another organisation's id is a 404; a broken
chain makes ``verify`` say ``broken`` and weakens — never hides — the evidence;
missing horizons and other limits are visible in the limits block.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from uuid import uuid4

import pytest
import sqlalchemy as sa

from app.core import error_codes as codes
from app.core.config import settings
from app.db.session import get_session_factory
from app.services.api_key_service import create_api_key
from app.services.audit_trail import compute_record_hash

_DEMO_RUN = "/v1/portfolio/demo-run/golden-antalya?max_assets=1"


@pytest.fixture(autouse=True)
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


def _run_demo(client, organisation: str) -> tuple[str, str, dict[str, str]]:
    headers = _key(organisation, ["portfolio:write", "evidence:read"])
    response = client.post(_DEMO_RUN, json={}, headers=headers)
    assert response.status_code == 200, response.content
    body = response.json()
    return body["narrative"]["assets"][0]["eal_audit_record_id"], body["run_id"], headers


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def test_audit_id_from_a_run_works_on_all_three_endpoints(client):
    org = _org()
    audit_id, run_id, headers = _run_demo(client, org)

    evidence = client.get(f"/v1/evidence/{audit_id}", headers=headers)
    assert evidence.status_code == 200, evidence.content
    body = evidence.json()
    assert body["audit_id"] == audit_id
    assert body["organisation_id"] == org
    assert body["run_id"] == run_id
    assert body["integrity_status"] == "intact"
    assert body["run"]["run_id"] == run_id
    assert body["identity"]["methodology_version"]
    assert body["identity"]["source_commit"]
    assert body["integrity"]["record_hash_valid"] is True
    assert body["integrity"]["chain"]["status"] == "intact"

    verify = client.get(f"/v1/evidence/{audit_id}/verify", headers=headers).json()
    assert verify["chain"] == "intact"
    assert verify["record_hash_valid"] is True
    assert verify["verified_at"]

    export = client.get(f"/v1/evidence/{audit_id}/export", headers=headers).json()
    content = export["content"]
    assert export["content_sha256"] == hashlib.sha256(_canonical(content).encode()).hexdigest()
    record = content["record"]
    assert compute_record_hash(record["prev_hash"], record["payload"]) == record["record_hash"]
    assert record["payload"]["organisation_id"] == org
    assert record["payload"]["run_id"] == run_id


def test_limits_are_derived_and_show_missing_horizons(client):
    audit_id, _, headers = _run_demo(client, _org())
    limits = client.get(f"/v1/evidence/{audit_id}", headers=headers).json()["limits"]
    assert limits["horizons"]["missing"] == ["2030", "2050"]
    assert limits["horizons"]["status"] == "not_available"
    for code in (
        codes.HORIZONS_MISSING,
        codes.SYNTHETIC_INPUTS_PRESENT,
        codes.NOT_PRODUCTION_ELIGIBLE,
        codes.MODEL_NOT_VALIDATED_FOR_USE_CASE,
    ):
        assert code in limits["codes"], code
    assert limits["production_eligible"] is False
    assert limits["model_validated_for_use_case"] is False
    assert limits["synthetic_inputs"], "stub/synthetic inputs must be listed, not dropped"


def test_recorded_source_manifest_is_returned(client):
    audit_id, _, headers = _run_demo(client, _org())
    body = client.get(f"/v1/evidence/{audit_id}", headers=headers).json()
    manifest = body["source_manifest"]
    assert manifest["status"] == "recorded"
    by_id = {item["source_id"]: item for item in manifest["records"]}
    assert by_id["damage_curves"]["state"] == "synthetic"
    assert codes.SOURCE_MANIFEST_NOT_AVAILABLE not in body["limits"]["codes"]
    synthetic = {item["source"] for item in body["limits"]["synthetic_inputs"]}
    assert "damage_curves" in synthetic


def _record_id_by_methodology(organisation: str, prefix: str) -> str:
    async def _run() -> str:
        async with get_session_factory()() as session:
            rows = (
                await session.execute(sa.select(_model()).where(_model().organisation_id == organisation))
            ).scalars().all()
            return next(row.record_id for row in rows if row.payload["methodology_version"].startswith(prefix))

    return asyncio.run(_run())


def test_record_without_a_manifest_shows_it_as_not_available(client):
    org = _org()
    _, _, headers = _run_demo(client, org)
    adaptation_id = _record_id_by_methodology(org, "adaptation-evidence")
    body = client.get(f"/v1/evidence/{adaptation_id}", headers=headers).json()
    assert body["source_manifest"]["status"] == "not_available"
    assert body["source_manifest"]["declared_versions"]
    assert codes.SOURCE_MANIFEST_NOT_AVAILABLE in body["limits"]["codes"]


def test_unlicensed_sources_are_listed_as_blocked(client):
    org = _org()
    headers = _key(org, ["portfolio:write", "evidence:read"])
    response = client.post(
        "/v1/portfolio/analyze",
        json={
            "valuation_date": "2021-07-28",
            "asset": {
                "asset_id": "IST-01", "latitude": 41.01, "longitude": 28.97,
                "asset_value": 2_000_000, "building_type": "office", "use_class": "commercial",
            },
        },
        headers=headers,
    )
    assert response.status_code == 200, response.content
    audit_id = response.json()["result"]["audit_record_id"]
    body = client.get(f"/v1/evidence/{audit_id}", headers=headers).json()
    manifest = body["source_manifest"]
    assert manifest["status"] == "recorded"
    assert manifest["blocked"], "unlicensed registry sources must stay listed as blocked"
    assert codes.SOURCES_BLOCKED in body["limits"]["codes"]
    for item in manifest["records"]:
        if item["state"] == "blocked":
            assert item["blocked_reason"]


def test_another_organisations_audit_id_is_a_404_like_an_unknown_one(client):
    audit_id, _, _ = _run_demo(client, _org())
    other = _key(_org(), ["evidence:read"])
    for suffix in ("", "/verify", "/export"):
        foreign = client.get(f"/v1/evidence/{audit_id}{suffix}", headers=other)
        unknown = client.get(f"/v1/evidence/atr_{uuid4().hex}{suffix}", headers=other)
        assert foreign.status_code == unknown.status_code == 404
        assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == codes.NOT_FOUND


def _tamper(audit_id: str) -> None:
    async def _run() -> None:
        async with get_session_factory()() as session:
            row = await session.get(_model(), audit_id)
            payload = dict(row.payload)
            payload["outputs"] = {**payload["outputs"], "eal_absolute": 0.0}
            await session.execute(
                sa.update(_model()).where(_model().record_id == audit_id).values(payload=payload)
            )
            await session.commit()

    asyncio.run(_run())


def _model():
    from app.db.models import AuditTrailRecordModel

    return AuditTrailRecordModel


def test_broken_chain_is_reported_and_weakens_but_does_not_hide_evidence(client):
    audit_id, _, headers = _run_demo(client, _org())
    _tamper(audit_id)

    verify = client.get(f"/v1/evidence/{audit_id}/verify", headers=headers).json()
    assert verify["chain"] == "broken"
    assert verify["record_hash_valid"] is False

    evidence = client.get(f"/v1/evidence/{audit_id}", headers=headers)
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["integrity_status"] == "broken"
    assert body["integrity"]["record_hash_valid"] is False
    assert body["integrity"]["chain"]["status"] == "broken"
    assert codes.EVIDENCE_RECORD_HASH_MISMATCH in body["limits"]["codes"]
    assert codes.EVIDENCE_CHAIN_NOT_INTACT in body["limits"]["codes"]


def test_evidence_requires_the_evidence_scope(client):
    audit_id, _, _ = _run_demo(client, _org())
    response = client.get(f"/v1/evidence/{audit_id}", headers=_key(_org(), ["portfolio:read"]))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == codes.INSUFFICIENT_SCOPE


def test_evidence_refuses_without_a_database(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key_required", False)
    monkeypatch.setattr(settings, "database_url", None)
    response = client.get("/v1/evidence/atr_x")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == codes.AUDIT_STORE_UNAVAILABLE
