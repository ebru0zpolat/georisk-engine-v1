"""WP-2: asset snapshots survive a restart via the ``asset_snapshots`` table."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401  (register tables on Base.metadata)
from app.db.base import Base
from app.services.asset_snapshot_store import AssetSnapshot
from app.storage.snapshot_repository import SnapshotRepository, SqlAlchemySnapshotBackend


def _snapshot(audit_id: str, *, score: int = 42, name: str = "asset") -> AssetSnapshot:
    return AssetSnapshot(
        audit_id=audit_id,
        asset_name=name,
        latitude=52.37,
        longitude=4.89,
        radius_km=10.0,
        sector="industry",
        overall_score=score,
        components={"flood": 50, "heat": 30},
        model_version="risk-score-v0.1",
        data_snapshot_id="hazard_layers_2026_05",
        asset_geometry_hash="deadbeef",
        uses_connector_fallback=False,
    )


@pytest.fixture
def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


def test_save_then_get_returns_same_snapshot(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            await SnapshotRepository(session).save(_snapshot("aud-1"), organisation_id="org-1")
            await session.commit()
        async with session_factory() as session:
            got = await SnapshotRepository(session).get("aud-1", organisation_id="org-1")
            assert got == _snapshot("aud-1")

    asyncio.run(_run())


def test_get_is_scoped_to_organisation(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            await SnapshotRepository(session).save(_snapshot("aud-1"), organisation_id="org-1")
            await session.commit()
        async with session_factory() as session:
            repo = SnapshotRepository(session)
            assert await repo.get("aud-1", organisation_id="org-2") is None

    asyncio.run(_run())


def test_list_only_returns_caller_organisation(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            repo = SnapshotRepository(session)
            await repo.save(_snapshot("aud-1", name="one"), organisation_id="org-1")
            await repo.save(_snapshot("aud-2", name="two"), organisation_id="org-1")
            await repo.save(_snapshot("aud-3", name="three"), organisation_id="org-2")
            await session.commit()
        async with session_factory() as session:
            rows = await SnapshotRepository(session).list_snapshots(organisation_id="org-1")
            assert {row.audit_id for row in rows} == {"aud-1", "aud-2"}

    asyncio.run(_run())


def test_save_replaces_existing_audit_id(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            repo = SnapshotRepository(session)
            await repo.save(_snapshot("aud-1", score=42), organisation_id="org-1")
            await repo.save(_snapshot("aud-1", score=99), organisation_id="org-1")
            await session.commit()
        async with session_factory() as session:
            got = await SnapshotRepository(session).get("aud-1", organisation_id="org-1")
            assert got is not None and got.overall_score == 99
            assert await SnapshotRepository(session).delete_all(organisation_id="org-1") == 1

    asyncio.run(_run())


def test_sync_backend_persists_across_instances(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'snapshots.db'}"
    backend = SqlAlchemySnapshotBackend(url)
    backend.register(_snapshot("aud-persist"))
    assert backend.get("aud-persist") == _snapshot("aud-persist")

    reopened = SqlAlchemySnapshotBackend(url)
    assert reopened.get("aud-persist") == _snapshot("aud-persist")
    assert reopened.count() == 1

    reopened.clear()
    assert reopened.count() == 0
    assert reopened.get("aud-persist") is None


def test_async_postgres_url_maps_to_an_installed_sync_driver() -> None:
    """SNAPSHOT_STORE_BACKEND=db with the documented asyncpg URL must not fail on import."""
    from sqlalchemy import create_engine

    from app.storage.snapshot_repository import sync_database_url

    url = sync_database_url("postgresql+asyncpg://user:pw@localhost:5432/db")
    assert url.startswith("postgresql+psycopg://")
    engine = create_engine(url)  # loads the dialect + driver module; does not connect
    assert engine.dialect.driver == "psycopg"


@pytest.mark.parametrize(
    ("explicit", "database_url", "expected"),
    [
        (None, "postgresql+asyncpg://u:p@h/db", "db"),
        (None, None, "memory"),
        ("memory", "postgresql+asyncpg://u:p@h/db", "memory"),
        ("db", None, "db"),
    ],
)
def test_snapshot_backend_defaults_to_db_when_a_database_is_configured(
    monkeypatch: pytest.MonkeyPatch, explicit, database_url, expected
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "snapshot_store_backend", explicit)
    monkeypatch.setattr(settings, "database_url", database_url)
    assert settings.effective_snapshot_store_backend == expected
