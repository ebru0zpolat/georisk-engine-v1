"""Regulatory Change Control Registry (RCCR).

Versioned Regulatory Registry for managing regulatory source
artifacts as provenance-aware, fail-closed data objects.  Designed
to sit above the Regulatory Evidence Pack as a control-plane layer.

Architecture:

    OFFICIAL PUBLICATION LAYER
        │
        ├── Netherlands
        │     ├── Officiële bekendmakingen
        │     ├── LVBB / STOP
        │     └── consolidated regulation
        │
        └── European Union
              ├── Official Journal
              ├── EUR-Lex / CELEX
              └── ELI
                    │
                    ▼
          SOURCE ACQUISITION
                    │
                    ▼
           SOURCE ARTIFACT
        raw bytes + metadata
                    │
                    ▼
             SHA-256 seal
                    │
                    ▼
       REGULATORY CHANGE REGISTRY
                    │
           ┌────────┼────────┐
           ▼        ▼        ▼
        ACTIVE    PENDING   RETIRED
           │
           ▼
      RULE MAPPING
           │
           ▼
    REGULATORY EVIDENCE PACK

This module implements the source-intake protocol, lifecycle state
machine, dual-hash verification, amendment lineage tracking, and
source-change detection with rule invalidation.

Implementation status:
  This is the TARGET ARCHITECTURE specification and initial
  implementation.  Automated authoritative-source acquisition,
  amendment-chain reconciliation and regulatory change-control
  invalidation are implementation gates — not production-verified
  capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------

class LifecycleState(str, Enum):
    """Registry entry lifecycle states.

    Progression: DISCOVERED → RETRIEVED → IDENTITY_VERIFIED →
    VERSION_VERIFIED → EFFECTIVE_STATUS_VERIFIED → HASH_VERIFIED →
    ACTIVE_FOR_RULE_MAPPING

    A publication can also reach terminal states:
      PENDING_NOT_EFFECTIVE (draft/consultation)
      PUBLISHED_NOT_EFFECTIVE (published but future effective date)
      RETIRED (repealed)
      SUPERSEDED (replaced by newer version)
      SOURCE_CHANGED_REVIEW_REQUIRED (hash/content changed)
    """
    DISCOVERED = "DISCOVERED"
    RETRIEVED = "RETRIEVED"
    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"
    VERSION_VERIFIED = "VERSION_VERIFIED"
    EFFECTIVE_STATUS_VERIFIED = "EFFECTIVE_STATUS_VERIFIED"
    HASH_VERIFIED = "HASH_VERIFIED"
    ACTIVE_FOR_RULE_MAPPING = "ACTIVE_FOR_RULE_MAPPING"
    # Terminal / non-active states
    PENDING_NOT_EFFECTIVE = "PENDING_NOT_EFFECTIVE"
    PUBLISHED_NOT_EFFECTIVE = "PUBLISHED_NOT_EFFECTIVE"
    RETIRED = "RETIRED"
    SUPERSEDED = "SUPERSEDED"
    SOURCE_CHANGED_REVIEW_REQUIRED = "SOURCE_CHANGED_REVIEW_REQUIRED"


# Valid forward transitions in the lifecycle
_LIFECYCLE_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.DISCOVERED: {LifecycleState.RETRIEVED, LifecycleState.PENDING_NOT_EFFECTIVE},
    LifecycleState.RETRIEVED: {LifecycleState.IDENTITY_VERIFIED},
    LifecycleState.IDENTITY_VERIFIED: {LifecycleState.VERSION_VERIFIED},
    LifecycleState.VERSION_VERIFIED: {LifecycleState.EFFECTIVE_STATUS_VERIFIED, LifecycleState.PUBLISHED_NOT_EFFECTIVE},
    LifecycleState.EFFECTIVE_STATUS_VERIFIED: {LifecycleState.HASH_VERIFIED},
    LifecycleState.HASH_VERIFIED: {LifecycleState.ACTIVE_FOR_RULE_MAPPING},
    # Any active state can transition to SOURCE_CHANGED_REVIEW_REQUIRED
    LifecycleState.ACTIVE_FOR_RULE_MAPPING: {
        LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED,
        LifecycleState.RETIRED,
        LifecycleState.SUPERSEDED,
    },
    LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED: {
        LifecycleState.HASH_VERIFIED,  # re-verification
        LifecycleState.RETIRED,
    },
}


# ---------------------------------------------------------------------------
# Source type classification
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """Classification of regulatory source types.

    Legal sources come from official publication services;
    geospatial sources provide applicability evidence.
    """
    LEGAL_SOURCE = "LEGAL_SOURCE"
    GEOSPATIAL_EVIDENCE = "GEOSPATIAL_EVIDENCE"


# ---------------------------------------------------------------------------
# Regulatory instrument identity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InstrumentIdentity:
    """Official identity of a regulatory instrument.

    For NL sources: official_identifier from Officiële bekendmakingen.
    For EU sources: CELEX number and ELI URI.
    """
    authority: str
    instrument_type: str  # e.g. "omgevingsplan", "waterschapsverordening", "delegated_regulation"
    official_identifier: str
    official_source: str  # e.g. "officielebekendmakingen", "EUR-Lex", "Wetten.nl"
    title: str = ""
    publication_url: str = ""


# ---------------------------------------------------------------------------
# Lifecycle metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LifecycleMetadata:
    """Temporal and status metadata for a regulatory instrument.

    Status values:
      current, draft, consultation, superseded, repealed,
      adopted_not_in_force, published_not_effective
    """
    regulatory_state: Literal[
        "current", "draft", "consultation", "superseded", "repealed",
        "adopted_not_in_force", "published_not_effective",
    ]
    publication_date: str = ""  # ISO 8601 date
    effective_from: str = ""  # ISO 8601 date
    effective_until: str | None = None  # None = currently in force
    consolidation_date: str = ""  # Date of last consolidated text
    adoption_date: str = ""  # For EU: date of adoption
    entry_into_force_date: str = ""  # For EU: date entry into force
    application_from: str = ""  # For EU: date application starts
    transitional_application_from: str = ""  # For EU: transitional period start


# ---------------------------------------------------------------------------
# Provenance (dual-hash)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceProvenance:
    """Provenance of a retrieved source artifact.

    Dual-hash architecture:
      artifact_sha256: SHA-256 of raw byte content (PDF/XML/JSON).
        Fingerprints byte-for-byte integrity of the retrieved artifact.
        A PDF re-rendering can change this hash without changing content.

      normalized_content_sha256: SHA-256 of extracted structural legal
        content (article / paragraph / lid / table).  Remains stable
        across representation changes (PDF re-rendering, formatting).

    When raw hash changes but normalized hash is stable:
      → artifact_representation_changed (not substantive)

    When both change:
      → substantive_change_candidate (triggers rule-impact analysis)
    """
    artifact_sha256: str = "PLACEHOLDER_NOT_VERIFIED"
    normalized_content_sha256: str = "PLACEHOLDER_NOT_VERIFIED"
    retrieved_at: str = ""  # ISO 8601 timestamp
    mime_type: str = "application/pdf"
    byte_length: int = 0
    source_identity_verified: bool = False
    effective_status_verified: bool = False


# ---------------------------------------------------------------------------
# Amendment lineage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AmendmentLineage:
    """Tracks the amendment history of a regulatory instrument.

    Each field references official_identifier values of related
    instruments.  An empty list means no amendments/supersessions.
    """
    amends: tuple[str, ...] = ()  # Instruments this one amends
    amended_by: tuple[str, ...] = ()  # Instruments that amend this one
    supersedes: tuple[str, ...] = ()  # Instruments this one supersedes
    superseded_by: tuple[str, ...] = ()  # Instruments that supersede this one


# ---------------------------------------------------------------------------
# Intake gates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntakeGates:
    """Verification gates for source intake.

    Derived gates:
      authoritative_source_verified =
          official_identity_verified
          AND artifact_retrieved
          AND artifact_hash_verified
          AND effective_status_verified
          AND amendment_chain_verified

      real_regulatory_evidence =
          authoritative_source_verified
          AND rule_mapping_verified

    Note: asset_applicability_verified is INDEPENDENT of these gates.
    A verified source does NOT automatically mean the rule applies to
    a specific asset.
    """
    official_identity_verified: bool = False
    artifact_retrieved: bool = False
    artifact_hash_verified: bool = False
    effective_status_verified: bool = False
    amendment_chain_verified: bool = False
    rule_mapping_verified: bool = False

    # These are independent of the source verification chain
    authoritative_source_verified: bool = False
    real_regulatory_evidence: bool = False

    def compute_derived_gates(self) -> IntakeGates:
        """Compute derived gates from primitive gates.

        Returns a new IntakeGates with authoritative_source_verified
        and real_regulatory_evidence computed.
        """
        authoritative = (
            self.official_identity_verified
            and self.artifact_retrieved
            and self.artifact_hash_verified
            and self.effective_status_verified
            and self.amendment_chain_verified
        )
        real_evidence = authoritative and self.rule_mapping_verified

        return IntakeGates(
            official_identity_verified=self.official_identity_verified,
            artifact_retrieved=self.artifact_retrieved,
            artifact_hash_verified=self.artifact_hash_verified,
            effective_status_verified=self.effective_status_verified,
            amendment_chain_verified=self.amendment_chain_verified,
            rule_mapping_verified=self.rule_mapping_verified,
            authoritative_source_verified=authoritative,
            real_regulatory_evidence=real_evidence,
        )


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------

@dataclass
class RegistryEntry:
    """Immutable registry record for a legal source version.

    Each entry represents a specific version of a regulatory
    instrument with full provenance, lifecycle, and gate state.
    """
    registry_entry_id: str
    source_type: SourceType
    identity: InstrumentIdentity
    lifecycle: LifecycleMetadata
    provenance: SourceProvenance
    lineage: AmendmentLineage = field(default_factory=AmendmentLineage)
    gates: IntakeGates = field(default_factory=IntakeGates)
    lifecycle_state: LifecycleState = LifecycleState.DISCOVERED
    notes: str = ""

    def to_dict(self) -> dict:
        """Deterministic serialization."""
        return {
            "registry_entry_id": self.registry_entry_id,
            "source_type": self.source_type.value,
            "identity": {
                "authority": self.identity.authority,
                "instrument_type": self.identity.instrument_type,
                "official_identifier": self.identity.official_identifier,
                "official_source": self.identity.official_source,
                "title": self.identity.title,
                "publication_url": self.identity.publication_url,
            },
            "lifecycle": {
                "regulatory_state": self.lifecycle.regulatory_state,
                "publication_date": self.lifecycle.publication_date,
                "effective_from": self.lifecycle.effective_from,
                "effective_until": self.lifecycle.effective_until,
                "consolidation_date": self.lifecycle.consolidation_date,
                "adoption_date": self.lifecycle.adoption_date,
                "entry_into_force_date": self.lifecycle.entry_into_force_date,
                "application_from": self.lifecycle.application_from,
                "transitional_application_from": self.lifecycle.transitional_application_from,
            },
            "provenance": {
                "artifact_sha256": self.provenance.artifact_sha256,
                "normalized_content_sha256": self.provenance.normalized_content_sha256,
                "retrieved_at": self.provenance.retrieved_at,
                "mime_type": self.provenance.mime_type,
                "byte_length": self.provenance.byte_length,
                "source_identity_verified": self.provenance.source_identity_verified,
                "effective_status_verified": self.provenance.effective_status_verified,
            },
            "lineage": {
                "amends": list(self.lineage.amends),
                "amended_by": list(self.lineage.amended_by),
                "supersedes": list(self.lineage.supersedes),
                "superseded_by": list(self.lineage.superseded_by),
            },
            "gates": {
                "official_identity_verified": self.gates.official_identity_verified,
                "artifact_retrieved": self.gates.artifact_retrieved,
                "artifact_hash_verified": self.gates.artifact_hash_verified,
                "effective_status_verified": self.gates.effective_status_verified,
                "amendment_chain_verified": self.gates.amendment_chain_verified,
                "rule_mapping_verified": self.gates.rule_mapping_verified,
                "authoritative_source_verified": self.gates.authoritative_source_verified,
                "real_regulatory_evidence": self.gates.real_regulatory_evidence,
            },
            "lifecycle_state": self.lifecycle_state.value,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------

def transition_lifecycle(
    entry: RegistryEntry,
    target_state: LifecycleState,
) -> RegistryEntry:
    """Attempt a lifecycle transition.

    Returns a new RegistryEntry with the updated lifecycle_state.
    Raises ValueError if the transition is not valid.

    Only forward transitions along the defined state machine are
    permitted.  Any active state can transition to
    SOURCE_CHANGED_REVIEW_REQUIRED.
    """
    current = entry.lifecycle_state
    allowed = _LIFECYCLE_TRANSITIONS.get(current, set())

    if target_state not in allowed:
        raise ValueError(
            f"Invalid transition: {current.value} → {target_state.value}. "
            f"Allowed: {sorted(s.value for s in allowed)}"
        )

    return RegistryEntry(
        registry_entry_id=entry.registry_entry_id,
        source_type=entry.source_type,
        identity=entry.identity,
        lifecycle=entry.lifecycle,
        provenance=entry.provenance,
        lineage=entry.lineage,
        gates=entry.gates,
        lifecycle_state=target_state,
        notes=entry.notes,
    )


# ---------------------------------------------------------------------------
# Source-change detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceChangeEvent:
    """Result of comparing a previously verified entry against
    a newly retrieved version of the same instrument.

    change_type:
      artifact_representation_changed — raw hash changed, normalized
        content hash unchanged (e.g. PDF re-rendering)
      substantive_change_candidate — normalized content hash changed
        (regulatory text was modified)
      no_change — both hashes match

    When substantive_change_candidate occurs, rule-impact analysis
    is required and affected rules must be re-verified.
    """
    registry_entry_id: str
    change_type: Literal[
        "no_change",
        "artifact_representation_changed",
        "substantive_change_candidate",
    ]
    previous_raw_hash: str
    new_raw_hash: str
    previous_normalized_hash: str
    new_normalized_hash: str
    affected_rule_ids: tuple[str, ...] = ()
    requires_rule_revalidation: bool = False


def detect_source_change(
    previous: RegistryEntry,
    new_artifact_sha256: str,
    new_normalized_content_sha256: str,
    affected_rule_ids: tuple[str, ...] = (),
) -> SourceChangeEvent:
    """Compare a previously verified entry against a new artifact.

    Returns a SourceChangeEvent describing what changed.

    When the normalized content hash changes, the affected rules
    must be re-verified (fail-closed: set threshold_source_verified=False
    until re-verification completes).
    """
    prev_raw = previous.provenance.artifact_sha256
    prev_norm = previous.provenance.normalized_content_sha256

    if new_artifact_sha256 == prev_raw and new_normalized_content_sha256 == prev_norm:
        return SourceChangeEvent(
            registry_entry_id=previous.registry_entry_id,
            change_type="no_change",
            previous_raw_hash=prev_raw,
            new_raw_hash=new_artifact_sha256,
            previous_normalized_hash=prev_norm,
            new_normalized_hash=new_normalized_content_sha256,
        )

    if new_normalized_content_sha256 != prev_norm:
        return SourceChangeEvent(
            registry_entry_id=previous.registry_entry_id,
            change_type="substantive_change_candidate",
            previous_raw_hash=prev_raw,
            new_raw_hash=new_artifact_sha256,
            previous_normalized_hash=prev_norm,
            new_normalized_hash=new_normalized_content_sha256,
            affected_rule_ids=affected_rule_ids,
            requires_rule_revalidation=True,
        )

    # Raw changed but normalized is stable
    return SourceChangeEvent(
        registry_entry_id=previous.registry_entry_id,
        change_type="artifact_representation_changed",
        previous_raw_hash=prev_raw,
        new_raw_hash=new_artifact_sha256,
        previous_normalized_hash=prev_norm,
        new_normalized_hash=new_normalized_content_sha256,
    )


# ---------------------------------------------------------------------------
# Registry management
# ---------------------------------------------------------------------------

class RegulatoryRegistry:
    """In-memory registry of source entries.

    Manages the lifecycle of regulatory source artifacts and
    detects source changes that may require rule re-validation.
    """

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        # Map official_identifier → list of entry IDs (for version tracking)
        self._versions: dict[str, list[str]] = {}

    def register(self, entry: RegistryEntry) -> None:
        """Register a new entry."""
        if entry.registry_entry_id in self._entries:
            raise ValueError(
                f"Duplicate registry_entry_id: '{entry.registry_entry_id}'"
            )
        self._entries[entry.registry_entry_id] = entry
        oid = entry.identity.official_identifier
        self._versions.setdefault(oid, []).append(entry.registry_entry_id)

    def get(self, entry_id: str) -> RegistryEntry | None:
        return self._entries.get(entry_id)

    def get_versions(self, official_identifier: str) -> list[RegistryEntry]:
        """Get all versions of a regulatory instrument."""
        ids = self._versions.get(official_identifier, [])
        return [self._entries[eid] for eid in ids if eid in self._entries]

    def get_active_entries(self) -> list[RegistryEntry]:
        """Get all entries in ACTIVE_FOR_RULE_MAPPING state."""
        return [
            e for e in self._entries.values()
            if e.lifecycle_state == LifecycleState.ACTIVE_FOR_RULE_MAPPING
        ]

    def check_source_change(
        self,
        entry_id: str,
        new_artifact_sha256: str,
        new_normalized_content_sha256: str,
    ) -> SourceChangeEvent:
        """Check for source changes against a registered entry.

        If a substantive change is detected, the entry is transitioned
        to SOURCE_CHANGED_REVIEW_REQUIRED.
        """
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"Registry entry '{entry_id}' not found")

        # Collect rule IDs that reference this source
        # (In a full implementation, this would query the rule registry)
        affected = ()

        event = detect_source_change(
            entry, new_artifact_sha256, new_normalized_content_sha256, affected
        )

        if event.change_type == "substantive_change_candidate":
            # Transition to SOURCE_CHANGED_REVIEW_REQUIRED
            updated = transition_lifecycle(entry, LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED)
            self._entries[entry_id] = updated

        return event

    def entries_to_dict(self) -> list[dict]:
        """Deterministic serialization of all entries."""
        return [e.to_dict() for e in sorted(self._entries.values(), key=lambda e: e.registry_entry_id)]
