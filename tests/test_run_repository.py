"""WP-2: portfolio runs are recorded in the ``runs`` table."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401  (register tables on Base.metadata)
from app.db.base import Base
from app.storage.run_repository import RunRepository


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


def test_create_and_load_run(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            repo = RunRepository(session)
            created = await repo.create_run(
                organisation_id="org-1",
                portfolio_id="portfolio-a",
                valuation_date=date(2026, 1, 1),
                methodology_version="eal-v0.1",
                analyzed_count=48,
                excluded_count=2,
            )
            await session.commit()
        async with session_factory() as session:
            loaded = await RunRepository(session).get_run(created.run_id, organisation_id="org-1")
            assert loaded is not None
            assert loaded.run_id == created.run_id
            assert loaded.portfolio_id == "portfolio-a"
            assert loaded.valuation_date == date(2026, 1, 1)
            assert loaded.methodology_version == "eal-v0.1"
            assert loaded.analyzed_count == 48
            assert loaded.excluded_count == 2

    asyncio.run(_run())


def test_run_is_scoped_to_organisation(session_factory) -> None:
    async def _run() -> None:
        async with session_factory() as session:
            created = await RunRepository(session).create_run(
                organisation_id="org-1", methodology_version="eal-v0.1"
            )
            await session.commit()
        async with session_factory() as session:
            repo = RunRepository(session)
            assert await repo.get_run(created.run_id, organisation_id="org-2") is None
            assert await repo.list_runs(organisation_id="org-2") == []

    asyncio.run(_run())
