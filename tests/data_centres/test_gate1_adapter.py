"""Data-centre backtests must call the shared Gate-1 harness."""

from __future__ import annotations

from datetime import date

import pytest

from app.data_centres.gate1 import GATE1_HARNESS, run_data_centre_backtest
from app.validation.gate1 import (
    ObservedLossDataUnavailable,
    PreRegistration,
    freeze_pre_registration,
    run_comparison,
)
from app.validation.gate1.pre_registration import SuccessRule


class _NoopModel:
    name = "dc-noop"

    def predict(self, unit: object) -> float:
        return 0.0


def test_adapter_names_the_shared_harness() -> None:
    assert GATE1_HARNESS == "app.validation.gate1.run_comparison"
    assert run_comparison.__module__ == "app.validation.gate1.harness"


def test_adapter_delegates_to_shared_run_comparison() -> None:
    """A licensed structural fake must still go through Gate-1, not a local loop."""
    from app.validation.gate1.observed_loss import SampleUnit
    from app.validation.gate1.pre_registration import SuccessRule

    cutoff = date(2019, 6, 30)
    units = [
        SampleUnit(
            unit_id="dc-a",
            observed_loss=1.0,
            observation_date=date(2019, 7, 15),
            features_as_of=cutoff,
            features={},
        )
    ]

    class _Licensed:
        name = "fake-licensed-dataset"

        def is_licensed_for_commercial_use(self) -> bool:
            return True

        def load(self, pre_registration: object) -> list[SampleUnit]:
            return list(units)

    pre_registration = freeze_pre_registration(
        PreRegistration(
            study_title="data-centre gate-1 adapter",
            hazard_type="heat",
            information_cutoff=cutoff,
            observed_loss_dataset="fake-licensed-dataset",
            baseline_name="zero_loss",
            baseline_params={},
            primary_metric="mae",
            success_rule=SuccessRule(type="relative_improvement", min_fraction=0.1),
            frozen=False,
        ),
        timestamp="2026-08-15T00:00:00+00:00",
        commit="a" * 40,
    )
    generated_at = "2026-08-15T00:00:00+00:00"
    via_adapter = run_data_centre_backtest(
        pre_registration=pre_registration,
        model=_NoopModel(),
        generated_at=generated_at,
        observed_loss_provider=_Licensed(),
    )
    via_harness = run_comparison(
        pre_registration=pre_registration,
        model=_NoopModel(),
        observed_loss_provider=_Licensed(),
        generated_at=generated_at,
    )
    assert via_adapter.config_hash == via_harness.config_hash
    assert via_adapter.model_name == via_harness.model_name
    assert via_adapter.baseline_name == via_harness.baseline_name


def test_unconfigured_data_centre_backtest_fails_closed() -> None:
    pre_registration = freeze_pre_registration(
        PreRegistration(
            study_title="data-centre gate-1 adapter",
            hazard_type="heat",
            information_cutoff=date(2019, 6, 30),
            observed_loss_dataset="unlicensed",
            baseline_name="zero_loss",
            baseline_params={},
            primary_metric="mae",
            success_rule=SuccessRule(type="relative_improvement", min_fraction=0.1),
            frozen=False,
        ),
        timestamp="2026-08-15T00:00:00+00:00",
        commit="a" * 40,
    )
    with pytest.raises(ObservedLossDataUnavailable):
        run_data_centre_backtest(
            pre_registration=pre_registration,
            model=_NoopModel(),
            generated_at="2026-08-15T00:00:00+00:00",
        )
