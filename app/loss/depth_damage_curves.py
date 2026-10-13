"""Depth–damage curves (JRC family) — real flood damage functions.

The legacy ``damage_curves`` module fits an ``intensity∈[0,1] → MDR`` power law
(labelled synthetic, STUBS #16). The physically-grounded, literature-cited
alternative is a **depth→damage** curve: inundation depth in metres mapped to a
damage fraction, tabulated per occupancy (and per continent). The reference set
is JRC's *Global flood depth-damage functions* (Huizinga, de Moel, Szewczyk,
2017), which is openly published and redistributable.

This module is the **engine** for that family — schema, load, monotonic
interpolation, occupancy selection, fail-closed guards. Authentic curve values
are vendored separately (``scripts/vendor_jrc_depth_damage.py``): a catalogue
with ``populated=false`` cannot be used, so real JRC numbers must be sealed in
before any real depth→damage number is emitted. A labelled SYNTHETIC-FIXTURE
catalogue ships for offline tests/demos and is never mistaken for JRC data
(``synthetic=true``).

Applying this to real assets needs a real inundation **depth**, which comes from
AHN elevation + a return-period reference level (the next P1 increment). Until
that lands, this engine is validated standalone and is **not** wired into the
audited ``expected-loss`` replay path (that wiring is a versioned
``expected-loss-v0.4`` change: depth input + replay dispatch).
"""

from __future__ import annotations

import json
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

_CURVES_DIR = Path(__file__).resolve().parent / "curves"

# JRC occupancy classes we map the universal building types onto.
_BUILDING_TYPE_TO_OCCUPANCY: dict[str, str] = {
    "residential": "residential",
    "apartment": "residential",
    "hotel": "commercial",
    "office": "commercial",
    "retail": "commercial",
    "commercial": "commercial",
    "industrial": "industrial",
    "other": "commercial",
}
_DEFAULT_OCCUPANCY = "commercial"


def occupancy_for_building_type(building_type: str) -> str:
    """Map a universal building type to a JRC occupancy class."""
    return _BUILDING_TYPE_TO_OCCUPANCY.get(building_type.strip().lower(), _DEFAULT_OCCUPANCY)


class DepthDamagePoint(BaseModel):
    depth_m: float = Field(..., ge=0.0)
    damage_ratio: float = Field(..., ge=0.0, le=1.0)


class DepthDamageCurve(BaseModel):
    """One tabulated depth→damage curve for an occupancy (× continent)."""

    curve_id: str
    occupancy: str
    use_class: str = "*"
    continent: str = "*"
    hazard_id: str = "flood"
    points: list[DepthDamagePoint]
    source: str
    synthetic: bool
    version: str

    @model_validator(mode="after")
    def _validate_points(self) -> "DepthDamageCurve":
        if len(self.points) < 2:
            raise ValueError(f"curve {self.curve_id!r} needs >= 2 points")
        depths = [p.depth_m for p in self.points]
        if depths != sorted(depths) or len(set(depths)) != len(depths):
            raise ValueError(f"curve {self.curve_id!r} depths must be strictly increasing")
        damages = [p.damage_ratio for p in self.points]
        if damages != sorted(damages):
            raise ValueError(f"curve {self.curve_id!r} damage_ratio must be non-decreasing")
        return self

    def damage_ratio_at_depth(self, depth_m: float) -> float:
        """Linear-interpolated damage fraction at ``depth_m`` (full precision).

        Clamps below the first point (typically depth 0 → 0 damage) and above the
        last point (typically the saturation depth → max damage).
        """
        d = float(depth_m)
        pts = self.points
        if d <= pts[0].depth_m:
            return pts[0].damage_ratio
        if d >= pts[-1].depth_m:
            return pts[-1].damage_ratio
        depths = [p.depth_m for p in pts]
        hi = bisect_right(depths, d)
        lo = hi - 1
        p0, p1 = pts[lo], pts[hi]
        span = p1.depth_m - p0.depth_m
        frac = (d - p0.depth_m) / span if span else 0.0
        return max(0.0, min(1.0, p0.damage_ratio + frac * (p1.damage_ratio - p0.damage_ratio)))


class DepthDamageCatalogue(BaseModel):
    catalogue_id: str
    version: str
    source: str
    synthetic: bool = True
    populated: bool = False
    methodology_note: str = ""
    curves: list[DepthDamageCurve]

    @property
    def methodology_artifact_id(self) -> str:
        return f"{self.catalogue_id}-v{self.version}"


def _catalogue_from_raw(raw: dict[str, Any]) -> DepthDamageCatalogue:
    version = str(raw["version"])
    source = str(raw["source"])
    synthetic = bool(raw.get("synthetic", True))
    curves: list[DepthDamageCurve] = []
    for entry in raw.get("curves", []):
        curves.append(
            DepthDamageCurve(
                curve_id=entry["curve_id"],
                occupancy=str(entry["occupancy"]).strip().lower(),
                use_class=entry.get("use_class", "*"),
                continent=str(entry.get("continent", "*")).strip().lower(),
                hazard_id=entry.get("hazard_id", "flood"),
                points=[DepthDamagePoint(**p) for p in entry["points"]],
                source=source,
                synthetic=synthetic,
                version=version,
            )
        )
    return DepthDamageCatalogue(
        catalogue_id=str(raw["catalogue_id"]),
        version=version,
        source=source,
        synthetic=synthetic,
        populated=bool(raw.get("populated", False)),
        methodology_note=str(raw.get("methodology_note", "")),
        curves=curves,
    )


@lru_cache(maxsize=8)
def load_depth_damage_catalogue(filename: str) -> DepthDamageCatalogue:
    return _catalogue_from_raw(json.loads((_CURVES_DIR / filename).read_text(encoding="utf-8")))


def load_depth_damage_from_path(path: str | Path) -> DepthDamageCatalogue:
    return _catalogue_from_raw(json.loads(Path(path).read_text(encoding="utf-8")))


def load_depth_damage_by_id_version(catalogue_id: str, version: str) -> DepthDamageCatalogue:
    """Resolve a depth-damage catalogue by id+version from the on-disk registry.

    Fail-closed: raises ``FileNotFoundError`` if no artefact matches — never
    falls back to a default catalogue (audited replay must reconstruct exactly).
    """
    wanted_id, wanted_ver = catalogue_id.strip(), version.strip()
    matches: list[Path] = []
    for path in sorted(_CURVES_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if str(raw.get("catalogue_id")) == wanted_id and str(raw.get("version")) == wanted_ver:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(
            f"No depth-damage catalogue for catalogue_id={wanted_id!r} version={wanted_ver!r}"
        )
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous depth-damage catalogue for {wanted_id!r} v{wanted_ver}")
    return load_depth_damage_from_path(matches[0])


def _match_score(curve: DepthDamageCurve, *, occupancy: str, continent: str) -> int:
    c_occ = curve.occupancy.strip().lower()
    c_cont = curve.continent.strip().lower()
    if c_occ not in (occupancy, "*"):
        return -1
    if c_cont not in (continent, "*"):
        return -1
    score = 0
    if c_occ == occupancy:
        score += 2
    if c_cont == continent:
        score += 1
    return score


def select_depth_curve(
    *,
    building_type: str,
    continent: str = "*",
    catalogue: DepthDamageCatalogue,
    occupancy: str | None = None,
) -> DepthDamageCurve:
    """Select the best occupancy×continent curve. Fail-closed on unpopulated."""
    if not catalogue.populated:
        raise ValueError(
            f"DEPTH_DAMAGE_UNPOPULATED_FAIL_CLOSED: catalogue "
            f"{catalogue.methodology_artifact_id!r} carries no real curve values yet. "
            "Vendor them: PYTHONPATH=. python scripts/vendor_jrc_depth_damage.py --from-csv <jrc.csv>"
        )
    occ = (occupancy or occupancy_for_building_type(building_type)).strip().lower()
    cont = continent.strip().lower()
    best: DepthDamageCurve | None = None
    best_score = -1
    for curve in catalogue.curves:
        score = _match_score(curve, occupancy=occ, continent=cont)
        if score > best_score:
            best_score = score
            best = curve
    if best is None:
        raise ValueError(
            f"No depth-damage curve for occupancy={occ!r} continent={cont!r} "
            f"in {catalogue.methodology_artifact_id!r}"
        )
    return best


def damage_ratio_at_depth(
    *,
    building_type: str,
    depth_m: float,
    continent: str = "*",
    catalogue: DepthDamageCatalogue,
    occupancy: str | None = None,
) -> tuple[float, DepthDamageCurve]:
    """Return (damage fraction in [0, 1], selected curve)."""
    curve = select_depth_curve(
        building_type=building_type,
        continent=continent,
        catalogue=catalogue,
        occupancy=occupancy,
    )
    return curve.damage_ratio_at_depth(depth_m), curve


__all__ = [
    "DepthDamageCatalogue",
    "DepthDamageCurve",
    "DepthDamagePoint",
    "damage_ratio_at_depth",
    "load_depth_damage_by_id_version",
    "load_depth_damage_catalogue",
    "load_depth_damage_from_path",
    "occupancy_for_building_type",
    "select_depth_curve",
]
