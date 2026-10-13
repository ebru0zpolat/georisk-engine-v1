"""Data models for the Regulatory Evidence Pack system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Official source artifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OfficialSourceArtifact:
    """A verified official publication artifact.

    This represents a retrieved and hashed official publication,
    establishing the provenance chain from raw publication bytes
    to threshold values used in regulatory rules.

    artifact_sha256 is the SHA-256 of the raw byte content of the
    retrieved PDF/XML/JSON artifact.  It is NOT computed from rendered
    HTML or copy-pasted text.

    source_checksums_verified is True only after an independent process
    has:
      1. Retrieved the artifact from the official publication domain
      2. Confirmed the publication status is 'current' (not draft/
         superseded/repealed)
      3. Computed a SHA-256 of the raw bytes
      4. Stored the hash as artifact_sha256

    Before this verification, artifact_sha256 MUST be
    PLACEHOLDER_NOT_VERIFIED and source_checksums_verified MUST be False.
    """

    source_id: str
    authority: str
    official_publication_id: str
    title: str
    source_url: str
    retrieved_at: str  # ISO 8601
    effective_from: str  # ISO 8601 date
    effective_until: str | None = None  # None = currently in force
    mime_type: str = "application/pdf"
    byte_length: int = 0
    artifact_sha256: str = "PLACEHOLDER_NOT_VERIFIED"
    source_checksums_verified: bool = False
    status: Literal["current", "superseded", "draft", "repealed"] = "current"
    notes: str = ""


# ---------------------------------------------------------------------------
# Threshold provenance — connects artifact → article/lid → rule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThresholdProvenance:
    """Exact citation linking a regulatory threshold to an official artifact.

    This is the evidence chain:
      official artifact bytes → source SHA256 → article/paragraph/lid
      → threshold value → rule → asset applicability → evidence pack

    Each field represents an independently verifiable link in the chain.
    When any link is missing, the threshold cannot be considered verified.
    """

    rule_id: str
    source_id: str  # Must reference an OfficialSourceArtifact
    official_artifact_sha256: str  # Must match artifact's artifact_sha256
    article_reference: str  # e.g. "Artikel 4.116"
    paragraph_reference: str  # e.g. "Paragraaf 4.4.2"
    lid_reference: str = ""  # e.g. "lid 1(a)"
    page_reference: str = ""  # e.g. "p. 42"
    effective_date: str = ""  # Date this specific threshold text was effective
    provenance_verified: bool = False  # True only after full chain verified


# ---------------------------------------------------------------------------
# Source registry entry (legacy — kept for backward compatibility)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatorySource:
    """A referenced official publication or regulation.

    content_hash: When the actual source artifact has not been retrieved
    and hashed, this MUST be set to the sentinel value
    ``PLACEHOLDER_NOT_VERIFIED``.  A real SHA-256 is only valid when the
    source document has been independently retrieved and its content
    hashed by a verified process.

    source_checksums_verified: False until an independent process has
    retrieved the publication and computed a real SHA-256 of its content.
    """

    source_id: str
    authority: str
    title: str
    reference_url: str
    content_hash: str  # SHA-256 or PLACEHOLDER_NOT_VERIFIED
    source_checksums_verified: bool  # False until real artifact retrieved
    status: Literal["current", "superseded", "draft", "repealed"]
    effective_date: str
    publication_reference: str = ""


# ---------------------------------------------------------------------------
# Applicability filter
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApplicabilityFilter:
    """Asset must match ALL non-None fields for the rule to apply.

    NOTE: Municipality name matching alone is insufficient to prove
    regulatory applicability.  Real applicability requires verifying
    building date, use type, exemptions, transitional provisions,
    and water authority scope.  This filter is a *screening* layer,
    not a legal determination.

    In the full decision chain:
      BAG building geometry → municipality polygon → applicable
      Omgevingsplan rule → applicable Waterschapsverordening polygon
      → asset/project applicability → normative capacity calculation
      → hydrological stress simulation → engineering gate → evidence pack
    """

    municipality: str | None = None
    use_class: str | None = None
    water_authority: str | None = None
    min_built_area_m2: float | None = None
    max_built_area_m2: float | None = None


# ---------------------------------------------------------------------------
# Regulatory rule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatoryRule:
    """A single measurable regulatory requirement.

    Threshold values are sourced from specific publication sections.
    Before any production use, each value must be independently
    verified against the current official publication text.
    """

    rule_id: str
    source_id: str
    rule_type: str
    parameter_name: str
    threshold_value: float
    threshold_unit: str
    comparison: Literal["gte", "lte", "eq"]
    applicability_filter: ApplicabilityFilter = field(default_factory=ApplicabilityFilter)
    # Exact publication evidence for the threshold
    publication_section: str = ""
    publication_page: str = ""
    effective_date: str = ""
    threshold_source_verified: bool = False  # False until independently verified


# ---------------------------------------------------------------------------
# Rule-level result for a single asset
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleResult:
    """Outcome of one rule check against one asset.

    Status uses neutral threshold terminology — NOT compliance language.
    """

    rule_id: str
    applicable: bool
    status: Literal[
        "threshold_satisfied",
        "threshold_not_satisfied",
        "not_applicable",
        "insufficient_data",
        "applicability_unverified",
        "source_unverified",
    ]
    engineered_value: float | None
    threshold_value: float
    threshold_unit: str
    evidence_note: str = ""


# ---------------------------------------------------------------------------
# Asset verification record
# ---------------------------------------------------------------------------

@dataclass
class AssetVerification:
    """Complete verification record for one property asset.

    Overall status uses neutral threshold terminology — NOT compliance
    language.  An overall_status of 'threshold_satisfied' does NOT
    mean the asset is legally compliant, because threshold provenance
    may be unverified, applicability may be incomplete, and exemptions
    may apply.
    """

    asset_id: str
    address: str
    crs: str
    x: float
    y: float
    built_area_m2: float
    use_class: str
    municipality: str
    water_authority: str
    asset_applicability_verified: bool
    applicability_reason: str = ""
    rule_results: list[RuleResult] = field(default_factory=list)
    overall_status: Literal[
        "threshold_satisfied",
        "threshold_not_satisfied",
        "partial",
        "not_applicable",
        "insufficient_data",
        "applicability_unverified",
        "source_unverified",
    ] = "not_applicable"

    def to_dict(self) -> dict:
        """Deterministic dictionary for serialization."""
        return {
            "asset_id": self.asset_id,
            "address": self.address,
            "coordinates": {"crs": self.crs, "x": self.x, "y": self.y},
            "built_area_m2": self.built_area_m2,
            "use_class": self.use_class,
            "municipality": self.municipality,
            "water_authority": self.water_authority,
            "asset_applicability_verified": self.asset_applicability_verified,
            "applicability_reason": self.applicability_reason,
            "rule_results": [
                {
                    "rule_id": r.rule_id,
                    "applicable": r.applicable,
                    "status": r.status,
                    "engineered_value": r.engineered_value,
                    "threshold_value": r.threshold_value,
                    "threshold_unit": r.threshold_unit,
                    "evidence_note": r.evidence_note,
                }
                for r in self.rule_results
            ],
            "overall_status": self.overall_status,
        }


# ---------------------------------------------------------------------------
# Jurisdiction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Jurisdiction:
    level: Literal["municipal", "provincial", "regional", "national", "eu"]
    name: str
    authority_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PackClassification:
    evidence_class: Literal["synthetic_reference", "bounded_pilot", "observed_production"]
    customer_data_status: Literal["not_customer_data", "anonymised_pilot", "consented_customer"]
    production_eligible: bool = False
    decision_use_approved: bool = False
