"""Strict contracts for data-centre physical-climate assessments.

The contracts intentionally accept evidence supplied by approved Country Packs or
due-diligence providers.  They do not embed a synthetic water-stress fallback or a
global data-centre damage curve.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.dc_vulnerability import DataCentreVulnerabilityProfile


SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40}$"


class CoolingType(StrEnum):
    AIR = "air"
    EVAPORATIVE = "evaporative"
    DIRECT_TO_CHIP_LIQUID = "direct_to_chip_liquid"
    IMMERSION = "immersion"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class WaterDependency(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class PowerRedundancy(StrEnum):
    NONE = "none"
    N = "n"
    N_PLUS_1 = "n_plus_1"
    N_PLUS_2 = "n_plus_2"
    TWO_N = "two_n"
    TWO_N_PLUS_1 = "two_n_plus_1"
    UNKNOWN = "unknown"


class ScenarioHorizon(StrEnum):
    CURRENT = "current"
    YEAR_2030 = "2030"
    YEAR_2050 = "2050"
    YEAR_2100 = "2100"


class WaterStressClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    NOT_CLASSIFIED = "not_classified"


class EvidenceManifest(BaseModel):
    """Immutable provenance for one externally supplied evidence artefact."""

    source: str = Field(min_length=3)
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    licence: str = Field(min_length=3)
    licensed_for_commercial_use: bool
    retrieved_on: date
    sha256: str = Field(pattern=SHA256_PATTERN)
    synthetic: bool = Field(
        default=False,
        description="True for test/demo material. Synthetic evidence never opens production gates.",
    )


class DataCentreVulnerability(BaseModel):
    """Screening/pathway input. Completeness is decided by the Profile evaluator."""

    asset_id: str = Field(min_length=1)
    cooling_type: CoolingType
    design_max_dry_bulb_c: float | None = Field(
        default=None,
        ge=-30,
        le=80,
        description=(
            "Declared dry-bulb design limit. For liquid/immersion cooling this is a "
            "provisional heat-rejection proxy: the loop architecture (dry vs "
            "adiabatic) is not yet represented, so any declared dry- or wet-bulb "
            "limit is compared. Pathway decidability is not engineering validation."
        ),
    )
    design_max_wet_bulb_c: float | None = Field(
        default=None,
        ge=-30,
        le=50,
        description=(
            "Declared wet-bulb design limit. For liquid/immersion cooling this is a "
            "provisional heat-rejection proxy until the canonical profile carries "
            "an explicit heat-rejection-loop field."
        ),
    )
    water_dependency: WaterDependency
    power_redundancy: PowerRedundancy
    finished_floor_elevation_m_agl: float | None = Field(default=None, ge=-20, le=200)
    backup_power_hours: float | None = Field(default=None, ge=0, le=720)
    critical_load_mw: float | None = Field(default=None, gt=0, le=10_000)
    flood_protection_return_period_years: int | None = Field(default=None, ge=1, le=100_000)
    independent_utility_feeds: int | None = Field(
        default=None,
        ge=0,
        le=8,
        description="Declared independent utility feeds. Unknown/missing blocks completeness.",
    )
    water_usage_effectiveness: float | None = Field(
        default=None,
        ge=0,
        le=50,
        description="Site WUE. Required when water_dependency is medium or high.",
    )
    design_pue: float | None = Field(default=None, ge=1.0, le=4.0)
    flood_barrier_height_m: float | None = Field(default=None, ge=0, le=50)
    it_load_density_kw_per_rack: float | None = Field(default=None, gt=0, le=200)


class HeatHazardEvidence(BaseModel):
    horizon: ScenarioHorizon
    projected_max_dry_bulb_c: float | None = Field(default=None, ge=-30, le=80)
    projected_max_wet_bulb_c: float | None = Field(default=None, ge=-30, le=50)
    wsdi_days: float | None = Field(default=None, ge=0, le=366)
    manifest: EvidenceManifest

    @model_validator(mode="after")
    def at_least_one_heat_measure(self) -> Self:
        if (
            self.projected_max_dry_bulb_c is None
            and self.projected_max_wet_bulb_c is None
            and self.wsdi_days is None
        ):
            raise ValueError("At least one heat measure is required")
        return self


class FloodHazardEvidence(BaseModel):
    horizon: ScenarioHorizon
    maximum_site_water_depth_m: float = Field(ge=0, le=100)
    flood_type: Literal["pluvial", "fluvial", "coastal", "compound"]
    return_period_years: int | None = Field(default=None, ge=1, le=100_000)
    manifest: EvidenceManifest


class WaterStressHazardEvidence(BaseModel):
    """Provider-classified water stress; thresholds remain in the source/pack."""

    horizon: ScenarioHorizon
    classification: WaterStressClass
    provider_metric: str = Field(min_length=1)
    provider_threshold_reference: str = Field(
        min_length=1,
        description="Versioned reference defining the provider's class thresholds.",
    )
    drought_indicator: float | None = None
    manifest: EvidenceManifest


class PowerContinuityEvidence(BaseModel):
    """Optional site/grid evidence; never inferred from climate hazards."""

    horizon: ScenarioHorizon
    maximum_climate_related_outage_hours: float = Field(ge=0, le=8_760)
    manifest: EvidenceManifest


class BacktestEvidence(BaseModel):
    """Evidence that a Gate-1 comparison already ran — not a second engine.

    ``harness_module`` / ``harness_entrypoint`` must name
    ``app.validation.gate1.run_comparison``. A data-centre backtest that
    invents its own comparison loop is rejected.
    """

    event_id: str = Field(min_length=1)
    harness_module: Literal["app.validation.gate1"] = "app.validation.gate1"
    harness_entrypoint: Literal["run_comparison"] = "run_comparison"
    pre_registration_commit_sha: str = Field(pattern=GIT_SHA_PATTERN)
    observed_loss_manifest: EvidenceManifest
    result_report_sha256: str = Field(pattern=SHA256_PATTERN)
    config_hash: str | None = Field(
        default=None,
        min_length=16,
        description="Gate-1 ComparisonReport.config_hash when a comparison has run.",
    )
    information_cutoff: date
    sample_size: int = Field(gt=0)
    comparison_status: Literal["passed", "failed"]


class ExternalReviewEvidence(BaseModel):
    reviewer_reference: str = Field(min_length=1)
    discipline: Literal[
        "data_centre_engineering",
        "mechanical_engineering",
        "electrical_engineering",
        "climate_risk",
    ]
    independent: bool
    conflicts_declaration_sha256: str = Field(pattern=SHA256_PATTERN)
    review_report_sha256: str = Field(pattern=SHA256_PATTERN)
    methodology_version: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    signed_on: date
    valid_until: date

    @model_validator(mode="after")
    def validity_window(self) -> Self:
        if self.valid_until < self.signed_on:
            raise ValueError("valid_until must not precede signed_on")
        return self


class ValidationEvidenceBundle(BaseModel):
    backtest: BacktestEvidence | None = None
    external_review: ExternalReviewEvidence | None = None


def _iter_profile_cutoff_fields(
    profile: DataCentreVulnerabilityProfile,
) -> list[tuple[str, date | int]]:
    """Every dated profile field that must be ``<= valuation_date``.

    A hand-maintained allow-list is how a later profile field bypasses the
    assessment cutoff. Walk the model instead.

    Traversal covers scalar ``date``/``datetime`` fields, ``commissioning_year``,
    and nested ``BaseModel`` fields. It does *not* descend into lists, tuples or
    dicts. No dated collection exists on the profile today — its only collections
    are ``water_source_mix``, ``supply_restrictions`` and
    ``critical_third_party_utilities``, none of them dated — so nothing currently
    bypasses the cutoff. Adding a collection of dated records requires extending
    this walker to sequences and mappings first.
    """

    dated: list[tuple[str, date | int]] = []

    def walk(obj: object, prefix: str) -> None:
        if not isinstance(obj, BaseModel):
            return
        for name in obj.model_fields:
            value = getattr(obj, name)
            path = f"{prefix}.{name}" if prefix else name
            if type(value) is date:
                dated.append((path, value))
            elif isinstance(value, datetime):
                dated.append((path, value.date()))
            elif name == "commissioning_year" and isinstance(value, int):
                dated.append((path, value))
            elif isinstance(value, BaseModel):
                walk(value, path)

    walk(profile, "vulnerability_profile")
    return dated


class DataCentreAssessmentRequest(BaseModel):
    methodology_version: Literal["data-centre-physical-risk-v0.1"] = (
        "data-centre-physical-risk-v0.1"
    )
    country_pack_id: str = Field(
        min_length=1,
        description="Versioned pack identifier supplying local evidence and thresholds.",
    )
    valuation_date: date = Field(
        description="Information cutoff; later evidence is rejected to prevent lookahead.",
    )
    vulnerability: DataCentreVulnerability
    vulnerability_profile: DataCentreVulnerabilityProfile | None = Field(
        default=None,
        description=(
            "Canonical engineering vulnerability contract. When present it is the "
            "sole completeness and pathway authority; overlapping flat fields must "
            "match or the request is rejected. When omitted, a lossy bridge is "
            "evaluated for completeness and the flat object remains the pathway input."
        ),
    )
    heat: HeatHazardEvidence
    flood: FloodHazardEvidence
    water_stress: WaterStressHazardEvidence
    power_continuity: PowerContinuityEvidence | None = None
    validation: ValidationEvidenceBundle = Field(default_factory=ValidationEvidenceBundle)

    @model_validator(mode="after")
    def horizons_match(self) -> Self:
        horizons = {self.heat.horizon, self.flood.horizon, self.water_stress.horizon}
        if self.power_continuity is not None:
            horizons.add(self.power_continuity.horizon)
        if len(horizons) != 1:
            raise ValueError("All evidence must use the same scenario horizon")
        return self

    @model_validator(mode="after")
    def no_lookahead_evidence(self) -> Self:
        """Reject any dated evidence after the request ``valuation_date``.

        The canonical profile is in scope: every dated profile field, including
        ``valuation_cutoff``, evidence dates, inspection/review dates, and
        ``cooling.commissioning_year``, must be ``<= valuation_date``. The
        walker replaces a hand-maintained allow-list; see
        ``_iter_profile_cutoff_fields`` for the one traversal limit it carries.
        An older profile is not lookahead; it may still open decision-support
        readiness and is flagged stale. Production eligibility requires cutoff
        equality. No processing date substitutes for this cutoff.
        """
        manifests = [self.heat.manifest, self.flood.manifest, self.water_stress.manifest]
        if self.power_continuity is not None:
            manifests.append(self.power_continuity.manifest)
        if any(manifest.retrieved_on > self.valuation_date for manifest in manifests):
            raise ValueError("Hazard evidence violates the valuation_date cutoff")
        backtest = self.validation.backtest
        if backtest is not None:
            if backtest.information_cutoff > self.valuation_date:
                raise ValueError(
                    "Backtest information_cutoff violates the valuation_date cutoff"
                )
            if backtest.observed_loss_manifest.retrieved_on > self.valuation_date:
                raise ValueError(
                    "Observed-loss evidence violates the valuation_date cutoff"
                )
        review = self.validation.external_review
        if review is not None and review.signed_on > self.valuation_date:
            raise ValueError("External review signed_on violates the valuation_date cutoff")
        profile = self.vulnerability_profile
        if profile is None:
            return self
        for label, value in _iter_profile_cutoff_fields(profile):
            if isinstance(value, int):
                if value > self.valuation_date.year:
                    raise ValueError(f"{label} violates the valuation_date cutoff")
            elif value > self.valuation_date:
                raise ValueError(f"{label} violates the valuation_date cutoff")
        return self

    @model_validator(mode="after")
    def profile_identity_matches_asset(self) -> Self:
        profile = self.vulnerability_profile
        if profile is not None and profile.facility_id != self.vulnerability.asset_id:
            raise ValueError(
                "vulnerability_profile.facility_id must equal vulnerability.asset_id"
            )
        return self

    @model_validator(mode="after")
    def profile_does_not_contradict_flat(self) -> Self:
        profile = self.vulnerability_profile
        if profile is None:
            return self
        from app.data_centres.vulnerability_bridge import overlapping_field_conflicts

        conflicts = overlapping_field_conflicts(self.vulnerability, profile)
        if conflicts:
            raise ValueError(
                "vulnerability_profile contradicts vulnerability: " + "; ".join(conflicts)
            )
        return self


class EvidenceGateResult(BaseModel):
    gate_id: str
    status: Literal["open", "blocked"]
    reasons: list[str] = Field(default_factory=list)


class IndicatorResult(BaseModel):
    indicator_id: Literal["heat", "flood", "water_stress", "power_continuity"]
    status: Literal["supported", "evidence_blocked"]
    horizon: ScenarioHorizon
    values: dict[str, float | int | str | None]
    evidence_sha256: str


class LossPathwayResult(BaseModel):
    pathway_id: Literal[
        "cooling_derating",
        "power_curtailment",
        "downtime",
        "business_interruption",
        "adaptation_capex",
    ]
    trigger_status: Literal["triggered", "not_triggered", "indeterminate"]
    rationale: list[str]
    monetary_quantification: Literal["blocked_pending_validation"] = (
        "blocked_pending_validation"
    )


class MonetaryOutputs(BaseModel):
    """Deliberately null until event evidence and model validation exist."""

    expected_annual_loss: None = None
    downtime_hours: None = None
    business_interruption_loss: None = None
    adaptation_capex: None = None
    currency: None = None


class EUDataCentreReportingBoundary(BaseModel):
    regulation: Literal["Commission Delegated Regulation (EU) 2024/1364"] = (
        "Commission Delegated Regulation (EU) 2024/1364"
    )
    support_level: Literal["supporting_evidence_only"] = "supporting_evidence_only"
    operational_kpis_outside_this_assessment: list[str]
    supported_uses: list[str]
    prohibited_claims: list[str]


class DataCentreAssessmentResponse(BaseModel):
    assessment_id: str = Field(pattern=r"^dc_[0-9a-f]{64}$")
    asset_id: str
    methodology_version: str
    country_pack_id: str
    valuation_date: date
    vulnerability_profile_cutoff: date | None = None
    vulnerability_evidence_stale: bool = False
    horizon: ScenarioHorizon
    readiness: Literal["blocked", "decision_support_only"]
    gates: list[EvidenceGateResult]
    indicators: list[IndicatorResult]
    loss_pathways: list[LossPathwayResult]
    evidence_manifest_sha256s: dict[str, str]
    monetary_outputs: MonetaryOutputs = Field(default_factory=MonetaryOutputs)
    production_release: Literal["none"] = "none"
    downtime_model_released: Literal[False] = False
    monetary_model_released: Literal[False] = False
    gate1_harness: Literal["app.validation.gate1.run_comparison"] = (
        "app.validation.gate1.run_comparison"
    )
    reporting_boundary: EUDataCentreReportingBoundary
    disclaimer: Literal[
        "Decision-support evidence only; not an engineering certification, loss estimate, or regulatory compliance opinion."
    ] = "Decision-support evidence only; not an engineering certification, loss estimate, or regulatory compliance opinion."
