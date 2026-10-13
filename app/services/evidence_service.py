"""Evidence blocks for one audit record (WP-3, ``/v1/evidence``).

Everything here is derived from data: the sealed record, the organisation's
chain verification, the run row, and the release manifest. Nothing is written
by hand, and nothing is hidden: a broken chain, a missing run row, a missing
source manifest or a synthetic input is reported in ``limits`` and weakens
``integrity_status``; the record is still shown (INV-02, INV-11).

``integrity_status`` is ``intact`` only when the record hashes to its
``record_hash`` and the organisation's chain is ``intact``; otherwise
``broken``. It is a hash-consistency statement, deliberately not called
"verified": in the glossary, verification means independent recomputation
from sealed inputs (INV-07, INV-12), which this endpoint does not do. Whether
the number is validated or production-eligible comes from the release manifest,
in ``limits``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.core import error_codes as codes
from app.loss.horizon_scenarios import HORIZONS
from app.schemas.release_manifest import ReleaseManifest
from app.services.audit_trail import canonical_json, compute_record_hash
from app.storage.audit_trail_store import UNKNOWN_SOURCE_COMMIT, ChainVerification, SealedRecord
from app.storage.run_repository import RunRecord

EVIDENCE_FORMAT_VERSION = "evidence-v1"
HASH_RULE = "record_hash = sha256(prev_hash + canonical_json(payload)); canonical_json = sorted keys, separators (',', ':')"

#: Substrings that mark a declared input as synthetic (stub, fixture, synthetic
#: calibration). Matching is on the recorded source id, version and catalogue
#: source; a match adds SYNTHETIC_INPUTS_PRESENT and never removes a limit.
_SYNTHETIC_MARKERS = ("stub", "synthetic", "fixture")


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_synthetic(*parts: object) -> bool:
    text = " ".join(str(part).lower() for part in parts if part is not None)
    return any(marker in text for marker in _SYNTHETIC_MARKERS)


def manifest_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The record's WP-4 source manifest (empty when the record carries none)."""
    return [dict(item) for item in payload.get("sources") or []]


def synthetic_inputs(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Synthetic inputs: from the source manifest when present, else from names.

    With a manifest, records in state ``synthetic`` — or whose id/version carries
    a synthetic marker — are listed. A record without one falls back to matching
    declared source names/versions.
    """
    manifest = manifest_records(payload)
    if manifest:
        return [
            {"source": str(item.get("source_id")), "version": str(item.get("version", ""))}
            for item in manifest
            if item.get("state") == "synthetic"
            or _is_synthetic(item.get("source_id"), item.get("version"))
        ]
    found: list[dict[str, str]] = []
    for source, version in sorted(dict(payload.get("data_versions") or {}).items()):
        if _is_synthetic(source, version):
            found.append({"source": str(source), "version": str(version)})
    params = dict(payload.get("parameters") or {})
    catalogue_source = params.get("catalogue_source")
    if catalogue_source is not None and _is_synthetic(catalogue_source):
        found.append(
            {
                "source": f"catalogue:{params.get('catalogue_id', 'unknown')}",
                "version": str(params.get("catalogue_version", "unknown")),
                "basis": str(catalogue_source),
            }
        )
    return found


def horizon_block(payload: dict[str, Any]) -> dict[str, Any]:
    params = dict(payload.get("parameters") or {})
    if "horizons" in params or "horizon_status" in params:
        available = sorted(str(h) for h in params.get("horizons") or [])
        status = str(params.get("horizon_status") or "recorded")
    else:
        available = []
        status = "not_recorded"
    missing = [h for h in HORIZONS if h not in available]
    return {
        "expected": list(HORIZONS),
        "available": available,
        "missing": missing,
        "status": status,
        "method": params.get("horizon_method"),
    }


def build_evidence(
    *,
    sealed: SealedRecord,
    chain: ChainVerification,
    run: RunRecord | None,
    release: ReleaseManifest,
) -> dict[str, Any]:
    payload = sealed.payload
    record = sealed.record
    limit_codes: list[str] = []

    record_hash_valid = compute_record_hash(record.prev_hash, payload) == record.record_hash
    if not record_hash_valid:
        limit_codes.append(codes.EVIDENCE_RECORD_HASH_MISMATCH)
    if chain.status != "intact":
        limit_codes.append(codes.EVIDENCE_CHAIN_NOT_INTACT)

    run_id = sealed.run_id
    if run_id is None:
        limit_codes.append(codes.EVIDENCE_NOT_FROM_RUN)
    elif run is None:
        limit_codes.append(codes.EVIDENCE_RUN_ROW_MISSING)

    data_versions = dict(payload.get("data_versions") or {})
    params = dict(payload.get("parameters") or {})
    country_pack = params.get("country_pack") or data_versions.get("country_pack")
    if country_pack is None:
        limit_codes.append(codes.COUNTRY_PACK_NOT_RECORDED)
    model_version = params.get("model_version") or data_versions.get("model")
    if model_version is None:
        limit_codes.append(codes.MODEL_VERSION_NOT_RECORDED)
    if sealed.source_commit == UNKNOWN_SOURCE_COMMIT:
        limit_codes.append(codes.SOURCE_COMMIT_UNKNOWN)

    manifest = manifest_records(payload)
    blocked = [item for item in manifest if item.get("state") == "blocked"]
    degraded = [item for item in manifest if item.get("state") == "degraded"]
    unclassified = [item for item in manifest if item.get("state") == "unclassified"]
    if not manifest:
        limit_codes.append(codes.SOURCE_MANIFEST_NOT_AVAILABLE)
    if blocked:
        limit_codes.append(codes.SOURCES_BLOCKED)
    if degraded:
        limit_codes.append(codes.SOURCES_DEGRADED)
    if unclassified:
        limit_codes.append(codes.SOURCES_UNCLASSIFIED)

    synthetic = synthetic_inputs(payload)
    if synthetic:
        limit_codes.append(codes.SYNTHETIC_INPUTS_PRESENT)
    horizons = horizon_block(payload)
    if horizons["missing"]:
        limit_codes.append(codes.HORIZONS_MISSING)
    if not release.production_eligible:
        limit_codes.append(codes.NOT_PRODUCTION_ELIGIBLE)
    if not release.gates.model_validated_for_use_case:
        limit_codes.append(codes.MODEL_NOT_VALIDATED_FOR_USE_CASE)

    integrity_ok = record_hash_valid and chain.status == "intact"
    return {
        "format": EVIDENCE_FORMAT_VERSION,
        "audit_id": record.record_id,
        "organisation_id": sealed.organisation_id,
        "run_id": run_id,
        "integrity_status": "intact" if integrity_ok else "broken",
        "identity": {
            "model_version": model_version,
            "methodology_version": record.methodology_version,
            "data_versions": data_versions,
            "country_pack": country_pack,
            "source_commit": sealed.source_commit,
            "generated_at": record.timestamp.isoformat(),
            "valuation_date": record.valuation_date.isoformat(),
        },
        "integrity": {
            "record_hash": record.record_hash,
            "prev_hash": record.prev_hash,
            "request_hash": sha256_of(payload.get("inputs") or {}),
            "response_hash": sha256_of(payload.get("outputs") or {}),
            "record_hash_valid": record_hash_valid,
            "hash_rule": HASH_RULE,
            "chain": {
                "status": chain.status,
                "reason": chain.reason,
                "first_bad_record_id": chain.record_id,
                "records": chain.records,
            },
        },
        "run": _run_block(run),
        "source_manifest": _manifest_block(manifest, blocked, data_versions),
        "limits": {
            "codes": limit_codes,
            "synthetic_inputs": synthetic,
            "horizons": horizons,
            "production_eligible": release.production_eligible,
            "model_validated_for_use_case": release.gates.model_validated_for_use_case,
            "release_decision": release.decision,
            "prohibited_uses": list(release.prohibited_uses),
        },
    }


def _manifest_block(
    manifest: list[dict[str, Any]], blocked: list[dict[str, Any]], data_versions: dict[str, Any]
) -> dict[str, Any]:
    if not manifest:
        return {
            "status": "not_available",
            "reason": codes.SOURCE_MANIFEST_NOT_AVAILABLE,
            "detail": "This record carries no per-source manifest; only declared source versions are known.",
            "declared_versions": data_versions,
        }
    return {
        "status": "recorded",
        "records": manifest,
        "blocked": [item.get("source_id") for item in blocked],
        "declared_versions": data_versions,
    }


def _run_block(run: RunRecord | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "run_id": run.run_id,
        "portfolio_id": run.portfolio_id,
        "valuation_date": run.valuation_date.isoformat() if run.valuation_date else None,
        "methodology_version": run.methodology_version,
        "analyzed_count": run.analyzed_count,
        "excluded_count": run.excluded_count,
        "created_at": run.created_at.isoformat(),
    }


def build_export(evidence: dict[str, Any], sealed: SealedRecord) -> dict[str, Any]:
    """Single-file evidence package; ``content_sha256`` covers ``content``.

    Deterministic for an unchanged record, chain and release (INV-08): no
    export timestamp is added, so repeated exports are byte-identical.
    """
    content = {
        "evidence": evidence,
        "record": {
            "payload": sealed.payload,
            "record_hash": sealed.record.record_hash,
            "prev_hash": sealed.record.prev_hash,
            "hash_rule": HASH_RULE,
        },
        "how_to_check_integrity": [
            "Recompute sha256(prev_hash + canonical_json(record.payload)) and compare with record.record_hash.",
            "Check record.payload.organisation_id and record.payload.run_id match evidence.organisation_id and evidence.run_id.",
            "Recompute content_sha256 = sha256(canonical_json(content)).",
            "Chain status reflects the organisation's chain at export; re-verify with GET /v1/evidence/{audit_id}/verify.",
        ],
    }
    return {"content": content, "content_sha256": sha256_of(content)}


__all__ = [
    "EVIDENCE_FORMAT_VERSION",
    "HASH_RULE",
    "build_evidence",
    "build_export",
    "horizon_block",
    "manifest_records",
    "sha256_of",
    "synthetic_inputs",
]
