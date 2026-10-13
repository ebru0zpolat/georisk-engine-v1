"""Universal RE / mortgage / collateral asset schema and portfolio upload contract (§3.1).

Builds on ``RiskBatchAsset`` field set; portfolio rows require value/type/use and
address **or** coordinates. Includes Annex B.1 ``valuation_date`` and B.7 adaptation fields.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.adaptation import AdaptationOutcome, MeasureStatus
from app.schemas.risk import RiskBatchAsset

PORTFOLIO_MIN_ASSETS = 1
PORTFOLIO_MAX_ASSETS = 500


class UniversalAsset(BaseModel):
    """Country-agnostic P0 asset row — stricter than batch (required §3.1 fields)."""

    asset_id: str = Field(..., min_length=1, description="Client asset identifier.")
    address: str | None = Field(default=None)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    asset_value: float = Field(..., gt=0)
    building_type: str = Field(..., min_length=1)
    use_class: str = Field(..., min_length=1)
    construction_year: int | None = Field(default=None, ge=1800, le=2100)
    floors: int | None = Field(default=None, ge=0, le=200)
    insurance_coverage: float | None = Field(default=None, ge=0)
    existing_adaptation_measures: list[str] = Field(default_factory=list)
    ltv: float | None = Field(default=None, ge=0, le=2)
    loan_id: str | None = None
    adaptation: AdaptationOutcome | None = None

    @field_validator("address")
    @classmethod
    def strip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def require_location(self) -> Self:
        has_coords = self.latitude is not None and self.longitude is not None
        if has_coords or bool(self.address):
            return self
        raise ValueError("Each asset requires address or both latitude and longitude.")

    @model_validator(mode="after")
    def coords_paired(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together.")
        return self

    def to_batch_asset(self) -> RiskBatchAsset:
        """Project to ``RiskBatchAsset`` when coordinates are present (batch scoring path)."""
        if self.latitude is None or self.longitude is None:
            raise ValueError(
                f"Asset {self.asset_id!r} has no coordinates; cannot convert to RiskBatchAsset."
            )
        return RiskBatchAsset(
            id=self.asset_id,
            lat=self.latitude,
            lon=self.longitude,
            address=self.address,
            asset_value=self.asset_value,
            building_type=self.building_type,
            use_class=self.use_class,
            construction_year=self.construction_year,
            floors=self.floors,
            insurance_coverage=self.insurance_coverage,
            existing_adaptation_measures=list(self.existing_adaptation_measures),
            ltv=self.ltv,
            loan_id=self.loan_id,
            adaptation=self.adaptation,
        )


class PortfolioUploadRequest(BaseModel):
    """JSON portfolio ingest (same contract as CSV / GeoJSON upload)."""

    valuation_date: date = Field(
        ...,
        description=(
            "As-of date for analysis (Annex B.1). Pipeline must use only data available "
            "on or before this date — no lookahead leakage."
        ),
    )
    assets: list[UniversalAsset] = Field(
        ...,
        min_length=PORTFOLIO_MIN_ASSETS,
        max_length=PORTFOLIO_MAX_ASSETS,
    )
    portfolio_id: str | None = None


class PortfolioUploadResponse(BaseModel):
    """Normalised echo of an accepted portfolio upload (no scoring yet)."""

    portfolio_id: str
    valuation_date: date
    asset_count: int
    assets: list[UniversalAsset]
    source: Literal["json", "csv", "geojson"]
    accepted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def new_portfolio_id() -> str:
    return f"pf_{uuid4().hex[:12]}"


__all__ = [
    "AdaptationOutcome",
    "MeasureStatus",
    "PORTFOLIO_MAX_ASSETS",
    "PORTFOLIO_MIN_ASSETS",
    "PortfolioUploadRequest",
    "PortfolioUploadResponse",
    "UniversalAsset",
    "new_portfolio_id",
]
