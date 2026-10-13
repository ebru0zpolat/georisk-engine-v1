from datetime import datetime

from pydantic import BaseModel, Field

from app.core.sector_registry import DEFAULT_SECTOR_ID


class PreviewRiskScoreRequest(BaseModel):
    """1-minute indicative scorecard: coordinate, address, or demo asset id."""

    location: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description=(
            "Latitude/longitude (e.g. 36.85,30.75), free-text address, "
            "or demo asset id (e.g. coastal_industrial_med)."
        ),
    )
    asset_name: str | None = Field(
        default=None,
        description="Optional display name; defaults from geocode or demo preset.",
    )
    radius_km: float = Field(default=10.0, gt=0, le=100)
    sector: str = Field(default=DEFAULT_SECTOR_ID)


class ResolvedLocation(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    asset_name: str
    sector: str
    resolution_method: str = Field(
        description="coordinates | demo_asset | address_alias | geocoder"
    )
    resolution_detail: str | None = None


class ScorecardComponent(BaseModel):
    id: str
    label: str
    score: int


class PreviewRiskScorecard(BaseModel):
    """Compact scorecard for agentic research / reporting layer (UC-01)."""

    indicative_climate_risk_score: int = Field(
        description="Indicative composite 0–100; not regulatory proof."
    )
    risk_band: str
    headline: str
    location_input: str
    resolved: ResolvedLocation
    components: list[ScorecardComponent]
    top_flags: list[str]
    interpretation: str
    disclaimer: str
    audit_id: str
    generated_at: datetime
    deep_dive_endpoints: dict[str, str] = Field(
        default_factory=lambda: {
            "full_score": "/v1/risk/score",
            "markdown_report": "/v1/reports/risk",
            "pdf_report": "/v1/reports/risk/pdf",
        }
    )
