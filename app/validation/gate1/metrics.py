"""Error metrics for model-vs-baseline comparison.

Each metric maps aligned ``(predicted, observed)`` sequences to a single
non-negative error, where lower is better. The primary metric is named in the
frozen pre-registration and computed identically for model and baseline.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Callable

Metric = Callable[[Sequence[float], Sequence[float]], float]


def _check_aligned(predicted: Sequence[float], observed: Sequence[float]) -> None:
    if len(predicted) != len(observed):
        raise ValueError(
            f"predicted/observed length mismatch: {len(predicted)} vs {len(observed)}"
        )
    if not predicted:
        raise ValueError("cannot compute a metric over an empty sample")


def mae(predicted: Sequence[float], observed: Sequence[float]) -> float:
    """Mean absolute error."""
    _check_aligned(predicted, observed)
    return sum(abs(p - o) for p, o in zip(predicted, observed)) / len(predicted)


def rmse(predicted: Sequence[float], observed: Sequence[float]) -> float:
    """Root mean squared error."""
    _check_aligned(predicted, observed)
    mse = sum((p - o) ** 2 for p, o in zip(predicted, observed)) / len(predicted)
    return math.sqrt(mse)


METRIC_REGISTRY: dict[str, Metric] = {
    "mae": mae,
    "rmse": rmse,
}


def get_metric(name: str) -> Metric:
    """Return a metric by name, or raise with the available names."""
    try:
        return METRIC_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown metric {name!r}; available: {sorted(METRIC_REGISTRY)}"
        ) from exc


def list_metrics() -> list[str]:
    return sorted(METRIC_REGISTRY)
