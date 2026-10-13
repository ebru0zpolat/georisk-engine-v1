"""Fail-closed freshness gate for AGV regulatory work-area geometry.

AGV published changed water-defence register and Waterschapsverordening
``werkingsgebieden`` on 11 June 2026.  Geometry captured before that change must
not be used to establish asset-level applicability.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


AGV_GEOMETRY_PUBLICATION_DATE = date(2026, 6, 11)
AGV_GEOMETRY_EFFECTIVE_DATE = date(2026, 6, 12)
AGV_DEFERRED_TRAJECTORIES = frozenset({"A709"})
AGV_HIGHLIGHTED_AMSTERDAM_TRAJECTORIES = frozenset(
    {"A511", "A518", "A519", "A708", "A709"}
)
AGV_AUTHORITY_IDS = frozenset({"agv", "waterschap-agv"})


def _sha256_is_valid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def requires_current_agv_geometry(asset: dict) -> bool:
    """Return whether the conservative June-2026 AGV freshness gate applies."""
    # Do not trust ``water_authority`` here: it may itself be the result of the
    # stale spatial layer this gate exists to quarantine.
    return asset.get("municipality") == "Amsterdam"


def verify_current_agv_geometry(asset: dict) -> tuple[bool, str]:
    """Verify acquisition, integrity and re-evaluation of current AGV geometry.

    The evidence is deliberately asset-scoped: a fresh layer alone is not
    enough; the asset must have been spatially re-evaluated against it.  A709
    must remain represented as deferred rather than treated as effective.
    """
    if not requires_current_agv_geometry(asset):
        return True, "AGV June-2026 geometry freshness gate not applicable"

    evidence = asset.get("agv_geometry_evidence")
    if not isinstance(evidence, dict):
        return False, "AGV_GEOMETRY_STALE: current AGV work-area evidence is missing"

    if _parse_date(evidence.get("publication_date")) != AGV_GEOMETRY_PUBLICATION_DATE:
        return False, "AGV_GEOMETRY_STALE: publication_date must be 2026-06-11"
    if _parse_date(evidence.get("effective_date")) != AGV_GEOMETRY_EFFECTIVE_DATE:
        return False, "AGV_GEOMETRY_STALE: effective_date must be 2026-06-12"
    if not evidence.get("geometry_version"):
        return False, "AGV_GEOMETRY_UNVERSIONED: geometry_version is required"
    if evidence.get("source_checksums_verified") is not True:
        return False, "AGV_GEOMETRY_UNVERIFIED: source_checksums_verified must be true"
    if not _sha256_is_valid(evidence.get("artifact_sha256")):
        return False, "AGV_GEOMETRY_UNVERIFIED: a lowercase artifact SHA-256 is required"

    acquired_at = _parse_datetime(evidence.get("acquired_at"))
    if acquired_at is None or acquired_at.date() < AGV_GEOMETRY_PUBLICATION_DATE:
        return False, "AGV_GEOMETRY_STALE: acquired_at must follow publication"
    evaluated_at = _parse_datetime(evidence.get("spatially_evaluated_at"))
    if evaluated_at is None or evaluated_at < acquired_at:
        return False, "AGV_ASSET_NOT_REEVALUATED: spatial evaluation must follow acquisition"

    deferred = evidence.get("deferred_trajectories")
    if not isinstance(deferred, list) or not AGV_DEFERRED_TRAJECTORIES.issubset(deferred):
        return False, "AGV_GEOMETRY_EFFECTIVITY_UNVERIFIED: A709 must be recorded as deferred"

    return True, "Current, hashed AGV geometry and asset spatial re-evaluation verified"
