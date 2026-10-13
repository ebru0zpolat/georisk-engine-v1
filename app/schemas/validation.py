"""Audit-ready evidence trail and validation API schemas.

Core principle (see GEO-121): GeoRisk does **not** reproduce company-reported figures.
It generates independent signals and flags divergence. Each :class:`EvidenceRecord`
makes one comparison traceable end-to-end — reported metric source, GeoRisk signal
source, methodology applied, and the resulting flag.

The HTTP API exposes a slimmer :class:`ValidationReport` / :class:`ValidationResult`
view built from persisted :class:`EvidenceTrail` fixtures under ``data/evidence/``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# --- evidence trail (VAL-005) ---------------------------------------------


class DivergenceFlag(str, Enum):
    """Validation outcome bands (thresholds in :data:`app.services.validation_service`)."""

    GREEN = "green"  # within ±15% or directionally consistent
    AMBER = "amber"  # 15–40% deviation or data-source gap
    RED = "red"  # >40% deviation or directional inconsistency
    NO_SIGNAL = "no_signal"  # GeoRisk cannot produce an independent signal


class ReportedMetric(BaseModel):
    """The company-disclosed value being checked (TSRS report reference)."""

    field: str = Field(..., description="Canonical metric key, e.g. ``scope_1_emissions``.")
    value: float | None = Field(
        default=None, description="Reported numeric value; null when only narrative is disclosed."
    )
    unit: str | None = None
    source: str = Field(..., description="TSRS report page/table reference for traceability.")
    assurance: Literal["reasonable", "limited", "none"] = Field(
        default="none", description="Third-party assurance level on the reported figure."
    )


class GeoRiskSignal(BaseModel):
    """The independent GeoRisk signal compared against the reported metric."""

    type: str = Field(..., description="Signal identifier, e.g. ``sectoral_emission_intensity_proxy``.")
    value: float | None = Field(
        default=None, description="Signal value in the same unit as the reported metric; null if no signal."
    )
    unit: str | None = None
    source: str = Field(..., description="Data provenance, e.g. ``World Steel 2024 + production proxy``.")
    source_version: str = Field(..., description="Dataset/feed version or snapshot date for reproducibility.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Signal confidence in the 0–1 band.")


class MethodologyRef(BaseModel):
    """Formula, threshold and version of the rule applied to derive the flag."""

    method: str = Field(..., description="Short methodology label, e.g. ``Emission intensity divergence``.")
    formula: str | None = Field(default=None, description="Human-readable formula applied.")
    threshold: str = Field(..., description="Flag threshold rule applied to ``divergence_pct``.")
    notes_tr: str | None = Field(default=None, description="Audit note (TR) — caveats, methodology alignment.")


class EvidenceRecord(BaseModel):
    """One audit-ready validation comparison, traceable end-to-end."""

    validation_id: str = Field(..., description="Stable id, e.g. ``ERD-2024-SCOPE1-001``.")
    reported_metric: ReportedMetric
    georisk_signal: GeoRiskSignal
    methodology: MethodologyRef
    divergence_pct: float | None = Field(
        default=None,
        description="Signed deviation of signal vs reported, percent; null when no signal.",
    )
    flag: DivergenceFlag
    explanation: str
    georisk_version: str = Field(..., description="GeoRisk engine version that produced this record.")
    generated_at: datetime


class EvidenceTrail(BaseModel):
    """Full evidence set for one benchmark case (e.g. Erdemir 2024)."""

    schema_version: str = "1.0"
    case_id: str = Field(..., description="Benchmark case identifier, e.g. ``erdemir_2024``.")
    subject_tr: str = Field(..., description="Subject of validation (company / asset), Turkish label.")
    georisk_version: str
    generated_at: datetime
    records: list[EvidenceRecord] = Field(default_factory=list)

    def summary_counts(self) -> dict[str, int]:
        """Flag → count rollup across all records (every flag value present)."""
        counts = {flag.value: 0 for flag in DivergenceFlag}
        for rec in self.records:
            counts[rec.flag.value] += 1
        return counts


# --- HTTP API (VAL-006) ---------------------------------------------------

# Magnitude-only thresholds for programmatic flag derivation in unit tests.
AMBER_THRESHOLD_PCT = 15.0
RED_THRESHOLD_PCT = 30.0


class ValidationFlag(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


def flag_for_divergence(divergence_pct: float) -> ValidationFlag:
    """Map an absolute divergence percentage to a traffic-light flag."""

    magnitude = abs(divergence_pct)
    if magnitude <= AMBER_THRESHOLD_PCT:
        return ValidationFlag.GREEN
    if magnitude <= RED_THRESHOLD_PCT:
        return ValidationFlag.AMBER
    return ValidationFlag.RED


def divergence_flag_to_validation(flag: DivergenceFlag) -> ValidationFlag:
    """Map persisted evidence flags to the three-band API summary."""

    if flag is DivergenceFlag.GREEN:
        return ValidationFlag.GREEN
    if flag is DivergenceFlag.RED:
        return ValidationFlag.RED
    return ValidationFlag.AMBER


class ValidationResult(BaseModel):
    """Single audit-ready evidence record exposed via the validation API."""

    validation_id: str = Field(..., description="Stable id, e.g. ERD-2024-SCOPE1-001.")
    reported_metric: ReportedMetric
    georisk_signal: GeoRiskSignal
    divergence_pct: float = Field(
        ..., description="Signed percent difference of the signal from the reported value."
    )
    flag: ValidationFlag
    explanation: str
    georisk_version: str = Field(..., description="GeoRisk methodology/engine version.")
    data_source_version: str = Field(..., description="Version of the underlying data sources.")
    generated_at: datetime


class ValidationSummary(BaseModel):
    total: int = Field(..., description="Total validated fields.")
    flagged_green: int
    flagged_amber: int
    flagged_red: int

    @classmethod
    def from_results(cls, results: list[ValidationResult]) -> ValidationSummary:
        counts = {flag: 0 for flag in ValidationFlag}
        for result in results:
            counts[result.flag] += 1
        return cls(
            total=len(results),
            flagged_green=counts[ValidationFlag.GREEN],
            flagged_amber=counts[ValidationFlag.AMBER],
            flagged_red=counts[ValidationFlag.RED],
        )


class ValidationReport(BaseModel):
    company_id: str
    reporting_year: int
    sector: str
    results: list[ValidationResult]
    summary: ValidationSummary
    generated_at: datetime


class BenchmarkRequest(BaseModel):
    company_id: str = Field(..., description="Company identifier, e.g. erdemir.")
    reporting_year: int = Field(..., ge=2000, le=2100)
    sector: str = Field(..., description="Sector label, e.g. steel.")
