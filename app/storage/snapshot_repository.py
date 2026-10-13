"""Persistence for asset snapshots (``asset_snapshots`` table, WP-2).

Two access paths share one mapping:

* :class:`SnapshotRepository` — async, session-per-request, used by the API and
  the test suite.
* :class:`SqlAlchemySnapshotBackend` — a synchronous backend that implements the
  ``app.services.asset_snapshot_store`` backend protocol, so the sync scoring
  path (``register_snapshot``) can be backed by the database without an async
  refactor. Selected with ``SNAPSHOT_STORE_BACKEND=db``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import DEFAULT_ORGANISATION_ID
from app.db.models import AssetSnapshotModel
from app.services.asset_snapshot_store import AssetSnapshot

_SNAPSHOT_FIELDS = (
    "asset_name",
    "latitude",
    "longitude",
    "radius_km",
    "sector",
    "overall_score",
    "components",
    "model_version",
    "data_snapshot_id",
    "asset_geometry_hash",
    "uses_connector_fallback",
)


def snapshot_columns(snapshot: AssetSnapshot, organisation_id: str) -> dict[str, Any]:
    columns = {field: getattr(snapshot, field) for field in _SNAPSHOT_FIELDS}
    columns["components"] = dict(snapshot.components)
    columns["audit_id"] = snapshot.audit_id
    columns["organisation_id"] = organisation_id
    return columns


def row_to_snapshot(row: AssetSnapshotModel) -> AssetSnapshot:
    return AssetSnapshot(
        audit_id=row.audit_id,
        asset_name=row.asset_name,
        latitude=row.latitude,
        longitude=row.longitude,
        radius_km=row.radius_km,
        sector=row.sector,
        overall_score=row.overall_score,
        components=dict(row.components or {}),
        model_version=row.model_version,
        data_snapshot_id=row.data_snapshot_id,
        asset_geometry_hash=row.asset_geometry_hash or "",
        uses_connector_fallback=bool(row.uses_connector_fallback),
    )


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, snapshot: AssetSnapshot, *, organisation_id: str) -> AssetSnapshot:
        """Insert or replace the snapshot identified by ``audit_id``."""
        model = AssetSnapshotModel(**snapshot_columns(snapshot, organisation_id))
        await self.session.merge(model)
        await self.session.flush()
        return snapshot

    async def get(self, audit_id: str, *, organisation_id: str) -> AssetSnapshot | None:
        result = await self.session.execute(
            select(AssetSnapshotModel).where(
                AssetSnapshotModel.audit_id == audit_id,
                AssetSnapshotModel.organisation_id == organisation_id,
            )
        )
        row = result.scalar_one_or_none()
        return row_to_snapshot(row) if row is not None else None

    async def list_snapshots(self, *, organisation_id: str) -> list[AssetSnapshot]:
        result = await self.session.execute(
            select(AssetSnapshotModel)
            .where(AssetSnapshotModel.organisation_id == organisation_id)
            .order_by(AssetSnapshotModel.created_at.desc())
        )
        return [row_to_snapshot(row) for row in result.scalars().all()]

    async def delete_all(self, *, organisation_id: str | None = None) -> int:
        query = delete(AssetSnapshotModel)
        if organisation_id is not None:
            query = query.where(AssetSnapshotModel.organisation_id == organisation_id)
        result = await self.session.execute(query)
        await self.session.flush()
        return int(result.rowcount or 0)


def sync_database_url(url: str | None) -> str:
    """Map an async SQLAlchemy URL onto its synchronous driver.

    ``sqlite+aiosqlite`` → ``sqlite`` (pysqlite, stdlib); ``postgresql+asyncpg``
    → ``postgresql+psycopg`` (requires the ``psycopg`` driver at deploy time).
    """
    if not url:
        raise RuntimeError("SNAPSHOT_STORE_BACKEND=db requires DATABASE_URL")
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


class SqlAlchemySnapshotBackend:
    """Synchronous DB backend for ``app.services.asset_snapshot_store``.

    Owns a private sync engine so the scoring path never touches the async
    request-scoped session. The table is expected to exist (created by Alembic);
    ``create`` is idempotent so an un-migrated dev database still works.
    """

    def __init__(self, url: str | None = None) -> None:
        from sqlalchemy import create_engine

        self._url = sync_database_url(url if url is not None else settings.database_url)
        connect_args = {"check_same_thread": False} if self._url.startswith("sqlite") else {}
        self._engine = create_engine(self._url, connect_args=connect_args)
        AssetSnapshotModel.__table__.create(bind=self._engine, checkfirst=True)

    def register(self, snapshot: AssetSnapshot) -> None:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        with Session(self._engine) as session:
            existing = session.execute(
                select(AssetSnapshotModel).where(AssetSnapshotModel.audit_id == snapshot.audit_id)
            ).scalar_one_or_none()
            columns = snapshot_columns(snapshot, DEFAULT_ORGANISATION_ID)
            if existing is None:
                session.add(AssetSnapshotModel(**columns))
            else:
                for key, value in columns.items():
                    setattr(existing, key, value)
            session.commit()

    def get(self, audit_id: str) -> AssetSnapshot | None:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        with Session(self._engine) as session:
            row = session.execute(
                select(AssetSnapshotModel).where(AssetSnapshotModel.audit_id == audit_id)
            ).scalar_one_or_none()
            return row_to_snapshot(row) if row is not None else None

    def clear(self) -> None:
        from sqlalchemy import delete as sa_delete
        from sqlalchemy.orm import Session

        with Session(self._engine) as session:
            session.execute(sa_delete(AssetSnapshotModel))
            session.commit()

    def count(self) -> int:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        with Session(self._engine) as session:
            return int(session.execute(select(func.count()).select_from(AssetSnapshotModel)).scalar_one())


__all__ = [
    "SnapshotRepository",
    "SqlAlchemySnapshotBackend",
    "row_to_snapshot",
    "snapshot_columns",
    "sync_database_url",
]
