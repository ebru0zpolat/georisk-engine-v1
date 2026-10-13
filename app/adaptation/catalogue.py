"""Global default adaptation measure catalogue (Country Packs may override costs)."""

from __future__ import annotations

from pydantic import BaseModel, Field

ADAPTATION_CATALOGUE_VERSION = "adaptation-catalogue-v0.2"


class CatalogueMeasure(BaseModel):
    """One financeable adaptation option."""

    measure_id: str
    label: str
    description: str = ""
    hazards_addressed: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Hazard ids this measure primarily reduces (flood, extreme_heat, …).",
    )
    cost_fraction_of_value: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Indicative capex as a fraction of asset value.",
    )
    risk_reduction_fraction: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of baseline EAL avoided if fully implemented.",
    )


# Global defaults — pack-tr / pack-nl may replace unit costs later.
DEFAULT_CATALOGUE: tuple[CatalogueMeasure, ...] = (
    CatalogueMeasure(
        measure_id="cool-roof-v1",
        label="Cool roof / reflective coating",
        description="Reduce heat gain and extreme-heat operational disruption.",
        hazards_addressed=("extreme_heat",),
        cost_fraction_of_value=0.015,
        risk_reduction_fraction=0.18,
    ),
    CatalogueMeasure(
        measure_id="flood-barrier-v1",
        label="Property-level flood barrier",
        description="Demountable or permanent barrier at building perimeter.",
        hazards_addressed=("flood",),
        cost_fraction_of_value=0.04,
        risk_reduction_fraction=0.35,
    ),
    CatalogueMeasure(
        measure_id="drainage-upgrade-v1",
        label="Site drainage upgrade",
        description="Improve pluvial runoff capacity and site grading.",
        hazards_addressed=("flood",),
        cost_fraction_of_value=0.025,
        risk_reduction_fraction=0.22,
    ),
    CatalogueMeasure(
        measure_id="hvac-resilience-v1",
        label="HVAC resilience upgrade",
        description="Upsize cooling and backup power for heat extremes.",
        hazards_addressed=("extreme_heat",),
        cost_fraction_of_value=0.03,
        risk_reduction_fraction=0.20,
    ),
    CatalogueMeasure(
        measure_id="green-infrastructure-v1",
        label="Green infrastructure (bioswales / permeable paving)",
        description="Multi-hazard site measures for heat and pluvial flood.",
        hazards_addressed=("flood", "extreme_heat"),
        cost_fraction_of_value=0.035,
        risk_reduction_fraction=0.28,
    ),
    CatalogueMeasure(
        measure_id="seismic-retrofit-v1",
        label="Seismic structural retrofit",
        description=(
            "Strengthen the lateral load path (shear walls, jacketing, base connections) "
            "to the current national seismic code; the only measure that reduces "
            "ground-shaking damage."
        ),
        hazards_addressed=("earthquake",),
        cost_fraction_of_value=0.08,
        # Single-peril measures are credited against total EAL in Phase A, so their
        # fractions are deliberately below the share a four-hazard stub gives one peril.
        risk_reduction_fraction=0.30,
    ),
    CatalogueMeasure(
        measure_id="wildfire-defensible-space-v1",
        label="Defensible space and ember-resistant envelope",
        description=(
            "Vegetation clearance zones, non-combustible roofing and ember-proof vents "
            "at the wildland-urban interface."
        ),
        hazards_addressed=("wildfire",),
        cost_fraction_of_value=0.012,
        risk_reduction_fraction=0.10,
    ),
)


def get_default_catalogue() -> tuple[CatalogueMeasure, ...]:
    return DEFAULT_CATALOGUE


__all__ = [
    "ADAPTATION_CATALOGUE_VERSION",
    "CatalogueMeasure",
    "DEFAULT_CATALOGUE",
    "get_default_catalogue",
]
