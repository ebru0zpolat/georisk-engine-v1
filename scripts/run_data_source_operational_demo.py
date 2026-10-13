#!/usr/bin/env python3
"""Show data_source_operational verdicts over the real registry.

Runs the fail-closed gate against every registered data source. In an
environment with no credentials/licence/evidence/retention records (this one),
**every source reads not-operational** — the honest state. The gate names, per
source, exactly which of the four controls (live delivery, licence, live-runtime
evidence, retention) is missing.

Usage:
    PYTHONPATH=. python scripts/run_data_source_operational_demo.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.data_source_operational_gate import (  # noqa: E402
    LicenceRecord,
    LiveRuntimeEvidence,
    RetentionPolicy,
    evaluate_data_source_operational,
)
from app.core.data_source_operational_records import OperationalRecordsStore  # noqa: E402
from app.core.data_source_registry import list_data_sources  # noqa: E402
from app.core.data_source_validation import delivery_mode_for  # noqa: E402


def main() -> int:
    entries = list_data_sources()
    delivery = {e.id: delivery_mode_for(e) for e in entries}
    as_of = date.today()

    # Verdicts come from the real records store (licence/retention config +
    # captured live-evidence log). Empty records → fail-closed, the honest state.
    verdicts = OperationalRecordsStore().verdicts(delivery, as_of=as_of)

    print("=" * 84)
    print("  data_source_operational — live registry (no records configured in this env)")
    print("-" * 84)
    print(f"{'source_id':<22}{'delivery':<10}{'operational':<13}first blocking reason")
    op_count = 0
    for e in entries:
        v = verdicts[e.id]
        op_count += int(v.operational)
        reason = v.reasons[0] if v.reasons else "—"
        print(f"{e.id:<22}{v.delivery_mode:<10}{str(v.operational):<13}{reason[:38]}")
    print("-" * 84)
    print(f"  operational: {op_count} of {len(entries)}  (data_source_operational gate = "
          f"{'PASS' if op_count == len(entries) else 'FALSE'})")

    # Illustrative FIXTURE: what a fully-operational source needs (labelled).
    print("-" * 84)
    print("  FIXTURE — what one operational source looks like (not real records):")
    sid = entries[0].id
    fix = evaluate_data_source_operational(
        source_id=sid, delivery_mode="live",
        licence=LicenceRecord(sid, "fixture-licence", "Provider", True, date(2026, 1, 1), date(2027, 1, 1)),
        live_evidence=[LiveRuntimeEvidence(sid, as_of, "fixture-req", "f" * 64, "live")],
        retention=RetentionPolicy(sid, 365, "s3://fixture"),
        as_of=as_of,
    )
    print(f"    {sid}: operational={fix.operational}  "
          f"(licence={fix.licence_ok} evidence={fix.live_evidence_ok} retention={fix.retention_ok})")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
