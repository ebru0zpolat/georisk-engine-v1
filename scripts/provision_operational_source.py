#!/usr/bin/env python3
"""Provision a credentialed data source toward ``data_source_operational``.

The single, validated operator command for populating the four controls the
``data_source_operational`` gate requires — "as keys become available" (roadmap
P2). It does **not** fabricate any control; it reports what is present, what is
missing, and the exact next action, and (with ``--capture``) drives the real
connector to record live evidence when credentials are configured.

What it does:
  1. Validates ``config/data_source_operational.json`` against the registry ids
     (a typo'd source_id fails loud here, not as a silent permanent fail-closed).
  2. Prints each source's four-control checklist with the next action per gap.
  3. ``--capture``: for a live-configured source, performs one real connector
     fetch and appends a fingerprinted LiveRuntimeEvidence record.
  4. Prints the resulting gate verdict.

Usage:
    PYTHONPATH=. python scripts/provision_operational_source.py [--source oras5_ocean]
    PYTHONPATH=. python scripts/provision_operational_source.py --source oras5_ocean --capture \
        [--lat 52.37 --lon 4.90]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.data_source_operational_records import (  # noqa: E402
    CAPTURABLE_PLANES,
    OperationalRecordsStore,
    append_evidence,
    capture_live_evidence,
    validate_operational_config,
)
from app.core.data_source_registry import list_data_sources  # noqa: E402
from app.core.data_source_validation import delivery_mode_for  # noqa: E402

# Delivery planes with a credentialed connector, shown in the checklist. Not all
# are *capturable*: audit sources (gee_audit) are listed but never fetched here —
# their dataset is not what GeeConnector returns (see CAPTURABLE_PLANES).
_CREDENTIALED = {"cds_zarr", "gee", "gee_audit"}


def _fetch(delivery: str, lat: float, lon: float):
    """Drive the real connector for a *capturable* delivery plane.

    Only planes in ``CAPTURABLE_PLANES`` are wired: their connector genuinely
    fetches that source's own dataset, so the payload is valid evidence for it.
    ``gee_audit`` is excluded — routing it through ``GeeConnector`` would
    fingerprint the production VIIRS/S5P payload, not the audit dataset.
    """
    if delivery == "cds_zarr":
        from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest

        return CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=lat, longitude=lon))
    if delivery == "gee":
        from app.connectors.gee import GeeConnector, GeePointRequest

        return GeeConnector().fetch_features(GeePointRequest(latitude=lat, longitude=lon))
    raise ValueError(
        f"delivery plane {delivery!r} is not capturable via the generic seam "
        f"(capturable: {sorted(CAPTURABLE_PLANES)})"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", help="Only this source_id (else all credentialed sources).")
    ap.add_argument("--capture", action="store_true", help="Capture live evidence if delivery is live.")
    ap.add_argument("--lat", type=float, default=52.37)
    ap.add_argument("--lon", type=float, default=4.90)
    args = ap.parse_args()

    entries = [e for e in list_data_sources() if e.delivery in _CREDENTIALED]
    known_ids = {e.id for e in list_data_sources()}
    if args.source:
        entries = [e for e in entries if e.id == args.source]
        if not entries:
            print(f"No credentialed source with id {args.source!r}.", file=sys.stderr)
            return 2

    # 1) Config validation — fail loud before anything else.
    issues = validate_operational_config(known_source_ids=known_ids)
    if issues:
        print("Config problems in config/data_source_operational.json:")
        for issue in issues:
            print(f"  ✗ {issue}")
        print("Fix these before provisioning — an invalid record fails closed silently.")
        return 1

    as_of = date.today()
    store = OperationalRecordsStore()
    delivery_by_source = {e.id: (e.delivery, delivery_mode_for(e)) for e in entries}

    # 2) Optional capture (only affects live-configured sources).
    if args.capture:
        for e in entries:
            mode = delivery_mode_for(e)
            if mode != "live":
                continue
            if e.delivery not in CAPTURABLE_PLANES:
                # e.g. gee_audit: not fetched by the generic connector — never
                # append a fingerprint of the wrong dataset as this source's evidence.
                print(f"  {e.id}: skip capture — {e.delivery} needs its dedicated "
                      "audit connector (generic seam would fingerprint the wrong dataset)")
                continue
            try:
                payload = _fetch(e.delivery, args.lat, args.lon)
                ev = capture_live_evidence(
                    source_id=e.id, payload=payload,
                    request_ref=f"{e.delivery}:{args.lat},{args.lon}", delivery_mode="live",
                )
                append_evidence(ev)
                print(f"  captured live evidence for {e.id}: sha256={ev.sample_sha256[:16]}…")
            except Exception as exc:  # noqa: BLE001 — report per source, keep going
                print(f"  {e.id}: live capture FAILED: {exc}", file=sys.stderr)
        store = OperationalRecordsStore()  # reload evidence log

    # 3) Per-source checklist.
    statuses = store.provisioning(delivery_by_source, as_of=as_of)
    print("=" * 84)
    print("  data_source_operational — provisioning checklist")
    print("-" * 84)
    ready = 0
    for e in entries:
        st = statuses[e.id]
        ready += int(st.operational)
        mark = "OPERATIONAL" if st.operational else "not operational"
        print(f"\n  {e.id}  [{st.delivery_plane}, delivery={st.delivery_mode}]  → {mark}")
        for c in st.controls:
            tick = "✓" if c.ok else "✗"
            print(f"    {tick} {c.name}")
            if not c.ok:
                print(f"        → {c.next_action}")
    print("-" * 84)
    print(f"  operational: {ready} of {len(entries)} credentialed source(s)")
    if not ready:
        print("  No source is operational yet — the honest state until real records land.")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
