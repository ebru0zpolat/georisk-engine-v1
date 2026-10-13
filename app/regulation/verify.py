"""Asset-level regulatory screening engine.

Deterministic, fail-closed verification of portfolio assets against
a set of regulatory rules.  Each asset is checked against every
applicable rule; the overall status is computed from individual
rule results.

This engine does NOT:
- Access external data sources
- Modify any readiness flags
- Produce compliance certifications
- Replace human legal review

Fail-closed invariant:
  1. applicability not verified → applicability_unverified
  2. official source artifact not verified → source_unverified
  3. threshold source not verified → source_unverified
  4. engineered data missing → insufficient_data
  5. numeric comparison → threshold_satisfied / threshold_not_satisfied

Precedence is strictly ordered: each gate blocks progression to the
next.  An unverified source cannot be "solved" by providing
engineered data.

Status terminology uses neutral threshold language (NOT compliance
language).  'threshold_satisfied' means the engineered value meets
the numeric threshold AND the threshold source was independently
verified AND the official source artifact was independently
retrieved and hashed — it does NOT mean the asset is legally
compliant, because applicability may be incomplete and exemptions
may apply.
"""

from __future__ import annotations

from app.regulation.agv_geometry import verify_current_agv_geometry
from app.regulation.models import (
    ApplicabilityFilter,
    AssetVerification,
    OfficialSourceArtifact,
    RegulatoryRule,
    RuleResult,
    ThresholdProvenance,
)


def verify_source_artifact(
    artifact: OfficialSourceArtifact,
) -> tuple[bool, str]:
    """Verify that an official source artifact has been independently
    retrieved and its content hashed.

    Returns (is_valid, reason).

    This confirms:
      1. The artifact status is 'current' (not draft/superseded/repealed)
      2. source_checksums_verified is True
      3. artifact_sha256 is a real SHA-256 (not PLACEHOLDER_NOT_VERIFIED)

    This does NOT confirm:
      - The publication content is legally correct
      - The threshold mapping is accurate
      - The asset is legally applicable
    """
    if artifact.status != "current":
        return False, (
            f"Artifact '{artifact.source_id}' has status '{artifact.status}'; "
            f"only 'current' artifacts pass verification"
        )

    if not artifact.source_checksums_verified:
        return False, (
            f"Artifact '{artifact.source_id}' has source_checksums_verified=False; "
            f"an independent retrieval and hash computation is required"
        )

    if artifact.artifact_sha256 == "PLACEHOLDER_NOT_VERIFIED":
        return False, (
            f"Artifact '{artifact.source_id}' has placeholder hash; "
            f"real SHA-256 of retrieved artifact bytes is required"
        )

    # Validate SHA-256 format
    if len(artifact.artifact_sha256) != 64 or not all(
        c in "0123456789abcdef" for c in artifact.artifact_sha256
    ):
        return False, (
            f"Artifact '{artifact.source_id}' has invalid SHA-256 format: "
            f"'{artifact.artifact_sha256[:16]}...'"
        )

    return True, "Artifact verification passed"


def verify_provenance_chain(
    provenance: ThresholdProvenance,
    artifacts: dict[str, OfficialSourceArtifact],
) -> tuple[bool, str]:
    """Verify the full provenance chain from artifact → article → rule.

    Returns (is_valid, reason).

    This checks:
      1. The referenced artifact exists in the registry
      2. The artifact is verified (passes verify_source_artifact)
      3. The artifact_sha256 matches the provenance record
      4. The provenance is marked as verified
    """
    artifact = artifacts.get(provenance.source_id)
    if artifact is None:
        return False, (
            f"Provenance for rule '{provenance.rule_id}' references "
            f"unknown source '{provenance.source_id}'"
        )

    is_valid, reason = verify_source_artifact(artifact)
    if not is_valid:
        return False, (
            f"Provenance for rule '{provenance.rule_id}': "
            f"artifact verification failed — {reason}"
        )

    if provenance.official_artifact_sha256 != artifact.artifact_sha256:
        return False, (
            f"Provenance for rule '{provenance.rule_id}': "
            f"artifact SHA mismatch — provenance has "
            f"'{provenance.official_artifact_sha256[:16]}...' "
            f"but artifact has '{artifact.artifact_sha256[:16]}...'"
        )

    if not provenance.provenance_verified:
        return False, (
            f"Provenance for rule '{provenance.rule_id}' is not marked "
            f"as provenance_verified=True"
        )

    return True, "Provenance chain verified"


def _matches_filter(
    asset: dict,
    filt: ApplicabilityFilter,
) -> bool:
    """Check if an asset matches ALL non-None fields of a filter."""
    if filt.municipality and asset.get("municipality") != filt.municipality:
        return False
    if filt.use_class and asset.get("use_class") != filt.use_class:
        return False
    if filt.water_authority and asset.get("water_authority") != filt.water_authority:
        return False
    built_area = asset.get("built_area_m2")
    if filt.min_built_area_m2 is not None:
        if built_area is None or built_area < filt.min_built_area_m2:
            return False
    if filt.max_built_area_m2 is not None:
        if built_area is None or built_area > filt.max_built_area_m2:
            return False
    return True


def _evaluate_rule(
    asset: dict,
    rule: RegulatoryRule,
) -> RuleResult:
    """Evaluate a single rule against an asset.

    Precedence (strictly fail-closed):
      1. not_applicable (asset doesn't match filter)
      2. source_unverified (threshold_source_verified=False)
      3. insufficient_data (engineered_value is None)
      4. threshold_satisfied / threshold_not_satisfied (numeric comparison)

    An unverified regulatory source must not be "solved" by
    providing engineered data — the source itself is the blocker.

    Returns neutral threshold status (NOT compliance language).
    """
    applicable = _matches_filter(asset, rule.applicability_filter)

    if not applicable:
        return RuleResult(
            rule_id=rule.rule_id,
            applicable=False,
            status="not_applicable",
            engineered_value=None,
            threshold_value=rule.threshold_value,
            threshold_unit=rule.threshold_unit,
            evidence_note="Asset does not match applicability filter",
        )

    # FAIL-CLOSED precedence: source verification BEFORE data check.
    # An unverified regulatory source must not be "solved" by
    # providing engineered data — the source itself is the blocker.
    if not rule.threshold_source_verified:
        engineered_value = asset.get(rule.parameter_name)
        return RuleResult(
            rule_id=rule.rule_id,
            applicable=True,
            status="source_unverified",
            engineered_value=engineered_value,
            threshold_value=rule.threshold_value,
            threshold_unit=rule.threshold_unit,
            evidence_note=(
                f"Threshold source for '{rule.rule_id}' is unverified "
                f"(threshold_source_verified=False); cannot produce "
                f"threshold_satisfied/threshold_not_satisfied. "
                f"Candidate: {engineered_value} {rule.threshold_unit} "
                f"vs threshold {rule.threshold_value} {rule.threshold_unit}"
            ),
        )

    # Extract the engineered value from the asset
    engineered_value = asset.get(rule.parameter_name)

    if engineered_value is None:
        return RuleResult(
            rule_id=rule.rule_id,
            applicable=True,
            status="insufficient_data",
            engineered_value=None,
            threshold_value=rule.threshold_value,
            threshold_unit=rule.threshold_unit,
            evidence_note=f"Asset does not provide '{rule.parameter_name}' — cannot verify threshold",
        )

    # Compare — neutral threshold language
    if rule.comparison == "gte":
        satisfied = engineered_value >= rule.threshold_value
    elif rule.comparison == "lte":
        satisfied = engineered_value <= rule.threshold_value
    elif rule.comparison == "eq":
        satisfied = abs(engineered_value - rule.threshold_value) < 1e-9
    else:
        return RuleResult(
            rule_id=rule.rule_id,
            applicable=True,
            status="insufficient_data",
            engineered_value=engineered_value,
            threshold_value=rule.threshold_value,
            threshold_unit=rule.threshold_unit,
            evidence_note=f"Unknown comparison operator '{rule.comparison}'",
        )

    status = "threshold_satisfied" if satisfied else "threshold_not_satisfied"

    return RuleResult(
        rule_id=rule.rule_id,
        applicable=True,
        status=status,
        engineered_value=engineered_value,
        threshold_value=rule.threshold_value,
        threshold_unit=rule.threshold_unit,
        evidence_note=(
            f"Engineered value {engineered_value} {rule.threshold_unit} "
            f"{'≥' if rule.comparison == 'gte' else '≤'} "
            f"threshold {rule.threshold_value} {rule.threshold_unit}"
        ),
    )


def verify_asset(
    asset: dict,
    rules: list[RegulatoryRule],
    applicability_verified: bool = False,
    applicability_reason: str = "",
) -> AssetVerification:
    """Verify a single asset against all rules.

    Parameters
    ----------
    asset : dict
        Asset dictionary with at minimum: asset_id, address,
        coordinates (crs, x, y), built_area_m2, use_class,
        municipality, water_authority.
    rules : list[RegulatoryRule]
        Rules to check against.
    applicability_verified : bool
        Whether asset-level applicability has been independently
        pre-verified (e.g. by BAG identity check, building date
        verification, use-class confirmation, exemption review).
        When False, overall_status is set to
        'applicability_unverified' regardless of threshold results.
    applicability_reason : str
        Explanation of why the asset is/isn't applicable.

    Fail-closed behavior:
        When applicability_verified=False, the overall_status is
        ALWAYS 'applicability_unverified' — even if all thresholds
        happen to be satisfied.  When any rule has
        threshold_source_verified=False, the overall_status is
        'source_unverified' — the system cannot produce a threshold
        determination from an unverified source.
    """
    geometry_verified, geometry_reason = verify_current_agv_geometry(asset)
    if not geometry_verified:
        applicability_verified = False
        applicability_reason = geometry_reason

    coords = asset.get("coordinates", {})
    crs = coords.get("crs", "EPSG:28992")

    rule_results = []
    for rule in rules:
        result = _evaluate_rule(asset, rule)
        rule_results.append(result)

    # Fail-closed: applicability not verified → overall status is unverified
    if not applicability_verified:
        return AssetVerification(
            asset_id=asset["asset_id"],
            address=asset.get("address", ""),
            crs=crs,
            x=coords.get("x", 0.0),
            y=coords.get("y", 0.0),
            built_area_m2=asset.get("built_area_m2", 0.0),
            use_class=asset.get("use_class", ""),
            municipality=asset.get("municipality", ""),
            water_authority=asset.get("water_authority", ""),
            asset_applicability_verified=False,
            applicability_reason=applicability_reason or "Applicability not independently verified",
            rule_results=rule_results,
            overall_status="applicability_unverified",
        )

    # Compute overall status from threshold results
    applicable_results = [r for r in rule_results if r.applicable]
    if not applicable_results:
        overall = "not_applicable"
    # FAIL-CLOSED: any source_unverified → overall is source_unverified
    elif any(r.status == "source_unverified" for r in applicable_results):
        overall = "source_unverified"
    elif all(r.status == "threshold_satisfied" for r in applicable_results):
        overall = "threshold_satisfied"
    elif any(r.status == "threshold_not_satisfied" for r in applicable_results):
        overall = "threshold_not_satisfied"
    elif any(r.status == "insufficient_data" for r in applicable_results):
        has_satisfied = any(r.status == "threshold_satisfied" for r in applicable_results)
        has_insufficient = any(r.status == "insufficient_data" for r in applicable_results)
        overall = "partial" if has_satisfied and has_insufficient else "insufficient_data"
    else:
        overall = "not_applicable"

    return AssetVerification(
        asset_id=asset["asset_id"],
        address=asset.get("address", ""),
        crs=crs,
        x=coords.get("x", 0.0),
        y=coords.get("y", 0.0),
        built_area_m2=asset.get("built_area_m2", 0.0),
        use_class=asset.get("use_class", ""),
        municipality=asset.get("municipality", ""),
        water_authority=asset.get("water_authority", ""),
        asset_applicability_verified=True,
        applicability_reason=applicability_reason,
        rule_results=rule_results,
        overall_status=overall,
    )


def verify_portfolio(
    assets: list[dict],
    rules: list[RegulatoryRule],
) -> list[AssetVerification]:
    """Verify all assets in a portfolio against the rule set.

    Deterministic output order: assets are processed in input order.
    """
    return [verify_asset(asset, rules) for asset in assets]


# ---------------------------------------------------------------------------
# Pack checksum verification
# ---------------------------------------------------------------------------


def verify_pack_checksum(pack: dict) -> tuple[bool, str]:
    """Verify the stored checksum of a regulatory evidence pack.

    Returns (is_valid, reason).

    This recomputes the deterministic JSON serialization of the pack
    content (excluding the checksum and volatile envelope fields) and
    compares it against the stored ``content_sha256``.

    NOTE: This is a checksum-integrity check, not an external-source
    verification.  It confirms the pack has not been modified since
    generation — it does NOT verify that the underlying source
    publications or threshold values are correct.
    """
    import hashlib
    import json

    stored_checksum = pack.get("checksum", {})
    stored_hash = stored_checksum.get("content_sha256")
    algorithm = stored_checksum.get("algorithm")

    if not stored_hash:
        return False, "No content_sha256 in checksum"
    if algorithm != "SHA-256":
        return False, f"Unsupported algorithm: {algorithm}"

    # Rebuild content dict, excluding checksum and volatile fields
    exclude_keys = {"checksum", "envelope_timestamp", "generated_at"}
    content = {k: v for k, v in pack.items() if k not in exclude_keys}

    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if recomputed == stored_hash:
        return True, "Checksum matches"
    return False, f"Checksum mismatch: stored={stored_hash[:16]}... recomputed={recomputed[:16]}..."
