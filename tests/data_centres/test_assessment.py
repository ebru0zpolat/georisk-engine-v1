from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.data_centres import assess_data_centre, reporting_boundary
from app.data_centres.contracts import DataCentreAssessmentRequest
from app.schemas.dc_facility_fixtures import facility_by_id
from app.data_centres.water_stress import (
    UnconfiguredWaterStressProvider,
    WaterStressEvidenceUnavailable,
    WaterStressQuery,
    require_production_water_stress,
)


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64


def _manifest(sha: str, *, synthetic: bool = False, licensed: bool = True) -> dict:
    return {
        "source": "test-only evidence fixture",
        "dataset_id": "fixture-v1",
        "version": "1.0",
        "licence": "test fixture licence",
        "licensed_for_commercial_use": licensed,
        "retrieved_on": "2026-08-13",
        "sha256": sha,
        "synthetic": synthetic,
    }


def _request(*, synthetic_water: bool = False, licensed_water: bool = True) -> dict:
    return {
        "country_pack_id": "pack-nl@0.1.0",
        "valuation_date": "2026-08-13",
        "vulnerability": {
            "asset_id": "dc-001",
            "cooling_type": "hybrid",
            "design_max_dry_bulb_c": 38,
            "design_max_wet_bulb_c": 25,
            "water_dependency": "high",
            "power_redundancy": "two_n",
            "finished_floor_elevation_m_agl": 0.5,
            "backup_power_hours": 12,
            "critical_load_mw": 40,
            "independent_utility_feeds": 2,
            "water_usage_effectiveness": 1.8,
            "design_pue": 1.3,
            "flood_barrier_height_m": 0.4,
            "it_load_density_kw_per_rack": 12,
        },
        "heat": {
            "horizon": "2050",
            "projected_max_dry_bulb_c": 42,
            "projected_max_wet_bulb_c": 27,
            "wsdi_days": 18,
            "manifest": _manifest(HEX_A),
        },
        "flood": {
            "horizon": "2050",
            "maximum_site_water_depth_m": 0.8,
            "flood_type": "pluvial",
            "return_period_years": 100,
            "manifest": _manifest(HEX_B),
        },
        "water_stress": {
            "horizon": "2050",
            "classification": "high",
            "provider_metric": "provider-water-stress-index",
            "provider_threshold_reference": "fixture-thresholds-v1",
            "drought_indicator": 2.1,
            "manifest": _manifest(
                HEX_C, synthetic=synthetic_water, licensed=licensed_water
            ),
        },
        "power_continuity": {
            "horizon": "2050",
            "maximum_climate_related_outage_hours": 20,
            "manifest": _manifest(HEX_D),
        },
    }


_ARCHITECTURE_TO_COOLING_TYPE = {
    "air_cooled_dx": "air",
    "chilled_water_air_cooled": "air",
    "chilled_water_water_cooled": "evaporative",
    "evaporative_direct": "evaporative",
    "evaporative_indirect": "evaporative",
    "hybrid_adiabatic": "hybrid",
    "direct_to_chip_liquid": "direct_to_chip_liquid",
    "free_cooling_only": "air",
}
_WATER_DEPENDENT_ARCHITECTURES = {
    "chilled_water_water_cooled",
    "evaporative_direct",
    "evaporative_indirect",
    "hybrid_adiabatic",
}


def _complete_profile_payload(*, facility_id: str = "DC-MIN-004") -> dict:
    """Engineering-complete synthetic profile without a signed review (STUBS.md #22)."""
    profile = facility_by_id(facility_id)
    assert profile is not None
    data = profile.model_dump(mode="json")
    data["facility_id"] = "dc-001"
    data["valuation_cutoff"] = "2026-08-13"
    data.pop("engineering_review", None)
    return data


def _align_flat_to_profile(payload: dict) -> dict:
    """Make overlapping flat fields match the profile so the request is valid."""
    profile = payload["vulnerability_profile"]
    cooling = profile["cooling"]
    electrical = profile["electrical"]
    flood = profile["flood"]
    architecture = cooling["cooling_architecture"]
    payload["vulnerability"]["cooling_type"] = _ARCHITECTURE_TO_COOLING_TYPE[architecture]
    payload["vulnerability"]["design_max_dry_bulb_c"] = cooling.get(
        "dry_bulb_design_limit_c"
    )
    payload["vulnerability"]["design_max_wet_bulb_c"] = cooling.get(
        "wet_bulb_design_limit_c"
    )
    water_dependent = architecture in _WATER_DEPENDENT_ARCHITECTURES
    payload["vulnerability"]["water_dependency"] = "high" if water_dependent else "none"
    if not water_dependent:
        payload["vulnerability"]["water_usage_effectiveness"] = None
    payload["vulnerability"]["finished_floor_elevation_m_agl"] = flood.get(
        "finished_floor_elevation_m"
    )
    payload["vulnerability"]["backup_power_hours"] = electrical.get(
        "generator_autonomy_hours"
    )
    payload["vulnerability"]["independent_utility_feeds"] = electrical.get(
        "grid_feed_count"
    )
    redundancy = electrical.get("electrical_redundancy_config")
    if redundancy:
        payload["vulnerability"]["power_redundancy"] = redundancy
    payload["vulnerability"]["flood_barrier_height_m"] = flood.get(
        "flood_defence_height_m"
    )
    payload["vulnerability"]["flood_protection_return_period_years"] = flood.get(
        "flood_defence_design_return_period_years"
    )
    return payload


def _request_with_complete_profile(*, facility_id: str = "DC-MIN-004") -> dict:
    payload = _request()
    payload["vulnerability_profile"] = _complete_profile_payload(facility_id=facility_id)
    return _align_flat_to_profile(payload)


def test_assessment_exposes_water_stress_and_all_loss_pathways() -> None:
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(_request_with_complete_profile())
    )
    assert result.readiness == "decision_support_only"
    assert result.assessment_id.startswith("dc_")
    assert result.country_pack_id == "pack-nl@0.1.0"
    assert {row.indicator_id for row in result.indicators} == {
        "heat",
        "flood",
        "water_stress",
        "power_continuity",
    }
    assert {row.pathway_id for row in result.loss_pathways} == {
        "cooling_derating",
        "power_curtailment",
        "downtime",
        "business_interruption",
        "adaptation_capex",
    }


def test_exceedances_trigger_non_monetary_pathways() -> None:
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(_request()))
    states = {row.pathway_id: row.trigger_status for row in result.loss_pathways}
    assert states["cooling_derating"] == "triggered"
    assert states["power_curtailment"] == "triggered"
    assert states["downtime"] == "triggered"


def test_monetary_outputs_always_fail_closed_without_validated_calculator() -> None:
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(_request()))
    assert result.monetary_outputs.model_dump() == {
        "expected_annual_loss": None,
        "downtime_hours": None,
        "business_interruption_loss": None,
        "adaptation_capex": None,
        "currency": None,
    }
    assert result.production_release == "none"
    assert result.downtime_model_released is False
    assert result.monetary_model_released is False
    assert result.gate1_harness == "app.validation.gate1.run_comparison"
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert gate.status == "blocked"
    assert "no validated data-centre monetary loss calculator is configured" in gate.reasons


def test_synthetic_water_stress_blocks_production_readiness() -> None:
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(_request(synthetic_water=True))
    )
    assert result.readiness == "blocked"
    water = next(row for row in result.indicators if row.indicator_id == "water_stress")
    assert water.status == "evidence_blocked"
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert "water_stress: synthetic evidence cannot open a production gate" in cooling.rationale


def test_unlicensed_water_stress_blocks_production_readiness() -> None:
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(_request(licensed_water=False))
    )
    gate = result.gates[0]
    assert gate.status == "blocked"
    assert "water_stress: commercial-use licence not confirmed" in gate.reasons
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert "water_stress: commercial-use licence not confirmed" in cooling.rationale


def test_missing_power_evidence_is_explicit_not_silently_assumed() -> None:
    payload = _request()
    payload.pop("power_continuity")
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    pathway = next(p for p in result.loss_pathways if p.pathway_id == "power_curtailment")
    assert pathway.trigger_status == "indeterminate"
    assert pathway.rationale == ["site/grid climate-related outage evidence is missing"]


def test_incomplete_vulnerability_blocks_readiness() -> None:
    payload = _request()
    payload["vulnerability"]["cooling_type"] = "unknown"
    payload["vulnerability"]["water_dependency"] = "unknown"
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    gate = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert gate.status == "blocked"
    assert any(reason.startswith("DC-001:") for reason in gate.reasons)


def test_flat_only_vulnerability_is_incomplete_against_engineering_contract() -> None:
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(_request()))
    assert result.readiness == "blocked"
    gate = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert gate.status == "blocked"
    assert any(reason.startswith("DC-002:") for reason in gate.reasons)
    assert any(reason.startswith("DC-049:") for reason in gate.reasons)
    production = next(
        g
        for g in result.gates
        if g.gate_id == "data_centre_vulnerability_production_eligibility"
    )
    assert production.status == "blocked"
    assert any(reason.startswith("DC-053:") for reason in production.reasons)


def test_engineering_review_does_not_block_decision_support() -> None:
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(_request_with_complete_profile())
    )
    assert result.readiness == "decision_support_only"
    completeness = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert completeness.status == "open"
    production = next(
        g
        for g in result.gates
        if g.gate_id == "data_centre_vulnerability_production_eligibility"
    )
    assert production.status == "blocked"
    assert any(reason.startswith("DC-053:") for reason in production.reasons)


def test_matching_profile_and_flat_fields_are_accepted() -> None:
    payload = _request_with_complete_profile()
    first = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    second = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert first.assessment_id == second.assessment_id
    assert first.readiness == "decision_support_only"
    assert first.vulnerability_profile_cutoff == date(2026, 8, 13)
    assert first.vulnerability_evidence_stale is False


def test_conflicting_profile_dry_bulb_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["cooling"]["dry_bulb_design_limit_c"] = 28
    payload["vulnerability"]["design_max_dry_bulb_c"] = 80
    payload["heat"]["projected_max_dry_bulb_c"] = 42
    with pytest.raises(ValidationError, match="design_max_dry_bulb_c"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_conflicting_flood_elevation_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability"]["finished_floor_elevation_m_agl"] = 99.0
    with pytest.raises(ValidationError, match="finished_floor_elevation"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_conflicting_backup_autonomy_is_rejected() -> None:
    payload = _request_with_complete_profile(facility_id="DC-EDG-002")
    payload["vulnerability"]["backup_power_hours"] = 1
    with pytest.raises(ValidationError, match="backup_power_hours"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_canonical_profile_limit_triggers_when_representations_match() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["cooling"]["dry_bulb_design_limit_c"] = 28
    payload["vulnerability"]["design_max_dry_bulb_c"] = 28
    payload["heat"]["projected_max_dry_bulb_c"] = 42
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "triggered"
    assert "projected dry-bulb temperature exceeds the declared design limit" in cooling.rationale


def test_legacy_request_without_profile_keeps_flat_pathway_authority() -> None:
    payload = _request()
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.vulnerability_profile_cutoff == date(2026, 8, 13)
    assert result.vulnerability_evidence_stale is False
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "triggered"


def test_future_profile_cutoff_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["valuation_cutoff"] = "2099-01-01"
    with pytest.raises(ValidationError, match="valuation_cutoff"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_future_profile_review_date_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["engineering_review"] = {
        "reviewer": "future reviewer",
        "report_reference": "future-review",
        "review_date": "2098-01-01",
        "git_commit": "fixture",
        "approved": True,
    }
    with pytest.raises(ValidationError, match="engineering_review.review_date"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_future_profile_evidence_date_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["evidence_document_date"] = "2098-01-01"
    with pytest.raises(ValidationError, match="evidence_document_date"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_future_profile_inspection_date_is_rejected() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["flood"]["protection_inspection_date"] = "2098-01-01"
    with pytest.raises(ValidationError, match="protection_inspection_date"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_future_profile_commissioning_year_is_rejected_without_profile_cutoff() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["valuation_cutoff"] = None
    payload["vulnerability_profile"]["cooling"]["commissioning_year"] = 2099
    with pytest.raises(ValidationError, match="commissioning_year"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_profile_evidence_after_valuation_is_rejected_when_cutoff_absent() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["valuation_cutoff"] = None
    payload["vulnerability_profile"]["evidence_effective_date"] = "2098-01-01"
    with pytest.raises(ValidationError, match="evidence_effective_date"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_immersion_conflicts_with_declared_profile_architecture() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability"]["cooling_type"] = "immersion"
    with pytest.raises(ValidationError, match="cooling_type contradicts"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_none_power_redundancy_conflicts_with_declared_electrical() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability"]["power_redundancy"] = "none"
    with pytest.raises(ValidationError, match="power_redundancy contradicts"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_water_dependency_contradicts_profile_architecture_rejected() -> None:
    """A flat no-water claim next to a water-cooled profile is rejected, not overridden."""
    payload = _request_with_complete_profile(facility_id="DC-HYP-001")
    payload["vulnerability"]["water_dependency"] = "none"
    with pytest.raises(ValidationError, match="water_dependency contradicts"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_unknown_screening_fields_may_be_filled_by_profile() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability"]["cooling_type"] = "unknown"
    payload["vulnerability"]["power_redundancy"] = "unknown"
    body = DataCentreAssessmentRequest.model_validate(payload)
    assert body.vulnerability_profile is not None
    assert body.vulnerability_profile.cooling.cooling_architecture is not None
    assert body.vulnerability_profile.electrical.electrical_redundancy_config is not None


def test_older_profile_cutoff_is_stale_for_decision_support() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["valuation_cutoff"] = "2026-06-30"
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "decision_support_only"
    assert result.vulnerability_profile_cutoff == date(2026, 6, 30)
    assert result.vulnerability_evidence_stale is True
    production = next(
        g
        for g in result.gates
        if g.gate_id == "data_centre_vulnerability_production_eligibility"
    )
    assert production.status == "blocked"
    assert (
        "profile valuation_cutoff must equal valuation_date for production eligibility"
        in production.reasons
    )


def test_matching_cutoff_with_pre_cutoff_evidence_is_accepted() -> None:
    payload = _request_with_complete_profile()
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    dumped = result.model_dump(mode="json")
    assert dumped["vulnerability_profile_cutoff"] == "2026-08-13"
    assert dumped["vulnerability_evidence_stale"] is False
    assert dumped["valuation_date"] == "2026-08-13"


def test_profile_facility_id_must_match_asset_id() -> None:
    payload = _request_with_complete_profile()
    payload["vulnerability_profile"]["facility_id"] = "other-asset"
    with pytest.raises(ValidationError, match="facility_id"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_horizons_must_match() -> None:
    payload = _request()
    payload["water_stress"]["horizon"] = "2030"
    with pytest.raises(ValidationError, match="same scenario horizon"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_valuation_cutoff_rejects_lookahead_evidence() -> None:
    payload = _request()
    payload["valuation_date"] = "2026-08-12"
    with pytest.raises(ValidationError, match="valuation_date cutoff"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_assessment_id_is_deterministic_for_replay() -> None:
    body = DataCentreAssessmentRequest.model_validate(_request())
    first = assess_data_centre(body, as_of=date(2026, 8, 13))
    second = assess_data_centre(body, as_of=date(2026, 8, 13))
    assert first.assessment_id == second.assessment_id
    assert first.evidence_manifest_sha256s == second.evidence_manifest_sha256s


def test_hashes_are_strict_sha256() -> None:
    payload = _request()
    payload["water_stress"]["manifest"]["sha256"] = "not-a-hash"
    with pytest.raises(ValidationError):
        DataCentreAssessmentRequest.model_validate(payload)


def test_heat_requires_at_least_one_measure() -> None:
    payload = _request()
    payload["heat"].pop("projected_max_dry_bulb_c")
    payload["heat"].pop("projected_max_wet_bulb_c")
    payload["heat"].pop("wsdi_days")
    with pytest.raises(ValidationError, match="At least one heat measure"):
        DataCentreAssessmentRequest.model_validate(payload)


def test_expired_external_review_remains_blocked() -> None:
    payload = _request()
    payload["validation"] = {
        "external_review": {
            "reviewer_reference": "reviewer-001",
            "discipline": "data_centre_engineering",
            "independent": True,
            "conflicts_declaration_sha256": HEX_A,
            "review_report_sha256": HEX_B,
            "methodology_version": "data-centre-physical-risk-v0.1",
            "decision": "approved",
            "signed_on": "2026-01-01",
            "valid_until": "2026-06-30",
        }
    }
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(payload), as_of=date(2026, 8, 13)
    )
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert "external review evidence has expired" in gate.reasons


def test_eu_boundary_never_claims_compliance() -> None:
    boundary = reporting_boundary()
    assert boundary.support_level == "supporting_evidence_only"
    assert "compliance with Regulation (EU) 2024/1364" in boundary.prohibited_claims
    assert "water consumption and water usage effectiveness" in (
        boundary.operational_kpis_outside_this_assessment
    )


def test_water_stress_provider_has_no_silent_fallback() -> None:
    query = WaterStressQuery(
        latitude=53.2,
        longitude=6.6,
        horizon="2050",
        valuation_date="2026-08-13",
        country_pack_id="pack-nl",
    )
    with pytest.raises(WaterStressEvidenceUnavailable, match="No approved"):
        require_production_water_stress(UnconfiguredWaterStressProvider(), query)


def test_not_classified_water_stress_blocks_readiness() -> None:
    payload = _request()
    payload["water_stress"]["classification"] = "not_classified"
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    gate = next(g for g in result.gates if g.gate_id == "water_stress_readiness")
    assert gate.status == "blocked"
    assert "water-stress classification is not_classified" in gate.reasons


def test_wue_is_outside_engineering_completeness_gate() -> None:
    """WUE is an EU 2024/1364 operational KPI, not a DC-xxx completeness field."""
    payload = _request_with_complete_profile()
    payload["vulnerability"]["water_usage_effectiveness"] = None
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    gate = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert gate.status == "open"
    assert result.readiness == "decision_support_only"
    assert not any("water usage effectiveness" in reason for reason in gate.reasons)


def test_missing_utility_feeds_blocks_bridged_completeness() -> None:
    payload = _request()
    payload["vulnerability"].pop("independent_utility_feeds")
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    gate = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert any(reason.startswith("DC-018:") for reason in gate.reasons)


def test_foreign_backtest_harness_is_rejected() -> None:
    payload = _request()
    payload["validation"] = {
        "backtest": {
            "event_id": "evt-1",
            "harness_module": "app.data_centres.backtest",
            "harness_entrypoint": "run_local_engine",
            "pre_registration_commit_sha": "a" * 40,
            "observed_loss_manifest": _manifest(HEX_A),
            "result_report_sha256": HEX_B,
            "information_cutoff": "2019-06-30",
            "sample_size": 3,
            "comparison_status": "passed",
        }
    }
    with pytest.raises(ValidationError):
        DataCentreAssessmentRequest.model_validate(payload)


def test_require_production_water_stress_rejects_not_classified() -> None:
    class _ClassifiedProvider:
        def fetch(self, query: WaterStressQuery):
            from app.data_centres.contracts import WaterStressHazardEvidence

            return WaterStressHazardEvidence.model_validate(
                {
                    "horizon": query.horizon,
                    "classification": "not_classified",
                    "provider_metric": "provider-water-stress-index",
                    "provider_threshold_reference": "fixture-thresholds-v1",
                    "manifest": _manifest(HEX_C, licensed=True),
                }
            )

    query = WaterStressQuery(
        latitude=53.2,
        longitude=6.6,
        horizon="2050",
        valuation_date="2026-08-13",
        country_pack_id="pack-nl",
    )
    with pytest.raises(WaterStressEvidenceUnavailable, match="not_classified"):
        require_production_water_stress(_ClassifiedProvider(), query)


def test_backtest_must_name_shared_gate1_harness() -> None:
    payload = _request()
    payload["validation"] = {
        "backtest": {
            "event_id": "evt-1",
            "harness_module": "app.validation.gate1",
            "harness_entrypoint": "run_comparison",
            "pre_registration_commit_sha": "a" * 40,
            "observed_loss_manifest": _manifest(HEX_A),
            "result_report_sha256": HEX_B,
            "information_cutoff": "2019-06-30",
            "sample_size": 3,
            "comparison_status": "passed",
        }
    }
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert gate.status == "blocked"
    assert "Gate-1 ComparisonReport.config_hash is missing" in gate.reasons
    assert "no validated data-centre monetary loss calculator is configured" in gate.reasons


def _cooling_matrix_payload(
    *,
    cooling_type: str,
    projected_max_dry_bulb_c: float | None,
    projected_max_wet_bulb_c: float | None,
    water_classification: str,
    water_dependency: str,
) -> dict:
    payload = _request()
    payload["vulnerability"]["cooling_type"] = cooling_type
    payload["vulnerability"]["water_dependency"] = water_dependency
    if cooling_type == "air":
        payload["vulnerability"]["design_max_wet_bulb_c"] = None
    elif cooling_type == "evaporative":
        payload["vulnerability"]["design_max_dry_bulb_c"] = None
    if water_dependency in {"none", "low"}:
        payload["vulnerability"]["water_usage_effectiveness"] = None
    payload["heat"]["projected_max_dry_bulb_c"] = projected_max_dry_bulb_c
    payload["heat"]["projected_max_wet_bulb_c"] = projected_max_wet_bulb_c
    payload["water_stress"]["classification"] = water_classification
    payload["flood"]["maximum_site_water_depth_m"] = 0.1
    payload["power_continuity"]["maximum_climate_related_outage_hours"] = 1
    return payload


def _pathway_states(result) -> dict[str, str]:
    return {row.pathway_id: row.trigger_status for row in result.loss_pathways}


@pytest.mark.parametrize(
    (
        "cooling_type",
        "projected_max_dry_bulb_c",
        "projected_max_wet_bulb_c",
        "water_classification",
        "water_dependency",
        "expected_cooling",
        "missing_rationale",
    ),
    [
        ("air", 30, None, "low", "none", "not_triggered", None),
        (
            "air",
            None,
            20,
            "low",
            "high",
            "indeterminate",
            "dry-bulb design limit or scenario value is missing",
        ),
        ("evaporative", None, 20, "low", "none", "not_triggered", None),
        (
            "evaporative",
            30,
            None,
            "low",
            "high",
            "indeterminate",
            "wet-bulb design limit or scenario value is missing",
        ),
        ("hybrid", 30, 20, "low", "high", "not_triggered", None),
        (
            "hybrid",
            30,
            None,
            "low",
            "high",
            "indeterminate",
            "wet-bulb design limit or scenario value is missing",
        ),
        ("hybrid", 42, None, "low", "high", "triggered", None),
        (
            "hybrid",
            30,
            20,
            "not_classified",
            "high",
            "indeterminate",
            "water stress is not classified by the evidence provider",
        ),
        ("hybrid", 30, 20, "high", "high", "triggered", None),
        (
            "hybrid",
            30,
            20,
            "low",
            "unknown",
            "indeterminate",
            "water dependency is unknown",
        ),
        ("air", 30, None, "low", "unknown", "indeterminate", "water dependency is unknown"),
        ("evaporative", None, 20, "low", "unknown", "indeterminate", "water dependency is unknown"),
    ],
)
def test_cooling_trigger_matrix_records_missing_required_measures(
    cooling_type: str,
    projected_max_dry_bulb_c: float | None,
    projected_max_wet_bulb_c: float | None,
    water_classification: str,
    water_dependency: str,
    expected_cooling: str,
    missing_rationale: str | None,
) -> None:
    payload = _cooling_matrix_payload(
        cooling_type=cooling_type,
        projected_max_dry_bulb_c=projected_max_dry_bulb_c,
        projected_max_wet_bulb_c=projected_max_wet_bulb_c,
        water_classification=water_classification,
        water_dependency=water_dependency,
    )
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == expected_cooling
    if missing_rationale is not None:
        assert missing_rationale in cooling.rationale


def _liquid_payload(
    *,
    cooling_type: str,
    dry_limit: float | None,
    wet_limit: float | None,
    projected_max_dry_bulb_c: float | None,
    projected_max_wet_bulb_c: float | None,
    water_dependency: str = "none",
    water_classification: str = "low",
) -> dict:
    payload = _request()
    payload["vulnerability"]["cooling_type"] = cooling_type
    payload["vulnerability"]["design_max_dry_bulb_c"] = dry_limit
    payload["vulnerability"]["design_max_wet_bulb_c"] = wet_limit
    payload["vulnerability"]["water_dependency"] = water_dependency
    if water_dependency in {"none", "low"}:
        payload["vulnerability"]["water_usage_effectiveness"] = None
    payload["heat"]["projected_max_dry_bulb_c"] = projected_max_dry_bulb_c
    payload["heat"]["projected_max_wet_bulb_c"] = projected_max_wet_bulb_c
    if projected_max_dry_bulb_c is None and projected_max_wet_bulb_c is None:
        payload["heat"]["wsdi_days"] = 1
    payload["water_stress"]["classification"] = water_classification
    payload["flood"]["maximum_site_water_depth_m"] = 0.1
    payload["power_continuity"]["maximum_climate_related_outage_hours"] = 1
    return payload


@pytest.mark.parametrize("cooling_type", ["direct_to_chip_liquid", "immersion"])
@pytest.mark.parametrize(
    (
        "dry_limit",
        "wet_limit",
        "projected_max_dry_bulb_c",
        "projected_max_wet_bulb_c",
        "expected_cooling",
        "expected_rationale",
    ),
    [
        (38, None, 30, None, "not_triggered", "projected dry-bulb temperature is within the declared design limit"),
        (38, None, 42, None, "triggered", "projected dry-bulb temperature exceeds the declared design limit"),
        (None, 25, None, 20, "not_triggered", "projected wet-bulb temperature is within the declared design limit"),
        (None, 25, None, 27, "triggered", "projected wet-bulb temperature exceeds the declared design limit"),
        (38, 25, 30, 20, "not_triggered", "projected dry-bulb temperature is within the declared design limit"),
        (38, 25, 42, 20, "triggered", "projected dry-bulb temperature exceeds the declared design limit"),
        (38, 25, 30, 27, "triggered", "projected wet-bulb temperature exceeds the declared design limit"),
        (None, None, 30, 20, "indeterminate", "liquid cooling requires a dry-bulb or wet-bulb design limit"),
    ],
)
def test_liquid_cooling_compares_declared_design_limits(
    cooling_type: str,
    dry_limit: float | None,
    wet_limit: float | None,
    projected_max_dry_bulb_c: float | None,
    projected_max_wet_bulb_c: float | None,
    expected_cooling: str,
    expected_rationale: str,
) -> None:
    payload = _liquid_payload(
        cooling_type=cooling_type,
        dry_limit=dry_limit,
        wet_limit=wet_limit,
        projected_max_dry_bulb_c=projected_max_dry_bulb_c,
        projected_max_wet_bulb_c=projected_max_wet_bulb_c,
    )
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == expected_cooling
    assert expected_rationale in cooling.rationale
    assert result.monetary_outputs.expected_annual_loss is None
    assert result.production_release == "none"


def test_liquid_cooling_without_design_limits_blocks_completeness() -> None:
    payload = _liquid_payload(
        cooling_type="direct_to_chip_liquid",
        dry_limit=None,
        wet_limit=None,
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=20,
    )
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    gate = next(
        g for g in result.gates if g.gate_id == "data_centre_vulnerability_completeness"
    )
    assert any(reason.startswith("DC-006:") for reason in gate.reasons)


def test_liquid_cooling_with_one_limit_is_decidable_on_the_legacy_path() -> None:
    payload = _liquid_payload(
        cooling_type="immersion",
        dry_limit=38,
        wet_limit=None,
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=None,
    )
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "not_triggered"
    assert result.readiness == "blocked"
    assert result.production_release == "none"
    assert result.monetary_model_released is False


def test_unknown_water_dependency_cannot_clear_air_site_with_synthetic_water() -> None:
    payload = _cooling_matrix_payload(
        cooling_type="air",
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=None,
        water_classification="low",
        water_dependency="unknown",
    )
    payload["water_stress"]["manifest"] = _manifest(HEX_C, synthetic=True)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert "water_stress: synthetic evidence cannot open a production gate" in cooling.rationale


def test_unknown_water_dependency_cannot_clear_air_site_with_unlicensed_water() -> None:
    payload = _cooling_matrix_payload(
        cooling_type="air",
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=None,
        water_classification="low",
        water_dependency="unknown",
    )
    payload["water_stress"]["manifest"] = _manifest(HEX_C, licensed=False)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert "water_stress: commercial-use licence not confirmed" in cooling.rationale


def test_partial_heat_on_open_hybrid_site_does_not_clear_downtime() -> None:
    payload = _request_with_complete_profile(facility_id="DC-HYP-001")
    payload["vulnerability_profile"]["cooling"]["cooling_architecture"] = "hybrid_adiabatic"
    payload = _align_flat_to_profile(payload)
    payload["heat"]["projected_max_dry_bulb_c"] = 30
    payload["heat"]["projected_max_wet_bulb_c"] = None
    payload["water_stress"]["classification"] = "low"
    payload["flood"]["maximum_site_water_depth_m"] = 0.1
    payload["power_continuity"]["maximum_climate_related_outage_hours"] = 1
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "decision_support_only"
    states = _pathway_states(result)
    assert states["cooling_derating"] == "indeterminate"
    assert states["downtime"] == "indeterminate"
    assert states["business_interruption"] == "indeterminate"


def test_partial_heat_on_open_air_site_does_not_clear_downtime() -> None:
    payload = _request_with_complete_profile()
    payload["heat"]["projected_max_dry_bulb_c"] = None
    payload["heat"]["projected_max_wet_bulb_c"] = 20
    payload["flood"]["maximum_site_water_depth_m"] = 0.1
    payload["power_continuity"]["maximum_climate_related_outage_hours"] = 1
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "decision_support_only"
    states = _pathway_states(result)
    assert states["cooling_derating"] == "indeterminate"
    assert states["downtime"] == "indeterminate"
    assert states["business_interruption"] == "indeterminate"


def test_unknown_water_dependency_never_reports_cooling_not_triggered() -> None:
    # In-limit heat on its own must not clear the cooling pathway when the
    # water dependency is unknown: the site may still rely on water.
    payload = _cooling_matrix_payload(
        cooling_type="hybrid",
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=20,
        water_classification="low",
        water_dependency="unknown",
    )
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert "water dependency is unknown" in cooling.rationale
    states = _pathway_states(result)
    assert states["cooling_derating"] != "not_triggered"


@pytest.mark.parametrize(
    ("synthetic", "licensed", "block_reason"),
    [
        (
            True,
            True,
            "water_stress: synthetic evidence cannot open a production gate",
        ),
        (
            False,
            False,
            "water_stress: commercial-use licence not confirmed",
        ),
    ],
)
def test_unknown_water_dependency_still_requires_open_water_stress_evidence(
    synthetic: bool, licensed: bool, block_reason: str
) -> None:
    # Bugbot: unknown water dependency must NOT bypass the water-stress
    # evidence short-circuit. Synthetic or unlicensed water-stress evidence
    # must hold the cooling pathway indeterminate even when heat is in-limit.
    payload = _cooling_matrix_payload(
        cooling_type="hybrid",
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=20,
        water_classification="low",
        water_dependency="unknown",
    )
    _block_manifest(payload, "water_stress", synthetic=synthetic, licensed=licensed)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    cooling = next(row for row in result.loss_pathways if row.pathway_id == "cooling_derating")
    assert cooling.trigger_status == "indeterminate"
    assert block_reason in cooling.rationale


def _block_manifest(payload: dict, field: str, *, synthetic: bool = False, licensed: bool = True) -> dict:
    payload[field]["manifest"] = _manifest(
        payload[field]["manifest"]["sha256"],
        synthetic=synthetic,
        licensed=licensed,
    )
    return payload


@pytest.mark.parametrize(
    ("field", "synthetic", "licensed", "pathway_id", "block_reason"),
    [
        (
            "heat",
            True,
            True,
            "cooling_derating",
            "heat: synthetic evidence cannot open a production gate",
        ),
        (
            "heat",
            False,
            False,
            "cooling_derating",
            "heat: commercial-use licence not confirmed",
        ),
        (
            "water_stress",
            True,
            True,
            "cooling_derating",
            "water_stress: synthetic evidence cannot open a production gate",
        ),
        (
            "water_stress",
            False,
            False,
            "cooling_derating",
            "water_stress: commercial-use licence not confirmed",
        ),
        (
            "flood",
            True,
            True,
            "downtime",
            "flood: synthetic evidence cannot open a production gate",
        ),
        (
            "flood",
            False,
            False,
            "downtime",
            "flood: commercial-use licence not confirmed",
        ),
        (
            "power_continuity",
            True,
            True,
            "power_curtailment",
            "power_continuity: synthetic evidence cannot open a production gate",
        ),
        (
            "power_continuity",
            False,
            False,
            "power_curtailment",
            "power_continuity: commercial-use licence not confirmed",
        ),
    ],
)
def test_blocked_evidence_short_circuits_affected_pathway(
    field: str,
    synthetic: bool,
    licensed: bool,
    pathway_id: str,
    block_reason: str,
) -> None:
    payload = _cooling_matrix_payload(
        cooling_type="hybrid",
        projected_max_dry_bulb_c=30 if field in {"flood", "power_continuity"} else 42,
        projected_max_wet_bulb_c=20 if field in {"flood", "power_continuity"} else 27,
        water_classification="low" if field in {"flood", "power_continuity"} else "high",
        water_dependency="high",
    )
    if field == "flood":
        payload["flood"]["maximum_site_water_depth_m"] = 0.8
    if field == "power_continuity":
        payload["power_continuity"]["maximum_climate_related_outage_hours"] = 20
    _block_manifest(payload, field, synthetic=synthetic, licensed=licensed)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    pathway = next(row for row in result.loss_pathways if row.pathway_id == pathway_id)
    assert pathway.trigger_status == "indeterminate"
    assert block_reason in pathway.rationale


def test_blocked_flood_alone_cannot_clear_or_trigger_downtime() -> None:
    payload = _cooling_matrix_payload(
        cooling_type="hybrid",
        projected_max_dry_bulb_c=30,
        projected_max_wet_bulb_c=20,
        water_classification="low",
        water_dependency="high",
    )
    payload["flood"]["maximum_site_water_depth_m"] = 0.8
    _block_manifest(payload, "flood", synthetic=True)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    states = _pathway_states(result)
    assert states["cooling_derating"] == "not_triggered"
    assert states["power_curtailment"] == "not_triggered"
    assert states["downtime"] == "indeterminate"
    assert states["business_interruption"] == "indeterminate"
    assert states["adaptation_capex"] == "indeterminate"


def test_all_blocked_hazard_evidence_keeps_pathways_indeterminate() -> None:
    payload = _request()
    for field in ("heat", "flood", "water_stress", "power_continuity"):
        _block_manifest(payload, field, licensed=False)
    result = assess_data_centre(DataCentreAssessmentRequest.model_validate(payload))
    assert result.readiness == "blocked"
    states = _pathway_states(result)
    assert states == {
        "cooling_derating": "indeterminate",
        "power_curtailment": "indeterminate",
        "downtime": "indeterminate",
        "business_interruption": "indeterminate",
        "adaptation_capex": "indeterminate",
    }


def _backtest(**overrides) -> dict:
    payload = {
        "event_id": "evt-1",
        "harness_module": "app.validation.gate1",
        "harness_entrypoint": "run_comparison",
        "pre_registration_commit_sha": "a" * 40,
        "observed_loss_manifest": _manifest(HEX_A),
        "result_report_sha256": HEX_B,
        "information_cutoff": "2019-06-30",
        "sample_size": 3,
        "comparison_status": "passed",
    }
    payload.update(overrides)
    return payload


def _review(**overrides) -> dict:
    payload = {
        "reviewer_reference": "reviewer-001",
        "discipline": "data_centre_engineering",
        "independent": True,
        "conflicts_declaration_sha256": HEX_A,
        "review_report_sha256": HEX_B,
        "methodology_version": "data-centre-physical-risk-v0.1",
        "decision": "approved",
        "signed_on": "2026-01-01",
        "valid_until": "2026-12-31",
    }
    payload.update(overrides)
    return payload


def test_valuation_cutoff_accepts_validation_evidence_on_the_boundary() -> None:
    payload = _request()
    payload["validation"] = {
        "backtest": _backtest(
            observed_loss_manifest={**_manifest(HEX_A), "retrieved_on": "2026-08-13"},
            information_cutoff="2026-08-13",
        ),
        "external_review": _review(signed_on="2026-08-13", valid_until="2026-08-13"),
    }
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(payload), as_of=date(2026, 8, 13)
    )
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert "external review signed_on is after the assessment date" not in gate.reasons
    assert "external review was not valid at valuation_date" not in gate.reasons
    assert "external review evidence has expired" not in gate.reasons


@pytest.mark.parametrize(
    ("validation", "match"),
    [
        (
            {
                "backtest": _backtest(
                    observed_loss_manifest={
                        **_manifest(HEX_A),
                        "retrieved_on": "2026-08-14",
                    }
                )
            },
            "Observed-loss evidence violates the valuation_date cutoff",
        ),
        (
            {"backtest": _backtest(information_cutoff="2026-08-14")},
            "Backtest information_cutoff violates the valuation_date cutoff",
        ),
        (
            {"external_review": _review(signed_on="2026-08-14", valid_until="2026-12-31")},
            "External review signed_on violates the valuation_date cutoff",
        ),
    ],
)
def test_valuation_cutoff_rejects_validation_lookahead(
    validation: dict,
    match: str,
) -> None:
    payload = _request()
    payload["validation"] = validation
    with pytest.raises(ValidationError, match=match):
        DataCentreAssessmentRequest.model_validate(payload)


def test_external_review_signed_after_as_of_is_lookahead() -> None:
    payload = _request()
    payload["validation"] = {"external_review": _review(signed_on="2026-08-13")}
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(payload), as_of=date(2026, 8, 1)
    )
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert "external review signed_on is after the assessment date" in gate.reasons


def test_external_review_expired_before_valuation_date_is_blocked() -> None:
    payload = _request()
    payload["validation"] = {
        "external_review": _review(signed_on="2025-01-01", valid_until="2026-06-30")
    }
    result = assess_data_centre(
        DataCentreAssessmentRequest.model_validate(payload), as_of=date(2026, 8, 13)
    )
    gate = next(g for g in result.gates if g.gate_id == "monetary_loss_validation")
    assert "external review was not valid at valuation_date" in gate.reasons
    assert "external review evidence has expired" in gate.reasons
