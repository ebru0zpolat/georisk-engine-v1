"""Earthquake hazard module (geophysical peril — Türkiye first).

Country-agnostic core module. The intensity driver is **peak ground
acceleration** (PGA, in g) for a stated return period, as published by a
national or regional seismic-hazard model (Türkiye: AFAD TDTH 2018, 475-year
DD-2 level; global: GEM). A seismic source is **mandatory** — this module has
no mock raster and fails closed without one, because there is no climate
proxy for ground shaking and inventing one would be exactly the kind of
plausible default the fail-closed contract forbids.

For offline demos and CI, :class:`SyntheticSeismicSource` provides a
deterministic, SHA-256 seeded PGA field that is labelled synthetic on every
result. It has the *shape* of a hazard-map lookup and none of its truth.

Earthquake is **not a climate hazard**: its intensity does not move with a
climate scenario. Horizon catalogues must carry a stationary (1.0) factor for
it, and results stamp ``hazard_class: geophysical`` so downstream consumers
can keep climate and non-climate perils apart.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.geo.interfaces import RasterTile
from app.hazards.base import HazardModuleResult, score_to_intensity

EARTHQUAKE_HAZARD_ID = "earthquake"
EARTHQUAKE_METHODOLOGY_VERSION = "earthquake-hazard-v0.1"
EARTHQUAKE_SYNTHETIC_DATA_VERSION = "seismic-pga-synthetic-v0.1"

#: PGA (g) at or above which the score saturates at 100 — the upper bound of the
#: highest AFAD TDTH DD-2 band; anything beyond it is treated as total exposure.
PGA_SATURATION_G = 0.6
#: Default return period stamped when the source does not state one.
DEFAULT_RETURN_PERIOD_YEARS = 475


class _SeismicSource(Protocol):
    def pga_g(self, lat: float, lon: float) -> RasterTile: ...


@dataclass(frozen=True)
class SyntheticSeismicSource:
    """Deterministic labelled PGA field for demos — never a hazard map."""

    seed_namespace: str = "synthetic-seismic-v0.1"
    max_pga_g: float = 0.5

    def pga_g(self, lat: float, lon: float) -> RasterTile:
        digest = hashlib.sha256(
            f"{self.seed_namespace}|{lat:.5f}|{lon:.5f}".encode()
        ).hexdigest()
        unit = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
        return RasterTile(
            source="SYNTHETIC-SEISMIC (SHA-256 seeded; not AFAD/GEM)",
            lat=lat,
            lon=lon,
            value=round(unit * self.max_pga_g, 4),
            unit="g",
            data_snapshot_id=self.seed_namespace,
        )


def score_from_pga_g(pga_g: float) -> int:
    raw = (max(0.0, float(pga_g)) / PGA_SATURATION_G) * 100.0
    return max(0, min(100, int(round(raw))))


class EarthquakeHazardModule:
    """Core earthquake hazard module — satisfies ``HazardModule``; fail-closed without a source."""

    hazard_id: str = EARTHQUAKE_HAZARD_ID
    methodology_version: str = EARTHQUAKE_METHODOLOGY_VERSION

    def __init__(
        self,
        *,
        source: _SeismicSource | None = None,
        data_version: str | None = None,
        return_period_years: int = DEFAULT_RETURN_PERIOD_YEARS,
    ) -> None:
        self._source = source
        self._data_version = data_version
        self._return_period_years = return_period_years

    def evaluate(
        self,
        *,
        latitude: float,
        longitude: float,
        valuation_date: date,
        parameters: dict[str, Any] | None = None,
    ) -> HazardModuleResult:
        _ = parameters  # reserved for pack overrides (site class, return period)
        if self._source is None:
            raise ValueError(
                "EARTHQUAKE_SOURCE_REQUIRED: no seismic-hazard source supplied and no proxy "
                "exists for ground shaking; pass a PGA source (AFAD TDTH / GEM) or, for a "
                "labelled demo, SyntheticSeismicSource()."
            )
        tile = self._source.pga_g(latitude, longitude)
        synthetic = isinstance(self._source, SyntheticSeismicSource)
        pga = float(tile.value)
        score = score_from_pga_g(pga)
        intensity = score_to_intensity(score)
        data_version = self._data_version or (
            EARTHQUAKE_SYNTHETIC_DATA_VERSION if synthetic else f"seismic-pga:{tile.source}"
        )
        return HazardModuleResult(
            hazard_id=self.hazard_id,
            intensity=intensity,
            score_0_100=score,
            subtypes={"ground_shaking": intensity},
            data_versions={"seismic_pga": data_version},
            methodology_version=self.methodology_version,
            valuation_date=valuation_date,
            latitude=latitude,
            longitude=longitude,
            metadata={
                "pga_g": round(pga, 4),
                "return_period_years": self._return_period_years,
                "seismic_source": tile.source,
                "synthetic": synthetic,
                "hazard_class": "geophysical",
                "climate_stationary": True,
                "input_cutoff": valuation_date.isoformat(),
            },
        )


__all__ = [
    "DEFAULT_RETURN_PERIOD_YEARS",
    "EARTHQUAKE_HAZARD_ID",
    "EARTHQUAKE_METHODOLOGY_VERSION",
    "EARTHQUAKE_SYNTHETIC_DATA_VERSION",
    "PGA_SATURATION_G",
    "EarthquakeHazardModule",
    "SyntheticSeismicSource",
    "score_from_pga_g",
]
