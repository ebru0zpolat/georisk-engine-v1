"""API-key lifecycle: create, verify, revoke, list.

Plaintext keys are returned exactly once by :func:`create_api_key` and never
persisted — only the digest is stored. :func:`verify_api_key` rejects unknown,
malformed, revoked and expired credentials, so a key is only ever as live as its
row. See ``app.core.security`` for hashing and ``app.api.deps`` for the request
dependency that consumes this service.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    SCOPES,
    Principal,
    generate_api_key,
    hash_api_key,
)
from app.db.models import ApiKeyModel, OrganisationModel
from app.storage.api_key_repository import ApiKeyRepository

_GRANTABLE = frozenset(SCOPES)


def _digest(raw_key: str) -> str:
    return hash_api_key(raw_key, pepper=settings.api_key_pepper)


def validate_scopes(scopes: list[str]) -> list[str]:
    """Return de-duplicated scopes; raise ``ValueError`` on any unknown scope."""
    unknown = sorted({s for s in scopes if s not in _GRANTABLE})
    if unknown:
        raise ValueError(f"Unknown scope(s): {', '.join(unknown)}")
    # Preserve caller order, drop duplicates.
    seen: list[str] = []
    for scope in scopes:
        if scope not in seen:
            seen.append(scope)
    return seen


async def create_api_key(
    session: AsyncSession,
    *,
    organisation_id: str,
    scopes: list[str],
    label: str = "",
    ttl_days: int | None = None,
) -> tuple[str, ApiKeyModel]:
    """Create a key. Returns ``(plaintext, model)`` — show the plaintext once."""
    granted = validate_scopes(scopes)
    if not organisation_id.strip():
        raise ValueError("organisation_id must not be empty")
    if not _GRANTABLE.issuperset(granted):
        raise ValueError("unknown scope")

    await ensure_organisation(session, organisation_id, label=label)

    expires_at: datetime | None = None
    if ttl_days is not None:
        if ttl_days <= 0:
            raise ValueError("ttl_days must be a positive integer")
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    plaintext = generate_api_key()
    repo = ApiKeyRepository(session)
    key = await repo.create(
        organisation_id=organisation_id,
        label=label,
        scopes=sorted(set(scopes)),
        key_hash=_digest(plaintext),
    )
    key.expires_at = expires_at
    await session.flush()
    return plaintext, key


async def ensure_organisation(
    session: AsyncSession, organisation_id: str, *, label: str = ""
) -> OrganisationModel:
    """Insert the owning organisation row if it does not exist yet.

    Keys, cases and persisted state all carry an ``organisation_id``; this makes
    that id refer to a real ``organisations`` row. Idempotent, so callers can
    invoke it before every write without checking first.
    """
    existing = await session.get(OrganisationModel, organisation_id)
    if existing is not None:
        return existing
    organisation = OrganisationModel(id=organisation_id, name=label or organisation_id)
    session.add(organisation)
    await session.flush()
    return organisation


async def verify_api_key(session: AsyncSession, raw_key: str) -> Principal | None:
    """Resolve ``raw_key`` to a :class:`Principal`, or ``None`` if unusable."""
    if not raw_key:
        return None
    repo = ApiKeyRepository(session)
    key = await repo.get_by_hash(_digest(raw_key))
    if key is None:
        return None
    if key.revoked_at is not None:
        return None
    if key.expires_at is not None and _is_expired(key.expires_at):
        return None

    await repo.mark_used(key, when=datetime.now(timezone.utc))
    scopes = frozenset(str(scope) for scope in (key.scopes or []))
    return Principal(
        organisation_id=key.organisation_id,
        scopes=scopes,
        key_id=key.id,
        label=key.label or "",
    )


async def revoke_api_key(
    session: AsyncSession,
    key_id: str,
    *,
    organisation_id: str | None = None,
) -> bool:
    """Soft-revoke a key. Returns False if it does not exist (or is not owned)."""
    repo = ApiKeyRepository(session)
    key = await repo.get(key_id)
    if key is None:
        return False
    if organisation_id is not None and key.organisation_id != organisation_id:
        return False
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
    return True


async def list_api_keys(session: AsyncSession, organisation_id: str) -> list[ApiKeyModel]:
    return await ApiKeyRepository(session).list_for_organisation(organisation_id)


def _is_expired(value: datetime, *, now: datetime | None = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= moment


__all__ = [
    "SCOPES",
    "create_api_key",
    "ensure_organisation",
    "list_api_keys",
    "revoke_api_key",
    "validate_scopes",
    "verify_api_key",
]
