"""Single-screen demo narrative: upload → hazard → EAL → adaptation → avoided loss."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.portfolio import UniversalAsset

# Honesty stamp for Phase A stub curves (product label; catalogue is stub_global_mdr v0.1.0).
SYNTHETIC_CALIBRATION_BADGE = "synthetic calibration v0.2"

# Citable English methodology note (Phase A). Bump with docs/methodology/GEORISK_ENGINE_METHODOLOGY.md.
METHODOLOGY_DOCUMENT_VERSION = "georisk-methodology-v0.4.0"
METHODOLOGY_DOCUMENT_PATH = "docs/methodology/GEORISK_ENGINE_METHODOLOGY.md"

EXCLUSION_MISSING_COORDINATES = "missing coordinates — geocoding not yet supported"
EXCLUSION_MAX_ASSETS_CAP = "beyond demo max_assets cap"


class MethodologyStamp(BaseModel):
    """Version ids attached to every financial figure in the demo."""

    document: str = METHODOLOGY_DOCUMENT_VERSION
    document_path: str = METHODOLOGY_DOCUMENT_PATH
    expected_loss: str
    damage_curves: str
    adaptation_evidence: str
    pipeline: str
    calibration_badge: str = SYNTHETIC_CALIBRATION_BADGE


class VerificationHazardStep(BaseModel):
    hazard_id: str
    intensity: float
    curve_id: str
    mdr: float
    attribution_share: float
    loss: float
    formula: str


class VerificationWalkthrough(BaseModel):
    """Audit story for one featured asset — independent recompute vs pipeline trail."""

    asset_id: str
    valuation_date: date
    asset_value: float
    building_type: str
    use_class: str
    trail_record_id: str
    trail_record_hash: str
    methodology_version: str
    damage_curves_version: str
    calibration_badge: str = SYNTHETIC_CALIBRATION_BADGE
    vulnerability: float
    combined_mdr: float
    steps: list[VerificationHazardStep]
    pipeline_eal: float
    independent_eal: float
    eal_2030_independent: float | None = None
    eal_2050_independent: float | None = None
    agreement: str
    sample_report_path: str = "docs/verification/sample_verification_report.md"
    sample_report_url: str = (
        "https://github.com/ebru0zpolat/georisk-engine/blob/main/"
        "docs/verification/sample_verification_report.md"
    )


class ExcludedAssetRow(BaseModel):
    """One uploaded asset that was not analyzed — never silently dropped."""

    asset_id: str
    reason: str


class CoverageSummary(BaseModel):
    """Explicit analyzed vs excluded counts for the demo run."""

    submitted_count: int = Field(..., ge=0)
    analyzed_count: int = Field(..., ge=0)
    excluded_count: int = Field(..., ge=0)
    message: str = Field(
        ...,
        description='e.g. "Analyzed 90 of 120 assets (30 excluded: no coordinates)"',
    )
    eal_scope: str = "analyzed assets only"
    reason_counts: dict[str, int] = Field(default_factory=dict)
    excluded: list[ExcludedAssetRow] = Field(default_factory=list)


class PortfolioDemoAssetRow(BaseModel):
    asset_id: str
    building_type: str
    use_class: str
    asset_value: float
    hazard_composite: float
    eal_absolute: float
    eal_2030: float | None = None
    eal_2050: float | None = None
    recommended_measure_id: str | None = None
    avoided_loss: float
    residual_eal: float
    eal_audit_record_id: str | None = None
    methodology_version: str | None = None
    damage_curves_version: str | None = None
    calibration_badge: str = SYNTHETIC_CALIBRATION_BADGE


class PortfolioDemoNarrative(BaseModel):
    """One-screen story payload — no map geometry."""

    portfolio_id: str
    valuation_date: date
    asset_count: int = Field(
        ...,
        description="Analyzed asset count (same as coverage.analyzed_count).",
    )
    source: str = "upload"
    currency: str = Field(
        default="TRY",
        description="Display currency for money figures (TRY / EUR). Values are fictional.",
    )
    methodology: MethodologyStamp
    calibration_badge: str = SYNTHETIC_CALIBRATION_BADGE
    coverage: CoverageSummary
    upload: dict[str, Any]
    hazard: dict[str, Any]
    expected_loss: dict[str, Any]
    adaptation: dict[str, Any]
    avoided_loss: dict[str, Any]
    verification: VerificationWalkthrough | None = None
    assets: list[PortfolioDemoAssetRow] = Field(
        ...,
        description="Analyzed assets only.",
    )
    honesty_note: str | None = Field(
        default=None,
        description="Optional synthetic / pack-calibration disclaimer for golden demos.",
    )


class PortfolioDemoRunRequest(BaseModel):
    valuation_date: date
    assets: list[UniversalAsset] = Field(..., min_length=1, max_length=500)
    portfolio_id: str | None = None
    max_assets: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Cap for demo latency; golden portfolio fits in 100.",
    )


class PortfolioDemoRunResponse(BaseModel):
    narrative: PortfolioDemoNarrative
    #: Persisted run (``runs`` row + sealed audit records); ``None`` on the
    #: local file-trail fallback, where no run row exists.
    run_id: str | None = None


__all__ = [
    "EXCLUSION_MAX_ASSETS_CAP",
    "EXCLUSION_MISSING_COORDINATES",
    "SYNTHETIC_CALIBRATION_BADGE",
    "CoverageSummary",
    "ExcludedAssetRow",
    "MethodologyStamp",
    "PortfolioDemoAssetRow",
    "PortfolioDemoNarrative",
    "PortfolioDemoRunRequest",
    "PortfolioDemoRunResponse",
    "VerificationHazardStep",
    "VerificationWalkthrough",
]
