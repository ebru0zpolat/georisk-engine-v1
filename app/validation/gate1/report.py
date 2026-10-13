"""Deterministic comparison report.

The report pins the study inputs with a config hash so an identical run produces
an identical artefact. It is the machine record that feeds the pre-registration
template's post-freeze results log (§11).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ComparisonReport:
    """Result of one model-vs-baseline comparison under a frozen pre-registration."""

    study_title: str
    pre_registration: dict[str, Any]
    observed_loss_dataset: str
    model_name: str
    baseline_name: str
    metric_name: str
    n_units: int
    model_metric: float
    baseline_metric: float
    relative_improvement: float | None
    success_rule: str
    passed: bool
    config_hash: str
    generated_at: str
    # Fail-closed provenance: a report is presumed synthetic unless the producer
    # (the harness, from the provider) affirmatively marks the dataset real. The
    # validation gate treats a synthetic dataset as never-validatable.
    dataset_is_synthetic: bool = True
    unit_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_title": self.study_title,
            "pre_registration": self.pre_registration,
            "observed_loss_dataset": self.observed_loss_dataset,
            "model_name": self.model_name,
            "baseline_name": self.baseline_name,
            "metric_name": self.metric_name,
            "n_units": self.n_units,
            "model_metric": self.model_metric,
            "baseline_metric": self.baseline_metric,
            "relative_improvement": self.relative_improvement,
            "success_rule": self.success_rule,
            "passed": self.passed,
            "config_hash": self.config_hash,
            "generated_at": self.generated_at,
            "dataset_is_synthetic": self.dataset_is_synthetic,
            "unit_ids": list(self.unit_ids),
            "notes": list(self.notes),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def compute_config_hash(
    *,
    pre_registration: dict[str, Any],
    model_name: str,
    baseline_name: str,
    metric_name: str,
    unit_ids: list[str],
) -> str:
    """SHA-256 over the study configuration and sample identity.

    Two runs with the same frozen pre-registration, model, baseline, metric and
    sample share a hash — a reproducibility anchor for auditors.
    """
    payload = json.dumps(
        {
            "pre_registration": pre_registration,
            "model_name": model_name,
            "baseline_name": baseline_name,
            "metric_name": metric_name,
            "unit_ids": sorted(unit_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
