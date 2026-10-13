"""Five-layer portfolio pipeline with audit-trail writes on every financial result.

Deterministic v0.1 methodology — stub hazard intensities until Country Packs wire
real layers. Formula changes require a methodology minor bump.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from app.schemas.five_layer import (
    METHODOLOGY_VERSION,
    AdaptationLayer,
    AdaptationMeasureResult,
    ExposureLayer,
    FinancialLayer,
    FiveLayerResult,
    HazardComponent,
    HazardLayer,
    VulnerabilityLayer,
)
from app.schemas.portfolio import UniversalAsset
from app.schemas.source_manifest import SourceRecord, refuse_blocked_contributors
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail

# Stub data lineage stamps (pack-tr connectors will replace these).
_DATA_VERSIONS = {
    "hazard_stub": "hazard-stub-v0.2",
    "vulnerability_curves": "vuln-curves-v0.1",
    "adaptation_catalogue": "adapt-catalogue-v0.2",
}

# Active modules (methodology v0.4.0): flood, extreme heat, wildfire (climate) and
# earthquake (geophysical). Each ships with its hazard module (app/hazards/) and a
# labelled synthetic curve family in stub_global_mdr v0.2.0. Drought / storm stay roadmap.
_HAZARDS = ("flood", "extreme_heat", "wildfire", "earthquake")


def _unit_float(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _hazard_layer(asset: UniversalAsset, valuation_date: date) -> HazardLayer:
    lat = asset.latitude if asset.latitude is not None else 0.0
    lon = asset.longitude if asset.longitude is not None else 0.0
    components: list[HazardComponent] = []
    for name in _HAZARDS:
        seed = f"{name}|{lat:.5f}|{lon:.5f}|{valuation_date.isoformat()}"
        components.append(
            HazardComponent(hazard_id=name, intensity=round(_unit_float(seed), 6))
        )
    composite = round(sum(c.intensity for c in components) / len(components), 6)
    return HazardLayer(
        components=components,
        composite_intensity=composite,
        data_versions={"hazard_stub": _DATA_VERSIONS["hazard_stub"]},
    )


def _vulnerability_layer(asset: UniversalAsset) -> VulnerabilityLayer:
    year = asset.construction_year or 2000
    age_penalty = min(0.35, max(0.0, (2026 - year) / 200.0))
    floor_penalty = min(0.15, (asset.floors or 1) / 100.0)
    building = (asset.building_type or "unknown").lower()
    type_factor = {
        "hotel": 0.55,
        "apartment": 0.45,
        "office": 0.40,
        "retail": 0.50,
        "industrial": 0.60,
    }.get(building, 0.50)
    existing = list(asset.existing_adaptation_measures or [])
    capacity = min(0.4, 0.08 * len(existing))
    fragility = round(min(1.0, type_factor + age_penalty + floor_penalty), 6)
    return VulnerabilityLayer(
        fragility_factor=fragility,
        adaptation_capacity_factor=round(capacity, 6),
        construction_year=asset.construction_year,
        floors=asset.floors,
        existing_measures=existing,
    )


def _financial_layer(
    asset: UniversalAsset,
    hazard: HazardLayer,
    exposure: ExposureLayer,
    vulnerability: VulnerabilityLayer,
    valuation_date: date,
    *,
    trail: AppendOnlyAuditTrail | None = None,
) -> FinancialLayer:
    """Delegate EAL to expected-loss v0.3 (combined MDR + hard asset-value cap)."""
    from app.loss.expected_loss import (
        HORIZON_UNAVAILABLE_METHOD,
        ExpectedLossAssetInput,
        HazardScenarioIntensities,
        compute_expected_loss,
        unavailable_horizon_provenance,
    )

    current = {c.hazard_id: float(c.intensity) for c in hazard.components}
    if not current:
        current = {"composite": float(hazard.composite_intensity)}
    hazards = HazardScenarioIntensities(
        current=current,
        data_versions={
            **dict(hazard.data_versions or {}),
            "horizon_method": HORIZON_UNAVAILABLE_METHOD,
        },
        as_of=valuation_date,
    )
    result = compute_expected_loss(
        asset=ExpectedLossAssetInput(
            asset_id=exposure.asset_id,
            asset_value=float(exposure.asset_value),
            building_type=exposure.building_type,
            use_class=exposure.use_class,
            fragility_factor=float(vulnerability.fragility_factor),
            adaptation_capacity_factor=float(vulnerability.adaptation_capacity_factor),
            insurance_coverage=asset.insurance_coverage,
        ),
        hazards=hazards,
        valuation_date=valuation_date,
        trail=trail,
        parameters=unavailable_horizon_provenance(),
    )
    return FinancialLayer(
        eal_absolute=result.eal_absolute,
        eal_pct_of_value=result.eal_pct_of_value,
        risk_score=result.risk_score,
        scenario_deltas=dict(result.scenario_eal),
        collateral_sensitivity=result.collateral_sensitivity,
        insurability=result.insurability,
    )


def _apply_insurance(financial: FinancialLayer, asset: UniversalAsset) -> FinancialLayer:
    if asset.insurance_coverage is None:
        return financial.model_copy(update={"insurability": "protection_gap"})
    if asset.insurance_coverage >= asset.asset_value:
        return financial.model_copy(update={"insurability": "insured"})
    if asset.insurance_coverage > 0:
        return financial.model_copy(update={"insurability": "insurable_with_conditions"})
    return financial.model_copy(update={"insurability": "protection_gap"})


def _adaptation_layer(
    asset: UniversalAsset,
    financial: FinancialLayer,
) -> AdaptationLayer:
    catalogue = [
        ("cool-roof-v1", "Cool roof / reflective coating", 0.015, 0.18),
        ("flood-barrier-v1", "Property-level flood barrier", 0.04, 0.35),
        ("drainage-upgrade-v1", "Site drainage upgrade", 0.025, 0.22),
        ("seismic-retrofit-v1", "Seismic structural retrofit", 0.08, 0.30),
        ("wildfire-defensible-space-v1", "Defensible space and ember-resistant envelope", 0.012, 0.10),
    ]
    measures: list[AdaptationMeasureResult] = []
    for measure_id, label, cost_frac, reduction in catalogue:
        cost = round(asset.asset_value * cost_frac, 2)
        avoided = round(financial.eal_absolute * reduction, 2)
        residual = round(max(0.0, financial.eal_absolute - avoided), 2)
        outcome = None
        if asset.adaptation and (
            asset.adaptation.measure_id == measure_id
            or asset.adaptation.measure_status is not None
        ):
            # Attach B.7 fields when the asset already carries outcome data.
            if asset.adaptation.measure_id in (None, measure_id):
                outcome = asset.adaptation
        measures.append(
            AdaptationMeasureResult(
                measure_id=measure_id,
                label=label,
                cost=cost,
                risk_reduction_fraction=reduction,
                avoided_loss=avoided,
                residual_eal=residual,
                outcome=outcome,
            )
        )
    # Recommend highest avoided_loss / cost ratio.
    ranked = sorted(
        measures,
        key=lambda m: (m.avoided_loss / m.cost) if m.cost else 0.0,
        reverse=True,
    )
    best = ranked[0] if ranked else None
    residual_score = (
        round(financial.risk_score * (1.0 - (best.risk_reduction_fraction if best else 0.0)), 4)
    )
    return AdaptationLayer(
        measures=measures,
        recommended_measure_id=best.measure_id if best else None,
        residual_risk_score=residual_score,
    )


def compute_five_layer(
    asset: UniversalAsset,
    valuation_date: date,
    *,
    parameters: dict[str, Any] | None = None,
    trail: AppendOnlyAuditTrail | None = None,
    hazard: HazardLayer | None = None,
) -> tuple[FiveLayerResult, dict[str, Any], dict[str, Any], dict[str, str]]:
    """Pure computation. Returns result draft fields + trail payloads.

    ``hazard`` injects a pre-computed Hazard layer (e.g. real ERA5/DEM-driven
    intensities). When ``None`` the deterministic SHA-256 stub layer is used
    (STUBS.md #16a). Downstream layers (Exposure→Vulnerability→EAL→Adaptation)
    are identical either way.
    """
    if asset.latitude is None or asset.longitude is None:
        # Address-only assets: geocode later; for v0.1 require coordinates for hazard.
        raise ValueError(
            f"Asset {asset.asset_id!r} needs latitude/longitude for five-layer hazard computation."
        )

    params = dict(parameters or {})
    hazard = hazard if hazard is not None else _hazard_layer(asset, valuation_date)
    exposure = ExposureLayer(
        asset_id=asset.asset_id,
        asset_value=asset.asset_value,
        building_type=asset.building_type,
        use_class=asset.use_class,
        latitude=asset.latitude,
        longitude=asset.longitude,
        address=asset.address,
        ltv=asset.ltv,
    )
    vulnerability = _vulnerability_layer(asset)
    # EAL path writes its own audit record via expected-loss; pass trail through.
    financial = _apply_insurance(
        _financial_layer(
            asset, hazard, exposure, vulnerability, valuation_date, trail=trail
        ),
        asset,
    )
    adaptation = _adaptation_layer(asset, financial)

    data_versions = {
        **_DATA_VERSIONS,
        **hazard.data_versions,
    }
    inputs = {
        "asset": asset.model_dump(mode="json"),
        "valuation_date": valuation_date.isoformat(),
    }
    outputs = {
        "eal_absolute": financial.eal_absolute,
        "eal_pct_of_value": financial.eal_pct_of_value,
        "risk_score": financial.risk_score,
        "scenario_deltas": financial.scenario_deltas,
        "collateral_sensitivity": financial.collateral_sensitivity,
        "insurability": financial.insurability,
        "recommended_measure_id": adaptation.recommended_measure_id,
        "residual_risk_score": adaptation.residual_risk_score,
        "hazard_composite_intensity": hazard.composite_intensity,
        "fragility_factor": vulnerability.fragility_factor,
    }
    # Placeholder result without audit_record_id — filled by run_five_layer.
    draft = FiveLayerResult(
        methodology_version=METHODOLOGY_VERSION,
        valuation_date=valuation_date,
        asset_id=asset.asset_id,
        hazard=hazard,
        exposure=exposure,
        vulnerability=vulnerability,
        financial=financial,
        adaptation=adaptation,
        audit_record_id="pending",
        computed_at=datetime.now(timezone.utc),
    )
    return draft, inputs, outputs, data_versions


def run_five_layer(
    asset: UniversalAsset,
    valuation_date: date,
    *,
    parameters: dict[str, Any] | None = None,
    trail: AppendOnlyAuditTrail | None = None,
    timestamp: datetime | None = None,
    hazard: HazardLayer | None = None,
    sources: list[SourceRecord] | None = None,
) -> FiveLayerResult:
    """Run all five layers and append a hash-chained audit record.

    ``hazard`` optionally injects a pre-computed (e.g. real-data) Hazard layer.
    ``sources`` are licence-gated *before* any layer runs: a blocked source that
    declares a use refuses the run (``SOURCE_LICENCE_NOT_VERIFIED``).
    """
    from app.services.source_manifest import build_result_manifest

    caller_sources = list(sources or [])
    refuse_blocked_contributors(
        build_result_manifest(
            data_versions={}, extra_records=caller_sources, include_registry=False
        )
    )
    # Do not use ``trail or …`` — empty trails are falsy via ``__len__``.
    store = get_audit_trail() if trail is None else trail
    draft, inputs, outputs, data_versions = compute_five_layer(
        asset, valuation_date, parameters=parameters, trail=store, hazard=hazard
    )
    # Pipeline-level trail record (layers 1–5 summary). EAL also wrote its own record.
    from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION

    run_data_versions = {
        **data_versions,
        "expected_loss": EXPECTED_LOSS_METHODOLOGY_VERSION,
    }
    # Full manifest: synthetic curves the run stamped plus every production-tier
    # registry source — including the ones blocked for lack of a licence, so the
    # record names what could not contribute.
    manifest = build_result_manifest(
        data_versions=run_data_versions, extra_records=caller_sources
    )
    record = store.append(
        methodology_version=METHODOLOGY_VERSION,
        valuation_date=valuation_date,
        data_versions=run_data_versions,
        parameters=dict(parameters or {}),
        inputs=inputs,
        outputs=outputs,
        timestamp=timestamp,
        sources=manifest.to_payload(),
    )
    return draft.model_copy(
        update={
            "audit_record_id": record.record_id,
            "computed_at": record.timestamp,
        }
    )


def recompute_eal_from_trail(
    record_id: str,
    *,
    trail: AppendOnlyAuditTrail | None = None,
) -> float:
    """Recompute EAL from a trail record's inputs (reproducibility)."""
    store = get_audit_trail() if trail is None else trail
    record = store.get(record_id)
    if record is None:
        raise KeyError(f"Unknown audit trail record: {record_id}")
    if record.methodology_version != METHODOLOGY_VERSION:
        raise ValueError(
            f"Unsupported methodology_version {record.methodology_version!r}; "
            f"this runtime has {METHODOLOGY_VERSION!r}."
        )
    asset = UniversalAsset.model_validate(record.inputs["asset"])
    valuation_date = date.fromisoformat(record.inputs["valuation_date"])
    # Disposable trail so replay does not append to the caller's store.
    draft, _, outputs, _ = compute_five_layer(
        asset,
        valuation_date,
        parameters=record.parameters,
        trail=AppendOnlyAuditTrail(),
    )
    return float(outputs["eal_absolute"])


__all__ = [
    "compute_five_layer",
    "recompute_eal_from_trail",
    "run_five_layer",
]
