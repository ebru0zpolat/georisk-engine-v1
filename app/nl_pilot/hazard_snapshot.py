"""Sealed hazard snapshot — real ERA5 heat + Copernicus DEM elevation.

Bridges the real Open-Meteo connector (``app/connectors/open_meteo.py``) to the
country-agnostic hazard modules (``app/hazards/flood.py``,
``app/hazards/extreme_heat.py``) by satisfying their injectable raster
protocols from a **sealed, hash-verified** derived snapshot.

Lifecycle (same contract as ``real_data_registry`` / ``real_assets``):
    live fetch (capture script) → derive point statistics → seal derived JSON →
    SHA-256 provenance manifest → deterministic replay here.

Fail-closed invariants (no synthetic fallback, ever):
    * snapshot file missing            → ``HazardSnapshotMissing``
    * manifest missing / entry missing → ``HazardSnapshotMissing``
    * SHA-256 mismatch                 → ``HazardSnapshotHashMismatch``
    * requested point not in snapshot  → ``HazardSnapshotPointMissing``

The SHA-256-seeded ``StubHazard`` path (STUBS.md #16a) is a *separate* labelled
artefact. This module refuses to invent a value under any condition.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.geo.interfaces import RasterTile

SNAPSHOT_DIR = "data/nl_pilot/snapshots/hazard"
HAZARD_MANIFEST = "data/nl_pilot/provenance-manifest-hazard-v1.json"
DEFAULT_SNAPSHOT_ID = "hazard-amsterdam-v1"
COORDINATE_PRECISION = 5
SNAPSHOT_SCHEMA_VERSION = "hazard-snapshot-v0.1"

ELEVATION_SOURCE_TAG = "copernicus_dem_glo90"
HEAT_SOURCE_TAG = "era5_tmax_p95"


class HazardSnapshotError(ValueError):
    """Base class for fail-closed hazard-snapshot errors."""


class HazardSnapshotMissing(HazardSnapshotError):
    """Sealed snapshot or its manifest entry is absent."""


class HazardSnapshotHashMismatch(HazardSnapshotError):
    """Sealed snapshot bytes do not match the provenance manifest."""


class HazardSnapshotPointMissing(HazardSnapshotError):
    """A requested asset coordinate is not covered by the snapshot."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_sha256(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _key(latitude: float, longitude: float, precision: int) -> tuple[float, float]:
    return (round(float(latitude), precision), round(float(longitude), precision))


# ---------------------------------------------------------------------------
# Derived snapshot builder (used by the capture script and by tests)
# ---------------------------------------------------------------------------


def build_derived_snapshot(
    *,
    snapshot_id: str,
    heat_source: dict[str, Any],
    heat_points: list[dict[str, Any]],
    elevation_source: dict[str, Any],
    elevation_points: list[dict[str, Any]],
    coordinate_precision: int = COORDINATE_PRECISION,
    synthetic: bool = False,
) -> dict[str, Any]:
    """Assemble the canonical derived-snapshot dict.

    ``synthetic=True`` stamps the artefact as a labelled test fixture (never
    real observations) so it can never masquerade as sealed real data.
    """
    return {
        "snapshot_id": snapshot_id,
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "crs": "EPSG:4326",
        "coordinate_precision": coordinate_precision,
        "synthetic": bool(synthetic),
        "heat": {"source": heat_source, "points": heat_points},
        "elevation": {"source": elevation_source, "points": elevation_points},
    }


def seal_snapshot_to_disk(
    derived: dict[str, Any],
    *,
    project_root: Path,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Write the derived snapshot and a provenance manifest, returning the manifest.

    The manifest fingerprints the exact bytes written (``artifact_sha256``) and
    the canonical content (``normalized_content_sha256``).
    """
    sid = snapshot_id or derived["snapshot_id"]
    snap_dir = project_root / SNAPSHOT_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{sid}.json"
    raw = json.dumps(derived, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")
    snap_path.write_bytes(raw)

    manifest = {
        "manifest_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Real hazard snapshots (ERA5 heat + Copernicus DEM) — byte-level provenance",
        "sources": {
            sid: {
                "source_id": sid,
                "snapshot_path": f"{SNAPSHOT_DIR}/{sid}.json",
                "artifact_sha256": _sha256(raw),
                "normalized_content_sha256": _normalized_sha256(derived),
                "byte_length": len(raw),
                "synthetic": bool(derived.get("synthetic", False)),
                "heat_source": derived["heat"]["source"],
                "elevation_source": derived["elevation"]["source"],
            }
        },
    }
    manifest_path = project_root / HAZARD_MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    return manifest


# ---------------------------------------------------------------------------
# Sealed snapshot adapter — satisfies the hazard-module raster protocols
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SealedHazardSnapshot:
    """Hash-verified real-data adapter for the flood and heat hazard modules."""

    snapshot_id: str
    synthetic: bool
    coordinate_precision: int
    artifact_sha256: str
    heat_source: dict[str, Any]
    elevation_source: dict[str, Any]
    _elevation: dict[tuple[float, float], float]
    _heat_p95: dict[tuple[float, float], float]

    # -- flood module protocol: ``.elevation_at(lat, lon) -> RasterTile`` -----
    def elevation_at(self, lat: float, lon: float) -> RasterTile:
        key = _key(lat, lon, self.coordinate_precision)
        if key not in self._elevation:
            raise HazardSnapshotPointMissing(
                f"HAZARD_SNAPSHOT_POINT_MISSING: elevation for {key} not in "
                f"snapshot {self.snapshot_id!r}"
            )
        return RasterTile(
            source=ELEVATION_SOURCE_TAG,
            lat=key[0],
            lon=key[1],
            value=self._elevation[key],
            unit="m",
            data_snapshot_id=self.snapshot_id,
        )

    # -- heat module protocol: ``.era5_temperature(lat, lon, date) -> Tile`` --
    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile:
        _ = date  # climatology (95th-pct Tmax over the sealed window), not one day
        key = _key(lat, lon, self.coordinate_precision)
        if key not in self._heat_p95:
            raise HazardSnapshotPointMissing(
                f"HAZARD_SNAPSHOT_POINT_MISSING: heat climatology for {key} not "
                f"in snapshot {self.snapshot_id!r}"
            )
        return RasterTile(
            source=HEAT_SOURCE_TAG,
            lat=key[0],
            lon=key[1],
            value=self._heat_p95[key],
            unit="degC",
            data_snapshot_id=self.snapshot_id,
        )

    def data_versions(self) -> dict[str, str]:
        return {
            "hazard_snapshot_id": self.snapshot_id,
            "hazard_snapshot_sha256": self.artifact_sha256,
            "heat_method": str(self.heat_source.get("method_version", "")),
            "elevation_method": str(self.elevation_source.get("method_version", "")),
        }

    def provenance(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "artifact_sha256": self.artifact_sha256,
            "synthetic": self.synthetic,
            "heat_source": self.heat_source,
            "elevation_source": self.elevation_source,
            "point_count": len(self._elevation),
        }

    # -- constructors ---------------------------------------------------------
    @classmethod
    def from_derived_dict(
        cls, derived: dict[str, Any], *, artifact_sha256: str = ""
    ) -> "SealedHazardSnapshot":
        precision = int(derived.get("coordinate_precision", COORDINATE_PRECISION))
        elevation: dict[tuple[float, float], float] = {}
        for pt in derived.get("elevation", {}).get("points", []):
            elevation[_key(pt["latitude"], pt["longitude"], precision)] = float(
                pt["elevation_m"]
            )
        heat_p95: dict[tuple[float, float], float] = {}
        for pt in derived.get("heat", {}).get("points", []):
            heat_p95[_key(pt["latitude"], pt["longitude"], precision)] = float(
                pt["p95_tmax_c"]
            )
        if not elevation or not heat_p95:
            raise HazardSnapshotMissing(
                "HAZARD_SNAPSHOT_EMPTY: snapshot has no heat or elevation points"
            )
        return cls(
            snapshot_id=str(derived["snapshot_id"]),
            synthetic=bool(derived.get("synthetic", False)),
            coordinate_precision=precision,
            artifact_sha256=artifact_sha256,
            heat_source=dict(derived.get("heat", {}).get("source", {})),
            elevation_source=dict(derived.get("elevation", {}).get("source", {})),
            _elevation=elevation,
            _heat_p95=heat_p95,
        )


def load_sealed_hazard_snapshot(
    project_root: Path | None = None,
    *,
    snapshot_id: str = DEFAULT_SNAPSHOT_ID,
) -> SealedHazardSnapshot:
    """Load and hash-verify a sealed hazard snapshot from disk (fail-closed).

    Raises ``HazardSnapshotMissing`` when the snapshot has not been captured
    yet — pointing the caller at the capture script rather than fabricating
    values.
    """
    root = project_root or Path(__file__).resolve().parents[2]
    manifest_path = root / HAZARD_MANIFEST
    snap_path = root / SNAPSHOT_DIR / f"{snapshot_id}.json"

    if not manifest_path.exists() or not snap_path.exists():
        raise HazardSnapshotMissing(
            "HAZARD_SNAPSHOT_MISSING_FAIL_CLOSED: no sealed real hazard snapshot "
            f"for {snapshot_id!r}. Capture it (needs egress to "
            "archive-api.open-meteo.com + api.open-meteo.com):\n"
            "  PYTHONPATH=. python scripts/capture_real_hazard_snapshots.py"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest.get("sources", {}).get(snapshot_id)
    if not entry:
        raise HazardSnapshotMissing(
            f"HAZARD_SNAPSHOT_MISSING_FAIL_CLOSED: manifest has no entry for "
            f"{snapshot_id!r}"
        )

    raw = snap_path.read_bytes()
    actual = _sha256(raw)
    expected = entry.get("artifact_sha256", "")
    if actual != expected:
        raise HazardSnapshotHashMismatch(
            f"HAZARD_SNAPSHOT_HASH_MISMATCH_FAIL_CLOSED: {snapshot_id} "
            f"expected={expected[:16]}... actual={actual[:16]}..."
        )

    derived = json.loads(raw)
    expected_norm = entry.get("normalized_content_sha256", "")
    actual_norm = _normalized_sha256(derived)
    if expected_norm and actual_norm != expected_norm:
        raise HazardSnapshotHashMismatch(
            f"HAZARD_SNAPSHOT_HASH_MISMATCH_FAIL_CLOSED: {snapshot_id} "
            f"normalized expected={expected_norm[:16]}... actual={actual_norm[:16]}..."
        )

    return SealedHazardSnapshot.from_derived_dict(derived, artifact_sha256=actual)


__all__ = [
    "COORDINATE_PRECISION",
    "DEFAULT_SNAPSHOT_ID",
    "ELEVATION_SOURCE_TAG",
    "HAZARD_MANIFEST",
    "HEAT_SOURCE_TAG",
    "SNAPSHOT_DIR",
    "HazardSnapshotError",
    "HazardSnapshotHashMismatch",
    "HazardSnapshotMissing",
    "HazardSnapshotPointMissing",
    "SealedHazardSnapshot",
    "build_derived_snapshot",
    "load_sealed_hazard_snapshot",
    "seal_snapshot_to_disk",
]
