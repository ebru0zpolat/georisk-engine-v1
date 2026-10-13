"""Guard: independent verifier must not import pipeline packages."""

from __future__ import annotations

import ast
from pathlib import Path

_VERIFIER = Path(__file__).resolve().parent / "independent_eal.py"
_FORBIDDEN = ("app.loss", "app.services", "app.pipeline")


def test_independent_eal_has_no_app_imports() -> None:
    tree = ast.parse(_VERIFIER.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app.") or alias.name == "app":
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "app" or mod.startswith("app."):
                offenders.append(mod)
            for prefix in _FORBIDDEN:
                if mod.startswith(prefix):
                    offenders.append(mod)
    assert not offenders, f"independent_eal.py must not import pipeline modules: {offenders}"


def test_independent_eal_stays_short() -> None:
    lines = _VERIFIER.read_text(encoding="utf-8").splitlines()
    # Cap raised 120→160 when v0.4 added: the verifier now covers two curve
    # families (intensity power curves + JRC depth-damage interpolation).
    assert len(lines) <= 160, f"verifier grew to {len(lines)} lines; keep it auditable (~140)"
