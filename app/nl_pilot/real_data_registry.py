"""Real-Data Registry — provenance-aware source data management.

Each real source artifact (BAG response, regulatory publication,
AHN window, KNMI scenario slice) is captured as a sealed snapshot
with full provenance metadata.  CI replays these snapshots
deterministically; live acquisition is opt-in.

Snapshot lifecycle:
  1. Live fetch from official source
  2. Raw bytes SHA-256 computed
  3. Snapshot saved to data/nl_pilot/snapshots/
  4. Provenance manifest recorded
  5. CI replays from snapshot (never from live source)

Fail-closed invariant:
  - Missing snapshot → fail-closed (not synthetic fallback)
  - Hash mismatch → fail-closed (source changed)
  - No silent synthetic fallback under any condition
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# Source classification
# ---------------------------------------------------------------------------

class RealDataSourceType(str, Enum):
    """Classification of real Dutch source data types."""
    REGULATORY_PUBLICATION = "REGULATORY_PUBLICATION"
    CADASTRE = "CADASTRE"          # BAG
    ELEVATION = "ELEVATION"        # AHN
    CLIMATE_SCENARIO = "CLIMATE_SCENARIO"  # KNMI'23
    GEOSPATIAL_BOUNDARY = "GEOSPATIAL_BOUNDARY"


class SnapshotStatus(str, Enum):
    """Status of a sealed snapshot."""
    SEALED = "SEALED"              # SHA-256 verified
    UNSEALED = "UNSEALED"          # Raw file exists, not yet sealed
    MISSING = "MISSING"            # No snapshot file
    HASH_MISMATCH = "HASH_MISMATCH"  # Source changed since sealing


# ---------------------------------------------------------------------------
# Provenance manifest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceProvenance:
    """Full provenance metadata for a real source artifact.

    Every field is independently verifiable.  The snapshot_sha256
    fingerprints the raw bytes of the retrieved artifact.
    """
    source_id: str
    source_type: RealDataSourceType
    authority: str
    official_identifier: str
    title: str
    source_url: str
    retrieved_at: str  # ISO 8601
    effective_from: str
    effective_until: str | None = None
    mime_type: str = "application/json"
    byte_length: int = 0
    snapshot_sha256: str = ""
    license_id: str = ""
    license_name: str = ""
    license_url: str = ""
    query_or_bbox: str = ""  # API query or bounding box used
    crs: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        """Deterministic serialization."""
        return {
            k: v for k, v in {
                "source_id": self.source_id,
                "source_type": self.source_type.value,
                "authority": self.authority,
                "official_identifier": self.official_identifier,
                "title": self.title,
                "source_url": self.source_url,
                "retrieved_at": self.retrieved_at,
                "effective_from": self.effective_from,
                "effective_until": self.effective_until,
                "mime_type": self.mime_type,
                "byte_length": self.byte_length,
                "snapshot_sha256": self.snapshot_sha256,
                "license_id": self.license_id,
                "license_name": self.license_name,
                "license_url": self.license_url,
                "query_or_bbox": self.query_or_bbox,
                "crs": self.crs,
                "notes": self.notes,
            }.items()
            if v is not None and v != ""
        }


# ---------------------------------------------------------------------------
# Sealed snapshot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SealedSnapshot:
    """A sealed snapshot of a real source artifact.

    The snapshot file is stored at snapshot_path.  The SHA-256
    of the raw file bytes must match snapshot_sha256.
    """
    source_id: str
    snapshot_path: str  # Relative to project root
    snapshot_sha256: str
    sealed_at: str  # ISO 8601
    status: SnapshotStatus = SnapshotStatus.SEALED

    def verify(self, project_root: Path) -> tuple[bool, str]:
        """Verify the snapshot file exists and its hash matches.

        Returns (is_valid, reason).
        """
        full_path = project_root / self.snapshot_path
        if not full_path.exists():
            return False, f"Snapshot file not found: {self.snapshot_path}"

        raw_bytes = full_path.read_bytes()
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()

        if actual_hash != self.snapshot_sha256:
            return False, (
                f"Snapshot hash mismatch for '{self.source_id}': "
                f"expected {self.snapshot_sha256[:16]}..., "
                f"got {actual_hash[:16]}..."
            )

        return True, "Snapshot verified"


# ---------------------------------------------------------------------------
# Source snapshot registry
# ---------------------------------------------------------------------------

class RealDataRegistry:
    """Registry of sealed source snapshots.

    Manages the lifecycle of real source data: sealing, verification,
    and deterministic replay.  All source data MUST be sealed before
    use in evidence pack generation.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(".")
        self._provenance: dict[str, SourceProvenance] = {}
        self._snapshots: dict[str, SealedSnapshot] = {}

    def register_provenance(self, provenance: SourceProvenance) -> None:
        """Register source provenance metadata."""
        self._provenance[provenance.source_id] = provenance

    def seal_snapshot(
        self,
        source_id: str,
        snapshot_path: str,
    ) -> SealedSnapshot:
        """Seal a snapshot file by computing its SHA-256.

        Returns the SealedSnapshot with SEALED status.
        Raises ValueError if source_id is not registered.
        """
        if source_id not in self._provenance:
            raise ValueError(
                f"Cannot seal snapshot for unknown source_id '{source_id}'; "
                f"register provenance first"
            )

        full_path = self._project_root / snapshot_path
        if not full_path.exists():
            raise FileNotFoundError(
                f"Snapshot file not found: {snapshot_path}"
            )

        raw_bytes = full_path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        snapshot = SealedSnapshot(
            source_id=source_id,
            snapshot_path=snapshot_path,
            snapshot_sha256=sha256,
            sealed_at=datetime.now(timezone.utc).isoformat(),
            status=SnapshotStatus.SEALED,
        )

        self._snapshots[source_id] = snapshot

        # Update provenance with hash
        prov = self._provenance[source_id]
        self._provenance[source_id] = SourceProvenance(
            source_id=prov.source_id,
            source_type=prov.source_type,
            authority=prov.authority,
            official_identifier=prov.official_identifier,
            title=prov.title,
            source_url=prov.source_url,
            retrieved_at=prov.retrieved_at,
            effective_from=prov.effective_from,
            effective_until=prov.effective_until,
            mime_type=prov.mime_type,
            byte_length=len(raw_bytes),
            snapshot_sha256=sha256,
            license_id=prov.license_id,
            license_name=prov.license_name,
            license_url=prov.license_url,
            query_or_bbox=prov.query_or_bbox,
            crs=prov.crs,
            notes=prov.notes,
        )

        return snapshot

    def verify_snapshot(self, source_id: str) -> tuple[bool, str]:
        """Verify a sealed snapshot's hash against the file on disk.

        Returns (is_valid, reason).
        """
        if source_id not in self._snapshots:
            return False, f"No snapshot registered for '{source_id}'"

        snapshot = self._snapshots[source_id]
        return snapshot.verify(self._project_root)

    def load_snapshot_bytes(self, source_id: str) -> bytes:
        """Load the raw bytes from a sealed snapshot.

        Raises ValueError if snapshot is missing or hash mismatch.
        This is the ONLY way to access real source data in the pilot.
        """
        if source_id not in self._snapshots:
            raise ValueError(
                f"No snapshot registered for '{source_id}'; "
                f"seal a snapshot before loading"
            )

        is_valid, reason = self.verify_snapshot(source_id)
        if not is_valid:
            raise ValueError(
                f"Snapshot verification failed for '{source_id}': {reason}"
            )

        snapshot = self._snapshots[source_id]
        full_path = self._project_root / snapshot.snapshot_path
        return full_path.read_bytes()

    def get_provenance(self, source_id: str) -> SourceProvenance | None:
        return self._provenance.get(source_id)

    def list_sources(self) -> list[str]:
        return sorted(self._provenance.keys())

    def list_sealed(self) -> list[str]:
        return sorted(self._snapshots.keys())

    def to_manifest(self) -> dict:
        """Export the full provenance manifest."""
        return {
            "sources": {
                sid: prov.to_dict()
                for sid, prov in sorted(self._provenance.items())
            },
            "snapshots": {
                sid: {
                    "snapshot_path": snap.snapshot_path,
                    "snapshot_sha256": snap.snapshot_sha256,
                    "sealed_at": snap.sealed_at,
                    "status": snap.status.value,
                }
                for sid, snap in sorted(self._snapshots.items())
            },
        }
