"""Hash-chained append-only audit trail for financial pipeline outputs.

Design test (directive §5): a regulator must be able to reproduce any number from
the trail. No blockchain — independent hash chain over canonical JSON payloads.

Default storage is **file-backed** JSONL. Append uses exclusive file locking and
re-reads the tip from disk — the in-memory tip is a cache only.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

GENESIS_PREV_HASH = "0" * 64

# Default relative to process CWD; override with GEORISK_AUDIT_TRAIL_PATH.
_DEFAULT_AUDIT_PATH = Path("data/audit_trail/expected_loss.jsonl")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_json(payload: Any) -> str:
    """The canonical serialisation hashed by the trail (sorted keys, no spaces)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_record_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return _sha256_hex(prev_hash + _canonical_json(payload))


def default_audit_trail_path() -> Path:
    override = os.environ.get("GEORISK_AUDIT_TRAIL_PATH")
    if override:
        return Path(override)
    return _DEFAULT_AUDIT_PATH


def tip_hash_from_file(path: Path) -> str:
    """Read the last record hash from disk (source of truth for chaining)."""
    if not path.is_file():
        return GENESIS_PREV_HASH
    last: AuditTrailRecord | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            last = AuditTrailRecord.model_validate_json(line)
    if last is None:
        return GENESIS_PREV_HASH
    return last.record_hash


class AuditTrailRecord(BaseModel):
    """One append-only record — enough to recompute financial outputs."""

    record_id: str
    prev_hash: str
    record_hash: str
    timestamp: datetime
    methodology_version: str
    data_versions: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    valuation_date: date
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    #: Per-source manifest (WP-4). Included in the hash only when present, so
    #: records written before WP-4 keep their original hash and still verify.
    sources: list[dict[str, Any]] = Field(default_factory=list)

    def hash_payload(self) -> dict[str, Any]:
        payload = {
            "record_id": self.record_id,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp.isoformat(),
            "methodology_version": self.methodology_version,
            "data_versions": self.data_versions,
            "parameters": self.parameters,
            "valuation_date": self.valuation_date.isoformat(),
            "inputs": self.inputs,
            "outputs": self.outputs,
        }
        if self.sources:
            payload["sources"] = self.sources
        return payload


class AppendOnlyAuditTrail:
    """Append-only store with JSONL persistence and exclusive file locking."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._mem_lock = threading.Lock()
        self._records: list[AuditTrailRecord] = []
        self._by_id: dict[str, AuditTrailRecord] = {}
        if path is not None and path.is_file():
            self._load(path)

    def _load(self, path: Path) -> None:
        self._records.clear()
        self._by_id.clear()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = AuditTrailRecord.model_validate_json(line)
            self._records.append(rec)
            self._by_id[rec.record_id] = rec

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def tip_hash(self) -> str:
        """In-memory cache tip — not authoritative when ``path`` is set."""
        if not self._records:
            return GENESIS_PREV_HASH
        return self._records[-1].record_hash

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
        record_id = f"atr_{uuid4().hex}"
        ts = timestamp or datetime.now(timezone.utc)

        if self._path is None:
            with self._mem_lock:
                return self._append_unlocked(
                    prev=self.tip_hash,
                    record_id=record_id,
                    ts=ts,
                    methodology_version=methodology_version,
                    valuation_date=valuation_date,
                    data_versions=data_versions,
                    parameters=parameters,
                    inputs=inputs,
                    outputs=outputs,
                    sources=sources,
                    persist=False,
                )

        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                # Disk tip is the source of truth — never chain from stale memory alone.
                prev = tip_hash_from_file(self._path)
                with self._mem_lock:
                    # Refresh cache from disk before applying the new tip.
                    if self._path.is_file():
                        self._load(self._path)
                    return self._append_unlocked(
                        prev=prev,
                        record_id=record_id,
                        ts=ts,
                        methodology_version=methodology_version,
                        valuation_date=valuation_date,
                        data_versions=data_versions,
                        parameters=parameters,
                        inputs=inputs,
                        outputs=outputs,
                        sources=sources,
                        persist=True,
                    )
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def _append_unlocked(
        self,
        *,
        prev: str,
        record_id: str,
        ts: datetime,
        methodology_version: str,
        valuation_date: date,
        data_versions: dict[str, str],
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        sources: list[dict[str, Any]] | None = None,
        persist: bool,
    ) -> AuditTrailRecord:
        stored_sources = list(sources or [])
        payload = {
            "record_id": record_id,
            "prev_hash": prev,
            "timestamp": ts.isoformat(),
            "methodology_version": methodology_version,
            "data_versions": dict(data_versions),
            "parameters": dict(parameters),
            "valuation_date": valuation_date.isoformat(),
            "inputs": dict(inputs),
            "outputs": dict(outputs),
        }
        if stored_sources:
            payload["sources"] = stored_sources
        record = AuditTrailRecord(
            record_id=record_id,
            prev_hash=prev,
            record_hash=compute_record_hash(prev, payload),
            timestamp=ts,
            methodology_version=methodology_version,
            data_versions=dict(data_versions),
            parameters=dict(parameters),
            valuation_date=valuation_date,
            inputs=dict(inputs),
            outputs=dict(outputs),
            sources=stored_sources,
        )
        self._records.append(record)
        self._by_id[record.record_id] = record
        if persist and self._path is not None:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return record

    def get(self, record_id: str) -> AuditTrailRecord | None:
        return self._by_id.get(record_id)

    def verify_chain(self) -> bool:
        prev = GENESIS_PREV_HASH
        for rec in self._records:
            if rec.prev_hash != prev:
                return False
            if compute_record_hash(rec.prev_hash, rec.hash_payload()) != rec.record_hash:
                return False
            prev = rec.record_hash
        return True

    def __len__(self) -> int:
        return len(self._records)


_default_trail: AppendOnlyAuditTrail | None = None


def get_audit_trail() -> AppendOnlyAuditTrail:
    """Return the process default trail (file-backed under ``data/audit_trail/``)."""
    global _default_trail
    if _default_trail is None:
        _default_trail = AppendOnlyAuditTrail(path=default_audit_trail_path())
    return _default_trail


def reset_audit_trail_for_tests(path: Path | None = None) -> AppendOnlyAuditTrail:
    """Replace the default trail. Pass a temp path for isolated tests."""
    global _default_trail
    _default_trail = AppendOnlyAuditTrail(path=path)
    return _default_trail


__all__ = [
    "AppendOnlyAuditTrail",
    "AuditTrailRecord",
    "GENESIS_PREV_HASH",
    "compute_record_hash",
    "default_audit_trail_path",
    "get_audit_trail",
    "reset_audit_trail_for_tests",
    "tip_hash_from_file",
]
