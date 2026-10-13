"""Tests for the model_validated_for_use_case readiness gate + v0.4 adapter."""

from __future__ import annotations

from datetime import date

import pytest

from app.loss.depth_damage_curves import load_depth_damage_catalogue
from app.validation.gate1.model_adapter import ExpectedLossModelAdapter
from app.validation.gate1.model_validation_gate import (
    ReviewerAttestation,
    ValidationTier,
    evaluate_model_validation,
)
from app.validation.gate1.observed_loss import SampleUnit
from app.validation.gate1.report import ComparisonReport

_HASH = "a" * 64


def _report(
    *, passed: bool = True, dataset: str = "nfip-2021-licensed",
    config_hash: str = _HASH, dataset_is_synthetic: bool = False,
):
    return ComparisonReport(
        study_title="NL flood EAL vs NFIP 2021",
        pre_registration={"study_title": "NL flood EAL vs NFIP 2021", "hazard_type": "flood"},
        observed_loss_dataset=dataset,
        model_name="expected-loss-v0.4-depth",
        baseline_name="value_fraction",
        metric_name="mae",
        n_units=50,
        model_metric=1000.0,
        baseline_metric=1500.0,
        relative_improvement=0.333,
        success_rule="model error <= baseline error reduced by >= 15%",
        passed=passed,
        config_hash=config_hash,
        generated_at="2026-01-01T00:00:00Z",
        dataset_is_synthetic=dataset_is_synthetic,
    )


def _reviewer(**kw):
    base = dict(
        reviewer_id="rev-1", reviewer_org="TU-Delft-Hydraulics",
        attested_config_hash=_HASH, decision="approve", signed_at="2026-01-02T00:00:00Z",
    )
    base.update(kw)
    return ReviewerAttestation(**base)


# ---- the gate ----

def test_validated_true_when_all_conditions_met():
    # Default minimum tier is self_attested; an independent-org reviewer clears it
    # and reaches the higher tier.
    v = evaluate_model_validation(report=_report(), reviewer=_reviewer())
    assert v.validated is True
    assert v.tier == "independent"
    assert v.reasons == []
    assert v.hazard_type == "flood"
    assert v.reviewer_id == "rev-1"


def test_self_attestation_validates_at_mvp_default():
    # MVP: a self-org (founder) attestation validates at the self_attested tier.
    v = evaluate_model_validation(report=_report(), reviewer=_reviewer(reviewer_org="georisk-engine"))
    assert v.validated is True
    assert v.tier == "self_attested"


def test_self_attestation_below_independent_minimum():
    v = evaluate_model_validation(
        report=_report(),
        reviewer=_reviewer(reviewer_org="georisk-engine"),
        minimum_tier=ValidationTier.INDEPENDENT,
    )
    assert v.validated is False
    assert v.tier == "self_attested"
    assert any("below the required minimum" in r for r in v.reasons)


def test_not_validated_when_comparison_failed():
    v = evaluate_model_validation(report=_report(passed=False), reviewer=_reviewer())
    assert v.validated is False
    assert any("success rule" in r for r in v.reasons)


def test_not_validated_when_dataset_synthetic():
    v = evaluate_model_validation(
        report=_report(dataset="synthetic-mechanics-fixture"), reviewer=_reviewer()
    )
    assert v.validated is False
    assert any("synthetic" in r for r in v.reasons)


def test_not_validated_when_provenance_not_real():
    # A non-denylisted name but synthetic provenance still cannot validate.
    v = evaluate_model_validation(
        report=_report(dataset="synthetic-backtest-v2", dataset_is_synthetic=True),
        reviewer=_reviewer(),
    )
    assert v.validated is False
    assert any("provenance is not affirmatively real" in r for r in v.reasons)


def test_not_validated_when_reviewer_org_empty():
    v = evaluate_model_validation(report=_report(), reviewer=_reviewer(reviewer_org="  "))
    assert v.validated is False
    assert any("empty reviewer_org" in r for r in v.reasons)


def test_not_validated_when_no_reviewer():
    v = evaluate_model_validation(report=_report(), reviewer=None)
    assert v.validated is False
    assert v.tier is None
    assert any("no reviewer attestation" in r for r in v.reasons)


def test_not_validated_when_reviewer_rejects():
    v = evaluate_model_validation(report=_report(), reviewer=_reviewer(decision="reject"))
    assert v.validated is False
    assert any("not 'approve'" in r for r in v.reasons)


def test_not_validated_when_config_hash_mismatch():
    v = evaluate_model_validation(
        report=_report(), reviewer=_reviewer(attested_config_hash="b" * 64)
    )
    assert v.validated is False
    assert any("binds to config_hash" in r for r in v.reasons)


def test_reasons_accumulate():
    v = evaluate_model_validation(
        report=_report(passed=False, dataset="synthetic-mechanics-fixture"),
        reviewer=None,
    )
    assert v.validated is False
    assert len(v.reasons) >= 3


def test_verdict_serialises():
    d = evaluate_model_validation(report=_report(), reviewer=_reviewer()).to_dict()
    assert d["validated"] is True
    assert d["tier"] == "independent"
    assert d["minimum_tier"] == "self_attested"
    assert d["use_case"] == "NL flood EAL vs NFIP 2021"


# ---- v0.4 adapter ----

def _unit(depths=None):
    return SampleUnit(
        unit_id="U1", observed_loss=50000.0,
        observation_date=date(2021, 7, 15), features_as_of=date(2021, 7, 1),
        features={
            "asset": {"asset_id": "U1", "asset_value": 1_000_000.0,
                      "building_type": "office", "use_class": "commercial",
                      "fragility_factor": 0.6},
            "hazards": {"current": {"flood": 0.9}},
            **({"depths": depths} if depths is not None else {}),
        },
    )


def test_adapter_v04_uses_depth_catalogue():
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="flood", depth_catalogue=cat
    )
    assert adapter.name.startswith("expected-loss-v0.4-depth")
    v04 = adapter.predict(_unit(depths={"flood": 3.0}))
    v03 = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="flood"
    ).predict(_unit())
    assert v04 > 0 and v03 > 0
    assert v04 != v03  # depth curve differs from intensity power curve


def test_adapter_v04_requires_depths():
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="flood", depth_catalogue=cat
    )
    with pytest.raises(ValueError, match="missing features.depths"):
        adapter.predict(_unit(depths=None))


def test_adapter_v04_requires_registered_hazard_depth():
    # depths present but missing the registered hazard → must raise, not silently
    # fall back to the v0.3 curve while claiming the v0.4-depth model.
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="flood", depth_catalogue=cat
    )
    with pytest.raises(ValueError, match="missing the registered study hazard"):
        adapter.predict(_unit(depths={"other": 3.0}))


def test_adapter_depth_catalogue_flood_only():
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    with pytest.raises(ValueError, match="only valid for a flood study"):
        ExpectedLossModelAdapter(
            information_cutoff=date(2021, 7, 1), hazard_type="heat", depth_catalogue=cat
        )


def test_adapter_v04_name_binds_catalogue_identity():
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="flood", depth_catalogue=cat
    )
    assert "jrc_depth_damage_fixture" in adapter.name and "v0.1" in adapter.name
