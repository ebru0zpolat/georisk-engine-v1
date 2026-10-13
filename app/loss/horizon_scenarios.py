"""Forward-horizon climate-scenario intensities (CMIP6/CORDEX/KNMI'23).

The expected-loss engine already consumes ``horizon_2030`` / ``horizon_2050``
intensity maps and emits ``scenario_eal`` when both are supplied. What was
missing (STUBS #16b) is a **versioned scenario source** for those horizons — the
disabled fallback invented ``current × 0.95 / 1.05`` with no provenance.

This provides the real source shape: a catalogue of **published, versioned
per-hazard uplift factors** for a named climate scenario (e.g. KNMI'23 or a
CMIP6/CORDEX-derived SSP pathway). A horizon intensity is
``clamp(current × factor[hazard, horizon], 0, 1)`` — the current intensity
projected by a real scenario multiplier, never a manufactured constant.

Fail-closed: an unpopulated catalogue cannot produce horizons. Authentic factors
are vendored (``scripts/vendor_horizon_scenarios.py``); a labelled synthetic
fixture ships for offline runs (``synthetic=true``) and is never mistaken for a
real scenario.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

_CURVES_DIR = Path(__file__).resolve().parent / "curves"
HORIZONS = ("2030", "2050")


class HorizonUplift(BaseModel):
    hazard_id: str
    horizon: str  # "2030" or "2050"
    factor: float = Field(..., ge=0.0)

    @field_validator("factor")
    @classmethod
    def _finite(cls, v: float) -> float:
        # Reject inf / nan: they would silently saturate every projection to 1.0.
        if not math.isfinite(v):
            raise ValueError(f"factor must be finite, got {v!r}")
        return v

    @model_validator(mode="after")
    def _valid_horizon(self) -> "HorizonUplift":
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}, got {self.horizon!r}")
        return self


class HorizonScenarioCatalogue(BaseModel):
    """Per-hazard uplift factors for one named climate scenario (both horizons)."""

    catalogue_id: str
    version: str
    scenario: str  # e.g. "SSP2-4.5", "KNMI23-Md"
    source: str
    synthetic: bool = True
    populated: bool = False
    methodology_note: str = ""
    uplifts: list[HorizonUplift]

    @model_validator(mode="after")
    def _unique_pairs(self) -> "HorizonScenarioCatalogue":
        seen: set[tuple[str, str]] = set()
        for u in self.uplifts:
            key = (u.hazard_id.strip().lower(), u.horizon)
            if key in seen:
                raise ValueError(
                    f"duplicate uplift for hazard/horizon {key}; a projection must "
                    "map to a single published factor, not depend on file order"
                )
            seen.add(key)
        return self

    @property
    def methodology_artifact_id(self) -> str:
        return f"{self.catalogue_id}-v{self.version}"

    def _factor(self, hazard_id: str, horizon: str) -> float | None:
        hid = hazard_id.strip().lower()
        for u in self.uplifts:
            if u.hazard_id.strip().lower() == hid and u.horizon == horizon:
                return u.factor
        return None

    def project(self, hazard_id: str, current_intensity: float, horizon: str) -> float:
        """clamp(current × factor, 0, 1) for one hazard/horizon (fail-closed)."""
        if not self.populated:
            raise ValueError(
                f"HORIZON_SCENARIO_UNPOPULATED_FAIL_CLOSED: catalogue "
                f"{self.methodology_artifact_id!r} has no real factors yet. Vendor "
                "them: PYTHONPATH=. python scripts/vendor_horizon_scenarios.py --from-csv <f.csv>"
            )
        factor = self._factor(hazard_id, horizon)
        if factor is None:
            raise ValueError(
                f"no uplift factor for hazard={hazard_id!r} horizon={horizon!r} "
                f"in {self.methodology_artifact_id!r}"
            )
        return max(0.0, min(1.0, float(current_intensity) * factor))

    def build_horizon_maps(
        self, current: dict[str, float]
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Return (horizon_2030, horizon_2050) maps projected from ``current``."""
        h2030 = {h: self.project(h, i, "2030") for h, i in current.items()}
        h2050 = {h: self.project(h, i, "2050") for h, i in current.items()}
        return h2030, h2050


def _catalogue_from_raw(raw: dict[str, Any]) -> HorizonScenarioCatalogue:
    return HorizonScenarioCatalogue(
        catalogue_id=str(raw["catalogue_id"]),
        version=str(raw["version"]),
        scenario=str(raw["scenario"]),
        source=str(raw["source"]),
        synthetic=bool(raw.get("synthetic", True)),
        populated=bool(raw.get("populated", False)),
        methodology_note=str(raw.get("methodology_note", "")),
        uplifts=[HorizonUplift(**u) for u in raw.get("uplifts", [])],
    )


def _verify_real_provenance(path: Path, raw: bytes) -> None:
    """A non-synthetic catalogue must ship a matching provenance sidecar.

    Fail-closed: without the sidecar (or on a SHA-256 mismatch) the vendored
    seal gives no protection, so altered factors could silently shape EAL.
    """
    sidecar = path.with_name(path.stem + ".provenance.json")
    if not sidecar.exists():
        raise ValueError(
            f"real catalogue {path.name!r} has no provenance sidecar "
            f"({sidecar.name}); refusing to use unverifiable real factors"
        )
    expected = str(json.loads(sidecar.read_text(encoding="utf-8")).get("artifact_sha256", ""))
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(
            f"catalogue {path.name!r} SHA-256 does not match its provenance "
            f"({actual[:16]}… vs {expected[:16]}…) — tampered or re-serialised"
        )


def load_horizon_scenario_from_path(path: str | Path) -> HorizonScenarioCatalogue:
    p = Path(path)
    raw = p.read_bytes()
    catalogue = _catalogue_from_raw(json.loads(raw))
    if not catalogue.synthetic:
        _verify_real_provenance(p, raw)
    return catalogue


@lru_cache(maxsize=8)
def load_horizon_scenario_catalogue(filename: str) -> HorizonScenarioCatalogue:
    return load_horizon_scenario_from_path(_CURVES_DIR / filename)


__all__ = [
    "HORIZONS",
    "HorizonScenarioCatalogue",
    "HorizonUplift",
    "load_horizon_scenario_catalogue",
    "load_horizon_scenario_from_path",
]
