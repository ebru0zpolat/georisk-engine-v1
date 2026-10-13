"""Gate 1 — Scientific validation harness (shell).

Implements exit criterion **1.4** of the six-month validation gates: evaluate
the model and a *named* naive baseline on the *same* sample under the *same*
information cutoff, and report the result against a pre-registered success rule.

Design principles (mirrors the gate's anti-patterns, which void the gate):

- **Fail-closed on data.** Observed-loss data must come from a provider that
  asserts a commercial-use licence (criterion 1.3). The default provider raises
  :class:`ObservedLossDataUnavailable` so the harness can never silently run on
  synthetic or unlicensed data.
- **Freeze before results.** The harness refuses to run against a
  :class:`PreRegistration` that is not frozen (criterion 1.2). The baseline,
  metric, cutoff and success rule are read from the frozen pre-registration —
  never chosen after seeing results.
- **One cutoff for both.** Model and baseline receive the *same* sample units,
  and every unit's ``features_as_of`` must be on or before the pre-registered
  information cutoff. Lookahead raises, structurally guaranteeing no leakage.
- **Deterministic.** No randomness; identical inputs yield a byte-identical
  report (a config hash pins the inputs).

This is a *shell*: the seams (observed-loss provider, sample) are defined and
tested, but wiring a licensed dataset in is Gate-1 execution work that happens
after the pre-registration is frozen and the data licence lands.
"""

from __future__ import annotations

from app.validation.gate1.baselines import (
    BASELINE_REGISTRY,
    get_baseline,
    list_baselines,
)
from app.validation.gate1.harness import LookaheadError, run_comparison
from app.validation.gate1.metrics import METRIC_REGISTRY, get_metric, list_metrics
from app.validation.gate1.model_adapter import ExpectedLossModelAdapter
from app.validation.gate1.model_validation_gate import (
    SYNTHETIC_DATASET_NAMES,
    ModelValidationVerdict,
    ReviewerAttestation,
    ValidationTier,
    evaluate_model_validation,
)
from app.validation.gate1.observed_loss import (
    RETROSPECTIVE_EVENT_CONDITIONING,
    EventConditioningHazard,
    EventConditioningHazardInvalid,
    ObservedLossDataUnavailable,
    ObservedLossProvider,
    SampleUnit,
    UnlicensedObservedLossProvider,
)
from app.validation.gate1.pre_registration import (
    HARVEY_REQUIRED_STUDY_DECISIONS,
    EventConditioningRegistration,
    EventConditioningRegistrationInvalid,
    PreRegistration,
    PreRegistrationNotFrozen,
    freeze_pre_registration,
    load_pre_registration,
    verify_git_freeze,
)
from app.validation.gate1.report import ComparisonReport

__all__ = [
    "BASELINE_REGISTRY",
    "ComparisonReport",
    "EventConditioningHazard",
    "EventConditioningHazardInvalid",
    "EventConditioningRegistration",
    "EventConditioningRegistrationInvalid",
    "HARVEY_REQUIRED_STUDY_DECISIONS",
    "RETROSPECTIVE_EVENT_CONDITIONING",
    "ExpectedLossModelAdapter",
    "LookaheadError",
    "METRIC_REGISTRY",
    "ModelValidationVerdict",
    "ObservedLossDataUnavailable",
    "ObservedLossProvider",
    "PreRegistration",
    "PreRegistrationNotFrozen",
    "ReviewerAttestation",
    "SYNTHETIC_DATASET_NAMES",
    "SampleUnit",
    "ValidationTier",
    "UnlicensedObservedLossProvider",
    "evaluate_model_validation",
    "get_baseline",
    "freeze_pre_registration",
    "get_metric",
    "list_baselines",
    "list_metrics",
    "load_pre_registration",
    "run_comparison",
    "verify_git_freeze",
]
