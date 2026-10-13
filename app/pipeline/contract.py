"""Typed five-layer pipeline contract.

Layer order (inviolable):
  Hazard → Exposure → Vulnerability → FinancialTranslation → AdaptationEvidence

Implementations may be stubs; any conforming pipeline must traverse all five
layers. A result that stops at Hazard/Exposure is a map, not a product.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.schemas.portfolio import UniversalAsset
from app.schemas.source_manifest import SourceRecord

LAYER_ORDER: tuple[str, ...] = (
    "Hazard",
    "Exposure",
    "Vulnerability",
    "FinancialTranslation",
    "AdaptationEvidence",
)


class PipelineContext(BaseModel):
    """Shared inputs for every layer."""

    asset: UniversalAsset
    valuation_date: date
    parameters: dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = "five-layer-contract-v0.1"
    #: Per-source manifest carried through the layers (WP-4). Blocked sources
    #: stay listed here but must not feed any layer's number.
    sources: list[SourceRecord] = Field(default_factory=list)


class HazardResult(BaseModel):
    """Output of the Hazard layer."""

    layer: Literal["Hazard"] = "Hazard"
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Hazard id → intensity in [0, 1].",
    )
    composite_intensity: float = Field(..., ge=0.0, le=1.0)
    data_versions: dict[str, str] = Field(default_factory=dict)


class ExposureResult(BaseModel):
    """Output of the Exposure layer."""

    layer: Literal["Exposure"] = "Exposure"
    asset_id: str
    asset_value: float = Field(..., gt=0)
    building_type: str
    use_class: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    ltv: float | None = None


class VulnerabilityResult(BaseModel):
    """Output of the Vulnerability layer."""

    layer: Literal["Vulnerability"] = "Vulnerability"
    fragility_factor: float = Field(..., ge=0.0, le=1.0)
    adaptation_capacity_factor: float = Field(..., ge=0.0, le=1.0)
    construction_year: int | None = None
    floors: int | None = None
    existing_measures: list[str] = Field(default_factory=list)


class FinancialTranslationResult(BaseModel):
    """Output of the FinancialTranslation layer (EAL and related indicators)."""

    layer: Literal["FinancialTranslation"] = "FinancialTranslation"
    eal_absolute: float = Field(..., ge=0.0)
    eal_pct_of_value: float = Field(..., ge=0.0)
    risk_score: float = Field(..., ge=0.0, le=100.0)
    scenario_deltas: dict[str, float] = Field(default_factory=dict)
    collateral_sensitivity: float = Field(..., ge=0.0, le=1.0)
    insurability: Literal["insured", "insurable_with_conditions", "protection_gap"]


class AdaptationEvidenceResult(BaseModel):
    """Output of the AdaptationEvidence layer."""

    layer: Literal["AdaptationEvidence"] = "AdaptationEvidence"
    measures: list[dict[str, Any]] = Field(default_factory=list)
    recommended_measure_id: str | None = None
    avoided_loss: float = Field(..., ge=0.0)
    residual_eal: float = Field(..., ge=0.0)
    residual_risk_score: float = Field(..., ge=0.0, le=100.0)


class FiveLayerPipelineResult(BaseModel):
    """Full contract output — all five layers must be present."""

    context: PipelineContext
    hazard: HazardResult
    exposure: ExposureResult
    vulnerability: VulnerabilityResult
    financial_translation: FinancialTranslationResult
    adaptation_evidence: AdaptationEvidenceResult

    def layer_names(self) -> tuple[str, ...]:
        return (
            self.hazard.layer,
            self.exposure.layer,
            self.vulnerability.layer,
            self.financial_translation.layer,
            self.adaptation_evidence.layer,
        )


@runtime_checkable
class Hazard(Protocol):
    def run(self, ctx: PipelineContext) -> HazardResult: ...


@runtime_checkable
class Exposure(Protocol):
    def run(self, ctx: PipelineContext, hazard: HazardResult) -> ExposureResult: ...


@runtime_checkable
class Vulnerability(Protocol):
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
    ) -> VulnerabilityResult: ...


@runtime_checkable
class FinancialTranslation(Protocol):
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
        vulnerability: VulnerabilityResult,
    ) -> FinancialTranslationResult: ...


@runtime_checkable
class AdaptationEvidence(Protocol):
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
        vulnerability: VulnerabilityResult,
        financial: FinancialTranslationResult,
    ) -> AdaptationEvidenceResult: ...


@runtime_checkable
class FiveLayerPipeline(Protocol):
    """Orchestrator: must invoke layers in ``LAYER_ORDER`` and return all five results."""

    hazard: Hazard
    exposure: Exposure
    vulnerability: Vulnerability
    financial_translation: FinancialTranslation
    adaptation_evidence: AdaptationEvidence

    def run(self, ctx: PipelineContext) -> FiveLayerPipelineResult: ...


def assert_complete_five_layer_result(result: FiveLayerPipelineResult) -> None:
    """Raise ``AssertionError`` if the contract is incomplete or mis-ordered."""
    names = result.layer_names()
    if names != LAYER_ORDER:
        raise AssertionError(f"Layer order mismatch: got {names}, expected {LAYER_ORDER}")
    if result.financial_translation.eal_absolute < 0:
        raise AssertionError("FinancialTranslation.eal_absolute must be >= 0")
    if result.adaptation_evidence.residual_eal < 0:
        raise AssertionError("AdaptationEvidence.residual_eal must be >= 0")


__all__ = [
    "LAYER_ORDER",
    "AdaptationEvidence",
    "AdaptationEvidenceResult",
    "Exposure",
    "ExposureResult",
    "FinancialTranslation",
    "FinancialTranslationResult",
    "FiveLayerPipeline",
    "FiveLayerPipelineResult",
    "Hazard",
    "HazardResult",
    "PipelineContext",
    "Vulnerability",
    "VulnerabilityResult",
    "assert_complete_five_layer_result",
]
