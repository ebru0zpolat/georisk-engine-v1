from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.research.vera_rap import (
    AbstractionStatus,
    ArtifactRegistry,
    ContradictionStatus,
    EvidenceActionType,
    VerificationStatus,
    replay_trace,
)
from benchmarks.vera_rap.models import SystemCaseResult
from demonstrators.vera_rap_georisk import (
    DemonstratorAsset,
    DemonstratorOutcome,
    DemonstratorQuestion,
    GeoRiskEvidenceType,
    load_scenario,
    run_georisk_demonstrator,
    to_system_case_result,
)


def run(name, mutate=None):
    raw = load_scenario(name)
    if mutate:
        mutate(raw)
    q = raw["question"]
    q["evaluation_time"] = datetime.fromisoformat(
        q["evaluation_time"].replace("Z", "+00:00")
    )
    q["required_evidence_types"] = tuple(
        GeoRiskEvidenceType(x) for x in q["required_evidence_types"]
    )
    question = DemonstratorQuestion(**q)
    return run_georisk_demonstrator(
        DemonstratorAsset(**raw["asset"]),
        question,
        raw["evidence"],
        evaluation_time=question.evaluation_time,
    )


def actions(result):
    return {a.action_type for p in result.plans for a in p.actions}


def test_complete_flood_evidence_can_reach_materiality():
    r = run("flood_complete")
    assert r.final_outcome is DemonstratorOutcome.SUPPORTED
    assert not r.plans
    assert replay_trace(r.trace, ArtifactRegistry(r.trace.artifacts)).valid


def test_stale_elevation_blocks_materiality_and_plans_refresh():
    r = run("flood_stale_elevation")
    assert r.final_outcome is DemonstratorOutcome.REPLAN_REQUIRED
    assert EvidenceActionType.REFRESH_STALE_EVIDENCE in actions(r)


def test_conflicting_flood_sources_block_materiality():
    r = run("flood_conflicting_sources")
    assert r.contradictions[0].status is ContradictionStatus.UNRESOLVED
    assert all(
        x.status is not AbstractionStatus.VERIFIED
        for x in r.abstraction_verifications[-1:]
    )


def test_excessive_flood_uncertainty_blocks_progression():
    assert (
        run("flood_uncertain_depth").final_outcome is not DemonstratorOutcome.SUPPORTED
    )


def test_missing_provenance_cannot_support_materiality():
    assert any(
        e.verification_status is VerificationStatus.REJECTED
        for e in run("flood_missing_provenance").evidence_objects
    )


def test_invalid_crs_transformation_blocks_spatial_inference():
    assert (
        run("flood_invalid_transformation").final_outcome
        is not DemonstratorOutcome.SUPPORTED
    )


def test_constraint_failure_blocks_even_with_sufficient_evidence():
    assert run("flood_constraint_blocked").final_outcome is DemonstratorOutcome.BLOCKED


def test_replanning_can_unlock_materiality_after_new_evidence():
    old = run("flood_replanning_required")
    new = run("flood_complete")
    assert (
        old.final_outcome is DemonstratorOutcome.REPLAN_REQUIRED
        and new.final_outcome is DemonstratorOutcome.SUPPORTED
    )
    assert old.final_outcome is DemonstratorOutcome.REPLAN_REQUIRED


def test_elevation_alone_is_insufficient_for_flood_materiality():
    def m(x):
        x["evidence"] = [
            e
            for e in x["evidence"]
            if e["evidence_type"]
            in {"ASSET_LOCATION", "GROUND_ELEVATION", "CRS_TRANSFORMATION"}
        ]

    assert run("flood_complete", m).final_outcome is not DemonstratorOutcome.SUPPORTED


def test_evidence_for_other_asset_cannot_support_target():
    def m(x):
        for e in x["evidence"]:
            if e["evidence_type"] == "FLOOD_DEPTH":
                e["spatial_scope"]["asset_id"] = "other"

    assert run("flood_complete", m).final_outcome is not DemonstratorOutcome.SUPPORTED


def test_climate_scenario_mismatch_is_detected():
    def m(x):
        x["evidence"][2]["content"]["scenario"] = "SSP5-8.5"

    assert "COMPATIBLE_CLIMATE_SCENARIO" in run("flood_complete", m).blockers


def test_return_period_mismatch_is_not_silently_accepted():
    def m(x):
        x["evidence"][2]["content"]["return_period_years"] = 10

    assert "COMPATIBLE_RETURN_PERIOD" in run("flood_complete", m).blockers


def test_duplicate_upstream_provenance_does_not_create_independence():
    def m(x):
        duplicate = deepcopy(x["evidence"][2])
        duplicate["evidence_id"] = "depth-copy"
        duplicate["provenance"]["upstream_evidence_ids"] = ["same-model-run"]
        x["evidence"][2]["provenance"]["upstream_evidence_ids"] = ["same-model-run"]
        x["evidence"].append(duplicate)

    r = run("flood_complete", m)
    assert (
        r.evidence_objects[2].provenance.upstream_evidence_ids
        == r.evidence_objects[-1].provenance.upstream_evidence_ids
    )


def test_georisk_demonstrator_is_deterministic():
    a, b = run("flood_complete"), run("flood_complete")
    assert a.fingerprint == b.fingerprint and a.trace.fingerprint == b.trace.fingerprint


def test_georisk_demonstrator_is_evidenceboundbench_compatible():
    assert isinstance(to_system_case_result(run("flood_complete")), SystemCaseResult)


def test_historical_supported_state_is_not_rewritten_when_evidence_stales():
    old = run("flood_complete")
    later = run("flood_stale_elevation")
    assert (
        old.final_outcome is DemonstratorOutcome.SUPPORTED
        and later.final_outcome is not old.final_outcome
    )


def test_models_are_immutable():
    r = run("flood_complete")
    with pytest.raises(FrozenInstanceError):
        r.asset.asset_id = "x"
