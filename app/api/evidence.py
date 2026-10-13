"""Evidence API (WP-3): retrieve, verify and export one audit record.

* ``GET /v1/evidence/{audit_id}`` — identity, integrity, run, source manifest
  and limits blocks (``app.services.evidence_service``).
* ``GET /v1/evidence/{audit_id}/verify`` — recompute the record hash and the
  organisation's chain now.
* ``GET /v1/evidence/{audit_id}/export`` — single-file JSON evidence package.

Scope ``evidence:read``. The organisation comes from the authenticated
principal. Another organisation's ``audit_id`` returns the same ``404`` as an
unknown one — never ``403`` — so its existence does not leak. Without a
database the endpoints refuse with ``503 AUDIT_STORE_UNAVAILABLE``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.api.audit_chain import get_audit_trail_store
from app.api.deps import require_scopes
from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.security import Principal
from app.services.audit_trail import compute_record_hash
from app.services.evidence_service import build_evidence, build_export
from app.services.release_manifest import build_release_manifest
from app.storage.audit_trail_store import PostgresAuditTrailStore, SealedRecord
from app.storage.run_repository import RunRecord, RunRepository

router = APIRouter()


def _not_found(audit_id: str) -> GeoRiskApiError:
    return GeoRiskApiError(
        code=codes.NOT_FOUND,
        message="Unknown audit_id.",
        status_code=404,
        details={"audit_id": audit_id},
    )


async def _load(
    audit_id: str, principal: Principal, store: PostgresAuditTrailStore
) -> SealedRecord:
    sealed = await store.get_sealed(audit_id, organisation_id=principal.organisation_id)
    if sealed is None:
        raise _not_found(audit_id)
    return sealed


async def _run_for(sealed: SealedRecord, organisation_id: str) -> RunRecord | None:
    if sealed.run_id is None:
        return None
    from app.db.session import get_session_factory

    async with get_session_factory()() as session:
        return await RunRepository(session).get_run(sealed.run_id, organisation_id=organisation_id)


async def _evidence(audit_id: str, principal: Principal, store: PostgresAuditTrailStore) -> tuple[dict[str, Any], SealedRecord]:
    sealed = await _load(audit_id, principal, store)
    chain = await store.verify_chain_report(principal.organisation_id)
    run = await _run_for(sealed, principal.organisation_id)
    evidence = build_evidence(
        sealed=sealed, chain=chain, run=run, release=build_release_manifest(settings)
    )
    return evidence, sealed


@router.get("/evidence/{audit_id}")
async def get_evidence(
    audit_id: str,
    principal: Principal = Depends(require_scopes("evidence:read")),
    store: PostgresAuditTrailStore = Depends(get_audit_trail_store),
) -> dict[str, Any]:
    evidence, _ = await _evidence(audit_id, principal, store)
    return evidence


@router.get("/evidence/{audit_id}/verify")
async def verify_evidence(
    audit_id: str,
    principal: Principal = Depends(require_scopes("evidence:read")),
    store: PostgresAuditTrailStore = Depends(get_audit_trail_store),
) -> dict[str, Any]:
    sealed = await _load(audit_id, principal, store)
    chain = await store.verify_chain_report(principal.organisation_id)
    record_hash_valid = (
        compute_record_hash(sealed.record.prev_hash, sealed.payload) == sealed.record.record_hash
    )
    intact = record_hash_valid and chain.status == "intact"
    return {
        "audit_id": audit_id,
        "chain": "intact" if intact else "broken",
        "record_hash_valid": record_hash_valid,
        "chain_status": chain.status,
        "reason": chain.reason if chain.status != "intact" else (
            None if record_hash_valid else codes.EVIDENCE_RECORD_HASH_MISMATCH
        ),
        "first_bad_record_id": chain.record_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/evidence/{audit_id}/export")
async def export_evidence(
    audit_id: str,
    principal: Principal = Depends(require_scopes("evidence:read")),
    store: PostgresAuditTrailStore = Depends(get_audit_trail_store),
) -> dict[str, Any]:
    evidence, sealed = await _evidence(audit_id, principal, store)
    # No export timestamp: identical sealed inputs give a byte-identical package (INV-08).
    return build_export(evidence, sealed)


__all__ = ["router"]
