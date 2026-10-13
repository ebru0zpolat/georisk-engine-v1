"""WP-3 item 0: a run row and its audit records are persisted together or not at all.

Invariant: a successful run's ``runs`` row and its database audit records commit
in one transaction; if either write fails, both roll back. Every record is
sealed with the run's ``run_id`` and the caller's organisation.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import error_codes as codes
from app.core.config import settings
from app.db import models  # noqa: F401  (register tables on Base.metadata)
from app.db.base import Base
from app.db.models import AuditTrailRecordModel, RunModel
from app.db.session import get_session_factory
from app.services.api_key_service import create_api_key
from app.services.portfolio_run_service import (
    RunPersistenceError,
    RunSummary,
    execute_persisted_run,
)
from app.storage.audit_trail_store import PostgresAuditTrailStore
from app.storage.run_repository import RunRepository

_DEMO_RUN = "/v1/portfolio/demo-run/golden-antalya?max_assets=2"


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


def _rows(organisation: str) -> tuple[list[AuditTrailRecordModel], list[RunModel]]:
    async def _run():
        async with get_session_factory()() as session:
            audit = (
                await session.execute(
                    sa.select(AuditTrailRecordModel).where(
                        AuditTrailRecordModel.organisation_id == organisation
                    )
                )
            ).scalars().all()
            runs = (
                await session.execute(sa.select(RunModel).where(RunModel.organisation_id == organisation))
            ).scalars().all()
            return list(audit), list(runs)

    return asyncio.run(_run())


@pytest.mark.usefixtures("_require_api_key")
def test_demo_run_persists_run_row_and_sealed_audit_records(client):
    org = _org()
    response = client.post(_DEMO_RUN, json={}, headers=_key(org, ["portfolio:write"]))
    assert response.status_code == 200, response.content
    body = response.json()
    run_id = body["run_id"]
    assert run_id

    audit, runs = _rows(org)
    assert [run.run_id for run in runs] == [run_id]
    assert runs[0].analyzed_count == body["narrative"]["asset_count"]
    assert runs[0].portfolio_id == body["narrative"]["portfolio_id"]
    assert audit, "a persisted run must have audit records"
    assert {row.payload["run_id"] for row in audit} == {run_id}
    assert {row.payload["organisation_id"] for row in audit} == {org}
    stored_ids = {row.record_id for row in audit}
    for asset in body["narrative"]["assets"]:
        assert asset["eal_audit_record_id"] in stored_ids
    assert body["narrative"]["verification"]["trail_record_id"] in stored_ids
    report = asyncio.run(PostgresAuditTrailStore(get_session_factory()).verify_chain_report(org))
    assert report.status == "intact"


@pytest.mark.usefixtures("_require_api_key")
def test_run_row_failure_rolls_back_audit_records(client, monkeypatch):
    org = _org()
    headers = _key(org, ["portfolio:write"])

    async def _fail(self, **kwargs):
        raise RuntimeError("injected run-row failure")

    monkeypatch.setattr(RunRepository, "create_run", _fail)
    response = client.post(_DEMO_RUN, json={}, headers=headers)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == codes.RUN_PERSISTENCE_FAILED
    audit, runs = _rows(org)
    assert audit == [] and runs == []


@pytest.mark.usefixtures("_require_api_key")
def test_audit_failure_after_partial_write_rolls_back_run_row(client, monkeypatch):
    org = _org()
    headers = _key(org, ["portfolio:write"])
    original = PostgresAuditTrailStore.persist_records

    async def _partial_then_fail(self, session, organisation_id, records):
        await original(self, session, organisation_id, records[:1])  # one record flushed
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(PostgresAuditTrailStore, "persist_records", _partial_then_fail)
    response = client.post(_DEMO_RUN, json={}, headers=headers)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == codes.RUN_PERSISTENCE_FAILED
    audit, runs = _rows(org)
    assert audit == [] and runs == []


@pytest.mark.usefixtures("_require_api_key")
def test_audit_failure_after_run_row_rolls_back_both(client, monkeypatch):
    """The run row is written first here; a later audit failure must undo it too."""
    org = _org()
    headers = _key(org, ["portfolio:write"])
    original_create = RunRepository.create_run
    original_persist = PostgresAuditTrailStore.persist_records
    calls: list[str] = []

    async def _persist_after_run_row(self, session, organisation_id, records):
        await original_create(
            RunRepository(session), organisation_id=organisation_id, methodology_version="x",
            run_id=f"run_injected_{uuid4().hex[:8]}",
        )
        calls.append("run-row-written")
        await original_persist(self, session, organisation_id, records)
        raise RuntimeError("injected audit failure after run row")

    monkeypatch.setattr(PostgresAuditTrailStore, "persist_records", _persist_after_run_row)
    response = client.post(_DEMO_RUN, json={}, headers=headers)
    assert response.status_code == 500
    assert calls == ["run-row-written"]
    audit, runs = _rows(org)
    assert audit == [] and runs == []


def _file_engine(tmp_path):
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")


async def _schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _compute(trail):
    trail.append(
        methodology_version="test-v1",
        valuation_date=date(2026, 1, 1),
        data_versions={"hazard": "v1"},
        parameters={},
        inputs={"x": 1},
        outputs={"y": 2},
    )
    return "ok", RunSummary(methodology_version="test-v1", analyzed_count=1)


def test_lost_tip_race_recomputes_against_the_new_tip(tmp_path) -> None:
    async def _run() -> None:
        engine = _file_engine(tmp_path)
        await _schema(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresAuditTrailStore(factory)
        attempts = {"n": 0}

        def compute(trail):
            attempts["n"] += 1
            if attempts["n"] == 1:
                # A concurrent writer moves the tip while this run computes.
                asyncio.run_coroutine_threadsafe(
                    store.append(
                        organisation_id="org-race", methodology_version="other", valuation_date=date(2026, 1, 1),
                        data_versions={}, parameters={}, inputs={}, outputs={},
                    ),
                    loop,
                ).result()
            return _compute(trail)

        loop = asyncio.get_running_loop()
        persisted = await execute_persisted_run(
            organisation_id="org-race", compute=compute, session_factory=factory
        )
        assert attempts["n"] == 2
        report = await store.verify_chain_report("org-race")
        assert (report.status, report.records) == ("intact", 2)
        async with factory() as session:
            runs = await RunRepository(session).list_runs(organisation_id="org-race")
        assert [run.run_id for run in runs] == [persisted.run_id]
        await engine.dispose()

    asyncio.run(_run())


def test_run_without_audit_record_is_refused(tmp_path) -> None:
    async def _run() -> None:
        engine = _file_engine(tmp_path)
        await _schema(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        with pytest.raises(RunPersistenceError) as excinfo:
            await execute_persisted_run(
                organisation_id="org-empty",
                compute=lambda trail: ("ok", RunSummary(methodology_version="x", analyzed_count=0)),
                session_factory=factory,
            )
        assert excinfo.value.code == codes.RUN_WITHOUT_AUDIT_RECORD
        async with factory() as session:
            assert await RunRepository(session).list_runs(organisation_id="org-empty") == []
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.parametrize("app_env", ["production", "demo"])
def test_deployed_runtime_without_database_refuses_runs(monkeypatch, app_env) -> None:
    from app.api.portfolio import _execute_run
    from app.core.exceptions import GeoRiskApiError
    from app.core.security import local_principal

    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(GeoRiskApiError) as excinfo:
        asyncio.run(_execute_run(local_principal(), _compute))
    assert excinfo.value.code == codes.AUDIT_STORE_UNAVAILABLE


def test_run_onto_a_branched_chain_is_refused_with_a_code(tmp_path) -> None:
    """Two records chained off the same genesis give two tips: refuse, named."""

    async def _run() -> None:
        engine = _file_engine(tmp_path)
        await _schema(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresAuditTrailStore(factory)
        await store.append(
            organisation_id="org-branch", methodology_version="a", valuation_date=date(2026, 1, 1),
            data_versions={}, parameters={}, inputs={}, outputs={},
        )
        async with engine.begin() as conn:  # forge a second genesis-linked tip
            await conn.execute(
                sa.text(
                    "INSERT INTO audit_trail_records "
                    "(record_id, organisation_id, prev_hash, record_hash, payload, created_at) "
                    "VALUES ('atr_forged', 'org-branch', :prev, :hash, '{}', CURRENT_TIMESTAMP)"
                ),
                {"prev": "1" * 64, "hash": "2" * 64},
            )
        with pytest.raises(RunPersistenceError) as excinfo:
            await execute_persisted_run(
                organisation_id="org-branch", compute=_compute, session_factory=factory
            )
        assert excinfo.value.code == codes.AUDIT_CHAIN_STRUCTURE_BROKEN
        async with factory() as session:
            assert await RunRepository(session).list_runs(organisation_id="org-branch") == []
        await engine.dispose()

    asyncio.run(_run())


def test_export_is_byte_identical_across_requests(client, monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "api_key_required", True)
    org = _org()
    headers = _key(org, ["portfolio:write", "evidence:read"])
    body = client.post(_DEMO_RUN, json={}, headers=headers).json()
    audit_id = body["narrative"]["assets"][0]["eal_audit_record_id"]
    first = client.get(f"/v1/evidence/{audit_id}/export", headers=headers).content
    second = client.get(f"/v1/evidence/{audit_id}/export", headers=headers).content
    assert first == second
