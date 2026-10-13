"""Country-Pack seam for water-stress/drought evidence.

There is deliberately no built-in global score and no synthetic fallback.  A
production caller must provide a licensed provider implementation.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field

from app.data_centres.contracts import ScenarioHorizon, WaterStressHazardEvidence


class WaterStressEvidenceUnavailable(RuntimeError):
    """Raised when no approved provider can produce water-stress evidence."""


class WaterStressQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    horizon: ScenarioHorizon
    valuation_date: date
    country_pack_id: str = Field(min_length=1)


class WaterStressProvider(Protocol):
    def fetch(self, query: WaterStressQuery) -> WaterStressHazardEvidence:
        """Return licensed, versioned evidence available by the valuation date."""


class UnconfiguredWaterStressProvider:
    def fetch(self, query: WaterStressQuery) -> WaterStressHazardEvidence:
        raise WaterStressEvidenceUnavailable(
            f"No approved water-stress provider configured for {query.country_pack_id}"
        )


def require_production_water_stress(
    provider: WaterStressProvider,
    query: WaterStressQuery,
) -> WaterStressHazardEvidence:
    evidence = provider.fetch(query)
    if evidence.horizon != query.horizon:
        raise WaterStressEvidenceUnavailable("Provider returned a different scenario horizon")
    if evidence.manifest.retrieved_on > query.valuation_date:
        raise WaterStressEvidenceUnavailable("Water-stress evidence violates the valuation cutoff")
    if evidence.manifest.synthetic:
        raise WaterStressEvidenceUnavailable("Synthetic water-stress evidence is not production evidence")
    if not evidence.manifest.licensed_for_commercial_use:
        raise WaterStressEvidenceUnavailable("Commercial-use licence is not confirmed")
    if evidence.classification.value == "not_classified":
        raise WaterStressEvidenceUnavailable(
            "Water-stress classification is not_classified; pack provider must classify"
        )
    return evidence
