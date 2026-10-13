"""Build the single-screen demo narrative from the five-layer pipeline.

Never calls ``/v1/risk/score`` (STUBS #3). Financial figures come from
expected-loss v0.3 via ``StubFiveLayerPipeline`` / ``ExpectedLossFinancialTranslation``.

Assets without coordinates are **never silently dropped** — they appear in
``coverage.excluded`` with an explicit reason (Phase A requires lat/lon;
geocoding is a STUBS/roadmap item).
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from app.adaptation.evidence import ADAPTATION_EVIDENCE_METHODOLOGY_VERSION
from app.loss.damage_curves import DAMAGE_CURVES_VERSION
from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_VERSION,
    ExpectedLossFinancialTranslation,
    unavailable_horizon_provenance,
)
from app.pipeline.contract import PipelineContext
from app.pipeline.stubs import StubFiveLayerPipeline
from app.portfolios.golden import (
    GOLDEN_ANTALYA_ID,
    GOLDEN_ANTALYA_VALUATION_DATE,
    GOLDEN_ROTTERDAM_PORT_ID,
    GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
    load_golden_antalya_assets,
    load_golden_rotterdam_port_assets,
)
from app.schemas.five_layer import METHODOLOGY_VERSION as PIPELINE_METHODOLOGY_VERSION
from app.schemas.portfolio import UniversalAsset, new_portfolio_id
from app.schemas.portfolio_demo import (
    EXCLUSION_MAX_ASSETS_CAP,
    EXCLUSION_MISSING_COORDINATES,
    METHODOLOGY_DOCUMENT_PATH,
    METHODOLOGY_DOCUMENT_VERSION,
    SYNTHETIC_CALIBRATION_BADGE,
    CoverageSummary,
    ExcludedAssetRow,
    MethodologyStamp,
    PortfolioDemoAssetRow,
    PortfolioDemoNarrative,
    VerificationHazardStep,
    VerificationWalkthrough,
)
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail

_ROOT = Path(__file__).resolve().parents[2]
_CURVES_PATH = _ROOT / "app" / "loss" / "curves" / "stub_global_mdr_v0.2.json"


class DemoNoAnalyzableAssetsError(ValueError):
    """Raised when every uploaded asset is excluded — maps to HTTP 422."""

    def __init__(
        self,
        message: str,
        *,
        coverage: CoverageSummary,
    ) -> None:
        super().__init__(message)
        self.coverage = coverage


def _methodology_stamp() -> MethodologyStamp:
    return MethodologyStamp(
        document=METHODOLOGY_DOCUMENT_VERSION,
        document_path=METHODOLOGY_DOCUMENT_PATH,
        expected_loss=EXPECTED_LOSS_METHODOLOGY_VERSION,
        damage_curves=DAMAGE_CURVES_VERSION,
        adaptation_evidence=ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
        pipeline=PIPELINE_METHODOLOGY_VERSION,
        calibration_badge=SYNTHETIC_CALIBRATION_BADGE,
    )


def _independent_eal_from_trail(record_payload: dict[str, Any]) -> dict[str, Any]:
    """Run the CI independent verifier (stdlib-only module under tests/)."""
    tests_dir = str(_ROOT / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from verification.independent_eal import eal_from_trail  # type: ignore[import-not-found]

    return eal_from_trail(record_payload, _CURVES_PATH)


def _build_verification(
    *,
    trail: AppendOnlyAuditTrail,
    eal_record_id: str,
    pipeline_eal: float,
    building_type: str,
    use_class: str,
) -> VerificationWalkthrough:
    record = trail.get(eal_record_id)
    if record is None:
        raise KeyError(f"Missing EAL audit record {eal_record_id}")
    payload = record.model_dump(mode="json")
    independent = _independent_eal_from_trail(payload)
    pipeline_rounded = round(float(pipeline_eal), 2)
    indep_rounded = round(float(independent["eal_absolute"]), 2)
    agreement = "PASS" if pipeline_rounded == indep_rounded else "FAIL"
    asset_in = payload["inputs"]["asset"]
    steps = [
        VerificationHazardStep(
            hazard_id=str(s["hazard_id"]),
            intensity=float(s["intensity"]),
            curve_id=str(s["curve_id"]),
            mdr=float(s["mdr"]),
            attribution_share=float(s["attribution_share"]),
            loss=float(s["loss"]),
            formula=str(s["formula"]),
        )
        for s in independent.get("steps") or []
    ]
    return VerificationWalkthrough(
        asset_id=str(asset_in["asset_id"]),
        valuation_date=date.fromisoformat(str(payload["valuation_date"])),
        asset_value=float(asset_in["asset_value"]),
        building_type=building_type,
        use_class=use_class,
        trail_record_id=str(payload["record_id"]),
        trail_record_hash=str(payload["record_hash"]),
        methodology_version=EXPECTED_LOSS_METHODOLOGY_VERSION,
        damage_curves_version=DAMAGE_CURVES_VERSION,
        calibration_badge=SYNTHETIC_CALIBRATION_BADGE,
        vulnerability=float(independent["vulnerability"]),
        combined_mdr=float(independent["combined_mdr"]),
        steps=steps,
        pipeline_eal=pipeline_rounded,
        independent_eal=indep_rounded,
        eal_2030_independent=independent.get("eal_2030"),
        eal_2050_independent=independent.get("eal_2050"),
        agreement=agreement,
    )


def _reason_summary(reason_counts: dict[str, int]) -> str:
    if not reason_counts:
        return "none"
    parts: list[str] = []
    if EXCLUSION_MISSING_COORDINATES in reason_counts:
        parts.append("no coordinates")
    if EXCLUSION_MAX_ASSETS_CAP in reason_counts:
        parts.append("demo max_assets cap")
    for reason, count in sorted(reason_counts.items()):
        if reason in (EXCLUSION_MISSING_COORDINATES, EXCLUSION_MAX_ASSETS_CAP):
            continue
        parts.append(f"{reason} ×{count}")
    return "; ".join(parts) if parts else "see exclusion list"


def _build_coverage(
    *,
    submitted_count: int,
    analyzed_count: int,
    excluded: list[ExcludedAssetRow],
) -> CoverageSummary:
    reason_counts: dict[str, int] = {}
    for row in excluded:
        reason_counts[row.reason] = reason_counts.get(row.reason, 0) + 1
    excluded_count = len(excluded)
    if excluded_count == 0:
        message = f"Analyzed {analyzed_count} of {submitted_count} assets (0 excluded)"
    else:
        message = (
            f"Analyzed {analyzed_count} of {submitted_count} assets "
            f"({excluded_count} excluded: {_reason_summary(reason_counts)})"
        )
    return CoverageSummary(
        submitted_count=submitted_count,
        analyzed_count=analyzed_count,
        excluded_count=excluded_count,
        message=message,
        eal_scope="analyzed assets only",
        reason_counts=reason_counts,
        excluded=excluded,
    )


def _partition_assets(
    assets: list[UniversalAsset],
    *,
    max_assets: int,
) -> tuple[list[UniversalAsset], list[ExcludedAssetRow]]:
    """Split upload into analyzable (≤ max_assets) and excluded (with reasons)."""
    excluded: list[ExcludedAssetRow] = []
    with_coords: list[UniversalAsset] = []
    for asset in assets:
        if asset.latitude is None or asset.longitude is None:
            excluded.append(
                ExcludedAssetRow(
                    asset_id=asset.asset_id,
                    reason=EXCLUSION_MISSING_COORDINATES,
                )
            )
        else:
            with_coords.append(asset)

    analyzed = with_coords[:max_assets]
    for asset in with_coords[max_assets:]:
        excluded.append(
            ExcludedAssetRow(
                asset_id=asset.asset_id,
                reason=EXCLUSION_MAX_ASSETS_CAP,
            )
        )
    return analyzed, excluded


def run_portfolio_demo(
    assets: list[UniversalAsset],
    valuation_date: date,
    *,
    portfolio_id: str | None = None,
    source: str = "upload",
    max_assets: int = 100,
    currency: str = "TRY",
    honesty_note: str | None = None,
    trail: AppendOnlyAuditTrail | None = None,
) -> PortfolioDemoNarrative:
    """Run the five-layer demo narrative.

    ``trail`` defaults to the process file trail (local, DB-less). A persisted
    run passes a staged trail that seals the run id into every record
    (``app.services.portfolio_run_service``).
    """
    if not assets:
        raise ValueError("Demo requires at least one asset.")

    submitted_count = len(assets)
    to_analyze, excluded = _partition_assets(assets, max_assets=max_assets)
    coverage_preview = _build_coverage(
        submitted_count=submitted_count,
        analyzed_count=len(to_analyze),
        excluded=excluded,
    )
    if not to_analyze:
        raise DemoNoAnalyzableAssetsError(
            (
                "No analyzable assets: Phase A demo requires latitude/longitude "
                f"on every analyzed row. {coverage_preview.message}. "
                "Geocoding from address is not yet supported (see STUBS.md)."
            ),
            coverage=coverage_preview,
        )

    # Do not use ``trail or …`` — empty trails are falsy via ``__len__``.
    trail = get_audit_trail() if trail is None else trail
    pipeline = StubFiveLayerPipeline(trail=trail)
    pid = portfolio_id or new_portfolio_id()
    stamp = _methodology_stamp()

    rows: list[PortfolioDemoAssetRow] = []
    hazard_sums: dict[str, float] = {}
    composites: list[float] = []
    eals: list[float] = []
    avoided: list[float] = []
    residual: list[float] = []
    recommendations: Counter[str] = Counter()
    featured: tuple[str, float, str, str] | None = None  # record_id, eal, bt, uc

    for asset in to_analyze:
        result = pipeline.run(
            PipelineContext(
                asset=asset,
                valuation_date=valuation_date,
                parameters={"demo": True, "portfolio_id": pid},
            )
        )
        ft = pipeline.financial_translation
        assert isinstance(ft, ExpectedLossFinancialTranslation)
        eal_result = ft.last_result
        if eal_result is None:
            raise RuntimeError("Expected-loss adapter did not retain last_result.")

        for hid, intensity in result.hazard.components.items():
            hazard_sums[hid] = hazard_sums.get(hid, 0.0) + intensity
        composites.append(result.hazard.composite_intensity)
        eal = result.financial_translation.eal_absolute
        eals.append(eal)
        avoided.append(result.adaptation_evidence.avoided_loss)
        residual.append(result.adaptation_evidence.residual_eal)
        rec = result.adaptation_evidence.recommended_measure_id or "none"
        recommendations[rec] += 1
        rows.append(
            PortfolioDemoAssetRow(
                asset_id=asset.asset_id,
                building_type=asset.building_type,
                use_class=asset.use_class,
                asset_value=asset.asset_value,
                hazard_composite=result.hazard.composite_intensity,
                eal_absolute=eal,
                eal_2030=result.financial_translation.scenario_deltas.get("2030"),
                eal_2050=result.financial_translation.scenario_deltas.get("2050"),
                recommended_measure_id=rec,
                avoided_loss=result.adaptation_evidence.avoided_loss,
                residual_eal=result.adaptation_evidence.residual_eal,
                eal_audit_record_id=eal_result.audit_record_id,
                methodology_version=eal_result.methodology_version,
                damage_curves_version=eal_result.damage_curves_version,
                calibration_badge=SYNTHETIC_CALIBRATION_BADGE,
            )
        )
        if featured is None or eal > featured[1]:
            featured = (
                eal_result.audit_record_id,
                eal,
                asset.building_type,
                asset.use_class,
            )

    assert featured is not None
    n = len(rows)
    coverage = _build_coverage(
        submitted_count=submitted_count,
        analyzed_count=n,
        excluded=excluded,
    )
    mean_components = {k: round(v / n, 6) for k, v in sorted(hazard_sums.items())}
    top_measure = recommendations.most_common(1)[0][0] if recommendations else None
    verification = _build_verification(
        trail=trail,
        eal_record_id=featured[0],
        pipeline_eal=featured[1],
        building_type=featured[2],
        use_class=featured[3],
    )

    return PortfolioDemoNarrative(
        portfolio_id=pid,
        valuation_date=valuation_date,
        asset_count=n,
        source=source,
        currency=currency,
        methodology=stamp,
        calibration_badge=SYNTHETIC_CALIBRATION_BADGE,
        coverage=coverage,
        honesty_note=honesty_note,
        upload={
            "portfolio_id": pid,
            "asset_count": n,
            "submitted_count": submitted_count,
            "excluded_count": coverage.excluded_count,
            "valuation_date": valuation_date.isoformat(),
            "message": (
                "Portfolio accepted — running five-layer analysis (not /v1/risk/score). "
                f"{coverage.message}. Phase A requires coordinates; geocoding is roadmap."
            ),
            "methodology_version": stamp.pipeline,
            "calibration_badge": SYNTHETIC_CALIBRATION_BADGE,
        },
        hazard={
            "mean_composite_intensity": round(sum(composites) / n, 6),
            "mean_components": mean_components,
            "message": "Hazard intelligence across flood and extreme heat stubs (wildfire is roadmap).",
            "methodology_version": "hazard-stub-v0.1",
            "calibration_badge": SYNTHETIC_CALIBRATION_BADGE,
            "coverage_scope": coverage.eal_scope,
        },
        expected_loss={
            "eal_sum": round(sum(eals), 2),
            "eal_mean": round(sum(eals) / n, 2),
            "message": (
                "Expected Annual Loss via combined MDR (v0.3) and versioned damage curves. "
                "Portfolio EAL covers analyzed assets only. "
                "2030/2050 outputs are unavailable until versioned climate-scenario "
                "intensity maps are supplied."
            ),
            "methodology_version": stamp.expected_loss,
            "damage_curves_version": stamp.damage_curves,
            "calibration_badge": SYNTHETIC_CALIBRATION_BADGE,
            "coverage_scope": coverage.eal_scope,
            "analyzed_count": n,
            **unavailable_horizon_provenance(),
        },
        adaptation={
            "recommended_measure_counts": dict(recommendations),
            "top_recommended_measure_id": top_measure,
            "message": "Measure catalogue scored by avoided loss per unit cost.",
            "methodology_version": stamp.adaptation_evidence,
            "calibration_badge": SYNTHETIC_CALIBRATION_BADGE,
            "coverage_scope": coverage.eal_scope,
        },
        avoided_loss={
            "avoided_loss_sum": round(sum(avoided), 2),
            "residual_eal_sum": round(sum(residual), 2),
            "avoided_loss_mean": round(sum(avoided) / n, 2),
            "message": (
                "Financeable adaptation: residual risk after recommended measures "
                "(analyzed assets only)."
            ),
            "methodology_version": stamp.adaptation_evidence,
            "calibration_badge": SYNTHETIC_CALIBRATION_BADGE,
            "coverage_scope": coverage.eal_scope,
        },
        verification=verification,
        assets=rows,
    )


def run_golden_antalya_demo(
    *,
    max_assets: int = 100,
    trail: AppendOnlyAuditTrail | None = None,
) -> PortfolioDemoNarrative:
    assets = load_golden_antalya_assets()
    return run_portfolio_demo(
        assets,
        GOLDEN_ANTALYA_VALUATION_DATE,
        portfolio_id=GOLDEN_ANTALYA_ID,
        source="golden-antalya",
        max_assets=max_assets,
        currency="TRY",
        honesty_note=(
            "Synthetic calibration on Antalya geographies — stub hazard + stub MDR; "
            "not observationally calibrated."
        ),
        trail=trail,
    )


def run_golden_rotterdam_port_demo(
    *,
    max_assets: int = 100,
    trail: AppendOnlyAuditTrail | None = None,
) -> PortfolioDemoNarrative:
    assets = load_golden_rotterdam_port_assets()
    return run_portfolio_demo(
        assets,
        GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
        portfolio_id=GOLDEN_ROTTERDAM_PORT_ID,
        source="golden-rotterdam-port",
        max_assets=max_assets,
        currency="EUR",
        honesty_note=(
            "Synthetic calibration on Rotterdam port geographies — same global stub MDR / "
            "stub hazard pipeline as Antalya; not pack-nl calibrated."
        ),
        trail=trail,
    )


__all__ = [
    "DemoNoAnalyzableAssetsError",
    "run_golden_antalya_demo",
    "run_golden_rotterdam_port_demo",
    "run_portfolio_demo",
]
