"""CI regression: Rotterdam port golden portfolio (Annex B.6 NL-next).

Geographic generalisation fixture — same stub pipeline as Antalya, not pack-nl.
Regenerate after intentional methodology changes:

  PYTHONPATH=. python scripts/generate_golden_rotterdam_port_portfolio.py
"""

from __future__ import annotations

from app.adaptation.evidence import ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
from app.loss.damage_curves import DAMAGE_CURVES_VERSION
from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION
from app.pipeline.contract import PipelineContext
from app.pipeline.stubs import StubFiveLayerPipeline
from app.portfolios.golden import (
    GOLDEN_ROTTERDAM_PORT_ID,
    GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
    load_golden_rotterdam_port_assets,
    load_golden_rotterdam_port_baseline,
)
from app.schemas.five_layer import METHODOLOGY_VERSION as FIVE_LAYER_METHODOLOGY_VERSION
from app.schemas.portfolio_demo import METHODOLOGY_DOCUMENT_VERSION
from app.services.audit_trail import AppendOnlyAuditTrail


def _rel_err(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / abs(expected)


def test_golden_rotterdam_port_portfolio_shape() -> None:
    assets = load_golden_rotterdam_port_assets()
    assert len(assets) == 100
    assert all(a.latitude is not None and a.longitude is not None for a in assets)
    assert all(a.asset_value > 0 for a in assets)
    # Rough Rotterdam harbour / hinterland bounding box
    assert all(51.75 <= a.latitude <= 52.05 for a in assets)  # type: ignore[operator]
    assert all(3.95 <= a.longitude <= 4.80 for a in assets)  # type: ignore[operator]
    assert all(a.asset_id.startswith("RTM-G-") for a in assets)
    building_types = {a.building_type for a in assets}
    assert building_types & {"warehouse", "port_terminal", "logistics_park", "cold_storage", "office"}


def test_golden_rotterdam_port_regression_against_baseline() -> None:
    baseline = load_golden_rotterdam_port_baseline()
    assets = load_golden_rotterdam_port_assets()
    assert baseline["portfolio_id"] == GOLDEN_ROTTERDAM_PORT_ID
    assert baseline["asset_count"] == 100
    assert baseline["valuation_date"] == GOLDEN_ROTTERDAM_PORT_VALUATION_DATE.isoformat()
    assert baseline.get("currency") == "EUR"
    assert baseline.get("honesty", {}).get("pack_nl_calibrated") is False

    assert baseline["methodology"]["document"] == METHODOLOGY_DOCUMENT_VERSION
    assert baseline["methodology"]["five_layer"] == FIVE_LAYER_METHODOLOGY_VERSION
    assert baseline["methodology"]["expected_loss"] == EXPECTED_LOSS_METHODOLOGY_VERSION
    assert baseline["methodology"]["damage_curves"] == DAMAGE_CURVES_VERSION
    assert baseline["methodology"]["adaptation_evidence"] == ADAPTATION_EVIDENCE_METHODOLOGY_VERSION

    trail = AppendOnlyAuditTrail()
    pipeline = StubFiveLayerPipeline(trail=trail)
    eals: list[float] = []
    scores: list[float] = []
    by_id = {row["asset_id"]: row for row in baseline["assets"]}

    for asset in assets:
        result = pipeline.run(
            PipelineContext(
                asset=asset,
                valuation_date=GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
                parameters={
                    "golden_portfolio": GOLDEN_ROTTERDAM_PORT_ID,
                    "future_pack_id": "pack-nl",
                },
            )
        )
        eal = result.financial_translation.eal_absolute
        score = result.financial_translation.risk_score
        eals.append(eal)
        scores.append(score)
        pin = by_id[asset.asset_id]
        assert _rel_err(eal, pin["eal_absolute"]) <= 1e-9
        assert abs(score - pin["risk_score"]) <= 1e-6
        assert set(result.hazard.components) == {"flood", "extreme_heat", "wildfire", "earthquake"}

    eal_sum = round(sum(eals), 2)
    risk_mean = round(sum(scores) / len(scores), 4)
    agg = baseline["aggregates"]
    assert _rel_err(eal_sum, agg["eal_sum"]) <= 1e-9
    assert abs(risk_mean - agg["risk_score_mean"]) <= 1e-6
