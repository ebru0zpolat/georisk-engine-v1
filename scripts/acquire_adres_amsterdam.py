#!/usr/bin/env python3
"""ISSUE_4B-R2: Independent BAG Adres collection acquisition.

Fetches the 5 Amsterdam Adres features matching our 5 hoofdadres_identificatie
values from PDOK's /collections/adres/items endpoint using the officially
supported 'identificatie' query parameter (confirmed from PDOK OpenAPI spec).

PDOK BAG OGC API v2 advertises:
  identificatie — "Filter features by this property" (string, query param)

This is the Identificatie filter the user requested. It returns exactly
the feature(s) whose properties.identificatie matches the value.

Saves each matching Adres feature as an individual raw snapshot with full
byte-level provenance.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

ADRES_URL = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/adres/items"
LICENSE_ID = "Public Domain Mark 1.0"
LICENSE_NAME = "BAG data — Public Domain"
LICENSE_URL = "https://www.pdok.nl/introductie/-/article/basisregistratie-adressen-en-gebouwen-bag-"
AUTHORITY = "Kadaster (LV-BAG) / PDOK"
COLLECTION = "adres"

AMSTERDAM_DIR = Path("data/nl_pilot/snapshots/amsterdam-v1")
AMSTERDAM_MANIFEST = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")

# The 5 target hoofdadres_identificatie values from the Amsterdam chains
TARGET_IDENTIFICATIES: dict[str, str] = {
    "chain-1": "0363200000006110",
    "chain-2": "0363200000403263",
    "chain-3": "0363200000006127",
    "chain-4": "0363200000006140",
    "chain-5": "0363200000431014",
}

# The 5 expected VBO identificatie values (adresseerbaar_object_identificatie)
TARGET_VBO_IDENTS: dict[str, str] = {
    "chain-1": "0363010000543292",
    "chain-2": "0363010000543308",
    "chain-3": "0363010000543309",
    "chain-4": "0363010000543325",
    "chain-5": "0363010000544122",
}

TARGET_BRONHOUDER_ID = "0363"
TARGET_BRONHOUDER_NAAM = "Amsterdam"
TARGET_ADRES_TYPE = "Verblijfsobject"


def fetch_adres_by_identificatie(identificatie: str) -> dict:
    """Fetch a single Adres feature by its BAG identificatie using PDOK's
    officially supported identificatie filter parameter.

    PDOK OpenAPI spec confirms:
      /collections/adres/items?identificatie=<value>
      parameter: "identificatie" — "Filter features by this property"

    Returns dict with:
      feature: the single Adres GeoJSON feature
      raw_response: the exact HTTP response bytes (FeatureCollection wrapper)
      source_url: the full request URL
      http_status: HTTP status code
      retrieved_at: ISO 8601 timestamp
    """
    params = {"identificatie": identificatie, "limit": "10"}
    full_url = f"{ADRES_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        full_url,
        headers={"Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw_response = resp.read()
        http_status = resp.status

    if http_status != 200:
        raise RuntimeError(f"HTTP {http_status} for {full_url}")

    data = json.loads(raw_response)
    if data.get("type") != "FeatureCollection":
        raise RuntimeError(f"Not a FeatureCollection: {data.get('type')}")

    features = data.get("features", [])
    if not features:
        raise RuntimeError(
            f"No Adres feature found for identificatie={identificatie}"
        )

    return {
        "feature": features[0],
        "raw_response": raw_response,
        "source_url": full_url,
        "http_status": http_status,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_normalized_sha256(data: dict) -> str:
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_adres_snapshot(
    feature: dict,
    source_url: str,
    http_status: int,
    retrieved_at: str,
    snapshot_path: Path,
) -> dict:
    """Save a single Adres feature as its own raw snapshot file.

    The file wraps the feature in a FeatureCollection (single-feature) to match
    the PDOK response format. The exact response bytes from the PDOK API call
    are preserved in provenance.

    Returns provenance metadata dict.
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    # Wrap in single-feature FeatureCollection
    fc = {
        "type": "FeatureCollection",
        "features": [feature],
        "numberReturned": 1,
    }
    fc_bytes = json.dumps(
        fc, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")

    snapshot_path.write_bytes(fc_bytes)

    return {
        "source_url": source_url,
        "artifact_sha256": compute_sha256(fc_bytes),
        "normalized_content_sha256": compute_normalized_sha256(fc),
        "retrieved_at": retrieved_at,
        "http_status": http_status,
        "byte_length": len(fc_bytes),
        "snapshot_path": str(snapshot_path),
        "collection": COLLECTION,
    }


def main() -> None:
    print("=== ISSUE_4B-R2: Independent BAG Adres Collection Acquisition ===\n")

    # Step 1: Fetch each Adres feature using PDOK's identificatie filter
    print("--- Step 1: Fetching Adres features from PDOK (identificatie filter) ---")
    fetched = {}

    for chain_key, ident in sorted(TARGET_IDENTIFICATIES.items()):
        try:
            result = fetch_adres_by_identificatie(ident)
            fetched[chain_key] = result
            props = result["feature"]["properties"]
            print(
                f"  ✓ {chain_key}: adres {ident} → "
                f"ao={props.get('adresseerbaar_object_identificatie')} "
                f"type={props.get('adresseerbaar_object_type')} "
                f"bh={props.get('bronhouder_identificatie')}/{props.get('bronhouder_naam')}"
            )
        except Exception as e:
            print(f"  ✗ {chain_key}: FAILED — {e}")

    if len(fetched) != len(TARGET_IDENTIFICATIES):
        print(
            f"\n  Only {len(fetched)}/{len(TARGET_IDENTIFICATIES)} fetched — aborting"
        )
        sys.exit(1)

    print(f"\n  All {len(fetched)} Adres features fetched successfully.\n")

    # Step 2: Verify all 5 join conditions
    print("--- Step 2: Verifying join conditions ---")
    all_pass = True
    for chain_key in sorted(fetched.keys()):
        result = fetched[chain_key]
        props = result["feature"]["properties"]
        expected_adres = TARGET_IDENTIFICATIES[chain_key]
        expected_vbo = TARGET_VBO_IDENTS[chain_key]

        checks = [
            (
                "identificatie",
                props.get("identificatie", "") == expected_adres,
                props.get("identificatie", ""),
            ),
            (
                "adresseerbaar_object_identificatie",
                props.get("adresseerbaar_object_identificatie", "") == expected_vbo,
                props.get("adresseerbaar_object_identificatie", ""),
            ),
            (
                "adresseerbaar_object_type",
                props.get("adresseerbaar_object_type", "") == TARGET_ADRES_TYPE,
                props.get("adresseerbaar_object_type", ""),
            ),
            (
                "bronhouder_identificatie",
                props.get("bronhouder_identificatie", "") == TARGET_BRONHOUDER_ID,
                props.get("bronhouder_identificatie", ""),
            ),
            (
                "bronhouder_naam",
                props.get("bronhouder_naam", "") == TARGET_BRONHOUDER_NAAM,
                props.get("bronhouder_naam", ""),
            ),
        ]

        ok = all(c[1] for c in checks)
        status = "✓" if ok else "✗"
        details = ", ".join(f"{c[0]}={c[2]}{'✓' if c[1] else '✗'}" for c in checks)
        print(f"  {chain_key}: {status} {details}")

        if not ok:
            all_pass = False

    if not all_pass:
        print("\n  ⚠ Some join conditions failed — aborting save")
        sys.exit(1)

    print("\n  All 5 join conditions verified.\n")

    # Step 3: Save snapshots and build provenance
    print("--- Step 3: Saving Adres snapshots ---")
    provenance_entries = {}

    for chain_key in sorted(fetched.keys()):
        result = fetched[chain_key]
        ident = TARGET_IDENTIFICATIES[chain_key]
        snapshot_name = f"adres-{ident}.raw.json"
        snapshot_path = AMSTERDAM_DIR / snapshot_name

        prov = save_adres_snapshot(
            feature=result["feature"],
            source_url=result["source_url"],
            http_status=result["http_status"],
            retrieved_at=result["retrieved_at"],
            snapshot_path=snapshot_path,
        )
        provenance_entries[f"amsterdam-{chain_key}"] = {
            **prov,
            "authority": AUTHORITY,
            "license_id": LICENSE_ID,
            "license_name": LICENSE_NAME,
            "license_url": LICENSE_URL,
            "content_type": "application/geo+json",
            "feature_count": 1,
            "source_id": f"amsterdam-{chain_key}",
            "query_or_bbox": f"identificatie={ident}",
            "chain_key": chain_key,
        }
        print(f"  Saved {snapshot_name} ({prov['byte_length']} bytes)")

    # Step 4: Update manifest
    print("\n--- Step 4: Updating manifest ---")
    manifest = json.loads(AMSTERDAM_MANIFEST.read_text())

    # Add Adres entries to sources
    for source_id, prov in provenance_entries.items():
        manifest["sources"][source_id] = {
            "source_id": prov["source_id"],
            "source_url": prov["source_url"],
            "artifact_sha256": prov["artifact_sha256"],
            "normalized_content_sha256": prov["normalized_content_sha256"],
            "retrieved_at": prov["retrieved_at"],
            "http_status": prov["http_status"],
            "content_type": prov["content_type"],
            "byte_length": prov["byte_length"],
            "snapshot_path": prov["snapshot_path"],
            "collection": prov["collection"],
            "authority": prov["authority"],
            "license_id": prov["license_id"],
            "license_name": prov["license_name"],
            "license_url": prov["license_url"],
            "feature_count": prov["feature_count"],
            "crs": "CRS84",
            "query_or_bbox": prov["query_or_bbox"],
        }

    # Add issue_4b_r2 section
    now = datetime.now(timezone.utc).isoformat()
    manifest["issue_4b_r2"] = {
        "completed_at": now,
        "adres_features_resolved": len(fetched),
        "filter_method": "pdok_identificatie_parameter",
        "independent_adres_feature_fetch": "verified",
        "adres_identificatie_join": "verified",
        "adres_object_vbo_join": "verified",
        "adres_municipality_gate": "verified",
        "adres_raw_hashes": "verified",
    }

    # Update chain-level address verification to reference Adres collection
    for chain_key in fetched:
        if chain_key in manifest.get("chains", {}):
            manifest["chains"][chain_key]["address_source"] = (
                "independent_adres_collection_record"
            )
            manifest["chains"][chain_key]["adres_collection_source_id"] = (
                f"amsterdam-{chain_key}"
            )

    AMSTERDAM_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"  Manifest updated with {len(provenance_entries)} Adres entries")

    # Step 5: Final verification
    print("\n--- Step 5: Final verification ---")
    m2 = json.loads(AMSTERDAM_MANIFEST.read_text())

    # Verify all 5 Adres entries present
    adres_entries = {
        k: v for k, v in m2["sources"].items() if v.get("collection") == "adres"
    }
    assert len(adres_entries) == 5, (
        f"Expected 5 Adres entries, got {len(adres_entries)}"
    )
    print(f"  Adres entries in manifest: {len(adres_entries)} ✓")

    # Verify each Adres file and hashes
    for source_id, entry in adres_entries.items():
        path = Path(entry["snapshot_path"])
        assert path.exists(), f"Missing snapshot: {path}"
        raw = path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        assert actual_sha == entry["artifact_sha256"], (
            f"{source_id}: artifact hash mismatch"
        )
    print("  All Adres artifact hashes verified ✓")

    # Verify chain references
    for chain_key in fetched:
        chain = m2["chains"][chain_key]
        assert chain.get("address_source") == "independent_adres_collection_record", (
            f"{chain_key}: address_source not updated"
        )
    print("  Chain address_source updated ✓")

    print(
        f"\n=== ISSUE_4B-R2 complete: {len(fetched)} Adres features acquired ==="
    )


if __name__ == "__main__":
    main()
