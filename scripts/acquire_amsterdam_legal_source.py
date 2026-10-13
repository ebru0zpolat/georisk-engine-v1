#!/usr/bin/env python3
"""Acquire the official Amsterdam Omgevingsplan (CVDR696291) from Overheid.nl.

Fetches the canonical legal publication artifact, computes dual SHA-256
hashes (raw artifact + normalized content), and saves the raw snapshot.

Three artifacts:
  A. pinned legal text /CVDR696291/15
  B. WTI /CVDR696291/15?show-wti=true
  C. amendment publication gmb-2026-243575

Fail-closed acquisition:
  validation failure => zero persistent mutation
  Files and manifest are written ONLY after build_provenance_entries()
  succeeds. No snapshot or manifest is touched before validation.

Usage:
    python scripts/acquire_amsterdam_legal_source.py
"""

from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Shared parsers from amsterdam_source
from app.nl_pilot.amsterdam_source import (
    _parse_wti_evidence,
    _parse_amendment_evidence,
    _derive_rule_mapping,
    compute_artifact_hash,
    compute_normalized_hash_html,
)

# Canonical Amsterdam Omgevingsplan — CVDR696291/15
CVDR_ID = "CVDR696291"
VERSION_NUMBER = 15
RESOLVED_REF = f"{CVDR_ID}/{VERSION_NUMBER}"
SOURCE_URL = f"https://lokaleregelgeving.overheid.nl/{CVDR_ID}/{VERSION_NUMBER}"
WTI_URL = f"{SOURCE_URL}?show-wti=true"
AUTHORITY = "Gemeente Amsterdam"
TITLE = (
    "Omgevingsplan gemeente Amsterdam — "
    "Paragraaf 4.4.2 Hemelwaterafvoer bij bouwwerken"
)
LICENSE_ID = "Public Domain Mark 1.0"

SNAPSHOT_DIR = Path("data/nl_pilot/snapshots/amsterdam-v1")
SNAPSHOT_FILENAME = f"amsterdam-omgevingsplan-{CVDR_ID.lower()}-v{VERSION_NUMBER}.raw.html"
WTI_FILENAME = f"amsterdam-omgevingsplan-{CVDR_ID.lower()}-v{VERSION_NUMBER}-wti.raw.html"
AMEND_FILENAME = "amsterdam-gmb-2026-243575-metadata.raw.html"
MANIFEST_PATH = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")

GMB_URL = "https://zoek.officielebekendmakingen.nl/gmb-2026-243575"


def fetch_url(url: str) -> tuple[bytes, str, str]:
    """Fetch URL, return (raw_bytes, content_type, retrieved_at)."""
    req = urllib.request.Request(
        url,
        headers={"Accept": "text/html", "User-Agent": "GeoRisk-Engine/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        ct = resp.headers.get("Content-Type", "")
        ts = datetime.datetime.utcnow().isoformat() + "Z"
    return raw, ct, ts


def build_provenance_entries(
    *,
    legal_bytes: bytes,
    legal_path: Path,
    legal_content_type: str,
    legal_retrieved_at: str,
    wti_bytes: bytes,
    wti_path: Path,
    wti_content_type: str,
    wti_retrieved_at: str,
    amendment_bytes: bytes,
    amendment_path: Path,
    amendment_content_type: str,
    amendment_retrieved_at: str,
) -> dict:
    """Build all three complete source entries from raw evidence bytes.

    Computes dual hashes, parses WTI/amendment facts, derives rule mapping,
    derives all verification gates. Fails closed if any gate is false.

    Returns:
        {
            "amsterdam-omgevingsplan-cvdr696291": {...},
            "amsterdam-omgevingsplan-cvdr696291-v15-wti": {...},
            "amsterdam-gmb-2026-243575-metadata": {...},
        }

    This is the single source of truth for manifest construction.
    main() and tests must both use this function.
    """
    # --- Hash all artifacts ---
    legal_sha = compute_artifact_hash(legal_bytes)
    legal_norm = compute_normalized_hash_html(legal_bytes)
    wti_sha = compute_artifact_hash(wti_bytes)
    wti_norm = compute_normalized_hash_html(wti_bytes)
    amend_sha = compute_artifact_hash(amendment_bytes)
    amend_norm = compute_normalized_hash_html(amendment_bytes)

    # --- Parse facts from evidence ---
    wti_facts = _parse_wti_evidence(wti_bytes)
    amend_facts = _parse_amendment_evidence(amendment_bytes)
    rule_ok = _derive_rule_mapping(legal_bytes)

    # --- Derive verification flags ---
    version_verified = wti_facts["version_number"] == VERSION_NUMBER
    effective_status_verified = (
        wti_facts["effective_from"] == "2026-06-19"
        and wti_facts["effective_until"] is None
        and wti_facts["regulatory_state"] == "current_in_force"
    )
    amendment_chain_verified = (
        wti_facts["amendment_publication"] == amend_facts["publication_id"]
        and amend_facts["publication_id"] == "gmb-2026-243575"
        and amend_facts["official_version_identifier"] == "CVDR696291_15"
        and amend_facts["decision_date"] == "2026-05-07"
        and amend_facts["publication_date"] == "2026-05-22"
    )

    # --- Fail closed: every gate must be true ---
    if not version_verified:
        raise RuntimeError("build_provenance_entries: version_verified=false")
    if not effective_status_verified:
        raise RuntimeError("build_provenance_entries: effective_status_verified=false")
    if not amendment_chain_verified:
        raise RuntimeError("build_provenance_entries: amendment_chain_verified=false")
    if not rule_ok:
        raise RuntimeError("build_provenance_entries: rule_mapping_verified=false")

    # --- Build primary legal source entry ---
    legal_entry = {
        "authority": AUTHORITY,
        "byte_length": len(legal_bytes),
        "collection": "regulatory_source",
        "content_type": legal_content_type,
        "cvdr_id": CVDR_ID,
        "version_number": wti_facts["version_number"],
        "resolved_version_ref": f"{CVDR_ID}/{wti_facts['version_number']}",
        "resolved_version_url": SOURCE_URL,
        "effective_from": wti_facts["effective_from"],
        "effective_until": wti_facts["effective_until"],
        "regulatory_state": wti_facts["regulatory_state"],
        "license_id": LICENSE_ID,
        "normalized_content_sha256": legal_norm,
        "artifact_sha256": legal_sha,
        "retrieved_at": legal_retrieved_at,
        "source_url": SOURCE_URL,
        "snapshot_path": str(legal_path),
        "title": TITLE,
        "latest_amendment_publication": wti_facts["amendment_publication"],
        "official_version_identifier": amend_facts["official_version_identifier"],
        "version_verified": version_verified,
        "effective_status_verified": effective_status_verified,
        "amendment_chain_verified": amendment_chain_verified,
        "rule_mapping_verified": rule_ok,
        "rule_mapping_version": f"{CVDR_ID}/{wti_facts['version_number']}",
    }

    # --- Build WTI entry ---
    wti_entry = {
        "authority": AUTHORITY,
        "byte_length": len(wti_bytes),
        "collection": "regulatory_metadata",
        "content_type": wti_content_type,
        "description": f"WTI/version metadata for {RESOLVED_REF} from Overheid.nl",
        "source_url": WTI_URL,
        "snapshot_path": str(wti_path),
        "artifact_sha256": wti_sha,
        "normalized_content_sha256": wti_norm,
    }

    # --- Build amendment entry ---
    amend_entry = {
        "authority": AUTHORITY,
        "byte_length": len(amendment_bytes),
        "collection": "regulatory_amendment",
        "content_type": amendment_content_type,
        "description": "Official amendment publication metadata for gmb-2026-243575",
        "source_url": GMB_URL,
        "snapshot_path": str(amendment_path),
        "artifact_sha256": amend_sha,
        "normalized_content_sha256": amend_norm,
        "publication_id": amend_facts["publication_id"],
        "decision_date": amend_facts["decision_date"],
        "publication_date": amend_facts["publication_date"],
        "official_version_identifier": amend_facts["official_version_identifier"],
        "regeling": amend_facts["official_version_identifier"],
    }

    return {
        "amsterdam-omgevingsplan-cvdr696291": legal_entry,
        "amsterdam-omgevingsplan-cvdr696291-v15-wti": wti_entry,
        "amsterdam-gmb-2026-243575-metadata": amend_entry,
    }


def main() -> None:
    # === 1. Fetch all three artifacts ===
    print(f"Fetching Amsterdam Omgevingsplan from {SOURCE_URL} ...")
    legal_bytes, legal_type, legal_retrieved = fetch_url(SOURCE_URL)
    print(f"  Legal bytes: {len(legal_bytes)}")

    print(f"\nFetching WTI metadata from {WTI_URL} ...")
    wti_bytes, wti_type, wti_retrieved = fetch_url(WTI_URL)
    print(f"  WTI bytes: {len(wti_bytes)}")

    print(f"\nFetching amendment metadata from {GMB_URL} ...")
    amend_bytes, amend_type, amend_retrieved = fetch_url(GMB_URL)
    print(f"  Amendment bytes: {len(amend_bytes)}")

    # === 2. Define intended final snapshot paths (NO WRITES YET) ===
    legal_path = SNAPSHOT_DIR / SNAPSHOT_FILENAME
    wti_path = SNAPSHOT_DIR / WTI_FILENAME
    amend_path = SNAPSHOT_DIR / AMEND_FILENAME

    # === 3. Validate all evidence BEFORE any file mutation ===
    # If build_provenance_entries raises, no snapshot or manifest is touched.
    entries = build_provenance_entries(
        legal_bytes=legal_bytes,
        legal_path=legal_path,
        legal_content_type=legal_type,
        legal_retrieved_at=legal_retrieved,
        wti_bytes=wti_bytes,
        wti_path=wti_path,
        wti_content_type=wti_type,
        wti_retrieved_at=wti_retrieved,
        amendment_bytes=amend_bytes,
        amendment_path=amend_path,
        amendment_content_type=amend_type,
        amendment_retrieved_at=amend_retrieved,
    )

    # === 4. Validation passed — NOW persist snapshots ===
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    legal_path.write_bytes(legal_bytes)
    print(f"\n  Saved: {legal_path}")
    wti_path.write_bytes(wti_bytes)
    print(f"  Saved: {wti_path}")
    amend_path.write_bytes(amend_bytes)
    print(f"  Saved: {amend_path}")

    # === 5. Persist manifest (last — atomic in spirit) ===
    manifest = json.loads(MANIFEST_PATH.read_text())
    for key, entry in entries.items():
        manifest["sources"][key] = entry
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"\n  Manifest updated: {MANIFEST_PATH}")

    # === 6. Report success ===
    legal_entry = entries["amsterdam-omgevingsplan-cvdr696291"]
    print("\n=== ISSUE_5 Legal Source Acquisition ===")
    print(f"CVDR_ID={CVDR_ID}")
    print(f"VERSION={RESOLVED_REF}")
    print(f"SOURCE_URL={SOURCE_URL}")
    print(f"WTI_URL={WTI_URL}")
    print(f"GMB_URL={GMB_URL}")
    print(f"ARTIFACT_SHA256={legal_entry['artifact_sha256']}")
    print(f"NORMALIZED_SHA256={legal_entry['normalized_content_sha256']}")
    print(f"BYTE_LENGTH={legal_entry['byte_length']}")
    print(f"VERSION_VERIFIED={legal_entry['version_verified']}")
    print(f"EFFECTIVE_STATUS_VERIFIED={legal_entry['effective_status_verified']}")
    print(f"AMENDMENT_CHAIN_VERIFIED={legal_entry['amendment_chain_verified']}")
    print(f"RULE_MAPPING_VERIFIED={legal_entry['rule_mapping_verified']}")
    print("ACQUISITION_COMPLETE=true")


if __name__ == "__main__":
    main()
