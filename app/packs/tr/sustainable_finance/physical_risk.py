"""Physical climate-risk KPI policy: suitability matrix + constant-hazard rule (spec §8)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class KPISuitability(str, Enum):
    """Default suitability of a physical-risk KPI for sustainability-linked use."""

    reject = "reject"
    conditional = "conditional"
    not_available_for_trigger_use = "not_available_for_trigger_use"


#: Suitability matrix (spec §8.1). Keys are stable candidate-KPI identifiers.
PHYSICAL_RISK_KPI_MATRIX: dict[str, dict[str, str]] = {
    "external_hazard_intensity_reduction": {
        "label": "Reduction in external flood, heat or other hazard intensity",
        "status": KPISuitability.reject.value,
        "reason": "The hazard is not controlled by the issuer.",
    },
    "pct_material_assets_meeting_resilience_threshold": {
        "label": "Percentage of material assets meeting a defined flood/heat resilience threshold",
        "status": KPISuitability.conditional.value,
        "reason": "Potentially controllable and measurable; engineering evidence and stable thresholds required.",
    },
    "asset_weighted_vulnerability_reduction_locked_scenario": {
        "label": "Reduction in asset-weighted vulnerability under a locked hazard scenario",
        "status": KPISuitability.conditional.value,
        "reason": "Separates issuer action from hazard change; methodology must be validated and externally verifiable.",
    },
    "adaptation_plan_completion_rate_high_risk_assets": {
        "label": "Completion rate of approved adaptation plans for high-risk assets",
        "status": KPISuitability.conditional.value,
        "reason": "Verifiable process metric, but materiality and outcome ambition may be challenged.",
    },
    "normalised_climate_disruption_hours": {
        "label": "Normalised climate-related disruption hours",
        "status": KPISuitability.conditional.value,
        "reason": "Outcome-oriented, but event variability, attribution and normalisation must be controlled.",
    },
    "adaptation_capex": {
        "label": "Adaptation capital expenditure",
        "status": KPISuitability.conditional.value,
        "reason": "Measurable input, but expenditure alone may not evidence improved sustainability performance.",
    },
    "modelled_eal_downtime_or_loss_reduction": {
        "label": "Reduction in modelled EAL, downtime or monetary loss",
        "status": KPISuitability.not_available_for_trigger_use.value,
        "reason": "Not suitable while loss pathways rely on synthetic or empirically unvalidated assumptions.",
    },
}


def lookup_kpi_suitability(candidate_id: str) -> dict[str, str] | None:
    """Return the matrix row for a known candidate KPI, or ``None`` if unknown."""
    row = PHYSICAL_RISK_KPI_MATRIX.get(candidate_id)
    return dict(row) if row is not None else None


def is_available_for_trigger_use(candidate_id: str) -> bool:
    """A KPI is trigger-eligible only if it is not rejected or trigger-barred by policy.

    Unknown candidates default to ``False`` (fail closed) — an unrecognised physical-risk
    metric is not presumed trigger-safe.
    """
    row = PHYSICAL_RISK_KPI_MATRIX.get(candidate_id)
    if row is None:
        return False
    status = row["status"]
    return status == KPISuitability.conditional.value


#: The fields that MUST be locked for a constant-hazard before/after comparison (spec §8.2).
CONSTANT_HAZARD_LOCK_FIELDS: tuple[str, ...] = (
    "hazard_definition_and_unit",
    "dataset_and_licence",
    "model_and_ensemble_member",
    "scenario_and_time_horizon",
    "baseline_period",
    "spatial_resolution_and_extraction_method",
    "bias_correction_method",
    "methodology_version",
    "missing_or_nonfinite_value_treatment",
)


class HazardReference(BaseModel):
    """A locked hazard reference for a constant-hazard resilience comparison (spec §8.2)."""

    hazard_definition_and_unit: str
    dataset_and_licence: str
    model_and_ensemble_member: str
    scenario_and_time_horizon: str
    baseline_period: str
    spatial_resolution_and_extraction_method: str
    bias_correction_method: str = "none"
    methodology_version: str
    missing_or_nonfinite_value_treatment: str

    def missing_locks(self) -> list[str]:
        """Locked fields left blank — these must be filled before the reference is usable."""
        missing: list[str] = []
        for field in CONSTANT_HAZARD_LOCK_FIELDS:
            value = getattr(self, field, "")
            if not str(value).strip():
                missing.append(field)
        return missing

    def is_constant_against(self, other: "HazardReference") -> bool:
        """True when every locked field matches ``other`` (hazard held constant)."""
        return all(
            str(getattr(self, f)).strip() == str(getattr(other, f)).strip()
            for f in CONSTANT_HAZARD_LOCK_FIELDS
        )


class RecalculationBridge(BaseModel):
    """Controlled bridge between two methodology/dataset versions (spec §8.2, §13).

    A scientific update that requires a new model or dataset must keep the original result
    reproducible and show the effect of the change through this bridge — historical results
    must never be silently overwritten.
    """

    from_methodology_version: str
    to_methodology_version: str
    reason: str = Field(..., min_length=1)
    original_value: float
    restated_value: float
    original_result_reproducible: bool
    original_run_id: str = Field(..., min_length=1)

    @property
    def delta(self) -> float:
        return round(self.restated_value - self.original_value, 10)

    def is_valid(self) -> tuple[bool, list[str]]:
        problems: list[str] = []
        if not self.original_result_reproducible:
            problems.append("original result is not reproducible — silent overwrite is prohibited")
        if self.from_methodology_version == self.to_methodology_version:
            problems.append("bridge from/to methodology versions are identical")
        if not self.reason.strip():
            problems.append("recalculation reason is empty")
        return (not problems, problems)


__all__ = [
    "CONSTANT_HAZARD_LOCK_FIELDS",
    "HazardReference",
    "KPISuitability",
    "PHYSICAL_RISK_KPI_MATRIX",
    "RecalculationBridge",
    "is_available_for_trigger_use",
    "lookup_kpi_suitability",
]
