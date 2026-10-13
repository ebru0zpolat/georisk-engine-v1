"""Evidence-pack schemas for the ``pack-tr`` sustainable-finance layer.

These pydantic models express the evidence contract (spec Part II §5–§9). They are
declarative: gate/scan logic lives in ``gates.py`` and ``claims.py``. Records expose small
``missing_*`` helpers so the gates can fail closed without re-deriving field lists.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.packs.tr.sustainable_finance import regulatory_source as rs
from app.packs.tr.sustainable_finance.physical_risk import HazardReference, RecalculationBridge
from app.packs.tr.sustainable_finance.routes import (
    EligibilityStatus,
    EngagementRole,
    ExternalReviewType,
    PackStatus,
    RegulatoryRoute,
)

# =========================================================================================
# Provenance (spec §9)
# =========================================================================================


class ProvenanceRecord(BaseModel):
    """Traceability record for one calculation included in the pack (spec §9).

    Synthetic / fallback / unlicensed inputs must be explicitly identified. Even when
    labelled they must not feed an external KPI baseline, SPT calculation, impact conclusion
    or coupon-trigger computation (spec §9, §14).
    """

    analysis_run_id: str = Field(..., min_length=1)
    asset_id: str | None = None
    portfolio_id: str | None = None

    source_dataset_id: str | None = None
    provider: str | None = None
    licence: str | None = None
    retrieval_date: date | None = None
    source_checksum: str | None = None

    climate_model: str | None = None
    scenario: str | None = None
    baseline: str | None = None
    horizon: str | None = None
    hazard_metric: str | None = None
    units: str | None = None

    methodology_versions: dict[str, str] = Field(default_factory=dict)
    input_hash: str | None = None
    output_hash: str | None = None

    # Honesty flags (must match the labelling in STUBS.md).
    is_synthetic: bool = False
    is_fallback: bool = False
    #: Whether the synthetic/fallback nature is explicitly surfaced in pack output.
    labelled: bool = False

    #: A forward-looking (scenario/horizon) result requires a real versioned scenario source.
    forward_looking: bool = False
    scenario_source_real: bool = False

    uncertainty: str | None = None
    warnings: list[str] = Field(default_factory=list)

    def is_licensed(self) -> bool:
        return bool(self.licence and self.licence.strip())

    def is_labelled(self) -> bool:
        """A synthetic/fallback record must be explicitly labelled; others are always OK."""
        if self.is_synthetic or self.is_fallback:
            return self.labelled
        return True

    def has_hashes(self) -> bool:
        return bool(self.input_hash and self.output_hash)

    def scenario_source_ok(self) -> bool:
        """Forward-looking results need a real, licensed, versioned scenario source."""
        if not self.forward_looking:
            return True
        return self.scenario_source_real and self.is_licensed()

    def usable_in_external_number(self) -> bool:
        """Whether this record may back an external KPI/SPT/impact/trigger number (spec §9)."""
        return (
            not self.is_synthetic
            and not self.is_fallback
            and self.is_licensed()
            and self.has_hashes()
            and self.scenario_source_ok()
        )

    def missing_traceability_fields(self) -> list[str]:
        """Mandatory source/methodology metadata for a traceable record (spec §9).

        A licence and input/output hashes are not enough: without the source identity,
        provider, retrieval date, source checksum and per-run methodology versions the
        calculation cannot be reproduced or traced, even though a manifest run id resolves.
        """
        missing: list[str] = []
        required_text = {
            "source_dataset_id": self.source_dataset_id,
            "provider": self.provider,
            "source_checksum": self.source_checksum,
        }
        for name, value in required_text.items():
            if not (value and value.strip()):
                missing.append(name)
        if self.retrieval_date is None:
            missing.append("retrieval_date")
        if not self.methodology_versions:
            missing.append("methodology_versions")
        return missing

    def gate_problems(self) -> list[str]:
        """Fail-closed release problems for this record (spec §13)."""
        problems: list[str] = []
        if (self.is_synthetic or self.is_fallback) and not self.labelled:
            problems.append(f"{self.analysis_run_id}: unlabelled synthetic/fallback input")
        if not self.is_licensed():
            problems.append(f"{self.analysis_run_id}: missing dataset licence")
        if not self.has_hashes():
            problems.append(f"{self.analysis_run_id}: missing source/calculation hashes")
        for field_name in self.missing_traceability_fields():
            problems.append(f"{self.analysis_run_id}: missing provenance field {field_name}")
        if not self.scenario_source_ok():
            problems.append(
                f"{self.analysis_run_id}: forward-looking result lacks a real versioned scenario source"
            )
        return problems


# =========================================================================================
# Responsibility map & external-review roles (spec §3.3, §5)
# =========================================================================================


class RoleAssignment(BaseModel):
    """One party and its role in the engagement (spec §3.3)."""

    role: EngagementRole
    party_name: str | None = None  # ``None`` == not_appointed
    responsibility: str = ""

    @property
    def not_appointed(self) -> bool:
        return not (self.party_name and self.party_name.strip())


class ExternalReviewRoles(BaseModel):
    """Named adviser, second-party opinion provider and verifier (spec §5)."""

    framework_adviser: str | None = None
    second_party_opinion_provider: str | None = None
    verifier: str | None = None


class ExternalReviewRef(BaseModel):
    """Pointer to an external-review document — GeoRisk records, never endorses (spec §12)."""

    review_type: ExternalReviewType
    provider_name: str
    document_ref: str
    received_date: date | None = None
    assurance_level: str | None = None  # limited | reasonable (verification only)


# =========================================================================================
# Pack manifest (spec §5)
# =========================================================================================


class PackManifest(BaseModel):
    """Machine- and human-readable manifest at the head of every pack (spec §5)."""

    pack_id: str = Field(..., min_length=1)
    pack_version: str = rs.EVIDENCE_PACK_FORMAT_VERSION
    status: PackStatus = PackStatus.draft
    regulatory_route: RegulatoryRoute

    regulatory_source_id: str = rs.DECISION_ID
    regulatory_decision_date: str = rs.DECISION_DATE
    regulatory_decision_number: str = rs.DECISION_NUMBER
    regulatory_cutoff_date: date | None = None

    issuer_legal_name: str | None = None
    responsibility_map: list[RoleAssignment] = Field(default_factory=list)
    framework_document_id: str | None = None
    authorised_body_decision_ref: str | None = None
    issuance_ceiling_ref: str | None = None

    analysis_run_ids: list[str] = Field(default_factory=list)
    methodology_versions: dict[str, str] = Field(default_factory=dict)
    country_pack: str = f"{rs.PACK_ID}@{rs.PACK_VERSION}"

    external_review_roles: ExternalReviewRoles = Field(default_factory=ExternalReviewRoles)

    generated_at: datetime | None = None
    generated_by: str | None = None
    manifest_sha256: str | None = None  # Filled after sealing.

    def missing_mandatory_fields(self) -> list[str]:
        """Mandatory provenance/responsibility fields for reviewer_ready (spec §5, §13)."""
        missing: list[str] = []
        if self.regulatory_cutoff_date is None:
            missing.append("regulatory_cutoff_date")
        if not (self.issuer_legal_name and self.issuer_legal_name.strip()):
            missing.append("issuer_legal_name")
        if not self.responsibility_map:
            missing.append("responsibility_map")
        if not self.framework_document_id:
            missing.append("framework_document_id")
        if not self.analysis_run_ids:
            missing.append("analysis_run_ids")
        if not self.methodology_versions:
            missing.append("methodology_versions")
        return missing


# =========================================================================================
# Use-of-proceeds route (spec §6)
# =========================================================================================


class ProjectEligibilityRecord(BaseModel):
    """Project / project-pool eligibility evidence (spec §6.2).

    ``eligibility_status`` uses only the permitted GeoRisk values — legal eligibility is
    never asserted by GeoRisk.
    """

    project_id: str = Field(..., min_length=1)
    owner: str | None = None
    location: str | None = None
    implementation_period: str | None = None

    financing_type: str | None = None  # new_financing | refinancing | mixed
    lookback_months: int | None = Field(default=None, ge=0)
    lookback_justification: str | None = None

    nace_code: str | None = None
    green_category: int | None = None  # key into GREEN_PROJECT_CATEGORIES
    social_category: str | None = None
    objective: str | None = None
    target_population: str | None = None  # social projects only

    taxonomy_or_standard: str | None = None
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    material_adverse_risks: list[str] = Field(default_factory=list)
    risk_mitigation_owner: str | None = None

    benefit_measures: list[str] = Field(default_factory=list)
    evidence_run_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    eligibility_status: EligibilityStatus = EligibilityStatus.technical_evidence_incomplete
    issuer_approved: bool = False
    second_party_opinion_status: str | None = None

    @field_validator("lookback_months")
    @classmethod
    def _flag_long_lookback(cls, value: int | None) -> int | None:
        # The guideline recommends a justification when the look-back exceeds 36 months;
        # we do not reject, but ``lookback_needs_justification`` surfaces it to reviewers.
        return value

    @property
    def lookback_needs_justification(self) -> bool:
        return (
            self.lookback_months is not None
            and self.lookback_months > rs.RECOMMENDED_LOOKBACK_MONTHS
            and not (self.lookback_justification and self.lookback_justification.strip())
        )


class PhysicalAdaptationEvidence(BaseModel):
    """Before/after physical-risk evidence for an adaptation project (spec §6.3)."""

    project_id: str = Field(..., min_length=1)
    material_hazards: list[str] = Field(default_factory=list)
    hazard_selection_rationale: str | None = None
    asset_or_portfolio_boundary: str | None = None

    baseline_exposure: str | None = None
    baseline_vulnerability: str | None = None
    baseline_date: date | None = None
    climate_baseline_period: str | None = None

    hazard_reference: HazardReference | None = None
    adaptation_measure: str | None = None
    implementation_status: str | None = None

    pre_implementation_method: str | None = None
    post_implementation_method: str | None = None
    expected_vulnerability_change: str | None = None
    residual_risk: str | None = None

    uncertainty_range: str | None = None
    material_data_gaps: list[str] = Field(default_factory=list)
    monitoring_frequency: str | None = None
    post_implementation_review_date: date | None = None

    #: True only when a hazard reduction is (incorrectly) attributed to the issuer.
    attributes_hazard_reduction_to_issuer: bool = False


class ImpactMetric(BaseModel):
    """Candidate qualitative/quantitative impact measure (spec §6.8)."""

    metric_id: str = Field(..., min_length=1)
    project_id: str | None = None
    description: str
    qualitative: bool = False
    value: float | None = None
    unit: str | None = None
    methodology_and_assumptions: str | None = None
    evidence_run_id: str | None = None
    is_modelled: bool = True
    absence_explanation: str | None = None  # required when a quantitative measure is absent


class ProceedsDataInterface(BaseModel):
    """Issuer-supplied proceeds / cash-management data — NO GeoRisk assurance (spec §10)."""

    issuer_supplied: bool = True
    proceeds_raised: float | None = None
    tracking_method: str | None = None
    unallocated_management: str | None = None
    first_tranche_date: date | None = None
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    note: str = "Issuer-supplied; GeoRisk provides no assurance over these figures."


# =========================================================================================
# Sustainability-linked route (spec §7)
# =========================================================================================


class KPIHistoryPoint(BaseModel):
    year: int
    value: float
    externally_verified: bool = False


class KPIRecord(BaseModel):
    """Candidate KPI record + evidence for the admission gates (spec §7.2, §7.3)."""

    kpi_id: str = Field(..., min_length=1)
    name: str

    strategy_materiality_link: str | None = None
    material_sector_issue: str | None = None
    controlled_management_lever: str | None = None

    boundary: str | None = None
    inclusions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    coverage_pct: float | None = Field(default=None, ge=0.0, le=100.0)

    unit: str | None = None
    numerator: str | None = None
    denominator: str | None = None

    baseline_value: float | None = None
    baseline_reference_date: date | None = None
    baseline_evidence_status: str | None = None

    history: list[KPIHistoryPoint] = Field(default_factory=list)
    external_benchmark: str | None = None

    methodology_versions: dict[str, str] = Field(default_factory=dict)
    dataset_versions: dict[str, str] = Field(default_factory=dict)
    data_owner: str | None = None
    source_system_owner: str | None = None
    measurement_frequency: str | None = None
    reporting_frequency: str | None = None

    verification_evidence: str | None = None
    responsible_external_reviewer: str | None = None
    recalculation_policy: str | None = None
    uncertainty: str | None = None
    limitations: list[str] = Field(default_factory=list)
    prohibited_interpretations: list[str] = Field(default_factory=list)

    #: Optional link to the physical-risk suitability matrix (physical_risk.py).
    physical_risk_candidate_id: str | None = None
    #: True when the KPI is a pure external-hazard metric (issuer does not control it).
    is_pure_external_hazard: bool = False
    #: True when the KPI is (or is intended as) a financial/structural instrument trigger.
    proposed_as_trigger: bool = False

    def externally_verified_history_years(self) -> int:
        return sum(1 for h in self.history if h.externally_verified)

    def has_measurement_definition(self) -> bool:
        return bool(
            (self.unit and self.unit.strip())
            and (self.numerator and self.numerator.strip())
            and (self.boundary and self.boundary.strip())
        )


class SPTRecord(BaseModel):
    """Sustainability performance target record (spec §7.4)."""

    spt_id: str = Field(..., min_length=1)
    linked_kpi_id: str = Field(..., min_length=1)

    target_value: float | None = None
    target_date: date | None = None
    observation_frequency: str | None = None

    materiality_explanation: str | None = None
    beyond_bau_explanation: str | None = None
    issuer_history_used: bool = False
    peer_or_sector_comparison: str | None = None
    science_based_reference: str | None = None

    starting_reference_value: float | None = None
    reference_verification_status: str | None = None

    action_plan: str | None = None
    quantified_contributions: str | None = None
    factors_outside_control: list[str] = Field(default_factory=list)

    trigger_event: str | None = None
    #: Financial/structural consequence — supplied by the issuer and its advisers, not GeoRisk.
    financial_or_structural_consequence: str | None = None
    fallback_if_not_calculable: str | None = None
    exceptional_event_rules: str | None = None
    spo_refresh_trigger: str | None = None
    performance_report_calendar: str | None = None

    def missing_required_fields(self) -> list[str]:
        """SPT fields whose absence fails the release gate (spec §13)."""
        missing: list[str] = []
        if self.starting_reference_value is None:
            missing.append("starting_reference_value")
        if self.target_date is None:
            missing.append("target_date")
        if not (self.trigger_event and self.trigger_event.strip()):
            missing.append("trigger_event")
        if not (self.fallback_if_not_calculable and self.fallback_if_not_calculable.strip()):
            missing.append("fallback_if_not_calculable")
        return missing


class InstrumentEffect(BaseModel):
    """Issuer/adviser-supplied instrument financial/structural effect (spec §7, §10)."""

    linked_spt_id: str
    issuer_supplied: bool = True
    description: str
    change_type: str | None = None  # e.g. coupon_step_up | structural_change
    note: str = "Financial/structural terms are issuer/adviser supplied; not a GeoRisk recommendation."


# =========================================================================================
# Claims register (spec §11)
# =========================================================================================


class ClaimEntry(BaseModel):
    """One controlled claim: the permitted wording actually used and its context."""

    topic: str
    permitted_wording: str
    location: str | None = None


class ClaimsRegister(BaseModel):
    """Register of permitted claims accompanying the pack (spec §11)."""

    entries: list[ClaimEntry] = Field(default_factory=list)
    limitations_present: bool = False


# =========================================================================================
# Route-scoped evidence bundle input
# =========================================================================================


class EvidencePackInput(BaseModel):
    """The complete sealed input from which a deterministic pack is built (spec §10)."""

    manifest: PackManifest
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    claims: ClaimsRegister = Field(default_factory=ClaimsRegister)
    external_reviews: list[ExternalReviewRef] = Field(default_factory=list)

    # Use-of-proceeds route
    projects: list[ProjectEligibilityRecord] = Field(default_factory=list)
    adaptation_evidence: list[PhysicalAdaptationEvidence] = Field(default_factory=list)
    impact_metrics: list[ImpactMetric] = Field(default_factory=list)
    proceeds_interface: ProceedsDataInterface | None = None

    # Sustainability-linked route
    kpis: list[KPIRecord] = Field(default_factory=list)
    spts: list[SPTRecord] = Field(default_factory=list)
    instrument_effects: list[InstrumentEffect] = Field(default_factory=list)

    # Shared
    recalculation_bridges: list[RecalculationBridge] = Field(default_factory=list)
    uncertainty_and_limitations: str = ""


__all__ = [
    "ClaimEntry",
    "ClaimsRegister",
    "EvidencePackInput",
    "ExternalReviewRef",
    "ExternalReviewRoles",
    "ImpactMetric",
    "InstrumentEffect",
    "KPIHistoryPoint",
    "KPIRecord",
    "PackManifest",
    "PhysicalAdaptationEvidence",
    "ProceedsDataInterface",
    "ProjectEligibilityRecord",
    "ProvenanceRecord",
    "RoleAssignment",
    "SPTRecord",
]
