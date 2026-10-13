"""CI regression: Antalya golden portfolio (Annex B.6).

Score / EAL drift beyond committed baseline tolerances fails the build.
Regenerate fixtures after intentional methodology changes:

  PYTHONPATH=. python scripts/generate_golden_antalya_portfolio.py
"""

from __future__ import annotations

from app.adaptation.evidence import ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
from app.loss.damage_curves import DAMAGE_CURVES_VERSION
from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION
from app.pipeline.contract import PipelineContext
from app.pipeline.stubs import StubFiveLayerPipeline
from app.portfolios.golden import (
    GOLDEN_ANTALYA_ID,
    GOLDEN_ANTALYA_VALUATION_DATE,
    load_golden_antalya_assets,
    load_golden_antalya_baseline,
)
from app.schemas.five_layer import METHODOLOGY_VERSION as FIVE_LAYER_METHODOLOGY_VERSION
from app.schemas.portfolio_demo import METHODOLOGY_DOCUMENT_VERSION
from app.services.audit_trail import AppendOnlyAuditTrail


def _rel_err(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / abs(expected)


def test_golden_antalya_portfolio_shape() -> None:
    assets = load_golden_antalya_assets()
    assert len(assets) == 100
    assert all(a.latitude is not None and a.longitude is not None for a in assets)
    assert all(a.asset_value > 0 for a in assets)
    # Rough Antalya bounding box (metro + Belek/Manavgat west corridor)
    assert all(36.7 <= a.latitude <= 37.1 for a in assets)  # type: ignore[operator]
    assert all(30.5 <= a.longitude <= 31.4 for a in assets)  # type: ignore[operator]
    assert all(a.asset_id.startswith("ANT-G-") for a in assets)


def test_golden_antalya_regression_against_baseline() -> None:
    baseline = load_golden_antalya_baseline()
    assets = load_golden_antalya_assets()
    assert baseline["portfolio_id"] == GOLDEN_ANTALYA_ID
    assert baseline["asset_count"] == 100
    assert baseline["valuation_date"] == GOLDEN_ANTALYA_VALUATION_DATE.isoformat()

    # Methodology pins — intentional bumps require baseline regeneration.
    assert baseline["methodology"]["document"] == METHODOLOGY_DOCUMENT_VERSION
    assert baseline["methodology"]["five_layer"] == FIVE_LAYER_METHODOLOGY_VERSION
    assert baseline["methodology"]["expected_loss"] == EXPECTED_LOSS_METHODOLOGY_VERSION
    assert baseline["methodology"]["damage_curves"] == DAMAGE_CURVES_VERSION
    assert baseline["methodology"]["adaptation_evidence"] == ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
    assert baseline["methodology"]["pipeline_contract"] == FIVE_LAYER_METHODOLOGY_VERSION

    trail = AppendOnlyAuditTrail()
    pipeline = StubFiveLayerPipeline(trail=trail)
    by_id = {row["asset_id"]: row for row in baseline["assets"]}
    eals: list[float] = []
    scores: list[float] = []

    for asset in assets:
        result = pipeline.run(
            PipelineContext(
                asset=asset,
                valuation_date=GOLDEN_ANTALYA_VALUATION_DATE,
                parameters={"golden_portfolio": GOLDEN_ANTALYA_ID},
            )
        )
        eal = result.financial_translation.eal_absolute
        score = result.financial_translation.risk_score
        eals.append(eal)
        scores.append(score)
        expected = by_id[asset.asset_id]
        tol = baseline["tolerances"]["per_asset_eal_abs"]
        assert abs(eal - expected["eal_absolute"]) <= tol, (
            f"{asset.asset_id} EAL drift: got {eal}, baseline {expected['eal_absolute']}"
        )
        assert abs(score - expected["risk_score"]) <= baseline["tolerances"]["risk_score_mean_abs"]
        assert (
            result.adaptation_evidence.recommended_measure_id
            == expected["recommended_measure_id"]
        )

    eal_sum = round(sum(eals), 2)
    eal_mean = round(sum(eals) / len(eals), 2)
    risk_mean = round(sum(scores) / len(scores), 4)
    agg = baseline["aggregates"]
    tol = baseline["tolerances"]

    assert _rel_err(eal_sum, agg["eal_sum"]) <= tol["eal_sum_rel"]
    assert _rel_err(eal_mean, agg["eal_mean"]) <= tol["eal_mean_rel"]
    assert abs(risk_mean - agg["risk_score_mean"]) <= tol["risk_score_mean_abs"]
