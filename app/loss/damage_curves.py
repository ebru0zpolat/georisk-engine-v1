"""Versioned mean-damage-ratio (MDR) curves as methodology artifacts.

Curves live in ``app/loss/curves/*.json``. Changing a curve requires bumping the
catalogue ``version`` (methodology minor) and updating callers' data_versions.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_CURVES_DIR = Path(__file__).resolve().parent / "curves"
_DEFAULT_CATALOGUE = "stub_global_mdr_v0.2.json"


class DamageCurve(BaseModel):
    """One versioned MDR power curve keyed by building / use / hazard."""

    curve_id: str
    building_type: str
    use_class: str = "*"
    hazard_id: str
    exponent: float = Field(..., gt=0)
    scale: float = Field(..., gt=0, le=1.5)
    source: str = "synthetic calibration"
    synthetic: bool = True
    version: str = "0.1.0"

    def mdr(self, intensity: float) -> float:
        """Mean damage ratio — full precision (no intermediate round)."""
        i = max(0.0, min(1.0, float(intensity)))
        return max(0.0, min(1.0, self.scale * (i**self.exponent)))


class DamageCurveCatalogue(BaseModel):
    catalogue_id: str
    version: str
    source: str
    synthetic: bool = True
    methodology_note: str = ""
    curves: list[DamageCurve]

    @property
    def methodology_artifact_id(self) -> str:
        return f"{self.catalogue_id}-v{self.version}"


def _load_catalogue_dict(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalogue_from_raw(raw: dict[str, Any]) -> DamageCurveCatalogue:
    version = str(raw["version"])
    source = str(raw.get("source", "synthetic calibration"))
    synthetic = bool(raw.get("synthetic", True))
    curves: list[DamageCurve] = []
    for entry in raw["curves"]:
        curves.append(
            DamageCurve(
                curve_id=entry["curve_id"],
                building_type=entry["building_type"],
                use_class=entry.get("use_class", "*"),
                hazard_id=entry["hazard_id"],
                exponent=float(entry["exponent"]),
                scale=float(entry["scale"]),
                source=source,
                synthetic=synthetic,
                version=version,
            )
        )
    return DamageCurveCatalogue(
        catalogue_id=str(raw["catalogue_id"]),
        version=version,
        source=source,
        synthetic=synthetic,
        methodology_note=str(raw.get("methodology_note", "")),
        curves=curves,
    )


@lru_cache(maxsize=8)
def load_catalogue(filename: str = _DEFAULT_CATALOGUE) -> DamageCurveCatalogue:
    path = _CURVES_DIR / filename
    return _catalogue_from_raw(_load_catalogue_dict(path))


def load_catalogue_from_path(path: str | Path) -> DamageCurveCatalogue:
    """Load a catalogue from an explicit filesystem path (no default)."""
    return _catalogue_from_raw(_load_catalogue_dict(Path(path)))


def load_catalogue_by_id_version(catalogue_id: str, version: str) -> DamageCurveCatalogue:
    """Resolve a catalogue by id+version from the on-disk registry.

    Raises ``FileNotFoundError`` if no matching artefact exists — never falls
    back to the current default catalogue.
    """
    wanted_id = catalogue_id.strip()
    wanted_ver = version.strip()
    matches: list[Path] = []
    for path in sorted(_CURVES_DIR.glob("*.json")):
        raw = _load_catalogue_dict(path)
        if str(raw.get("catalogue_id")) == wanted_id and str(raw.get("version")) == wanted_ver:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(
            f"No damage-curve catalogue for catalogue_id={wanted_id!r} version={wanted_ver!r} "
            f"under {_CURVES_DIR}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous catalogue registry match for {wanted_id!r} v{wanted_ver}: {matches}"
        )
    return load_catalogue_from_path(matches[0])


def _match_score(
    curve: DamageCurve,
    *,
    building_type: str,
    use_class: str,
    hazard_id: str,
) -> int:
    """Higher is better; -1 = no match."""
    bt = building_type.strip().lower()
    uc = use_class.strip().lower()
    hz = hazard_id.strip().lower()
    c_bt = curve.building_type.strip().lower()
    c_uc = curve.use_class.strip().lower()
    c_hz = curve.hazard_id.strip().lower()

    if c_hz not in (hz, "*"):
        return -1
    if c_bt not in (bt, "*"):
        return -1
    if c_uc not in (uc, "*"):
        return -1

    score = 0
    if c_hz == hz:
        score += 4
    if c_bt == bt:
        score += 2
    if c_uc == uc:
        score += 1
    return score


def select_curve(
    *,
    building_type: str,
    use_class: str,
    hazard_id: str,
    catalogue: DamageCurveCatalogue | None = None,
) -> DamageCurve:
    cat = catalogue or load_catalogue()
    best: DamageCurve | None = None
    best_score = -1
    for curve in cat.curves:
        score = _match_score(
            curve,
            building_type=building_type,
            use_class=use_class,
            hazard_id=hazard_id,
        )
        if score > best_score:
            best_score = score
            best = curve
    if best is None:
        raise ValueError(
            f"No damage curve for building_type={building_type!r} "
            f"use_class={use_class!r} hazard_id={hazard_id!r}"
        )
    return best


def mean_damage_ratio(
    *,
    building_type: str,
    intensity: float,
    hazard_id: str = "flood",
    use_class: str = "*",
    catalogue: DamageCurveCatalogue | None = None,
) -> tuple[float, DamageCurve]:
    """Return (MDR in [0, 1], selected curve artifact)."""
    curve = select_curve(
        building_type=building_type,
        use_class=use_class,
        hazard_id=hazard_id,
        catalogue=catalogue,
    )
    return curve.mdr(intensity), curve


def damage_curves_version(catalogue: DamageCurveCatalogue | None = None) -> str:
    cat = catalogue or load_catalogue()
    return cat.methodology_artifact_id


# Stable alias for golden baselines / older callers.
DAMAGE_CURVES_VERSION = damage_curves_version()


__all__ = [
    "DAMAGE_CURVES_VERSION",
    "DamageCurve",
    "DamageCurveCatalogue",
    "damage_curves_version",
    "load_catalogue",
    "load_catalogue_by_id_version",
    "load_catalogue_from_path",
    "mean_damage_ratio",
    "select_curve",
]
