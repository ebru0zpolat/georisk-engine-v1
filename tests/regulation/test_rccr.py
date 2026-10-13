"""Comprehensive tests for the Regulatory Change Control Registry (RCCR).

Covers: lifecycle state machine, dual-hash architecture, intake gates,
amendment lineage, source-change detection, rule invalidation,
NL and EU source types, fail-closed invariants.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.regulation.registry import (
    AmendmentLineage,
    IntakeGates,
    InstrumentIdentity,
    LifecycleMetadata,
    LifecycleState,
    RegulatoryRegistry,
    RegistryEntry,
    SourceChangeEvent,
    SourceProvenance,
    SourceType,
    detect_source_change,
    transition_lifecycle,
)

PLACEHOLDER = "PLACEHOLDER_NOT_VERIFIED"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nl_amsterdam_entry() -> RegistryEntry:
    """A NL Amsterdam Omgevingsplan registry entry."""
    return RegistryEntry(
        registry_entry_id="NL-AM-OMGEVINGSPLAN-HW-2026-001",
        source_type=SourceType.LEGAL_SOURCE,
        identity=InstrumentIdentity(
            authority="Gemeente Amsterdam",
            instrument_type="omgevingsplan",
            official_identifier="Omgevingsplan gemeente Amsterdam",
            official_source="officielebekendmakingen",
            title="Omgevingsplan gemeente Amsterdam — Paragraaf 4.4.2",
            publication_url="https://lokaleregelgeving.overheid.nl/DR000417648",
        ),
        lifecycle=LifecycleMetadata(
            regulatory_state="current",
            publication_date="2024-01-01",
            effective_from="2024-01-01",
            effective_until=None,
            consolidation_date="2024-01-01",
        ),
        provenance=SourceProvenance(
            artifact_sha256=PLACEHOLDER,
            normalized_content_sha256=PLACEHOLDER,
            retrieved_at="",
            mime_type="application/pdf",
            byte_length=0,
        ),
        lineage=AmendmentLineage(),
        lifecycle_state=LifecycleState.DISCOVERED,
    )


@pytest.fixture
def eu_esrs_entry() -> RegistryEntry:
    """A EU ESRS delegated regulation entry."""
    return RegistryEntry(
        registry_entry_id="EU-ESRS-2026-REVISION-001",
        source_type=SourceType.LEGAL_SOURCE,
        identity=InstrumentIdentity(
            authority="European Commission",
            instrument_type="delegated_regulation",
            official_identifier="C(2026)5010",
            official_source="EUR-Lex",
            title="Commission Delegated Regulation — ESRS amendments",
            publication_url="https://eur-lex.europa.eu/",
        ),
        lifecycle=LifecycleMetadata(
            regulatory_state="adopted_not_in_force",
            adoption_date="2026-07-03",
            application_from="2027-01-01",
        ),
        provenance=SourceProvenance(
            artifact_sha256=PLACEHOLDER,
            normalized_content_sha256=PLACEHOLDER,
        ),
        lineage=AmendmentLineage(amends=("eu-2023-2772",)),
        lifecycle_state=LifecycleState.DISCOVERED,
    )


@pytest.fixture
def fully_verified_entry() -> RegistryEntry:
    """An entry that has been fully verified and is ACTIVE."""
    real_sha = hashlib.sha256(b"verified content").hexdigest()
    norm_sha = hashlib.sha256(b"normalized content").hexdigest()
    return RegistryEntry(
        registry_entry_id="VERIFIED-001",
        source_type=SourceType.LEGAL_SOURCE,
        identity=InstrumentIdentity(
            authority="Gemeente Amsterdam",
            instrument_type="omgevingsplan",
            official_identifier="Omgevingsplan gemeente Amsterdam",
            official_source="officielebekendmakingen",
        ),
        lifecycle=LifecycleMetadata(
            regulatory_state="current",
            effective_from="2024-01-01",
        ),
        provenance=SourceProvenance(
            artifact_sha256=real_sha,
            normalized_content_sha256=norm_sha,
            retrieved_at="2026-08-27T10:00:00Z",
            mime_type="application/pdf",
            byte_length=123456,
            source_identity_verified=True,
            effective_status_verified=True,
        ),
        gates=IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=True,
            effective_status_verified=True,
            amendment_chain_verified=True,
            rule_mapping_verified=True,
        ).compute_derived_gates(),
        lifecycle_state=LifecycleState.ACTIVE_FOR_RULE_MAPPING,
    )


# ---------------------------------------------------------------------------
# Lifecycle state machine tests
# ---------------------------------------------------------------------------

class TestLifecycleStateMachine:
    def test_discovered_to_retrieved(self, nl_amsterdam_entry: RegistryEntry):
        updated = transition_lifecycle(nl_amsterdam_entry, LifecycleState.RETRIEVED)
        assert updated.lifecycle_state == LifecycleState.RETRIEVED

    def test_full_happy_path(self, nl_amsterdam_entry: RegistryEntry):
        """DISCOVERED → RETRIEVED → IDENTITY_VERIFIED → VERSION_VERIFIED →
        EFFECTIVE_STATUS_VERIFIED → HASH_VERIFIED → ACTIVE_FOR_RULE_MAPPING"""
        e = nl_amsterdam_entry
        for target in [
            LifecycleState.RETRIEVED,
            LifecycleState.IDENTITY_VERIFIED,
            LifecycleState.VERSION_VERIFIED,
            LifecycleState.EFFECTIVE_STATUS_VERIFIED,
            LifecycleState.HASH_VERIFIED,
            LifecycleState.ACTIVE_FOR_RULE_MAPPING,
        ]:
            e = transition_lifecycle(e, target)
        assert e.lifecycle_state == LifecycleState.ACTIVE_FOR_RULE_MAPPING

    def test_invalid_transition_raises(self, nl_amsterdam_entry: RegistryEntry):
        """Cannot skip steps in the lifecycle."""
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_lifecycle(nl_amsterdam_entry, LifecycleState.ACTIVE_FOR_RULE_MAPPING)

    def test_cannot_go_backwards(self, fully_verified_entry: RegistryEntry):
        """Cannot transition from ACTIVE back to DISCOVERED."""
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_lifecycle(fully_verified_entry, LifecycleState.DISCOVERED)

    def test_active_to_source_changed(self, fully_verified_entry: RegistryEntry):
        updated = transition_lifecycle(fully_verified_entry, LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED)
        assert updated.lifecycle_state == LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED

    def test_source_changed_can_reverify(self, fully_verified_entry: RegistryEntry):
        """SOURCE_CHANGED → HASH_VERIFIED (re-verification)."""
        e = transition_lifecycle(fully_verified_entry, LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED)
        e = transition_lifecycle(e, LifecycleState.HASH_VERIFIED)
        assert e.lifecycle_state == LifecycleState.HASH_VERIFIED

    def test_source_changed_can_retire(self, fully_verified_entry: RegistryEntry):
        e = transition_lifecycle(fully_verified_entry, LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED)
        e = transition_lifecycle(e, LifecycleState.RETIRED)
        assert e.lifecycle_state == LifecycleState.RETIRED

    def test_active_to_retired(self, fully_verified_entry: RegistryEntry):
        updated = transition_lifecycle(fully_verified_entry, LifecycleState.RETIRED)
        assert updated.lifecycle_state == LifecycleState.RETIRED

    def test_active_to_superseded(self, fully_verified_entry: RegistryEntry):
        updated = transition_lifecycle(fully_verified_entry, LifecycleState.SUPERSEDED)
        assert updated.lifecycle_state == LifecycleState.SUPERSEDED

    def test_draft_goes_to_pending(self, nl_amsterdam_entry: RegistryEntry):
        updated = transition_lifecycle(nl_amsterdam_entry, LifecycleState.PENDING_NOT_EFFECTIVE)
        assert updated.lifecycle_state == LifecycleState.PENDING_NOT_EFFECTIVE

    def test_version_verified_to_published_not_effective(self, nl_amsterdam_entry: RegistryEntry):
        e = nl_amsterdam_entry
        e = transition_lifecycle(e, LifecycleState.RETRIEVED)
        e = transition_lifecycle(e, LifecycleState.IDENTITY_VERIFIED)
        e = transition_lifecycle(e, LifecycleState.VERSION_VERIFIED)
        e = transition_lifecycle(e, LifecycleState.PUBLISHED_NOT_EFFECTIVE)
        assert e.lifecycle_state == LifecycleState.PUBLISHED_NOT_EFFECTIVE

    def test_preserves_entry_fields(self, nl_amsterdam_entry: RegistryEntry):
        """Transition preserves all other entry fields."""
        updated = transition_lifecycle(nl_amsterdam_entry, LifecycleState.RETRIEVED)
        assert updated.registry_entry_id == nl_amsterdam_entry.registry_entry_id
        assert updated.identity == nl_amsterdam_entry.identity
        assert updated.lifecycle == nl_amsterdam_entry.lifecycle
        assert updated.provenance == nl_amsterdam_entry.provenance
        assert updated.lineage == nl_amsterdam_entry.lineage
        assert updated.gates == nl_amsterdam_entry.gates


# ---------------------------------------------------------------------------
# Dual-hash architecture tests
# ---------------------------------------------------------------------------

class TestDualHashArchitecture:
    def test_raw_hash_stable_across_representation(self):
        """Raw hash changes but normalized hash stays → artifact_representation_changed."""
        real_sha = hashlib.sha256(b"original PDF").hexdigest()
        norm_sha = hashlib.sha256(b"article 4.116 text").hexdigest()
        new_raw_sha = hashlib.sha256(b"re-rendered PDF").hexdigest()

        entry = RegistryEntry(
            registry_entry_id="TEST-001",
            source_type=SourceType.LEGAL_SOURCE,
            identity=InstrumentIdentity(
                authority="Test", instrument_type="test",
                official_identifier="test-id", official_source="test",
            ),
            lifecycle=LifecycleMetadata(regulatory_state="current"),
            provenance=SourceProvenance(
                artifact_sha256=real_sha,
                normalized_content_sha256=norm_sha,
            ),
            lifecycle_state=LifecycleState.ACTIVE_FOR_RULE_MAPPING,
        )

        event = detect_source_change(entry, new_raw_sha, norm_sha)
        assert event.change_type == "artifact_representation_changed"
        assert not event.requires_rule_revalidation

    def test_substantive_change_detected(self):
        """Both hashes change → substantive_change_candidate."""
        real_sha = hashlib.sha256(b"original PDF").hexdigest()
        norm_sha = hashlib.sha256(b"original text").hexdigest()
        new_raw_sha = hashlib.sha256(b"new PDF").hexdigest()
        new_norm_sha = hashlib.sha256(b"new text").hexdigest()

        entry = RegistryEntry(
            registry_entry_id="TEST-002",
            source_type=SourceType.LEGAL_SOURCE,
            identity=InstrumentIdentity(
                authority="Test", instrument_type="test",
                official_identifier="test-id", official_source="test",
            ),
            lifecycle=LifecycleMetadata(regulatory_state="current"),
            provenance=SourceProvenance(
                artifact_sha256=real_sha,
                normalized_content_sha256=norm_sha,
            ),
            lifecycle_state=LifecycleState.ACTIVE_FOR_RULE_MAPPING,
        )

        event = detect_source_change(
            entry, new_raw_sha, new_norm_sha,
            affected_rule_ids=("RULE-001", "RULE-002"),
        )
        assert event.change_type == "substantive_change_candidate"
        assert event.requires_rule_revalidation
        assert event.affected_rule_ids == ("RULE-001", "RULE-002")

    def test_no_change(self):
        """Both hashes match → no_change."""
        real_sha = hashlib.sha256(b"content").hexdigest()
        norm_sha = hashlib.sha256(b"normalized").hexdigest()

        entry = RegistryEntry(
            registry_entry_id="TEST-003",
            source_type=SourceType.LEGAL_SOURCE,
            identity=InstrumentIdentity(
                authority="Test", instrument_type="test",
                official_identifier="test-id", official_source="test",
            ),
            lifecycle=LifecycleMetadata(regulatory_state="current"),
            provenance=SourceProvenance(
                artifact_sha256=real_sha,
                normalized_content_sha256=norm_sha,
            ),
            lifecycle_state=LifecycleState.ACTIVE_FOR_RULE_MAPPING,
        )

        event = detect_source_change(entry, real_sha, norm_sha)
        assert event.change_type == "no_change"
        assert not event.requires_rule_revalidation


# ---------------------------------------------------------------------------
# Intake gates tests
# ---------------------------------------------------------------------------

class TestIntakeGates:
    def test_all_false_initially(self):
        gates = IntakeGates()
        assert gates.authoritative_source_verified is False
        assert gates.real_regulatory_evidence is False

    def test_authoritative_requires_all_primitives(self):
        """authoritative_source_verified = all 5 primitives."""
        full = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=True,
            effective_status_verified=True,
            amendment_chain_verified=True,
        ).compute_derived_gates()
        assert full.authoritative_source_verified is True
        assert full.real_regulatory_evidence is False  # rule_mapping not set

    def test_real_evidence_requires_authoritative_and_rule_mapping(self):
        """real_regulatory_evidence = authoritative AND rule_mapping_verified."""
        full = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=True,
            effective_status_verified=True,
            amendment_chain_verified=True,
            rule_mapping_verified=True,
        ).compute_derived_gates()
        assert full.authoritative_source_verified is True
        assert full.real_regulatory_evidence is True

    def test_missing_one_primitive_blocks_authoritative(self):
        """Missing any one primitive → authoritative = False."""
        for field_name in [
            "official_identity_verified",
            "artifact_retrieved",
            "artifact_hash_verified",
            "effective_status_verified",
            "amendment_chain_verified",
        ]:
            gates = IntakeGates(
                official_identity_verified=True,
                artifact_retrieved=True,
                artifact_hash_verified=True,
                effective_status_verified=True,
                amendment_chain_verified=True,
            )
            # Set the specific field to False
            object.__setattr__(gates, field_name, False)
            computed = gates.compute_derived_gates()
            assert computed.authoritative_source_verified is False, (
                f"Missing {field_name} should block authoritative_source_verified"
            )

    def test_applicability_independent_of_source_gates(self):
        """asset_applicability_verified is NOT part of IntakeGates."""
        # The gates don't have an applicability field — it's a separate concern
        gates = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=True,
            effective_status_verified=True,
            amendment_chain_verified=True,
            rule_mapping_verified=True,
        ).compute_derived_gates()
        assert gates.authoritative_source_verified is True
        # applicability is checked at asset level, not source level


# ---------------------------------------------------------------------------
# Amendment lineage tests
# ---------------------------------------------------------------------------

class TestAmendmentLineage:
    def test_empty_lineage(self):
        lineage = AmendmentLineage()
        assert lineage.amends == ()
        assert lineage.amended_by == ()
        assert lineage.supersedes == ()
        assert lineage.superseded_by == ()

    def test_with_amendments(self):
        lineage = AmendmentLineage(amends=("eu-2023-2772",))
        assert "eu-2023-2772" in lineage.amends

    def test_lineage_in_entry(self, eu_esrs_entry: RegistryEntry):
        assert "eu-2023-2772" in eu_esrs_entry.lineage.amends


# ---------------------------------------------------------------------------
# NL source type tests
# ---------------------------------------------------------------------------

class TestNLSources:
    def test_nl_entry_structure(self, nl_amsterdam_entry: RegistryEntry):
        assert nl_amsterdam_entry.source_type == SourceType.LEGAL_SOURCE
        assert nl_amsterdam_entry.identity.official_source == "officielebekendmakingen"
        assert nl_amsterdam_entry.identity.instrument_type == "omgevingsplan"
        assert nl_amsterdam_entry.lifecycle.regulatory_state == "current"

    def test_nl_entry_to_dict(self, nl_amsterdam_entry: RegistryEntry):
        d = nl_amsterdam_entry.to_dict()
        assert d["registry_entry_id"] == "NL-AM-OMGEVINGSPLAN-HW-2026-001"
        assert d["source_type"] == "LEGAL_SOURCE"
        assert d["identity"]["official_source"] == "officielebekendmakingen"

    def test_nl_provenance_placeholders(self, nl_amsterdam_entry: RegistryEntry):
        assert nl_amsterdam_entry.provenance.artifact_sha256 == PLACEHOLDER
        assert nl_amsterdam_entry.provenance.normalized_content_sha256 == PLACEHOLDER
        assert nl_amsterdam_entry.provenance.source_identity_verified is False


# ---------------------------------------------------------------------------
# EU source type tests
# ---------------------------------------------------------------------------

class TestEUSources:
    def test_eu_entry_structure(self, eu_esrs_entry: RegistryEntry):
        assert eu_esrs_entry.source_type == SourceType.LEGAL_SOURCE
        assert eu_esrs_entry.identity.official_source == "EUR-Lex"
        assert eu_esrs_entry.identity.instrument_type == "delegated_regulation"

    def test_eu_lifecycle_metadata(self, eu_esrs_entry: RegistryEntry):
        assert eu_esrs_entry.lifecycle.regulatory_state == "adopted_not_in_force"
        assert eu_esrs_entry.lifecycle.adoption_date == "2026-07-03"
        assert eu_esrs_entry.lifecycle.application_from == "2027-01-01"

    def test_eu_lineage(self, eu_esrs_entry: RegistryEntry):
        assert "eu-2023-2772" in eu_esrs_entry.lineage.amends


# ---------------------------------------------------------------------------
# Registry management tests
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_register_and_get(self, nl_amsterdam_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(nl_amsterdam_entry)
        assert reg.get("NL-AM-OMGEVINGSPLAN-HW-2026-001") is nl_amsterdam_entry

    def test_duplicate_id_rejected(self, nl_amsterdam_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(nl_amsterdam_entry)
        with pytest.raises(ValueError, match="Duplicate"):
            reg.register(nl_amsterdam_entry)

    def test_get_nonexistent(self):
        reg = RegulatoryRegistry()
        assert reg.get("nonexistent") is None

    def test_get_versions(self, nl_amsterdam_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(nl_amsterdam_entry)
        versions = reg.get_versions("Omgevingsplan gemeente Amsterdam")
        assert len(versions) == 1

    def test_get_active_entries(self, fully_verified_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(fully_verified_entry)
        active = reg.get_active_entries()
        assert len(active) == 1
        assert active[0].registry_entry_id == "VERIFIED-001"

    def test_get_active_excludes_non_active(self, nl_amsterdam_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(nl_amsterdam_entry)
        active = reg.get_active_entries()
        assert len(active) == 0

    def test_entries_to_dict_deterministic(self, nl_amsterdam_entry: RegistryEntry, eu_esrs_entry: RegistryEntry):
        reg = RegulatoryRegistry()
        reg.register(nl_amsterdam_entry)
        reg.register(eu_esrs_entry)
        d1 = reg.entries_to_dict()
        d2 = reg.entries_to_dict()
        assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

    def test_source_change_detection(self, fully_verified_entry: RegistryEntry):
        """Substantive change triggers lifecycle transition."""
        reg = RegulatoryRegistry()
        reg.register(fully_verified_entry)

        new_norm = hashlib.sha256(b"changed text").hexdigest()
        new_raw = hashlib.sha256(b"changed PDF").hexdigest()

        event = reg.check_source_change(
            "VERIFIED-001", new_raw, new_norm
        )
        assert event.change_type == "substantive_change_candidate"
        assert event.requires_rule_revalidation

        # Entry should now be in SOURCE_CHANGED_REVIEW_REQUIRED
        updated = reg.get("VERIFIED-001")
        assert updated.lifecycle_state == LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED

    def test_source_change_nonexistent_raises(self):
        reg = RegulatoryRegistry()
        with pytest.raises(KeyError, match="not found"):
            reg.check_source_change("nonexistent", "a" * 64, "b" * 64)


# ---------------------------------------------------------------------------
# Fail-closed invariants
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_placeholder_prevents_authoritative(self):
        """PLACEHOLDER_NOT_VERIFIED → authoritative_source_verified=False."""
        gates = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=False,  # placeholder hash
            effective_status_verified=True,
            amendment_chain_verified=True,
        ).compute_derived_gates()
        assert gates.authoritative_source_verified is False

    def test_unverified_source_cannot_produce_real_evidence(self):
        """real_regulatory_evidence requires authoritative_source_verified."""
        gates = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=True,
            effective_status_verified=True,
            amendment_chain_verified=True,
            rule_mapping_verified=True,
        ).compute_derived_gates()
        # All true → real_evidence = True
        assert gates.real_regulatory_evidence is True

        # Remove one → authoritative = False → real_evidence = False
        partial = IntakeGates(
            official_identity_verified=True,
            artifact_retrieved=True,
            artifact_hash_verified=False,  # this breaks it
            effective_status_verified=True,
            amendment_chain_verified=True,
            rule_mapping_verified=True,
        ).compute_derived_gates()
        assert partial.authoritative_source_verified is False
        assert partial.real_regulatory_evidence is False

    def test_source_changed_requires_revalidation(self, fully_verified_entry: RegistryEntry):
        """After source change, entry must be re-verified before returning to ACTIVE."""
        reg = RegulatoryRegistry()
        reg.register(fully_verified_entry)

        new_norm = hashlib.sha256(b"different text").hexdigest()
        new_raw = hashlib.sha256(b"different PDF").hexdigest()

        reg.check_source_change("VERIFIED-001", new_raw, new_norm)

        entry = reg.get("VERIFIED-001")
        assert entry.lifecycle_state == LifecycleState.SOURCE_CHANGED_REVIEW_REQUIRED

        # Cannot go directly back to ACTIVE — must go through HASH_VERIFIED
        with pytest.raises(ValueError):
            transition_lifecycle(entry, LifecycleState.ACTIVE_FOR_RULE_MAPPING)

        # Must re-verify
        entry = transition_lifecycle(entry, LifecycleState.HASH_VERIFIED)
        assert entry.lifecycle_state == LifecycleState.HASH_VERIFIED


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_entry_to_dict_roundtrip(self, nl_amsterdam_entry: RegistryEntry):
        d = nl_amsterdam_entry.to_dict()
        assert d["registry_entry_id"] == "NL-AM-OMGEVINGSPLAN-HW-2026-001"
        assert d["lifecycle_state"] == "DISCOVERED"
        assert d["source_type"] == "LEGAL_SOURCE"

    def test_gates_serialization(self, fully_verified_entry: RegistryEntry):
        d = fully_verified_entry.to_dict()
        assert d["gates"]["authoritative_source_verified"] is True
        assert d["gates"]["real_regulatory_evidence"] is True

    def test_provenance_serialization(self, fully_verified_entry: RegistryEntry):
        d = fully_verified_entry.to_dict()
        assert d["provenance"]["artifact_sha256"] != PLACEHOLDER
        assert d["provenance"]["source_identity_verified"] is True
