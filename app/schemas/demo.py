from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gee import GeeBaselineFeatures, GeeFeatures
from app.schemas.industrial_verification import IndustrialVerificationRef
from app.schemas.insights import Insight
from app.schemas.risk import ComponentScores


class DemoAsset(BaseModel):
    name: str
    sector: str
    latitude: float
    longitude: float
    radius_km: float


class DemoAssetOut(BaseModel):
    id: str
    name: str
    sector: str
    latitude: float
    longitude: float
    radius_km: float
    start_date: date | None = None
    end_date: date | None = None


class DemoSummary(BaseModel):
    overall_score: int
    risk_band: str
    headline: str


class DemoFeatures(BaseModel):
    gee: GeeFeatures
    oras5: dict[str, float]


class DemoBaselines(BaseModel):
    gee: GeeBaselineFeatures | None = None


class DemoReport(BaseModel):
    available: bool
    pdf_endpoint: str
    bundle_endpoint: str


class DemoAudit(BaseModel):
    audit_id: str
    generated_at: datetime
    model_version: str


class DemoResponse(BaseModel):
    demo_id: str
    asset: DemoAsset
    summary: DemoSummary
    components: ComponentScores
    features: DemoFeatures
    baselines: DemoBaselines
    flags: list[str]
    interpretation: str
    insights: list[Insight]
    report: DemoReport
    audit: DemoAudit
    industrial_verification: IndustrialVerificationRef | None = None
    emission_zscore: float = 0.0
    anomaly_flag: bool = False
    coastal_exposure_score: float = 0.0
    data_mode: Literal["live", "stub"] = Field(
        default="stub",
        description="``stub`` when any scoring connector used deterministic fallback features.",
    )
    production_eligible: bool = Field(
        default=False,
        description="False for stub demo scores; never implied production asset-risk scoring.",
    )
