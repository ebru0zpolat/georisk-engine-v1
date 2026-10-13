"""Ensure downstream modules import geospatial contracts via app.geo.interfaces only."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
FORBIDDEN_MODULES = {
    "app.geo.geometry_registry",
    "app.geo.spatial_index",
    "app.geo.raster_access",
}
ALLOWED_PREFIXES = (
    REPO_ROOT / "app" / "geo",
    REPO_ROOT / "tests",
)


def _module_path_for_file(path: Path) -> str | None:
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _is_allowed_importer(path: Path) -> bool:
    return any(str(path).startswith(str(prefix)) for prefix in ALLOWED_PREFIXES)


def test_no_external_imports_of_geo_concrete_modules() -> None:
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if _is_allowed_importer(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULES:
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in FORBIDDEN_MODULES:
                    violations.append(f"{path}: from {node.module} import ...")
    assert not violations, "Direct geo concrete imports found:\n" + "\n".join(violations)
