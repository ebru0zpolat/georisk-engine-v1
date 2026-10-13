"""ESRS Evidence Mapping — GeoRisk Engine to CSRD/ESRS E1.

Maps GeoRisk Engine's regulatory screening outputs to ESRS E1
disclosure requirements using versioned instrument + semantic
concept pairs.

Architecture:

    GeoRisk physical-risk evidence
        │
        ├── hazard / exposure / sensitivity
        ├── local regulatory requirements
        ├── adaptation measures
        └── financial exposure
                │
                ▼
         ESRS evidence mapping

This module does NOT:
- Produce compliance verdicts
- Certify regulatory alignment
- Replace professional ESG reporting

Status terminology:
  - evidence_supported / evidence_supported_with_caveats /
    insufficient_evidence / not_assessed  (NOT eligible/aligned)
  - mapped / partially_mapped / unmapped  (NOT compliance status)

Implementation status:
  This is the TARGET ARCHITECTURE specification and initial
  implementation.  Actual ESRS disclosure mapping requires
  portfolio-level data (carrying values, financial statement
  reconciliation) that is not yet available in the pilot
  infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ---------------------------------------------------------------------------
# ESRS evidence status — neutral terminology
# ---------------------------------------------------------------------------

class ESRSEvidenceStatus(str, Enum):
    """Evidence readiness status for ESRS disclosure preparation.

    These statuses describe the evidence state, NOT regulatory
    compliance or alignment.  'evidence_supported' means evidence
    artifacts exist; it does NOT mean the disclosure is complete
    or the undertaking is compliant.
    """
    EVIDENCE_SUPPORTED = "evidence_supported"
    EVIDENCE_SUPPORTED_WITH_CAVEATS = "evidence_supported_with_caveats"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_ASSESSED = "not_assessed"


class ESRSMappingStatus(str, Enum):
    """Mapping completeness status.

    Describes how well GeoRisk outputs map to ESRS disclosure
    requirements.  NOT a compliance or alignment status.
    """
    MAPPED = "mapped"
    PARTIALLY_MAPPED = "partially_mapped"
    UNMAPPED = "unmapped"


# ---------------------------------------------------------------------------
# Versioned ESRS instrument
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ESRSInstrument:
    """A versioned ESRS instrument.

    Critical: the same disclosure requirement number (e.g. E1-3)
    maps to DIFFERENT semantic concepts depending on instrument
    version.  The 2023 in-force standard and the 2026 adopted-not-
    in-force revision have different numbering for the same
    conceptual requirements.

    The 2026 revision is adopted_not_in_force as of August 2026
    and must NOT be used for production disclosure mapping until
    the Parliament/Council scrutiny period completes.
    """
    instrument_id: str  # e.g. "ESRS-2023-2772", "ESRS-2026-REVISION"
    title: str
    official_identifier: str  # e.g. "Reg. (EU) 2023/2772"
    legal_state: Literal[
        "current_in_force",
        "adopted_not_in_force",
        "superseded",
        "repealed",
    ]
    adoption_date: str = ""
    application_from: str = ""  # mandatory application date
    entry_into_force_date: str = ""
    transitional_application_from: str = ""  # optional early application
    amendment_ids: tuple[str, ...] = ()  # amending instruments
    notes: str = ""


# ---------------------------------------------------------------------------
# Disclosure requirement — instrument version + semantic concept
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DisclosureRequirement:
    """A disclosure requirement mapped to a semantic concept.

    Key design: disclosure_requirement alone is insufficient
    because the same number maps to different concepts across
    instrument versions.  The semantic_concept provides the
    stable, version-independent identifier.

    Example:
      ESRS 2023 E1-3 → semantic: "climate_adaptation_actions_and_resources"
      ESRS 2026 E1-5 → semantic: "climate_adaptation_actions_and_resources"
      (same concept, different numbering)
    """
    instrument_id: str  # References ESRSInstrument
    disclosure_requirement: str  # e.g. "E1-3", "E1-5"
    semantic_concept: str  # stable cross-version identifier
    title: str
    description: str = ""
    is_materiality_dependent: bool = True  # most ESRS DRs are materiality-dependent


# ---------------------------------------------------------------------------
# Financial value with provenance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FinancialValue:
    """Portfolio financial value with ESRS-appropriate provenance.

    ESRS Application Requirements specify that anticipated financial
    effects must be based on carrying values from financial statements,
    NOT arbitrary asset valuations.  The value_basis field distinguishes
    between different input types.
    """
    amount: float
    currency: str = "EUR"
    value_basis: Literal[
        "carrying_value",
        "market_value",
        "replacement_cost",
        "user_supplied",
    ] = "user_supplied"
    reporting_date: str = ""
    financial_statement_reconciled: bool = False


# ---------------------------------------------------------------------------
# ESRS mapping result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ESRSDisclosureMapping:
    """Result of mapping one ESRS disclosure requirement.

    Contains the evidence status, mapping status, and references
    to supporting GeoRisk artifacts.  Does NOT assert compliance.
    """
    instrument_id: str
    disclosure_requirement: str
    semantic_concept: str
    evidence_status: ESRSEvidenceStatus
    mapping_status: ESRSMappingStatus
    supporting_evidence_ids: tuple[str, ...] = ()
    supporting_rule_ids: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    notes: str = ""


@dataclass
class ESRSMappingResult:
    """Complete ESRS mapping result for one portfolio.

    Aggregates all disclosure requirement mappings and provides
    the overall evidence readiness picture.  This is an
    evidence-support artifact, NOT a compliance verdict.
    """
    portfolio_id: str
    instrument_id: str  # Which ESRS version is being mapped to
    evidence_status: ESRSEvidenceStatus  # overall
    mapping_status: ESRSMappingStatus  # overall
    disclosure_mappings: list[ESRSDisclosureMapping] = field(default_factory=list)
    financial_value: FinancialValue | None = None
    prohibited_claims_applied: bool = True
    prospective_only: bool = False  # True when using non-current instrument
    notes: str = ""

    def to_dict(self) -> dict:
        """Deterministic serialization."""
        return {
            "portfolio_id": self.portfolio_id,
            "instrument_id": self.instrument_id,
            "evidence_status": self.evidence_status.value,
            "mapping_status": self.mapping_status.value,
            "disclosure_mappings": [
                {
                    "instrument_id": m.instrument_id,
                    "disclosure_requirement": m.disclosure_requirement,
                    "semantic_concept": m.semantic_concept,
                    "evidence_status": m.evidence_status.value,
                    "mapping_status": m.mapping_status.value,
                    "supporting_evidence_ids": list(m.supporting_evidence_ids),
                    "supporting_rule_ids": list(m.supporting_rule_ids),
                    "caveats": list(m.caveats),
                    "notes": m.notes,
                }
                for m in self.disclosure_mappings
            ],
            "financial_value": (
                {
                    "amount": self.financial_value.amount,
                    "currency": self.financial_value.currency,
                    "value_basis": self.financial_value.value_basis,
                    "reporting_date": self.financial_value.reporting_date,
                    "financial_statement_reconciled": self.financial_value.financial_statement_reconciled,
                }
                if self.financial_value
                else None
            ),
            "prohibited_claims_applied": self.prohibited_claims_applied,
            "prospective_only": self.prospective_only,
            "notes": self.notes,
        }
