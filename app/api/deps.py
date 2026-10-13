"""Request authentication / authorization dependencies.

``require_scopes(*scopes)`` returns a FastAPI dependency that resolves the
caller's :class:`~app.core.security.Principal` and enforces the listed scopes.
When ``settings.auth_required`` is false (local/dev/test) the dependency
short-circuits to a wildcard :func:`local_principal` and never opens a database
session, so DB-less deployments and the existing suite keep working.
"""

from __future__ import annotations

from starlette.requests import Request

from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.security import Principal, local_principal


def extract_api_key(request: Request) -> str | None:
    """Read the key from ``Authorization: Bearer`` or ``X-API-Key``.

    Query-string keys are deliberately ignored so credentials never land in
    access logs or referrers.
    """
    header = request.headers.get("authorization")
    if header:
        parts = header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            return token or None
        return None
    key = request.headers.get("x-api-key")
    if key and key.strip():
        return key.strip()
    return None


async def get_principal(request: Request) -> Principal:
    """FastAPI dependency returning the resolved caller :class:`Principal`."""
    return await resolve_principal(request)


async def resolve_principal(request: Request) -> Principal:
    """Resolve and cache the caller principal on ``request.state``."""
    cached = getattr(request.state, "principal", None)
    if cached is not None:
        return cached

    if not settings.auth_required:
        principal = local_principal()
        request.state.principal = principal
        return principal

    raw = extract_api_key(request)
    if raw is None:
        raise GeoRiskApiError(
            code=codes.AUTHENTICATION_REQUIRED,
            message="An API key is required (Authorization: Bearer <key>).",
            status_code=401,
        )

    from app.db.session import get_session_factory
    from app.services.api_key_service import verify_api_key

    async with get_session_factory()() as session:
        principal = await verify_api_key(session, raw)
        if principal is not None:
            # Persist last_used_at; the session closes at the end of this block.
            await session.commit()

    if principal is None:
        raise GeoRiskApiError(
            code=codes.INVALID_API_KEY,
            message="The supplied API key is invalid, expired, or revoked.",
            status_code=401,
        )
    request.state.principal = principal
    return principal


def require_scopes(*required: str):
    """Build a dependency enforcing ``required`` scopes on the caller."""

    async def _dependency(request: Request) -> Principal:
        principal = await resolve_principal(request)
        missing = [scope for scope in required if not principal.has_scope(scope)]
        if missing:
            raise GeoRiskApiError(
                code=codes.INSUFFICIENT_SCOPE,
                message="The API key lacks a required scope.",
                status_code=403,
                details={"required": sorted(required), "missing": sorted(missing)},
            )
        return principal

    _dependency.__name__ = f"require_scopes_{'_'.join(required) or 'any'}"
    return _dependency


__all__ = [
    "extract_api_key",
    "get_principal",
    "require_scopes",
    "resolve_principal",
]
