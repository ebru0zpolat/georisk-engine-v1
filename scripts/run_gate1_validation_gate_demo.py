#!/usr/bin/env python3
"""Mechanics demo for the model_validated_for_use_case gate (GEO-105).

Proves the wiring end-to-end on a LABELLED SYNTHETIC event and shows the gate's
central property: **a comparison that mechanically PASSES is still NOT a
validation** without a licensed dataset and an independent reviewer sign-off.

Everything here is a fixture. The observed losses are set equal to the model's
own output (a self-fulfilling sample), so the comparison passes — and the gate
STILL returns validated=False, because the dataset is synthetic and (in the
second pass) a reviewer signature cannot rescue synthetic data. There is no
flag that turns this into a real validation result; that needs a real
preregistered study on licensed observed losses.

Usage:
    PYTHONPATH=. python scripts/run_gate1_validation_gate_demo.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.loss.depth_damage_curves import load_depth_damage_catalogue  # noqa: E402
from app.validation.gate1 import (  # noqa: E402
    ExpectedLossModelAdapter,
    PreRegistration,
    ReviewerAttestation,
    SampleUnit,
    evaluate_model_validation,
    run_comparison,
    freeze_pre_registration,
)
from app.validation.gate1.pre_registration import SuccessRule  # noqa: E402

_DATASET = "synthetic-mechanics-fixture"  # denylisted — can never validate
_CUTOFF = date(2021, 7, 1)


class _MechanicsFixtureProvider:
    """In-memory fixture provider. Licensed flag True only to exercise mechanics.

    NOT a licensed dataset. Its name is on the gate's synthetic denylist, so no
    verdict built on it can ever read validated=True.
    """

    is_synthetic = True  # provenance: never a real dataset

    def __init__(self, units: list[SampleUnit]) -> None:
        self._units = units

    @property
    def name(self) -> str:
        return _DATASET

    def is_licensed_for_commercial_use(self) -> bool:
        return True  # mechanics only — the gate still refuses via the denylist

    def load(self, pre_registration) -> list[SampleUnit]:  # noqa: ARG002
        return self._units


def _build_units(adapter: ExpectedLossModelAdapter) -> list[SampleUnit]:
    units: list[SampleUnit] = []
    for i, (value, depth) in enumerate(
        [(1e6, 3.0), (5e5, 1.5), (2e6, 0.3), (8e5, 4.4)]
    ):
        feats = {
            "asset": {
                "asset_id": f"U{i}",
                "asset_value": value,
                "building_type": "office",
                "use_class": "commercial",
                "fragility_factor": 0.6,
            },
            "hazards": {"current": {"flood": 0.9}},
            "depths": {"flood": depth},
        }
        probe = SampleUnit(f"U{i}", 0.0, date(2021, 7, 15), _CUTOFF, feats)
        # Self-fulfilling synthetic target: observed = model output.
        units.append(
            SampleUnit(
                f"U{i}", adapter.predict(probe), date(2021, 7, 15), _CUTOFF, feats
            )
        )
    return units


def main() -> int:
    cat = load_depth_damage_catalogue("jrc_depth_damage_fixture_v0.1.json")
    adapter = ExpectedLossModelAdapter(
        information_cutoff=_CUTOFF, hazard_type="flood", depth_catalogue=cat
    )
    prereg = freeze_pre_registration(
        PreRegistration(
            study_title="MECHANICS FIXTURE — flood depth EAL (NOT a validation)",
            hazard_type="flood",
            information_cutoff=_CUTOFF,
            observed_loss_dataset=_DATASET,
            baseline_name="value_fraction",
            baseline_params={"fraction": 0.5},
            primary_metric="mae",
            success_rule=SuccessRule(type="relative_improvement", min_fraction=0.15),
            frozen=False,
        ),
        timestamp="2026-01-01T00:00:00Z",
        commit="f" * 40,
    )
    provider = _MechanicsFixtureProvider(_build_units(adapter))
    report = run_comparison(
        pre_registration=prereg,
        model=adapter,
        observed_loss_provider=provider,
        generated_at="2026-01-01T00:00:00Z",
    )

    print("=" * 84)
    print("  ⚠  SYNTHETIC MECHANICS FIXTURE — NOT a validation result  ⚠")
    print("=" * 84)
    print(f"  comparison passed (beat baseline)?  {report.passed}")
    print(
        f"  model MAE={report.model_metric:,.1f}  baseline MAE={report.baseline_metric:,.1f}"
    )
    print(f"  config_hash: {report.config_hash[:16]}…")
    print("-" * 84)

    v1 = evaluate_model_validation(report=report, reviewer=None)
    print(
        f"  gate — no reviewer               → validated={v1.validated}  tier={v1.tier}"
    )
    for r in v1.reasons:
        print(f"      · {r}")

    founder = ReviewerAttestation(
        reviewer_id="founder",
        reviewer_org="georisk-engine",
        attested_config_hash=report.config_hash,
        decision="approve",
        signed_at="2026-01-02T00:00:00Z",
    )
    v2 = evaluate_model_validation(report=report, reviewer=founder)
    print(
        f"  gate — founder self-attestation  → validated={v2.validated}  tier={v2.tier}"
    )
    for r in v2.reasons:
        print(f"      · {r}")

    print("-" * 84)
    print("  Tiers: MVP validates at 'self_attested' (founder sign-off) — no external")
    print("  reviewer needed. But that requires a LICENSED observed-loss dataset; a")
    print(
        "  synthetic fixture (this run) can never validate at any tier. 'independent'"
    )
    print(
        "  is the higher tier unlocked later. model_validated_for_use_case stays FALSE here."
    )
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
