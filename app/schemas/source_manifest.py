"""Per-result source manifest (WP-4).

Every financial result carries one :class:`SourceRecord` per data source that
touched it — including sources that were *blocked* and therefore contributed to
no number. The manifest is the machine-readable answer to "where did this number
come from, and what could not enter it".

States (``state``):

* ``live``      — real data fetched from the source at runtime;
* ``fixture``   — a captured real sample used offline (deterministic replay);
* ``synthetic`` — a labelled synthetic curve/stub (STUBS.md), never real data;
* ``degraded``  — real source partially available (fallback inside the source);
* ``blocked``   — not permitted to contribute (e.g. licence not verified);
* ``unclassified`` — a version the run stamped in ``data_versions`` whose
  retrieval path and licence are not recorded (e.g. the NL pilot's ERA5 + DEM
  snapshot). Not gated in WP-4 — a known gap, surfaced as
  ``SOURCES_UNCLASSIFIED`` so it is never mistaken for ``synthetic``.

A blocked record must never feed a number. Records a caller hands to a run are
gated by :func:`apply_licence_gate` and checked by
:func:`refuse_blocked_contributors` *before* the computation, which refuses
rather than relabelling afterwards, so the manifest and the computation agree.

``licence_state``:

* ``verified``       — a valid commercial-use licence is on file (see
  ``app.core.data_source_operational_records``);
* ``unverified``     — no valid licence; real data from this source is blocked;
* ``not_applicable`` — our own synthetic curves (no third-party licence needed).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core import error_codes as codes

SourceState = Literal["live", "fixture", "synthetic", "degraded", "blocked", "unclassified"]
LicenceState = Literal["verified", "unverified", "not_applicable"]

#: States that represent real, licensable third-party data.
REAL_DATA_STATES: frozenset[str] = frozenset({"live", "fixture", "degraded"})


class SourceRecord(BaseModel):
    """One data source as it touched (or was excluded from) one result."""

    source_id: str
    version: str = ""
    retrieved_at: datetime | None = None
    licence_state: LicenceState = "unverified"
    #: e.g. ``{"crs": "CRS84", "min_lon": ..., "min_lat": ..., "max_lon": ..., "max_lat": ...}``
    spatial_bounds: dict[str, Any] | None = None
    #: SHA-256 of the payload actually consumed, when available (provenance).
    payload_hash: str | None = None
    #: What this source fed, e.g. ``["hazard", "financial"]``.
    used_for: list[str] = Field(default_factory=list)
    state: SourceState = "synthetic"
    #: Human-readable reason when ``state == "blocked"``.
    blocked_reason: str | None = None

    def is_blocked(self) -> bool:
        return self.state == "blocked"


class SourceManifest(BaseModel):
    """Ordered set of :class:`SourceRecord` attached to a single result."""

    records: list[SourceRecord] = Field(default_factory=list)

    def add(self, record: SourceRecord) -> None:
        self.records.append(record)

    def contributing(self) -> list[SourceRecord]:
        """Records allowed to feed the number (everything not blocked)."""
        return [r for r in self.records if not r.is_blocked()]

    def blocked(self) -> list[SourceRecord]:
        return [r for r in self.records if r.is_blocked()]

    def get(self, source_id: str) -> SourceRecord | None:
        return next((r for r in self.records if r.source_id == source_id), None)

    def to_payload(self) -> list[dict[str, Any]]:
        return [record.model_dump(mode="json") for record in self.records]

    @classmethod
    def from_payload(cls, payload: list[dict[str, Any]] | None) -> "SourceManifest":
        return cls(records=[SourceRecord.model_validate(item) for item in (payload or [])])


#: Registry delivery mode (``data_source_validation.delivery_mode_for``) → state.
_DELIVERY_MODE_TO_STATE: dict[str, SourceState] = {
    "live": "live",
    # Mock data is not a captured real sample: label it synthetic, never fixture.
    "mock": "synthetic",
    "stub": "synthetic",
    "fallback": "synthetic",
    "fixture": "fixture",
    "degraded": "degraded",
}


def state_for_delivery_mode(mode: str) -> SourceState:
    """Map a registry delivery mode to a manifest state (fail-closed default)."""
    return _DELIVERY_MODE_TO_STATE.get(mode, "degraded")


def apply_licence_gate(records: list[SourceRecord]) -> SourceManifest:
    """Block every real-data record whose licence is not verified.

    Synthetic records (our own curves) are exempt: they are labelled, not
    licensed third-party data. Returns a new :class:`SourceManifest`; the input
    records are not mutated.
    """
    gated: list[SourceRecord] = []
    for record in records:
        if record.state in REAL_DATA_STATES and record.licence_state != "verified":
            gated.append(
                record.model_copy(
                    update={
                        "state": "blocked",
                        "blocked_reason": (
                            "no verified commercial-use licence on file "
                            f"(licence_state={record.licence_state})"
                        ),
                    }
                )
            )
        else:
            gated.append(record)
    return SourceManifest(records=gated)


class SourceLicenceNotVerifiedError(ValueError):
    """A blocked source was declared as feeding a number; the run is refused."""

    code = codes.SOURCE_LICENCE_NOT_VERIFIED

    def __init__(self, source_ids: list[str]) -> None:
        self.source_ids = source_ids
        super().__init__(
            f"{self.code}: blocked source(s) {source_ids} cannot feed a number "
            "(no verified commercial-use licence on file)"
        )


def refuse_blocked_contributors(manifest: SourceManifest) -> None:
    """Refuse when a blocked record declares a use; call before computing.

    A blocked record with ``used_for == []`` is a listed exclusion and is fine.
    """
    offending = [r.source_id for r in manifest.blocked() if r.used_for]
    if offending:
        raise SourceLicenceNotVerifiedError(offending)


__all__ = [
    "LicenceState",
    "REAL_DATA_STATES",
    "SourceManifest",
    "SourceRecord",
    "SourceLicenceNotVerifiedError",
    "SourceState",
    "apply_licence_gate",
    "refuse_blocked_contributors",
    "state_for_delivery_mode",
]
