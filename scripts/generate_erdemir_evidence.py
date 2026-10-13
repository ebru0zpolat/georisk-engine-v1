"""Regenerate the Erdemir validation evidence trail (JSON + audit summary markdown).

Outputs:
- ``data/evidence/erdemir_2024_evidence.json``
- ``data/evidence/erdemir_2024_evidence.md``

A **fixed** ``generated_at`` keeps the committed files stable across regenerations;
override with ``--generated-at`` for an ad-hoc run.

Usage::

    PYTHONPATH=. python scripts/generate_erdemir_evidence.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.services.validation_service import ValidationService

# Deterministic timestamp so committed artefacts stay stable across regenerations.
_FIXED_GENERATED_AT = datetime.fromisoformat("2025-05-03T00:00:00+00:00")


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate Erdemir validation evidence files.")
    parser.add_argument(
        "--generated-at",
        type=datetime.fromisoformat,
        default=_FIXED_GENERATED_AT,
        help="ISO-8601 timestamp stamped onto records (default: fixed 2025-05-03).",
    )
    args = parser.parse_args()

    service = ValidationService()
    trail = service.build_erdemir_trail(generated_at=args.generated_at)
    json_path = service.export_trail_json(trail)
    md_path = service.export_summary_markdown(trail)
    print(json_path.resolve())
    print(md_path.resolve())


if __name__ == "__main__":
    main()
