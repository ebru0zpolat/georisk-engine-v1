#!/usr/bin/env python3
"""Capture live-runtime evidence by driving the real data-source connectors.

For each registered source configured with **live** credentials (per
``delivery_mode_for``), this performs one real connector fetch and appends a
fingerprinted ``LiveRuntimeEvidence`` record to the operational evidence log.
That evidence is the third of the four controls the ``data_source_operational``
gate requires (licence + retention come from the config; delivery-live from
``delivery_mode_for``).

Honest by construction:
- Only ``live`` deliveries are recorded — a fallback/stub fetch is never evidence.
- No live-configured source (this sandbox: no credentials) → nothing captured,
  and the gate stays fail-closed. This is the correct outcome, not an error.

Run where the source credentials + egress exist:
    PYTHONPATH=. python scripts/capture_live_evidence.py \
        [--lat 52.37 --lon 4.90] [--source oras5_ocean]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.data_source_operational_records import (  # noqa: E402
    CAPTURABLE_PLANES,
    DEFAULT_EVIDENCE_LOG,
    append_evidence,
    capture_live_evidence,
)
from app.core.data_source_registry import list_data_sources  # noqa: E402
from app.core.data_source_validation import delivery_mode_for  # noqa: E402


def _fetch(source_id: str, delivery: str, lat: float, lon: float):
    """Drive the real connector for one *capturable* source's own dataset.

    Only ``CAPTURABLE_PLANES`` are wired. ``gee_audit`` is excluded: those audit
    datasets (Landsat thermal, S5P CO, VIIRS DNB monthly) are NOT what the
    production ``GeeConnector`` fetches — fingerprinting its output would fabricate
    provenance for a dataset never retrieved. Audit sources use their own pipeline.
    """
    if delivery == "cds_zarr":
        from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest

        return CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=lat, longitude=lon))
    if delivery == "gee":
        from app.connectors.gee import GeeConnector, GeePointRequest

        return GeeConnector().fetch_features(GeePointRequest(latitude=lat, longitude=lon))
    raise ValueError(
        f"delivery plane {delivery!r} (source {source_id}) is not capturable via "
        f"the generic seam (capturable: {sorted(CAPTURABLE_PLANES)})"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lat", type=float, default=52.37)
    ap.add_argument("--lon", type=float, default=4.90)
    ap.add_argument("--source", help="Only this source_id (else all live-configured).")
    args = ap.parse_args()

    entries = [e for e in list_data_sources() if e.delivery in CAPTURABLE_PLANES]
    if args.source:
        entries = [e for e in entries if e.id == args.source]

    captured = 0
    skipped = 0
    for e in entries:
        mode = delivery_mode_for(e)
        if mode != "live":
            print(f"  {e.id:<22} delivery={mode:<9} → skip (not live-configured)")
            skipped += 1
            continue
        try:
            payload = _fetch(e.id, e.delivery, args.lat, args.lon)
            ev = capture_live_evidence(
                source_id=e.id, payload=payload,
                request_ref=f"{e.delivery}:{args.lat},{args.lon}", delivery_mode="live",
            )
            append_evidence(ev)
            captured += 1
            print(f"  {e.id:<22} delivery=live      → captured sha256={ev.sample_sha256[:16]}…")
        except Exception as exc:  # noqa: BLE001 — report per source, keep going
            print(f"  {e.id:<22} delivery=live      → FETCH FAILED: {exc}", file=sys.stderr)

    print("-" * 60)
    if captured:
        print(f"Captured {captured} live-evidence record(s) → {DEFAULT_EVIDENCE_LOG.relative_to(_ROOT)}")
    else:
        print(
            "No live evidence captured (no live-configured source reachable). "
            "The data_source_operational gate stays fail-closed — the honest state."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
