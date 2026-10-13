"""ESRS E1 mapping registry and mapping engine.

Provides versioned ESRS instrument definitions and maps GeoRisk
Engine regulatory screening outputs to ESRS E1 disclosure evidence.

The mapping uses semantic concepts as the stable cross-version
identifier, because disclosure requirement numbers change between
ESRS instrument versions:

2023 CURRENT (Reg. (EU) 2023/2772):
  E1-1            → transition_plan_climate_mitigation
  ESRS2-IRO1/E1   → climate_risk_identification  (cross-reference)
  E1-2            → climate_policies
  E1-3            → climate_actions_and_resources
  E1-6            → ghg_emissions
  E1-7            → ghg_removals_and_carbon_credits
  E1-8            → internal_carbon_pricing
  E1-9            → anticipated_financial_effects

2026 ADOPTED_NOT_IN_FORCE (C(2026)5010):
  E1-1  → transition_plan_climate_mitigation
  E1-2  → climate_risk_identification
  E1-3  → climate_resilience
  E1-4  → climate_policies
  E1-5  → climate_actions_and_resources
  E1-8  → ghg_emissions
  E1-11 → anticipated_financial_effects

Implementation status:
  This is the TARGET ARCHITECTURE specification and initial
  implementation.  Actual ESRS disclosure mapping requires
  portfolio-level data (carrying values, financial statement
  reconciliation) not yet available in the pilot infrastructure.
  The mapping engine produces evidence-readiness assessments,
  NOT compliance verdicts.
"""

from __future__ import annotations

from app.regulation.esrs_mapping import (
    ESRSDisclosureMapping,
    ESRSEvidenceStatus,
    ESRSInstrument,
    ESRSMappingResult,
    ESRSMappingStatus,
    DisclosureRequirement,
    FinancialValue,
)

# ---------------------------------------------------------------------------
# Canonical instrument registry — single source of truth
# ---------------------------------------------------------------------------

def _build_canonical_registry() -> dict[str, ESRSInstrument]:
    """Build the canonical instrument registry.

    All instruments are defined here.  Callers MUST NOT create
    ESRSInstrument objects directly for mapping; the engine
    resolves instrument_id against this registry and rejects
    any metadata mismatch (instrument metadata spoofing defense).
    """
    return {
        "ESRS-2023-2772": esrs_2023_in_force(),
        "ESRS-2026-REVISION": esrs_2026_adopted(),
    }


# Lazy-initialized canonical registry
_CANONICAL_REGISTRY: dict[str, ESRSInstrument] | None = None


def _get_canonical_registry() -> dict[str, ESRSInstrument]:
    global _CANONICAL_REGISTRY
    if _CANONICAL_REGISTRY is None:
        _CANONICAL_REGISTRY = _build_canonical_registry()
    return _CANONICAL_REGISTRY


def get_esrs_instrument(instrument_id: str) -> ESRSInstrument:
    """Resolve an instrument_id against the canonical registry.

    Returns the canonical instrument or raises ValueError.
    """
    registry = _get_canonical_registry()
    if instrument_id not in registry:
        raise ValueError(
            f"Unknown ESRS instrument_id '{instrument_id}'; "
            f"known instruments: {sorted(registry.keys())}"
        )
    return registry[instrument_id]


# ---------------------------------------------------------------------------
# ESRS E1 instruments — versioned
# ---------------------------------------------------------------------------

def esrs_2023_in_force() -> ESRSInstrument:
    """Current in-force ESRS, Reg. (EU) 2023/2772.

    As of August 2026, this is the legally applicable standard.
    Disclosure requirements are numbered E1-1 through E1-9 for E1.

    As amended by Delegated Regulation (EU) 2025/1416 which
    modified phase-in/application provisions.
    """
    return ESRSInstrument(
        instrument_id="ESRS-2023-2772",
        title="European Sustainability Reporting Standards — Climate Change",
        official_identifier="Reg. (EU) 2023/2772",
        legal_state="current_in_force",
        adoption_date="2023-07-31",
        application_from="2024-01-01",
        amendment_ids=("EU-2025-1416",),
        notes=(
            "In-force ESRS as of August 2026.  As amended by "
            "Delegated Regulation (EU) 2025/1416 (phase-in changes). "
            "Parliament/Council scrutiny of the 2026 revision is ongoing."
        ),
    )


def esrs_2026_adopted() -> ESRSInstrument:
    """Adopted-not-in-force ESRS revision, C(2026)5010.

    Adopted by the Commission on 3 July 2026.  Subject to
    two-month Parliament/Council scrutiny period.  MUST NOT
    be used for production disclosure mapping until the
    scrutiny period completes and the regulation enters into force.

    Key numbering changes vs 2023:
      E1-1 = transition_plan (same)
      E1-2 = climate risk identification (was ESRS2-IRO1)
      E1-3 = climate resilience (new)
      E1-4 = policies (was E1-2)
      E1-5 = actions/resources (was E1-3)
      E1-8 = GHG emissions (was E1-6)
      E1-11 = anticipated financial effects (was E1-9)
    """
    return ESRSInstrument(
        instrument_id="ESRS-2026-REVISION",
        title="European Sustainability Reporting Standards — Climate Change (Revised)",
        official_identifier="C(2026)5010",
        legal_state="adopted_not_in_force",
        adoption_date="2026-07-03",
        application_from="2027-01-01",
        transitional_application_from="2026-01-01",
        notes=(
            "Adopted 3 Jul 2026.  Under Parliament/Council scrutiny. "
            "Mandatory application from 2027-01-01.  Optional early "
            "application for FY2026 available.  MUST NOT replace "
            "ESRS-2023-2772 for current reporting until entry into force."
        ),
    )


# ---------------------------------------------------------------------------
# Disclosure requirements — ESRS E1 (2023 in-force)
# ---------------------------------------------------------------------------

def esrs_e1_disclosure_requirements_2023() -> list[DisclosureRequirement]:
    """ESRS E1 disclosure requirements under the 2023 in-force standard.

    Semantic concepts are the stable cross-version identifiers.
    E1-1 is transition_plan_climate_mitigation, NOT
    climate_risk_identification.  Risk identification is covered
    by ESRS 2 IRO-1 (cross-referenced here for completeness).
    """
    return [
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-1",
            semantic_concept="transition_plan_climate_mitigation",
            title="Transition plan for climate change mitigation",
            description=(
                "Transition plan for climate change mitigation, "
                "including GHG emissions reduction targets and "
                "progress towards them."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="ESRS2-IRO1/E1",
            semantic_concept="climate_risk_identification",
            title="Climate risk identification (cross-ref ESRS 2 IRO-1)",
            description=(
                "Process to identify, assess and prioritise climate "
                "transition and physical risks, including scenario "
                "analysis.  Sourced from ESRS 2 IRO-1 applied to E1."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-2",
            semantic_concept="climate_policies",
            title="Policies to manage climate risks",
            description=(
                "Policies adopted to manage climate transition and "
                "physical risks, including their role in the "
                "undertaking's risk management process."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-3",
            semantic_concept="climate_actions_and_resources",
            title="Actions and resources for climate adaptation",
            description=(
                "Actions and resources in relation to climate change "
                "adaptation and mitigation, including implementation "
                "plans, timelines, and resource allocation."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-4",
            semantic_concept="climate_targets_and_performance",
            title="Targets and performance",
            description=(
                "Climate-related targets and the undertaking's "
                "performance against those targets."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-5",
            semantic_concept="energy_consumption_and_mix",
            title="Energy consumption and mix",
            description="Energy consumption and energy mix.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-6",
            semantic_concept="ghg_emissions",
            title="GHG emissions (Scope 1, 2, 3, total)",
            description="Scope 1, Scope 2, Scope 3, and total GHG emissions.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-7",
            semantic_concept="ghg_removals_and_carbon_credits",
            title="GHG removals and carbon credits",
            description=(
                "GHG removals and GHG mitigation projects financed "
                "through carbon credits."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-8",
            semantic_concept="internal_carbon_pricing",
            title="Internal carbon pricing",
            description="Internal carbon price and its governance.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2023-2772",
            disclosure_requirement="E1-9",
            semantic_concept="anticipated_financial_effects",
            title="Anticipated financial effects — physical and transition risks",
            description=(
                "Monetary amount and percentage of assets/business "
                "activities vulnerable to physical and transition "
                "risks; before and after adaptation actions; "
                "acute and chronic breakdown; significant locations."
            ),
            is_materiality_dependent=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Disclosure requirements — ESRS E1 (2026 adopted-not-in-force)
# ---------------------------------------------------------------------------

def esrs_e1_disclosure_requirements_2026() -> list[DisclosureRequirement]:
    """ESRS E1 disclosure requirements under the 2026 adopted revision.

    Uses the NEW numbering but maps to the SAME semantic concepts
    as the 2023 standard where they overlap.  New concepts specific
    to the 2026 revision (e.g. E1-3 climate_resilience) are also
    included.
    """
    return [
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-1",
            semantic_concept="transition_plan_climate_mitigation",
            title="Transition plan for climate change mitigation (revised)",
            description=(
                "Transition plan for climate change mitigation, "
                "including GHG emissions reduction targets."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-2",
            semantic_concept="climate_risk_identification",
            title="Climate risk identification (revised)",
            description=(
                "Process to identify, assess and prioritise climate "
                "transition and physical risks."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-3",
            semantic_concept="climate_resilience",
            title="Climate resilience",
            description=(
                "Analysis of the undertaking's climate resilience "
                "under different scenarios."
            ),
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-4",
            semantic_concept="climate_policies",
            title="Policies to manage climate risks (revised)",
            description="Policies adopted to manage climate risks.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-5",
            semantic_concept="climate_actions_and_resources",
            title="Actions and resources for climate adaptation (revised)",
            description="Actions and resources for climate change adaptation.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-8",
            semantic_concept="ghg_emissions",
            title="GHG emissions (revised)",
            description="Scope 1, Scope 2, Scope 3, and total GHG emissions.",
            is_materiality_dependent=True,
        ),
        DisclosureRequirement(
            instrument_id="ESRS-2026-REVISION",
            disclosure_requirement="E1-11",
            semantic_concept="anticipated_financial_effects",
            title="Anticipated financial effects — physical and transition risks (revised)",
            description=(
                "Monetary amount and percentage of assets/business "
                "activities vulnerable to physical and transition "
                "risks; before and after adaptation actions."
            ),
            is_materiality_dependent=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Mapping engine
# ---------------------------------------------------------------------------

def map_georisk_to_esrs(
    *,
    asset_verifications: list[dict],
    source_unverified_count: int = 0,
    applicability_unverified_count: int = 0,
    total_assets: int = 0,
    financial_value: FinancialValue | None = None,
    instrument: ESRSInstrument | None = None,
    mapping_mode: str = "current_reporting",
) -> ESRSMappingResult:
    """Map GeoRisk Engine screening outputs to ESRS E1 disclosure evidence.

    This produces an evidence-readiness assessment, NOT a compliance
    verdict.  The mapping identifies which ESRS E1 disclosure
    requirements can be partially supported by GeoRisk evidence and
    which remain insufficient.

    Parameters
    ----------
    asset_verifications : list[dict]
        Serialized asset verification results from verify_asset().to_dict().
    source_unverified_count : int
        Number of assets with source_unverified overall status.
    applicability_unverified_count : int
        Number of assets with applicability_unverified overall status.
    total_assets : int
        Total number of assets in the portfolio.
    financial_value : FinancialValue | None
        Portfolio financial value, if available.
    instrument : ESRSInstrument | None
        Target ESRS instrument version.  Defaults to 2023 in-force.
    mapping_mode : str
        "current_reporting" (default) — only allows current_in_force instruments.
        "prospective_analysis" — allows adopted_not_in_force instruments
        for forward-looking analysis only.

    Returns
    -------
    ESRSMappingResult
        Mapping result with evidence status and disclosure mappings.
        NOT a compliance verdict.

    Raises
    ------
    ValueError
        If instrument is unknown, or if a not_in_force instrument is
        used with mapping_mode="current_reporting".

    Fail-closed behavior:
        - Unknown instrument → ValueError
        - not_in_force instrument + current_reporting → ValueError
        - total_assets == 0 → NOT_ASSESSED
        - All assets source_unverified → INSUFFICIENT_EVIDENCE
        - Financial value missing → anticipated_financial_effects = INSUFFICIENT_EVIDENCE
        - Financial value without carrying_value + reconciled + reporting_date → PARTIALLY_MAPPED
    """
    if instrument is None:
        instrument = esrs_2023_in_force()

    # FAIL-CLOSED: resolve against canonical registry (prevents metadata spoofing)
    # Caller-provided ESRSInstrument is IGNORED; we resolve by instrument_id
    # and verify all metadata matches the canonical definition.
    canonical = get_esrs_instrument(instrument.instrument_id)
    if instrument != canonical:
        raise ValueError(
            f"ESRS instrument metadata for '{instrument.instrument_id}' does not "
            f"match canonical registry.  Caller provided legal_state="
            f"'{instrument.legal_state}' but canonical is '{canonical.legal_state}'.  "
            f"Use get_esrs_instrument('{instrument.instrument_id}') to obtain "
            f"the canonical instrument."
        )
    instrument = canonical

    # FAIL-CLOSED: not_in_force instrument requires prospective_analysis mode
    if (
        instrument.legal_state != "current_in_force"
        and mapping_mode != "prospective_analysis"
    ):
        raise ValueError(
            f"ESRS instrument '{instrument.instrument_id}' has legal_state "
            f"'{instrument.legal_state}'; it cannot be used for current "
            f"reporting.  Use mapping_mode='prospective_analysis' explicitly "
            f"for forward-looking analysis with non-current instruments."
        )

    # Get disclosure requirements for this instrument version
    if instrument.instrument_id == "ESRS-2023-2772":
        drs = esrs_e1_disclosure_requirements_2023()
    elif instrument.instrument_id == "ESRS-2026-REVISION":
        drs = esrs_e1_disclosure_requirements_2026()
    else:
        # Should not reach here due to canonical registry check
        raise ValueError(f"Unhandled instrument_id: '{instrument.instrument_id}'")

    # Map each disclosure requirement
    disclosure_mappings: list[ESRSDisclosureMapping] = []

    for dr in drs:
        mapping = _map_single_dr(
            dr=dr,
            asset_verifications=asset_verifications,
            source_unverified_count=source_unverified_count,
            applicability_unverified_count=applicability_unverified_count,
            total_assets=total_assets,
            financial_value=financial_value,
        )
        disclosure_mappings.append(mapping)

    # FAIL-CLOSED: compute overall evidence from child results
    # (not from premature count-based estimation)
    overall_evidence, overall_mapping = _aggregate_overall_status(
        disclosure_mappings=disclosure_mappings,
        total_assets=total_assets,
    )

    # Determine prospective_only flag
    is_prospective = (
        instrument.legal_state != "current_in_force"
        and mapping_mode == "prospective_analysis"
    )

    notes = (
        f"ESRS evidence mapping for {total_assets} assets against "
        f"{instrument.instrument_id} ({instrument.legal_state}).  "
        f"This is an evidence-readiness assessment, NOT a compliance "
        f"verdict."
    )
    if is_prospective:
        notes += (
            "  MAPPING_MODE: prospective_analysis — not suitable for "
            "current production disclosure."
        )

    return ESRSMappingResult(
        portfolio_id="",
        instrument_id=instrument.instrument_id,
        evidence_status=overall_evidence,
        mapping_status=overall_mapping,
        disclosure_mappings=disclosure_mappings,
        financial_value=financial_value,
        prohibited_claims_applied=True,
        prospective_only=is_prospective,
        notes=notes,
    )


def _aggregate_overall_status(
    *,
    disclosure_mappings: list[ESRSDisclosureMapping],
    total_assets: int,
) -> tuple[ESRSEvidenceStatus, ESRSMappingStatus]:
    """Aggregate overall evidence/mapping status from child results.

    This prevents the premature-count estimation bug where
    total_assets=1 + source_unverified_count=0 produced
    EVIDENCE_SUPPORTED_WITH_CAVEATS despite no evidence existing.

    Logic:
      - No disclosures or all NOT_ASSESSED → NOT_ASSESSED / UNMAPPED
      - Any EVIDENCE_SUPPORTED → EVIDENCE_SUPPORTED_WITH_CAVEATS / PARTIALLY_MAPPED
      - All INSUFFICIENT_EVIDENCE → INSUFFICIENT_EVIDENCE / UNMAPPED
      - Mix of INSUFFICIENT and NOT_ASSESSED → INSUFFICIENT_EVIDENCE / UNMAPPED
    """
    if total_assets == 0 or not disclosure_mappings:
        return ESRSEvidenceStatus.NOT_ASSESSED, ESRSMappingStatus.UNMAPPED

    has_any_evidence = any(
        m.evidence_status in (
            ESRSEvidenceStatus.EVIDENCE_SUPPORTED,
            ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS,
        )
        for m in disclosure_mappings
    )
    has_any_insufficient = any(
        m.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
        for m in disclosure_mappings
    )
    has_any_mapped = any(
        m.mapping_status in (
            ESRSMappingStatus.MAPPED,
            ESRSMappingStatus.PARTIALLY_MAPPED,
        )
        for m in disclosure_mappings
    )
    all_not_assessed = all(
        m.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        for m in disclosure_mappings
    )

    if all_not_assessed:
        return ESRSEvidenceStatus.NOT_ASSESSED, ESRSMappingStatus.UNMAPPED

    # Only promote to EVIDENCE_SUPPORTED when actual evidence exists.
    # Financial DR's INSUFFICIENT_EVIDENCE alone does NOT constitute evidence.
    if has_any_evidence and has_any_mapped:
        return ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS, ESRSMappingStatus.PARTIALLY_MAPPED

    if has_any_insufficient:
        # No real evidence exists.  Financial absence without actual
        # evidence → NOT_ASSESSED (not INSUFFICIENT, not SUPPORTED).
        has_non_financial_insufficiency = any(
            m.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
            and m.semantic_concept != "anticipated_financial_effects"
            for m in disclosure_mappings
        )
        if has_non_financial_insufficiency:
            return ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE, ESRSMappingStatus.UNMAPPED
        # Only financial DR is insufficient, no real evidence anywhere
        return ESRSEvidenceStatus.NOT_ASSESSED, ESRSMappingStatus.UNMAPPED

    # Fallback
    return ESRSEvidenceStatus.NOT_ASSESSED, ESRSMappingStatus.UNMAPPED


def _map_single_dr(
    *,
    dr: DisclosureRequirement,
    asset_verifications: list[dict],
    source_unverified_count: int,
    applicability_unverified_count: int,
    total_assets: int,
    financial_value: FinancialValue | None,
) -> ESRSDisclosureMapping:
    """Map a single disclosure requirement based on available evidence.

    Returns neutral evidence/mapping status — never compliance language.

    Design decisions:
    - Threshold results are NOT adaptation action evidence
    - Financial mapping requires carrying_value + reconciled + reporting_date
    - GHG data is never produced by GeoRisk
    - transition_plan and climate_risk_identification require
      undertaking-level data not available from property screening
    """
    # Collect evidence references — but threshold results are regulatory
    # screening evidence, NOT adaptation action evidence
    evidence_ids: list[str] = []
    rule_ids: list[str] = []
    caveats: list[str] = []

    # Scan asset verifications for regulatory screening evidence
    for v in asset_verifications:
        asset_id = v.get("asset_id", "")
        for rr in v.get("rule_results", []):
            rule_id = rr.get("rule_id", "")
            status = rr.get("status", "")
            if status in ("threshold_satisfied", "threshold_not_satisfied"):
                evidence_ids.append(f"{asset_id}:{rule_id}")
                if rule_id:
                    rule_ids.append(rule_id)

    # Determine evidence status for each semantic concept
    if dr.semantic_concept == "anticipated_financial_effects":
        return _map_financial_effects(
            dr=dr,
            financial_value=financial_value,
            evidence_ids=evidence_ids,
            rule_ids=rule_ids,
        )

    elif dr.semantic_concept == "climate_actions_and_resources":
        # Threshold results are regulatory screening evidence, NOT
        # adaptation action evidence.  A threshold_satisfied result
        # means the engineered value meets a numeric threshold; it
        # does NOT prove an adaptation measure is planned/implemented
        # with allocated resources.
        caveats = (
            "GeoRisk regulatory screening results are NOT adaptation "
            "action evidence.  ESRS E1-3/E1-5 requires evidence of "
            "specific adaptation measures with implementation plans, "
            "timelines, and resource allocation — not threshold compliance.",
        )
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            supporting_evidence_ids=(),
            supporting_rule_ids=(),
            caveats=caveats,
        )

    elif dr.semantic_concept in (
        "transition_plan_climate_mitigation",
        "climate_policies",
    ):
        # Transition plans and policies require undertaking-level data.
        # source_unverified is NOT evidence — only actual evidence_ids count.
        if evidence_ids:
            caveats = (
                "GeoRisk provides physical-risk screening evidence; "
                "transition plans and policies require undertaking-level "
                "information not available from property screening.",
            )
            return ESRSDisclosureMapping(
                instrument_id=dr.instrument_id,
                disclosure_requirement=dr.disclosure_requirement,
                semantic_concept=dr.semantic_concept,
                evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
                mapping_status=ESRSMappingStatus.UNMAPPED,
                supporting_evidence_ids=(),
                supporting_rule_ids=(),
                caveats=caveats,
            )
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
        )

    elif dr.semantic_concept == "climate_risk_identification":
        # GeoRisk provides physical-risk screening — but only actual
        # evidence (verified threshold results) counts.  source_unverified
        # is NOT evidence.
        if evidence_ids:
            caveats = (
                "GeoRisk provides property-level physical-risk screening; "
                "ESRS climate risk identification also requires transition "
                "risk assessment, scenario analysis, and double materiality "
                "determination at undertaking level.",
            )
            return ESRSDisclosureMapping(
                instrument_id=dr.instrument_id,
                disclosure_requirement=dr.disclosure_requirement,
                semantic_concept=dr.semantic_concept,
                evidence_status=ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS,
                mapping_status=ESRSMappingStatus.PARTIALLY_MAPPED,
                supporting_evidence_ids=tuple(evidence_ids),
                supporting_rule_ids=tuple(sorted(set(rule_ids))),
                caveats=caveats,
            )
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
        )

    elif dr.semantic_concept == "climate_resilience":
        # 2026-specific: climate resilience analysis
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "GeoRisk does not currently produce scenario-based "
                "climate resilience analysis.",
            ),
        )

    elif dr.semantic_concept == "ghg_emissions":
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "GeoRisk Engine does not produce GHG emission data. "
                "This disclosure requirement requires separate data sources.",
            ),
        )

    elif dr.semantic_concept in (
        "ghg_removals_and_carbon_credits",
        "internal_carbon_pricing",
    ):
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                f"GeoRisk Engine does not produce {dr.semantic_concept.replace('_', ' ')} data.",
            ),
        )

    elif dr.semantic_concept == "climate_targets_and_performance":
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "Climate targets and performance require undertaking-level "
                "commitment data not available from property screening.",
            ),
        )

    elif dr.semantic_concept == "energy_consumption_and_mix":
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "GeoRisk Engine does not produce energy consumption data.",
            ),
        )

    # Default fallback — should not normally be reached
    return ESRSDisclosureMapping(
        instrument_id=dr.instrument_id,
        disclosure_requirement=dr.disclosure_requirement,
        semantic_concept=dr.semantic_concept,
        evidence_status=ESRSEvidenceStatus.NOT_ASSESSED,
        mapping_status=ESRSMappingStatus.UNMAPPED,
    )


def _map_financial_effects(
    *,
    dr: DisclosureRequirement,
    financial_value: FinancialValue | None,
    evidence_ids: list[str],
    rule_ids: list[str],
) -> ESRSDisclosureMapping:
    """Map anticipated_financial_effects with strict provenance requirements.

    ESRS E1-9 requires:
    - assets_at_material_physical_risk (amount + percentage)
    - acute_risk_amount
    - chronic_risk_amount
    - adaptation_addressed_percentage
    - significant_asset_locations
    - financial_statement_reconciliation_reference

    Minimum gate for ANY mapping:
      value_basis == "carrying_value"
      AND financial_statement_reconciled == True
      AND reporting_date present

    Even with all three, GeoRisk can only provide partial support
    (PARTIALLY_MAPPED) because it lacks the full E1-9 disclosure
    structure (acute/chronic breakdown, adaptation percentage, etc.).
    """
    if financial_value is None:
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "Financial value not provided; ESRS anticipated financial "
                "effects require carrying values from financial statements.",
            ),
        )

    # Risk linkage BEFORE provenance: carrying value without verified
    # physical-risk evidence is insufficient for E1-9 mapping.
    if not evidence_ids:
        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE,
            mapping_status=ESRSMappingStatus.UNMAPPED,
            caveats=(
                "No verified physical-risk evidence is linked to the "
                "financial values.  Carrying value alone is not "
                "sufficient for ESRS anticipated financial effects — "
                "material physical-risk exposure must first be "
                "established for the asset population.",
            ),
        )

    # Risk evidence exists — now check financial provenance.
    has_carrying_value = financial_value.value_basis == "carrying_value"
    has_reconciliation = financial_value.financial_statement_reconciled
    has_reporting_date = bool(financial_value.reporting_date)

    if not (has_carrying_value and has_reconciliation and has_reporting_date):
        missing = []
        if not has_carrying_value:
            missing.append(f"value_basis='{financial_value.value_basis}' (need 'carrying_value')")
        if not has_reconciliation:
            missing.append("financial_statement_reconciled=False (need True)")
        if not has_reporting_date:
            missing.append("reporting_date missing")

        return ESRSDisclosureMapping(
            instrument_id=dr.instrument_id,
            disclosure_requirement=dr.disclosure_requirement,
            semantic_concept=dr.semantic_concept,
            evidence_status=ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS,
            mapping_status=ESRSMappingStatus.PARTIALLY_MAPPED,
            caveats=(
                f"Verified risk evidence exists but incomplete financial "
                f"provenance: {'; '.join(missing)}.  "
                "ESRS E1-9 requires carrying values from audited financial "
                "statements with reconciliation reference.",
            ),
        )

    # Both risk evidence AND full financial provenance.
    # GeoRisk still only provides partial support because E1-9 requires
    # acute/chronic breakdown, adaptation percentage, significant
    # locations, etc.
    return ESRSDisclosureMapping(
        instrument_id=dr.instrument_id,
        disclosure_requirement=dr.disclosure_requirement,
        semantic_concept=dr.semantic_concept,
        evidence_status=ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS,
        mapping_status=ESRSMappingStatus.PARTIALLY_MAPPED,
        supporting_evidence_ids=tuple(evidence_ids),
        supporting_rule_ids=tuple(sorted(set(rule_ids))),
        caveats=(
            "Financial value meets minimum provenance gate (carrying_value "
            "+ reconciled + reporting_date) AND verified physical-risk "
            "evidence exists.  However, E1-9 also requires acute/chronic "
            "breakdown, adaptation-addressed percentage, significant "
            "locations, and full financial statement reconciliation — "
            "not yet available from GeoRisk.",
        ),
    )
