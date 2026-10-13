"""Canonical geometry store and authoritative asset_geometry_hash derivation (GEO-189)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.geo.exceptions import GeometryAlreadyRegisteredError, GeometryNotFoundError
from app.geo.interfaces import AssetGeometry, GeometryAuditEvent, derive_geometry_hash


@dataclass
class _StoredGeometry:
    asset_id: str
    geojson: dict[str, Any]
    geometry_hash: str
    version: int
    registered_at: datetime
    updated_at: datetime


class GeometryStore(Protocol):
    def get(self, asset_id: str) -> _StoredGeometry | None: ...

    def put(self, record: _StoredGeometry) -> None: ...

    def list_asset_ids(self) -> list[str]: ...


class InMemoryGeometryStore:
    """Process-local store for CI and local development."""

    def __init__(self) -> None:
        self._records: dict[str, _StoredGeometry] = {}

    def get(self, asset_id: str) -> _StoredGeometry | None:
        return self._records.get(asset_id)

    def put(self, record: _StoredGeometry) -> None:
        self._records[record.asset_id] = record

    def list_asset_ids(self) -> list[str]:
        return list(self._records.keys())


class GeometryRegistry:
    """Canonical registry for verified asset geometries and derived hashes."""

    def __init__(self, store: GeometryStore | None = None) -> None:
        self._store = store or InMemoryGeometryStore()
        self._audit_log: list[GeometryAuditEvent] = []

    @property
    def audit_log(self) -> tuple[GeometryAuditEvent, ...]:
        return tuple(self._audit_log)

    def register(self, asset_id: str, geojson: dict[str, Any]) -> AssetGeometry:
        if self._store.get(asset_id) is not None:
            raise GeometryAlreadyRegisteredError(asset_id)

        now = _utc_now()
        geometry_hash = derive_geometry_hash(geojson)
        record = _StoredGeometry(
            asset_id=asset_id,
            geojson=geojson,
            geometry_hash=geometry_hash,
            version=1,
            registered_at=now,
            updated_at=now,
        )
        self._store.put(record)
        self._record_audit(record)
        return _to_asset_geometry(record)

    def update(self, asset_id: str, geojson: dict[str, Any]) -> AssetGeometry:
        existing = self._store.get(asset_id)
        if existing is None:
            raise GeometryNotFoundError(asset_id)

        now = _utc_now()
        geometry_hash = derive_geometry_hash(geojson)
        record = _StoredGeometry(
            asset_id=asset_id,
            geojson=geojson,
            geometry_hash=geometry_hash,
            version=existing.version + 1,
            registered_at=existing.registered_at,
            updated_at=now,
        )
        self._store.put(record)
        self._record_audit(record)
        return _to_asset_geometry(record)

    def get(self, asset_id: str) -> AssetGeometry:
        record = self._store.get(asset_id)
        if record is None:
            raise GeometryNotFoundError(asset_id)
        return _to_asset_geometry(record)

    def hash_for(self, asset_id: str) -> str:
        record = self._store.get(asset_id)
        if record is None:
            raise GeometryNotFoundError(asset_id)
        return record.geometry_hash

    def list_asset_ids(self) -> list[str]:
        return self._store.list_asset_ids()

    def _record_audit(self, record: _StoredGeometry) -> None:
        self._audit_log.append(
            GeometryAuditEvent(
                event="geometry_registered",
                asset_id=record.asset_id,
                asset_geometry_hash=record.geometry_hash,
                version=record.version,
                timestamp=record.updated_at,
            )
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_asset_geometry(record: _StoredGeometry) -> AssetGeometry:
    return AssetGeometry(
        asset_id=record.asset_id,
        geojson=record.geojson,
        asset_geometry_hash=record.geometry_hash,
        registered_at=record.registered_at,
        version=record.version,
    )
