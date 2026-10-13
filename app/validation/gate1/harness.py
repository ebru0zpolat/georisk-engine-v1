"""Gate-1 comparison orchestrator (criterion 1.4).

``run_comparison`` is the single entry point. It enforces, in order:

1. the pre-registration is frozen (criterion 1.2);
2. the observed-loss provider holds a commercial-use licence (criterion 1.3);
3. the sample is non-empty and every unit respects the information cutoff
   (no lookahead — the leakage guard for a fair comparison);
4. model and baseline predict on the *same* units;
5. the primary metric is computed for both, and the pre-registered success rule
   decides pass/fail.

The result is a deterministic :class:`ComparisonReport`.
"""

from __future__ import annotations

from typing import Protocol

from app.validation.gate1.baselines import get_baseline
from app.validation.gate1.metrics import get_metric
from app.validation.gate1.observed_loss import (
    ObservedLossDataUnavailable,
    ObservedLossProvider,
    SampleUnit,
)
from app.validation.gate1.pre_registration import PreRegistration
from app.validation.gate1.report import ComparisonReport, compute_config_hash


class LookaheadError(RuntimeError):
    """Raised when a sample unit's features look ahead of the study cutoff."""


class Predictor(Protocol):
    """A model with a stable name that predicts absolute loss per unit."""

    @property
    def name(self) -> str: ...

    def predict(self, unit: SampleUnit) -> float: ...


def _evaluate_success(
    pre_registration: PreRegistration,
    model_metric: float,
    baseline_metric: float,
) -> tuple[bool, float | None]:
    """Apply the frozen success rule. Returns (passed, relative_improvement)."""
    rule = pre_registration.success_rule
    relative_improvement: float | None = None
    if baseline_metric > 0.0:
        relative_improvement = (baseline_metric - model_metric) / baseline_metric

    # Gate 1 requires the model to *strictly* beat the baseline — a tie or a
    # loss fails — regardless of which success rule is configured. The rule's
    # threshold is an additional bar on top of this, never a substitute for it.
    beats_baseline = model_metric < baseline_metric

    if rule.type == "relative_improvement":
        if baseline_metric <= 0.0:
            # Baseline error is zero (already perfect) or degenerate: a
            # >=min_fraction relative improvement is undefined and unachievable,
            # and a tie is not a pass. Fail closed rather than pass on a
            # collapsed threshold.
            return False, relative_improvement
        threshold = baseline_metric * (1.0 - (rule.min_fraction or 0.0))
        return (beats_baseline and model_metric <= threshold), relative_improvement
    if rule.type == "absolute_threshold":
        # Must clear the pre-stated ceiling AND still beat the baseline; a model
        # under max_value but no better than the baseline does not pass Gate 1.
        passed = beats_baseline and model_metric <= (rule.max_value or 0.0)
        return passed, relative_improvement
    raise ValueError(f"unknown success_rule type {rule.type!r}")


def run_comparison(
    *,
    pre_registration: PreRegistration,
    model: Predictor,
    observed_loss_provider: ObservedLossProvider,
    generated_at: str,
    include_unit_ids: bool = True,
) -> ComparisonReport:
    """Run one model-vs-baseline comparison and return a report.

    Args:
        pre_registration: Frozen study parameters. Must pass ``require_frozen``.
        model: The model under test (e.g. :class:`ExpectedLossModelAdapter`).
        observed_loss_provider: Supplies the licensed sample; a fail-closed
            default will raise :class:`ObservedLossDataUnavailable`.
        generated_at: Caller-supplied ISO-8601 timestamp for the report (kept as
            a parameter so the report stays deterministic and testable).
        include_unit_ids: Whether to record unit ids in the report.

    The baseline is never injectable: it is always resolved from the frozen
    ``pre_registration.baseline_name`` via the registry, so the executed
    comparator cannot diverge from the one the report and config hash name.

    Raises:
        PreRegistrationNotFrozen: pre-registration is not frozen.
        ObservedLossDataUnavailable: provider has no licensed data.
        LookaheadError: a unit's ``features_as_of`` is past the cutoff, or it carries
            event-conditioning hazard the preregistration does not admit.
        ValueError: empty sample or provider/pre-registration mismatch.
    """
    # 1. Freeze guard (criterion 1.2).
    pre_registration.require_frozen()

    # 2. Licence guard (criterion 1.3).
    if not observed_loss_provider.is_licensed_for_commercial_use():
        raise ObservedLossDataUnavailable(
            f"observed-loss provider {observed_loss_provider.name!r} does not "
            "hold a commercial-use licence; Gate-1 criterion 1.3 is not met."
        )

    # 2b. Dataset guard: the provider must be the dataset named in the frozen
    # pre-registration. Otherwise the report would attribute a pass/fail to a
    # dataset the study was never registered against (criterion 1.2).
    if observed_loss_provider.name != pre_registration.observed_loss_dataset:
        raise ValueError(
            f"observed-loss provider {observed_loss_provider.name!r} does not "
            f"match the pre-registered dataset "
            f"{pre_registration.observed_loss_dataset!r}; the frozen study is "
            "bound to a specific dataset and may not be scored on another."
        )

    units = list(observed_loss_provider.load(pre_registration))
    if not units:
        raise ValueError("observed-loss provider returned an empty sample")

    # 3. Cutoff guard: no unit's PRE-EVENT information may look ahead of the cutoff.
    #    This guard is absolute and is not weakened for any study. Post-event
    #    observed hazard is a separate typed field, checked in step 3b against the
    #    preregistration's registered hazard contract, so the exception can never be
    #    reached by relabelling a post-cutoff predictor as pre-event information.
    cutoff = pre_registration.information_cutoff
    lookahead = [u.unit_id for u in units if u.features_as_of > cutoff]
    if lookahead:
        raise LookaheadError(
            f"{len(lookahead)} unit(s) have features_as_of past the information "
            f"cutoff {cutoff.isoformat()}: {lookahead[:5]}"
            + (" ..." if len(lookahead) > 5 else "")
        )

    # 3b. Event-conditioning guard (P1-07). A unit may carry observed-event hazard
    #     only when the frozen study registered that exact source/artifact/window and
    #     selected the source before any outcome was read. Fail closed: no
    #     registration, or any mismatch, is a refusal, never a downgrade.
    registration = pre_registration.event_conditioning
    hazard_units = [u for u in units if u.event_conditioning_hazard is not None]
    if hazard_units:
        if registration is None:
            raise LookaheadError(
                f"{len(hazard_units)} unit(s) carry observed-event hazard evidence "
                f"({', '.join(u.unit_id for u in hazard_units[:5])}"
                + (", ..." if len(hazard_units) > 5 else "")
                + f") but the frozen study registers no event-conditioning hazard "
                "contract; post-cutoff hazard may not enter a study that did not "
                "preregister it"
            )
        refusals: list[str] = []
        for unit in hazard_units:
            hazard = unit.event_conditioning_hazard
            assert hazard is not None  # guarded by the comprehension above
            reason = registration.admits(
                source_id=hazard.source_id,
                artifact_sha256=hazard.artifact_sha256,
                observed_at=hazard.observed_at,
            )
            if reason is not None:
                refusals.append(f"{unit.unit_id}: {reason}")
        if refusals:
            raise LookaheadError(
                f"{len(refusals)} unit(s) carry event-conditioning hazard that the "
                f"preregistration does not admit: {refusals[:5]}"
                + (" ..." if len(refusals) > 5 else "")
            )

    baseline_fn = get_baseline(pre_registration.baseline_name)
    metric_fn = get_metric(pre_registration.primary_metric)

    # 4. Both predictors see the identical sample, in identical order.
    observed = [u.observed_loss for u in units]
    model_preds = [model.predict(u) for u in units]
    baseline_preds = [baseline_fn(u, pre_registration.baseline_params) for u in units]

    # 5. Metric + pre-registered success rule.
    model_metric = metric_fn(model_preds, observed)
    baseline_metric = metric_fn(baseline_preds, observed)
    passed, relative_improvement = _evaluate_success(
        pre_registration, model_metric, baseline_metric
    )

    unit_ids = [u.unit_id for u in units]
    config_hash = compute_config_hash(
        pre_registration=pre_registration.summary(),
        model_name=model.name,
        baseline_name=pre_registration.baseline_name,
        metric_name=pre_registration.primary_metric,
        unit_ids=unit_ids,
    )

    return ComparisonReport(
        study_title=pre_registration.study_title,
        pre_registration=pre_registration.summary(),
        observed_loss_dataset=observed_loss_provider.name,
        model_name=model.name,
        baseline_name=pre_registration.baseline_name,
        metric_name=pre_registration.primary_metric,
        n_units=len(units),
        model_metric=model_metric,
        baseline_metric=baseline_metric,
        relative_improvement=relative_improvement,
        success_rule=pre_registration.success_rule.describe(),
        passed=passed,
        config_hash=config_hash,
        generated_at=generated_at,
        # Fail-closed provenance: a provider must affirmatively assert real data
        # (is_synthetic=False). Absent/unknown → treated as synthetic, so the
        # validation gate cannot be satisfied on unverified provenance.
        dataset_is_synthetic=bool(getattr(observed_loss_provider, "is_synthetic", True)),
        unit_ids=unit_ids if include_unit_ids else [],
    )
