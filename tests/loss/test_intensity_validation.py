"""Invalid intensities must never produce a number."""

from __future__ import annotations

import math

import pytest

from app.loss.expected_loss import HazardScenarioIntensities


@pytest.mark.parametrize(
    "bad",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.01,
        1.01,
    ],
)
def test_non_finite_or_out_of_range_intensity_raises(bad: float) -> None:
    with pytest.raises(ValueError):
        HazardScenarioIntensities(
            current={"flood": bad},
            horizon_2030={"flood": 0.1},
            horizon_2050={"flood": 0.2},
        )


def test_valid_finite_unit_interval_accepted() -> None:
    hz = HazardScenarioIntensities(
        current={"flood": 0.0, "extreme_heat": 1.0},
        horizon_2030={"flood": 0.5},
        horizon_2050={"flood": 0.75},
    )
    assert all(math.isfinite(v) for v in hz.current.values())
