"""Data-centre backtests call the shared Gate-1 harness — no second engine.

The merged Gate-1 comparison infrastructure (``app.validation.gate1``) is the
only allowed orchestrator. This module is a thin, fail-closed adapter:

- default observed-loss provider is the unlicensed Gate-1 provider;
- ``run_data_centre_backtest`` only calls ``run_comparison``;
- supplied ``BacktestEvidence`` must name this harness.
"""

from __future__ import annotations

from app.data_centres.contracts import BacktestEvidence
from app.validation.gate1 import (
    ComparisonReport,
    ObservedLossProvider,
    PreRegistration,
    UnlicensedObservedLossProvider,
    run_comparison,
)
from app.validation.gate1.harness import Predictor

GATE1_MODULE = "app.validation.gate1"
GATE1_ENTRYPOINT = "run_comparison"
GATE1_HARNESS = f"{GATE1_MODULE}.{GATE1_ENTRYPOINT}"


def harness_mismatch_reasons(backtest: BacktestEvidence) -> list[str]:
    """Reject evidence that claims a comparison outside the shared harness."""
    reasons: list[str] = []
    if backtest.harness_module != GATE1_MODULE:
        reasons.append(
            f"backtest harness_module must be {GATE1_MODULE}, not {backtest.harness_module}"
        )
    if backtest.harness_entrypoint != GATE1_ENTRYPOINT:
        reasons.append(
            "backtest harness_entrypoint must be run_comparison "
            f"(got {backtest.harness_entrypoint})"
        )
    return reasons


def run_data_centre_backtest(
    *,
    pre_registration: PreRegistration,
    model: Predictor,
    generated_at: str,
    observed_loss_provider: ObservedLossProvider | None = None,
    include_unit_ids: bool = True,
) -> ComparisonReport:
    """Execute a data-centre backtest exclusively via Gate-1 ``run_comparison``.

    Omitting ``observed_loss_provider`` uses ``UnlicensedObservedLossProvider``
    so an unconfigured study fails closed instead of inventing a local engine.
    """
    provider = observed_loss_provider or UnlicensedObservedLossProvider()
    return run_comparison(
        pre_registration=pre_registration,
        model=model,
        observed_loss_provider=provider,
        generated_at=generated_at,
        include_unit_ids=include_unit_ids,
    )
