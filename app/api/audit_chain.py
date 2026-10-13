"""Audit-chain verification for the caller's organisation (WP-2).

``GET /v1/audit-chain/verify`` recomputes the caller's own chain in the
database store (:class:`~app.storage.audit_trail_store.PostgresAuditTrailStore`).
The organisation comes from the authenticated principal only — the endpoint
takes no organisation argument, so a caller cannot ask about another one.

Portfolio runs are persisted to this store together with their run rows
(WP-3, ``app.services.portfolio_run_service``) whenever a database is
configured. An empty chain is reported as ``empty``, never as ``intact``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_scopes
from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.security import Principal
from app.storage.audit_trail_store import PostgresAuditTrailStore

router = APIRouter()


def get_audit_trail_store() -> PostgresAuditTrailStore:
    """The database audit store; refuses with a code when no database is set."""
    if not settings.database_url:
        raise GeoRiskApiError(
            code=codes.AUDIT_STORE_UNAVAILABLE,
            message="The database audit trail store is not configured.",
            status_code=503,
        )
    from app.db.session import get_session_factory

    return PostgresAuditTrailStore(get_session_factory())


@router.get("/audit-chain/verify")
async def verify_audit_chain(
    principal: Principal = Depends(require_scopes("evidence:read")),
    store: PostgresAuditTrailStore = Depends(get_audit_trail_store),
) -> dict[str, Any]:
    result = await store.verify_chain_report(principal.organisation_id)
    limits = [codes.AUDIT_CHAIN_EMPTY] if result.status == "empty" else []
    return {
        "organisation_id": result.organisation_id,
        "chain": result.status,
        "records": result.records,
        "tip_hash": result.tip_hash,
        "reason": result.reason,
        "record_id": result.record_id,
        "limits": limits,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
