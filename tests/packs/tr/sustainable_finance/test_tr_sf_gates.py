"""KPI admission gates and fail-closed release gates."""

from __future__ import annotations

import factories as f

from app.packs.tr.sustainable_finance.gates import (
    GateOutcome,
    evaluate_kpi_gates,
    evaluate_release_gates,
)
from app.packs.tr.sustainable_finance.routes import RegulatoryRoute


# --- KPI admission gates ---------------------------------------------------------------


def test_valid_kpi_passes_all_hard_gates() -> None:
    result = evaluate_kpi_gates(f.valid_kpi())
    assert result.reviewer_ready
    assert result.failed_gates() == []


def test_pure_external_hazard_kpi_rejected() -> None:
    kpi = f.valid_kpi().model_copy(update={"is_pure_external_hazard": True})
    result = evaluate_kpi_gates(kpi)
    assert not result.reviewer_ready
    assert "issuer_control" in result.failed_gates()


def test_kpi_without_measurement_definition_rejected() -> None:
    kpi = f.valid_kpi().model_copy(update={"numerator": None})
    result = evaluate_kpi_gates(kpi)
    assert "measurement" in result.failed_gates()


def test_kpi_without_recalculation_policy_rejected() -> None:
    kpi = f.valid_kpi().model_copy(update={"recalculation_policy": None})
    result = evaluate_kpi_gates(kpi)
    assert "data_and_model_stability" in result.failed_gates()


def test_kpi_missing_comparability_is_conditional_not_fatal() -> None:
    kpi = f.valid_kpi().model_copy(update={"external_benchmark": None})
    result = evaluate_kpi_gates(kpi)
    assert result.gates["comparability"] is GateOutcome.conditional
    assert result.reviewer_ready  # conditional does not block


def test_kpi_short_history_is_conditional() -> None:
    kpi = f.valid_kpi().model_copy(update={"history": []})
    result = evaluate_kpi_gates(kpi)
    assert result.gates["historical_evidence"] is GateOutcome.conditional
    assert result.reviewer_ready


def test_kpi_unknown_physical_risk_candidate_fails_closed() -> None:
    kpi = f.valid_kpi().model_copy(update={"physical_risk_candidate_id": "not_in_matrix"})
    result = evaluate_kpi_gates(kpi)
    assert "physical_risk_policy" in result.failed_gates()


def test_kpi_rejected_physical_risk_candidate_fails() -> None:
    kpi = f.valid_kpi().model_copy(
        update={"physical_risk_candidate_id": "external_hazard_intensity_reduction"}
    )
    result = evaluate_kpi_gates(kpi)
    assert "physical_risk_policy" in result.failed_gates()


def test_kpi_eal_as_trigger_fails_physical_risk_policy() -> None:
    kpi = f.valid_kpi().model_copy(
        update={
            "physical_risk_candidate_id": "modelled_eal_downtime_or_loss_reduction",
            "proposed_as_trigger": True,
        }
    )
    result = evaluate_kpi_gates(kpi)
    assert "physical_risk_policy" in result.failed_gates()


# --- Release gates: happy paths --------------------------------------------------------


def test_valid_uop_pack_passes_release_gates() -> None:
    result = evaluate_release_gates(f.valid_uop_pack())
    assert result.reviewer_ready, result.blocking_reasons


def test_valid_sll_pack_passes_release_gates() -> None:
    result = evaluate_release_gates(f.valid_sll_pack())
    assert result.reviewer_ready, result.blocking_reasons


# --- Release gates: fail-closed cases ---------------------------------------------------


def test_missing_cutoff_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.manifest.regulatory_cutoff_date = None
    result = evaluate_release_gates(pack)
    assert not result.reviewer_ready
    assert any("regulatory_cutoff_date" in r for r in result.blocking_reasons)


def test_missing_issuer_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.manifest.issuer_legal_name = "   "
    result = evaluate_release_gates(pack)
    assert any("issuer_legal_name" in r for r in result.blocking_reasons)


def test_unlabelled_synthetic_input_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].is_synthetic = True
    pack.provenance[0].labelled = False
    result = evaluate_release_gates(pack)
    assert any("unlabelled synthetic/fallback" in r for r in result.blocking_reasons)


def test_labelled_synthetic_still_reports_but_not_unlabelled() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].is_fallback = True
    pack.provenance[0].labelled = True
    result = evaluate_release_gates(pack)
    # Labelling clears the "unlabelled" block; nothing else about it fails here.
    assert not any("unlabelled" in r for r in result.blocking_reasons)


def test_missing_licence_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].licence = None
    result = evaluate_release_gates(pack)
    assert any("missing dataset licence" in r for r in result.blocking_reasons)


def test_missing_hashes_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].output_hash = None
    result = evaluate_release_gates(pack)
    assert any("missing source/calculation hashes" in r for r in result.blocking_reasons)


def test_forward_looking_without_scenario_source_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].forward_looking = True
    pack.provenance[0].scenario_source_real = False
    result = evaluate_release_gates(pack)
    assert any("real versioned scenario source" in r for r in result.blocking_reasons)


def test_forward_looking_with_real_scenario_source_ok() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].forward_looking = True
    pack.provenance[0].scenario_source_real = True
    result = evaluate_release_gates(pack)
    assert result.reviewer_ready, result.blocking_reasons


def test_manifest_run_id_without_provenance_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.manifest.analysis_run_ids = ["run-1", "run-missing"]
    result = evaluate_release_gates(pack)
    assert any("run-missing" in r and "not reproducible" in r for r in result.blocking_reasons)


def test_suppressed_uncertainty_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.uncertainty_and_limitations = "   "
    result = evaluate_release_gates(pack)
    assert any("uncertainty" in r for r in result.blocking_reasons)


def test_role_separation_violation_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.manifest.external_review_roles.verifier = "SPO Ltd"  # == SPO provider
    result = evaluate_release_gates(pack)
    assert any("review role separation" in r for r in result.blocking_reasons)


def test_uop_without_projects_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.projects = []
    result = evaluate_release_gates(pack)
    assert any("no project register" in r for r in result.blocking_reasons)


def test_uop_hazard_attribution_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.adaptation_evidence[0].attributes_hazard_reduction_to_issuer = True
    result = evaluate_release_gates(pack)
    assert any("hazard reduction wrongly attributed" in r for r in result.blocking_reasons)


def test_sll_without_kpis_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.kpis = []
    result = evaluate_release_gates(pack)
    assert any("no KPI register" in r for r in result.blocking_reasons)


def test_spt_missing_baseline_and_fallback_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.spts[0].starting_reference_value = None
    pack.spts[0].fallback_if_not_calculable = None
    result = evaluate_release_gates(pack)
    reasons = " ".join(result.blocking_reasons)
    assert "starting_reference_value" in reasons
    assert "fallback_if_not_calculable" in reasons


def test_spt_links_unknown_kpi_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.spts[0].linked_kpi_id = "KPI-does-not-exist"
    result = evaluate_release_gates(pack)
    assert any("unknown KPI" in r for r in result.blocking_reasons)


def test_kpi_gate_failure_propagates_to_release() -> None:
    pack = f.valid_sll_pack()
    pack.kpis[0].is_pure_external_hazard = True
    result = evaluate_release_gates(pack)
    assert any("fails admission gate" in r for r in result.blocking_reasons)
    assert pack.manifest.regulatory_route is RegulatoryRoute.sustainability_linked


def test_sll_without_spts_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.spts = []
    result = evaluate_release_gates(pack)
    assert any("no SPT register" in r for r in result.blocking_reasons)


def test_labelled_synthetic_backing_impact_number_blocks() -> None:
    # Labelling clears the honesty gate but a synthetic run must not back an external number.
    pack = f.valid_uop_pack()
    pack.provenance[0].is_synthetic = True
    pack.provenance[0].labelled = True
    result = evaluate_release_gates(pack)
    assert not result.reviewer_ready
    assert any("not usable for an external number" in r for r in result.blocking_reasons)


def test_impact_metric_referencing_missing_run_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.impact_metrics[0].evidence_run_id = "run-does-not-exist"
    result = evaluate_release_gates(pack)
    assert any("run-does-not-exist" in r for r in result.blocking_reasons)


def test_quantitative_impact_metric_without_run_blocks() -> None:
    pack = f.valid_uop_pack()
    pack.impact_metrics[0].evidence_run_id = None
    result = evaluate_release_gates(pack)
    assert any("no evidence_run_id" in r for r in result.blocking_reasons)


def test_missing_provenance_metadata_blocks() -> None:
    pack = f.valid_sll_pack()
    pack.provenance[0].source_checksum = None
    pack.provenance[0].retrieval_date = None
    result = evaluate_release_gates(pack)
    reasons = " ".join(result.blocking_reasons)
    assert "missing provenance field source_checksum" in reasons
    assert "missing provenance field retrieval_date" in reasons


def test_non_physical_kpi_used_as_trigger_is_not_blocked() -> None:
    # A KPI with no physical-risk candidate id is outside the physical-risk trigger policy;
    # proposing it as an instrument trigger must not block the release gate.
    pack = f.valid_sll_pack()
    pack.kpis[0].physical_risk_candidate_id = None
    pack.kpis[0].proposed_as_trigger = True
    result = evaluate_release_gates(pack)
    assert result.reviewer_ready, result.blocking_reasons


def test_physical_risk_eal_trigger_still_blocks_at_release() -> None:
    pack = f.valid_sll_pack()
    pack.kpis[0].physical_risk_candidate_id = "modelled_eal_downtime_or_loss_reduction"
    pack.kpis[0].proposed_as_trigger = True
    result = evaluate_release_gates(pack)
    assert not result.reviewer_ready
    assert any("trigger" in r for r in result.blocking_reasons)
