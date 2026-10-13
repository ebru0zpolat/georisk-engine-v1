"""Financial translation layer — Expected Annual Loss (EAL).

Forward horizons are optional. Scenario deltas are computed only when callers
supply versioned 2030/2050 hazard-intensity maps. Phase A adapters with
current-only inputs leave horizon outputs unavailable; they never manufacture
future intensities from the current value.

Every successful computation appends a hash-chained audit-trail record **before**
returning. Default trail storage is file-backed JSONL.

Replay must dispatch on ``record.methodology_version`` via ``FORMULAS`` — never
silently run the current formula against an older trail (see
``.cursor/rules/ci-stubs-honesty.mdc``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.loss.damage_curves import (
    DamageCurveCatalogue,
    damage_curves_version,
    load_catalogue,
    load_catalogue_by_id_version,
    mean_damage_ratio,
)
from app.loss.depth_damage_curves import (
    DepthDamageCatalogue,
    load_depth_damage_by_id_version,
    select_depth_curve,
)
from app.services.audit_trail import (
    AppendOnlyAuditTrail,
    AuditTrailRecord,
    get_audit_trail,
)
from app.services.source_manifest import build_result_manifest

# Latest live methodology. Bump only when adding a new FORMULAS entry.
EXPECTED_LOSS_METHODOLOGY_VERSION = "expected-loss-v0.3"
EXPECTED_LOSS_METHODOLOGY_V0_2 = "expected-loss-v0.2"
# Opt-in hybrid depth/intensity methodology (flood uses JRC depth curves).
# NOT the default — selected only when a caller passes depths + a depth catalogue.
EXPECTED_LOSS_METHODOLOGY_V0_4 = "expected-loss-v0.4"

# Forward-looking outputs are unavailable until a versioned climate-scenario
# hazard source supplies horizon-specific intensity maps.
HORIZON_UNAVAILABLE_METHOD = "not_available_without_climate_scenario_data"
HORIZON_UNAVAILABLE_DISCLAIMER = (
    "2030/2050 outputs are omitted because no versioned CMIP6/CORDEX or other "
    "climate-scenario intensity maps were supplied."
)

Insurability = Literal["insured", "insurable_with_conditions", "protection_gap"]

FormulaFn = Callable[..., dict[str, Any]]


def unavailable_horizon_provenance() -> dict[str, Any]:
    """Explain why forward-looking outputs are intentionally absent."""
    return {
        "horizon_method": HORIZON_UNAVAILABLE_METHOD,
        "horizon_status": "not_available",
        "horizon_disclaimer": HORIZON_UNAVAILABLE_DISCLAIMER,
    }


class HazardScenarioIntensities(BaseModel):
    """Per-hazard intensities in [0, 1] for current climate and scenario horizons.

    Callers (hazard modules) must only supply intensities that are valid as of
    ``valuation_date`` — no lookahead. Optional ``as_of`` documents the data cut.
    """

    current: dict[str, float]
    horizon_2030: dict[str, float] = Field(default_factory=dict)
    horizon_2050: dict[str, float] = Field(default_factory=dict)
    data_versions: dict[str, str] = Field(default_factory=dict)
    as_of: date | None = Field(
        default=None,
        description="Latest observation / model cut date for these intensities.",
    )

    @field_validator("current", "horizon_2030", "horizon_2050")
    @classmethod
    def intensities_in_unit_interval(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            return {}
        out: dict[str, float] = {}
        for key, raw in value.items():
            try:
                intensity = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"intensity for {key!r} is not numeric: {raw!r}") from exc
            if not math.isfinite(intensity):
                raise ValueError(
                    f"intensity for {key!r} must be finite, got {intensity!r}"
                )
            if intensity < 0.0 or intensity > 1.0:
                raise ValueError(f"intensity for {key!r} must be in [0, 1], got {intensity}")
            out[str(key)] = intensity
        return out

    @model_validator(mode="after")
    def require_current_intensities(self) -> HazardScenarioIntensities:
        if not self.current:
            raise ValueError("current hazard intensity map must be non-empty")
        if bool(self.horizon_2030) != bool(self.horizon_2050):
            raise ValueError("2030 and 2050 intensity maps must be supplied together")
        return self

    def assert_no_lookahead(self, valuation_date: date) -> None:
        if self.as_of is not None and self.as_of > valuation_date:
            raise ValueError(
                f"hazard intensities as_of={self.as_of.isoformat()} look ahead of "
                f"valuation_date={valuation_date.isoformat()}"
            )


class ExpectedLossAssetInput(BaseModel):
    """Minimal exposure/vulnerability inputs for EAL (P0 UniversalAsset subset)."""

    asset_id: str
    asset_value: float = Field(..., gt=0)
    building_type: str
    use_class: str
    fragility_factor: float = Field(default=1.0, ge=0.0, le=2.0)
    adaptation_capacity_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    insurance_coverage: float | None = Field(default=None, ge=0)


class ExpectedLossResult(BaseModel):
    """Full expected-loss output including audit linkage."""

    methodology_version: str = EXPECTED_LOSS_METHODOLOGY_VERSION
    damage_curves_version: str
    valuation_date: date
    asset_id: str
    eal_absolute: float = Field(..., ge=0.0)
    eal_pct_of_value: float = Field(..., ge=0.0)
    eal_by_hazard: dict[str, float] = Field(default_factory=dict)
    mdr_by_hazard: dict[str, float] = Field(default_factory=dict)
    curve_ids_by_hazard: dict[str, str] = Field(default_factory=dict)
    scenario_eal: dict[str, float] = Field(
        default_factory=dict,
        description="Absolute EAL by horizon key (2030, 2050).",
    )
    risk_score: float = Field(..., ge=0.0, le=100.0)
    collateral_sensitivity: float = Field(..., ge=0.0, le=1.0)
    insurability: Insurability
    audit_record_id: str
    computed_at: datetime

    @model_validator(mode="after")
    def validate_scenario_horizons(self) -> ExpectedLossResult:
        keys = set(self.scenario_eal)
        if keys and keys != {"2030", "2050"}:
            raise ValueError("scenario_eal must be empty or include both 2030 and 2050")
        return self


def _effective_vulnerability(asset: ExpectedLossAssetInput) -> float:
    return max(0.05, asset.fragility_factor * (1.0 - asset.adaptation_capacity_factor))


def _insurability(asset: ExpectedLossAssetInput) -> Insurability:
    if asset.insurance_coverage is None:
        return "protection_gap"
    if asset.insurance_coverage >= asset.asset_value:
        return "insured"
    if asset.insurance_coverage > 0:
        return "insurable_with_conditions"
    return "protection_gap"


def intensity_sum(components: dict[str, float]) -> float:
    """Σ intensity — denominator for attribution_share (not the mean)."""
    return float(sum(components.values()))


def attribution_shares(intensities: dict[str, float]) -> dict[str, float]:
    """Return attribution_share_h = i_h / Σ i. Informational only; empty when Σ i == 0.

    v0.3 trail / live output key: ``attribution_share``.
    """
    total = intensity_sum(intensities)
    if total <= 0.0:
        return {}
    return {hid: float(i) / total for hid, i in intensities.items()}


def hazard_weights(intensities: dict[str, float]) -> dict[str, float]:
    """v0.2 intensity shares ``w_h = i_h / Σ i`` (informational; empty when Σ i == 0).

    Same math as ``attribution_shares``; kept under the historical name so frozen
    v0.2 replay can reconstruct trail field ``attribution_weights``.
    """
    return attribution_shares(intensities)


def combined_mdr(mdr_by_hazard: dict[str, float]) -> float:
    """Union of per-hazard MDRs: 1 − ∏(1 − mdr_h). Full precision (no intermediate round)."""
    survival = 1.0
    for mdr in mdr_by_hazard.values():
        survival *= 1.0 - max(0.0, min(1.0, float(mdr)))
    return max(0.0, min(1.0, 1.0 - survival))


def _round_cents(value: float) -> float:
    """Money output-boundary rounding (cents). Never use mid-formula."""
    return round(float(value), 2)


# ---------------------------------------------------------------------------
# FROZEN: expected-loss-v0.2
# Copied as-shipped from methodology v0.2 (PR #68). Do not edit. New work adds
# a new version function + FORMULAS entry only.
# Historical intermediate round() calls below are intentional replay fidelity —
# the "round once at output" rule applies to live (v0.3+) formulas only.
# ---------------------------------------------------------------------------


def _eal_for_intensities_v0_2(
    *,
    asset: ExpectedLossAssetInput,
    intensities: dict[str, float],
    catalogue: DamageCurveCatalogue,
) -> tuple[float, dict[str, float], dict[str, float], dict[str, str]]:
    """Return total EAL, per-hazard loss, MDR, and curve_id maps (methodology v0.2)."""
    vuln = _effective_vulnerability(asset)
    total_intensity = intensity_sum(intensities)
    per_loss: dict[str, float] = {}
    per_mdr: dict[str, float] = {}
    per_curve: dict[str, str] = {}

    # No hazard mass → no loss. Never invent uniform weights.
    if total_intensity <= 0.0:
        for hazard_id, intensity in intensities.items():
            mdr, curve = mean_damage_ratio(
                building_type=asset.building_type,
                use_class=asset.use_class,
                intensity=intensity,
                hazard_id=hazard_id,
                catalogue=catalogue,
            )
            per_mdr[hazard_id] = mdr
            per_loss[hazard_id] = 0.0
            per_curve[hazard_id] = curve.curve_id
        return 0.0, per_loss, per_mdr, per_curve

    # Independent per-hazard losses (see METHODOLOGY.md v0.2). Weights are for
    # attribution only — computed via hazard_weights() by callers / audit layer.
    total = 0.0
    for hazard_id, intensity in intensities.items():
        mdr, curve = mean_damage_ratio(
            building_type=asset.building_type,
            use_class=asset.use_class,
            intensity=intensity,
            hazard_id=hazard_id,
            catalogue=catalogue,
        )
        loss = asset.asset_value * mdr * vuln
        per_mdr[hazard_id] = mdr
        per_loss[hazard_id] = round(loss, 2)
        per_curve[hazard_id] = curve.curve_id
        total += loss
    return round(total, 2), per_loss, per_mdr, per_curve


def _compute_core_v0_2(
    *,
    asset: ExpectedLossAssetInput,
    hazards: HazardScenarioIntensities,
    valuation_date: date,
    catalogue: DamageCurveCatalogue,
) -> dict[str, Any]:
    """Pure computation for methodology expected-loss-v0.2 (FROZEN)."""
    hazards.assert_no_lookahead(valuation_date)

    base_eal, per_loss, per_mdr, per_curve = _eal_for_intensities_v0_2(
        asset=asset,
        intensities=hazards.current,
        catalogue=catalogue,
    )
    eal_2030, _, _, _ = _eal_for_intensities_v0_2(
        asset=asset,
        intensities=hazards.horizon_2030,
        catalogue=catalogue,
    )
    eal_2050, _, _, _ = _eal_for_intensities_v0_2(
        asset=asset,
        intensities=hazards.horizon_2050,
        catalogue=catalogue,
    )
    eal_pct = (
        round((base_eal / asset.asset_value) * 100.0, 6) if asset.asset_value else 0.0
    )
    # Risk score uses mean intensity as a 0–100 display index (not a weight denominator).
    current_vals = list(hazards.current.values())
    mean_intensity = sum(current_vals) / len(current_vals) if current_vals else 0.0
    risk_score = round(
        min(100.0, mean_intensity * _effective_vulnerability(asset) * 100.0),
        4,
    )
    collateral = (
        round(min(1.0, base_eal / asset.asset_value), 6) if asset.asset_value else 0.0
    )
    return {
        "eal_absolute": base_eal,
        "eal_pct_of_value": eal_pct,
        "eal_by_hazard": per_loss,
        "mdr_by_hazard": per_mdr,
        "curve_ids_by_hazard": per_curve,
        # Historical trail key from the v0.2 live path (not attribution_share).
        "attribution_weights": hazard_weights(hazards.current),
        "scenario_eal": {"2030": eal_2030, "2050": eal_2050},
        "risk_score": risk_score,
        "collateral_sensitivity": collateral,
        "insurability": _insurability(asset),
        "damage_curves_version": damage_curves_version(catalogue),
    }


# ---------------------------------------------------------------------------
# expected-loss-v0.3 (current)
# ---------------------------------------------------------------------------


def _eal_for_intensities_v0_3(
    *,
    asset: ExpectedLossAssetInput,
    intensities: dict[str, float],
    catalogue: DamageCurveCatalogue,
    apply_output_rounding: bool = True,
) -> tuple[float, dict[str, float], dict[str, float], dict[str, str], float]:
    """Return EAL, notional per-hazard loss, MDR, curve_id maps, combined_MDR (v0.3).

    Intermediates (MDR, combined_MDR, uncapped loss) stay full precision.
    When ``apply_output_rounding`` is True, money fields are rounded to cents
    only at this output boundary.
    """
    vuln = _effective_vulnerability(asset)
    total_intensity = intensity_sum(intensities)
    per_loss_raw: dict[str, float] = {}
    per_mdr: dict[str, float] = {}
    per_curve: dict[str, str] = {}

    for hazard_id, intensity in intensities.items():
        mdr, curve = mean_damage_ratio(
            building_type=asset.building_type,
            use_class=asset.use_class,
            intensity=intensity,
            hazard_id=hazard_id,
            catalogue=catalogue,
        )
        per_mdr[hazard_id] = mdr
        per_curve[hazard_id] = curve.curve_id
        per_loss_raw[hazard_id] = (
            0.0 if total_intensity <= 0.0 else asset.asset_value * mdr * vuln
        )

    if total_intensity <= 0.0:
        per_loss = (
            {k: _round_cents(v) for k, v in per_loss_raw.items()}
            if apply_output_rounding
            else per_loss_raw
        )
        return 0.0, per_loss, per_mdr, per_curve, 0.0

    combo = combined_mdr(per_mdr)
    uncapped = asset.asset_value * combo * vuln
    eal_full = min(asset.asset_value, uncapped)
    if apply_output_rounding:
        eal = min(asset.asset_value, _round_cents(uncapped))
        per_loss = {k: _round_cents(v) for k, v in per_loss_raw.items()}
    else:
        eal = eal_full
        per_loss = per_loss_raw
    return eal, per_loss, per_mdr, per_curve, combo


def _compute_core_v0_3(
    *,
    asset: ExpectedLossAssetInput,
    hazards: HazardScenarioIntensities,
    valuation_date: date,
    catalogue: DamageCurveCatalogue,
    apply_output_rounding: bool = True,
) -> dict[str, Any]:
    """Pure computation for methodology expected-loss-v0.3."""
    hazards.assert_no_lookahead(valuation_date)

    base_eal, per_loss, per_mdr, per_curve, combo = _eal_for_intensities_v0_3(
        asset=asset,
        intensities=hazards.current,
        catalogue=catalogue,
        apply_output_rounding=apply_output_rounding,
    )
    scenario_eal: dict[str, float] = {}
    if hazards.horizon_2030 and hazards.horizon_2050:
        eal_2030, _, _, _, _ = _eal_for_intensities_v0_3(
            asset=asset,
            intensities=hazards.horizon_2030,
            catalogue=catalogue,
            apply_output_rounding=apply_output_rounding,
        )
        eal_2050, _, _, _, _ = _eal_for_intensities_v0_3(
            asset=asset,
            intensities=hazards.horizon_2050,
            catalogue=catalogue,
            apply_output_rounding=apply_output_rounding,
        )
        scenario_eal = {"2030": eal_2030, "2050": eal_2050}
    eal_pct_full = (
        (base_eal / asset.asset_value) * 100.0 if asset.asset_value else 0.0
    )
    # Risk score uses mean intensity as a 0–100 display index (not an EAL input).
    current_vals = list(hazards.current.values())
    mean_intensity = sum(current_vals) / len(current_vals) if current_vals else 0.0
    risk_score_full = min(
        100.0, mean_intensity * _effective_vulnerability(asset) * 100.0
    )
    collateral_full = (
        min(1.0, base_eal / asset.asset_value) if asset.asset_value else 0.0
    )
    if apply_output_rounding:
        eal_pct = round(eal_pct_full, 6)
        risk_score = round(risk_score_full, 4)
        collateral = round(collateral_full, 6)
    else:
        eal_pct = eal_pct_full
        risk_score = risk_score_full
        collateral = collateral_full
    return {
        "eal_absolute": base_eal,
        "eal_pct_of_value": eal_pct,
        "eal_by_hazard": per_loss,
        "mdr_by_hazard": per_mdr,
        "combined_mdr": combo,
        "curve_ids_by_hazard": per_curve,
        "scenario_eal": scenario_eal,
        "risk_score": risk_score,
        "collateral_sensitivity": collateral,
        "insurability": _insurability(asset),
        "damage_curves_version": damage_curves_version(catalogue),
    }


# ---------------------------------------------------------------------------
# expected-loss-v0.4 (opt-in) — hybrid depth/intensity damage
#
# Identical to v0.3 for every hazard EXCEPT those with a supplied inundation
# depth and a depth-damage (JRC) catalogue: their MDR comes from the depth curve
# instead of the intensity power law. combined_MDR / vulnerability / hard cap /
# risk_score / scenario horizons are the v0.3 mechanics unchanged. Not the
# default — callers opt in by passing methodology_version=v0.4 + depths +
# depth_catalogue, so v0.3 (and the golden baselines) are untouched.
# ---------------------------------------------------------------------------


def _eal_for_intensities_v0_4(
    *,
    asset: ExpectedLossAssetInput,
    intensities: dict[str, float],
    catalogue: DamageCurveCatalogue,
    depths: dict[str, float] | None,
    depth_catalogue: DepthDamageCatalogue | None,
    apply_output_rounding: bool = True,
) -> tuple[float, dict[str, float], dict[str, float], dict[str, str], float]:
    """v0.3 EAL, but flood-family hazards with a depth use the JRC depth curve."""
    vuln = _effective_vulnerability(asset)
    total_intensity = intensity_sum(intensities)
    per_loss_raw: dict[str, float] = {}
    per_mdr: dict[str, float] = {}
    per_curve: dict[str, str] = {}
    depths = depths or {}

    for hazard_id, intensity in intensities.items():
        if hazard_id in depths and depth_catalogue is not None:
            curve = select_depth_curve(
                building_type=asset.building_type,
                catalogue=depth_catalogue,
            )
            mdr = curve.damage_ratio_at_depth(float(depths[hazard_id]))
            curve_id = curve.curve_id
        else:
            mdr, power_curve = mean_damage_ratio(
                building_type=asset.building_type,
                use_class=asset.use_class,
                intensity=intensity,
                hazard_id=hazard_id,
                catalogue=catalogue,
            )
            curve_id = power_curve.curve_id
        per_mdr[hazard_id] = mdr
        per_curve[hazard_id] = curve_id
        per_loss_raw[hazard_id] = (
            0.0 if total_intensity <= 0.0 else asset.asset_value * mdr * vuln
        )

    if total_intensity <= 0.0:
        per_loss = (
            {k: _round_cents(v) for k, v in per_loss_raw.items()}
            if apply_output_rounding
            else per_loss_raw
        )
        return 0.0, per_loss, per_mdr, per_curve, 0.0

    combo = combined_mdr(per_mdr)
    uncapped = asset.asset_value * combo * vuln
    if apply_output_rounding:
        eal = min(asset.asset_value, _round_cents(uncapped))
        per_loss = {k: _round_cents(v) for k, v in per_loss_raw.items()}
    else:
        eal = min(asset.asset_value, uncapped)
        per_loss = per_loss_raw
    return eal, per_loss, per_mdr, per_curve, combo


def _compute_core_v0_4(
    *,
    asset: ExpectedLossAssetInput,
    hazards: HazardScenarioIntensities,
    valuation_date: date,
    catalogue: DamageCurveCatalogue,
    depths: dict[str, float] | None = None,
    depth_catalogue: DepthDamageCatalogue | None = None,
    apply_output_rounding: bool = True,
) -> dict[str, Any]:
    """Pure computation for methodology expected-loss-v0.4 (hybrid depth/intensity)."""
    hazards.assert_no_lookahead(valuation_date)

    base_eal, per_loss, per_mdr, per_curve, combo = _eal_for_intensities_v0_4(
        asset=asset,
        intensities=hazards.current,
        catalogue=catalogue,
        depths=depths,
        depth_catalogue=depth_catalogue,
        apply_output_rounding=apply_output_rounding,
    )
    # Horizons keep the intensity path (no depth horizons supplied in Phase A).
    scenario_eal: dict[str, float] = {}
    if hazards.horizon_2030 and hazards.horizon_2050:
        eal_2030, _, _, _, _ = _eal_for_intensities_v0_4(
            asset=asset, intensities=hazards.horizon_2030, catalogue=catalogue,
            depths=None, depth_catalogue=None, apply_output_rounding=apply_output_rounding,
        )
        eal_2050, _, _, _, _ = _eal_for_intensities_v0_4(
            asset=asset, intensities=hazards.horizon_2050, catalogue=catalogue,
            depths=None, depth_catalogue=None, apply_output_rounding=apply_output_rounding,
        )
        scenario_eal = {"2030": eal_2030, "2050": eal_2050}
    eal_pct_full = (base_eal / asset.asset_value) * 100.0 if asset.asset_value else 0.0
    current_vals = list(hazards.current.values())
    mean_intensity = sum(current_vals) / len(current_vals) if current_vals else 0.0
    risk_score_full = min(100.0, mean_intensity * _effective_vulnerability(asset) * 100.0)
    collateral_full = min(1.0, base_eal / asset.asset_value) if asset.asset_value else 0.0
    if apply_output_rounding:
        eal_pct, risk_score, collateral = (
            round(eal_pct_full, 6), round(risk_score_full, 4), round(collateral_full, 6)
        )
    else:
        eal_pct, risk_score, collateral = eal_pct_full, risk_score_full, collateral_full
    return {
        "eal_absolute": base_eal,
        "eal_pct_of_value": eal_pct,
        "eal_by_hazard": per_loss,
        "mdr_by_hazard": per_mdr,
        "combined_mdr": combo,
        "curve_ids_by_hazard": per_curve,
        "scenario_eal": scenario_eal,
        "risk_score": risk_score,
        "collateral_sensitivity": collateral,
        "insurability": _insurability(asset),
        "damage_curves_version": damage_curves_version(catalogue),
    }


# Alias used by property tests that exercise the live (latest) formula.
_eal_for_intensities = _eal_for_intensities_v0_3
_compute_core = _compute_core_v0_3

FORMULAS: dict[str, FormulaFn] = {
    EXPECTED_LOSS_METHODOLOGY_V0_2: _compute_core_v0_2,
    EXPECTED_LOSS_METHODOLOGY_VERSION: _compute_core_v0_3,
    EXPECTED_LOSS_METHODOLOGY_V0_4: _compute_core_v0_4,
}


def formula_for_version(methodology_version: str) -> FormulaFn:
    """Resolve a trail/live methodology version to its frozen formula.

    Unknown versions fail explicitly — never fall back to the current formula.
    """
    try:
        return FORMULAS[methodology_version]
    except KeyError as exc:
        raise ValueError(
            f"methodology {methodology_version} not in registry"
        ) from exc


def _asset_from_inputs(raw: dict[str, Any]) -> ExpectedLossAssetInput:
    return ExpectedLossAssetInput.model_validate(raw)


def _hazards_from_inputs(raw: dict[str, Any]) -> HazardScenarioIntensities:
    return HazardScenarioIntensities.model_validate(raw)


def compute_expected_loss(
    *,
    asset: ExpectedLossAssetInput,
    hazards: HazardScenarioIntensities,
    valuation_date: date,
    trail: AppendOnlyAuditTrail | None = None,
    timestamp: datetime | None = None,
    parameters: dict[str, Any] | None = None,
    catalogue: DamageCurveCatalogue | None = None,
    methodology_version: str = EXPECTED_LOSS_METHODOLOGY_VERSION,
    depths: dict[str, float] | None = None,
    depth_catalogue: DepthDamageCatalogue | None = None,
) -> ExpectedLossResult:
    """Compute current loss and any caller-supplied horizon losses.

    Every successful computation writes an audit record before returning. The
    default path uses the latest intensity methodology (v0.3). Pass
    ``methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4`` with ``depths`` and a
    ``depth_catalogue`` to price flood from JRC depth-damage curves; that opt-in
    is stamped, persisted and replayed like any other methodology.
    """
    cat = catalogue or load_catalogue()
    store = get_audit_trail() if trail is None else trail
    params = dict(parameters or {})
    available_horizons = (
        ["2030", "2050"] if hazards.horizon_2030 and hazards.horizon_2050 else []
    )
    params.setdefault("horizons", available_horizons)
    params.setdefault("catalogue_id", cat.catalogue_id)
    params.setdefault("catalogue_version", cat.version)
    params.setdefault("catalogue_source", cat.source)

    is_v04 = methodology_version == EXPECTED_LOSS_METHODOLOGY_V0_4
    if is_v04:
        if not depths:
            raise ValueError("expected-loss-v0.4 requires a non-empty depths map")
        if depth_catalogue is None:
            raise ValueError("expected-loss-v0.4 requires a depth_catalogue")
        params["depth_catalogue_id"] = depth_catalogue.catalogue_id
        params["depth_catalogue_version"] = depth_catalogue.version

    formula = formula_for_version(methodology_version)
    formula_kwargs: dict[str, Any] = {
        "asset": asset,
        "hazards": hazards,
        "valuation_date": valuation_date,
        "catalogue": cat,
    }
    if is_v04:
        formula_kwargs["depths"] = depths
        formula_kwargs["depth_catalogue"] = depth_catalogue
    core = formula(**formula_kwargs)
    ts = timestamp or datetime.now(timezone.utc)
    data_versions = {
        "damage_curves": core["damage_curves_version"],
        **dict(hazards.data_versions or {}),
    }
    if is_v04:
        data_versions["depth_damage"] = (
            f"{depth_catalogue.catalogue_id}-v{depth_catalogue.version}"
        )
    inputs = {
        "asset": asset.model_dump(mode="json"),
        "hazards": hazards.model_dump(mode="json"),
    }
    if is_v04:
        inputs["depths"] = {k: float(v) for k, v in depths.items()}
    outputs = {
        "eal_absolute": core["eal_absolute"],
        "eal_pct_of_value": core["eal_pct_of_value"],
        "eal_by_hazard": core["eal_by_hazard"],
        "mdr_by_hazard": core["mdr_by_hazard"],
        "curve_ids_by_hazard": core["curve_ids_by_hazard"],
        "scenario_eal": core["scenario_eal"],
        "risk_score": core["risk_score"],
        "collateral_sensitivity": core["collateral_sensitivity"],
        "insurability": core["insurability"],
        "attribution_share": attribution_shares(hazards.current),
    }
    if "combined_mdr" in core:
        outputs["combined_mdr"] = core["combined_mdr"]

    # Audit trail must be written before the result is returned.
    record = store.append(
        methodology_version=methodology_version,
        valuation_date=valuation_date,
        data_versions=data_versions,
        parameters=params,
        inputs=inputs,
        outputs=outputs,
        timestamp=ts,
        sources=build_result_manifest(
            data_versions=data_versions, include_registry=False
        ).to_payload(),
    )

    return ExpectedLossResult(
        methodology_version=methodology_version,
        damage_curves_version=core["damage_curves_version"],
        valuation_date=valuation_date,
        asset_id=asset.asset_id,
        eal_absolute=core["eal_absolute"],
        eal_pct_of_value=core["eal_pct_of_value"],
        eal_by_hazard=core["eal_by_hazard"],
        mdr_by_hazard=core["mdr_by_hazard"],
        curve_ids_by_hazard=core["curve_ids_by_hazard"],
        scenario_eal=core["scenario_eal"],
        risk_score=core["risk_score"],
        collateral_sensitivity=core["collateral_sensitivity"],
        insurability=core["insurability"],
        audit_record_id=record.record_id,
        computed_at=ts,
    )


def recompute_eal_from_trail_record(record: AuditTrailRecord) -> dict[str, Any]:
    """Recompute financial outputs from a trail record alone (acceptance path).

    Catalogue id+version and ``methodology_version`` are taken from the record —
    never from process defaults / the latest formula.
    """
    params = record.parameters or {}
    catalogue_id = params.get("catalogue_id")
    catalogue_version = params.get("catalogue_version")
    if not catalogue_id or not catalogue_version:
        raise ValueError(
            "trail record missing parameters.catalogue_id / catalogue_version; "
            "cannot replay without explicit catalogue context"
        )
    cat = load_catalogue_by_id_version(str(catalogue_id), str(catalogue_version))
    asset = _asset_from_inputs(record.inputs["asset"])
    hazards = _hazards_from_inputs(record.inputs["hazards"])
    formula = formula_for_version(record.methodology_version)
    formula_kwargs: dict[str, Any] = {
        "asset": asset,
        "hazards": hazards,
        "valuation_date": record.valuation_date,
        "catalogue": cat,
    }
    if record.methodology_version == EXPECTED_LOSS_METHODOLOGY_V0_4:
        depth_cat_id = params.get("depth_catalogue_id")
        depth_cat_ver = params.get("depth_catalogue_version")
        if not depth_cat_id or not depth_cat_ver:
            raise ValueError(
                "v0.4 trail record missing depth_catalogue_id / depth_catalogue_version"
            )
        formula_kwargs["depths"] = {
            k: float(v) for k, v in (record.inputs.get("depths") or {}).items()
        }
        formula_kwargs["depth_catalogue"] = load_depth_damage_by_id_version(
            str(depth_cat_id), str(depth_cat_ver)
        )
    core = formula(**formula_kwargs)
    out: dict[str, Any] = {
        "eal_absolute": core["eal_absolute"],
        "eal_pct_of_value": core["eal_pct_of_value"],
        "eal_by_hazard": core["eal_by_hazard"],
        "mdr_by_hazard": core["mdr_by_hazard"],
        "curve_ids_by_hazard": core["curve_ids_by_hazard"],
        "scenario_eal": core["scenario_eal"],
        "risk_score": core["risk_score"],
        "collateral_sensitivity": core["collateral_sensitivity"],
        "insurability": core["insurability"],
        "methodology_version": record.methodology_version,
        "catalogue_id": cat.catalogue_id,
        "catalogue_version": cat.version,
    }
    if "combined_mdr" in core:
        out["combined_mdr"] = core["combined_mdr"]
    # v0.2 trail field (do not rename to attribution_share on replay).
    if "attribution_weights" in core:
        out["attribution_weights"] = core["attribution_weights"]
    # v0.3+/v0.4 live trail field — reconstruct from record inputs for parity.
    if record.methodology_version in (
        EXPECTED_LOSS_METHODOLOGY_VERSION,
        EXPECTED_LOSS_METHODOLOGY_V0_4,
    ):
        out["attribution_share"] = attribution_shares(hazards.current)
    return out


class ExpectedLossFinancialTranslation:
    """Adapter: pipeline contract → ``compute_expected_loss`` (methodology v0.3)."""

    def __init__(self, *, trail: AppendOnlyAuditTrail | None = None) -> None:
        self._trail = trail
        self.last_result: ExpectedLossResult | None = None

    def run(
        self,
        ctx: Any,
        hazard: Any,
        exposure: Any,
        vulnerability: Any,
    ) -> Any:
        from app.pipeline.contract import FinancialTranslationResult

        components = dict(hazard.components or {})
        if not components:
            components = {"composite": float(hazard.composite_intensity)}
        # Phase A has current-only stub components. Forward-looking outputs stay
        # absent until a versioned climate-scenario hazard module supplies maps.
        current = {k: float(v) for k, v in components.items()}
        hazards = HazardScenarioIntensities(
            current=current,
            data_versions={
                **dict(getattr(hazard, "data_versions", None) or {}),
                "horizon_method": HORIZON_UNAVAILABLE_METHOD,
            },
            as_of=ctx.valuation_date,
        )
        params = dict(ctx.parameters or {})
        params.update(unavailable_horizon_provenance())
        asset_in = ExpectedLossAssetInput(
            asset_id=exposure.asset_id,
            asset_value=float(exposure.asset_value),
            building_type=exposure.building_type,
            use_class=exposure.use_class,
            fragility_factor=float(vulnerability.fragility_factor),
            adaptation_capacity_factor=float(vulnerability.adaptation_capacity_factor),
            insurance_coverage=getattr(ctx.asset, "insurance_coverage", None),
        )
        result = compute_expected_loss(
            asset=asset_in,
            hazards=hazards,
            valuation_date=ctx.valuation_date,
            trail=self._trail,
            timestamp=getattr(ctx, "timestamp", None),
            parameters=params,
        )
        self.last_result = result
        return FinancialTranslationResult(
            eal_absolute=result.eal_absolute,
            eal_pct_of_value=result.eal_pct_of_value,
            risk_score=result.risk_score,
            scenario_deltas=dict(result.scenario_eal),
            collateral_sensitivity=result.collateral_sensitivity,
            insurability=result.insurability,
        )


__all__ = [
    "EXPECTED_LOSS_METHODOLOGY_VERSION",
    "EXPECTED_LOSS_METHODOLOGY_V0_2",
    "EXPECTED_LOSS_METHODOLOGY_V0_4",
    "FORMULAS",
    "ExpectedLossAssetInput",
    "ExpectedLossFinancialTranslation",
    "ExpectedLossResult",
    "HazardScenarioIntensities",
    "attribution_shares",
    "combined_mdr",
    "compute_expected_loss",
    "formula_for_version",
    "hazard_weights",
    "intensity_sum",
    "recompute_eal_from_trail_record",
]
