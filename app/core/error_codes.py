"""Stable, machine-readable API error ``code`` strings (error envelope)."""

from __future__ import annotations

INVALID_COORDINATES = "INVALID_COORDINATES"
INVALID_ASSET = "INVALID_ASSET"
PRESET_NOT_FOUND = "PRESET_NOT_FOUND"
INVALID_BATCH = "INVALID_BATCH"
BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
TIMEOUT_ERROR = "TIMEOUT_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"
#: Per-point ORAS5 data gap: the store is reachable but this point has no
#: scorable series (land-masked, out of coverage, or too short for the
#: feature statistics). Batch rows with this code fail individually so valid
#: rows in the same request still succeed.
ORAS5_SERIES_UNSCORABLE = "ORAS5_SERIES_UNSCORABLE"
CONNECTOR_STUB_PROHIBITED = "CONNECTOR_STUB_PROHIBITED"
DATA_CENTRE_ASSESS_DISABLED = "DATA_CENTRE_ASSESS_DISABLED"
#: No API key was supplied (or the scheme was not ``Bearer``).
AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
#: The supplied API key is unknown, malformed, expired, or revoked.
INVALID_API_KEY = "INVALID_API_KEY"
#: A valid key lacks a scope the endpoint requires.
INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
#: The database-backed audit trail store is not configured (no DATABASE_URL).
AUDIT_STORE_UNAVAILABLE = "AUDIT_STORE_UNAVAILABLE"

# Audit-chain verification outcomes (WP-2). Reported in a 200 body, not as
# errors: a broken or empty chain is a finding about the evidence.
#: The organisation has no records in the database store. Not integrity.
AUDIT_CHAIN_EMPTY = "AUDIT_CHAIN_EMPTY"
#: A run could not be persisted: its run row and audit records were rolled
#: back together, so neither exists (WP-3 item 0).
RUN_PERSISTENCE_FAILED = "RUN_PERSISTENCE_FAILED"
#: Concurrent writers kept moving the organisation's chain tip; the run was
#: retried and still could not be linked. Nothing was persisted.
AUDIT_CHAIN_CONTENDED = "AUDIT_CHAIN_CONTENDED"
#: A run finished without writing any audit record, so it has no evidence and
#: is refused rather than stored as an unevidenced run.
RUN_WITHOUT_AUDIT_RECORD = "RUN_WITHOUT_AUDIT_RECORD"
# Evidence limits (WP-3). Reported in the evidence ``limits`` block; each one
# weakens what the evidence can support, none of them hides the record.
#: The stored record does not hash to its record_hash.
EVIDENCE_RECORD_HASH_MISMATCH = "EVIDENCE_RECORD_HASH_MISMATCH"
#: The organisation's chain does not verify (see the chain block's reason).
EVIDENCE_CHAIN_NOT_INTACT = "EVIDENCE_CHAIN_NOT_INTACT"
#: The record names a run whose run row is missing.
EVIDENCE_RUN_ROW_MISSING = "EVIDENCE_RUN_ROW_MISSING"
#: The record was not written by a persisted run (no run id sealed).
EVIDENCE_NOT_FROM_RUN = "EVIDENCE_NOT_FROM_RUN"
#: The record carries no per-source manifest (WP-4), e.g. a record type that
#: does not write one; only declared source versions are known.
SOURCE_MANIFEST_NOT_AVAILABLE = "SOURCE_MANIFEST_NOT_AVAILABLE"
#: At least one source was blocked (e.g. no verified licence) and fed no number.
SOURCES_BLOCKED = "SOURCES_BLOCKED"
#: At least one contributing source was only partially available.
SOURCES_DEGRADED = "SOURCES_DEGRADED"
#: At least one declared source version has no recorded retrieval path or
#: licence (``state=unclassified``); it was not licence-gated (WP-4 known gap).
SOURCES_UNCLASSIFIED = "SOURCES_UNCLASSIFIED"
#: A run was refused before computing: a source declared as feeding a number
#: has no verified commercial-use licence.
SOURCE_LICENCE_NOT_VERIFIED = "SOURCE_LICENCE_NOT_VERIFIED"
#: At least one declared input is a stub, fixture or synthetic calibration.
SYNTHETIC_INPUTS_PRESENT = "SYNTHETIC_INPUTS_PRESENT"
#: One or more forward horizons (2030/2050) are absent from the record.
HORIZONS_MISSING = "HORIZONS_MISSING"
#: The release is not production eligible (release manifest).
NOT_PRODUCTION_ELIGIBLE = "NOT_PRODUCTION_ELIGIBLE"
#: The model is not validated for a named use case (release manifest gate).
MODEL_NOT_VALIDATED_FOR_USE_CASE = "MODEL_NOT_VALIDATED_FOR_USE_CASE"
#: The record does not carry a model version distinct from its methodology.
MODEL_VERSION_NOT_RECORDED = "MODEL_VERSION_NOT_RECORDED"
#: The record does not name a country pack.
COUNTRY_PACK_NOT_RECORDED = "COUNTRY_PACK_NOT_RECORDED"
#: The producing code revision was not known when the record was sealed.
SOURCE_COMMIT_UNKNOWN = "SOURCE_COMMIT_UNKNOWN"
#: Genesis missing or duplicated, a branch, a cycle, or orphaned records.
AUDIT_CHAIN_STRUCTURE_BROKEN = "AUDIT_CHAIN_STRUCTURE_BROKEN"
#: A record's prev_hash does not match its predecessor's record_hash.
AUDIT_CHAIN_LINK_MISMATCH = "AUDIT_CHAIN_LINK_MISMATCH"
#: A record's stored hash does not match the hash recomputed from its payload.
AUDIT_CHAIN_HASH_MISMATCH = "AUDIT_CHAIN_HASH_MISMATCH"
#: A record's sealed organisation differs from the chain it is stored in.
AUDIT_CHAIN_OWNER_MISMATCH = "AUDIT_CHAIN_OWNER_MISMATCH"

OPENAPI_DOCUMENTED_ERROR_CODES: tuple[str, ...] = (
    INVALID_COORDINATES,
    INVALID_ASSET,
    PRESET_NOT_FOUND,
    INVALID_BATCH,
    BATCH_TOO_LARGE,
    VALIDATION_ERROR,
    NOT_FOUND,
    RATE_LIMIT_EXCEEDED,
    TIMEOUT_ERROR,
    INTERNAL_ERROR,
    ORAS5_SERIES_UNSCORABLE,
    CONNECTOR_STUB_PROHIBITED,
    DATA_CENTRE_ASSESS_DISABLED,
    AUTHENTICATION_REQUIRED,
    INVALID_API_KEY,
    INSUFFICIENT_SCOPE,
    AUDIT_STORE_UNAVAILABLE,
    RUN_PERSISTENCE_FAILED,
    AUDIT_CHAIN_CONTENDED,
    RUN_WITHOUT_AUDIT_RECORD,
)

__all__ = [
    "BATCH_TOO_LARGE",
    "CONNECTOR_STUB_PROHIBITED",
    "DATA_CENTRE_ASSESS_DISABLED",
    "INTERNAL_ERROR",
    "INVALID_ASSET",
    "INVALID_BATCH",
    "INVALID_COORDINATES",
    "NOT_FOUND",
    "OPENAPI_DOCUMENTED_ERROR_CODES",
    "ORAS5_SERIES_UNSCORABLE",
    "PRESET_NOT_FOUND",
    "RATE_LIMIT_EXCEEDED",
    "TIMEOUT_ERROR",
    "VALIDATION_ERROR",
]
