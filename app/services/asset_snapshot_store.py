from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class AssetSnapshot(BaseModel):
    audit_id: str
    asset_name: str
    latitude: float
    longitude: float
    radius_km: float
    sector: str
    overall_score: int
    components: dict[str, int]
    model_version: str = "risk-score-v0.1"
    data_snapshot_id: str = "hazard_layers_2026_05"
    asset_geometry_hash: str = ""
    uses_connector_fallback: bool = False


class SnapshotBackend(Protocol):
    """Storage seam. The module-level API never changes; the backend does.

    The in-memory backend is the test fixture and the default. The Postgres
    backend (``app.storage.snapshot_repository.SqlAlchemySnapshotBackend``) is
    selected by ``SNAPSHOT_STORE_BACKEND=db``.
    """

    def register(self, snapshot: AssetSnapshot) -> None: ...

    def get(self, audit_id: str) -> AssetSnapshot | None: ...

    def clear(self) -> None: ...

    def count(self) -> int: ...


class InMemorySnapshotBackend:
    """Process-memory backend — test fixture only (WP-2)."""

    def __init__(self) -> None:
        self._store: dict[str, AssetSnapshot] = {}

    def register(self, snapshot: AssetSnapshot) -> None:
        self._store[snapshot.audit_id] = snapshot

    def get(self, audit_id: str) -> AssetSnapshot | None:
        return self._store.get(audit_id)

    def clear(self) -> None:
        self._store.clear()

    def count(self) -> int:
        return len(self._store)


_backend: SnapshotBackend = InMemorySnapshotBackend()


def get_snapshot_backend() -> SnapshotBackend:
    return _backend


def set_snapshot_backend(backend: SnapshotBackend) -> None:
    global _backend
    _backend = backend


def reset_snapshot_backend() -> SnapshotBackend:
    """Restore the in-memory fixture backend (test helper)."""
    global _backend
    _backend = InMemorySnapshotBackend()
    return _backend


def register_snapshot(snapshot: AssetSnapshot) -> None:
    _backend.register(snapshot)


def get_snapshot(audit_id: str) -> AssetSnapshot | None:
    return _backend.get(audit_id)


def clear_snapshots() -> None:
    """Test helper."""
    _backend.clear()


def snapshot_count() -> int:
    return _backend.count()


__all__ = [
    "AssetSnapshot",
    "InMemorySnapshotBackend",
    "SnapshotBackend",
    "clear_snapshots",
    "get_snapshot",
    "get_snapshot_backend",
    "register_snapshot",
    "reset_snapshot_backend",
    "set_snapshot_backend",
    "snapshot_count",
]
