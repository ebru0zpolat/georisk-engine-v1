"""Expected-loss layer adapter + damage-curve smoke (v0.3 API)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.loss.damage_curves import DAMAGE_CURVES_VERSION, mean_damage_ratio
from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_VERSION,
    ExpectedLossAssetInput,
    ExpectedLossFinancialTranslation,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.pipeline.contract import (
    ExposureResult,
    FinancialTranslation,
    HazardResult,
    PipelineContext,
    VulnerabilityResult,
)
from app.pipeline.stubs import StubFiveLayerPipeline
from app.schemas.portfolio import UniversalAsset
from app.services.audit_trail import AppendOnlyAuditTrail


def _ctx(asset_value: float = 2_000_000.0) -> PipelineContext:
    return PipelineContext(
        asset=UniversalAsset(
            asset_id="EL-01",
            latitude=36.9,
            longitude=30.7,
            asset_value=asset_value,
            building_type="hotel",
            use_class="tourism",
            construction_year=2005,
            floors=8,
            insurance_coverage=500_000,
        ),
        valuation_date=date(2021, 7, 1),
        parameters={"scenario": "ssp245"},
    )


def _layers(
    *,
    intensity: float = 0.6,
    asset_value: float = 2_000_000.0,
) -> tuple[HazardResult, ExposureResult, VulnerabilityResult]:
    hazard = HazardResult(
        components={"flood": intensity, "extreme_heat": intensity * 0.8},
        composite_intensity=round((intensity + intensity * 0.8) / 2, 6),
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
    )
    exposure = ExposureResult(
        asset_id="EL-01",
        asset_value=asset_value,
        building_type="hotel",
        use_class="tourism",
        latitude=36.9,
        longitude=30.7,
    )
    vulnerability = VulnerabilityResult(
        fragility_factor=0.55,
        adaptation_capacity_factor=0.08,
        construction_year=2005,
        floors=8,
    )
    return hazard, exposure, vulnerability


def _hazards(intensity: float = 0.6) -> HazardScenarioIntensities:
    current = {"flood": intensity, "extreme_heat": intensity * 0.8}
    # Explicit caller-supplied test fixtures; production adapters never derive these.
    h2030 = {key: value * 0.9 for key, value in current.items()}
    h2050 = {key: min(1.0, value * 1.1) for key, value in current.items()}
    return HazardScenarioIntensities(
        current=current,
        horizon_2030=h2030,
        horizon_2050=h2050,
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
        as_of=date(2021, 7, 1),
    )


def _asset(asset_value: float = 2_000_000.0) -> ExpectedLossAssetInput:
    return ExpectedLossAssetInput(
        asset_id="EL-01",
        asset_value=asset_value,
        building_type="hotel",
        use_class="tourism",
        fragility_factor=0.55,
        adaptation_capacity_factor=0.08,
        insurance_coverage=500_000,
    )


def test_damage_curve_mdr_rises_with_intensity() -> None:
    low, _ = mean_damage_ratio(building_type="office", intensity=0.2, hazard_id="flood")
    high, _ = mean_damage_ratio(building_type="office", intensity=0.9, hazard_id="flood")
    assert high > low
    assert 0.0 <= low <= 1.0 and 0.0 <= high <= 1.0


def test_damage_curves_differ_by_building_type() -> None:
    hotel, _ = mean_damage_ratio(building_type="hotel", intensity=0.7, hazard_id="flood")
    office, _ = mean_damage_ratio(building_type="office", intensity=0.7, hazard_id="flood")
    assert hotel != office


def test_compute_expected_loss_writes_audit_trail() -> None:
    trail = AppendOnlyAuditTrail()
    result = compute_expected_loss(
        asset=_asset(),
        hazards=_hazards(),
        valuation_date=date(2021, 7, 1),
        trail=trail,
        timestamp=datetime(2026, 8, 5, 15, 0, tzinfo=timezone.utc),
        parameters={"scenario": "ssp245"},
    )
    assert result.eal_absolute >= 0
    assert "2030" in result.scenario_eal and "2050" in result.scenario_eal
    assert result.methodology_version == EXPECTED_LOSS_METHODOLOGY_VERSION
    assert result.damage_curves_version == DAMAGE_CURVES_VERSION

    record = trail.get(result.audit_record_id)
    assert record is not None
    assert record.methodology_version == EXPECTED_LOSS_METHODOLOGY_VERSION
    assert record.data_versions["damage_curves"] == DAMAGE_CURVES_VERSION
    assert record.parameters["scenario"] == "ssp245"
    assert record.timestamp == datetime(2026, 8, 5, 15, 0, tzinfo=timezone.utc)
    assert record.outputs["eal_absolute"] == result.eal_absolute
    assert record.outputs["scenario_eal"]["2030"] == result.scenario_eal["2030"]
    assert record.outputs["scenario_eal"]["2050"] == result.scenario_eal["2050"]
    assert trail.verify_chain()


def test_scenario_2050_eal_at_least_2030_under_default_scales() -> None:
    trail = AppendOnlyAuditTrail()
    result = compute_expected_loss(
        asset=_asset(),
        hazards=_hazards(),
        valuation_date=date(2021, 7, 1),
        trail=trail,
    )
    assert result.scenario_eal["2050"] >= result.scenario_eal["2030"]


def test_eal_scales_with_asset_value() -> None:
    trail = AppendOnlyAuditTrail()
    low = compute_expected_loss(
        asset=_asset(1_000_000),
        hazards=_hazards(),
        valuation_date=date(2021, 7, 1),
        trail=trail,
    )
    high = compute_expected_loss(
        asset=_asset(4_000_000),
        hazards=_hazards(),
        valuation_date=date(2021, 7, 1),
        trail=trail,
    )
    assert high.eal_absolute > low.eal_absolute


def test_expected_loss_adapter_satisfies_financial_translation_protocol() -> None:
    trail = AppendOnlyAuditTrail()
    adapter = ExpectedLossFinancialTranslation(trail=trail)
    assert isinstance(adapter, FinancialTranslation)
    ctx = _ctx()
    hazard, exposure, vulnerability = _layers()
    financial = adapter.run(ctx, hazard, exposure, vulnerability)
    assert financial.layer == "FinancialTranslation"
    assert financial.scenario_deltas == {}
    assert adapter.last_result is not None
    assert trail.get(adapter.last_result.audit_record_id) is not None


def test_adapter_omits_horizons_without_climate_scenario_data() -> None:
    from app.loss.expected_loss import HORIZON_UNAVAILABLE_METHOD

    trail = AppendOnlyAuditTrail()
    adapter = ExpectedLossFinancialTranslation(trail=trail)
    hazard, exposure, vulnerability = _layers()
    adapter.run(_ctx(), hazard, exposure, vulnerability)
    assert adapter.last_result is not None
    record = trail.get(adapter.last_result.audit_record_id)
    assert record is not None
    assert record.parameters.get("horizon_method") == HORIZON_UNAVAILABLE_METHOD
    assert record.parameters.get("horizon_status") == "not_available"
    assert record.parameters.get("horizons") == []
    assert "omitted" in str(record.parameters.get("horizon_disclaimer", "")).lower()
    assert record.data_versions.get("horizon_method") == HORIZON_UNAVAILABLE_METHOD
    assert record.outputs["scenario_eal"] == {}


def test_stub_pipeline_financial_layer_writes_audit_record() -> None:
    trail = AppendOnlyAuditTrail()
    pipeline = StubFiveLayerPipeline(trail=trail)
    result = pipeline.run(_ctx())
    assert result.financial_translation.eal_absolute >= 0
    assert result.financial_translation.scenario_deltas == {}
    ft = pipeline.financial_translation
    assert isinstance(ft, ExpectedLossFinancialTranslation)
    assert ft.last_result is not None
    assert trail.get(ft.last_result.audit_record_id) is not None
    assert len(trail) >= 1
