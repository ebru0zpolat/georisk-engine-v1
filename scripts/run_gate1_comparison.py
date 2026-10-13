#!/usr/bin/env python3
"""Run the Gate-1 model-vs-baseline comparison from a frozen pre-registration.

This is the runnable shell for Gate-1 criterion 1.4. It will refuse to produce a
result until (a) the pre-registration JSON is frozen and (b) a licensed
observed-loss provider is wired in. Until then it fails closed with a clear
message — by design, so no result is ever produced on synthetic/unlicensed data.

Usage::

    python3 scripts/run_gate1_comparison.py \
        --pre-registration path/to/frozen_pre_registration.json \
        [--out report.json]

Wiring a licensed dataset: implement an ``ObservedLossProvider`` (see
``app/validation/gate1/observed_loss.py``) that loads your licensed sample, and
replace ``UnlicensedObservedLossProvider`` below with it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.validation.gate1 import (
    ExpectedLossModelAdapter,
    ObservedLossDataUnavailable,
    PreRegistrationNotFrozen,
    UnlicensedObservedLossProvider,
    load_pre_registration,
    run_comparison,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pre-registration",
        required=True,
        help="Path to the frozen pre-registration JSON.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the JSON report (defaults to stdout).",
    )
    args = parser.parse_args(argv)

    pre_registration = load_pre_registration(args.pre_registration)

    # --- Provider seam -----------------------------------------------------
    # Replace this fail-closed default with a licensed ObservedLossProvider once
    # criterion 1.3 (data licence) is satisfied. The harness will not run
    # against synthetic or unlicensed data.
    observed_loss_provider = UnlicensedObservedLossProvider()
    # -----------------------------------------------------------------------

    model = ExpectedLossModelAdapter(
        information_cutoff=pre_registration.information_cutoff,
        hazard_type=pre_registration.hazard_type,
    )

    try:
        report = run_comparison(
            pre_registration=pre_registration,
            model=model,
            observed_loss_provider=observed_loss_provider,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except PreRegistrationNotFrozen as exc:
        print(f"[gate1] refusing to run: {exc}", file=sys.stderr)
        return 2
    except ObservedLossDataUnavailable as exc:
        print(f"[gate1] refusing to run: {exc}", file=sys.stderr)
        return 3

    payload = report.to_json()
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
        print(f"[gate1] wrote report to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
