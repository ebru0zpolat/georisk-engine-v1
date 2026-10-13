"""Real Amsterdam Asset Fixtures for the Controlled Pilot.

5 Amsterdam non-residential buildings derived from sealed
Adres → VBO → PAND evidence chains (ISSUE_4C-R3).

Asset construction:
  load_pilot_assets(project_root) reads the Amsterdam provenance
  manifest and sealed raw snapshots at runtime.  Every raw source
  file is hash-verified against manifest provenance before use.
  All identity fields are verified against the evidence chain.
  Address is constructed from the actual Adres raw feature fields.
  Pand footprint area is derived from the sealed Pand polygon via
  CRS84→RDNew transformation (ISSUE_7).

Fail-closed contract:
  The public factory returns verified source-derived assets OR
  raising ValueError.  It never returns unverified assets.

Verification fields:
  asset_identity_verified, source_integrity_verified,
  building_geometry_verified, use_class_verified are NOT
  caller-settable (field(init=False)).  The factory sets them
  after evidence gates pass.  The dataclass defaults are False.

Classification:
  pilot_real_assets — real BAG identity, NOT customer data
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RealAmsterdamAsset:
    """A real Amsterdam asset with verified BAG identity.

    Verification flags are factory-only (field(init=False)).
    A caller cannot assert verified state.
    All defaults are False (fail-closed).
    """
    asset_id: str
    address: str

    # BAG identity
    bag_pand_id: str
    bag_verblijfsobject_id: str

    # BAG geometry — VBO point (centroid)
    geometry_type: str  # "Point" (centroid)
    coordinates_x: float  # longitude / CRS84
    coordinates_y: float  # latitude / CRS84
    crs: str

    # BAG attributes
    bouwjaar: int  # construction year (from Pand)
    gebruiksdoel: str  # use class (from VBO)
    oppervlakte_m2: float  # VBO floor area m² (NOT built_area_m2)

    # Pand footprint geometry (ISSUE_7) — factory-only
    pand_footprint_area_m2: float | None = field(init=False, default=None)
    pand_geometry_source_crs: str | None = field(init=False, default=None)
    pand_geometry_area_crs: str | None = field(init=False, default=None)
    # Full provenance from PandFootprintEvidence (ISSUE_7-R1)
    pand_geometry_algorithm: str | None = field(init=False, default=None)
    pand_geometry_algorithm_version: str | None = field(init=False, default=None)
    pand_geometry_shapely_version: str | None = field(init=False, default=None)
    pand_geometry_pyproj_version: str | None = field(init=False, default=None)
    pand_geometry_proj_version: str | None = field(init=False, default=None)
    pand_geometry_source_artifact_sha256: str | None = field(init=False, default=None)
    pand_geometry_source_normalized_sha256: str | None = field(init=False, default=None)
    pand_geometry_feature_id: str | None = field(init=False, default=None)
    pand_source_id: str | None = field(init=False, default=None)
    pand_geometry_type: str | None = field(init=False, default=None)

    # Provenance metadata (V2) — factory-only, not verification inputs
    chain_id: str | None = field(init=False, default=None)
    vbo_feature_id: str | None = field(init=False, default=None)
    vbo_raw_source_id: str | None = field(init=False, default=None)
    adres_source_id: str | None = field(init=False, default=None)

    # Verification flags — factory-only, not caller-settable
    asset_identity_verified: bool = field(init=False, default=False)
    source_integrity_verified: bool = field(init=False, default=False)
    building_geometry_verified: bool = field(init=False, default=False)
    use_class_verified: bool = field(init=False, default=False)

    # Pilot invariants — always False
    asset_applicability_verified: bool = field(init=False, default=False)
    engineering_capacity_verified: bool = field(init=False, default=False)
    production_eligible: bool = field(init=False, default=False)

    def to_dict(self) -> dict:
        """Convert to asset dict for the regulation engine.

        Note: oppervlakte_m2 is VBO floor area, NOT built_area_m2
        (bebouwd oppervlak for hemelwater rules).  These have
        different semantics and must not be conflated.
        """
        return {
            "asset_id": self.asset_id,
            "address": self.address,
            "bag_pand_id": self.bag_pand_id,
            "bag_verblijfsobject_id": self.bag_verblijfsobject_id,
            "coordinates": {
                "crs": self.crs,
                "x": self.coordinates_x,
                "y": self.coordinates_y,
            },
            "use_class": self.gebruiksdoel,
            "municipality": "Amsterdam",
            "water_authority": "waterschap-agv",
            "bouwjaar": self.bouwjaar,
            "asset_identity_verified": self.asset_identity_verified,
            "source_integrity_verified": self.source_integrity_verified,
            "building_geometry_verified": self.building_geometry_verified,
            "use_class_verified": self.use_class_verified,
            "pand_footprint_area_m2": self.pand_footprint_area_m2,
            "pand_geometry_source_crs": self.pand_geometry_source_crs,
            "pand_geometry_area_crs": self.pand_geometry_area_crs,
        }


# ---------------------------------------------------------------------------
# Factory: load from sealed evidence with full hash verification
# ---------------------------------------------------------------------------

_AMSTERDAM_MANIFEST = "provenance-manifest-amsterdam-v1.json"
_AMSTERDAM_SNAPSHOT_DIR = "snapshots/amsterdam-v1"


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compute_normalized_sha256(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_source_hash(
    file_path: Path,
    source_id: str,
    source_entry: dict,
) -> None:
    """Verify a raw source file's SHA-256 hashes against manifest provenance.

    Raises ValueError on mismatch (fail-closed).
    """
    raw_bytes = file_path.read_bytes()
    actual_artifact = _compute_sha256(raw_bytes)
    expected_artifact = source_entry.get("artifact_sha256", "")

    if actual_artifact != expected_artifact:
        raise ValueError(
            f"HASH_MISMATCH_FAIL_CLOSED: {source_id} artifact_sha256 "
            f"expected={expected_artifact} actual={actual_artifact}"
        )

    data = json.loads(raw_bytes)
    actual_normalized = _compute_normalized_sha256(data)
    expected_normalized = source_entry.get("normalized_content_sha256", "")

    if actual_normalized != expected_normalized:
        raise ValueError(
            f"HASH_MISMATCH_FAIL_CLOSED: {source_id} normalized_content_sha256 "
            f"expected={expected_normalized} actual={actual_normalized}"
        )


def _require_source_entry(
    sources: dict,
    source_id: str,
    chain_key: str,
    collection: str,
) -> dict:
    """Require a manifest source entry to exist.  Absence = fail-closed."""
    entry = sources.get(source_id)
    if not entry:
        raise ValueError(
            f"PROVENANCE_ENTRY_REQUIRED_FAIL_CLOSED: {chain_key} "
            f"missing {collection} source entry '{source_id}'"
        )
    return entry


def load_pilot_assets(project_root: Path | None = None) -> list[RealAmsterdamAsset]:
    """Load 5 pilot assets from sealed Amsterdam evidence chains.

    Public contract:
      Returns verified source-derived assets, OR raising ValueError.
      Never returns unverified assets.

    Verification pipeline:
      1. Verify VBO derived artifact hash
      2. Verify every VBO raw page in derived_from lineage
      3. Verify each selected VBO feature traces to a verified raw page
      4. For each chain:
         a. Verify Pand raw artifact hash (mandatory provenance)
         b. Verify Pand.feature.id and Pand.identificatie
         c. Verify Adres raw artifact hash (mandatory provenance)
         d. Verify full 5-condition Adres identity gate
         e. Verify VBO→Pand join via feature.id UUID
         f. Derive Pand footprint from sealed polygon (ISSUE_7)
      5. Compute source_integrity = all hashes pass
      6. Compute asset_identity = all identity gates pass
      7. source_integrity_verified = True only after step 5
      8. asset_identity_verified = source_integrity AND all identity gates

    Raises
    ------
    FileNotFoundError
        If any required evidence file is missing.
    ValueError
        If provenance entry missing, hash mismatch, or identity gate fails.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent

    data_dir = project_root / "data" / "nl_pilot"
    manifest_path = data_dir / _AMSTERDAM_MANIFEST
    snapshot_dir = data_dir / _AMSTERDAM_SNAPSHOT_DIR

    if not manifest_path.exists():
        raise FileNotFoundError(f"Amsterdam manifest missing: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chains = manifest.get("chains", {})
    sources = manifest.get("sources", {})
    derived = manifest.get("derived_artifacts", {})

    if len(chains) < 5:
        raise ValueError(f"Expected >= 5 chains, got {len(chains)}")

    # --- Step 1: Verify VBO derived artifact hash (mandatory provenance) ---
    vbo_derived_entry = _require_source_entry(
        derived, "amsterdam-vbo-selected", "all", "vbo_derived"
    )
    vbo_path = snapshot_dir / "amsterdam-vbo-selected.derived.json"
    if not vbo_path.exists():
        raise FileNotFoundError(f"VBO derived snapshot missing: {vbo_path}")
    _verify_source_hash(vbo_path, "amsterdam-vbo-selected", vbo_derived_entry)

    # --- Step 2: Verify every VBO raw page in derived_from lineage ---
    derived_from = vbo_derived_entry.get("derived_from", [])
    for lineage_id in derived_from:
        lineage_entry = _require_source_entry(
            sources, lineage_id, "all", "vbo_raw_lineage"
        )
        lineage_path = project_root / lineage_entry.get("snapshot_path", "")
        if not lineage_path.exists():
            raise FileNotFoundError(
                f"VBO lineage source missing: {lineage_path}"
            )
        _verify_source_hash(lineage_path, lineage_id, lineage_entry)

    # --- Step 3: Load VBO derived snapshot and trace features to raw lineage ---
    vbo_fc = json.loads(vbo_path.read_text(encoding="utf-8"))
    vbo_by_ident = {
        f["properties"]["identificatie"]: f
        for f in vbo_fc.get("features", [])
    }

    # Build a set of all verified VBO feature.id values from raw lineage
    verified_vbo_feature_ids: set[str] = set()
    vbo_raw_pages: dict[str, dict] = {}
    for lineage_id in derived_from:
        lineage_entry = sources.get(lineage_id, {})
        lineage_path = project_root / lineage_entry.get("snapshot_path", "")
        if lineage_path.exists():
            page_data = json.loads(lineage_path.read_text(encoding="utf-8"))
            vbo_raw_pages[lineage_id] = page_data
            for f in page_data.get("features", []):
                verified_vbo_feature_ids.add(f.get("id", ""))

    # --- Step 4+: Per-chain verification ---
    assets: list[RealAmsterdamAsset] = []

    for chain_key in sorted(chains.keys()):
        chain = chains[chain_key]
        pand_ident = chain["pand_identificatie"]
        vbo_ident = chain["vbo_identificatie"]
        pand_feature_id = chain["pand_feature_id"]

        # --- Load VBO feature ---
        vbo_feature = vbo_by_ident.get(vbo_ident)
        if vbo_feature is None:
            raise ValueError(
                f"{chain_key}: VBO {vbo_ident} not in derived snapshot"
            )

        # --- Trace selected VBO to verified raw lineage ---
        vbo_feature_id = vbo_feature.get("id", "")
        if vbo_feature_id not in verified_vbo_feature_ids:
            raise ValueError(
                f"{chain_key}: VBO feature.id {vbo_feature_id} "
                f"not found in verified raw VBO lineage"
            )

        # Determine which raw lineage page contains this VBO
        matched_vbo_raw_source_id: str | None = None
        for lineage_id, page_data in vbo_raw_pages.items():
            if any(
                f.get("id") == vbo_feature_id
                for f in page_data.get("features", [])
            ):
                matched_vbo_raw_source_id = lineage_id
                break
        if matched_vbo_raw_source_id is None:
            raise ValueError(
                f"{chain_key}: VBO feature.id {vbo_feature_id} "
                f"not found in any raw VBO lineage page"
            )

        vbo_props = vbo_feature["properties"]
        vbo_geom = vbo_feature.get("geometry", {})
        vbo_coords = vbo_geom.get("coordinates", [0.0, 0.0])

        # --- Verify VBO→Pand join via feature.id UUID ---
        pand_hrefs = vbo_props.get("pand.href") or []
        vbo_pand_join_verified = False
        for href in pand_hrefs:
            uuid = href.rstrip("/").split("/")[-1]
            if uuid == pand_feature_id:
                vbo_pand_join_verified = True
                break

        # --- Load and hash-verify Pand feature (mandatory provenance) ---
        pand_source_id = f"amsterdam-pand-{pand_feature_id[:8]}"
        pand_source_entry = _require_source_entry(
            sources, pand_source_id, chain_key, "pand"
        )
        pand_path = snapshot_dir / f"pand-{pand_feature_id}.raw.json"
        if not pand_path.exists():
            raise FileNotFoundError(
                f"{chain_key}: Pand snapshot missing: {pand_path}"
            )
        _verify_source_hash(pand_path, pand_source_id, pand_source_entry)

        pand_raw = pand_path.read_bytes()
        pand_data = json.loads(pand_raw)
        if pand_data.get("type") == "Feature":
            pand_feat = pand_data
        elif "features" in pand_data and pand_data["features"]:
            pand_feat = pand_data["features"][0]
        else:
            raise ValueError(f"{chain_key}: unexpected Pand format")

        pand_props = pand_feat.get("properties", {})
        pand_geometry = pand_feat.get("geometry", {})

        # --- Full Pand identity gate ---
        pand_feature_id_actual = pand_feat.get("id", "")
        pand_identificatie_actual = pand_props.get("identificatie", "")

        if pand_feature_id_actual != pand_feature_id:
            raise ValueError(
                f"{chain_key}: Pand.feature.id={pand_feature_id_actual} "
                f"!= chain.pand_feature_id={pand_feature_id}"
            )
        if pand_identificatie_actual != pand_ident:
            raise ValueError(
                f"{chain_key}: Pand.identificatie={pand_identificatie_actual} "
                f"!= chain.pand_identificatie={pand_ident}"
            )

        # --- ISSUE_7: Derive Pand footprint from sealed polygon ---
        # compute_pand_footprint_area returns verified evidence or raises
        from app.nl_pilot.geometry import (
            compute_pand_footprint_area,
            SOURCE_CRS,
            AREA_CRS,
        )

        footprint_evidence = compute_pand_footprint_area(
            pand_geometry,
            pand_status=pand_props.get("status", ""),
            bag_pand_id=pand_ident,
            pand_feature_id=pand_feature_id,
            source_artifact_sha256=pand_source_entry.get(
                "artifact_sha256", ""
            ),
            source_normalized_sha256=pand_source_entry.get(
                "normalized_content_sha256", ""
            ),
        )
        # footprint_evidence.geometry_verified is already True
        # (set inside the factory after all gates pass)

        # --- Load and hash-verify Adres feature (mandatory provenance) ---
        adres_source_id = chain.get("adres_collection_source_id", "")
        adres_source_entry = _require_source_entry(
            sources, adres_source_id, chain_key, "adres"
        )
        adres_snapshot_path = adres_source_entry.get("snapshot_path", "")
        adres_full_path = project_root / adres_snapshot_path
        if not adres_full_path.exists():
            raise FileNotFoundError(
                f"{chain_key}: Adres snapshot missing: {adres_full_path}"
            )
        _verify_source_hash(
            adres_full_path, adres_source_id, adres_source_entry
        )

        adres_fc = json.loads(
            adres_full_path.read_text(encoding="utf-8")
        )
        adres_features = adres_fc.get("features", [])
        if not adres_features:
            raise ValueError(
                f"{chain_key}: Adres snapshot has no features"
            )
        adres_feat = adres_features[0]
        adres_props = adres_feat.get("properties", {})

        # --- Full Adres identity gate (5 conditions) ---
        id_match = (
            adres_props.get("identificatie")
            == vbo_props.get("hoofdadres_identificatie")
        )
        ao_match = (
            adres_props.get("adresseerbaar_object_identificatie")
            == vbo_ident
        )
        type_match = (
            adres_props.get("adresseerbaar_object_type")
            == "Verblijfsobject"
        )
        bh_id_match = (
            adres_props.get("bronhouder_identificatie") == "0363"
        )
        bh_naam_match = (
            adres_props.get("bronhouder_naam") == "Amsterdam"
        )

        adres_identity_ok = (
            id_match
            and ao_match
            and type_match
            and bh_id_match
            and bh_naam_match
        )

        if not adres_identity_ok:
            raise ValueError(
                f"{chain_key}: Adres identity gate failed "
                f"(id={id_match} ao={ao_match} type={type_match} "
                f"bh_id={bh_id_match} bh_naam={bh_naam_match})"
            )

        # --- Construct address from Adres raw feature ---
        street = adres_props.get("openbare_ruimte_naam", "")
        num = str(adres_props.get("huisnummer", ""))
        toevoeging = adres_props.get("toevoeging") or ""
        woonplaats = adres_props.get("woonplaats_naam", "Amsterdam")
        address_full = f"{street} {num}{toevoeging}, {woonplaats}"

        # --- Compute verification flags ---
        chain_identity = (
            adres_identity_ok
            and vbo_pand_join_verified
            and pand_feature_id_actual == pand_feature_id
            and pand_identificatie_actual == pand_ident
        )

        if not chain_identity:
            raise ValueError(
                f"{chain_key}: identity gate failed "
                f"(adres={adres_identity_ok} "
                f"vbo_pand_join={vbo_pand_join_verified})"
            )

        # --- Build asset with zero-padded ID ---
        chain_number = int(chain_key.split("-")[1])
        asset_id = f"NL-AM-CHAIN-{chain_number:03d}"

        expected_id = manifest.get("issue_4c", {}).get(
            "chain_mapping", {}
        ).get(chain_key, "")
        if expected_id and asset_id != expected_id:
            raise ValueError(
                f"{chain_key}: asset_id={asset_id} "
                f"!= manifest chain_mapping={expected_id}"
            )

        asset = RealAmsterdamAsset(
            asset_id=asset_id,
            address=address_full,
            bag_pand_id=pand_ident,
            bag_verblijfsobject_id=vbo_ident,
            geometry_type=vbo_geom.get("type", "Point"),
            coordinates_x=float(vbo_coords[0]),
            coordinates_y=float(vbo_coords[1]),
            crs="EPSG:4326",
            bouwjaar=int(pand_props.get("bouwjaar", 0)),
            gebruiksdoel=str(vbo_props.get("gebruiksdoel", "")),
            oppervlakte_m2=float(vbo_props.get("oppervlakte", 0)),
        )

        # Set factory-only verification fields via object.__setattr__
        object.__setattr__(asset, "source_integrity_verified", True)
        object.__setattr__(asset, "asset_identity_verified", True)
        object.__setattr__(asset, "building_geometry_verified", True)
        object.__setattr__(asset, "use_class_verified", bool(vbo_props.get("gebruiksdoel")))
        # Pand footprint — persist full provenance from verified evidence
        object.__setattr__(asset, "pand_footprint_area_m2", footprint_evidence.footprint_area_m2)
        object.__setattr__(asset, "pand_geometry_source_crs", footprint_evidence.source_crs)
        object.__setattr__(asset, "pand_geometry_area_crs", footprint_evidence.area_crs)
        object.__setattr__(asset, "pand_geometry_algorithm", footprint_evidence.geometry_algorithm)
        object.__setattr__(asset, "pand_geometry_algorithm_version", footprint_evidence.geometry_algorithm_version)
        object.__setattr__(asset, "pand_geometry_shapely_version", footprint_evidence.shapely_version)
        object.__setattr__(asset, "pand_geometry_pyproj_version", footprint_evidence.pyproj_version)
        object.__setattr__(asset, "pand_geometry_proj_version", footprint_evidence.proj_version)
        object.__setattr__(asset, "pand_geometry_source_artifact_sha256", footprint_evidence.source_artifact_sha256)
        object.__setattr__(asset, "pand_geometry_source_normalized_sha256", footprint_evidence.source_normalized_sha256)
        object.__setattr__(asset, "pand_geometry_feature_id", footprint_evidence.pand_feature_id)
        object.__setattr__(asset, "pand_source_id", footprint_evidence.pand_source_id)
        object.__setattr__(asset, "pand_geometry_type", footprint_evidence.source_geometry_type)
        # V2 provenance metadata
        object.__setattr__(asset, "chain_id", chain_key)
        object.__setattr__(asset, "vbo_feature_id", vbo_feature_id)
        object.__setattr__(asset, "vbo_raw_source_id", matched_vbo_raw_source_id)
        object.__setattr__(asset, "adres_source_id", adres_source_id)

        assets.append(asset)

    return assets


def pilot_assets() -> list[RealAmsterdamAsset]:
    """Backward-compatible wrapper — loads from sealed evidence."""
    return load_pilot_assets()
