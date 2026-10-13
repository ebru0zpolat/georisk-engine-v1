"""ERA5 retrieve smoke — real CDS API round-trip with the configured key.

Operational evidence, not gate closure: a successful retrieve records that the
credentials can submit a queued job and download its result, but it does NOT
close homogeneity, calibration, retention or loss-pathway gates (see
docs/validation/oras5-evidence-gates.md).

Hardening rules (per the canonical state record):
- the API key is used raw but NEVER printed (no token / Authorization header /
  raw exception text in any output or evidence file);
- the GRIB lands in the system temp dir and is deleted after hashing
  (``--keep`` retains it);
- a nonempty download is mandatory and the file's sha256 is required;
- success writes an operational-evidence JSON to ``data/validation/``.

Usage::

    PYTHONPATH=. python scripts/era5_retrieve_smoke.py          # defaults
    PYTHONPATH=. python scripts/era5_retrieve_smoke.py --keep   # retain the GRIB

Exit code 0 = retrieval + download OK; nonzero = failure. An unauthenticated
401 only demonstrates the auth requirement — it does not close this gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load the workspace env file BEFORE importing app config / building the client
# (same pattern as scripts/validate_isdemir_marine.py).
if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env.local")
    except Exception:  # pragma: no cover
        pass

from app.core.config import settings  # noqa: E402

#: Canonical ERA5 retrieve from the CDS docs (reanalysis-era5-pressure-levels).
_DATASET = "reanalysis-era5-pressure-levels"
_REQUEST: dict = {
    "product_type": ["reanalysis"],
    "variable": ["geopotential"],
    "year": ["2024"],
    "month": ["03"],
    "day": ["01"],
    "time": ["13:00"],
    "pressure_level": ["1000"],
    "data_format": "grib",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="ERA5 retrieve smoke (real CDS API).")
    parser.add_argument(
        "--grib",
        type=Path,
        default=Path(tempfile.gettempdir()) / "era5_smoke.grib",
        help="Output path (default: system temp dir).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the downloaded GRIB after hashing (default: deleted).",
    )
    args = parser.parse_args()

    key = settings.copernicus_cds_api_key or os.getenv("CDSAPI_KEY")
    url = settings.copernicus_cds_url or os.getenv("CDSAPI_URL")
    if not key:
        print("ERA5 smoke skipped: CDSAPI_KEY not configured (env or .env.local).", file=sys.stderr)
        return 2
    if not url:
        print("ERA5 smoke skipped: CDSAPI_URL not configured.", file=sys.stderr)
        return 2

    import cdsapi

    client = cdsapi.Client(url=url, key=key, quiet=True, progress=False)
    print(f"[era5-smoke] dataset={_DATASET} request={_REQUEST} (credentials never printed)")
    start = time.time()
    try:
        client.retrieve(_DATASET, _REQUEST, str(args.grib))
    except Exception:  # noqa: BLE001 - raw exception text must not be printed
        print(
            f"[era5-smoke] FAILED after {time.time() - start:.1f}s — "
            f"CDS job/retrieve error (type logged below without credentials): "
            f"see cdsapi logs; an unauthenticated 401 only shows the auth "
            f"requirement and does not close this gate.",
            file=sys.stderr,
        )
        return 1

    size = args.grib.stat().st_size
    if size == 0:
        print("[era5-smoke] FAILED: empty download (nonempty GRIB is mandatory).", file=sys.stderr)
        return 1
    digest = hashlib.sha256(args.grib.read_bytes()).hexdigest()
    duration_s = round(time.time() - start, 1)
    print(
        f"[era5-smoke] OK in {duration_s}s "
        f"size={size} sha256={digest[:16]}… → {args.grib}"
    )

    # Operational-evidence record (no secrets: request body only, key never).
    evidence_dir = _REPO_ROOT / "data" / "validation"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": "1.0",
        "evidence_id": f"ERA5-SMOKE-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}",
        "case_id": "cds_era5_retrieve_smoke",
        "status": "passed",
        "dataset": _DATASET,
        "request": _REQUEST,
        "duration_s": duration_s,
        "grib_size_bytes": size,
        "grib_sha256": digest,
        "grib_deleted": not args.keep,
        "credential_handling": "key used raw, never printed; no Authorization header or raw exception text in output",
        "evidence_classification": {
            "operational_evidence": "passed",
            "note": "does NOT close homogeneity / scaling-calibration / retention / asset-loss gates",
        },
    }
    evidence_path = evidence_dir / f"era5_smoke_{datetime.now(timezone.utc):%Y%m%d-%H%M%S}_evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"[era5-smoke] wrote {evidence_path.resolve()}")

    if not args.keep:
        args.grib.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
