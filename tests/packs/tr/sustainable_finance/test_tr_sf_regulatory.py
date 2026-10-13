"""Regulatory source, routes, physical-risk policy and claim-scanner unit tests."""

from __future__ import annotations

from app.packs.tr.sustainable_finance import regulatory_source as rs
from app.packs.tr.sustainable_finance.claims import scan_text
from app.packs.tr.sustainable_finance.physical_risk import (
    HazardReference,
    KPISuitability,
    RecalculationBridge,
    is_available_for_trigger_use,
    lookup_kpi_suitability,
)
from app.packs.tr.sustainable_finance.routes import (
    EligibilityStatus,
    GEORISK_ASSIGNABLE_STATES,
    PackStatus,
    is_georisk_assignable,
    role_separation_ok,
)


def test_decision_identity_is_pinned() -> None:
    m = rs.regulatory_source_manifest()
    assert m["regulatory_source_id"] == "i-SPK.128.29"
    assert m["decision_date"] == "2026-08-13"
    assert m["decision_number"] == "49/1500"
    assert rs.SUPERSEDED_DECISION_ID == "i-SPK.128.18"
    assert rs.CMB_FEE_DISCOUNT_FRACTION == 0.50


def test_only_two_external_review_types_remain() -> None:
    # 2022's certification and green rating/scoring are no longer guideline review types.
    assert set(rs.EXTERNAL_REVIEW_TYPES) == {"second_party_opinion", "verification"}


def test_georisk_relevant_green_categories() -> None:
    # Water/flood (8), adaptation (9) and green buildings (11) are GeoRisk-relevant.
    assert set(rs.GEORISK_RELEVANT_GREEN_CATEGORIES) == {8, 9, 11}


def test_interpretation_flags_include_physical_risk_not_named() -> None:
    ids = {f["id"] for f in rs.INTERPRETATION_FLAGS}
    assert "physical_risk_kpi_not_named" in ids
    assert "uop_verifier_eligibility" in ids


def test_eligibility_status_has_no_true_value() -> None:
    values = {s.value for s in EligibilityStatus}
    assert "true" not in values
    assert "project_eligible" not in values
    assert EligibilityStatus.requires_external_review.value == "requires_external_review"


def test_georisk_assignable_states() -> None:
    assert GEORISK_ASSIGNABLE_STATES == {
        PackStatus.draft,
        PackStatus.technical_evidence_complete,
        PackStatus.reviewer_ready,
    }
    assert is_georisk_assignable(PackStatus.reviewer_ready)
    assert not is_georisk_assignable(PackStatus.verification_received)
    assert not is_georisk_assignable(PackStatus.issuer_approved)


def test_role_separation_flags_adviser_as_reviewer() -> None:
    ok, violations = role_separation_ok(
        framework_adviser="Adviser",
        second_party_opinion_provider="Adviser",  # same as framework adviser -> violation
        verifier="Auditor",
    )
    assert not ok
    assert any("framework adviser" in v for v in violations)


def test_role_separation_flags_spo_equals_verifier() -> None:
    ok, violations = role_separation_ok(
        framework_adviser="Adviser",
        second_party_opinion_provider="Both Ltd",
        verifier="both ltd",  # case-insensitive match -> violation
    )
    assert not ok


def test_role_separation_allows_distinct_or_unappointed() -> None:
    ok, _ = role_separation_ok(
        framework_adviser="Adviser", second_party_opinion_provider=None, verifier=None
    )
    assert ok


def test_physical_risk_matrix_defaults() -> None:
    external = lookup_kpi_suitability("external_hazard_intensity_reduction")
    assert external is not None and external["status"] == KPISuitability.reject.value

    eal = lookup_kpi_suitability("modelled_eal_downtime_or_loss_reduction")
    assert eal is not None
    assert eal["status"] == KPISuitability.not_available_for_trigger_use.value

    # Only conditional metrics are trigger-eligible; reject / not-available are not.
    assert is_available_for_trigger_use("pct_material_assets_meeting_resilience_threshold")
    assert not is_available_for_trigger_use("external_hazard_intensity_reduction")
    assert not is_available_for_trigger_use("modelled_eal_downtime_or_loss_reduction")
    # Unknown candidates fail closed.
    assert not is_available_for_trigger_use("something_unknown")


def test_constant_hazard_reference_lock_and_equality() -> None:
    ref = HazardReference(
        hazard_definition_and_unit="return-period flood depth (m)",
        dataset_and_licence="dataset-x / licence-y",
        model_and_ensemble_member="model-a / r1",
        scenario_and_time_horizon="baseline",
        baseline_period="1991-2020",
        spatial_resolution_and_extraction_method="90m / bilinear",
        methodology_version="v1",
        missing_or_nonfinite_value_treatment="drop",
    )
    assert ref.missing_locks() == []
    assert ref.is_constant_against(ref.model_copy())

    drifted = ref.model_copy(update={"model_and_ensemble_member": "model-b / r2"})
    assert not ref.is_constant_against(drifted)


def test_constant_hazard_reference_missing_locks() -> None:
    ref = HazardReference(
        hazard_definition_and_unit="",  # blank locked field
        dataset_and_licence="d/l",
        model_and_ensemble_member="m/r",
        scenario_and_time_horizon="s",
        baseline_period="p",
        spatial_resolution_and_extraction_method="r/m",
        methodology_version="v1",
        missing_or_nonfinite_value_treatment="drop",
    )
    assert "hazard_definition_and_unit" in ref.missing_locks()


def test_recalculation_bridge_rejects_silent_overwrite() -> None:
    bridge = RecalculationBridge(
        from_methodology_version="v1",
        to_methodology_version="v2",
        reason="dataset upgrade",
        original_value=10.0,
        restated_value=11.0,
        original_result_reproducible=False,  # silent overwrite
        original_run_id="run-1",
    )
    ok, problems = bridge.is_valid()
    assert not ok
    assert any("reproducible" in p for p in problems)
    assert bridge.delta == 1.0


def test_recalculation_bridge_valid() -> None:
    bridge = RecalculationBridge(
        from_methodology_version="v1",
        to_methodology_version="v2",
        reason="dataset upgrade",
        original_value=10.0,
        restated_value=11.0,
        original_result_reproducible=True,
        original_run_id="run-1",
    )
    ok, problems = bridge.is_valid()
    assert ok and problems == []


def test_claim_scan_flags_prohibited_outside_context() -> None:
    result = scan_text("This pack is CMB compliant and CMB approved.", file="x.md")
    assert not result.ok
    phrases = {f.phrase for f in result.findings}
    assert "cmb compliant" in phrases


def test_claim_scan_allows_prohibited_in_table_or_quote() -> None:
    table = "| Prohibited | CMB compliant |"
    assert scan_text(table, file="x.md").ok

    quote = '> The guideline text uses the words "CMB approved" verbatim here.'
    assert scan_text(quote, file="x.md").ok

    fenced = "```\nCMB compliant\n```"
    assert scan_text(fenced, file="x.md").ok


def test_claim_scan_flags_prediction_of_actual_loss() -> None:
    result = scan_text("GeoRisk gives a prediction of actual loss.", file="x.md")
    assert not result.ok


def test_claim_scan_flags_prohibited_in_json_value() -> None:
    # JSON string values are double-quoted; the quotes must NOT exempt the line.
    body = '{\n  "objective": "CMB compliant",\n  "note": "ok"\n}'
    result = scan_text(body, file="project-register.json")
    assert not result.ok
    assert "cmb compliant" in {f.phrase for f in result.findings}


def test_claim_scan_unrelated_apostrophe_does_not_suppress_markdown() -> None:
    # An apostrophe elsewhere on the line must not clear a bare prohibited phrase.
    line = "The issuer's pack is CMB compliant."
    assert not scan_text(line, file="x.md").ok
