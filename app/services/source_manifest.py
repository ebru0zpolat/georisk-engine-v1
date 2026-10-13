"""Build per-result source manifests (WP-4).

The five-layer pipeline consumes labelled synthetic curves plus, optionally,
real connector layers. This module turns (a) the ``data_versions`` a run stamped
and (b) the data-source registry into a :class:`SourceManifest`, applying the
licence gate so blocked sources are recorded but never contribute.

Licence truth lives in ``app.core.data_source_operational_records`` (a
commercial-use :class:`LicenceRecord` per source). With no licence on file —
the demo default — every real source is ``blocked``; the synthetic curves the
pipeline actually uses are labelled ``synthetic`` / ``not_applicable``; other
stamped versions are ``unclassified`` (see :func:`records_from_data_versions`).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from app.core.data_source_operational_gate import LicenceRecord
from app.core.data_source_operational_records import load_licences_and_retentions
from app.core.data_source_registry import DataSourceEntry, list_data_sources
from app.schemas.source_manifest import (
    LicenceState,
    SourceManifest,
    SourceRecord,
    apply_licence_gate,
    state_for_delivery_mode,
)

#: ``data_versions`` key → the layer(s) the value fed.
_USED_FOR: dict[str, list[str]] = {
    "hazard_stub": ["hazard"],
    "vulnerability_curves": ["vulnerability"],
    "adaptation_catalogue": ["adaptation"],
    "damage_curves": ["financial"],
    "expected_loss": ["financial"],
    "horizon_method": ["financial"],
    "depth_damage": ["financial"],
}

#: Keys whose value is always one of our own fixed synthetic stamps. Curve
#: catalogues (``damage_curves``, ``depth_damage``) are not here: a vendored
#: catalogue can be real, so they are classified by their labelled version.
_INTERNAL_SYNTHETIC_KEYS: frozenset[str] = frozenset(
    {"hazard_stub", "vulnerability_curves", "adaptation_catalogue", "expected_loss", "horizon_method"}
)


def licence_state_for(
    source_id: str,
    *,
    licences: dict[str, LicenceRecord] | None = None,
    as_of: date,
) -> LicenceState:
    """Return the licence posture for ``source_id`` as of ``as_of`` (fail-closed)."""
    record = (licences or {}).get(source_id)
    if record is None:
        return "unverified"
    if not record.commercial_use:
        return "unverified"
    if record.valid_from > as_of:
        return "unverified"
    if record.valid_until is not None and record.valid_until < as_of:
        return "unverified"
    return "verified"


#: Markers that label a stamped version as our own synthetic stand-in.
_SYNTHETIC_MARKERS = ("synthetic", "stub")


def records_from_data_versions(
    data_versions: dict[str, str],
    *,
    retrieved_at: datetime | None = None,
) -> list[SourceRecord]:
    """One record per stamped ``data_versions`` key, classified conservatively.

    * our own fixed stamps (``_INTERNAL_SYNTHETIC_KEYS``), and versions labelled
      ``synthetic``/``stub`` → ``synthetic`` / ``not_applicable``;
    * anything else (e.g. ``elevation``, ``era5_temperature``, the NL pilot's
      snapshot stamps) → ``unclassified`` / ``unverified``: its retrieval path
      and licence are not recorded, so it is never presented as synthetic,
      live or fixture. It is not licence-gated here (WP-4 known gap).

    ``retrieved_at`` stays ``None`` unless a caller supplies a real retrieval
    time; a run-time clock would make identical runs differ (INV-08).
    """
    records: list[SourceRecord] = []
    for key, value in data_versions.items():
        version = str(value)
        internal = key in _INTERNAL_SYNTHETIC_KEYS or any(
            marker in version.lower() for marker in _SYNTHETIC_MARKERS
        )
        records.append(
            SourceRecord(
                source_id=key,
                version=version,
                retrieved_at=retrieved_at,
                licence_state="not_applicable" if internal else "unverified",
                used_for=list(_USED_FOR.get(key, [key])),
                state="synthetic" if internal else "unclassified",
            )
        )
    return records


def registry_source_records(
    *,
    licences: dict[str, LicenceRecord] | None = None,
    as_of: date,
    delivery_mode_by_source: dict[str, str] | None = None,
    tiers: Iterable[str] = ("production",),
    used_for_by_source: dict[str, list[str]] | None = None,
) -> list[SourceRecord]:
    """One record per registry source, blocked when unlicensed.

    Sources not actually used by the run are still recorded (``used_for=[]``) so
    the manifest names what was excluded — the acceptance condition for WP-4.
    """
    delivery = delivery_mode_by_source or {}
    used_for = used_for_by_source or {}
    records: list[SourceRecord] = []
    for entry in _iter_registry(tiers):
        licence_state = licence_state_for(entry.id, licences=licences, as_of=as_of)
        if licence_state == "verified":
            state = state_for_delivery_mode(delivery.get(entry.id, "fallback"))
        else:
            state = "blocked"
        records.append(
            SourceRecord(
                source_id=entry.id,
                version=entry.dataset_id or "",
                licence_state=licence_state,
                used_for=list(used_for.get(entry.id, [])),
                state=state,
                blocked_reason=(
                    None
                    if licence_state == "verified"
                    else f"no verified commercial-use licence for {entry.id!r}"
                ),
            )
        )
    return records


def build_result_manifest(
    *,
    data_versions: dict[str, str],
    licences: dict[str, LicenceRecord] | None = None,
    as_of: date | None = None,
    delivery_mode_by_source: dict[str, str] | None = None,
    extra_records: Iterable[SourceRecord] = (),
    include_registry: bool = True,
) -> SourceManifest:
    """Assemble and gate the manifest for one result.

    ``licences`` defaults to the operator's licence register
    (``config/data_source_operational.json``). ``extra_records`` (sources a
    caller handed to the run) carry no trusted claim of their own: whatever
    ``state`` or ``licence_state`` they declare, their licence is re-derived
    from the register and, unless verified, they are ``blocked``. A caller
    record replaces the registry's placeholder for the same source — one
    record per source.
    """
    day = as_of or datetime.now(timezone.utc).date()
    register = licences if licences is not None else load_licences_and_retentions()[0]
    extras = [_gate_caller_record(record, licences=register, as_of=day) for record in extra_records]
    supplied = {record.source_id for record in extras}
    records = records_from_data_versions(data_versions)
    if include_registry:
        records.extend(
            record
            for record in registry_source_records(
                licences=register,
                as_of=day,
                delivery_mode_by_source=delivery_mode_by_source,
            )
            if record.source_id not in supplied
        )
    records.extend(extras)
    return apply_licence_gate(records)


def _gate_caller_record(
    record: SourceRecord, *, licences: dict[str, LicenceRecord], as_of: date
) -> SourceRecord:
    licence_state = licence_state_for(record.source_id, licences=licences, as_of=as_of)
    if licence_state == "verified":
        return record.model_copy(update={"licence_state": licence_state})
    return record.model_copy(
        update={
            "licence_state": licence_state,
            "state": "blocked",
            "blocked_reason": f"no verified commercial-use licence for {record.source_id!r}",
        }
    )


def _iter_registry(tiers: Iterable[str]) -> list[DataSourceEntry]:
    wanted = set(tiers)
    return [entry for entry in list_data_sources() if entry.tier in wanted]


__all__ = [
    "build_result_manifest",
    "licence_state_for",
    "records_from_data_versions",
    "registry_source_records",
]
