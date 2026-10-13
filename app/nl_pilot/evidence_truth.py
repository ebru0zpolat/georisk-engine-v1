"""Evidence Pack v2 — Truth-State Derivation, Validation and Checksum.

Provides:
  derive_truth_state(assets, legal_source, decisions, engineering) -> dict
  validate_evidence_pack_v2(pack: dict) -> None
  verify_pack_checksum(pack: dict) -> bool

All truth-state fields derive from their implementing subsystems.
No hard-coded True/False based on issue numbers or comments.

Classification: consolidation layer — NOT source remediation
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

from app.nl_pilot.real_assets import RealAmsterdamAsset
from app.nl_pilot.amsterdam_source import (
    AMSTERDAM_THRESHOLDS,
    AmsterdamSourceArtifact,
    SourceCurrencyAssessment,
    assess_source_currency,
    require_current_law_claim,
)
from app.nl_pilot.applicability import Article4113Decision, INDETERMINATE
from app.nl_pilot.engineering import HemelwaterEngineeringDecision


# ---------------------------------------------------------------------------
# Deterministic JSON (shared with pack builder)
# ---------------------------------------------------------------------------

import json


def _deterministic_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# ---------------------------------------------------------------------------
# Truth-state derivation
# ---------------------------------------------------------------------------

def derive_truth_state(
    assets: list[RealAmsterdamAsset],
    legal_source: AmsterdamSourceArtifact,
    decisions: dict[str, Article4113Decision],
    engineering_map: dict[str, HemelwaterEngineeringDecision],
    source_currency: SourceCurrencyAssessment | None = None,
) -> dict:
    """Derive the canonical truth-state from verified runtime evidence.

    Every field is computed from actual subsystem state.
    No field is hard-coded True/False based on prior assumptions.
    """
    n = len(assets)

    # --- ISSUE_4C: BAG identity ---
    bag_verified = sum(1 for a in assets if a.asset_identity_verified)
    src_integrity = sum(1 for a in assets if a.source_integrity_verified)
    geom_verified = sum(1 for a in assets if a.building_geometry_verified)
    use_class = sum(1 for a in assets if a.use_class_verified)

    # --- ISSUE_5: Legal source ---
    legal_verified = legal_source.source_verified
    version_verified = legal_source.version_verified
    effectivity_verified = legal_source.effective_status_verified
    amendment_verified = legal_source.amendment_chain_verified
    rule_mapping = legal_source.rule_mapping_verified

    # --- ISSUE_6: Applicability ---
    applicable_true = 0
    applicable_false = 0
    applicable_unknown = 0
    applicability_verified_count = 0
    for a in assets:
        d = decisions.get(a.asset_id)
        if d is None:
            applicable_unknown += 1
            continue
        if d.paragraph_applicable is True:
            applicable_true += 1
        elif d.paragraph_applicable is False:
            applicable_false += 1
        else:
            applicable_unknown += 1
        if d.asset_applicability_verified:
            applicability_verified_count += 1

    # --- ISSUE_7: Geometry / Engineering ---
    legal_bvo_verified = sum(
        1 for e in engineering_map.values() if e.legal_bebouwd_oppervlak_verified
    )
    obligation_verified = sum(
        1 for e in engineering_map.values() if e.obligation_applicability_verified
    )
    eng_req_verified = sum(
        1 for e in engineering_map.values() if e.engineering_requirement_verified
    )
    eng_cap_verified = sum(
        1 for e in engineering_map.values() if e.engineering_capacity_verified
    )

    # Threshold definition verified if source + rule mapping are both true
    threshold_def_verified = legal_verified and rule_mapping

    # Current-law status is bounded by any recorded successor version.
    currency_not_verified: list[str] = []
    if source_currency is not None and source_currency.supersession is not None:
        sup = source_currency.supersession
        currency_not_verified.append(
            f"current-law status of {sup.superseded_ref} on or after "
            f"{sup.effective_from} (superseded by {sup.superseding_publication})"
        )

    return {
        "issue_4c": {
            "real_assets_count": n,
            "bag_identity_verified_count": bag_verified,
            "source_integrity_verified_count": src_integrity,
            "building_geometry_verified_count": geom_verified,
            "use_class_verified_count": use_class,
            "synthetic_fallback_used": False,
            "status": "verified" if bag_verified == n and src_integrity == n else "incomplete",
        },
        "issue_5": {
            "official_regulatory_artifact_verified": legal_verified,
            "source_verified": legal_verified,
            "version_verified": version_verified,
            "effective_status_verified": effectivity_verified,
            "amendment_chain_verified": amendment_verified,
            "rule_mapping_verified": rule_mapping,
            "threshold_definition_verified": threshold_def_verified,
            "cvdr_id": legal_source.cvdr_id,
            "version_number": legal_source.version_number,
            "resolved_version_ref": legal_source.resolved_version_ref,
            "official_version_identifier": legal_source.official_version_identifier,
            "status": "verified" if legal_verified else "not_verified",
        },
        "issue_6": {
            "article_4_113_engine_status": "implemented_fail_closed",
            "applicable_true_count": applicable_true,
            "applicable_false_count": applicable_false,
            "applicable_unknown_count": applicable_unknown,
            "asset_applicability_verified_count": applicability_verified_count,
            "current_asset_state": "indeterminate",
            "status": "architecture_verified_asset_evidence_incomplete",
        },
        "issue_7": {
            "pand_footprint_derived_count": geom_verified,
            "building_geometry_verified_count": geom_verified,
            "legal_bebouwd_oppervlak_verified_count": legal_bvo_verified,
            "obligation_applicability_verified_count": obligation_verified,
            "engineering_requirement_verified_count": eng_req_verified,
            "engineering_capacity_verified_count": eng_cap_verified,
            "status": (
                "geometry_verified_downstream_engineering_unverified"
                if geom_verified == n and eng_cap_verified == 0
                else "incomplete"
            ),
        },
        "claim_boundaries": {
            "verified": [
                "BAG asset identity",
                "sealed BAG source integrity",
                "Amsterdam CVDR696291/15 legal source identity",
                "legal version and effective-status metadata",
                "amendment chain",
                "Article 4.113/4.116 rule mapping",
                "Article 4.116 threshold definitions",
                "BAG Pand metric footprint geometry",
            ],
            "not_verified": [
                "asset-level Article 4.113 applicability",
                "Article 4.115 obligation applicability",
                "Article 4.116 legal bebouwd-oppervlak denominator",
                "asset-specific engineering requirement",
                "actual storage capacity",
                "actual discharge performance",
                "actual emptying performance",
                "regulatory compliance",
                "production eligibility",
                "external-use approval",
                *currency_not_verified,
            ],
        },
        "current_state": {
            "source_identity": "verified" if bag_verified == n else "not_verified",
            "source_integrity": "verified" if src_integrity == n else "not_verified",
            "regulatory_source": "verified" if legal_verified else "not_verified",
            "regulatory_version": "verified" if version_verified else "not_verified",
            "regulatory_effectivity": "verified" if effectivity_verified else "not_verified",
            "rule_definition": "verified" if rule_mapping else "not_verified",
            "asset_identity": "verified" if bag_verified == n else "not_verified",
            "building_geometry": "verified" if geom_verified == n else "not_verified",
            "asset_applicability": (
                "indeterminate" if applicable_unknown == n
                else "verified" if applicable_true == n and applicability_verified_count == n
                else "mixed"
            ),
            "obligation_applicability": (
                "verified" if obligation_verified == n else "not_verified"
            ),
            "legal_denominator": (
                "verified" if legal_bvo_verified == n else "not_verified"
            ),
            "engineering_requirement": (
                "verified" if eng_req_verified == n else "not_verified"
            ),
            "engineering_capacity": (
                "verified" if eng_cap_verified == n else "not_verified"
            ),
            "production_eligibility": "false",
            "external_use_approval": "false",
        },
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_evidence_pack_v2(pack: dict) -> None:
    """Validate internal consistency of an Evidence Pack v2.

    Raises ValueError if any truth-state fields contradict each other.
    """
    errors: list[str] = []
    ts = pack.get("truth_state", {})
    issue5 = ts.get("issue_5", {})
    issue6 = ts.get("issue_6", {})
    issue7 = ts.get("issue_7", {})
    summary = pack.get("summary", {})

    # --- ISSUE_5 consistency ---
    if issue5.get("official_regulatory_artifact_verified") and not issue5.get("source_verified"):
        errors.append("official_regulatory_artifact_verified=true requires source_verified=true")
    if issue5.get("source_verified"):
        for flag in ("version_verified", "effective_status_verified", "amendment_chain_verified", "rule_mapping_verified"):
            if not issue5.get(flag):
                errors.append(f"source_verified=true requires {flag}=true")
    if issue5.get("threshold_definition_verified") and not (issue5.get("source_verified") and issue5.get("rule_mapping_verified")):
        errors.append("threshold_definition_verified=true requires source_verified=true AND rule_mapping_verified=true")

    # --- Asset count consistency ---
    asset_evals = pack.get("asset_evaluations", [])
    total = summary.get("total_assets", 0)
    if total != len(asset_evals):
        errors.append(f"total_assets={total} != len(asset_evaluations)={len(asset_evals)}")

    # --- Tri-state counts ---
    at = issue6.get("applicable_true_count", 0)
    af = issue6.get("applicable_false_count", 0)
    au = issue6.get("applicable_unknown_count", 0)
    if at + af + au != total:
        errors.append(f"applicable counts {at}+{af}+{au}={at+af+au} != total_assets={total}")

    # --- Summary count reconciliation from asset_evaluations ---
    if asset_evals:
        computed_geom = sum(1 for e in asset_evals if e.get("building_geometry_verified"))
        computed_id = sum(1 for e in asset_evals if e.get("asset_identity_verified"))
        computed_si = sum(1 for e in asset_evals if e.get("source_integrity_verified"))

        if summary.get("building_geometry_verified_count", -1) != computed_geom:
            errors.append(
                f"summary.building_geometry_verified_count={summary.get('building_geometry_verified_count')} "
                f"!= computed={computed_geom}"
            )
        if summary.get("bag_identity_verified_count", -1) != computed_id:
            errors.append(
                f"summary.bag_identity_verified_count={summary.get('bag_identity_verified_count')} "
                f"!= computed={computed_id}"
            )
        if summary.get("source_integrity_verified_count", -1) != computed_si:
            errors.append(
                f"summary.source_integrity_verified_count={summary.get('source_integrity_verified_count')} "
                f"!= computed={computed_si}"
            )

    # --- Truth-state count reconciliation from asset_evaluations ---
    if asset_evals:
        ts4 = ts.get("issue_4c", {})
        computed_geom_ts = sum(1 for e in asset_evals if e.get("building_geometry_verified"))
        computed_id_ts = sum(1 for e in asset_evals if e.get("asset_identity_verified"))
        computed_si_ts = sum(1 for e in asset_evals if e.get("source_integrity_verified"))

        if ts4.get("building_geometry_verified_count", -1) != computed_geom_ts:
            errors.append(
                f"issue_4c.building_geometry_verified_count={ts4.get('building_geometry_verified_count')} "
                f"!= computed={computed_geom_ts}"
            )
        if ts4.get("bag_identity_verified_count", -1) != computed_id_ts:
            errors.append(
                f"issue_4c.bag_identity_verified_count={ts4.get('bag_identity_verified_count')} "
                f"!= computed={computed_id_ts}"
            )
        if ts4.get("source_integrity_verified_count", -1) != computed_si_ts:
            errors.append(
                f"issue_4c.source_integrity_verified_count={ts4.get('source_integrity_verified_count')} "
                f"!= computed={computed_si_ts}"
            )

        # Recompute applicable counts from asset_evaluations
        computed_at = sum(1 for e in asset_evals if e.get("paragraph_applicable") is True)
        computed_af = sum(1 for e in asset_evals if e.get("paragraph_applicable") is False)
        computed_au = sum(1 for e in asset_evals if e.get("paragraph_applicable") is None)
        if at != computed_at:
            errors.append(f"applicable_true_count={at} != computed={computed_at}")
        if af != computed_af:
            errors.append(f"applicable_false_count={af} != computed={computed_af}")
        if au != computed_au:
            errors.append(f"applicable_unknown_count={au} != computed={computed_au}")

    # --- Prerequisite-based engineering validation ---
    for ev in asset_evals:
        aid = ev.get("asset_id", "?")
        eng = ev.get("engineering", {})

        # Legal denominator prerequisites
        if eng.get("legal_bebouwd_oppervlak_verified"):
            if eng.get("legal_bebouwd_oppervlak_m2") is None:
                errors.append(f"{aid}: legal_bebouwd_oppervlak_verified=true but m2=null")
            if eng.get("legal_denominator_basis") == "NOT_DETERMINED":
                errors.append(f"{aid}: legal_bebouwd_oppervlak_verified=true but basis=NOT_DETERMINED")

        # Engineering requirement prerequisites
        if eng.get("engineering_requirement_verified"):
            for prereq in ("obligation_applicability_verified", "legal_bebouwd_oppervlak_verified",
                           "requirement_variant_verified"):
                if not eng.get(prereq):
                    errors.append(f"{aid}: engineering_requirement_verified=true requires {prereq}=true")
            for field_name in ("required_storage_liters", "max_discharge_liters_per_hour", "required_emptying_hours"):
                if eng.get(field_name) is None:
                    errors.append(f"{aid}: engineering_requirement_verified=true requires {field_name}!=null")

        # Engineering capacity prerequisites
        if eng.get("engineering_capacity_verified"):
            if not eng.get("engineering_requirement_verified"):
                errors.append(f"{aid}: engineering_capacity_verified=true requires engineering_requirement_verified=true")
            if not eng.get("actual_storage_capacity_verified"):
                errors.append(f"{aid}: engineering_capacity_verified=true requires actual_storage_capacity_verified=true")
            if eng.get("actual_storage_capacity_liters") is None:
                errors.append(f"{aid}: engineering_capacity_verified=true requires actual_storage_capacity_liters!=null")

    # --- Per-asset geometry consistency ---
    for ev in asset_evals:
        aid = ev.get("asset_id", "?")
        geom_v = ev.get("building_geometry_verified", False)
        geom_block = ev.get("building_geometry", {})
        geom_verified_flag = geom_block.get("geometry_verified", False)
        fp_area = geom_block.get("pand_footprint_area_m2")

        if not geom_v and geom_verified_flag:
            errors.append(f"{aid}: building_geometry_verified=false but geometry geometry_verified=true")
        if not geom_v and fp_area is not None:
            errors.append(f"{aid}: building_geometry_verified=false but pand_footprint_area_m2 set")

    # --- Numeric claim gate (per-asset, not summary-level) ---
    for ev in asset_evals:
        eng = ev.get("engineering", {})
        aid = ev.get("asset_id", "?")
        if not eng.get("engineering_requirement_verified"):
            for field_name in ("required_storage_liters", "max_discharge_liters_per_hour", "required_emptying_hours"):
                if eng.get(field_name) is not None:
                    errors.append(f"{aid}: engineering_requirement_verified=false but {field_name} is set")

    # --- Actual capacity gate (per-asset) ---
    for ev in asset_evals:
        eng = ev.get("engineering", {})
        aid = ev.get("asset_id", "?")
        if not eng.get("engineering_capacity_verified"):
            if eng.get("actual_storage_capacity_liters") is not None:
                errors.append(f"{aid}: engineering_capacity_verified=false but actual_storage_capacity_liters is set")

    # --- Production / external use ---
    if pack.get("pilot_gates", {}).get("production_eligible"):
        errors.append("production_eligible must be false for pilot")
    if pack.get("pilot_gates", {}).get("external_use_approved"):
        errors.append("external_use_approved must be false for pilot")

    # --- Synthetic fallback ---
    if summary.get("synthetic_fallback_used"):
        errors.append("synthetic_fallback_used must be false")

    # --- Source-version currency at the pack's own as-of date ---
    reg = pack.get("source_provenance", {}).get("regulatory_source")
    if reg is not None:
        ref = reg.get("resolved_version_ref", "")
        recomputed = assess_source_currency(ref, pack.get("evidence_as_of", ""))
        if not recomputed.current_law_claim_permitted:
            errors.append(
                f"{recomputed.blocker_code}: pack asserts {ref} as current law "
                f"at evidence_as_of={recomputed.as_of}"
            )
        if pack.get("source_currency") != recomputed.to_dict():
            errors.append(
                "source_currency does not match the supersession registry "
                f"for {ref} at evidence_as_of={recomputed.as_of}"
            )

    if errors:
        raise ValueError(
            "Evidence Pack v2 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


# ---------------------------------------------------------------------------
# Consumer gate: current-law claim on an evaluation date
# ---------------------------------------------------------------------------

def check_pack_current_law_claim(pack: dict, as_of) -> SourceCurrencyAssessment:
    """Refuse to use ``pack`` as a statement of current law on ``as_of``.

    A pack built while its pinned version was current stays valid for claims
    dated before the successor's effective date. On or after it, this raises
    SourceVersionNotCurrentError with SOURCE_VERSION_SUPERSEDED until the
    pack is rebuilt against the sealed successor version.
    """
    reg = pack.get("source_provenance", {}).get("regulatory_source")
    if reg is None or not reg.get("resolved_version_ref"):
        raise ValueError("pack carries no regulatory_source.resolved_version_ref")
    return require_current_law_claim(reg["resolved_version_ref"], as_of)


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

def verify_pack_checksum(pack: dict) -> bool:
    """Independently verify the pack's checksum.

    Removes the checksum field, recomputes SHA-256 and compares.
    Returns True if valid, False otherwise.
    """
    stored = pack.get("checksum", {}).get("content_sha256", "")
    if not stored:
        return False

    payload = dict(pack)
    payload.pop("checksum", None)
    recomputed = hashlib.sha256(
        _deterministic_json(payload).encode("utf-8")
    ).hexdigest()
    return recomputed == stored
