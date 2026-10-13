"""PostgreSQL-backed audit trail store (``audit_trail_records`` table, WP-2).

The product's defensibility claim rests on a hash-chained, append-only trail.
File-backed JSONL (``app.services.audit_trail``) is fine for local development
but is wiped by a container restart without a mounted volume (STUBS #20). This
store persists the same records to the database, using the *same* hashing
function so the two backends agree byte-for-byte.

The chain is per organisation: every organisation has its own genesis record,
its own tip, and its own links. ``(organisation_id, prev_hash)`` is unique, so a
concurrent append that chains off the same tip loses the race with an
``IntegrityError`` and is retried against the now-current tip.

``organisation_id`` is part of the hashed payload, not only a column. Without
that, rewriting the column on a whole chain would move it to another
organisation and the moved chain would still verify. With it, every record is
sealed to its owner, and :meth:`PostgresAuditTrailStore.verify_chain_report`
rejects a record whose sealed owner differs from the chain it sits in.

``source_commit`` (the deployed git SHA) and ``run_id`` (the run that produced
the record, ``None`` outside a run) are sealed the same way: a record names the
code and the run behind it (INV-05), and neither claim can be edited later.

Writes can join the caller's transaction (WP-3): :meth:`append` and
:meth:`persist_records` accept an ``AsyncSession`` and only flush, so a run row
and its audit records commit together or roll back together. Without a session
``append`` opens its own and commits.

``append`` does **not** re-verify the existing chain before linking a new
record: it costs a full chain read per write, and a broken chain is reported by
verification, never repaired by an append (INV-03). A record appended after a
tamper is therefore chained onto a broken link, and the chain stays ``broken``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import error_codes as codes
from app.db.models import AuditTrailRecordModel
from app.services.audit_trail import (
    GENESIS_PREV_HASH,
    AuditTrailRecord,
    compute_record_hash,
)

_MAX_APPEND_RETRIES = 8

#: Key under which the owning organisation is sealed into the hashed payload.
_ORG_KEY = "organisation_id"
#: Key under which the producing code revision is sealed into the hashed payload.
_COMMIT_KEY = "source_commit"
#: Key under which the run that produced a record is sealed (``None`` outside a run).
_RUN_KEY = "run_id"
#: Sealed keys that are not fields of :class:`AuditTrailRecord`.
_SEALED_KEYS = frozenset({_ORG_KEY, _COMMIT_KEY, _RUN_KEY})

UNKNOWN_SOURCE_COMMIT = "unknown"


def build_sealed_payload(
    *,
    organisation_id: str,
    source_commit: str,
    run_id: str | None,
    record_id: str,
    prev_hash: str,
    timestamp: datetime,
    methodology_version: str,
    valuation_date: date,
    data_versions: dict[str, str],
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The exact payload hashed and stored for one record (single definition).

    ``sources`` (the WP-4 source manifest) is included only when non-empty —
    the same rule as ``AuditTrailRecord.hash_payload`` on the file trail.
    """
    payload = {
        _ORG_KEY: organisation_id,
        _COMMIT_KEY: source_commit,
        _RUN_KEY: run_id,
        "record_id": record_id,
        "prev_hash": prev_hash,
        "timestamp": timestamp.isoformat(),
        "methodology_version": methodology_version,
        "data_versions": dict(data_versions),
        "parameters": dict(parameters),
        "valuation_date": valuation_date.isoformat(),
        "inputs": dict(inputs),
        "outputs": dict(outputs),
    }
    if sources:
        payload["sources"] = [dict(item) for item in sources]
    return payload


@dataclass(frozen=True)
class SealedRecord:
    """A record plus the exact payload its ``record_hash`` was computed over."""

    record: AuditTrailRecord
    payload: dict[str, Any]

    @property
    def organisation_id(self) -> str:
        return str(self.payload[_ORG_KEY])

    @property
    def run_id(self) -> str | None:
        value = self.payload.get(_RUN_KEY)
        return None if value is None else str(value)

    @property
    def source_commit(self) -> str:
        return str(self.payload.get(_COMMIT_KEY) or UNKNOWN_SOURCE_COMMIT)


def seal_record(
    *,
    organisation_id: str,
    source_commit: str,
    prev_hash: str,
    run_id: str | None = None,
    methodology_version: str,
    valuation_date: date,
    data_versions: dict[str, str],
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    timestamp: datetime | None = None,
    record_id: str | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> SealedRecord:
    ts = timestamp or datetime.now(timezone.utc)
    rid = record_id or f"atr_{uuid4().hex}"
    payload = build_sealed_payload(
        organisation_id=organisation_id, source_commit=source_commit, run_id=run_id, record_id=rid,
        prev_hash=prev_hash, timestamp=ts, methodology_version=methodology_version,
        valuation_date=valuation_date, data_versions=data_versions, parameters=parameters,
        inputs=inputs, outputs=outputs, sources=sources,
    )
    record = AuditTrailRecord(
        record_id=rid,
        prev_hash=prev_hash,
        record_hash=compute_record_hash(prev_hash, payload),
        timestamp=ts,
        methodology_version=methodology_version,
        data_versions=dict(data_versions),
        parameters=dict(parameters),
        valuation_date=valuation_date,
        inputs=dict(inputs),
        outputs=dict(outputs),
        sources=list(payload.get("sources") or []),
    )
    return SealedRecord(record=record, payload=payload)




class AuditChainError(RuntimeError):
    """The persisted chain is corrupt (branch, cycle, or orphaned record)."""


@dataclass(frozen=True)
class ChainVerification:
    """Outcome of verifying one organisation's chain.

    ``status`` is ``empty`` when the organisation has no records: an empty chain
    is not evidence of integrity and is never reported as ``intact``.
    """

    organisation_id: str
    status: Literal["intact", "broken", "empty"]
    records: int
    tip_hash: str | None
    reason: str | None = None
    record_id: str | None = None


class PostgresAuditTrailStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(
        self,
        *,
        organisation_id: str,
        methodology_version: str,
        valuation_date: date,
        data_versions: dict[str, str],
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        timestamp: datetime | None = None,
        source_commit: str = UNKNOWN_SOURCE_COMMIT,
        session: AsyncSession | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> AuditTrailRecord:
        """Append one record to ``organisation_id``'s chain.

        With ``session`` the record joins the caller's transaction: one attempt,
        flushed, not committed — a lost tip race surfaces as ``IntegrityError``
        on the caller's commit, and the caller retries the whole transaction.
        Without it the store commits on its own and retries a lost race.
        """
        ts = timestamp or datetime.now(timezone.utc)
        record_id = f"atr_{uuid4().hex}"
        fields = dict(
            organisation_id=organisation_id, source_commit=source_commit,
            methodology_version=methodology_version, valuation_date=valuation_date,
            data_versions=data_versions, parameters=parameters, inputs=inputs,
            outputs=outputs, timestamp=ts, record_id=record_id, sources=sources,
        )

        if session is not None:
            sealed = seal_record(prev_hash=await _tip_hash(session, organisation_id), **fields)
            await self.persist_records(session, organisation_id, [sealed])
            return sealed.record

        for _ in range(_MAX_APPEND_RETRIES):
            async with self._session_factory() as own:
                sealed = seal_record(prev_hash=await _tip_hash(own, organisation_id), **fields)
                own.add(_to_model(sealed))
                try:
                    await own.commit()
                    return sealed.record
                except IntegrityError:
                    await own.rollback()
                    continue

        raise AuditChainError(
            f"could not append audit record for {organisation_id!r} after "
            f"{_MAX_APPEND_RETRIES} attempts (concurrent writers?)"
        )

    async def tip_hash(self, organisation_id: str, *, session: AsyncSession | None = None) -> str:
        """Hash of the last link in ``organisation_id``'s chain (genesis if empty)."""
        if session is not None:
            return await _tip_hash(session, organisation_id)
        async with self._session_factory() as own:
            return await _tip_hash(own, organisation_id)

    async def persist_records(
        self, session: AsyncSession, organisation_id: str, records: list[SealedRecord]
    ) -> None:
        """Add pre-sealed records to ``session`` (flush only; the caller commits).

        The records must be one contiguous run of links, each sealed to
        ``organisation_id``. The first link must chain off the tip it was sealed
        against; if another writer moved the tip meanwhile, the unique
        ``(organisation_id, prev_hash)`` constraint rejects the flush or commit.
        """
        prev: str | None = None
        for sealed in records:
            if sealed.organisation_id != organisation_id:
                raise AuditChainError("sealed record belongs to another organisation")
            if compute_record_hash(sealed.record.prev_hash, sealed.payload) != sealed.record.record_hash:
                raise AuditChainError(f"sealed record {sealed.record.record_id} does not hash to its record_hash")
            if prev is not None and sealed.record.prev_hash != prev:
                raise AuditChainError("sealed records are not one contiguous chain segment")
            prev = sealed.record.record_hash
            session.add(_to_model(sealed))
        await session.flush()

    async def get(self, record_id: str, *, organisation_id: str) -> AuditTrailRecord | None:
        """Return ``record_id`` only if it belongs to ``organisation_id``.

        Another organisation's record is indistinguishable from a missing one,
        so a caller cannot probe for its existence.
        """
        async with self._session_factory() as session:
            row = await session.get(AuditTrailRecordModel, record_id)
            if row is None or row.organisation_id != organisation_id:
                return None
            return _row_to_record(row)

    async def get_sealed(self, record_id: str, *, organisation_id: str) -> SealedRecord | None:
        """Like :meth:`get`, plus the exact stored payload the hash covers."""
        async with self._session_factory() as session:
            row = await session.get(AuditTrailRecordModel, record_id)
            if row is None or row.organisation_id != organisation_id:
                return None
            return SealedRecord(record=_row_to_record(row), payload=dict(row.payload))

    async def records(self, organisation_id: str) -> list[AuditTrailRecord]:
        """Return the organisation's chain in chain order (genesis first)."""
        async with self._session_factory() as session:
            rows = await _load_chain(session, organisation_id)
            return [_row_to_record(row) for row in rows]

    async def verify_chain(self, organisation_id: str) -> bool:
        return (await self.verify_chain_report(organisation_id)).status == "intact"

    async def verify_chain_report(self, organisation_id: str) -> ChainVerification:
        """Recompute ``organisation_id``'s chain from its own genesis record.

        Only that organisation's rows are read, and each must carry the same
        sealed ``organisation_id`` inside its hashed payload.
        """
        try:
            async with self._session_factory() as session:
                rows = await _load_chain(session, organisation_id)
        except AuditChainError:
            return ChainVerification(organisation_id, "broken", 0, None, codes.AUDIT_CHAIN_STRUCTURE_BROKEN)

        if not rows:
            return ChainVerification(organisation_id, "empty", 0, None)

        prev = GENESIS_PREV_HASH
        for row in rows:
            payload = dict(row.payload)
            if row.prev_hash != prev or payload.get("prev_hash") != row.prev_hash:
                return ChainVerification(
                    organisation_id, "broken", len(rows), None, codes.AUDIT_CHAIN_LINK_MISMATCH, row.record_id
                )
            if compute_record_hash(row.prev_hash, payload) != row.record_hash:
                return ChainVerification(
                    organisation_id, "broken", len(rows), None, codes.AUDIT_CHAIN_HASH_MISMATCH, row.record_id
                )
            if payload.get(_ORG_KEY) != organisation_id:
                return ChainVerification(
                    organisation_id, "broken", len(rows), None, codes.AUDIT_CHAIN_OWNER_MISMATCH, row.record_id
                )
            prev = row.record_hash
        return ChainVerification(organisation_id, "intact", len(rows), prev)


def _row_to_record(row: AuditTrailRecordModel) -> AuditTrailRecord:
    payload = {k: v for k, v in dict(row.payload).items() if k not in _SEALED_KEYS}
    return AuditTrailRecord.model_validate({**payload, "record_hash": row.record_hash})


def _to_model(sealed: SealedRecord) -> AuditTrailRecordModel:
    return AuditTrailRecordModel(
        record_id=sealed.record.record_id,
        organisation_id=sealed.organisation_id,
        prev_hash=sealed.record.prev_hash,
        record_hash=sealed.record.record_hash,
        payload=sealed.payload,
        created_at=sealed.record.timestamp,
    )


async def _tip_hash(session: AsyncSession, organisation_id: str) -> str:
    """Hash of the last link in the organisation's chain (genesis if empty)."""
    referenced = select(AuditTrailRecordModel.prev_hash).where(
        AuditTrailRecordModel.organisation_id == organisation_id
    )
    result = await session.execute(
        select(AuditTrailRecordModel.record_hash).where(
            AuditTrailRecordModel.organisation_id == organisation_id,
            AuditTrailRecordModel.record_hash.notin_(referenced),
        )
    )
    tips = list(result.scalars().all())
    if not tips:
        return GENESIS_PREV_HASH
    if len(tips) > 1:
        raise AuditChainError(f"branched audit chain for {organisation_id!r}: {len(tips)} tips")
    return tips[0]


async def _load_chain(session: AsyncSession, organisation_id: str) -> list[AuditTrailRecordModel]:
    result = await session.execute(
        select(AuditTrailRecordModel).where(
            AuditTrailRecordModel.organisation_id == organisation_id
        )
    )
    rows = list(result.scalars().all())
    if not rows:
        return []

    by_prev = {row.prev_hash: row for row in rows}
    genesis = [row for row in rows if row.prev_hash == GENESIS_PREV_HASH]
    if len(genesis) != 1:
        raise AuditChainError(f"expected one genesis record for {organisation_id!r}, found {len(genesis)}")

    ordered: list[AuditTrailRecordModel] = []
    seen: set[str] = set()
    current: AuditTrailRecordModel | None = genesis[0]
    while current is not None:
        if current.record_hash in seen:
            raise AuditChainError(f"cycle in audit chain for {organisation_id!r}")
        seen.add(current.record_hash)
        ordered.append(current)
        current = by_prev.get(current.record_hash)

    if len(ordered) != len(rows):
        raise AuditChainError(f"orphaned records in audit chain for {organisation_id!r}")
    return ordered


__all__ = [
    "UNKNOWN_SOURCE_COMMIT",
    "AuditChainError",
    "ChainVerification",
    "PostgresAuditTrailStore",
    "SealedRecord",
    "build_sealed_payload",
    "seal_record",
]
