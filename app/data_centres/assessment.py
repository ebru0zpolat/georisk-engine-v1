"""Fail-closed data-centre physical-climate assessment."""

from __future__ import annotations

from datetime import date
import hashlib
import json

from app.data_centres.contracts import (
    CoolingType,
    DataCentreAssessmentRequest,
    DataCentreAssessmentResponse,
    EUDataCentreReportingBoundary,
    EvidenceGateResult,
    EvidenceManifest,
    IndicatorResult,
    LossPathwayResult,
    MonetaryOutputs,
    WaterDependency,
    WaterStressClass,
)
from app.data_centres.gate1 import GATE1_HARNESS, harness_mismatch_reasons
from app.data_centres.vulnerability_bridge import (
    ResolvedVulnerabilityInputs,
    completeness_gate_from_readiness,
    production_eligibility_gate_from_readiness,
    resolve_assessment_profile,
    resolved_vulnerability_inputs,
)
from app.scoring.dc_vulnerability_rules import evaluate_dc_vulnerability_readiness


def reporting_boundary() -> EUDataCentreReportingBoundary:
    return EUDataCentreReportingBoundary(
        operational_kpis_outside_this_assessment=[
            "energy consumption",
            "power utilisation",
            "temperature set points",
            "waste heat utilisation",
            "water consumption and water usage effectiveness",
        ],
        supported_uses=[
            "physical-climate site screening",
            "vulnerability evidence for financing and insurance due diligence",
            "scenario comparison and evidence-gap identification",
        ],
        prohibited_claims=[
            "compliance with Regulation (EU) 2024/1364",
            "engineering certification or availability guarantee",
            "validated EAL, downtime, business-interruption loss, or adaptation capex",
            "sovereign-AI or data-sovereignty compliance",
        ],
    )


def _manifest_reasons(label: str, manifest: EvidenceManifest) -> list[str]:
    reasons: list[str] = []
    if manifest.synthetic:
        reasons.append(f"{label}: synthetic evidence cannot open a production gate")
    if not manifest.licensed_for_commercial_use:
        reasons.append(f"{label}: commercial-use licence not confirmed")
    return reasons


def _blocked_evidence_reasons(
    *labelled: tuple[str, EvidenceManifest | None],
) -> list[str]:
    return [
        reason
        for label, manifest in labelled
        if manifest is not None
        for reason in _manifest_reasons(label, manifest)
    ]


_LIQUID_COOLING_TYPES = frozenset(
    {CoolingType.DIRECT_TO_CHIP_LIQUID, CoolingType.IMMERSION}
)
_DRY_BULB_REQUIRED_TYPES = frozenset({CoolingType.AIR, CoolingType.HYBRID})
_WET_BULB_REQUIRED_TYPES = frozenset({CoolingType.EVAPORATIVE, CoolingType.HYBRID})
_POTENTIALLY_WATER_DEPENDENT = frozenset(
    {WaterDependency.MEDIUM, WaterDependency.HIGH, WaterDependency.UNKNOWN}
)


def _cooling_required_evidence(
    body: DataCentreAssessmentRequest,
    vulnerability: ResolvedVulnerabilityInputs,
) -> list[tuple[str, EvidenceManifest]]:
    evidence: list[tuple[str, EvidenceManifest]] = []
    if vulnerability.cooling_type in {
        CoolingType.AIR,
        CoolingType.HYBRID,
        CoolingType.EVAPORATIVE,
        CoolingType.DIRECT_TO_CHIP_LIQUID,
        CoolingType.IMMERSION,
        CoolingType.UNKNOWN,
    }:
        evidence.append(("heat", body.heat.manifest))
    # Unknown water dependency is fail-closed: the site may rely on water
    # but we cannot rule it out, so water-stress evidence is still required.
    # Read the resolved profile, not the flat request field.
    if vulnerability.water_dependency in _POTENTIALLY_WATER_DEPENDENT:
        evidence.append(("water_stress", body.water_stress.manifest))
    return evidence


def _evidence_gate(body: DataCentreAssessmentRequest) -> EvidenceGateResult:
    manifests = [
        ("heat", body.heat.manifest),
        ("flood", body.flood.manifest),
        ("water_stress", body.water_stress.manifest),
    ]
    if body.power_continuity is not None:
        manifests.append(("power_continuity", body.power_continuity.manifest))
    reasons = [reason for label, manifest in manifests for reason in _manifest_reasons(label, manifest)]
    return EvidenceGateResult(
        gate_id="licensed_non_synthetic_hazard_evidence",
        status="blocked" if reasons else "open",
        reasons=reasons,
    )


def _validation_gate(body: DataCentreAssessmentRequest, *, as_of: date) -> EvidenceGateResult:
    reasons: list[str] = []
    backtest = body.validation.backtest
    if backtest is None:
        reasons.append("licensed observed-loss backtest evidence is missing")
    else:
        reasons.extend(_manifest_reasons("observed_loss", backtest.observed_loss_manifest))
        reasons.extend(harness_mismatch_reasons(backtest))
        if backtest.comparison_status != "passed":
            reasons.append("pre-registered model-versus-baseline comparison did not pass")
        if not backtest.config_hash:
            reasons.append("Gate-1 ComparisonReport.config_hash is missing")

    review = body.validation.external_review
    if review is None:
        reasons.append("independent engineering review evidence is missing")
    else:
        if not review.independent:
            reasons.append("reviewer independence is not confirmed")
        if review.decision != "approved":
            reasons.append("external reviewer did not approve the methodology")
        if review.methodology_version != body.methodology_version:
            reasons.append("external review methodology version does not match the request")
        if review.signed_on > as_of:
            reasons.append("external review signed_on is after the assessment date")
        if review.valid_until < body.valuation_date:
            reasons.append("external review was not valid at valuation_date")
        if review.valid_until < as_of:
            reasons.append("external review evidence has expired")

    # A future validated monetary calculator must be separately versioned and approved.
    reasons.append("no validated data-centre monetary loss calculator is configured")
    return EvidenceGateResult(
        gate_id="monetary_loss_validation",
        status="blocked",
        reasons=reasons,
    )


def _vulnerability_gates(
    body: DataCentreAssessmentRequest,
) -> tuple[EvidenceGateResult, EvidenceGateResult]:
    """Completeness and production-eligibility from the canonical evaluator.

    The independent nine-check screening gate is retired. DC-053 does not
    block decision-support completeness.
    """
    profile = resolve_assessment_profile(body)
    readiness = evaluate_dc_vulnerability_readiness(profile)
    completeness = completeness_gate_from_readiness(readiness)
    production = production_eligibility_gate_from_readiness(readiness)
    if (
        body.vulnerability_profile is not None
        and profile.valuation_cutoff != body.valuation_date
    ):
        production = EvidenceGateResult(
            gate_id=production.gate_id,
            status="blocked",
            reasons=[
                *production.reasons,
                "profile valuation_cutoff must equal valuation_date for production eligibility",
            ],
        )
    return completeness, production


def _water_stress_gate(body: DataCentreAssessmentRequest) -> EvidenceGateResult:
    reasons = _manifest_reasons("water_stress", body.water_stress.manifest)
    if body.water_stress.classification is WaterStressClass.NOT_CLASSIFIED:
        reasons.append("water-stress classification is not_classified")
    return EvidenceGateResult(
        gate_id="water_stress_readiness",
        status="blocked" if reasons else "open",
        reasons=reasons,
    )


def _indicator_status(manifest: EvidenceManifest) -> str:
    return (
        "supported"
        if manifest.licensed_for_commercial_use and not manifest.synthetic
        else "evidence_blocked"
    )


def _design_limit_comparison(
    *,
    design_limit: float | None,
    projected: float | None,
    measure: str,
) -> tuple[bool | None, str]:
    if design_limit is None or projected is None:
        return None, f"{measure} design limit or scenario value is missing"
    exceeded = projected > design_limit
    return (
        exceeded,
        (
            f"projected {measure} temperature exceeds the declared design limit"
            if exceeded
            else f"projected {measure} temperature is within the declared design limit"
        ),
    )


def _cooling_trigger(
    body: DataCentreAssessmentRequest,
    vulnerability: ResolvedVulnerabilityInputs,
) -> tuple[str, list[str]]:
    heat = body.heat
    rationales: list[str] = []
    comparisons: list[bool] = []
    required_measure_missing = False

    measures: list[tuple[str, float | None, float | None]] = []
    if vulnerability.cooling_type in _DRY_BULB_REQUIRED_TYPES or (
        vulnerability.cooling_type in _LIQUID_COOLING_TYPES
        and vulnerability.design_max_dry_bulb_c is not None
    ):
        measures.append(
            (
                "dry-bulb",
                vulnerability.design_max_dry_bulb_c,
                heat.projected_max_dry_bulb_c,
            )
        )
    if vulnerability.cooling_type in _WET_BULB_REQUIRED_TYPES or (
        vulnerability.cooling_type in _LIQUID_COOLING_TYPES
        and vulnerability.design_max_wet_bulb_c is not None
    ):
        measures.append(
            (
                "wet-bulb",
                vulnerability.design_max_wet_bulb_c,
                heat.projected_max_wet_bulb_c,
            )
        )

    if vulnerability.cooling_type in _LIQUID_COOLING_TYPES and not measures:
        required_measure_missing = True
        rationales.append("liquid cooling requires a dry-bulb or wet-bulb design limit")

    for measure, design_limit, projected in measures:
        exceeded, rationale = _design_limit_comparison(
            design_limit=design_limit,
            projected=projected,
            measure=measure,
        )
        rationales.append(rationale)
        if exceeded is None:
            required_measure_missing = True
        else:
            comparisons.append(exceeded)

    if vulnerability.cooling_type is CoolingType.UNKNOWN:
        required_measure_missing = True
        rationales.append("cooling type is unknown")

    if vulnerability.water_dependency is WaterDependency.UNKNOWN:
        required_measure_missing = True
        rationales.append("water dependency is unknown")

    if vulnerability.water_dependency in _POTENTIALLY_WATER_DEPENDENT:
        if body.water_stress.classification in {WaterStressClass.HIGH, WaterStressClass.EXTREME}:
            comparisons.append(True)
            rationales.append("provider-classified water stress is high/extreme for a water-dependent site")
        elif body.water_stress.classification is WaterStressClass.NOT_CLASSIFIED:
            required_measure_missing = True
            rationales.append("water stress is not classified by the evidence provider")
        else:
            comparisons.append(False)
            rationales.append("provider-classified water stress is below high for this horizon")

    if any(comparisons):
        return "triggered", rationales
    if required_measure_missing or not comparisons:
        return "indeterminate", rationales or ["insufficient cooling vulnerability evidence"]
    return "not_triggered", rationales


def _flood_trigger(
    body: DataCentreAssessmentRequest,
    vulnerability: ResolvedVulnerabilityInputs,
) -> tuple[str, list[str]]:
    floor = vulnerability.finished_floor_elevation_m_agl
    if floor is None:
        return "indeterminate", ["finished-floor elevation is missing"]
    triggered = body.flood.maximum_site_water_depth_m > floor
    return (
        "triggered" if triggered else "not_triggered",
        [
            "scenario water depth exceeds finished-floor elevation"
            if triggered
            else "scenario water depth does not exceed finished-floor elevation"
        ],
    )


def _power_trigger(
    body: DataCentreAssessmentRequest,
    vulnerability: ResolvedVulnerabilityInputs,
) -> tuple[str, list[str]]:
    continuity = body.power_continuity
    backup = vulnerability.backup_power_hours
    if continuity is None:
        return "indeterminate", ["site/grid climate-related outage evidence is missing"]
    if backup is None:
        return "indeterminate", ["backup-power duration is missing"]
    triggered = continuity.maximum_climate_related_outage_hours > backup
    return (
        "triggered" if triggered else "not_triggered",
        [
            "evidenced outage duration exceeds declared backup-power duration"
            if triggered
            else "declared backup-power duration covers the evidenced outage duration"
        ],
    )


def _aggregate_trigger(*statuses: str) -> str:
    if "triggered" in statuses:
        return "triggered"
    if "indeterminate" in statuses:
        return "indeterminate"
    return "not_triggered"


def assess_data_centre(
    body: DataCentreAssessmentRequest,
    *,
    as_of: date | None = None,
) -> DataCentreAssessmentResponse:
    assessment_date = as_of or date.today()
    vulnerability = resolved_vulnerability_inputs(body)
    profile = resolve_assessment_profile(body)
    evidence_gate = _evidence_gate(body)
    vulnerability_gate, production_eligibility_gate = _vulnerability_gates(body)
    water_stress_gate = _water_stress_gate(body)
    validation_gate = _validation_gate(body, as_of=assessment_date)

    heat_status = _indicator_status(body.heat.manifest)
    flood_status = _indicator_status(body.flood.manifest)
    water_status = _indicator_status(body.water_stress.manifest)
    indicators = [
        IndicatorResult(
            indicator_id="heat",
            status=heat_status,
            horizon=body.heat.horizon,
            values={
                "projected_max_dry_bulb_c": body.heat.projected_max_dry_bulb_c,
                "projected_max_wet_bulb_c": body.heat.projected_max_wet_bulb_c,
                "wsdi_days": body.heat.wsdi_days,
            },
            evidence_sha256=body.heat.manifest.sha256,
        ),
        IndicatorResult(
            indicator_id="flood",
            status=flood_status,
            horizon=body.flood.horizon,
            values={
                "maximum_site_water_depth_m": body.flood.maximum_site_water_depth_m,
                "flood_type": body.flood.flood_type,
                "return_period_years": body.flood.return_period_years,
            },
            evidence_sha256=body.flood.manifest.sha256,
        ),
        IndicatorResult(
            indicator_id="water_stress",
            status=water_status,
            horizon=body.water_stress.horizon,
            values={
                "classification": body.water_stress.classification.value,
                "provider_metric": body.water_stress.provider_metric,
                "drought_indicator": body.water_stress.drought_indicator,
            },
            evidence_sha256=body.water_stress.manifest.sha256,
        ),
    ]
    if body.power_continuity is not None:
        indicators.append(
            IndicatorResult(
                indicator_id="power_continuity",
                status=_indicator_status(body.power_continuity.manifest),
                horizon=body.power_continuity.horizon,
                values={
                    "maximum_climate_related_outage_hours": (
                        body.power_continuity.maximum_climate_related_outage_hours
                    )
                },
                evidence_sha256=body.power_continuity.manifest.sha256,
            )
        )

    cooling_block = _blocked_evidence_reasons(
        *_cooling_required_evidence(body, vulnerability)
    )
    if cooling_block:
        cooling_status, cooling_reasons = "indeterminate", cooling_block
    else:
        cooling_status, cooling_reasons = _cooling_trigger(body, vulnerability)

    flood_block = _blocked_evidence_reasons(("flood", body.flood.manifest))
    if flood_block:
        flood_trigger, flood_reasons = "indeterminate", flood_block
    else:
        flood_trigger, flood_reasons = _flood_trigger(body, vulnerability)

    power_status, power_reasons = _power_trigger(body, vulnerability)
    if body.power_continuity is not None:
        power_block = _blocked_evidence_reasons(
            ("power_continuity", body.power_continuity.manifest)
        )
        if power_block:
            power_status, power_reasons = "indeterminate", power_block
    downtime_status = _aggregate_trigger(cooling_status, flood_trigger, power_status)
    downtime_reasons = [*cooling_reasons, *flood_reasons, *power_reasons]
    adaptation_status = "triggered" if downtime_status == "triggered" else downtime_status

    pathways = [
        LossPathwayResult(
            pathway_id="cooling_derating",
            trigger_status=cooling_status,
            rationale=cooling_reasons,
        ),
        LossPathwayResult(
            pathway_id="power_curtailment",
            trigger_status=power_status,
            rationale=power_reasons,
        ),
        LossPathwayResult(
            pathway_id="downtime",
            trigger_status=downtime_status,
            rationale=downtime_reasons,
        ),
        LossPathwayResult(
            pathway_id="business_interruption",
            trigger_status=downtime_status,
            rationale=[
                "Business interruption follows the downtime trigger, but monetary severity is not validated."
            ],
        ),
        LossPathwayResult(
            pathway_id="adaptation_capex",
            trigger_status=adaptation_status,
            rationale=[
                "Adaptation investigation is indicated when a physical pathway triggers; cost remains unquantified."
            ],
        ),
    ]

    readiness = (
        "decision_support_only"
        if (
            evidence_gate.status == "open"
            and vulnerability_gate.status == "open"
            and water_stress_gate.status == "open"
        )
        else "blocked"
    )
    canonical_request = json.dumps(
        body.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assessment_id = f"dc_{hashlib.sha256(canonical_request).hexdigest()}"
    evidence_hashes = {
        "heat": body.heat.manifest.sha256,
        "flood": body.flood.manifest.sha256,
        "water_stress": body.water_stress.manifest.sha256,
    }
    if body.power_continuity is not None:
        evidence_hashes["power_continuity"] = body.power_continuity.manifest.sha256
    return DataCentreAssessmentResponse(
        assessment_id=assessment_id,
        asset_id=body.vulnerability.asset_id,
        methodology_version=body.methodology_version,
        country_pack_id=body.country_pack_id,
        valuation_date=body.valuation_date,
        vulnerability_profile_cutoff=profile.valuation_cutoff,
        vulnerability_evidence_stale=(
            body.vulnerability_profile is not None
            and profile.valuation_cutoff is not None
            and profile.valuation_cutoff < body.valuation_date
        ),
        horizon=body.heat.horizon,
        readiness=readiness,
        gates=[
            evidence_gate,
            vulnerability_gate,
            production_eligibility_gate,
            water_stress_gate,
            validation_gate,
        ],
        production_release="none",
        downtime_model_released=False,
        monetary_model_released=False,
        gate1_harness=GATE1_HARNESS,
        indicators=indicators,
        loss_pathways=pathways,
        evidence_manifest_sha256s=evidence_hashes,
        monetary_outputs=MonetaryOutputs(),
        reporting_boundary=reporting_boundary(),
    )
