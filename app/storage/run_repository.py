"""Persistence for portfolio runs (``runs`` table, WP-2).

One row per portfolio analysis, recording the partition between analyzed and
excluded assets and the methodology version used. WP-8 layers async status
(``queued`` / ``running`` / ``partial`` / ``complete`` / ``failed``) on top.

Not wired yet: no portfolio execution path calls :meth:`RunRepository.create_run`,
so the ``runs`` table stays empty in real use. WP-3 item 0 (a required acceptance
criterion) writes the run row and the database audit record for the same run in
one transaction — both commit or both roll back. ``create_run`` therefore only
flushes and leaves the commit to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RunModel


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    organisation_id: str
    portfolio_id: str | None
    valuation_date: date | None
    methodology_version: str
    analyzed_count: int
    excluded_count: int
    created_at: datetime


def new_run_id() -> str:
    return f"run_{uuid4().hex[:24]}"


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        *,
        organisation_id: str,
        methodology_version: str,
        portfolio_id: str | None = None,
        valuation_date: date | None = None,
        analyzed_count: int = 0,
        excluded_count: int = 0,
        run_id: str | None = None,
        created_at: datetime | None = None,
    ) -> RunRecord:
        model = RunModel(
            run_id=run_id or new_run_id(),
            organisation_id=organisation_id,
            portfolio_id=portfolio_id,
            valuation_date=valuation_date,
            methodology_version=methodology_version,
            analyzed_count=analyzed_count,
            excluded_count=excluded_count,
            created_at=created_at or datetime.now(timezone.utc),
        )
        self.session.add(model)
        await self.session.flush()
        return _to_record(model)

    async def get_run(self, run_id: str, *, organisation_id: str) -> RunRecord | None:
        result = await self.session.execute(
            select(RunModel).where(
                RunModel.run_id == run_id,
                RunModel.organisation_id == organisation_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_record(row) if row is not None else None

    async def list_runs(self, *, organisation_id: str) -> list[RunRecord]:
        result = await self.session.execute(
            select(RunModel)
            .where(RunModel.organisation_id == organisation_id)
            .order_by(RunModel.created_at.desc())
        )
        return [_to_record(row) for row in result.scalars().all()]


def _to_record(row: RunModel) -> RunRecord:
    return RunRecord(
        run_id=row.run_id,
        organisation_id=row.organisation_id,
        portfolio_id=row.portfolio_id,
        valuation_date=row.valuation_date,
        methodology_version=row.methodology_version,
        analyzed_count=row.analyzed_count,
        excluded_count=row.excluded_count,
        created_at=row.created_at,
    )


__all__ = ["RunRecord", "RunRepository", "new_run_id"]
