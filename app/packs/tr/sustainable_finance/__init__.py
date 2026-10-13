"""``pack-tr`` sustainable-finance evidence layer.

Technical data, methodology and evidence-packaging support for the two CMB/SPK guidelines
adopted by decision ``i-SPK.128.29`` (spec: ``docs/turkiye/sustainable-finance/``).

This layer is support-only: it never determines legal eligibility, approves an issuance,
gives a second-party opinion, or performs verification/assurance. See ``routes.py`` for the
product boundary and ``gates.py`` for the fail-closed controls.
"""

from __future__ import annotations

from app.packs.tr.sustainable_finance.builder import (
    BuiltPack,
    PackSealError,
    build_pack,
    pack_diff,
)
from app.packs.tr.sustainable_finance.claims import (
    ClaimScanResult,
    scan_bundle,
    scan_text,
)
from app.packs.tr.sustainable_finance.gates import (
    KPIGateResult,
    ReleaseGateResult,
    evaluate_kpi_gates,
    evaluate_release_gates,
)
from app.packs.tr.sustainable_finance.physical_risk import (
    HazardReference,
    KPISuitability,
    RecalculationBridge,
    is_available_for_trigger_use,
    lookup_kpi_suitability,
)
from app.packs.tr.sustainable_finance.regulatory_source import (
    DECISION_ID,
    Guideline,
    regulatory_source_manifest,
)
from app.packs.tr.sustainable_finance.routes import (
    EligibilityStatus,
    EngagementRole,
    ExternalReviewType,
    PackStatus,
    RegulatoryRoute,
)
from app.packs.tr.sustainable_finance.schemas import (
    ClaimEntry,
    ClaimsRegister,
    EvidencePackInput,
    ExternalReviewRef,
    ExternalReviewRoles,
    ImpactMetric,
    InstrumentEffect,
    KPIRecord,
    PackManifest,
    PhysicalAdaptationEvidence,
    ProjectEligibilityRecord,
    ProvenanceRecord,
    RoleAssignment,
    SPTRecord,
)

__all__ = [
    "BuiltPack",
    "ClaimEntry",
    "ClaimScanResult",
    "ClaimsRegister",
    "DECISION_ID",
    "EligibilityStatus",
    "EngagementRole",
    "EvidencePackInput",
    "ExternalReviewRef",
    "ExternalReviewRoles",
    "ExternalReviewType",
    "Guideline",
    "HazardReference",
    "ImpactMetric",
    "InstrumentEffect",
    "KPIGateResult",
    "KPIRecord",
    "KPISuitability",
    "PackManifest",
    "PackSealError",
    "PackStatus",
    "PhysicalAdaptationEvidence",
    "ProjectEligibilityRecord",
    "ProvenanceRecord",
    "RecalculationBridge",
    "RegulatoryRoute",
    "ReleaseGateResult",
    "RoleAssignment",
    "SPTRecord",
    "build_pack",
    "evaluate_kpi_gates",
    "evaluate_release_gates",
    "is_available_for_trigger_use",
    "lookup_kpi_suitability",
    "pack_diff",
    "regulatory_source_manifest",
    "scan_bundle",
    "scan_text",
]
