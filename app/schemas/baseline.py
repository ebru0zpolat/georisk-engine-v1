"""Date windows and validators for current vs baseline comparison."""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, model_validator


class BaselineComparison(BaseModel):
    current_mean: float
    baseline_mean: float
    absolute_change: float
    percent_change: float
    z_score: float


def baseline_comparison_from_means(
    current: float,
    baseline: float,
    *,
    baseline_epsilon: float,
    z_score: float = 0.0,
) -> BaselineComparison:
    abs_ch = current - baseline
    denom = max(abs(baseline), baseline_epsilon)
    pct = (abs_ch / denom) * 100.0
    return BaselineComparison(
        current_mean=current,
        baseline_mean=baseline,
        absolute_change=abs_ch,
        percent_change=pct,
        z_score=z_score,
    )


class BaselinePeriod(BaseModel):
    """Reference period used to compare against a current observation window."""

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def end_on_or_after_start(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


def optional_paired_dates_or_none(
    start: date | None,
    end: date | None,
    *,
    label: str,
) -> None:
    """Require both bounds or neither (e.g. baseline_start_date / baseline_end_date)."""
    if (start is None) != (end is None):
        raise ValueError(
            f"{label}_start_date and {label}_end_date must both be set, or both omitted"
        )
