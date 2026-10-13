"""Hashed API credentials, scopes and the request principal.

Layering: this module depends on nothing but the standard library, so it can be
imported by ``app.db.models`` (for :data:`DEFAULT_ORGANISATION_ID`) without a cycle.
DB access lives in ``app.storage.api_key_repository``; the FastAPI dependency
that turns a request into a :class:`Principal` lives in ``app.api.deps``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from typing import Iterable

#: Organisation for records written before tenancy existed (single-organisation default).
DEFAULT_ORGANISATION_ID = "default"

#: Grantable scope strings. ``SCOPES`` is the closed set; the wildcard ``*`` is
#: only handed out by the local (auth-disabled) principal. The five the plan
#: names — ``risk:read``, ``portfolio:write``, ``evidence:read``, ``reports:write``,
#: ``admin`` — are the coarse set; the remaining entries gate read/write per
#: resource family so a router can be narrowed without a new coarse scope.
SCOPES: tuple[str, ...] = (
    "portfolio:read",
    "portfolio:write",
    "risk:read",
    "cases:read",
    "cases:write",
    "reports:read",
    "reports:write",
    "data_sources:read",
    "connectors:read",
    "tiles:read",
    "validation:read",
    "validation:write",
    "demo:read",
    "demo:write",
    "scenario:write",
    "release:read",
    "evidence:read",
    "admin",
)

WILDCARD_SCOPE = "*"

_KEY_PREFIX = "grk_"


def generate_api_key() -> str:
    """Return a fresh plaintext key. Shown once; only its hash is stored."""
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def is_api_key_shaped(value: str) -> bool:
    """Cheap shape check before touching the database."""
    return isinstance(value, str) and value.startswith(_KEY_PREFIX) and len(value) > len(_KEY_PREFIX)


def hash_api_key(raw: str, *, pepper: str | None = None) -> str:
    """Return the 64-char hex digest stored for ``raw``.

    With a pepper, HMAC-SHA256; without, plain SHA-256 (local/test only). The
    digest is deterministic so a lookup by hash is a single indexed read.
    """
    if not raw:
        raise ValueError("API key must be non-empty")
    if pepper:
        return hmac.new(pepper.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_api_key_id() -> str:
    return f"key_{uuid.uuid4().hex[:24]}"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller for one request."""

    organisation_id: str
    scopes: frozenset[str]
    key_id: str | None = None
    label: str = ""

    @property
    def is_local(self) -> bool:
        return self.key_id == "local"

    def has_scope(self, scope: str) -> bool:
        """True if granted directly, by the wildcard, or ``x:read`` via ``x:write``.

        Write implies read within one resource family, so a key holding the
        plan's coarse ``portfolio:write`` or ``reports:write`` passes the
        router-level ``*:read`` gate in front of the write endpoints.
        """
        if WILDCARD_SCOPE in self.scopes or scope in self.scopes:
            return True
        family, _, action = scope.partition(":")
        return action == "read" and f"{family}:write" in self.scopes

    def missing_scopes(self, required: Iterable[str]) -> list[str]:
        return sorted(scope for scope in required if not self.has_scope(scope))


def local_principal(*, organisation_id: str = DEFAULT_ORGANISATION_ID) -> Principal:
    """Principal used when the API-key gate is disabled (local/dev/test)."""
    return Principal(
        organisation_id=organisation_id,
        scopes=frozenset({WILDCARD_SCOPE}),
        key_id="local",
        label="local",
    )


__all__ = [
    "DEFAULT_ORGANISATION_ID",
    "SCOPES",
    "WILDCARD_SCOPE",
    "Principal",
    "generate_api_key",
    "local_principal",
]
