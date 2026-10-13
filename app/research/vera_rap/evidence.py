"""Immutable, domain-independent evidence primitive for VERA-RAP research.

This module is intentionally independent of GeoRisk's production evidence models.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class VerificationStatus(Enum):
    """An explicit assessment state; enum members have no string coercion."""

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"

    def __str__(self) -> str:
        raise TypeError("VerificationStatus cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("VerificationStatus cannot be used as an implicit boolean")


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _freeze_json(value: Any, path: str) -> Any:
    """Validate JSON-compatible data and recursively make containers immutable."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            frozen[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    raise ValueError(f"{path} must contain only JSON-compatible values")


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    # Equivalent offsets describe the same instant, so identity always uses UTC.
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(
    value: object, name: str, *, optional: bool = False
) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc


@dataclass(frozen=True, slots=True)
class Uncertainty:
    """Minimal descriptive uncertainty; it performs no probabilistic inference."""

    kind: str
    lower: float | None = None
    upper: float | None = None
    confidence: float | None = None
    method: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.kind, "uncertainty.kind")
        for name in ("lower", "upper", "confidence"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"uncertainty.{name} must be a finite number or null")
        if (self.lower is None) != (self.upper is None):
            raise ValueError("uncertainty bounds must both be present or both be null")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("uncertainty lower bound must not exceed upper bound")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("uncertainty confidence must be between 0 and 1")
        if self.method is not None:
            _required_text(self.method, "uncertainty.method")

    def to_dict(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in ("kind", "lower", "upper", "confidence", "method")
        }


@dataclass(frozen=True, slots=True)
class Provenance:
    """Machine-readable origin and derivation information."""

    source_identifier: str
    retrieval_mechanism: str
    artifact_content_hash: str
    transformation_ids: tuple[str, ...] = ()
    upstream_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required_text(self.source_identifier, "provenance.source_identifier")
        _required_text(self.retrieval_mechanism, "provenance.retrieval_mechanism")
        if not isinstance(self.artifact_content_hash, str) or not _SHA256_RE.fullmatch(
            self.artifact_content_hash
        ):
            raise ValueError(
                "provenance.artifact_content_hash must be a lowercase SHA-256 hex digest"
            )
        for name in ("transformation_ids", "upstream_evidence_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
            for item in getattr(self, name):
                _required_text(item, f"provenance.{name} item")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_identifier": self.source_identifier,
            "retrieval_mechanism": self.retrieval_mechanism,
            "artifact_content_hash": self.artifact_content_hash,
            "transformation_ids": list(self.transformation_ids),
            "upstream_evidence_ids": list(self.upstream_evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class EvidenceObject:
    """Canonical immutable record of evidence identity and epistemic state."""

    evidence_id: str
    evidence_type: str
    source_id: str
    source_uri: str | None
    content_hash: str
    retrieved_at: datetime
    observed_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    jurisdiction: Any
    spatial_scope: Any
    measurement: Any
    unit: str | None
    uncertainty: Uncertainty | None
    licence_status: str
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    provenance: Provenance = field(kw_only=True)
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "evidence_type", "source_id", "licence_status"):
            _required_text(getattr(self, name), name)
        if self.source_uri is not None:
            _required_text(self.source_uri, "source_uri")
            parsed = urlparse(self.source_uri)
            if not parsed.scheme or (
                parsed.scheme in {"http", "https"} and not parsed.netloc
            ):
                raise ValueError("source_uri must be an absolute URI")
        if not isinstance(self.content_hash, str) or not _SHA256_RE.fullmatch(
            self.content_hash
        ):
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
        retrieved = _timestamp(self.retrieved_at, "retrieved_at")
        for name in ("observed_at", "valid_from", "valid_until"):
            value = getattr(self, name)
            if value is not None:
                _timestamp(value, name)
        if self.observed_at is not None and self.observed_at > retrieved:
            raise ValueError("observed_at must not be later than retrieved_at")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must not be before valid_from")
        if self.unit is not None:
            _required_text(self.unit, "unit")
        if not isinstance(self.verification_status, VerificationStatus):
            raise ValueError(
                "verification_status must be a VerificationStatus enum member"
            )
        if not isinstance(self.provenance, Provenance):
            raise ValueError("provenance must be a Provenance object")
        if self.uncertainty is not None and not isinstance(
            self.uncertainty, Uncertainty
        ):
            raise ValueError("uncertainty must be an Uncertainty object or null")
        if self.provenance.source_identifier != self.source_id:
            raise ValueError("provenance source identifier must match source_id")
        if self.provenance.artifact_content_hash != self.content_hash:
            raise ValueError("provenance artifact hash must match content_hash")
        for name in ("jurisdiction", "spatial_scope", "measurement", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object or null")

    def canonical_dict(self) -> dict[str, Any]:
        """Return all semantic fields in their canonical JSON representation."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "source_id": self.source_id,
            "source_uri": self.source_uri,
            "content_hash": self.content_hash,
            "retrieved_at": _iso(self.retrieved_at),
            "observed_at": _iso(self.observed_at),
            "valid_from": _iso(self.valid_from),
            "valid_until": _iso(self.valid_until),
            "jurisdiction": _plain_json(self.jurisdiction),
            "spatial_scope": _plain_json(self.spatial_scope),
            "measurement": _plain_json(self.measurement),
            "unit": self.unit,
            "uncertainty": (
                None if self.uncertainty is None else self.uncertainty.to_dict()
            ),
            "licence_status": self.licence_status,
            "verification_status": self.verification_status.value,
            "provenance": self.provenance.to_dict(),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        """Serialize deterministically as compact UTF-8-compatible JSON."""
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def is_stale(self, *, at: datetime) -> bool:
        """Evaluate staleness at an explicit instant without changing this record."""
        evaluation_time = _timestamp(at, "at")
        return self.verification_status is VerificationStatus.STALE or (
            self.valid_until is not None and evaluation_time > self.valid_until
        )

    @classmethod
    def from_canonical_json(cls, serialized: str) -> EvidenceObject:
        """Reconstruct and fully validate an object from canonical JSON."""
        try:
            payload = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized evidence must be valid JSON") from exc
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError(
                "serialized evidence fields do not match the canonical schema"
            )
        try:
            status = VerificationStatus(payload["verification_status"])
            uncertainty = (
                None
                if payload["uncertainty"] is None
                else Uncertainty(**payload["uncertainty"])
            )
            provenance = Provenance(**payload["provenance"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "serialized evidence contains malformed epistemic state or provenance"
            ) from exc
        return cls(
            **{
                **payload,
                "retrieved_at": _parse_timestamp(
                    payload["retrieved_at"], "retrieved_at"
                ),
                "observed_at": _parse_timestamp(
                    payload["observed_at"], "observed_at", optional=True
                ),
                "valid_from": _parse_timestamp(
                    payload["valid_from"], "valid_from", optional=True
                ),
                "valid_until": _parse_timestamp(
                    payload["valid_until"], "valid_until", optional=True
                ),
                "verification_status": status,
                "uncertainty": uncertainty,
                "provenance": provenance,
            }
        )
