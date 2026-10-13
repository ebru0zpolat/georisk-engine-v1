"""Persist a portfolio run and its audit records together (WP-3 item 0).

``RunRepository`` and ``PostgresAuditTrailStore`` hold two pieces of evidence
for the same run. They are never written independently:

1. Open a session and read the organisation's chain tip.
2. Run the (synchronous) computation against a :class:`StagedAuditTrail`
   chained off that tip. The trail seals the run's ``run_id`` into every
   record's hashed payload, which is what links the records to the run row.
3. In the same transaction, add every staged record and the run row, then
   commit. Any failure rolls back both — no run row without its audit records,
   no audit record without its run row.

If another writer moved the tip between steps 1 and 3, the unique
``(organisation_id, prev_hash)`` constraint rejects the commit; the whole run is
recomputed against the new tip, because staged hashes chain off the old one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Generic, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core import error_codes as codes
from app.services.staged_audit_trail import StagedAuditTrail
from app.storage.audit_trail_store import (
    UNKNOWN_SOURCE_COMMIT,
    AuditChainError,
    PostgresAuditTrailStore,
)
from app.storage.run_repository import RunRepository, new_run_id

T = TypeVar("T")

_MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class RunSummary:
    """What the run row records about a computation."""

    methodology_version: str
    analyzed_count: int
    excluded_count: int = 0
    portfolio_id: str | None = None
    valuation_date: date | None = None


@dataclass(frozen=True)
class PersistedRun(Generic[T]):
    run_id: str
    result: T
    audit_record_ids: list[str] = field(default_factory=list)


class RunPersistenceError(RuntimeError):
    """The run was not persisted; nothing from it was committed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


Compute = Callable[[StagedAuditTrail], tuple[T, RunSummary]]


async def execute_persisted_run(
    *,
    organisation_id: str,
    compute: Compute[T],
    session_factory: async_sessionmaker[AsyncSession],
    source_commit: str | None = None,
    store: PostgresAuditTrailStore | None = None,
    run_repository: Callable[[AsyncSession], RunRepository] = RunRepository,
    max_attempts: int = _MAX_ATTEMPTS,
) -> PersistedRun[T]:
    """Run ``compute(trail)`` and commit its run row + audit records atomically.

    ``compute`` appends its audit records to the trail it is given. Errors from
    ``compute`` itself propagate unchanged (nothing has been written yet).
    """
    store = store or PostgresAuditTrailStore(session_factory)
    commit_sha = source_commit or UNKNOWN_SOURCE_COMMIT

    for _ in range(max_attempts):
        run_id = new_run_id()
        async with session_factory() as session:
            try:
                tip = await store.tip_hash(organisation_id, session=session)
            except AuditChainError as exc:
                # A branched chain has no single tip: nothing can be linked to it,
                # and appending would not repair it (INV-03). Refuse, named.
                raise RunPersistenceError(
                    codes.AUDIT_CHAIN_STRUCTURE_BROKEN,
                    "The organisation's audit chain is structurally broken; no run can be linked to it.",
                ) from exc
            trail = StagedAuditTrail(
                organisation_id=organisation_id, tip_hash=tip, source_commit=commit_sha, run_id=run_id
            )
            result, summary = await run_in_threadpool(compute, trail)
            sealed = trail.sealed_records
            if not sealed:
                await session.rollback()
                raise RunPersistenceError(
                    codes.RUN_WITHOUT_AUDIT_RECORD,
                    "The run produced no audit record, so it cannot be persisted as evidence.",
                )
            try:
                await store.persist_records(session, organisation_id, sealed)
                await run_repository(session).create_run(
                    organisation_id=organisation_id,
                    run_id=run_id,
                    methodology_version=summary.methodology_version,
                    portfolio_id=summary.portfolio_id,
                    valuation_date=summary.valuation_date,
                    analyzed_count=summary.analyzed_count,
                    excluded_count=summary.excluded_count,
                )
                await session.commit()
            except IntegrityError:
                # Lost the tip race (or a duplicate id): nothing was committed.
                await session.rollback()
                continue
            except Exception as exc:
                await session.rollback()
                raise RunPersistenceError(
                    codes.RUN_PERSISTENCE_FAILED,
                    "The run and its audit records were rolled back together.",
                ) from exc
            return PersistedRun(
                run_id=run_id,
                result=result,
                audit_record_ids=[item.record.record_id for item in sealed],
            )

    raise RunPersistenceError(
        codes.AUDIT_CHAIN_CONTENDED,
        f"Could not link the run to the audit chain after {max_attempts} attempts.",
    )


__all__ = [
    "PersistedRun",
    "RunPersistenceError",
    "RunSummary",
    "execute_persisted_run",
]
