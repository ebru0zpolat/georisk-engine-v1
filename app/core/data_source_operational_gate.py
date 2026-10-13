"""The ``data_source_operational`` readiness gate (roadmap §1).

The data-source registry + ``delivery_mode_for`` already track whether a
connector is wired to **live** credentials (vs a fallback/mock/stub). That is
necessary but **not sufficient** for the production readiness state
``data_source_operational``, which the roadmap defines as:

    "Required source connector has verified **licence**, **live runtime
    evidence**, **provenance** and **retention** controls."

This module turns those four controls into a fail-closed verdict. A source is
``operational=True`` only when:

1. its delivery mode is ``live`` (real credentials configured);
2. a commercial-use **licence** is on file and in effect;
3. at least one recent **live-runtime evidence** sample exists, captured from a
   real live call and fingerprinted (provenance hash);
4. a **retention** policy is declared (positive horizon + storage location).

Anything missing leaves ``operational=False`` with the reason named. A connector
that merely *could* run live (credentials present) but has no licence, no
captured live evidence, or no retention policy is **not** operational — the same
discipline the model-validation gate applies to ``model_validated_for_use_case``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

DEFAULT_MAX_EVIDENCE_AGE_DAYS = 90


def _is_sha256_hex(value: str) -> bool:
    """True iff ``value`` is exactly 64 hexadecimal characters."""
    v = value.strip().lower()
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


@dataclass(frozen=True)
class LicenceRecord:
    """A commercial-use licence for a source dataset."""

    source_id: str
    licence_id: str
    licensor: str
    commercial_use: bool
    valid_from: date
    valid_until: date | None = None  # None = perpetual
    document_ref: str = ""


@dataclass(frozen=True)
class LiveRuntimeEvidence:
    """Proof of one real live fetch from the source, with provenance."""

    source_id: str
    captured_at: date
    request_ref: str
    sample_sha256: str
    delivery_mode: str  # must be "live" to count


@dataclass(frozen=True)
class RetentionPolicy:
    """Declared retention controls for a source's captured data."""

    source_id: str
    retention_days: int
    storage_location: str
    policy_ref: str = ""


@dataclass(frozen=True)
class DataSourceOperationalVerdict:
    """Fail-closed verdict for ``data_source_operational`` on one source."""

    operational: bool
    source_id: str
    delivery_mode: str
    licence_ok: bool
    live_evidence_ok: bool
    retention_ok: bool
    reasons: list[str] = field(default_factory=list)
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operational": self.operational,
            "source_id": self.source_id,
            "delivery_mode": self.delivery_mode,
            "licence_ok": self.licence_ok,
            "live_evidence_ok": self.live_evidence_ok,
            "retention_ok": self.retention_ok,
            "reasons": list(self.reasons),
            "evaluated_at": self.evaluated_at,
        }


def evaluate_data_source_operational(
    *,
    source_id: str,
    delivery_mode: str,
    licence: LicenceRecord | None,
    live_evidence: list[LiveRuntimeEvidence] | None,
    retention: RetentionPolicy | None,
    as_of: date,
    max_evidence_age_days: int = DEFAULT_MAX_EVIDENCE_AGE_DAYS,
    evaluated_at: str | None = None,
) -> DataSourceOperationalVerdict:
    """Decide ``data_source_operational`` for one source (fail-closed)."""
    reasons: list[str] = []

    if delivery_mode != "live":
        reasons.append(
            f"delivery_mode is {delivery_mode!r}, not 'live' — the connector is "
            "not configured with live credentials"
        )

    # --- licence ---
    licence_ok = False
    if licence is None:
        reasons.append("no commercial-use licence record on file")
    elif licence.source_id != source_id:
        reasons.append(
            f"licence record is for {licence.source_id!r}, not {source_id!r}"
        )
    elif not licence.commercial_use:
        reasons.append("licence does not grant commercial use")
    elif licence.valid_from > as_of:
        reasons.append(f"licence is not yet in effect (valid_from {licence.valid_from})")
    elif licence.valid_until is not None and licence.valid_until < as_of:
        reasons.append(f"licence expired on {licence.valid_until}")
    else:
        licence_ok = True

    # --- live runtime evidence (with provenance) ---
    live_evidence_ok = False
    relevant = [
        e for e in (live_evidence or [])
        if e.source_id == source_id and e.delivery_mode == "live"
    ]
    if not relevant:
        reasons.append(
            "no live-runtime evidence: a real live fetch must be captured with a "
            "provenance hash (delivery_mode='live')"
        )
    else:
        def _valid(e: LiveRuntimeEvidence) -> bool:
            # Age must be within [0, max]: a future-dated capture (negative age)
            # is not evidence that existed at evaluation time.
            age = (as_of - e.captured_at).days
            return 0 <= age <= max_evidence_age_days and _is_sha256_hex(e.sample_sha256)

        # At least ONE recent, correctly fingerprinted sample suffices — a later
        # incomplete record must not disqualify a valid one.
        if any(_valid(e) for e in relevant):
            live_evidence_ok = True
        else:
            fresh = [
                e for e in relevant
                if 0 <= (as_of - e.captured_at).days <= max_evidence_age_days
            ]
            if not fresh:
                reasons.append(
                    "no live-runtime evidence within "
                    f"[0, {max_evidence_age_days}] days (stale or future-dated)"
                )
            else:
                reasons.append(
                    "no fresh live-runtime evidence carries a valid SHA-256 "
                    "provenance hash (64 hex chars)"
                )

    # --- retention controls ---
    retention_ok = False
    if retention is None:
        reasons.append("no retention policy declared")
    elif retention.source_id != source_id:
        reasons.append(
            f"retention policy is for {retention.source_id!r}, not {source_id!r}"
        )
    elif retention.retention_days <= 0:
        reasons.append("retention policy has non-positive retention_days")
    elif not retention.storage_location.strip():
        reasons.append("retention policy has no storage_location")
    else:
        retention_ok = True

    return DataSourceOperationalVerdict(
        operational=not reasons,
        source_id=source_id,
        delivery_mode=delivery_mode,
        licence_ok=licence_ok,
        live_evidence_ok=live_evidence_ok,
        retention_ok=retention_ok,
        reasons=reasons,
        evaluated_at=evaluated_at,
    )


def evaluate_sources_operational(
    *,
    delivery_mode_by_source: dict[str, str],
    licences: dict[str, LicenceRecord] | None = None,
    evidence: dict[str, list[LiveRuntimeEvidence]] | None = None,
    retentions: dict[str, RetentionPolicy] | None = None,
    as_of: date,
    max_evidence_age_days: int = DEFAULT_MAX_EVIDENCE_AGE_DAYS,
) -> dict[str, DataSourceOperationalVerdict]:
    """Evaluate every source's operational verdict (fail-closed for missing records).

    Pure: the caller supplies ``delivery_mode_by_source`` (e.g. built from
    ``data_source_validation.delivery_mode_for``) and any licence/evidence/
    retention records it holds. A source with no records simply fails closed
    with the reasons naming what is absent.
    """
    licences = licences or {}
    evidence = evidence or {}
    retentions = retentions or {}
    return {
        sid: evaluate_data_source_operational(
            source_id=sid,
            delivery_mode=mode,
            licence=licences.get(sid),
            live_evidence=evidence.get(sid),
            retention=retentions.get(sid),
            as_of=as_of,
            max_evidence_age_days=max_evidence_age_days,
        )
        for sid, mode in delivery_mode_by_source.items()
    }


__all__ = [
    "DEFAULT_MAX_EVIDENCE_AGE_DAYS",
    "DataSourceOperationalVerdict",
    "LicenceRecord",
    "LiveRuntimeEvidence",
    "RetentionPolicy",
    "evaluate_data_source_operational",
    "evaluate_sources_operational",
]
