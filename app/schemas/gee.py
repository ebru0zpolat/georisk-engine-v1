from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

from app.schemas.baseline import BaselineComparison


class GeeFeatures(BaseModel):
    night_lights_mean: float
    no2_mean: float
    #: Mean NDVI (or similar greenness), ~-1..1 when from satellite; ``None`` if not applicable.
    ndvi_mean: float | None = Field(
        default=None,
        description="Vegetation index mean over the AOI for the current window (agriculture path; optional).",
    )
    #: Unitless 0–1 style proxy until ERA5-Land / SMAP is wired (agriculture stub or future connector).
    soil_moisture_proxy: float | None = Field(
        default=None,
        description="Soil moisture / wetness proxy for the AOI (agriculture path; optional).",
    )


class GeeBaselineFeatures(BaseModel):
    night_lights: BaselineComparison
    no2: BaselineComparison


class GeeFeaturesGetResponse(BaseModel):
    """Shape for GET /gee/features: current-window means plus optional baseline comparisons."""

    current: GeeFeatures
    gee_baseline: GeeBaselineFeatures | None = None
    data_mode: Literal["live", "stub"] = "stub"
    production_eligible: bool = False


def gee_baseline_from_raw(raw: Mapping[str, Any]) -> GeeBaselineFeatures | None:
    nl = raw.get("night_lights_comparison")
    no2 = raw.get("no2_comparison")
    if nl is None or no2 is None:
        return None
    return GeeBaselineFeatures.model_validate({"night_lights": nl, "no2": no2})
