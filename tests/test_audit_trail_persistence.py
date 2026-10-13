"""WP-2: hash-chained audit trail persisted in ``audit_trail_records``.

Covers the acceptance criteria: append → new process/store → the same record is
returned and the chain still verifies; the chain cannot branch or fork in the
table; and both the per-organisation chain and the global record-hash are unique.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models  # noqa: F401  (register tables on Base.metadata)
from app.db.base import Base
from app.db.models import AuditTrailRecordModel
from app.services.audit_trail import GENESIS_PREV_HASH, compute_record_hash
from app.storage.audit_trail_store import AuditChainError, PostgresAuditTrailStore

_TS = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


def _engine(db_path):
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}")


async def _create_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _append(store: PostgresAuditTrailStore, org: str, *, outputs: dict):
    return await store.append(
        organisation_id=org,
        methodology_version="eal-v0.1",
        valuation_date=date(2026, 1, 1),
        data_versions={"hazard": "v1"},
        parameters={"currency": "EUR"},
        inputs={"value": 1_000_000},
        outputs=outputs,
        timestamp=_TS,
    )


def test_append_survives_restart_and_verifies(tmp_path) -> None:
    db_path = tmp_path / "audit.db"

    async def _run() -> None:
        engine1 = _engine(db_path)
        await _create_schema(engine1)
        store1 = PostgresAuditTrailStore(async_sessionmaker(engine1, expire_on_commit=False))
        first = await _append(store1, "org-1", outputs={"eal": 1.0})
        second = await _append(store1, "org-1", outputs={"eal": 2.0})
        assert second.prev_hash == first.record_hash
        assert await store1.verify_chain("org-1") is True
        await engine1.dispose()

        # New engine/session factory == a fresh process against the same database.
        engine2 = _engine(db_path)
        store2 = PostgresAuditTrailStore(async_sessionmaker(engine2, expire_on_commit=False))
        reloaded = await store2.get(first.record_id, organisation_id="org-1")
        assert reloaded == first
        assert await store2.verify_chain("org-1") is True
        ordered = await store2.records("org-1")
        assert [rec.record_id for rec in ordered] == [first.record_id, second.record_id]
        await engine2.dispose()

    asyncio.run(_run())


def test_first_record_per_organisation_is_genesis(tmp_path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        a = await _append(store, "org-a", outputs={"eal": 1.0})
        b = await _append(store, "org-b", outputs={"eal": 1.0})
        assert a.prev_hash == GENESIS_PREV_HASH
        assert b.prev_hash == GENESIS_PREV_HASH
        assert await store.verify_chain("org-a") is True
        assert await store.verify_chain("org-b") is True
        await engine.dispose()

    asyncio.run(_run())


def test_tampered_payload_breaks_verification(tmp_path) -> None:
    db_path = tmp_path / "audit.db"

    async def _run() -> None:
        engine = _engine(db_path)
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        record = await _append(store, "org-1", outputs={"eal": 1.0})
        assert await store.verify_chain("org-1") is True

        tampered = {**record.hash_payload(), "outputs": {"eal": 999.0}}
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE audit_trail_records SET payload = :p WHERE record_id = :rid"),
                {"p": json.dumps(tampered), "rid": record.record_id},
            )
        assert await store.verify_chain("org-1") is False
        await engine.dispose()

    asyncio.run(_run())


def test_stored_hash_matches_recompute(tmp_path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        record = await _append(store, "org-1", outputs={"eal": 1.0})
        # Owner, producing commit and run are sealed into the hashed payload.
        expected = compute_record_hash(
            record.prev_hash,
            {
                "organisation_id": "org-1",
                "source_commit": "unknown",
                "run_id": None,
                **record.hash_payload(),
            },
        )
        assert record.record_hash == expected
        await engine.dispose()

    asyncio.run(_run())


def test_chain_cannot_branch_on_same_prev_hash(tmp_path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresAuditTrailStore(factory)
        first = await _append(store, "org-1", outputs={"eal": 1.0})

        # A second record claiming the same predecessor would fork the chain.
        async with factory() as session:
            session.add(
                AuditTrailRecordModel(
                    record_id="atr_fork",
                    organisation_id="org-1",
                    prev_hash=first.prev_hash,
                    record_hash="f" * 64,
                    payload={"bogus": True},
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def test_orphaned_record_is_reported_as_broken(tmp_path) -> None:
    db_path = tmp_path / "audit.db"

    async def _run() -> None:
        engine = _engine(db_path)
        await _create_schema(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresAuditTrailStore(factory)
        await _append(store, "org-1", outputs={"eal": 1.0})

        async with factory() as session:
            session.add(
                AuditTrailRecordModel(
                    record_id="atr_orphan",
                    organisation_id="org-1",
                    prev_hash="a" * 64,
                    record_hash="b" * 64,
                    payload={"bogus": True},
                )
            )
            await session.commit()

        with pytest.raises(AuditChainError):
            await store.records("org-1")
        assert await store.verify_chain("org-1") is False
        await engine.dispose()

    asyncio.run(_run())


def test_chains_are_independent_per_organisation(tmp_path) -> None:
    """Each organisation has its own genesis; tampering one leaves the other intact."""

    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        a1 = await _append(store, "org-a", outputs={"eal": 1.0})
        b1 = await _append(store, "org-b", outputs={"eal": 5.0})
        a2 = await _append(store, "org-a", outputs={"eal": 2.0})
        assert a1.prev_hash == GENESIS_PREV_HASH
        assert b1.prev_hash == GENESIS_PREV_HASH
        assert a2.prev_hash == a1.record_hash  # not b1: no global interleaving

        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE audit_trail_records SET record_hash = :h WHERE record_id = :rid"),
                {"h": "f" * 64, "rid": b1.record_id},
            )
        report_a = await store.verify_chain_report("org-a")
        report_b = await store.verify_chain_report("org-b")
        assert (report_a.status, report_a.records, report_a.tip_hash) == ("intact", 2, a2.record_hash)
        assert report_b.status == "broken"
        assert report_b.reason == "AUDIT_CHAIN_HASH_MISMATCH"
        await engine.dispose()

    asyncio.run(_run())


def test_chain_moved_to_another_organisation_does_not_verify(tmp_path) -> None:
    """Rewriting organisation_id on a whole chain is caught by the sealed owner."""

    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        await _append(store, "org-a", outputs={"eal": 1.0})
        await _append(store, "org-a", outputs={"eal": 2.0})
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE audit_trail_records SET organisation_id = 'org-c' WHERE organisation_id = 'org-a'")
            )
        report = await store.verify_chain_report("org-c")
        assert report.status == "broken"
        assert report.reason == "AUDIT_CHAIN_OWNER_MISMATCH"
        await engine.dispose()

    asyncio.run(_run())


def test_empty_chain_is_not_intact(tmp_path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        report = await store.verify_chain_report("org-none")
        assert report.status == "empty"
        assert await store.verify_chain("org-none") is False
        await engine.dispose()

    asyncio.run(_run())


def test_get_does_not_return_another_organisations_record(tmp_path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path / "audit.db")
        await _create_schema(engine)
        store = PostgresAuditTrailStore(async_sessionmaker(engine, expire_on_commit=False))
        record = await _append(store, "org-a", outputs={"eal": 1.0})
        assert await store.get(record.record_id, organisation_id="org-a") == record
        assert await store.get(record.record_id, organisation_id="org-b") is None
        await engine.dispose()

    asyncio.run(_run())
