"""WP-C: Versioned, deterministic smoke evidence record (GEO-62).

Contains only status and provenance metadata.  Never stores tokens,
cookies, authorization headers, provider response bodies or local
filesystem paths.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = "geo-62-smoke-evidence-v2"
_GIT_SHA_RE = r"^[0-9a-f]{40}$"


class SmokeEvidence(BaseModel, frozen=True):
    """Machine-readable evidence record for a controlled-pilot smoke."""

    schema_version: str = SCHEMA_VERSION
    verification_id: str
    release_commit_sha: str
    source_tree_dirty: bool
    timestamp_utc: str
    environment_name: str
    endpoint: str
    target_hostname: str
    request_method: str
    response_status: int
    response_content_type: str
    response_byte_count: int
    latency_ms: float
    authentication_attempted: bool
    authentication_succeeded: bool
    transport_verified: bool
    application_response_verified: bool
    # --- v2: the three GEO-62 authenticated-smoke assertions ---
    # None = the assertion was not attempted, never "assumed true".
    unauthenticated_access_denied: bool | None = None
    deployed_git_sha: str = ""
    release_sha_match: bool | None = None
    golden_verification: Literal["PASS", "FAIL", "NOT_RUN"] = "NOT_RUN"
    retention_status: Literal["pending", "persisted", "failed", "unavailable"]
    evidence_sha256: str = ""
    limitations: list[str] = Field(default_factory=list)
    runtime_live_verified: Literal[False] = False
    production_eligible: Literal[False] = False

    def canonical_payload(self) -> str:
        """Deterministic canonical JSON for hashing.

        Excludes ``evidence_sha256`` itself to avoid circularity.
        """
        d = self.model_dump(mode="json")
        d.pop("evidence_sha256", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        """SHA-256 of the canonical payload."""
        return hashlib.sha256(self.canonical_payload().encode()).hexdigest()

    def with_hash(self) -> SmokeEvidence:
        """Return a copy with ``evidence_sha256`` populated."""
        h = self.compute_hash()
        return self.model_copy(update={"evidence_sha256": h})

    def verify_hash(self) -> bool:
        """Check that the stored hash matches recomputation."""
        return self.evidence_sha256 == self.compute_hash()


def build_smoke_evidence(
    *,
    verification_id: str,
    release_commit_sha: str,
    source_tree_dirty: bool,
    environment_name: str,
    endpoint: str,
    target_hostname: str,
    request_method: str,
    response_status: int,
    response_content_type: str,
    response_byte_count: int,
    latency_ms: float,
    authentication_attempted: bool,
    authentication_succeeded: bool,
    transport_verified: bool,
    application_response_verified: bool,
    retention_status: Literal["pending", "persisted", "failed", "unavailable"],
    limitations: list[str] | None = None,
    unauthenticated_access_denied: bool | None = None,
    deployed_git_sha: str = "",
    release_sha_match: bool | None = None,
    golden_verification: Literal["PASS", "FAIL", "NOT_RUN"] = "NOT_RUN",
) -> SmokeEvidence:
    """Build a hash-verified smoke evidence record."""
    ev = SmokeEvidence(
        verification_id=verification_id,
        release_commit_sha=release_commit_sha,
        source_tree_dirty=source_tree_dirty,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        environment_name=environment_name,
        endpoint=endpoint,
        target_hostname=target_hostname,
        request_method=request_method,
        response_status=response_status,
        response_content_type=response_content_type,
        response_byte_count=response_byte_count,
        latency_ms=latency_ms,
        authentication_attempted=authentication_attempted,
        authentication_succeeded=authentication_succeeded,
        transport_verified=transport_verified,
        application_response_verified=application_response_verified,
        retention_status=retention_status,
        limitations=limitations or [],
        unauthenticated_access_denied=unauthenticated_access_denied,
        deployed_git_sha=deployed_git_sha,
        release_sha_match=release_sha_match,
        golden_verification=golden_verification,
    )
    return ev.with_hash()
