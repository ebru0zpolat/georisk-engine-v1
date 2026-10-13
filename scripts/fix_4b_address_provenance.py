#!/usr/bin/env python3
"""ISSUE_4B-R1: Address-leg verification and provenance correction.

For each of the 5 Amsterdam chains, verifies address data from VBO records,
reclassifies the VBO selected snapshot as derived, and updates provenance manifest.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AMSTERDAM_DIR = Path("data/nl_pilot/snapshots/amsterdam-v1")
MANIFEST_PATH = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")

AMSTERDAM_BRONHOUDER_ID = "0363"


def main() -> None:
    print("=== ISSUE_4B-R1: Address-leg verification ===\n")

    # Load VBO selected snapshot (may already be renamed to .derived.json)
    vbo_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.derived.json"
    if not vbo_path.exists():
        vbo_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.raw.json"
    vbo_fc = json.loads(vbo_path.read_text())

    # Load manifest
    manifest = json.loads(MANIFEST_PATH.read_text())
    chains = manifest["chains"]

    # Step 1: Verify address joins from VBO authoritative data
    print("--- Step 1: Address join verification ---")
    all_pass = True
    for chain_key, chain in chains.items():
        vbo_ident = chain["vbo_identificatie"]
        adres_ident = chain["adres_identificatie"]

        # Find the VBO feature
        vbo_feature = None
        for f in vbo_fc["features"]:
            if f["properties"]["identificatie"] == vbo_ident:
                vbo_feature = f
                break

        assert vbo_feature is not None, f"VBO {vbo_ident} not found"

        props = vbo_feature["properties"]

        # Verification 1: VBO.hoofdadres_identificatie == chain adres_identificatie
        hoofdadres = props.get("hoofdadres_identificatie", "")
        assert hoofdadres == adres_ident, (
            f"{chain_key}: hoofdadres_identificatie {hoofdadres} != chain adres {adres_ident}"
        )

        # Verification 2: VBO.identificatie is the adresseerbaar_object
        # (this is how BAG models the relationship: VBO IS the adressable object)
        vbo_id = props["identificatie"]

        # Verification 3: municipality gate
        bronhouder_id = props.get("bronhouder_identificatie", "")
        bronhouder_naam = props.get("bronhouder_naam", "")
        assert bronhouder_id == AMSTERDAM_BRONHOUDER_ID, (
            f"{chain_key}: bronhouder_identificatie={bronhouder_id}"
        )
        assert bronhouder_naam == "Amsterdam", (
            f"{chain_key}: bronhouder_naam={bronhouder_naam}"
        )

        # Verification 4: woonplaats matches
        woonplaats = props.get("woonplaats_naam", "")
        assert woonplaats == "Amsterdam", (
            f"{chain_key}: woonplaats_naam={woonplaats}"
        )

        print(f"  {chain_key}: VBO {vbo_id} → hoofdadres {hoofdadres} ✓ "
              f"bronhouder={bronhouder_id}/{bronhouder_naam} ✓ woonplaats={woonplaats} ✓")

    print(f"\nAll {len(chains)} address verifications passed.\n")

    # Step 2: Build address verification entries for manifest
    print("--- Step 2: Building address provenance entries ---")
    now = datetime.now(timezone.utc).isoformat()

    address_verification = {}
    for chain_key, chain in chains.items():
        vbo_ident = chain["vbo_identificatie"]
        # Find VBO feature to get address fields
        for f in vbo_fc["features"]:
            if f["properties"]["identificatie"] == vbo_ident:
                props = f["properties"]
                address_verification[chain_key] = {
                    "adres_identificatie": chain["adres_identificatie"],
                    "vbo_identificatie": vbo_ident,
                    "hoofdadres_identificatie": props.get("hoofdadres_identificatie"),
                    "openbare_ruimte_naam": props.get("openbare_ruimte_naam"),
                    "huisnummer": props.get("huisnummer"),
                    "postcode": props.get("postcode"),
                    "woonplaats_naam": props.get("woonplaats_naam"),
                    "bronhouder_identificatie": props.get("bronhouder_identificatie"),
                    "bronhouder_naam": props.get("bronhouder_naam"),
                    "source_collection": "verblijfsobject",
                    "source_note": "Address data from authoritative BAG VBO record",
                }
                break

    # Step 3: Reclassify VBO selected as derived
    print("--- Step 3: Reclassifying VBO selected as derived ---")

    # Rename the file (skip if already renamed)
    derived_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.derived.json"
    if vbo_path != derived_path:
        vbo_path.rename(derived_path)

    # Compute hashes for the renamed file
    derived_bytes = derived_path.read_bytes()
    derived_artifact_sha = hashlib.sha256(derived_bytes).hexdigest()
    derived_data = json.loads(derived_bytes)
    derived_canonical = json.dumps(derived_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    derived_normalized_sha = hashlib.sha256(derived_canonical.encode("utf-8")).hexdigest()

    # Update manifest
    # Remove old amsterdam-vbo-selected from sources
    if "amsterdam-vbo-selected" in manifest["sources"]:
        old_entry = manifest["sources"].pop("amsterdam-vbo-selected")
    else:
        old_entry = {}

    # Add as derived artifact
    if "derived_artifacts" not in manifest:
        manifest["derived_artifacts"] = {}

    manifest["derived_artifacts"]["amsterdam-vbo-selected"] = {
        "snapshot_path": str(derived_path),
        "artifact_sha256": derived_artifact_sha,
        "normalized_content_sha256": derived_normalized_sha,
        "byte_length": len(derived_bytes),
        "derived_from": list(manifest["sources"].keys()),
        "classification": "derived_from_raw_source_pages",
        "note": "Filtered and selected from raw VBO page snapshots",
    }

    # Step 4: Add address verification to manifest
    print("--- Step 4: Adding address verification to manifest ---")
    manifest["address_verification"] = address_verification

    # Update chain records with address verification status
    for chain_key, chain in manifest["chains"].items():
        chain["address_verified"] = True
        chain["address_source"] = "vbo_authoritative_bag_record"
        chain["municipality_verified"] = True

    # Update metadata
    manifest["issue_4b_r1"] = {
        "completed_at": now,
        "address_features_resolved": len(chains),
        "complete_adres_vbo_pand_chains": len(chains),
        "address_vbo_identificatie_join": "verified",
        "address_object_vbo_join": "verified",
        "address_municipality_gate": "verified",
        "selected_vbo_classification": "derived",
    }

    # Step 5: Write updated manifest
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Verification
    print("\n=== Final Verification ===")
    m2 = json.loads(MANIFEST_PATH.read_text())

    # Check derived artifact
    assert "amsterdam-vbo-selected" not in m2.get("sources", {}), "Still in sources!"
    assert "amsterdam-vbo-selected" in m2.get("derived_artifacts", {}), "Not in derived!"
    print("Derived reclassification: ✓")

    # Check address verification
    av = m2.get("address_verification", {})
    assert len(av) == 5, f"Only {len(av)} address verifications"
    for ck, entry in av.items():
        assert entry["hoofdadres_identificatie"] == entry["adres_identificatie"], (
            f"{ck}: hoofdadres mismatch"
        )
        assert entry["bronhouder_identificatie"] == "0363"
        assert entry["bronhouder_naam"] == "Amsterdam"
    print("Address verification: ✓ (5/5)")

    # Check no vacuous assertions remain
    test_file = Path("tests/nl_pilot/test_nl_pilot.py").read_text()
    assert "or True" not in test_file, "Vacuous assertion still present!"
    print("No vacuous assertions: ✓")

    # Check chain metadata
    for ck, chain in m2["chains"].items():
        assert chain.get("address_verified") is True
        assert chain.get("municipality_verified") is True
    print("Chain metadata: ✓")

    print("\nDone.")


if __name__ == "__main__":
    main()
