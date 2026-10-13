"""Adaptation evidence layer: catalogue → cost → risk reduction → residual → avoided loss.

Every successful evaluation appends a hash-chained audit-trail record.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.adaptation.catalogue import (
    ADAPTATION_CATALOGUE_VERSION,
    CatalogueMeasure,
    get_default_catalogue,
)
from app.pipeline.contract import (
    AdaptationEvidenceResult,
    ExposureResult,
    FinancialTranslationResult,
    HazardResult,
    PipelineContext,
    VulnerabilityResult,
)
from app.schemas.adaptation import AdaptationOutcome
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail

ADAPTATION_EVIDENCE_METHODOLOGY_VERSION = "adaptation-evidence-v0.1"


class EvaluatedMeasure(BaseModel):
    """One catalogue measure priced against the asset and baseline EAL."""

    measure_id: str
    label: str
    description: str = ""
    hazards_addressed: list[str] = Field(default_factory=list)
    cost: float = Field(..., ge=0.0)
    risk_reduction_fraction: float = Field(..., ge=0.0, le=1.0)
    avoided_loss: float = Field(..., ge=0.0)
    residual_eal: float = Field(..., ge=0.0)
    residual_risk_score: float = Field(..., ge=0.0, le=100.0)
    roi_avoided_per_cost: float = Field(
        ...,
        description="Avoided loss / cost (investment priority signal).",
    )
    outcome: AdaptationOutcome | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        # Keep AdaptationEvidenceResult.measures as plain dicts (contract).
        return payload


class AdaptationEvidenceOutput(BaseModel):
    """Full adaptation-evidence output including audit linkage."""

    methodology_version: str = ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
    catalogue_version: str = ADAPTATION_CATALOGUE_VERSION
    valuation_date: date
    asset_id: str
    measures: list[EvaluatedMeasure]
    recommended_measure_id: str | None = None
    avoided_loss: float = Field(..., ge=0.0)
    residual_eal: float = Field(..., ge=0.0)
    residual_risk_score: float = Field(..., ge=0.0, le=100.0)
    audit_record_id: str
    computed_at: datetime

    def to_adaptation_evidence_result(self) -> AdaptationEvidenceResult:
        return AdaptationEvidenceResult(
            measures=[m.as_dict() for m in self.measures],
            recommended_measure_id=self.recommended_measure_id,
            avoided_loss=self.avoided_loss,
            residual_eal=self.residual_eal,
            residual_risk_score=self.residual_risk_score,
        )


def _hazard_relevance(measure: CatalogueMeasure, hazard: HazardResult) -> float:
    """Boost reduction slightly when the measure targets the dominant hazards present."""
    if not measure.hazards_addressed or not hazard.components:
        return 1.0
    total = sum(hazard.components.values()) or 1.0
    addressed = sum(hazard.components.get(h, 0.0) for h in measure.hazards_addressed)
    share = addressed / total
    # Up to +15% effective reduction when measure aligns with active hazards.
    return 1.0 + 0.15 * share


def _attach_outcome(
    measure_id: str,
    ctx: PipelineContext,
) -> AdaptationOutcome | None:
    outcome = ctx.asset.adaptation
    if outcome is None:
        return None
    if outcome.measure_id in (None, measure_id):
        return outcome
    return None


def evaluate_measure(
    measure: CatalogueMeasure,
    *,
    exposure: ExposureResult,
    financial: FinancialTranslationResult,
    hazard: HazardResult,
    ctx: PipelineContext,
) -> EvaluatedMeasure:
    cost = round(exposure.asset_value * measure.cost_fraction_of_value, 2)
    relevance = _hazard_relevance(measure, hazard)
    reduction = min(1.0, measure.risk_reduction_fraction * relevance)
    avoided = round(financial.eal_absolute * reduction, 2)
    residual_eal = round(max(0.0, financial.eal_absolute - avoided), 2)
    residual_risk = round(financial.risk_score * (1.0 - reduction), 4)
    roi = round(avoided / cost, 6) if cost > 0 else 0.0
    return EvaluatedMeasure(
        measure_id=measure.measure_id,
        label=measure.label,
        description=measure.description,
        hazards_addressed=list(measure.hazards_addressed),
        cost=cost,
        risk_reduction_fraction=round(reduction, 6),
        avoided_loss=avoided,
        residual_eal=residual_eal,
        residual_risk_score=residual_risk,
        roi_avoided_per_cost=roi,
        outcome=_attach_outcome(measure.measure_id, ctx),
    )


def compute_adaptation_evidence(
    *,
    ctx: PipelineContext,
    hazard: HazardResult,
    exposure: ExposureResult,
    vulnerability: VulnerabilityResult,
    financial: FinancialTranslationResult,
    catalogue: tuple[CatalogueMeasure, ...] | None = None,
    trail: AppendOnlyAuditTrail | None = None,
    timestamp: datetime | None = None,
    parameters: dict[str, Any] | None = None,
) -> AdaptationEvidenceOutput:
    """Catalogue → cost → risk reduction → residual risk → avoided loss (+ audit write)."""
    _ = vulnerability  # reserved for capacity-adjusted residual in later methodology
    store = get_audit_trail() if trail is None else trail
    params = dict(parameters or {})
    measures_src = catalogue if catalogue is not None else get_default_catalogue()

    evaluated = [
        evaluate_measure(m, exposure=exposure, financial=financial, hazard=hazard, ctx=ctx)
        for m in measures_src
    ]
    if not evaluated:
        raise ValueError("Adaptation catalogue is empty.")

    # Investment priority: highest avoided loss per unit cost.
    ranked = sorted(evaluated, key=lambda m: m.roi_avoided_per_cost, reverse=True)
    best = ranked[0]

    ts = timestamp or datetime.now(timezone.utc)
    data_versions = {
        "adaptation_catalogue": ADAPTATION_CATALOGUE_VERSION,
        **dict(hazard.data_versions or {}),
    }
    outputs = {
        "recommended_measure_id": best.measure_id,
        "avoided_loss": best.avoided_loss,
        "residual_eal": best.residual_eal,
        "residual_risk_score": best.residual_risk_score,
        "measures": [m.as_dict() for m in evaluated],
    }
    inputs = {
        "asset_id": exposure.asset_id,
        "asset_value": exposure.asset_value,
        "baseline_eal": financial.eal_absolute,
        "baseline_risk_score": financial.risk_score,
        "hazard_components": hazard.components,
        "valuation_date": ctx.valuation_date.isoformat(),
        "catalogue_size": len(evaluated),
    }

    record = store.append(
        methodology_version=ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
        valuation_date=ctx.valuation_date,
        data_versions=data_versions,
        parameters=params,
        inputs=inputs,
        outputs=outputs,
        timestamp=ts,
    )

    return AdaptationEvidenceOutput(
        methodology_version=ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
        catalogue_version=ADAPTATION_CATALOGUE_VERSION,
        valuation_date=ctx.valuation_date,
        asset_id=exposure.asset_id,
        measures=evaluated,
        recommended_measure_id=best.measure_id,
        avoided_loss=best.avoided_loss,
        residual_eal=best.residual_eal,
        residual_risk_score=best.residual_risk_score,
        audit_record_id=record.record_id,
        computed_at=record.timestamp,
    )


class CatalogueAdaptationEvidence:
    """``AdaptationEvidence`` adapter backed by the catalogue engine + audit trail."""

    def __init__(
        self,
        *,
        catalogue: tuple[CatalogueMeasure, ...] | None = None,
        trail: AppendOnlyAuditTrail | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._trail = trail
        self.last_result: AdaptationEvidenceOutput | None = None

    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
        vulnerability: VulnerabilityResult,
        financial: FinancialTranslationResult,
    ) -> AdaptationEvidenceResult:
        result = compute_adaptation_evidence(
            ctx=ctx,
            hazard=hazard,
            exposure=exposure,
            vulnerability=vulnerability,
            financial=financial,
            catalogue=self._catalogue,
            trail=self._trail,
            parameters=dict(ctx.parameters),
        )
        self.last_result = result
        return result.to_adaptation_evidence_result()


__all__ = [
    "ADAPTATION_EVIDENCE_METHODOLOGY_VERSION",
    "AdaptationEvidenceOutput",
    "CatalogueAdaptationEvidence",
    "EvaluatedMeasure",
    "compute_adaptation_evidence",
    "evaluate_measure",
]
