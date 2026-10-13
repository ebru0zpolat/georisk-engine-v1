#!/usr/bin/env python3
"""Acquire Amsterdam-targeted BAG chains with complete source joins.

Acquires VBO records filtered by Amsterdam municipality (bronhouder 0363),
resolves Pand and Adres for each selected candidate, and preserves all raw
HTTP response bytes with dual-hash provenance.

Usage:
    python scripts/acquire_amsterdam_chains.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
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
)

# Tighter Amsterdam-central bbox (CRS84)
# Focus on central Amsterdam non-residential corridor
AMSTERDAM_CENTRAL_BBOX = "4.88,52.34,5.00,52.40"

SNAPSHOT_DIR = Path("data/nl_pilot/snapshots/amsterdam-v1")
MANIFEST_PATH = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")

# Amsterdam municipality identifiers
AMSTERDAM_BRONHOUDER_ID = "0363"
AMSTERDAM_BRONHOUDER_NAME = "Amsterdam"

# Selection criteria
MIN_CHAINS = 5
MAX_PAGES = 10
PAGE_LIMIT = 100  # PDOK supports up to 1000, use 100 per page

# Non-residential use classes (Dutch, lowercase)
NON_RESIDENTIAL_KEYWORDS = [
    "kantoor", "winkel", "industrie", "logies", "maatschappelijk",
    "sport", "cultuur", "onderwijs", "zorg", "horeca", "bergruimte",
    "overig", "bijeenkomst", "kantoorfunctie", "winkelfunctie",
    "industriefunctie", "logiesfunctie", "bijeenkomstfunctie",
]

# Active VBO status (Dutch)
ACTIVE_STATUSES = ["Verblijfsobject in gebruik"]


@dataclass
class ChainResult:
    """A complete Amsterdam Adres → VBO → Pand chain."""
    adres_identificatie: str
    vbo_identificatie: str
    vbo_feature_id: str
    pand_identificatie: str
    pand_feature_id: str
    gebruiksdoel: str
    oppervlakte: float
    bouwjaar: int
    woonplaats: str
    bronhouder_id: str
    bronhouder_naam: str
    straatnaam: str
    huisnummer: str | None


def fetch_page(url: str, bbox: str, limit: int, cursor: str | None = None) -> RawFetchResult:
    """Fetch one page from a PDOK OGC API items endpoint."""
    params = {"bbox": bbox, "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    full_url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        full_url,
        headers={"Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "application/geo+json")
        http_status = resp.status

    result = RawFetchResult(
        source_url=full_url,
        raw_bytes=raw,
        content_type=content_type,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        http_status=http_status,
    )
    result.validate()
    return result


def fetch_feature_by_url(url: str) -> RawFetchResult:
    """Fetch a single OGC Feature by its exact URL."""
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "application/geo+json")
        http_status = resp.status

    result = RawFetchResult(
        source_url=url,
        raw_bytes=raw,
        content_type=content_type,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        http_status=http_status,
    )
    return result


def is_amsterdam(feature: dict) -> bool:
    """Check if a feature belongs to Amsterdam municipality."""
    props = feature.get("properties", {})
    return (
        props.get("bronhouder_identificatie") == AMSTERDAM_BRONHOUDER_ID
        and props.get("bronhouder_naam") == AMSTERDAM_BRONHOUDER_NAME
    )


def is_non_residential(props: dict) -> bool:
    """Check if gebruiksdoel contains at least one non-residential use."""
    gd = props.get("gebruiksdoel") or ""
    if not gd:
        return False
    gd_lower = gd.lower()
    return any(kw in gd_lower for kw in NON_RESIDENTIAL_KEYWORDS)


def is_active(props: dict) -> bool:
    """Check if VBO is active (in use)."""
    status = props.get("status", "")
    return status in ACTIVE_STATUSES


def select_candidate(props: dict) -> bool:
    """Check if a VBO qualifies as a pilot candidate."""
    if not is_non_residential(props):
        return False
    if not is_active(props):
        return False
    if not props.get("pand.href"):
        return False
    pand_hrefs = props["pand.href"]
    if not isinstance(pand_hrefs, list) or len(pand_hrefs) != 1:
        return False
    if not props.get("identificatie"):
        return False
    if not props.get("hoofdadres_identificatie"):
        return False
    opp = props.get("oppervlakte", 0)
    if not opp or opp <= 0:
        return False
    return True


def main() -> None:
    print("=== Amsterdam-Targeted BAG Acquisition ===")
    print(f"Bbox: {AMSTERDAM_CENTRAL_BBOX} (CRS84)")
    print()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    provenance_entries = []

    # Step 1: Paginate VBO records to find Amsterdam candidates
    print("--- Step 1: Fetching VBO records ---")
    all_vbo_features = []
    vbo_raw_results = []

    next_url = None
    for page in range(MAX_PAGES):
        if page == 0:
            print(f"  Page {page + 1}...")
            result = fetch_page(BAG_VERBLIJDSDOBJECT_URL, AMSTERDAM_CENTRAL_BBOX, PAGE_LIMIT)
        else:
            if not next_url:
                print("  No next link.")
                break
            print(f"  Page {page + 1} (cursor)...")
            # Fetch from the PDOK next URL directly
            req = urllib.request.Request(next_url, headers={"Accept": "application/geo+json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                ct = resp.headers.get("Content-Type", "application/geo+json")
                result = RawFetchResult(
                    source_url=next_url, raw_bytes=raw, content_type=ct,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    http_status=resp.status,
                )
                result.validate()

        data = json.loads(result.raw_bytes)
        features = data.get("features", [])
        all_vbo_features.extend(features)

        # Save raw page
        page_path = SNAPSHOT_DIR / f"vbo-page-{page}.raw.json"
        page_path.write_bytes(result.raw_bytes)
        provenance_entries.append({
            "source_id": f"amsterdam-vbo-page-{page}",
            "authority": BAG_AUTHORITY,
            "source_url": result.source_url,
            "collection": "verblijfsobject",
            "query_or_bbox": AMSTERDAM_CENTRAL_BBOX,
            "crs": "CRS84",
            "retrieved_at": result.retrieved_at,
            "http_status": result.http_status,
            "content_type": result.content_type,
            "byte_length": len(result.raw_bytes),
            "artifact_sha256": result.artifact_sha256,
            "normalized_content_sha256": result.normalized_content_sha256,
            "license_id": BAG_LICENSE_ID,
            "license_name": BAG_LICENSE_NAME,
            "license_url": BAG_LICENSE_URL,
            "snapshot_path": str(page_path),
            "feature_count": len(features),
        })

        # Check if we have enough Amsterdam non-residential candidates
        amsterdam_vbo = [f for f in all_vbo_features if is_amsterdam(f)]
        candidates = [f for f in amsterdam_vbo if select_candidate(f["properties"])]
        print(f"    Total VBO: {len(all_vbo_features)}, Amsterdam: {len(amsterdam_vbo)}, Candidates: {len(candidates)}")

        if len(candidates) >= MIN_CHAINS:
            break

        # Extract next link
        next_url = None
        for link in data.get("links", []):
            if link.get("rel") == "next":
                next_url = link["href"]
                break

        if not next_url or len(features) < PAGE_LIMIT:
            print("  No more pages.")
            break

        time.sleep(0.5)  # polite delay

    # Step 2: Select top 5 candidates
    print("\n--- Step 2: Selecting candidates ---")
    amsterdam_vbo = [f for f in all_vbo_features if is_amsterdam(f)]
    candidates = [f for f in amsterdam_vbo if select_candidate(f["properties"])]
    candidates.sort(key=lambda f: f["properties"]["identificatie"])
    selected = candidates[:MIN_CHAINS]
    print(f"  Amsterdam VBO total: {len(amsterdam_vbo)}")
    print(f"  Qualifying candidates: {len(candidates)}")
    print(f"  Selected: {len(selected)}")

    if len(selected) < MIN_CHAINS:
        print(f"\nFAIL: Only {len(selected)} qualifying Amsterdam chains found (need {MIN_CHAINS})")
        sys.exit(1)

    for s in selected:
        p = s["properties"]
        print(f"    VBO {p['identificatie']}: {p.get('gebruiksdoel')}, {p.get('oppervlakte')}m², pand.href={len(p.get('pand.href', []))}")

    # Step 3: Resolve Pand features by following pand.href
    print("\n--- Step 3: Resolving Pand features ---")
    pand_raw_results = {}
    pand_features = {}
    chains = []

    for vbo_feature in selected:
        vbo_props = vbo_feature["properties"]
        vbo_id = vbo_props["identificatie"]
        pand_hrefs = vbo_props.get("pand.href", [])
        pand_href = pand_hrefs[0]
        pand_uuid = pand_href.rstrip("/").split("/")[-1]

        print(f"  Fetching Pand for VBO {vbo_id}: {pand_uuid}...")
        pand_result = fetch_feature_by_url(pand_href)
        pand_data = json.loads(pand_result.raw_bytes)

        # Verify feature.id matches UUID
        feature_id = pand_data.get("id", "")
        assert feature_id == pand_uuid, (
            f"Pand feature.id {feature_id} != href UUID {pand_uuid}"
        )

        # Save raw pand response
        pand_path = SNAPSHOT_DIR / f"pand-{pand_uuid}.raw.json"
        pand_path.write_bytes(pand_result.raw_bytes)
        pand_raw_results[pand_uuid] = pand_result
        pand_features[pand_uuid] = pand_data

        provenance_entries.append({
            "source_id": f"amsterdam-pand-{pand_uuid[:8]}",
            "authority": BAG_AUTHORITY,
            "source_url": pand_result.source_url,
            "collection": "pand",
            "query_or_bbox": "",
            "crs": "",
            "retrieved_at": pand_result.retrieved_at,
            "http_status": pand_result.http_status,
            "content_type": pand_result.content_type,
            "byte_length": len(pand_result.raw_bytes),
            "artifact_sha256": pand_result.artifact_sha256,
            "normalized_content_sha256": pand_result.normalized_content_sha256,
            "license_id": BAG_LICENSE_ID,
            "license_name": BAG_LICENSE_NAME,
            "license_url": BAG_LICENSE_URL,
            "snapshot_path": str(pand_path),
            "feature_count": 1,
        })

        pand_props = pand_data.get("properties", {})
        print(f"    Pand {pand_props.get('identificatie')}: bouwjaar={pand_props.get('bouwjaar')}, gebruiksdoel={pand_props.get('gebruiksdoel')}")

    # Step 4: Resolve addresses
    print("\n--- Step 4: Resolving addresses ---")
    for vbo_feature in selected:
        vbo_props = vbo_feature["properties"]
        vbo_id = vbo_props["identificatie"]
        hoofdadres_id = vbo_props.get("hoofdadres_identificatie", "")
        pand_hrefs = vbo_props.get("pand.href", [])
        pand_uuid = pand_hrefs[0].rstrip("/").split("/")[-1]
        pand_data = pand_features[pand_uuid]
        pand_props = pand_data.get("properties", {})

        # Build chain
        chain = ChainResult(
            adres_identificatie=hoofdadres_id,
            vbo_identificatie=vbo_id,
            vbo_feature_id=vbo_feature.get("id", ""),
            pand_identificatie=pand_props.get("identificatie", ""),
            pand_feature_id=pand_uuid,
            gebruiksdoel=vbo_props.get("gebruiksdoel", ""),
            oppervlakte=float(vbo_props.get("oppervlakte", 0)),
            bouwjaar=int(pand_props.get("bouwjaar", 0)),
            woonplaats=vbo_props.get("woonplaats_naam", ""),
            bronhouder_id=vbo_props.get("bronhouder_identificatie", ""),
            bronhouder_naam=vbo_props.get("bronhouder_naam", ""),
            straatnaam=vbo_props.get("openbare_ruimte_naam", ""),
            huisnummer=str(vbo_props.get("huisnummer", "")) if vbo_props.get("huisnummer") else None,
        )
        chains.append(chain)
        print(f"  Chain: {chain.straatnaam} {chain.huisnummer} ({chain.woonplaats}) "
              f"→ VBO {chain.vbo_identificatie} → Pand {chain.pand_identificatie}")

    # Step 5: Save selected VBO features as Amsterdam VBO snapshot
    print("\n--- Step 5: Saving Amsterdam VBO snapshot ---")
    amsterdam_fc = {
        "type": "FeatureCollection",
        "features": selected,
    }
    vbo_snapshot_path = SNAPSHOT_DIR / "amsterdam-vbo-selected.raw.json"
    vbo_snapshot_bytes = json.dumps(amsterdam_fc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    vbo_snapshot_path.write_bytes(vbo_snapshot_bytes)
    vbo_sha = hashlib.sha256(vbo_snapshot_bytes).hexdigest()
    vbo_norm = hashlib.sha256(json.dumps(json.loads(vbo_snapshot_bytes), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()

    now = datetime.now(timezone.utc).isoformat()
    provenance_entries.append({
        "source_id": "amsterdam-vbo-selected",
        "authority": BAG_AUTHORITY,
        "source_url": f"{BAG_VERBLIJDSDOBJECT_URL}?bbox={AMSTERDAM_CENTRAL_BBOX}",
        "collection": "verblijfsobject",
        "query_or_bbox": AMSTERDAM_CENTRAL_BBOX,
        "crs": "CRS84",
        "retrieved_at": now,
        "http_status": 200,
        "content_type": "application/geo+json",
        "byte_length": len(vbo_snapshot_bytes),
        "artifact_sha256": vbo_sha,
        "normalized_content_sha256": vbo_norm,
        "license_id": BAG_LICENSE_ID,
        "license_name": BAG_LICENSE_NAME,
        "license_url": BAG_LICENSE_URL,
        "snapshot_path": str(vbo_snapshot_path),
        "feature_count": len(selected),
    })

    # Step 6: Write chain manifest
    print("\n--- Step 6: Writing manifest ---")
    chains_dict = {}
    for i, c in enumerate(chains):
        chains_dict[f"chain-{i + 1}"] = {
            "address": f"{c.straatnaam} {c.huisnummer}",
            "woonplaats": c.woonplaats,
            "adres_identificatie": c.adres_identificatie,
            "vbo_identificatie": c.vbo_identificatie,
            "vbo_feature_id": c.vbo_feature_id,
            "pand_identificatie": c.pand_identificatie,
            "pand_feature_id": c.pand_feature_id,
            "gebruiksdoel": c.gebruiksdoel,
            "oppervlakte": c.oppervlakte,
            "bouwjaar": c.bouwjaar,
            "bronhouder_id": c.bronhouder_id,
            "bronhouder_naam": c.bronhouder_naam,
        }

    manifest = {
        "manifest_version": "1.0",
        "acquisition": "amsterdam-targeted",
        "created_at": now,
        "bbox": AMSTERDAM_CENTRAL_BBOX,
        "crs": "CRS84",
        "municipality_filter": {
            "bronhouder_identificatie": AMSTERDAM_BRONHOUDER_ID,
            "bronhouder_naam": AMSTERDAM_BRONHOUDER_NAME,
        },
        "chain_count": len(chains),
        "chains": chains_dict,
        "sources": {e["source_id"]: e for e in provenance_entries},
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Verification
    print("\n=== Verification ===")
    print(f"Chains: {len(chains)}")
    for i, c in enumerate(chains):
        print(f"  {i + 1}. {c.straatnaam} {c.huisnummer} ({c.woonplaats}) "
              f"VBO={c.vbo_identificatie} Pand={c.pand_identificatie} "
              f"gebruiksdoel={c.gebruiksdoel}")

    # Verify all hashes
    for entry in provenance_entries:
        path = Path(entry["snapshot_path"])
        if path.exists():
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry["artifact_sha256"], (
                f"Hash mismatch: {entry['source_id']}"
            )
    print("\nAll hashes verified. Done.")


if __name__ == "__main__":
    main()
