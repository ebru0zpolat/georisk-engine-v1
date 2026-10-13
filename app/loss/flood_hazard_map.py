"""Return-period flood-hazard map — the real source for the reference flood level.

The reference flood level converts real ground elevation into inundation depth for
the JRC depth-damage curves (``flood_depth``). Until now it was a single synthetic
scalar (STUBS #26). This module is its real shape: a **versioned, provenanced grid
of per-cell water levels by return period** — e.g. NL LIWO / a Country-Pack flood
extent — so each asset gets the water level of its own location at a chosen return
period (T=10 / 100 / 1000 yr), in the same datum as the elevation (NAP).

Fail-closed and honest, mirroring the other real seams:

- an **unpopulated** map cannot produce a level;
- a cell the map does not cover fails closed (no interpolation of thin air);
- a **non-synthetic** map must ship a matching SHA-256 provenance sidecar, or its
  sealed water levels are refused;
- a labelled synthetic fixture ships for offline runs (``synthetic=true``) and is
  never mistaken for a real flood surface.

Authentic values are vendored (``scripts/vendor_flood_hazard_map.py``).
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

_CURVES_DIR = Path(__file__).resolve().parent / "curves"


class ReturnPeriodWaterLevel(BaseModel):
    """Water level at one grid cell for one return period, in the map's datum."""

    cell_id: str  # "<lat>,<lon>" rounded to the map's cell size
    return_period_years: int = Field(..., gt=0)
    water_level_m: float

    @field_validator("water_level_m")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError(f"water_level_m must be finite, got {v!r}")
        return v


class FloodHazardMap(BaseModel):
    """A versioned grid of per-cell return-period water levels (one datum).

    Carries the metadata needed to prove a water level may be differenced from a
    ground elevation (``flood_depth.assert_differenceable``): the vertical ``datum``,
    ``units``, ``horizontal_crs``, ``value_semantics`` (a water-surface elevation)
    and an explicit datum ``transformation``.
    """

    map_id: str
    version: str
    source: str
    datum: str = "NAP"  # vertical datum; must match the elevation datum (AHN = NAP)
    units: str = "m"
    horizontal_crs: str = "EPSG:4326"
    value_semantics: str = "water_surface_elevation"
    transformation: str = "none_required"  # transform id, or the explicit assertion
    cell_size_deg: float = Field(0.01, gt=0.0)
    synthetic: bool = True
    populated: bool = False
    methodology_note: str = ""
    levels: list[ReturnPeriodWaterLevel]

    # Built once at validation: (cell_id, return_period) → water_level_m. A national
    # 0.01-deg map can hold 100k+ levels, so per-asset lookups must be O(1), not a
    # scan of ``levels`` (assets × rows).
    _index: dict[tuple[str, int], float] = PrivateAttr(default_factory=dict)
    # SHA-256 of the exact sealed artifact bytes, set when loaded from a path (both
    # real and synthetic). ``None`` for a map constructed directly in code/tests.
    _artifact_sha256: str | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _index_and_validate(self) -> "FloodHazardMap":
        index: dict[tuple[str, int], float] = {}
        for lvl in self.levels:
            key = (lvl.cell_id, lvl.return_period_years)
            if key in index:
                raise ValueError(
                    f"duplicate water level for cell/return-period {key}; a lookup "
                    "must map to a single published level, not depend on file order"
                )
            index[key] = lvl.water_level_m
        self._index = index
        return self

    @property
    def methodology_artifact_id(self) -> str:
        return f"{self.map_id}-v{self.version}"

    @property
    def artifact_sha256(self) -> str | None:
        """SHA-256 of the sealed bytes this map was loaded from (``None`` if built in code)."""
        return self._artifact_sha256

    def provenance_stamp(self, cell_id: str, return_period_years: int) -> dict[str, Any]:
        """Audit-record identity of this map for a resolved cell (synthetic vs real).

        Carries the map id, checksum, source + source type, datum, cell id, return
        period and synthetic status — everything the audit trail needs to name and
        trust (or reject) the water level. ``checksum`` is ``"unsealed"`` only for a
        map constructed directly in code (never for one loaded from a sealed file).
        """
        return {
            "flood_map": self.methodology_artifact_id,
            "flood_map_source": self.source,
            "flood_map_source_type": "synthetic" if self.synthetic else "real",
            "flood_map_synthetic": self.synthetic,
            "flood_map_sha256": self._artifact_sha256 or "unsealed",
            "flood_map_datum": self.datum,
            "flood_map_units": self.units,
            "flood_cell_id": cell_id,
            "flood_cell_size_deg": self.cell_size_deg,
            "flood_return_period_years": return_period_years,
        }

    def _cell_id(self, latitude: float, longitude: float) -> str:
        size = self.cell_size_deg
        lat = round(round(float(latitude) / size) * size, 6)
        lon = round(round(float(longitude) / size) * size, 6)
        # Normalise -0.0 → 0.0 and trim to the cell precision for a stable key.
        return f"{lat + 0.0:g},{lon + 0.0:g}"

    def available_return_periods(self) -> list[int]:
        return sorted({lvl.return_period_years for lvl in self.levels})

    def _level_for_cell(self, cell: str, latitude: float, longitude: float, rp: int) -> float:
        if not self.populated:
            raise ValueError(
                f"FLOOD_HAZARD_MAP_UNPOPULATED_FAIL_CLOSED: map "
                f"{self.methodology_artifact_id!r} has no real water levels yet. "
                "Vendor them: scripts/vendor_flood_hazard_map.py --from-csv <f.csv>"
            )
        level = self._index.get((cell, rp))
        if level is not None:
            return level
        raise ValueError(
            f"no water level for cell {cell!r} (lat={latitude}, lon={longitude}) at "
            f"return period {rp}yr in {self.methodology_artifact_id!r}; "
            f"covered return periods: {self.available_return_periods()}"
        )

    def reference_level_at(
        self, latitude: float, longitude: float, return_period_years: int
    ) -> float:
        """Water level (datum metres) for a location + return period (fail-closed)."""
        cell = self._cell_id(latitude, longitude)
        return self._level_for_cell(cell, latitude, longitude, return_period_years)

    def lookup_provenance(
        self, latitude: float, longitude: float, return_period_years: int
    ) -> tuple[float, dict[str, Any]]:
        """Resolve the water level *and* its full provenance stamp (fail-closed).

        Returns ``(water_level_m, provenance)`` where ``provenance`` names the exact
        resolved cell — so the audit record ties the level to a specific grid cell,
        not just the map. Fails closed identically to ``reference_level_at``.
        """
        cell = self._cell_id(latitude, longitude)
        level = self._level_for_cell(cell, latitude, longitude, return_period_years)
        return level, self.provenance_stamp(cell, return_period_years)


def _map_from_raw(raw: dict[str, Any]) -> FloodHazardMap:
    return FloodHazardMap(
        map_id=str(raw["map_id"]),
        version=str(raw["version"]),
        source=str(raw["source"]),
        datum=str(raw.get("datum", "NAP")),
        units=str(raw.get("units", "m")),
        horizontal_crs=str(raw.get("horizontal_crs", "EPSG:4326")),
        value_semantics=str(raw.get("value_semantics", "water_surface_elevation")),
        transformation=str(raw.get("transformation", "none_required")),
        cell_size_deg=float(raw.get("cell_size_deg", 0.01)),
        synthetic=bool(raw.get("synthetic", True)),
        populated=bool(raw.get("populated", False)),
        methodology_note=str(raw.get("methodology_note", "")),
        levels=[ReturnPeriodWaterLevel(**lvl) for lvl in raw.get("levels", [])],
    )


def _verify_real_provenance(path: Path, raw: bytes) -> None:
    """A non-synthetic map must ship a matching SHA-256 provenance sidecar."""
    sidecar = path.with_name(path.stem + ".provenance.json")
    if not sidecar.exists():
        raise ValueError(
            f"real flood-hazard map {path.name!r} has no provenance sidecar "
            f"({sidecar.name}); refusing to use unverifiable real water levels"
        )
    expected = str(json.loads(sidecar.read_text(encoding="utf-8")).get("artifact_sha256", ""))
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(
            f"flood-hazard map {path.name!r} SHA-256 does not match its provenance "
            f"({actual[:16]}… vs {expected[:16]}…) — tampered or re-serialised"
        )


def load_flood_hazard_map_from_path(path: str | Path) -> FloodHazardMap:
    p = Path(path)
    raw = p.read_bytes()
    fhm = _map_from_raw(json.loads(raw))
    if not fhm.synthetic:
        _verify_real_provenance(p, raw)
    # Bind the map to the exact sealed bytes it came from, so the audit record can
    # carry a checksum (real maps are provenance-verified above; synthetic fixtures
    # are stamped too, purely for traceability — never to imply they are real).
    fhm._artifact_sha256 = hashlib.sha256(raw).hexdigest()
    return fhm


@lru_cache(maxsize=8)
def load_flood_hazard_map(filename: str) -> FloodHazardMap:
    return load_flood_hazard_map_from_path(_CURVES_DIR / filename)


__all__ = [
    "FloodHazardMap",
    "ReturnPeriodWaterLevel",
    "load_flood_hazard_map",
    "load_flood_hazard_map_from_path",
]
