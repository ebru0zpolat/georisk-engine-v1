#!/usr/bin/env python3
"""Acquire real BAG snapshots from PDOK OGC API v2.

Live-acquires pand, verblijfsobject, and adres data from the official
PDOK BAG endpoints, saves raw HTTP response bytes as snapshots, and
creates a provenance manifest with dual-hash (artifact + normalized).

This script performs ONE live acquisition. After this, CI replays
from the committed snapshots deterministically.

Usage:
    python scripts/acquire_bag_snapshots.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.nl_pilot.bag_connector import (
    AMSTERDAM_BBOX_CRS84,
    BAG_ADRES_URL,
    BAG_AUTHORITY,
    BAG_LICENSE_ID,
    BAG_LICENSE_NAME,
    BAG_LICENSE_URL,
    BAG_PAND_URL,
    BAG_VERBLIJDSDOBJECT_URL,
    RawFetchResult,
    raw_fetch,
    save_raw_snapshot,
)

SNAPSHOT_DIR = Path("data/nl_pilot/snapshots")
MANIFEST_PATH = Path("data/nl_pilot/provenance-manifest.json")

COLLECTIONS = [
    ("bag-pand", BAG_PAND_URL, "pand"),
    ("bag-verblijfsobject", BAG_VERBLIJDSDOBJECT_URL, "verblijfsobject"),
    ("bag-adres", BAG_ADRES_URL, "adres"),
]


def acquire_all() -> list[dict]:
    """Live-acquire all three BAG collections and return provenance entries."""
    entries = []
    now = datetime.now(timezone.utc).isoformat()

    for source_id, url, collection in COLLECTIONS:
        print(f"Fetching {collection} from {url}...")
        result = raw_fetch(url, bbox=AMSTERDAM_BBOX_CRS84, limit=20)

        snapshot_path = SNAPSHOT_DIR / f"{source_id}.raw.json"
        meta = save_raw_snapshot(result, snapshot_path)

        # Count features
        data = json.loads(result.raw_bytes)
        feature_count = len(data.get("features", []))
        print(f"  → {feature_count} features, {meta['byte_length']} bytes")

        entry = {
            "source_id": source_id,
            "authority": BAG_AUTHORITY,
            "source_url": result.source_url,
            "collection": collection,
            "query_or_bbox": AMSTERDAM_BBOX_CRS84,
            "crs": "CRS84",
            "retrieved_at": result.retrieved_at,
            "http_status": result.http_status,
            "content_type": result.content_type,
            "byte_length": meta["byte_length"],
            "artifact_sha256": meta["artifact_sha256"],
            "normalized_content_sha256": meta["normalized_content_sha256"],
            "license_id": BAG_LICENSE_ID,
            "license_name": BAG_LICENSE_NAME,
            "license_url": BAG_LICENSE_URL,
            "snapshot_path": meta["snapshot_path"],
            "feature_count": feature_count,
        }
        entries.append(entry)

    return entries


def write_manifest(entries: list[dict]) -> None:
    """Write provenance manifest to disk."""
    manifest = {
        "manifest_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Real BAG source snapshots — byte-level provenance",
        "sources": {e["source_id"]: e for e in entries},
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\nManifest written to {MANIFEST_PATH}")


def main() -> None:
    print("=== BAG Real Snapshot Acquisition ===")
    print(f"Bbox: {AMSTERDAM_BBOX_CRS84} (CRS84)")
    print()

    entries = acquire_all()
    write_manifest(entries)

    # Verify committed bytes match
    print("\n=== Verification ===")
    for entry in entries:
        path = Path(entry["snapshot_path"])
        actual_bytes = path.read_bytes()
        actual_artifact_sha = hashlib.sha256(actual_bytes).hexdigest()
        canonical = json.dumps(
            json.loads(actual_bytes),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        actual_normalized_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        assert actual_artifact_sha == entry["artifact_sha256"], (
            f"Artifact hash mismatch for {entry['source_id']}"
        )
        assert actual_normalized_sha == entry["normalized_content_sha256"], (
            f"Normalized hash mismatch for {entry['source_id']}"
        )
        print(f"  {entry['source_id']}: artifact={actual_artifact_sha[:16]}... "
              f"normalized={actual_normalized_sha[:16]}... "
              f"features={entry['feature_count']} ✓")

    print("\nAll snapshots verified.")


if __name__ == "__main__":
    main()
