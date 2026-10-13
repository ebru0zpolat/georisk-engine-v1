"""Gate-1 comparison harness — shell behaviour and guards.

These tests exercise the harness *structure* with in-memory fakes. They do NOT
constitute a validation result: no licensed observed-loss data is involved. The
one test that touches the real model uses an explicitly synthetic feature dict
to prove the adapter wiring, not to validate the model.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.validation.gate1 import (
    ComparisonReport,
    ExpectedLossModelAdapter,
    LookaheadError,
    ObservedLossDataUnavailable,
    PreRegistration,
    PreRegistrationNotFrozen,
    SampleUnit,
    UnlicensedObservedLossProvider,
    freeze_pre_registration,
    list_baselines,
    list_metrics,
    load_pre_registration,
    run_comparison,
)
from app.validation.gate1.baselines import (
    historical_coverage_ratio,
    prior_mean,
    value_fraction,
    zero_loss,
)
from app.validation.gate1.metrics import mae, rmse
from app.validation.gate1.pre_registration import SuccessRule

CUTOFF = date(2019, 6, 30)
_TS = "2026-08-13T00:00:00+00:00"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeModel:
    """Predicts the value stashed under features['pred']."""

    name = "fake-model"

    def predict(self, unit: SampleUnit) -> float:
        return float(unit.features["pred"])


class _LicensedFakeProvider:
    """In-memory provider that claims a licence — for structural tests only."""

    name = "fake-licensed-dataset"
    is_synthetic = True  # a test fake is never real data (contract field)

    def __init__(self, units: list[SampleUnit]) -> None:
        self._units = units

    def is_licensed_for_commercial_use(self) -> bool:
        return True

    def load(self, pre_registration: object) -> list[SampleUnit]:  # noqa: ARG002
        return list(self._units)


def _unit(uid: str, observed: float, pred: float, as_of: date = CUTOFF) -> SampleUnit:
    return SampleUnit(
        unit_id=uid,
        observed_loss=observed,
        observation_date=date(2019, 7, 15),
        features_as_of=as_of,
        features={"pred": pred},
    )


def _prereg(
    *,
    frozen: bool = True,
    baseline_name: str = "zero_loss",
    baseline_params: dict | None = None,
    metric: str = "rmse",
    rule: SuccessRule | None = None,
) -> PreRegistration:
    prereg = PreRegistration(
        study_title="unit-test-study",
        hazard_type="heat",
        information_cutoff=CUTOFF,
        observed_loss_dataset="fake-licensed-dataset",
        baseline_name=baseline_name,
        baseline_params=baseline_params or {},
        primary_metric=metric,
        success_rule=rule
        or SuccessRule(type="relative_improvement", min_fraction=0.15),
        frozen=False,
    )
    if frozen:
        return freeze_pre_registration(
            prereg, timestamp="2026-08-13T00:00:00Z", commit="deadbeef"
        )
    return prereg


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_mae_and_rmse_values() -> None:
    predicted = [1.0, 2.0, 3.0]
    observed = [1.0, 4.0, 3.0]  # errors: 0, 2, 0
    assert mae(predicted, observed) == pytest.approx(2.0 / 3.0)
    assert rmse(predicted, observed) == pytest.approx((4.0 / 3.0) ** 0.5)


def test_metric_requires_aligned_nonempty() -> None:
    with pytest.raises(ValueError):
        mae([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        rmse([], [])


def test_registries_expose_names() -> None:
    assert "rmse" in list_metrics() and "mae" in list_metrics()
    assert {
        "zero_loss",
        "prior_mean",
        "value_fraction",
        "historical_coverage_ratio",
    } <= set(list_baselines())


# --------------------------------------------------------------------------- #
# Baselines (cutoff-safe, param-driven)
# --------------------------------------------------------------------------- #
def test_baselines_use_preregistered_params() -> None:
    unit = SampleUnit(
        unit_id="a",
        observed_loss=100.0,
        observation_date=date(2019, 7, 1),
        features_as_of=CUTOFF,
        features={"asset": {"asset_value": 1_000_000.0}},
    )
    assert zero_loss(unit, {}) == 0.0
    assert prior_mean(unit, {"mean_loss": 12345.0}) == 12345.0
    assert value_fraction(unit, {"fraction": 0.02}) == pytest.approx(20_000.0)


def test_value_fraction_rejects_bad_params() -> None:
    unit = SampleUnit(
        unit_id="a",
        observed_loss=1.0,
        observation_date=CUTOFF,
        features_as_of=CUTOFF,
        features={"asset": {"asset_value": 100.0}},
    )
    with pytest.raises(ValueError):
        value_fraction(unit, {"fraction": 1.5})
    with pytest.raises(ValueError):
        prior_mean(unit, {})


def test_historical_baseline_requires_frozen_source_hash() -> None:
    unit = SampleUnit(
        unit_id="claim-a",
        observed_loss=1.0,
        observation_date=CUTOFF,
        features_as_of=CUTOFF,
        features={"total_building_insurance_coverage": 100_000.0},
    )
    params = {"loss_to_coverage_ratio": 0.03, "source_sha256": "a" * 64}
    assert historical_coverage_ratio(unit, params) == pytest.approx(3_000.0)
    with pytest.raises(ValueError, match="source_sha256"):
        historical_coverage_ratio(unit, {**params, "source_sha256": "unfrozen"})


# --------------------------------------------------------------------------- #
# Guard rails
# --------------------------------------------------------------------------- #
def test_refuses_unfrozen_pre_registration() -> None:
    provider = _LicensedFakeProvider([_unit("a", 100.0, 100.0)])
    with pytest.raises(PreRegistrationNotFrozen):
        run_comparison(
            pre_registration=_prereg(frozen=False),
            model=_FakeModel(),
            observed_loss_provider=provider,
            generated_at=_TS,
        )


def test_frozen_flag_needs_timestamp_and_commit() -> None:
    prereg = PreRegistration(
        study_title="s",
        hazard_type="heat",
        information_cutoff=CUTOFF,
        observed_loss_dataset="d",
        baseline_name="zero_loss",
        baseline_params={},
        primary_metric="rmse",
        success_rule=SuccessRule(type="absolute_threshold", max_value=1.0),
        frozen=True,
        freeze_timestamp=None,
        freeze_commit=None,
    )
    with pytest.raises(PreRegistrationNotFrozen):
        prereg.require_frozen()


def test_scientific_payload_tampering_invalidates_freeze() -> None:
    prereg = _prereg()
    object.__setattr__(prereg, "primary_metric", "mae")
    with pytest.raises(PreRegistrationNotFrozen, match="changed"):
        prereg.require_frozen()


def test_freeze_rejects_unset_baseline_parameter() -> None:
    prereg = _prereg(frozen=False, baseline_params={"ratio": None})
    with pytest.raises(ValueError, match="must be fixed"):
        freeze_pre_registration(prereg, timestamp=_TS, commit="a" * 40)


def test_fail_closed_on_unlicensed_provider() -> None:
    with pytest.raises(ObservedLossDataUnavailable):
        run_comparison(
            pre_registration=_prereg(),
            model=_FakeModel(),
            observed_loss_provider=UnlicensedObservedLossProvider(),
            generated_at=_TS,
        )


def test_lookahead_unit_is_rejected() -> None:
    units = [
        _unit("a", 100.0, 100.0, as_of=CUTOFF),
        _unit("b", 200.0, 200.0, as_of=date(2019, 12, 31)),  # past cutoff
    ]
    with pytest.raises(LookaheadError):
        run_comparison(
            pre_registration=_prereg(),
            model=_FakeModel(),
            observed_loss_provider=_LicensedFakeProvider(units),
            generated_at=_TS,
        )


def test_empty_sample_is_rejected() -> None:
    with pytest.raises(ValueError):
        run_comparison(
            pre_registration=_prereg(),
            model=_FakeModel(),
            observed_loss_provider=_LicensedFakeProvider([]),
            generated_at=_TS,
        )


# --------------------------------------------------------------------------- #
# End-to-end pass / fail decisions
# --------------------------------------------------------------------------- #
def test_perfect_model_beats_zero_baseline() -> None:
    units = [_unit("a", 100.0, 100.0), _unit("b", 200.0, 200.0)]
    report = run_comparison(
        pre_registration=_prereg(baseline_name="zero_loss"),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert isinstance(report, ComparisonReport)
    assert report.model_metric == pytest.approx(0.0)
    assert report.baseline_metric > 0.0
    assert report.relative_improvement == pytest.approx(1.0)
    assert report.passed is True
    assert report.n_units == 2


def test_model_no_better_than_baseline_fails_rule() -> None:
    # Model predicts 0 too — identical to the zero baseline → no improvement.
    units = [_unit("a", 100.0, 0.0), _unit("b", 200.0, 0.0)]
    report = run_comparison(
        pre_registration=_prereg(baseline_name="zero_loss"),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert report.model_metric == pytest.approx(report.baseline_metric)
    assert report.relative_improvement == pytest.approx(0.0)
    assert report.passed is False


def test_absolute_threshold_rule() -> None:
    units = [_unit("a", 100.0, 105.0), _unit("b", 200.0, 195.0)]  # rmse = 5.0
    report = run_comparison(
        pre_registration=_prereg(
            rule=SuccessRule(type="absolute_threshold", max_value=10.0)
        ),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert report.model_metric == pytest.approx(5.0)
    assert report.passed is True


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_report_config_hash_is_deterministic() -> None:
    units = [_unit("a", 100.0, 90.0), _unit("b", 200.0, 210.0)]
    kwargs = dict(
        pre_registration=_prereg(),
        model=_FakeModel(),
        generated_at=_TS,
    )
    r1 = run_comparison(observed_loss_provider=_LicensedFakeProvider(units), **kwargs)
    r2 = run_comparison(observed_loss_provider=_LicensedFakeProvider(units), **kwargs)
    assert r1.config_hash == r2.config_hash
    assert r1.to_json() == r2.to_json()


# --------------------------------------------------------------------------- #
# Pre-registration file loading
# --------------------------------------------------------------------------- #
def test_example_pre_registration_loads_and_is_unfrozen() -> None:
    example = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "validation"
        / "gate1"
        / "pre_registration.example.json"
    )
    prereg = load_pre_registration(example)
    assert prereg.frozen is False
    with pytest.raises(PreRegistrationNotFrozen):
        prereg.require_frozen()


# --------------------------------------------------------------------------- #
# Real-model adapter wiring (synthetic input — NOT a validation result)
# --------------------------------------------------------------------------- #
def test_expected_loss_adapter_predicts_and_blocks_lookahead() -> None:
    adapter = ExpectedLossModelAdapter(information_cutoff=date(2021, 7, 1))
    unit = SampleUnit(
        unit_id="EL-01",
        observed_loss=0.0,  # unused by the adapter
        observation_date=date(2021, 7, 15),
        features_as_of=date(2021, 7, 1),
        features={
            "asset": {
                "asset_id": "EL-01",
                "asset_value": 2_000_000.0,
                "building_type": "hotel",
                "use_class": "tourism",
                "fragility_factor": 0.55,
                "adaptation_capacity_factor": 0.08,
                "insurance_coverage": 500_000,
            },
            "hazards": {"current": {"flood": 0.6, "extreme_heat": 0.48}},
        },
    )
    predicted = adapter.predict(unit)
    assert predicted > 0.0

    ahead = SampleUnit(
        unit_id="EL-02",
        observed_loss=0.0,
        observation_date=date(2021, 8, 1),
        features_as_of=date(2021, 8, 1),  # past the adapter cutoff
        features=unit.features,
    )
    with pytest.raises(ValueError):
        adapter.predict(ahead)


# --------------------------------------------------------------------------- #
# Success-rule integrity and dataset binding (Bugbot fixes)
# --------------------------------------------------------------------------- #
def test_unknown_success_rule_type_is_rejected() -> None:
    # A typo or unknown rule from JSON must not be silently accepted and then
    # decided under the wrong (absolute-threshold) path.
    with pytest.raises(ValueError):
        SuccessRule(type="realtive_improvement", min_fraction=0.15)  # typo


def test_provider_dataset_must_match_pre_registration() -> None:
    units = [_unit("a", 100.0, 100.0), _unit("b", 200.0, 200.0)]
    prereg = _prereg()  # observed_loss_dataset == "fake-licensed-dataset"

    class _WrongDatasetProvider(_LicensedFakeProvider):
        name = "some-other-dataset"

    with pytest.raises(ValueError):
        run_comparison(
            pre_registration=prereg,
            model=_FakeModel(),
            observed_loss_provider=_WrongDatasetProvider(units),
            generated_at=_TS,
        )


def test_relative_rule_does_not_pass_on_zero_baseline_tie() -> None:
    # Baseline error is zero (perfect) and model also predicts perfectly: the
    # relative rule is undefined and a tie is not a pass under Gate 1.
    units = [_unit("a", 0.0, 0.0), _unit("b", 0.0, 0.0)]
    report = run_comparison(
        pre_registration=_prereg(baseline_name="zero_loss"),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert report.baseline_metric == pytest.approx(0.0)
    assert report.model_metric == pytest.approx(0.0)
    assert report.passed is False


# --------------------------------------------------------------------------- #
# Strict baseline win + baseline binding + hazard restriction (Codex fixes)
# --------------------------------------------------------------------------- #
def test_absolute_threshold_requires_beating_baseline() -> None:
    # Model clears the absolute ceiling (err 2 <= 5) but is WORSE than the
    # zero_loss baseline (err 1). Gate 1 must fail it: a tie or loss is a fail.
    units = [_unit("a", 1.0, 3.0)]  # model err 2, baseline(zero) err 1
    report = run_comparison(
        pre_registration=_prereg(
            rule=SuccessRule(type="absolute_threshold", max_value=5.0)
        ),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert report.model_metric == pytest.approx(2.0)
    assert report.baseline_metric == pytest.approx(1.0)
    assert report.passed is False


def test_relative_rule_zero_fraction_tie_fails() -> None:
    # min_fraction == 0 with model == baseline is a tie; Gate 1 fails ties.
    units = [_unit("a", 100.0, 0.0), _unit("b", 200.0, 0.0)]
    report = run_comparison(
        pre_registration=_prereg(
            rule=SuccessRule(type="relative_improvement", min_fraction=0.0)
        ),
        model=_FakeModel(),
        observed_loss_provider=_LicensedFakeProvider(units),
        generated_at=_TS,
    )
    assert report.model_metric == pytest.approx(report.baseline_metric)
    assert report.passed is False


def test_baseline_is_not_injectable() -> None:
    # The executed baseline must always come from the frozen pre-registration,
    # so run_comparison exposes no baseline override to masquerade one.
    import inspect

    assert "baseline" not in inspect.signature(run_comparison).parameters


def test_adapter_rejects_off_study_hazard() -> None:
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="heat"
    )
    unit = SampleUnit(
        unit_id="H-1",
        observed_loss=0.0,
        observation_date=date(2021, 7, 15),
        features_as_of=date(2021, 7, 1),
        features={
            "asset": {
                "asset_id": "H-1",
                "asset_value": 2_000_000.0,
                "building_type": "hotel",
                "use_class": "tourism",
            },
            "hazards": {"current": {"flood": 0.6, "extreme_heat": 0.48}},
        },
    )
    with pytest.raises(ValueError, match="off-study"):
        adapter.predict(unit)


def test_adapter_requires_registered_hazard_present() -> None:
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="heat"
    )
    unit = SampleUnit(
        unit_id="H-2",
        observed_loss=0.0,
        observation_date=date(2021, 7, 15),
        features_as_of=date(2021, 7, 1),
        features={
            "asset": {
                "asset_id": "H-2",
                "asset_value": 2_000_000.0,
                "building_type": "hotel",
                "use_class": "tourism",
            },
            "hazards": {"current": {"flood": 0.6}},  # heat study, no heat hazard
        },
    )
    with pytest.raises(ValueError):
        adapter.predict(unit)


def test_adapter_scores_registered_hazard_only() -> None:
    adapter = ExpectedLossModelAdapter(
        information_cutoff=date(2021, 7, 1), hazard_type="heat"
    )
    unit = SampleUnit(
        unit_id="H-3",
        observed_loss=0.0,
        observation_date=date(2021, 7, 15),
        features_as_of=date(2021, 7, 1),
        features={
            "asset": {
                "asset_id": "H-3",
                "asset_value": 2_000_000.0,
                "building_type": "hotel",
                "use_class": "tourism",
            },
            "hazards": {"current": {"extreme_heat": 0.48}},
        },
    )
    assert adapter.predict(unit) >= 0.0
