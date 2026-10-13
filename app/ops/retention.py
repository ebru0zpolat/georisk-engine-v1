"""WP-D: Provider-neutral evidence retention interface (GEO-62).

Write-once evidence storage with checksum verification, metadata
lookup and duplicate/conflict rejection.  Retention failure must
never be silently treated as persisted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Evidence ID must match: alphanumeric start, then alphanumeric, dot,
# underscore or hyphen, 1-128 chars total.
_EVIDENCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


class EvidenceRecord(BaseModel, frozen=True):
    """A single stored evidence record."""

    evidence_id: str
    content_sha256: str
    payload: str  # canonical JSON string
    metadata: dict[str, str] = Field(default_factory=dict)
    retention_status: Literal["persisted", "failed", "unavailable"] = (
        "persisted"
    )


class RetentionResult(BaseModel, frozen=True):
    """Result of a retention operation."""

    success: bool
    evidence_id: str
    content_sha256: str
    retention_status: Literal["persisted", "failed", "unavailable"]
    error: str | None = None


class EvidenceRetention(ABC):
    """Abstract base for evidence retention adapters."""

    @abstractmethod
    def write(
        self,
        evidence_id: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> RetentionResult:
        """Write-once evidence storage.  Rejects duplicates."""
        ...

    @abstractmethod
    def read(self, evidence_id: str) -> EvidenceRecord | None:
        """Read by immutable evidence ID."""
        ...

    @abstractmethod
    def exists(self, evidence_id: str) -> bool:
        """Check if evidence exists."""
        ...

    @abstractmethod
    def verify_checksum(self, evidence_id: str) -> bool:
        """Verify stored content matches its SHA-256."""
        ...


# ---------------------------------------------------------------------------
# In-memory adapter (testing)
# ---------------------------------------------------------------------------


class InMemoryRetention(EvidenceRetention):
    """Write-once in-memory evidence store for testing."""

    def __init__(self) -> None:
        self._store: dict[str, EvidenceRecord] = {}

    def write(
        self,
        evidence_id: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> RetentionResult:
        if evidence_id in self._store:
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error=f"Duplicate evidence_id: {evidence_id}",
            )
        sha = hashlib.sha256(payload.encode()).hexdigest()
        record = EvidenceRecord(
            evidence_id=evidence_id,
            content_sha256=sha,
            payload=payload,
            metadata=metadata or {},
            retention_status="persisted",
        )
        self._store[evidence_id] = record
        return RetentionResult(
            success=True,
            evidence_id=evidence_id,
            content_sha256=sha,
            retention_status="persisted",
        )

    def read(self, evidence_id: str) -> EvidenceRecord | None:
        return self._store.get(evidence_id)

    def exists(self, evidence_id: str) -> bool:
        return evidence_id in self._store

    def verify_checksum(self, evidence_id: str) -> bool:
        rec = self._store.get(evidence_id)
        if rec is None:
            return False
        actual = hashlib.sha256(rec.payload.encode()).hexdigest()
        return actual == rec.content_sha256


# ---------------------------------------------------------------------------
# Disabled / unconfigured adapter (fail-closed production default)
# ---------------------------------------------------------------------------


class DisabledRetention(EvidenceRetention):
    """Fails closed when no retention backend is configured."""

    def write(
        self,
        evidence_id: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> RetentionResult:
        return RetentionResult(
            success=False,
            evidence_id=evidence_id,
            content_sha256="",
            retention_status="unavailable",
            error="No retention backend configured",
        )

    def read(self, evidence_id: str) -> EvidenceRecord | None:
        return None

    def exists(self, evidence_id: str) -> bool:
        return False

    def verify_checksum(self, evidence_id: str) -> bool:
        return False


# ---------------------------------------------------------------------------
# Temp-directory adapter (integration testing)
# ---------------------------------------------------------------------------


class TempDirRetention(EvidenceRetention):
    """Write-once temp-directory evidence store for integration testing.

    Not production-durable.  Must never set durable_retention_verified=true.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        import tempfile

        self._dir = (base_dir or Path(tempfile.mkdtemp(prefix="geo62-ev-"))).resolve()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, evidence_id: str) -> None:
        """Reject invalid IDs: traversal, null bytes, non-canonical."""
        if "\x00" in evidence_id:
            raise ValueError("Evidence ID contains null byte")
        if not _EVIDENCE_ID_RE.match(evidence_id):
            raise ValueError(
                f"Invalid evidence ID format: {evidence_id!r}; "
                f"must match {_EVIDENCE_ID_RE.pattern}"
            )

    def _safe_path(self, evidence_id: str) -> Path:
        """Return the file path after containment and symlink checks."""
        self._validate_id(evidence_id)
        raw = self._dir / f"{evidence_id}.json"
        target = raw.resolve()
        # Containment: resolved path must be under base dir
        try:
            target.relative_to(self._dir)
        except ValueError:
            raise ValueError(
                "Evidence path escapes base directory"
            )
        # Check for symlinks in the raw path components
        # (before resolution, so we catch the actual symlink)
        check = self._dir
        for part in Path(evidence_id).parts:
            check = check / part
            if check.is_symlink():
                raise ValueError(
                    f"Symlink component detected: {part}"
                )
        # Also check the .json file itself (os.path.lexists catches dangling symlinks)
        if os.path.lexists(str(raw)) and os.path.islink(str(raw)):
            raise ValueError(
                f"Symlink target detected: {evidence_id}.json"
            )
        return target

    @staticmethod
    def _write_all(fd: int, data: bytes) -> None:
        """Write all bytes to *fd*, raising on partial write."""
        written = 0
        total = len(data)
        while written < total:
            n = os.write(fd, data[written:])
            if n == 0:
                raise OSError("os.write returned 0")
            written += n

    @staticmethod
    def _fsync_fd(fd: int) -> None:
        """fsync an open file descriptor."""
        os.fsync(fd)

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        """fsync the parent directory of *path*."""
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    @staticmethod
    def _same_file(fd: int, path: Path) -> bool:
        """True when *path* names exactly the file *fd* is open on.

        Identity is decided on (st_dev, st_ino), never on the string: a path
        that merely looks plausible is not the file.
        """
        try:
            a = os.fstat(fd)
            b = os.stat(path)
        except OSError:
            return False
        return a.st_ino == b.st_ino and a.st_dev == b.st_dev

    def _open_temp(self) -> tuple[int, Path | None]:
        """Create the unique temp file, returning (fd, its real path).

        Two strategies, in order.

        1. Linux: create a fixed-name placeholder with O_CREAT|O_EXCL and
           resolve the descriptor's real path through ``/proc/self/fd``.
        2. Everywhere else: a bounded search for an unused random name.

        Strategy 1 must be *verified*, not assumed. ``os.path.realpath`` does
        not raise on a path that does not exist - it returns the input
        unchanged - so on any platform without ``/proc`` (macOS, BSD, some
        containers) the resolution silently yields a path naming no file. Two
        consequences followed while this was trusted: the placeholder was never
        unlinked, because the cleanup unlinked the phantom path instead; and
        ``os.link`` could never publish from it, so the atomic hard-link publish
        was silently disabled and every write fell through to the O_EXCL
        fallback. The inode check below is what makes strategy 1 fail loudly
        into strategy 2 rather than quietly into a half-working path.

        Leaves no residue on any outcome: a placeholder this call created is
        unlinked before strategy 2 runs. A placeholder created by a concurrent
        writer is never touched - that writer owns it.
        """
        placeholder = self._dir / ".tmp"
        fd = -1
        created = False
        try:
            fd = os.open(
                str(placeholder),
                os.O_RDWR | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
            candidate = Path(os.path.realpath(f"/proc/self/fd/{fd}"))
            if self._same_file(fd, candidate):
                return fd, candidate
        except (OSError, AttributeError):
            pass

        # Strategy 1 unavailable or unverifiable: discard what we made.
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
            fd = -1
        if created:
            try:
                placeholder.unlink(missing_ok=True)
            except OSError:
                pass

        # Strategy 2: named temp, bounded retry.
        import random
        import string
        for _ in range(50):
            name = "ev-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=16)) + ".tmp"
            candidate = self._dir / name
            try:
                fd = os.open(
                    str(candidate),
                    os.O_RDWR | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                continue
            except OSError:
                return -1, None
            return fd, candidate
        return -1, None

    def write(
        self,
        evidence_id: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> RetentionResult:
        """Write-once evidence with POSIX O_CREAT|O_EXCL atomicity.

        Strategy:
        1. Create a unique temporary file via O_CREAT|O_EXCL.
        2. Write all canonical bytes through an explicit file descriptor.
        3. fsync the temporary descriptor before close.
        4. Publish via ``os.link(temp, final)`` — atomic and fails with
           EEXIST if the final name already exists.
        5. If hard links are unavailable (Windows, some mounted FSes),
           fall back to ``os.open(final, O_CREAT|O_EXCL)`` which still
           guarantees no-overwrite but has a small TOCTOU window.
        6. fsync the parent directory after successful publish.
        7. Unlink the temporary file in a ``finally`` block.
        """
        try:
            final_path = self._safe_path(evidence_id)
        except ValueError as exc:
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error=str(exc),
            )

        sha = hashlib.sha256(payload.encode()).hexdigest()
        try:
            record = EvidenceRecord(
                evidence_id=evidence_id,
                content_sha256=sha,
                payload=payload,
                metadata=metadata or {},
                retention_status="persisted",
            )
            content_bytes = record.model_dump_json(indent=2).encode("utf-8")
        except Exception as exc:
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error=f"Evidence serialisation failed: {type(exc).__name__}",
            )

        # Step 1: create unique temp via O_CREAT|O_EXCL
        tmp_fd, tmp_path = self._open_temp()
        if tmp_fd < 0 or tmp_path is None:
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error="Could not create unique temporary file",
            )

        try:
            # Step 2: write all bytes
            self._write_all(tmp_fd, content_bytes)

            # Step 3: fsync temp descriptor
            self._fsync_fd(tmp_fd)

            # Step 4: publish via os.link (atomic, no-overwrite)
            published = False
            try:
                os.link(str(tmp_path), str(final_path))
                published = True
                self._fsync_dir(final_path)
            except OSError:
                # os.link unsupported or EEXIST — fall back to O_EXCL
                try:
                    pub_fd = os.open(
                        str(final_path),
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o600,
                    )
                    try:
                        self._write_all(pub_fd, content_bytes)
                        self._fsync_fd(pub_fd)
                    finally:
                        os.close(pub_fd)
                    published = True
                    self._fsync_dir(final_path)
                except FileExistsError:
                    # EEXIST → duplicate, not an error in the write path
                    return RetentionResult(
                        success=False,
                        evidence_id=evidence_id,
                        content_sha256="",
                        retention_status="failed",
                        error=f"Duplicate evidence_id: {evidence_id}",
                    )
                except OSError as exc:
                    return RetentionResult(
                        success=False,
                        evidence_id=evidence_id,
                        content_sha256="",
                        retention_status="failed",
                        error=f"Retention write failed: {type(exc).__name__}",
                    )

            if published:
                return RetentionResult(
                    success=True,
                    evidence_id=evidence_id,
                    content_sha256=sha,
                    retention_status="persisted",
                )
            # Should not reach here, but fail closed
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error="Publish did not complete",
            )
        except OSError as exc:
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error=f"Retention write failed: {type(exc).__name__}",
            )
        finally:
            # Step 7: always close descriptor and unlink temp
            try:
                os.close(tmp_fd)
            except OSError:
                pass
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def read(self, evidence_id: str) -> EvidenceRecord | None:
        try:
            p = self._safe_path(evidence_id)
        except ValueError:
            return None
        if not p.exists():
            return None
        return EvidenceRecord.model_validate_json(p.read_text(encoding="utf-8"))

    def exists(self, evidence_id: str) -> bool:
        try:
            p = self._safe_path(evidence_id)
        except ValueError:
            return False
        return p.exists()

    def verify_checksum(self, evidence_id: str) -> bool:
        rec = self.read(evidence_id)
        if rec is None:
            return False
        actual = hashlib.sha256(rec.payload.encode()).hexdigest()
        return actual == rec.content_sha256


# ---------------------------------------------------------------------------
# S3 Object Lock adapter (durable retention)
# ---------------------------------------------------------------------------


class S3ObjectLockRetention(EvidenceRetention):
    """Durable, immutable retention backed by S3 Object Lock in COMPLIANCE mode.

    This is the only backend in this module that satisfies
    ``durable_retention_verified``.  ``InMemoryRetention`` and
    ``TempDirRetention`` are write-once but not durable; ``DisabledRetention``
    persists nothing.

    Fail-closed properties:

    - The bucket must have versioning **and** Object Lock enabled.  Neither is
      assumed; both are read back before anything is written.
    - The write is rejected if an object already exists under the key
      (write-once), and if the bucket already holds a different payload for the
      same ``evidence_id``.
    - After the write, ``ObjectLockMode`` and ``ObjectLockRetainUntilDate`` are
      read back from the stored version.  A mode that is not ``COMPLIANCE`` or
      a retain-until earlier than requested is a failure, not a warning — an
      object written without an enforced lock is not retained evidence.
    - ``retain_days`` must meet ``MIN_RETENTION_DAYS``.  A shorter horizon is
      rejected rather than silently accepted.

    The S3 client is injected rather than constructed, so the adapter is
    testable without network access and adds no dependency of its own.  Any
    object exposing the botocore/boto3 S3 client surface works; see
    :meth:`from_botocore` for the runtime factory.
    """

    #: Retention floor for controlled-pilot evidence.
    MIN_RETENTION_DAYS = 365

    def __init__(
        self,
        client: object,
        bucket: str,
        *,
        prefix: str = "controlled-pilot",
        retain_days: int = MIN_RETENTION_DAYS,
    ) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        if retain_days < self.MIN_RETENTION_DAYS:
            raise ValueError(
                f"retain_days {retain_days} is below the "
                f"{self.MIN_RETENTION_DAYS}-day retention floor"
            )
        self._client = client
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._retain_days = retain_days

    @classmethod
    def from_botocore(
        cls,
        bucket: str,
        *,
        region: str | None = None,
        prefix: str = "controlled-pilot",
        retain_days: int = MIN_RETENTION_DAYS,
    ) -> "S3ObjectLockRetention":
        """Build an adapter over a botocore S3 client.

        ``botocore`` is already a project dependency; ``boto3`` is not required.
        """
        import botocore.session  # local import: keeps the module import-light

        session = botocore.session.get_session()
        client = session.create_client("s3", region_name=region)
        return cls(client, bucket, prefix=prefix, retain_days=retain_days)

    # -- internals ---------------------------------------------------------

    def _key(self, evidence_id: str) -> str:
        return f"{self._prefix}/{evidence_id}.json" if self._prefix else f"{evidence_id}.json"

    def _assert_bucket_is_lockable(self) -> None:
        """Fail closed unless versioning and Object Lock are both enabled."""
        versioning = self._client.get_bucket_versioning(Bucket=self._bucket)  # type: ignore[attr-defined]
        if versioning.get("Status") != "Enabled":
            raise RuntimeError(
                f"bucket {self._bucket!r} does not have versioning enabled"
            )
        lock = self._client.get_object_lock_configuration(Bucket=self._bucket)  # type: ignore[attr-defined]
        enabled = lock.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled")
        if enabled != "Enabled":
            raise RuntimeError(
                f"bucket {self._bucket!r} does not have Object Lock enabled"
            )

    # -- EvidenceRetention -------------------------------------------------

    def write(
        self,
        evidence_id: str,
        payload: str,
        metadata: dict[str, str] | None = None,
    ) -> RetentionResult:
        if not _EVIDENCE_ID_RE.match(evidence_id):
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256="",
                retention_status="failed",
                error="invalid evidence_id",
            )
        digest = hashlib.sha256(payload.encode()).hexdigest()
        key = self._key(evidence_id)

        try:
            self._assert_bucket_is_lockable()

            if self.exists(evidence_id):
                return RetentionResult(
                    success=False,
                    evidence_id=evidence_id,
                    content_sha256=digest,
                    retention_status="failed",
                    error="evidence_id already retained (write-once)",
                )

            from datetime import datetime, timedelta, timezone

            retain_until = datetime.now(timezone.utc) + timedelta(
                days=self._retain_days
            )
            put = self._client.put_object(  # type: ignore[attr-defined]
                Bucket=self._bucket,
                Key=key,
                Body=payload.encode(),
                ContentType="application/json",
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=retain_until,
                Metadata={**(metadata or {}), "content-sha256": digest},
            )
            version_id = put.get("VersionId")
            if not version_id:
                raise RuntimeError("put_object returned no VersionId")

            # Read the lock back: an unenforced object is not retained evidence.
            head = self._client.head_object(  # type: ignore[attr-defined]
                Bucket=self._bucket, Key=key, VersionId=version_id
            )
            if head.get("ObjectLockMode") != "COMPLIANCE":
                raise RuntimeError(
                    f"stored object lock mode is {head.get('ObjectLockMode')!r}, "
                    "not COMPLIANCE"
                )
            actual_until = head.get("ObjectLockRetainUntilDate")
            if actual_until is None or actual_until < retain_until:
                raise RuntimeError(
                    "stored retain-until is earlier than requested"
                )
        except Exception as exc:  # noqa: BLE001 — any failure is a failure
            return RetentionResult(
                success=False,
                evidence_id=evidence_id,
                content_sha256=digest,
                retention_status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )

        return RetentionResult(
            success=True,
            evidence_id=evidence_id,
            content_sha256=digest,
            retention_status="persisted",
        )

    def read(self, evidence_id: str) -> EvidenceRecord | None:
        if not _EVIDENCE_ID_RE.match(evidence_id):
            return None
        try:
            obj = self._client.get_object(  # type: ignore[attr-defined]
                Bucket=self._bucket, Key=self._key(evidence_id)
            )
            body = obj["Body"].read()
        except Exception:  # noqa: BLE001 — absent or unreachable reads as None
            return None
        payload = body.decode() if isinstance(body, bytes) else str(body)
        return EvidenceRecord(
            evidence_id=evidence_id,
            content_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            payload=payload,
            metadata={k: str(v) for k, v in (obj.get("Metadata") or {}).items()},
            retention_status="persisted",
        )

    def exists(self, evidence_id: str) -> bool:
        if not _EVIDENCE_ID_RE.match(evidence_id):
            return False
        try:
            self._client.head_object(  # type: ignore[attr-defined]
                Bucket=self._bucket, Key=self._key(evidence_id)
            )
        except Exception:  # noqa: BLE001 — treat any failure as absent
            return False
        return True

    def verify_checksum(self, evidence_id: str) -> bool:
        rec = self.read(evidence_id)
        if rec is None:
            return False
        stored = (rec.metadata or {}).get("content-sha256")
        actual = hashlib.sha256(rec.payload.encode()).hexdigest()
        if stored and stored != actual:
            return False
        return actual == rec.content_sha256
