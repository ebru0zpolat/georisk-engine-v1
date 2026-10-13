"""Stub implementations of the five-layer contract (deterministic, no I/O)."""

from __future__ import annotations

import hashlib

from app.pipeline.contract import (
    LAYER_ORDER,
    AdaptationEvidenceResult,
    ExposureResult,
    FinancialTranslationResult,
    FiveLayerPipelineResult,
    HazardResult,
    PipelineContext,
    VulnerabilityResult,
    assert_complete_five_layer_result,
)
from app.services.audit_trail import AppendOnlyAuditTrail


def _unit(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


class StubHazard:
    def run(self, ctx: PipelineContext) -> HazardResult:
        lat = ctx.asset.latitude if ctx.asset.latitude is not None else 0.0
        lon = ctx.asset.longitude if ctx.asset.longitude is not None else 0.0
        components: dict[str, float] = {}
        # Active modules (methodology v0.4.0): flood, extreme heat, wildfire and
        # earthquake — same set as five_layer_pipeline._HAZARDS. Drought / storm stay roadmap.
        for name in ("flood", "extreme_heat", "wildfire", "earthquake"):
            seed = f"{name}|{lat:.5f}|{lon:.5f}|{ctx.valuation_date.isoformat()}"
            components[name] = round(_unit(seed), 6)
        composite = round(sum(components.values()) / len(components), 6)
        return HazardResult(
            components=components,
            composite_intensity=composite,
            data_versions={"hazard_stub": "hazard-stub-v0.2"},
        )


class StubExposure:
    def run(self, ctx: PipelineContext, hazard: HazardResult) -> ExposureResult:
        _ = hazard  # dependency present for contract ordering
        a = ctx.asset
        return ExposureResult(
            asset_id=a.asset_id,
            asset_value=a.asset_value,
            building_type=a.building_type,
            use_class=a.use_class,
            latitude=a.latitude,
            longitude=a.longitude,
            address=a.address,
            ltv=a.ltv,
        )


class StubVulnerability:
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
    ) -> VulnerabilityResult:
        _ = hazard, exposure
        year = ctx.asset.construction_year or 2000
        age = min(0.35, max(0.0, (2026 - year) / 200.0))
        floors = min(0.15, (ctx.asset.floors or 1) / 100.0)
        building = ctx.asset.building_type.lower()
        base = {
            "hotel": 0.55,
            "apartment": 0.45,
            "office": 0.40,
            "retail": 0.50,
        }.get(building, 0.50)
        measures = list(ctx.asset.existing_adaptation_measures or [])
        capacity = min(0.4, 0.08 * len(measures))
        return VulnerabilityResult(
            fragility_factor=round(min(1.0, base + age + floors), 6),
            adaptation_capacity_factor=round(capacity, 6),
            construction_year=ctx.asset.construction_year,
            floors=ctx.asset.floors,
            existing_measures=measures,
        )


class StubFinancialTranslation:
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
        vulnerability: VulnerabilityResult,
    ) -> FinancialTranslationResult:
        effective = max(
            0.05,
            vulnerability.fragility_factor * (1.0 - vulnerability.adaptation_capacity_factor),
        )
        eal = round(exposure.asset_value * hazard.composite_intensity * effective, 2)
        eal_pct = round((eal / exposure.asset_value) * 100.0, 6)
        risk = round(min(100.0, hazard.composite_intensity * effective * 100.0), 4)
        if ctx.asset.insurance_coverage is None:
            insurability: str = "protection_gap"
        elif ctx.asset.insurance_coverage >= exposure.asset_value:
            insurability = "insured"
        elif ctx.asset.insurance_coverage > 0:
            insurability = "insurable_with_conditions"
        else:
            insurability = "protection_gap"
        return FinancialTranslationResult(
            eal_absolute=eal,
            eal_pct_of_value=eal_pct,
            risk_score=risk,
            # No forward-looking output without horizon-specific climate data.
            scenario_deltas={},
            collateral_sensitivity=round(min(1.0, eal / exposure.asset_value), 6),
            insurability=insurability,  # type: ignore[arg-type]
        )


class StubAdaptationEvidence:
    def run(
        self,
        ctx: PipelineContext,
        hazard: HazardResult,
        exposure: ExposureResult,
        vulnerability: VulnerabilityResult,
        financial: FinancialTranslationResult,
    ) -> AdaptationEvidenceResult:
        _ = hazard, vulnerability
        catalogue = [
            ("cool-roof-v1", "Cool roof", 0.015, 0.18),
            ("flood-barrier-v1", "Flood barrier", 0.04, 0.35),
            ("drainage-upgrade-v1", "Drainage upgrade", 0.025, 0.22),
            ("seismic-retrofit-v1", "Seismic retrofit", 0.08, 0.30),
            ("wildfire-defensible-space-v1", "Defensible space", 0.012, 0.10),
        ]
        measures: list[dict] = []
        for measure_id, label, cost_frac, reduction in catalogue:
            cost = round(exposure.asset_value * cost_frac, 2)
            avoided = round(financial.eal_absolute * reduction, 2)
            measures.append(
                {
                    "measure_id": measure_id,
                    "label": label,
                    "cost": cost,
                    "risk_reduction_fraction": reduction,
                    "avoided_loss": avoided,
                    "residual_eal": round(max(0.0, financial.eal_absolute - avoided), 2),
                }
            )
        best = max(measures, key=lambda m: m["avoided_loss"] / m["cost"] if m["cost"] else 0.0)
        return AdaptationEvidenceResult(
            measures=measures,
            recommended_measure_id=best["measure_id"],
            avoided_loss=best["avoided_loss"],
            residual_eal=best["residual_eal"],
            residual_risk_score=round(
                financial.risk_score * (1.0 - best["risk_reduction_fraction"]), 4
            ),
        )


class StubFiveLayerPipeline:
    """Reference stub pipeline that satisfies ``FiveLayerPipeline``.

    FinancialTranslation uses the expected-loss engine (damage curves + EAL +
    2030/2050 deltas) and writes an audit-trail record on every run.
    """

    def __init__(self, *, trail: AppendOnlyAuditTrail | None = None) -> None:
        # Local imports avoid circular import: loss/adaptation → pipeline.contract.
        from app.adaptation.evidence import CatalogueAdaptationEvidence
        from app.loss.expected_loss import ExpectedLossFinancialTranslation

        self.hazard = StubHazard()
        self.exposure = StubExposure()
        self.vulnerability = StubVulnerability()
        self.financial_translation = ExpectedLossFinancialTranslation(trail=trail)
        self.adaptation_evidence = CatalogueAdaptationEvidence(trail=trail)
        self._trail = trail

    def run(self, ctx: PipelineContext) -> FiveLayerPipelineResult:
        hazard = self.hazard.run(ctx)
        exposure = self.exposure.run(ctx, hazard)
        vulnerability = self.vulnerability.run(ctx, hazard, exposure)
        financial = self.financial_translation.run(ctx, hazard, exposure, vulnerability)
        adaptation = self.adaptation_evidence.run(
            ctx, hazard, exposure, vulnerability, financial
        )
        result = FiveLayerPipelineResult(
            context=ctx,
            hazard=hazard,
            exposure=exposure,
            vulnerability=vulnerability,
            financial_translation=financial,
            adaptation_evidence=adaptation,
        )
        assert_complete_five_layer_result(result)
        assert result.layer_names() == LAYER_ORDER
        return result


__all__ = [
    "StubAdaptationEvidence",
    "StubExposure",
    "StubFinancialTranslation",
    "StubFiveLayerPipeline",
    "StubHazard",
    "StubVulnerability",
]
