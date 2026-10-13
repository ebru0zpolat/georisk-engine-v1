"""RAP-012 research-only GeoRisk flood demonstrator."""

from .evidence_adapter import GeoRiskEvidenceAdapter
from .models import (
    DemonstratorAsset,
    DemonstratorOutcome,
    DemonstratorQuestion,
    DemonstratorRunResult,
    GeoRiskEvidenceType,
)
from .report import DemonstratorReport, build_report, to_system_case_result
from .runner import run_georisk_demonstrator
from .scenarios import load_scenario

__all__ = [
    "DemonstratorAsset",
    "DemonstratorOutcome",
    "DemonstratorQuestion",
    "DemonstratorRunResult",
    "GeoRiskEvidenceAdapter",
    "GeoRiskEvidenceType",
    "DemonstratorReport",
    "build_report",
    "to_system_case_result",
    "run_georisk_demonstrator",
    "load_scenario",
]
