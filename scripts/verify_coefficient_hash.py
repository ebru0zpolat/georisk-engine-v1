#!/usr/bin/env python3
"""CI merge-blocking: coefficient JSON must match manifest hash."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "app" / "scoring" / "data"
COEFF_FILE = DATA_DIR / "scenario_coefficients_v1.json"
MANIFEST_FILE = DATA_DIR / "scenario_coefficients_v1.manifest.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not COEFF_FILE.is_file():
        print(f"Missing {COEFF_FILE}", file=sys.stderr)
        return 1
    if not MANIFEST_FILE.is_file():
        print(f"Missing {MANIFEST_FILE}", file=sys.stderr)
        return 1

    actual = sha256_file(COEFF_FILE)
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    expected = str(manifest["coefficient_table_hash"])

    if actual != expected:
        print(
            "coefficient_table_hash mismatch:\n"
            f"  expected (manifest): {expected}\n"
            f"  actual (file):       {actual}\n"
            "Update scenario_coefficients_v1.manifest.json after intentional table changes.",
            file=sys.stderr,
        )
        return 1

    version = manifest.get("coefficient_table_version")
    table = json.loads(COEFF_FILE.read_text(encoding="utf-8"))
    if table.get("coefficient_table_version") != version:
        print(
            f"coefficient_table_version mismatch: manifest={version!r} "
            f"json={table.get('coefficient_table_version')!r}",
            file=sys.stderr,
        )
        return 1

    print(f"OK coefficient_table_version={version} hash={actual[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
