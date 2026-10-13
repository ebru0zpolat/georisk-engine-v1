"""Adaptation evidence: catalogue → cost → risk reduction → residual → avoided loss."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.adaptation.catalogue import (
    ADAPTATION_CATALOGUE_VERSION,
    CatalogueMeasure,
    get_default_catalogue,
)
from app.adaptation.evidence import (
    ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
    CatalogueAdaptationEvidence,
    compute_adaptation_evidence,
    evaluate_measure,
)
from app.pipeline.contract import (
    AdaptationEvidence,
    ExposureResult,
    FinancialTranslationResult,
    HazardResult,
    PipelineContext,
    VulnerabilityResult,
)
from app.pipeline.stubs import StubFiveLayerPipeline
from app.schemas.adaptation import AdaptationOutcome, MeasureStatus
from app.schemas.portfolio import UniversalAsset
from app.services.audit_trail import AppendOnlyAuditTrail


def _ctx(**overrides: object) -> PipelineContext:
    data = dict(
        asset_id="AD-01",
        latitude=36.9,
        longitude=30.7,
        asset_value=2_000_000.0,
        building_type="hotel",
        use_class="tourism",
        adaptation=AdaptationOutcome(
            measure_id="flood-barrier-v1",
            measure_status=MeasureStatus.recommended,
            share_outcome_consented=False,
            anonymise_in_aggregate=True,
        ),
    )
    data.update(overrides)
    return PipelineContext(
        asset=UniversalAsset(**data),  # type: ignore[arg-type]
        valuation_date=date(2021, 7, 1),
        parameters={"pack": "pack-tr"},
    )


def _inputs(
    *,
    eal: float = 400_000.0,
    risk_score: float = 55.0,
) -> tuple[HazardResult, ExposureResult, VulnerabilityResult, FinancialTranslationResult]:
    hazard = HazardResult(
        components={"flood": 0.7, "extreme_heat": 0.4},
        composite_intensity=0.55,
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
    )
    exposure = ExposureResult(
        asset_id="AD-01",
        asset_value=2_000_000.0,
        building_type="hotel",
        use_class="tourism",
        latitude=36.9,
        longitude=30.7,
    )
    vulnerability = VulnerabilityResult(
        fragility_factor=0.5,
        adaptation_capacity_factor=0.1,
    )
    financial = FinancialTranslationResult(
        eal_absolute=eal,
        eal_pct_of_value=20.0,
        risk_score=risk_score,
        scenario_deltas={"2030": eal * 0.9, "2050": eal},
        collateral_sensitivity=0.2,
        insurability="protection_gap",
    )
    return hazard, exposure, vulnerability, financial


def test_catalogue_has_versioned_measures() -> None:
    catalogue = get_default_catalogue()
    assert len(catalogue) >= 3
    assert all(isinstance(m, CatalogueMeasure) for m in catalogue)
    assert ADAPTATION_CATALOGUE_VERSION.startswith("adaptation-catalogue-")


def test_evaluate_measure_chain_cost_reduction_residual_avoided() -> None:
    hazard, exposure, _, financial = _inputs(eal=500_000.0, risk_score=60.0)
    measure = CatalogueMeasure(
        measure_id="test-barrier",
        label="Test barrier",
        hazards_addressed=("flood",),
        cost_fraction_of_value=0.05,
        risk_reduction_fraction=0.40,
    )
    evaluated = evaluate_measure(
        measure,
        exposure=exposure,
        financial=financial,
        hazard=hazard,
        ctx=_ctx(),
    )
    assert evaluated.cost == 100_000.0  # 5% of 2M
    assert evaluated.avoided_loss > 0
    assert evaluated.residual_eal == round(financial.eal_absolute - evaluated.avoided_loss, 2)
    assert evaluated.residual_eal < financial.eal_absolute
    assert evaluated.residual_risk_score < financial.risk_score
    assert evaluated.roi_avoided_per_cost == round(evaluated.avoided_loss / evaluated.cost, 6)


def test_compute_adaptation_evidence_writes_audit_trail() -> None:
    trail = AppendOnlyAuditTrail()
    hazard, exposure, vulnerability, financial = _inputs()
    result = compute_adaptation_evidence(
        ctx=_ctx(),
        hazard=hazard,
        exposure=exposure,
        vulnerability=vulnerability,
        financial=financial,
        trail=trail,
        timestamp=datetime(2026, 8, 5, 16, 0, tzinfo=timezone.utc),
        parameters={"pack": "pack-tr"},
    )
    assert result.methodology_version == ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
    assert result.catalogue_version == ADAPTATION_CATALOGUE_VERSION
    assert result.recommended_measure_id is not None
    assert result.avoided_loss >= 0
    assert result.residual_eal >= 0
    assert result.residual_eal <= financial.eal_absolute + 1e-9
    assert len(result.measures) == len(get_default_catalogue())

    record = trail.get(result.audit_record_id)
    assert record is not None
    assert record.methodology_version == ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
    assert record.data_versions["adaptation_catalogue"] == ADAPTATION_CATALOGUE_VERSION
    assert record.parameters["pack"] == "pack-tr"
    assert record.timestamp == datetime(2026, 8, 5, 16, 0, tzinfo=timezone.utc)
    assert record.outputs["avoided_loss"] == result.avoided_loss
    assert record.outputs["residual_eal"] == result.residual_eal
    assert trail.verify_chain()


def test_recommendation_prefers_higher_roi() -> None:
    trail = AppendOnlyAuditTrail()
    catalogue = (
        CatalogueMeasure(
            measure_id="expensive-weak",
            label="Expensive",
            hazards_addressed=("flood",),
            cost_fraction_of_value=0.20,
            risk_reduction_fraction=0.10,
        ),
        CatalogueMeasure(
            measure_id="cheap-strong",
            label="Cheap",
            hazards_addressed=("flood",),
            cost_fraction_of_value=0.02,
            risk_reduction_fraction=0.25,
        ),
    )
    hazard, exposure, vulnerability, financial = _inputs()
    result = compute_adaptation_evidence(
        ctx=_ctx(),
        hazard=hazard,
        exposure=exposure,
        vulnerability=vulnerability,
        financial=financial,
        catalogue=catalogue,
        trail=trail,
    )
    assert result.recommended_measure_id == "cheap-strong"


def test_annex_b7_outcome_attached_to_matching_measure() -> None:
    trail = AppendOnlyAuditTrail()
    hazard, exposure, vulnerability, financial = _inputs()
    result = compute_adaptation_evidence(
        ctx=_ctx(),
        hazard=hazard,
        exposure=exposure,
        vulnerability=vulnerability,
        financial=financial,
        trail=trail,
    )
    barrier = next(m for m in result.measures if m.measure_id == "flood-barrier-v1")
    assert barrier.outcome is not None
    assert barrier.outcome.measure_status == MeasureStatus.recommended


def test_adapter_satisfies_adaptation_evidence_protocol() -> None:
    trail = AppendOnlyAuditTrail()
    adapter = CatalogueAdaptationEvidence(trail=trail)
    assert isinstance(adapter, AdaptationEvidence)
    hazard, exposure, vulnerability, financial = _inputs()
    out = adapter.run(_ctx(), hazard, exposure, vulnerability, financial)
    assert out.layer == "AdaptationEvidence"
    assert out.recommended_measure_id is not None
    assert adapter.last_result is not None
    assert trail.get(adapter.last_result.audit_record_id) is not None


def test_stub_pipeline_uses_catalogue_adaptation_evidence() -> None:
    trail = AppendOnlyAuditTrail()
    result = StubFiveLayerPipeline(trail=trail).run(_ctx())
    ae = result.adaptation_evidence
    assert ae.layer == "AdaptationEvidence"
    assert ae.recommended_measure_id is not None
    assert ae.avoided_loss >= 0
    assert ae.residual_eal >= 0
    assert len(ae.measures) >= 3
    # Two audit writes: expected-loss + adaptation evidence
    assert len(trail) >= 2
    adapter = StubFiveLayerPipeline(trail=AppendOnlyAuditTrail()).adaptation_evidence
    assert isinstance(adapter, CatalogueAdaptationEvidence)
