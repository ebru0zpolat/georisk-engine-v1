from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.core.exceptions import GeoRiskApiError
from app.scoring.scenario_constants import HAZARD_DRIVER_LABELS

_DATA_DIR = Path(__file__).parent / "data"
_COEFFICIENT_PATH = _DATA_DIR / "scenario_coefficients_v1.json"
_MANIFEST_PATH = _DATA_DIR / "scenario_coefficients_v1.manifest.json"
_SUPPORTED_HORIZONS = (2030, 2050, 2100)


@lru_cache(maxsize=1)
def load_coefficient_table() -> dict:
    with _COEFFICIENT_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_coefficient_manifest() -> dict:
    with _MANIFEST_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def coefficient_table_version() -> str:
    return str(load_coefficient_table()["coefficient_table_version"])


def coefficient_table_hash() -> str:
    return str(load_coefficient_manifest()["coefficient_table_hash"])


def verify_coefficient_table_hash() -> bool:
    actual = hashlib.sha256(_COEFFICIENT_PATH.read_bytes()).hexdigest()
    return actual == coefficient_table_hash()


def _normalize_horizon(target_year: int) -> int:
    if target_year in _SUPPORTED_HORIZONS:
        return target_year
    return min(_SUPPORTED_HORIZONS, key=lambda h: abs(h - target_year))


def lookup_hazard_multiplier(
    hazard: str,
    pathway: str,
    target_year: int,
) -> float:
    table = load_coefficient_table()
    horizon_key = str(_normalize_horizon(target_year))
    hazards = table.get("hazards", {})
    hazard_entry = hazards.get(hazard)
    if hazard_entry and horizon_key in hazard_entry:
        pathway_row = hazard_entry[horizon_key]
        if pathway in pathway_row:
            return float(pathway_row[pathway])
    defaults = table.get("default_horizon_multipliers", {})
    if horizon_key not in defaults:
        raise GeoRiskApiError(
            "coefficient_lookup_failed",
            f"No coefficients for horizon {horizon_key}",
            status_code=422,
        )
    pathway_row = defaults[horizon_key]
    if pathway not in pathway_row:
        raise GeoRiskApiError(
            "coefficient_lookup_failed",
            f"No coefficients for pathway {pathway}",
            status_code=422,
        )
    return float(pathway_row[pathway])


def hazard_driver_multipliers(
    hazards: list[str],
    pathway: str,
    target_year: int,
) -> dict[str, float]:
    """Per-driver multipliers keyed by display labels (e.g. pluvial_flood)."""
    if not hazards:
        hazards = ["flood"]
    return {
        HAZARD_DRIVER_LABELS.get(h, h): round(
            lookup_hazard_multiplier(h, pathway, target_year), 2
        )
        for h in hazards
    }


def weighted_effective_multiplier(driver_multipliers: dict[str, float]) -> float:
    """Equal-weight mean across requested hazard drivers (GEO-150 / G-005)."""
    if not driver_multipliers:
        return 1.0
    values = list(driver_multipliers.values())
    return round(sum(values) / len(values), 4)


def effective_hazard_multiplier(
    hazards: list[str],
    pathway: str,
    target_year: int,
) -> float:
    """Backward-compatible alias for weighted effective multiplier."""
    return weighted_effective_multiplier(
        hazard_driver_multipliers(hazards, pathway, target_year)
    )
