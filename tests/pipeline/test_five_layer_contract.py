"""Contract tests for Hazard → Exposure → Vulnerability → FinancialTranslation → AdaptationEvidence."""

from __future__ import annotations

from datetime import date

import pytest

from app.pipeline.contract import (
    LAYER_ORDER,
    AdaptationEvidence,
    Exposure,
    FinancialTranslation,
    FiveLayerPipeline,
    FiveLayerPipelineResult,
    Hazard,
    PipelineContext,
    Vulnerability,
    assert_complete_five_layer_result,
)
from app.pipeline.stubs import (
    StubAdaptationEvidence,
    StubExposure,
    StubFinancialTranslation,
    StubFiveLayerPipeline,
    StubHazard,
    StubVulnerability,
)
from app.schemas.portfolio import UniversalAsset


def _ctx(**asset_overrides: object) -> PipelineContext:
    data = dict(
        asset_id="CONTRACT-01",
        latitude=36.8969,
        longitude=30.7133,
        asset_value=2_500_000,
        building_type="hotel",
        use_class="tourism",
        construction_year=2008,
        floors=6,
        insurance_coverage=500_000,
        existing_adaptation_measures=["shutters"],
    )
    data.update(asset_overrides)
    return PipelineContext(
        asset=UniversalAsset(**data),  # type: ignore[arg-type]
        valuation_date=date(2021, 7, 1),
        parameters={"contract_test": True},
    )


def test_layer_order_constant() -> None:
    assert LAYER_ORDER == (
        "Hazard",
        "Exposure",
        "Vulnerability",
        "FinancialTranslation",
        "AdaptationEvidence",
    )


def test_stub_layers_satisfy_protocols() -> None:
    assert isinstance(StubHazard(), Hazard)
    assert isinstance(StubExposure(), Exposure)
    assert isinstance(StubVulnerability(), Vulnerability)
    assert isinstance(StubFinancialTranslation(), FinancialTranslation)
    assert isinstance(StubAdaptationEvidence(), AdaptationEvidence)
    assert isinstance(StubFiveLayerPipeline(), FiveLayerPipeline)


def test_stub_pipeline_returns_all_five_layers_in_order() -> None:
    pipeline = StubFiveLayerPipeline()
    result = pipeline.run(_ctx())
    assert isinstance(result, FiveLayerPipelineResult)
    assert result.layer_names() == LAYER_ORDER
    assert_complete_five_layer_result(result)


def test_each_layer_result_carries_layer_discriminator() -> None:
    result = StubFiveLayerPipeline().run(_ctx())
    assert result.hazard.layer == "Hazard"
    assert result.exposure.layer == "Exposure"
    assert result.vulnerability.layer == "Vulnerability"
    assert result.financial_translation.layer == "FinancialTranslation"
    assert result.adaptation_evidence.layer == "AdaptationEvidence"


def test_financial_translation_produces_eal() -> None:
    result = StubFiveLayerPipeline().run(_ctx())
    ft = result.financial_translation
    assert ft.eal_absolute >= 0
    assert ft.eal_pct_of_value >= 0
    assert ft.scenario_deltas == {}
    assert ft.insurability in {
        "insured",
        "insurable_with_conditions",
        "protection_gap",
    }


def test_adaptation_evidence_produces_avoided_loss() -> None:
    result = StubFiveLayerPipeline().run(_ctx())
    ae = result.adaptation_evidence
    assert ae.recommended_measure_id is not None
    assert ae.avoided_loss >= 0
    assert ae.residual_eal >= 0
    assert ae.residual_eal <= result.financial_translation.eal_absolute + 1e-9
    assert len(ae.measures) >= 1


def test_pipeline_is_deterministic() -> None:
    pipeline = StubFiveLayerPipeline()
    ctx = _ctx()
    a = pipeline.run(ctx)
    b = pipeline.run(ctx)
    assert a.financial_translation.eal_absolute == b.financial_translation.eal_absolute
    assert a.adaptation_evidence.avoided_loss == b.adaptation_evidence.avoided_loss


def test_incomplete_result_fails_contract_assertion() -> None:
    result = StubFiveLayerPipeline().run(_ctx())
    # Tamper layer discriminator to simulate a mis-ordered / incomplete product.
    broken = result.model_copy(
        update={
            "adaptation_evidence": result.adaptation_evidence.model_copy(
                update={"layer": "Hazard"}  # type: ignore[arg-type]
            )
        }
    )
    with pytest.raises(AssertionError, match="Layer order mismatch"):
        assert_complete_five_layer_result(broken)


def test_manual_layer_chain_matches_orchestrator() -> None:
    """Call each Protocol in order — same contract as FiveLayerPipeline.run."""
    from app.adaptation.evidence import CatalogueAdaptationEvidence
    from app.loss.expected_loss import ExpectedLossFinancialTranslation
    from app.services.audit_trail import AppendOnlyAuditTrail

    ctx = _ctx()
    trail = AppendOnlyAuditTrail()
    h = StubHazard().run(ctx)
    e = StubExposure().run(ctx, h)
    v = StubVulnerability().run(ctx, h, e)
    f = ExpectedLossFinancialTranslation(trail=trail).run(ctx, h, e, v)
    a = CatalogueAdaptationEvidence(trail=trail).run(ctx, h, e, v, f)
    orchestrated = StubFiveLayerPipeline(trail=AppendOnlyAuditTrail()).run(ctx)
    assert h.composite_intensity == orchestrated.hazard.composite_intensity
    assert f.eal_absolute == orchestrated.financial_translation.eal_absolute
    assert a.avoided_loss == orchestrated.adaptation_evidence.avoided_loss


_ACTIVE = {"flood", "extreme_heat", "wildfire", "earthquake"}


def test_stub_hazard_emits_only_active_modules() -> None:
    """Methodology v0.4.0 active set; drought / storm stay roadmap and are never priced."""
    from app.loss.expected_loss import ExpectedLossFinancialTranslation
    from app.services.audit_trail import AppendOnlyAuditTrail

    ctx = _ctx()
    h = StubHazard().run(ctx)
    assert set(h.components.keys()) == _ACTIVE
    assert not {"drought", "storm"} & set(h.components)

    ft = ExpectedLossFinancialTranslation(trail=AppendOnlyAuditTrail())
    e = StubExposure().run(ctx, h)
    v = StubVulnerability().run(ctx, h, e)
    ft.run(ctx, h, e, v)
    assert ft.last_result is not None
    assert not {"drought", "storm"} & set(ft.last_result.eal_by_hazard)
    assert set(ft.last_result.eal_by_hazard.keys()) <= _ACTIVE
