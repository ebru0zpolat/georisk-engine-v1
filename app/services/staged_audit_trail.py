"""In-memory staging trail for one database-backed run (WP-3 item 0).

The five-layer pipeline is synchronous and appends to a trail object as it goes
(``append`` / ``get`` / ``tip_hash`` / ``verify_chain`` / ``len``). The database
store is asynchronous. A run therefore appends to this staging trail first; the
records are sealed exactly as :class:`PostgresAuditTrailStore` seals them,
chained off the organisation's current database tip, and nothing reaches the
database until the run has finished. Then the run row and every staged record
are written in one transaction (``app.services.portfolio_run_service``).
Every staged record seals the run's ``run_id``, whichever pipeline path wrote
it, so the run row and its records are linked inside the hashed payload.

A run that raises leaves no records behind. A staged record is not evidence:
only a committed one is.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterator

from app.services.audit_trail import AuditTrailRecord, compute_record_hash
from app.storage.audit_trail_store import SealedRecord, seal_record


class StagedAuditTrail:
    def __init__(
        self, *, organisation_id: str, tip_hash: str, source_commit: str, run_id: str
    ) -> None:
        self.organisation_id = organisation_id
        self.source_commit = source_commit
        self.run_id = run_id
        self._base_tip = tip_hash
        self._sealed: list[SealedRecord] = []

    @property
    def path(self) -> None:
        return None

    @property
    def base_tip(self) -> str:
        """The database tip this segment was chained against."""
        return self._base_tip

    @property
    def tip_hash(self) -> str:
        return self._sealed[-1].record.record_hash if self._sealed else self._base_tip

    @property
    def sealed_records(self) -> list[SealedRecord]:
        return list(self._sealed)

    def append(
        self,
        *,
        methodology_version: str,
        valuation_date: date,
        data_versions: dict[str, str],
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        timestamp: datetime | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> AuditTrailRecord:
        sealed = seal_record(
            organisation_id=self.organisation_id,
            source_commit=self.source_commit,
            run_id=self.run_id,
            prev_hash=self.tip_hash,
            methodology_version=methodology_version,
            valuation_date=valuation_date,
            data_versions=data_versions,
            parameters=parameters,
            inputs=inputs,
            outputs=outputs,
            timestamp=timestamp,
            sources=sources,
        )
        self._sealed.append(sealed)
        return sealed.record

    def get(self, record_id: str) -> AuditTrailRecord | None:
        for sealed in self._sealed:
            if sealed.record.record_id == record_id:
                return sealed.record
        return None

    def verify_chain(self) -> bool:
        prev = self._base_tip
        for sealed in self._sealed:
            if sealed.record.prev_hash != prev:
                return False
            if compute_record_hash(prev, sealed.payload) != sealed.record.record_hash:
                return False
            prev = sealed.record.record_hash
        return True

    def __len__(self) -> int:
        return len(self._sealed)

    def __iter__(self) -> Iterator[AuditTrailRecord]:
        return iter([sealed.record for sealed in self._sealed])


__all__ = ["StagedAuditTrail"]
