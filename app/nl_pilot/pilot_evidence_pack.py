"""Real-Data Pilot Evidence Pack Generator — V2.

Consolidates ISSUE_4C + ISSUE_5 + ISSUE_6 + ISSUE_7 into a single
canonical truth-state evidence pack.

Architecture (V2):
  Sealed BAG snapshot → parse assets → load sealed ISSUE_5 legal source
  → evaluate Article 4.113 applicability → derive Pand geometry
  → build V2 pack with truth-state derivation → validate → checksum

Key changes from V1:
  - PILOT_PACK_VERSION = 2, SCHEMA_VERSION = "2.0"
  - Loads sealed legal source via load_sealed_snapshot()
  - Truth-state derived from actual subsystems (no hard-coded booleans)
  - Byte-reproducible (no runtime generated_at in canonical content)
  - claim_boundaries, current_state, evidence_set blocks
  - Validator checks cross-field consistency

Fail-closed invariants:
  - Missing/tampered snapshot → raise (not synthetic fallback)
  - Legal source verification failure → pack build fails
  - asset_applicability_verified = False (always in pilot)
  - engineering_capacity_verified = False (always in pilot)
  - production_eligible = False (always in pilot)

Classification: pilot — NOT production-eligible
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.nl_pilot.real_assets import RealAmsterdamAsset, pilot_assets
from app.nl_pilot.amsterdam_source import (
    AMSTERDAM_THRESHOLDS,
    AmsterdamSourceArtifact,
    load_sealed_snapshot,
    require_current_law_claim,
)
from app.nl_pilot.applicability import (
    Article4113Evidence,
    Article4113Decision,
    evaluate_article_4_113,
    INDETERMINATE,
    NOT_APPLICABLE,
    APPLICABLE,
)
from app.nl_pilot.engineering import (
    HemelwaterEngineeringDecision,
)
from app.nl_pilot.evidence_truth import (
    derive_truth_state,
    validate_evidence_pack_v2,
    verify_pack_checksum,
)


# ---------------------------------------------------------------------------
# Constants — V2
# ---------------------------------------------------------------------------

PILOT_PACK_VERSION = 2
PILOT_PACK_ID = "NL-AMSTERDAM-REAL-DATA-PILOT-V2"
PILOT_SCHEMA_VERSION = "2.0"
GENERATOR_VERSION = "4.0.0"
GENERATOR_SEED = 42

PILOT_CLASSIFICATION_TEMPLATE = {
    "evidence_class": "real_data_pilot",
    "customer_data_status": "public_official_data_only",
    "production_eligible": False,
    "decision_use_approved": False,
}
# Legacy alias for backward compatibility with existing imports
PILOT_CLASSIFICATION = PILOT_CLASSIFICATION_TEMPLATE

# Sealed source paths
_SNAPSHOT_DIR = Path("data/nl_pilot/snapshots/amsterdam-v1")
_LEGAL_SNAPSHOT = _SNAPSHOT_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
_MANIFEST_PATH = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")


# ---------------------------------------------------------------------------
# Deterministic JSON
# ---------------------------------------------------------------------------

def _deterministic_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_checksum(content_dict: dict) -> str:
    payload = dict(content_dict)
    payload.pop("checksum", None)
    return hashlib.sha256(
        _deterministic_json(payload).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Threshold evaluation
# ---------------------------------------------------------------------------

def _evaluate_threshold(
    asset: RealAmsterdamAsset,
    threshold: dict,
    applicability_decision: Article4113Decision,
    engineering: HemelwaterEngineeringDecision,
    *,
    threshold_definition_verified: bool = False,
) -> dict:
    """Evaluate a single threshold for V2 evidence pack.

    Clearly separates:
      - threshold_definition_verified (source-level)
      - paragraph_applicable (asset-level, from Art. 4.113)
      - engineering state (from ISSUE_7)
    """
    paragraph_applicable = applicability_decision.paragraph_applicable
    applicability_state = applicability_decision.applicability_state

    if applicability_state == APPLICABLE:
        status = "applicability_confirmed"
    elif applicability_state == NOT_APPLICABLE:
        status = "not_applicable"
    else:
        status = "applicability_unverified"

    # Comparison only after ALL relevant gates are verified
    comparison_performed = bool(
        threshold_definition_verified
        and paragraph_applicable is True
        and applicability_decision.asset_applicability_verified
        and engineering.obligation_applicability_verified
        and engineering.legal_bebouwd_oppervlak_verified
        and engineering.requirement_variant_verified
        and engineering.engineering_requirement_verified
    )

    return {
        "rule_id": threshold["threshold_id"],
        "article": threshold["article"],
        "paragraph": threshold["lid"],
        "parameter_name": threshold["parameter"],
        "threshold_value": threshold["value"],
        "threshold_unit": threshold["unit"],
        "comparison": threshold["comparison"],
        "legal_source_version": "CVDR696291/15",
        "threshold_definition_verified": threshold_definition_verified,
        "threshold_source_verified": threshold_definition_verified,
        "paragraph_applicable": paragraph_applicable,
        "applicable": paragraph_applicable,
        "municipality_match": applicability_decision.municipality_match,
        "applicability_candidate": applicability_decision.applicability_candidate,
        "asset_applicability_verified": applicability_decision.asset_applicability_verified,
        "obligation_applicable": engineering.obligation_applicable,
        "obligation_applicability_verified": engineering.obligation_applicability_verified,
        "legal_bebouwd_oppervlak_verified": engineering.legal_bebouwd_oppervlak_verified,
        "engineering_requirement_verified": engineering.engineering_requirement_verified,
        "engineered_value": None,
        "comparison_performed": comparison_performed,
        "compliance_result": None if not comparison_performed else None,
        "status": status,
        "source_citation": f"{threshold['article']}, {threshold['lid']}",
        "evidence_note": (
            f"Article 4.116 threshold definition is "
            f"{'verified' if threshold_definition_verified else 'not verified'} "
            f"against the sealed CVDR696291/15 source. "
            f"No asset-level threshold comparison was "
            f"performed because Article 4.113 applicability and downstream "
            f"engineering gates are not verified."
        ),
    }


# ---------------------------------------------------------------------------
# Overall status
# ---------------------------------------------------------------------------

def _derive_overall_status(
    decision: Article4113Decision,
    engineering: HemelwaterEngineeringDecision,
) -> str:
    pa = decision.paragraph_applicable
    if pa is None:
        return "applicability_unverified"
    if pa is False:
        return "not_applicable"
    if not decision.asset_applicability_verified:
        return "applicability_evidence_unverified"
    if not engineering.obligation_applicability_verified:
        return "obligation_applicability_unverified"
    if not engineering.legal_bebouwd_oppervlak_verified:
        return "legal_denominator_unverified"
    if not engineering.requirement_variant_verified:
        return "engineering_variant_unverified"
    if not engineering.engineering_requirement_verified:
        return "engineering_requirement_unverified"
    if not engineering.engineering_capacity_verified:
        return "engineering_capacity_unverified"
    return "fully_verified"


# ---------------------------------------------------------------------------
# Legacy pilot_gates projection
# ---------------------------------------------------------------------------

def _derive_legacy_pilot_gates(truth_state: dict, assets: list[RealAmsterdamAsset]) -> dict:
    """Project truth_state into legacy pilot_gates format."""
    ts4 = truth_state.get("issue_4c", {})
    ts5 = truth_state.get("issue_5", {})
    ts6 = truth_state.get("issue_6", {})
    ts7 = truth_state.get("issue_7", {})
    n = ts4.get("real_assets_count", 0)

    return {
        "real_assets": ts4.get("bag_identity_verified_count", 0) == n and n >= 5,
        "customer_data": 0,
        "public_official_data_only": True,
        "bag_identity_verified": ts4.get("bag_identity_verified_count", 0) == n,
        "official_regulatory_artifact_verified": ts5.get("official_regulatory_artifact_verified", False),
        "threshold_source_verified": ts5.get("threshold_definition_verified", False),
        "asset_applicability_verified": ts6.get("asset_applicability_verified_count", 0) > 0,
        "legal_bebouwd_oppervlak_verified": ts7.get("legal_bebouwd_oppervlak_verified_count", 0) > 0,
        "engineering_capacity_verified": ts7.get("engineering_capacity_verified_count", 0) > 0,
        "production_eligible": False,
        "external_use_approved": False,
    }


# ---------------------------------------------------------------------------
# Evidence as of (deterministic timestamp from sealed sources)
# ---------------------------------------------------------------------------

def _determine_evidence_as_of(manifest: dict) -> str:
    """Deterministic 'as of' timestamp from sealed manifest sources.

    Uses max retrieved_at across all legal source entries.
    Falls back to manifest created_at.
    """
    sources = manifest.get("sources", {})
    legal_ids = [
        "amsterdam-omgevingsplan-cvdr696291",
        "amsterdam-omgevingsplan-cvdr696291-v15-wti",
        "amsterdam-gmb-2026-243575-metadata",
    ]
    timestamps = []
    for lid in legal_ids:
        entry = sources.get(lid, {})
        rt = entry.get("retrieved_at", "")
        if rt:
            timestamps.append(rt)
    if timestamps:
        return max(timestamps)
    return manifest.get("created_at", "unknown")


# ---------------------------------------------------------------------------
# Build evidence pack V2
# ---------------------------------------------------------------------------

def build_pilot_evidence_pack(
    assets: list[RealAmsterdamAsset] | None = None,
    *,
    output_path: str | None = None,
    evidence_map: dict[str, Article4113Evidence] | None = None,
) -> dict:
    """Build the Evidence Pack v2 — truth-state consolidation.

    Parameters
    ----------
    assets : list[RealAmsterdamAsset] | None
        Assets to evaluate. Defaults to pilot_assets().
    output_path : str | None
        If provided, written atomically.
    evidence_map : dict[str, Article4113Evidence] | None
        Per-asset Article 4.113 evidence.

    Raises
    ------
    SystemExit
        If assets cannot be loaded or identity verification fails.
    ValueError
        If sealed legal source verification fails.
    """
    if assets is None:
        assets = pilot_assets()
    if evidence_map is None:
        evidence_map = {}

    # --- FAIL-CLOSED: asset identity ---
    asset_ids = [a.asset_id for a in assets]
    if len(asset_ids) != len(set(asset_ids)):
        duplicates = [aid for aid in asset_ids if asset_ids.count(aid) > 1]
        raise SystemExit(f"FAIL-CLOSED: duplicate asset IDs: {set(duplicates)}")

    # --- Load sealed ISSUE_5 legal source (FAIL-CLOSED) ---
    # This raises on failure — no degraded pack produced.
    legal_source = load_sealed_snapshot(_LEGAL_SNAPSHOT, _MANIFEST_PATH)

    # Load manifest for evidence chain provenance
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))

    # --- Article 4.113 applicability evaluation ---
    decisions: dict[str, Article4113Decision] = {}
    for asset in assets:
        evidence = evidence_map.get(asset.asset_id)
        decision = evaluate_article_4_113(
            municipality=asset.to_dict()["municipality"],
            evidence=evidence,
        )
        decisions[asset.asset_id] = decision

    # --- Per-asset evaluation ---
    engineering_map: dict[str, HemelwaterEngineeringDecision] = {}
    asset_evaluations = []

    for asset in assets:
        decision = decisions[asset.asset_id]

        # Engineering decision
        engineering = HemelwaterEngineeringDecision(
            pand_footprint_area_m2=asset.pand_footprint_area_m2,
            building_geometry_verified=asset.building_geometry_verified,
        )
        engineering_map[asset.asset_id] = engineering

        # Threshold evaluations
        threshold_def_verified = (
            legal_source.source_verified and legal_source.rule_mapping_verified
        )
        evaluations = []
        for name, threshold in AMSTERDAM_THRESHOLDS.items():
            result = _evaluate_threshold(
                asset, threshold, decision, engineering,
                threshold_definition_verified=threshold_def_verified,
            )
            evaluations.append(result)

        overall = _derive_overall_status(decision, engineering)

        # Identity evidence block — derive from manifest
        chain_id = asset.chain_id or f"chain-{asset.asset_id.split('-')[-1]}"
        chain_data = manifest.get("chains", {}).get(chain_id, {})
        sources_map = manifest.get("sources", {})

        # Adres provenance from manifest
        adres_src = sources_map.get(asset.adres_source_id, {}) if asset.adres_source_id else {}
        # VBO provenance from manifest
        vbo_src = sources_map.get(asset.vbo_raw_source_id, {}) if asset.vbo_raw_source_id else {}
        # Pand provenance from manifest
        pand_src = sources_map.get(asset.pand_source_id, {}) if asset.pand_source_id else {}

        identity_evidence = {
            "chain_id": chain_id,
            "adres": {
                "source_id": asset.adres_source_id,
                "bag_identificatie": chain_data.get("adres_identificatie"),
                "artifact_sha256": adres_src.get("artifact_sha256"),
                "normalized_content_sha256": adres_src.get("normalized_content_sha256"),
                "snapshot_path": adres_src.get("snapshot_path"),
                "source_url": adres_src.get("source_url"),
            },
            "vbo": {
                "source_id": asset.vbo_raw_source_id,
                "feature_id": asset.vbo_feature_id,
                "bag_identificatie": asset.bag_verblijfsobject_id,
                "artifact_sha256": vbo_src.get("artifact_sha256"),
                "normalized_content_sha256": vbo_src.get("normalized_content_sha256"),
                "snapshot_path": vbo_src.get("snapshot_path"),
                "source_url": vbo_src.get("source_url"),
            },
            "pand": {
                "source_id": asset.pand_source_id,
                "feature_id": asset.pand_geometry_feature_id,
                "bag_identificatie": asset.bag_pand_id,
                "artifact_sha256": pand_src.get("artifact_sha256"),
                "normalized_content_sha256": pand_src.get("normalized_content_sha256"),
                "snapshot_path": pand_src.get("snapshot_path"),
                "source_url": pand_src.get("source_url"),
            },
        }

        asset_evaluations.append({
            "asset_id": asset.asset_id,
            "address": asset.address,
            "bag_pand_id": asset.bag_pand_id,
            "bag_verblijfsobject_id": asset.bag_verblijfsobject_id,
            "coordinates": {
                "crs": asset.crs,
                "x": asset.coordinates_x,
                "y": asset.coordinates_y,
            },
            "bouwjaar": asset.bouwjaar,
            "gebruiksdoel": asset.gebruiksdoel,
            "oppervlakte_m2": asset.oppervlakte_m2,
            "municipality": "Amsterdam",
            "water_authority": "waterschap-agv",

            # Identity verification
            "asset_identity_verified": asset.asset_identity_verified,
            "source_integrity_verified": asset.source_integrity_verified,
            "use_class_verified": asset.use_class_verified,
            "identity_evidence": identity_evidence,

            # Geometry (ISSUE_7)
            "building_geometry_verified": asset.building_geometry_verified,
            "building_geometry": {
                "source": "BAG Pand",
                "source_id": asset.pand_source_id,
                "bag_pand_id": asset.bag_pand_id,
                "pand_feature_id": asset.pand_geometry_feature_id,
                "geometry_type": asset.pand_geometry_type,
                "source_crs": asset.pand_geometry_source_crs,
                "area_crs": asset.pand_geometry_area_crs,
                "pand_footprint_area_m2": (
                    round(asset.pand_footprint_area_m2, 3)
                    if asset.pand_footprint_area_m2 is not None else None
                ),
                "geometry_verified": asset.building_geometry_verified,
                "source_artifact_sha256": asset.pand_geometry_source_artifact_sha256,
                "source_normalized_sha256": asset.pand_geometry_source_normalized_sha256,
                "geometry_algorithm": asset.pand_geometry_algorithm,
                "geometry_algorithm_version": asset.pand_geometry_algorithm_version,
                "shapely_version": asset.pand_geometry_shapely_version,
                "pyproj_version": asset.pand_geometry_pyproj_version,
                "proj_version": asset.pand_geometry_proj_version,
            },

            # Legal denominator (explicit, claim-safe)
            "legal_denominator": {
                "article": "Artikel 4.116",
                "legal_bebouwd_oppervlak_m2": None,
                "verified": False,
                "basis": "NOT_DETERMINED",
                "note": (
                    "Verified BAG Pand footprint is not automatically promoted "
                    "to the legal Article 4.116 bebouwd-oppervlak denominator."
                ),
            },

            # Applicability (ISSUE_6)
            "applicability": {
                "article": "Artikel 4.113",
                "municipality_match": decision.municipality_match,
                "applicability_candidate": decision.applicability_candidate,
                "paragraph_applicable": decision.paragraph_applicable,
                "paragraph_scope_article": decision.paragraph_scope_article,
                "asset_applicability_verified": decision.asset_applicability_verified,
                "state": decision.applicability_state,
                "trigger": decision.trigger,
                "transition_exemption": decision.transition_exemption,
                "reason_code": decision.reason_code,
                "missing_evidence": decision.missing_evidence,
            },
            "asset_applicability_verified": decision.asset_applicability_verified,
            "applicability_state": decision.applicability_state,
            "paragraph_applicable": decision.paragraph_applicable,

            # Engineering (ISSUE_7)
            "engineering": engineering.to_dict(),

            # Rule evaluation
            "rule_results": evaluations,
            "overall_status": overall,
        })

    # --- Source-version currency at the evidence date (FAIL-CLOSED) ---
    # Raises SourceVersionNotCurrentError if the pinned version was already
    # superseded when the sealed evidence was retrieved.
    source_currency = require_current_law_claim(
        legal_source.resolved_version_ref, _determine_evidence_as_of(manifest)
    )

    # --- Derive truth-state ---
    truth_state = derive_truth_state(
        assets, legal_source, decisions, engineering_map, source_currency
    )

    # --- Legal evidence chain from manifest ---
    legal_sources = manifest.get("sources", {})
    legal_evidence_chain = {}
    for lid in [
        "amsterdam-omgevingsplan-cvdr696291",
        "amsterdam-omgevingsplan-cvdr696291-v15-wti",
        "amsterdam-gmb-2026-243575-metadata",
    ]:
        entry = legal_sources.get(lid, {})
        legal_evidence_chain[lid] = {
            "source_id": lid,
            "source_url": entry.get("source_url"),
            "snapshot_path": entry.get("snapshot_path"),
            "artifact_sha256": entry.get("artifact_sha256"),
            "normalized_content_sha256": entry.get("normalized_content_sha256"),
            "retrieved_at": entry.get("retrieved_at"),
            "authority": entry.get("authority"),
        }

    # --- Regulatory source provenance ---
    ts5 = truth_state["issue_5"]
    regulatory_source = {
        "artifact_source_id": legal_source.source_id,
        "manifest_source_id": "amsterdam-omgevingsplan-cvdr696291",
        "authority": legal_source.authority,
        "title": legal_source.title,
        "source_url": legal_source.source_url,
        "cvdr_id": legal_source.cvdr_id,
        "version_number": legal_source.version_number,
        "resolved_version_ref": legal_source.resolved_version_ref,
        "resolved_version_url": legal_source.resolved_version_url,
        "official_version_identifier": legal_source.official_version_identifier,
        "effective_from": legal_source.effective_from,
        "effective_until": legal_source.effective_until,
        "regulatory_state": legal_source.regulatory_state,
        "latest_amendment_publication": legal_source.latest_amendment_publication,
        "artifact_sha256": legal_source.artifact_sha256,
        "normalized_content_sha256": legal_source.normalized_content_sha256,
        "verification": {
            "source_verified": legal_source.source_verified,
            "version_verified": legal_source.version_verified,
            "effective_status_verified": legal_source.effective_status_verified,
            "amendment_chain_verified": legal_source.amendment_chain_verified,
            "rule_mapping_verified": legal_source.rule_mapping_verified,
        },
    }

    # --- Summary ---
    n = len(assets)
    ts4 = truth_state["issue_4c"]
    ts6 = truth_state["issue_6"]
    ts7 = truth_state["issue_7"]
    threshold_def_verified = ts5.get("threshold_definition_verified", False)

    summary = {
        "total_assets": n,
        "real_assets_verified_count": ts4["bag_identity_verified_count"],
        "bag_identity_verified_count": ts4["bag_identity_verified_count"],
        "source_integrity_verified_count": ts4["source_integrity_verified_count"],
        "official_regulatory_artifact_verified": ts5["official_regulatory_artifact_verified"],
        "threshold_definition_verified": threshold_def_verified,
        "building_geometry_verified_count": ts7["building_geometry_verified_count"],
        "applicable_true_count": ts6["applicable_true_count"],
        "applicable_false_count": ts6["applicable_false_count"],
        "applicable_unknown_count": ts6["applicable_unknown_count"],
        "asset_applicability_verified_count": ts6["asset_applicability_verified_count"],
        "legal_bebouwd_oppervlak_verified_count": ts7["legal_bebouwd_oppervlak_verified_count"],
        "obligation_applicability_verified_count": ts7["obligation_applicability_verified_count"],
        "engineering_requirement_verified_count": ts7["engineering_requirement_verified_count"],
        "engineering_capacity_verified_count": ts7["engineering_capacity_verified_count"],
        "production_eligible": False,
        "external_use_approved": False,
        "synthetic_fallback_used": False,
        "overall_applicability_unverified_count": sum(
            1 for ev in asset_evaluations if ev["overall_status"] == "applicability_unverified"
        ),
    }

    # --- Legacy pilot_gates (projection of truth_state) ---
    pilot_gates = _derive_legacy_pilot_gates(truth_state, assets)

    # --- Classification ---
    verified_assets = [
        a for a in assets if a.asset_identity_verified and a.source_integrity_verified
    ]
    all_verified = len(assets) > 0 and len(verified_assets) == len(assets)
    classification = {
        **PILOT_CLASSIFICATION_TEMPLATE,
        "real_assets_count": len(verified_assets),
        "real_source_artifacts": all_verified,
    }

    # --- Deterministic evidence_as_of ---
    evidence_as_of = _determine_evidence_as_of(manifest)

    # --- Build content dict (without checksum) ---
    content_dict = {
        "pack_id": PILOT_PACK_ID,
        "schema_version": PILOT_SCHEMA_VERSION,
        "pack_version": PILOT_PACK_VERSION,
        "pack_type": "real_data_pilot",
        "regulatory_domain": "hemelwater",
        "evidence_as_of": evidence_as_of,
        "jurisdiction": {
            "level": "municipal",
            "name": "Amsterdam",
            "authority_ids": ["gemeente-amsterdam", "waterschap-agv"],
        },
        "classification": classification,

        # Current-law status of the pinned legal version at evidence_as_of.
        # Consumers must re-check at their own date with
        # check_pack_current_law_claim().
        "source_currency": source_currency.to_dict(),

        # Provenance
        "evidence_set": {
            "manifest": "data/nl_pilot/provenance-manifest-amsterdam-v1.json",
            "snapshot_set": "amsterdam-v1",
            "source_mode": "sealed_official_sources",
            "live_fetch_used": False,
            "synthetic_fallback_used": False,
        },
        "source_provenance": {
            "regulatory_source": regulatory_source,
            "legal_evidence_chain": legal_evidence_chain,
            "cadastre_source": {
                "source_id": "amsterdam-v1-chains",
                "authority": "Kadaster (LV-BAG) / PDOK",
                "endpoint": "https://api.pdok.nl/kadaster/bag/ogc/v2",
                "license": "Public Domain Mark 1.0",
                "crs": "CRS84",
                "snapshot_dir": "data/nl_pilot/snapshots/amsterdam-v1",
                "manifest": "data/nl_pilot/provenance-manifest-amsterdam-v1.json",
            },
        },

        # Regulatory rules
        "regulatory_rules": [
            {
                "rule_id": t["threshold_id"],
                "article": t["article"],
                "paragraph": t["lid"],
                "parameter_name": t["parameter"],
                "threshold_value": t["value"],
                "threshold_unit": t["unit"],
                "comparison": t["comparison"],
                "legal_source_version": "CVDR696291/15",
                "threshold_definition_verified": threshold_def_verified,
                "threshold_source_verified": threshold_def_verified,
                "asset_applicability_verified": False,
                "description": t["description"],
            }
            for name, t in AMSTERDAM_THRESHOLDS.items()
        ],

        # Asset evaluations
        "asset_evaluations": asset_evaluations,

        # Truth-state consolidation
        "truth_state": truth_state,

        # Summary
        "summary": summary,

        # Legacy gates (projection)
        "pilot_gates": pilot_gates,

        # Pack-level note
        "pack_note": (
            "The pack verifies source identity, integrity, legal rule definitions, "
            "and BAG geometry. It does not establish asset-specific legal "
            "applicability or engineering compliance."
        ),

        # Metadata
        "generator_version": GENERATOR_VERSION,
        "deterministic_seed": GENERATOR_SEED,
    }

    # --- Compute checksum (over content excluding checksum field) ---
    checksum = _compute_checksum(content_dict)
    content_dict["checksum"] = {
        "algorithm": "SHA-256",
        "content_sha256": checksum,
    }

    # --- Validate ---
    validate_evidence_pack_v2(content_dict)

    # --- Atomic write ---
    if output_path:
        out = Path(output_path)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(_deterministic_json(content_dict), encoding="utf-8")
        tmp.replace(out)

    return content_dict
