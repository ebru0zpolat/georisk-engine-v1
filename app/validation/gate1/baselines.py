"""Named naive baselines (criterion 1.4).

The baseline is chosen in the frozen pre-registration and must be defensible as
a *naive* comparator. Every baseline here is **cutoff-safe**: its parameters
come from the pre-registration (``baseline_params``), never fit on the
evaluation targets. Fitting a baseline on the observed losses it is scored
against would leak and void the gate.

A baseline maps a :class:`SampleUnit` plus pre-registered params to a predicted
loss (absolute, study currency).
"""

from __future__ import annotations

from typing import Any, Callable

from app.validation.gate1.observed_loss import SampleUnit

Baseline = Callable[[SampleUnit, dict[str, Any]], float]


def zero_loss(unit: SampleUnit, params: dict[str, Any]) -> float:  # noqa: ARG001
    """Predict zero loss everywhere — the trivial null comparator."""
    return 0.0


def prior_mean(unit: SampleUnit, params: dict[str, Any]) -> float:  # noqa: ARG001
    """Predict a single pre-registered prior mean loss for every unit.

    ``params["mean_loss"]`` must be a fixed value declared before results exist
    (e.g. a historical sector-average loss). It is *not* the mean of the
    evaluation sample.
    """
    try:
        value = float(params["mean_loss"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "prior_mean baseline requires numeric baseline_params.mean_loss"
        ) from exc
    if value < 0.0:
        raise ValueError("prior_mean baseline_params.mean_loss must be >= 0")
    return value


def value_fraction(unit: SampleUnit, params: dict[str, Any]) -> float:
    """Predict a pre-registered fraction of the unit's asset value.

    A simple hazard-agnostic rule: ``fraction * asset_value``. The fraction is
    pre-registered; ``asset_value`` is read from the unit's features. This is a
    common, defensible naive comparator for loss models.
    """
    try:
        fraction = float(params["fraction"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "value_fraction baseline requires numeric baseline_params.fraction"
        ) from exc
    if not (0.0 <= fraction <= 1.0):
        raise ValueError("value_fraction baseline_params.fraction must be in [0, 1]")

    asset = unit.features.get("asset", {})
    try:
        asset_value = float(asset["asset_value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"value_fraction baseline needs features.asset.asset_value on unit "
            f"{unit.unit_id!r}"
        ) from exc
    return fraction * asset_value


def historical_coverage_ratio(unit: SampleUnit, params: dict[str, Any]) -> float:
    """Apply a loss ratio fitted only on a hashed pre-event historical sample."""
    try:
        ratio = float(params["loss_to_coverage_ratio"])
        source_sha256 = str(params["source_sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "historical_coverage_ratio requires loss_to_coverage_ratio and source_sha256"
        ) from exc
    if not (0.0 <= ratio <= 1.0):
        raise ValueError("loss_to_coverage_ratio must be in [0, 1]")
    if not _is_sha256(source_sha256):
        raise ValueError("source_sha256 must be a 64-character lowercase hex digest")
    try:
        coverage = float(unit.features["total_building_insurance_coverage"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "historical_coverage_ratio needs total_building_insurance_coverage "
            f"on unit {unit.unit_id!r}"
        ) from exc
    return ratio * coverage


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


BASELINE_REGISTRY: dict[str, Baseline] = {
    "zero_loss": zero_loss,
    "prior_mean": prior_mean,
    "value_fraction": value_fraction,
    "historical_coverage_ratio": historical_coverage_ratio,
}


def get_baseline(name: str) -> Baseline:
    """Return a baseline by name, or raise with the available names."""
    try:
        return BASELINE_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown baseline {name!r}; available: {sorted(BASELINE_REGISTRY)}"
        ) from exc


def list_baselines() -> list[str]:
    return sorted(BASELINE_REGISTRY)
