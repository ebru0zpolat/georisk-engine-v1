from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from app.core.preset_registry import DEFAULT_PRESET_ID, is_preset_registered
from app.core.sector_registry import DEFAULT_SECTOR_ID
from app.schemas.adaptation import AdaptationOutcome
from app.schemas.baseline import BaselinePeriod, optional_paired_dates_or_none
from app.schemas.industrial_verification import IndustrialVerificationRef
from app.schemas.gee import GeeBaselineFeatures, GeeFeatures
from app.schemas.ocean import OceanFeatures


class RiskScoreLocation(BaseModel):
    """Echo of coordinates as ``lat`` / ``lon`` (enterprise contract)."""

    lat: float
    lon: float


class RiskScoreRequest(BaseModel):
    asset_name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=100)
    preset_id: str = Field(
        default=DEFAULT_PRESET_ID,
        min_length=1,
        description=(
            "Execution-level calibration id (e.g. ``industrial_v1``). "
            "Must be in ``REGISTERED_PRESET_IDS``. Defaults to ``industrial_v1`` for "
            "backward compatibility with clients that omit the field."
        ),
    )
    sector: str = Field(
        default=DEFAULT_SECTOR_ID,
        description=(
            "Logical sector label for reporting and future sector-specific weighting. "
            "Registered first-class ids live in ``app.core.sector_registry.REGISTERED_SECTOR_IDS``; "
            "extension checklist: ``docs/turkiye/sector-extensions.md``. "
            "Other strings remain valid for forward compatibility."
        ),
    )
    include_industrial_verification_ref: bool = Field(
        default=False,
        description=(
            "When true, response includes ``industrial_verification`` with the same ``audit_id`` "
            "and pointers to sealed operational pipelines (no extra Earth Engine cost)."
        ),
    )
    start_date: date | None = Field(
        default=None,
        description="Start of the assessment window for recent/current climate-related behavior.",
    )
    end_date: date | None = Field(
        default=None,
        description="End of the assessment window for recent/current climate-related behavior.",
    )
    baseline_start_date: date | None = Field(
        default=None,
        description=(
            "Start of the climatological baseline window; omit both baseline dates to use the "
            "configured default (e.g. 30-year WMO 1991–2020)."
        ),
    )
    baseline_end_date: date | None = Field(
        default=None,
        description=(
            "End of the climatological baseline window; omit both baseline dates to use the "
            "configured default (e.g. 30-year WMO 1991–2020)."
        ),
    )

    @model_validator(mode="after")
    def baseline_dates_paired(self) -> Self:
        optional_paired_dates_or_none(
            self.baseline_start_date,
            self.baseline_end_date,
            label="baseline",
        )
        if self.baseline_start_date is not None:
            BaselinePeriod(
                start_date=self.baseline_start_date,
                end_date=self.baseline_end_date,
            )
        if not is_preset_registered(self.preset_id):
            raise ValueError("Unknown preset_id")
        return self


class RiskReportRequest(RiskScoreRequest):
    """Same body as ``RiskScoreRequest``; reports default industrial bundle on."""

    include_industrial_verification_ref: bool = Field(
        default=True,
        description=(
            "When true (default for report endpoints), response/report includes "
            "``industrial_verification`` with the same ``audit_id``. Set false to omit."
        ),
    )


class ComponentScores(BaseModel):
    industrial: int
    pollution: int
    land: int
    ocean: int
    agriculture: int
    sensitivity: int
    flood: int | None = Field(
        default=None,
        description="Flood hazard score (0-100). Scaffold pending HydroSAT + MERIT DEM integration.",
    )
    heat: int | None = Field(
        default=None,
        description="Heat hazard score (0-100). Scaffold pending ERA5 land surface temperature integration.",
    )


class CompoundDriverScores(BaseModel):
    """Normalized [0, 1] drivers; ``risk_score`` equals the preset-weighted sum of these three."""

    heat: float = Field(ge=0.0, le=1.0)
    water_stress: float = Field(ge=0.0, le=1.0)
    climate: float = Field(ge=0.0, le=1.0)


class RiskScoreMeta(BaseModel):
    """Assessment metadata; ``updated_at`` is set when the engine finishes the score (UTC)."""

    updated_at: datetime
    resolution_km: float | None = Field(default=None)
    data_version: str | None = Field(default=None)


class RiskScoreResponse(BaseModel):
    asset_name: str
    latitude: float
    longitude: float
    radius_km: float
    sector: str
    preset_id: str
    overall_score: int
    risk_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted compound index in [0, 1]; equals preset weights · (heat, water_stress, climate).",
    )
    scores: CompoundDriverScores
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Single 0–1 confidence from driver spread (see scoring module).",
    )
    risk_band: str
    components: ComponentScores
    ocean_features: OceanFeatures
    gee_features: GeeFeatures
    gee_baseline: GeeBaselineFeatures | None = None
    flags: list[str]
    interpretation: str
    audit_id: str
    generated_at: datetime
    meta: RiskScoreMeta
    industrial_verification: IndustrialVerificationRef | None = None
    emission_zscore: float = Field(
        default=0.0,
        description="NO2 emission anomaly z-score proxy vs the climatological baseline.",
    )
    anomaly_flag: bool = Field(
        default=False,
        description="True when |emission_zscore| exceeds the anomaly threshold.",
    )
    coastal_exposure_score: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Coastal exposure score (0-1) from sea level rise rate and SST anomaly.",
    )
    data_mode: Literal["live", "stub"] = Field(
        default="stub",
        description=(
            "``stub`` when any scoring connector used deterministic fallback features; "
            "``live`` when ORAS5 Zarr and GEE are both configured."
        ),
    )
    production_eligible: bool = Field(
        default=False,
        description=(
            "False when data_mode=stub. Live reads also stay false while ORAS5 "
            "evidence gates remain open — never implied production asset-risk scoring."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def location(self) -> RiskScoreLocation:
        return RiskScoreLocation(lat=self.latitude, lon=self.longitude)

    @model_validator(mode="after")
    def compound_risk_identity(self) -> Self:
        from app.scoring.risk_score import compound_weights_for_preset

        wh, ww, wc = compound_weights_for_preset(self.preset_id)
        blended = wh * self.scores.heat + ww * self.scores.water_stress + wc * self.scores.climate
        if abs(blended - self.risk_score) > 1e-5:
            raise ValueError(
                "risk_score must equal weighted sum of scores.heat, scores.water_stress, scores.climate"
            )
        return self


class RiskBatchAsset(BaseModel):
    """One row in a synchronous batch / portfolio request.

    Scoring batch path still requires ``lat`` / ``lon``. Portfolio ingest (§3.1) may
    supply richer fields (``asset_value``, ``building_type``, ``use_class``, optional
    vulnerability / Annex B.7 adaptation fields); those are optional here so existing
    batch clients remain valid.
    """

    id: str = Field(..., min_length=1, description="Client asset identifier echoed in results.")
    lat: float = Field(..., description="Latitude (decimal degrees); out-of-range rows fail individually.")
    lon: float = Field(..., description="Longitude (decimal degrees).")
    address: str | None = Field(default=None, description="Optional street address (§3.1).")
    asset_value: float | None = Field(default=None, gt=0, description="Asset / collateral value.")
    building_type: str | None = Field(default=None, min_length=1)
    use_class: str | None = Field(default=None, min_length=1)
    construction_year: int | None = Field(default=None, ge=1800, le=2100)
    floors: int | None = Field(default=None, ge=0, le=200)
    insurance_coverage: float | None = Field(default=None, ge=0)
    existing_adaptation_measures: list[str] = Field(default_factory=list)
    ltv: float | None = Field(default=None, ge=0, le=2, description="Loan-to-value ratio (1.0 = 100%).")
    loan_id: str | None = None
    adaptation: AdaptationOutcome | None = Field(
        default=None,
        description="Annex B.7 adaptation-outcome fields.",
    )


class RiskBatchRequest(BaseModel):
    preset_id: str = Field(..., min_length=1)
    assets: list[RiskBatchAsset] = Field(..., min_length=1, max_length=500)
    sector: str = Field(default=DEFAULT_SECTOR_ID)
    radius_km: float = Field(
        default=10,
        gt=0,
        le=100,
        description="Applied to every batch row when building ``RiskScoreRequest``.",
    )
    include_industrial_verification_ref: bool = Field(default=False)
    valuation_date: date | None = Field(
        default=None,
        description=(
            "Optional as-of date for analysis (Annex B.1). When set, the pipeline must "
            "use only data available on or before this date — no lookahead leakage."
        ),
    )

    @model_validator(mode="after")
    def preset_ok(self) -> Self:
        if not is_preset_registered(self.preset_id):
            raise ValueError("Unknown preset_id")
        return self


class RiskBatchCoordinates(BaseModel):
    lat: float
    lon: float


class RiskBatchRowErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskBatchSummary(BaseModel):
    total_assets: int
    success_count: int
    failed_count: int
    avg_risk: float | None = Field(
        default=None,
        description="Mean overall score over successful rows; null if all rows failed.",
    )
    min_risk: int | None = None
    max_risk: int | None = None
    high_risk_ratio: float | None = Field(
        default=None,
        description="Share of successful rows with score >= 67; null if none.",
    )


class RiskBatchResultRow(BaseModel):
    id: str
    location: RiskBatchCoordinates
    success: bool
    risk: int | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_band: str | None = None
    sector: str | None = None
    preset_id: str | None = None
    error: RiskBatchRowErrorBody | None = None

    @model_validator(mode="after")
    def success_xor_error(self) -> Self:
        if self.success:
            if self.error is not None:
                raise ValueError("error must be null when success is true")
            if self.risk is None or self.risk_score is None or self.risk_band is None or self.sector is None:
                raise ValueError("risk, risk_score, risk_band, and sector are required when success is true")
        else:
            if self.error is None:
                raise ValueError("error is required when success is false")
            if self.risk is not None or self.risk_band is not None:
                raise ValueError("risk and risk_band must be null when success is false")
        return self


class RiskBatchMeta(BaseModel):
    preset_id: str
    processed_at: datetime


class RiskBatchResponse(BaseModel):
    summary: RiskBatchSummary
    results: list[RiskBatchResultRow]
    meta: RiskBatchMeta
