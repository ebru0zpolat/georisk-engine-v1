from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_verify_coefficient_hash_script_passes() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_coefficient_hash.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
