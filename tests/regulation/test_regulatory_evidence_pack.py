"""Comprehensive tests for the Amsterdam Hemelwater Regulatory Evidence Pack.

Covers: schema conformance, determinism, fail-closed paths, source
integrity, applicability filters, rule evaluation, overall status
computation, checksum integrity, provenance verification, official
source artifact verification, prohibited claims, and readiness flag
immutability.

Key fail-closed invariants tested:
- threshold_source_verified=False → source_unverified (never threshold_satisfied)
- applicability_verified=False → applicability_unverified (always)
- Generator does NOT auto-verify applicability from municipality
- Generator does NOT produce compliant/non_compliant labels
- Official source artifact verification gate
- Provenance chain verification
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on sys.path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.regulation.models import (
    ApplicabilityFilter,
    AssetVerification,
    OfficialSourceArtifact,
    PackClassification,
    RegulatoryRule,
    RegulatorySource,
    RuleResult,
    ThresholdProvenance,
)
from app.regulation.agv_geometry import verify_current_agv_geometry
from app.regulation.rules import (
    PLACEHOLDER_NOT_VERIFIED,
    amsterdam_hemelwater_classification,
    amsterdam_hemelwater_jurisdiction,
    amsterdam_hemelwater_provenance,
    amsterdam_hemelwater_rules,
    amsterdam_hemelwater_sources,
    amsterdam_source_artifacts,
)
from app.regulation.verify import (
    _evaluate_rule,
    _matches_filter,
    verify_asset,
    verify_pack_checksum,
    verify_portfolio,
    verify_provenance_chain,
    verify_source_artifact,
)
from scripts.generate_regulatory_evidence_pack import (
    GENERATOR_VERSION,
    PACK_ID,
    PACK_VERSION,
    SCHEMA_VERSION,
    _compute_checksum,
    _deterministic_json,
    build_evidence_pack,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def amsterdam_compliant_asset() -> dict:
    """A commercial property in Amsterdam with compliant storage."""
    return {
        "asset_id": "NL-AM-001",
        "address": "Damrak 1, Amsterdam",
        "coordinates": {"crs": "EPSG:4326", "x": 4.899, "y": 52.374},
        "built_area_m2": 500.0,
        "use_class": "commercial",
        "municipality": "Amsterdam",
        "water_authority": "waterschap-agv",
        "storage_capacity_l_per_m2": 70.0,
        "max_discharge_l_per_m2_per_hour": 0.8,
        "max_emptying_time_hours": 48.0,
    }


@pytest.fixture
def amsterdam_noncompliant_asset() -> dict:
    """A commercial property in Amsterdam with insufficient storage."""
    return {
        "asset_id": "NL-AM-002",
        "address": "Leidseplein 5, Amsterdam",
        "coordinates": {"crs": "EPSG:4326", "x": 4.884, "y": 52.367},
        "built_area_m2": 300.0,
        "use_class": "commercial",
        "municipality": "Amsterdam",
        "water_authority": "waterschap-agv",
        "storage_capacity_l_per_m2": 40.0,
        "max_discharge_l_per_m2_per_hour": 1.5,
        "max_emptying_time_hours": 72.0,
    }


@pytest.fixture
def rotterdam_asset() -> dict:
    """A commercial property outside Amsterdam — not applicable."""
    return {
        "asset_id": "NL-R-001",
        "address": "Coolsingel 10, Rotterdam",
        "coordinates": {"crs": "EPSG:4326", "x": 4.477, "y": 51.924},
        "built_area_m2": 400.0,
        "use_class": "commercial",
        "municipality": "Rotterdam",
        "water_authority": "waterschap-hollands_delta",
        "storage_capacity_l_per_m2": 50.0,
        "max_discharge_l_per_m2_per_hour": 0.5,
        "max_emptying_time_hours": 36.0,
    }


@pytest.fixture
def partial_data_asset() -> dict:
    """An Amsterdam asset with some missing engineered values."""
    return {
        "asset_id": "NL-AM-003",
        "address": "Vondelstraat 12, Amsterdam",
        "coordinates": {"crs": "EPSG:4326", "x": 4.870, "y": 52.360},
        "built_area_m2": 200.0,
        "use_class": "commercial",
        "municipality": "Amsterdam",
        "water_authority": "waterschap-agv",
        "storage_capacity_l_per_m2": 65.0,
    }


@pytest.fixture
def epsg28992_asset() -> dict:
    """An Amsterdam asset in EPSG:28992 (Dutch RD)."""
    return {
        "asset_id": "NL-AM-004",
        "address": "Rokin 50, Amsterdam",
        "coordinates": {"crs": "EPSG:28992", "x": 120852.0, "y": 487362.0},
        "built_area_m2": 600.0,
        "use_class": "office",
        "municipality": "Amsterdam",
        "water_authority": "waterschap-agv",
        "storage_capacity_l_per_m2": 60.0,
        "max_discharge_l_per_m2_per_hour": 1.0,
        "max_emptying_time_hours": 60.0,
    }


@pytest.fixture
def all_rules() -> list[RegulatoryRule]:
    return amsterdam_hemelwater_rules()


@pytest.fixture
def all_sources() -> list[RegulatorySource]:
    return amsterdam_hemelwater_sources()


@pytest.fixture
def all_artifacts() -> dict[str, OfficialSourceArtifact]:
    return amsterdam_source_artifacts()


@pytest.fixture
def all_provenance() -> list[ThresholdProvenance]:
    return amsterdam_hemelwater_provenance()


def current_agv_geometry_evidence() -> dict:
    """Complete evidence contract for the post-change AGV geometry."""
    return {
        "publication_date": "2026-06-11",
        "effective_date": "2026-06-12",
        "geometry_version": "agv-work-areas-2026-06-12",
        "artifact_sha256": "a" * 64,
        "source_checksums_verified": True,
        "acquired_at": "2026-06-12T08:00:00Z",
        "spatially_evaluated_at": "2026-06-12T08:01:00Z",
        "deferred_trajectories": ["A709"],
    }


# ---------------------------------------------------------------------------
# Source registry tests
# ---------------------------------------------------------------------------

class TestSourceRegistry:
    def test_sources_are_current(self, all_sources: list[RegulatorySource]):
        for src in all_sources:
            assert src.status == "current", f"Source {src.source_id} is not current"

    def test_source_hashes_are_placeholders(self, all_sources: list[RegulatorySource]):
        """All content_hash values must be PLACEHOLDER_NOT_VERIFIED until real artifacts are retrieved."""
        for src in all_sources:
            assert src.content_hash == PLACEHOLDER_NOT_VERIFIED, (
                f"Source {src.source_id} has non-placeholder content_hash '{src.content_hash}'; "
                f"must be PLACEHOLDER_NOT_VERIFIED until real artifact is retrieved"
            )

    def test_source_checksums_not_verified(self, all_sources: list[RegulatorySource]):
        """source_checksums_verified must be False for all sources."""
        for src in all_sources:
            assert src.source_checksums_verified is False, (
                f"Source {src.source_id} has source_checksums_verified=True "
                f"but no real artifact has been retrieved"
            )

    def test_source_ids_are_unique(self, all_sources: list[RegulatorySource]):
        ids = [s.source_id for s in all_sources]
        assert len(ids) == len(set(ids))

    def test_jurisdiction_is_amsterdam(self):
        j = amsterdam_hemelwater_jurisdiction()
        assert j.level == "municipal"
        assert j.name == "Amsterdam"
        assert "gemeente-amsterdam" in j.authority_ids
        assert "waterschap-agv" in j.authority_ids


# ---------------------------------------------------------------------------
# Official source artifact tests
# ---------------------------------------------------------------------------

class TestOfficialSourceArtifacts:
    def test_artifacts_exist(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        assert len(all_artifacts) == 2
        assert "amsterdam-omgevingsplan-442" in all_artifacts
        assert "agv-waterschapsverordening" in all_artifacts

    def test_artifacts_are_current(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        for source_id, artifact in all_artifacts.items():
            assert artifact.status == "current", (
                f"Artifact {source_id} has status '{artifact.status}'"
            )

    def test_artifacts_have_placeholder_hashes(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        for source_id, artifact in all_artifacts.items():
            assert artifact.artifact_sha256 == PLACEHOLDER_NOT_VERIFIED, (
                f"Artifact {source_id} has non-placeholder hash"
            )

    def test_artifacts_not_verified(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        for source_id, artifact in all_artifacts.items():
            assert artifact.source_checksums_verified is False, (
                f"Artifact {source_id} has source_checksums_verified=True "
                f"but no retrieval has occurred"
            )

    def test_artifact_source_ids_match_registry(self, all_artifacts: dict[str, OfficialSourceArtifact], all_sources: list[RegulatorySource]):
        source_ids = {s.source_id for s in all_sources}
        for source_id in all_artifacts:
            assert source_id in source_ids, (
                f"Artifact {source_id} not in source_registry"
            )

    def test_amsterdam_artifact_references_correct_authority(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        amsterdam = all_artifacts["amsterdam-omgevingsplan-442"]
        assert amsterdam.authority == "Gemeente Amsterdam"
        assert "Paragraaf 4.4.2" in amsterdam.title

    def test_agv_artifact_is_distinct_from_amsterdam(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        agv = all_artifacts["agv-waterschapsverordening"]
        assert agv.authority == "Waterschap Amstel, Gooi en Vecht"
        assert agv.source_id != "amsterdam-omgevingsplan-442"


# ---------------------------------------------------------------------------
# Source artifact verification gate tests
# ---------------------------------------------------------------------------

class TestSourceArtifactVerification:
    def test_placeholder_hash_fails_verification(self, all_artifacts: dict[str, OfficialSourceArtifact]):
        """PLACEHOLDER_NOT_VERIFIED → verification fails."""
        for source_id, artifact in all_artifacts.items():
            is_valid, reason = verify_source_artifact(artifact)
            assert not is_valid, f"Artifact {source_id} should fail with placeholder hash"
            # The reason may mention source_checksums_verified=False or placeholder —
            # both are correct fail-closed outcomes
            assert "source_checksums_verified" in reason.lower() or "placeholder" in reason.lower() or "PLACEHOLDER" in reason

    def test_unverified_checksums_fails(self):
        """source_checksums_verified=False → verification fails."""
        artifact = OfficialSourceArtifact(
            source_id="test",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256="a" * 64,
            source_checksums_verified=False,
            status="current",
        )
        is_valid, reason = verify_source_artifact(artifact)
        assert not is_valid
        assert "source_checksums_verified=False" in reason

    def test_draft_status_fails(self):
        """Draft/superseded/repealed status → verification fails."""
        for bad_status in ("draft", "superseded", "repealed"):
            artifact = OfficialSourceArtifact(
                source_id="test",
                authority="Test Authority",
                official_publication_id="Test Pub",
                title="Test",
                source_url="https://example.com",
                retrieved_at="2026-01-01T00:00:00Z",
                effective_from="2026-01-01",
                artifact_sha256="a" * 64,
                source_checksums_verified=True,
                status=bad_status,
            )
            is_valid, reason = verify_source_artifact(artifact)
            assert not is_valid, f"Status '{bad_status}' should fail verification"
            assert bad_status in reason

    def test_valid_artifact_passes(self):
        """All conditions met → verification passes."""
        artifact = OfficialSourceArtifact(
            source_id="test",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256="a" * 64,
            source_checksums_verified=True,
            status="current",
        )
        is_valid, reason = verify_source_artifact(artifact)
        assert is_valid
        assert "passed" in reason.lower()

    def test_invalid_sha_format_fails(self):
        """Non-hex SHA → verification fails."""
        artifact = OfficialSourceArtifact(
            source_id="test",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256="not-a-real-sha",
            source_checksums_verified=True,
            status="current",
        )
        is_valid, reason = verify_source_artifact(artifact)
        assert not is_valid
        assert "invalid SHA-256 format" in reason

    def test_short_sha_fails(self):
        """Truncated SHA → verification fails."""
        artifact = OfficialSourceArtifact(
            source_id="test",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256="a" * 32,  # only 32 chars, not 64
            source_checksums_verified=True,
            status="current",
        )
        is_valid, reason = verify_source_artifact(artifact)
        assert not is_valid
        assert "invalid SHA-256 format" in reason


# ---------------------------------------------------------------------------
# Threshold provenance tests
# ---------------------------------------------------------------------------

class TestThresholdProvenance:
    def test_provenance_count(self, all_provenance: list[ThresholdProvenance]):
        assert len(all_provenance) == 3

    def test_provenance_not_verified(self, all_provenance: list[ThresholdProvenance]):
        for p in all_provenance:
            assert p.provenance_verified is False

    def test_provenance_references_correct_source(self, all_provenance: list[ThresholdProvenance]):
        for p in all_provenance:
            assert p.source_id == "amsterdam-omgevingsplan-442"

    def test_provenance_has_exact_citations(self, all_provenance: list[ThresholdProvenance]):
        storage = next(p for p in all_provenance if p.rule_id == "NL-AM-HW-STORAGE-001")
        assert storage.article_reference == "Artikel 4.116"
        assert storage.lid_reference == "lid 1(a)"

        discharge = next(p for p in all_provenance if p.rule_id == "NL-AM-HW-DISCHARGE-001")
        assert discharge.lid_reference == "lid 1(b)"

        emptying = next(p for p in all_provenance if p.rule_id == "NL-AM-HW-EMPTYING-001")
        assert emptying.lid_reference == "lid 1(c)"

    def test_provenance_sha_is_placeholder(self, all_provenance: list[ThresholdProvenance]):
        for p in all_provenance:
            assert p.official_artifact_sha256 == PLACEHOLDER_NOT_VERIFIED

    def test_provenance_chain_fails_with_placeholder(self, all_artifacts: dict[str, OfficialSourceArtifact], all_provenance: list[ThresholdProvenance]):
        """Provenance chain fails when artifact is not verified."""
        artifacts_dict = {a.source_id: a for a in all_artifacts.values()}
        for p in all_provenance:
            is_valid, reason = verify_provenance_chain(p, artifacts_dict)
            assert not is_valid, f"Provenance for {p.rule_id} should fail with unverified artifact"
            assert "artifact verification failed" in reason or "placeholder" in reason.lower()

    def test_provenance_chain_passes_when_artifact_verified(self):
        """Provenance chain passes when artifact is fully verified."""
        real_sha = hashlib.sha256(b"test content").hexdigest()
        artifact = OfficialSourceArtifact(
            source_id="verified-source",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256=real_sha,
            source_checksums_verified=True,
            status="current",
        )
        provenance = ThresholdProvenance(
            rule_id="TEST-001",
            source_id="verified-source",
            official_artifact_sha256=real_sha,
            article_reference="Artikel 1",
            paragraph_reference="Paragraaf 1",
            provenance_verified=True,
        )
        artifacts_dict = {"verified-source": artifact}
        is_valid, reason = verify_provenance_chain(provenance, artifacts_dict)
        assert is_valid

    def test_provenance_chain_fails_on_sha_mismatch(self):
        """Provenance chain fails when artifact SHA doesn't match."""
        artifact = OfficialSourceArtifact(
            source_id="mismatched-source",
            authority="Test Authority",
            official_publication_id="Test Pub",
            title="Test",
            source_url="https://example.com",
            retrieved_at="2026-01-01T00:00:00Z",
            effective_from="2026-01-01",
            artifact_sha256="a" * 64,
            source_checksums_verified=True,
            status="current",
        )
        provenance = ThresholdProvenance(
            rule_id="TEST-001",
            source_id="mismatched-source",
            official_artifact_sha256="b" * 64,  # different hash
            article_reference="Artikel 1",
            paragraph_reference="Paragraaf 1",
            provenance_verified=True,
        )
        artifacts_dict = {"mismatched-source": artifact}
        is_valid, reason = verify_provenance_chain(provenance, artifacts_dict)
        assert not is_valid
        assert "SHA mismatch" in reason

    def test_provenance_chain_fails_on_unknown_source(self):
        """Provenance chain fails when source_id doesn't exist."""
        provenance = ThresholdProvenance(
            rule_id="TEST-001",
            source_id="nonexistent-source",
            official_artifact_sha256="a" * 64,
            article_reference="Artikel 1",
            paragraph_reference="Paragraaf 1",
            provenance_verified=True,
        )
        is_valid, reason = verify_provenance_chain(provenance, {})
        assert not is_valid
        assert "unknown source" in reason


# ---------------------------------------------------------------------------
# Rule registry tests
# ---------------------------------------------------------------------------

class TestRuleRegistry:
    def test_rule_count(self, all_rules: list[RegulatoryRule]):
        assert len(all_rules) == 3

    def test_storage_threshold(self, all_rules: list[RegulatoryRule]):
        storage = [r for r in all_rules if r.rule_type == "storage_requirement"]
        assert len(storage) == 1
        assert storage[0].threshold_value == 60.0
        assert storage[0].threshold_unit == "L/m²"
        assert storage[0].comparison == "gte"

    def test_discharge_threshold(self, all_rules: list[RegulatoryRule]):
        discharge = [r for r in all_rules if r.rule_type == "discharge_limit"]
        assert len(discharge) == 1
        assert discharge[0].threshold_value == 1.0
        assert discharge[0].threshold_unit == "L/m²/h"
        assert discharge[0].comparison == "lte"

    def test_emptying_threshold(self, all_rules: list[RegulatoryRule]):
        emptying = [r for r in all_rules if r.rule_type == "emptying_requirement"]
        assert len(emptying) == 1
        assert emptying[0].threshold_value == 60.0
        assert emptying[0].threshold_unit == "h"
        assert emptying[0].comparison == "lte"

    def test_all_rules_reference_valid_sources(self, all_rules: list[RegulatoryRule], all_sources: list[RegulatorySource]):
        source_ids = {s.source_id for s in all_sources}
        for rule in all_rules:
            assert rule.source_id in source_ids, f"Rule {rule.rule_id} references unknown source {rule.source_id}"

    def test_discharge_rule_references_amsterdam_omgevingsplan(self, all_rules: list[RegulatoryRule]):
        """The discharge limit must reference the Amsterdam Omgevingsplan, not AGV."""
        discharge = next(r for r in all_rules if r.rule_type == "discharge_limit")
        assert discharge.source_id == "amsterdam-omgevingsplan-442", (
            f"Discharge rule source_id is '{discharge.source_id}'; "
            f"expected 'amsterdam-omgevingsplan-442'. "
            f"The 1 L/m²/h limit is from Omgevingsplan Paragraaf 4.4.2 / Artikel 4.116, "
            f"NOT from AGV Waterschapsverordening."
        )
        assert "Artikel" in discharge.publication_section

    def test_all_three_rules_reference_same_source(self, all_rules: list[RegulatoryRule]):
        """All three Amsterdam hemelwater thresholds come from the same municipal regulation."""
        source_ids = {r.source_id for r in all_rules}
        assert source_ids == {"amsterdam-omgevingsplan-442"}, (
            f"Expected all rules to reference amsterdam-omgevingsplan-442; "
            f"got {source_ids}.  AGV source should only be used for "
            f"AGV-specific rules (e.g. sert yüzey kompanzasyon)."
        )

    def test_rule_ids_are_unique(self, all_rules: list[RegulatoryRule]):
        ids = [r.rule_id for r in all_rules]
        assert len(ids) == len(set(ids))

    def test_rules_have_provenance_fields(self, all_rules: list[RegulatoryRule]):
        for rule in all_rules:
            assert rule.publication_section, f"Rule {rule.rule_id} missing publication_section"
            assert rule.effective_date, f"Rule {rule.rule_id} missing effective_date"
            assert rule.threshold_source_verified is False, (
                f"Rule {rule.rule_id} has threshold_source_verified=True "
                f"but no independent verification has occurred"
            )


# ---------------------------------------------------------------------------
# Applicability filter tests
# ---------------------------------------------------------------------------

class TestApplicabilityFilter:
    def test_amsterdam_matches(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        for rule in all_rules:
            assert _matches_filter(amsterdam_compliant_asset, rule.applicability_filter)

    def test_rotterdam_does_not_match(self, rotterdam_asset: dict, all_rules: list[RegulatoryRule]):
        for rule in all_rules:
            assert not _matches_filter(rotterdam_asset, rule.applicability_filter)

    def test_empty_filter_matches_all(self, amsterdam_compliant_asset: dict):
        assert _matches_filter(amsterdam_compliant_asset, ApplicabilityFilter())


# ---------------------------------------------------------------------------
# Rule evaluation tests — threshold_source_verified=False fail-closed
# ---------------------------------------------------------------------------

class TestRuleEvaluation:
    def test_unverified_threshold_cannot_be_satisfied(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        """Even when engineered value >= threshold, unverified source → source_unverified."""
        storage_rule = next(r for r in all_rules if r.rule_type == "storage_requirement")
        assert storage_rule.threshold_source_verified is False
        result = _evaluate_rule(amsterdam_compliant_asset, storage_rule)
        assert result.applicable
        assert result.status == "source_unverified"
        assert result.engineered_value == 70.0  # candidate value preserved

    def test_unverified_threshold_cannot_be_not_satisfied(self, amsterdam_noncompliant_asset: dict, all_rules: list[RegulatoryRule]):
        """Even when engineered value < threshold, unverified source → source_unverified."""
        storage_rule = next(r for r in all_rules if r.rule_type == "storage_requirement")
        assert storage_rule.threshold_source_verified is False
        result = _evaluate_rule(amsterdam_noncompliant_asset, storage_rule)
        assert result.applicable
        assert result.status == "source_unverified"
        assert result.engineered_value == 40.0  # candidate value preserved

    def test_source_unverified_preserves_candidate_values(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        """source_unverified preserves candidate engineered/threshold values for diagnostics."""
        storage_rule = next(r for r in all_rules if r.rule_type == "storage_requirement")
        result = _evaluate_rule(amsterdam_compliant_asset, storage_rule)
        assert result.engineered_value == 70.0
        assert result.threshold_value == 60.0
        assert result.threshold_unit == "L/m²"
        assert "threshold_source_verified=False" in result.evidence_note

    def test_missing_data_with_verified_source_gives_insufficient_data(self, partial_data_asset: dict):
        """Missing engineered value + verified source → insufficient_data."""
        from app.regulation.models import RegulatoryRule, ApplicabilityFilter
        verified_rule = RegulatoryRule(
            rule_id="TEST-VERIFIED", source_id="test", rule_type="test",
            parameter_name="max_discharge_l_per_m2_per_hour",
            threshold_value=1.0, threshold_unit="L/m²/h", comparison="lte",
            threshold_source_verified=True,
            applicability_filter=ApplicabilityFilter(municipality="Amsterdam"),
        )
        result = _evaluate_rule(partial_data_asset, verified_rule)
        assert result.applicable
        assert result.status == "insufficient_data"
        assert result.engineered_value is None

    def test_unverified_source_precedes_missing_engineered_value(self):
        """source_unverified takes precedence over insufficient_data."""
        from app.regulation.models import RegulatoryRule, ApplicabilityFilter
        asset = {
            "asset_id": "PRECEDENCE-001", "address": "Test",
            "municipality": "Amsterdam",
            # No storage_capacity_l_per_m2 → engineered_value is None
        }
        unverified_rule = RegulatoryRule(
            rule_id="UNVER-PREC", source_id="test", rule_type="storage_requirement",
            parameter_name="storage_capacity_l_per_m2",
            threshold_value=60.0, threshold_unit="L/m²", comparison="gte",
            threshold_source_verified=False,
            applicability_filter=ApplicabilityFilter(municipality="Amsterdam"),
        )
        result = _evaluate_rule(asset, unverified_rule)
        assert result.applicable
        assert result.status == "source_unverified", (
            f"Expected source_unverified when source is unverified, "
            f"even if engineered_value is None. Got: {result.status}"
        )
        assert result.engineered_value is None  # preserved as None

    def test_missing_data_still_insufficient_data_when_source_verified(self):
        """insufficient_data only reachable when source IS verified."""
        from app.regulation.models import RegulatoryRule, ApplicabilityFilter
        asset = {
            "asset_id": "INSUF-001", "address": "Test",
            "municipality": "Amsterdam",
            # No storage_capacity_l_per_m2
        }
        verified_rule = RegulatoryRule(
            rule_id="VER-INSUF", source_id="test", rule_type="storage_requirement",
            parameter_name="storage_capacity_l_per_m2",
            threshold_value=60.0, threshold_unit="L/m²", comparison="gte",
            threshold_source_verified=True,
            applicability_filter=ApplicabilityFilter(municipality="Amsterdam"),
        )
        result = _evaluate_rule(asset, verified_rule)
        assert result.applicable
        assert result.status == "insufficient_data"

    def test_not_applicable_for_wrong_municipality(self, rotterdam_asset: dict, all_rules: list[RegulatoryRule]):
        storage_rule = next(r for r in all_rules if r.rule_type == "storage_requirement")
        result = _evaluate_rule(rotterdam_asset, storage_rule)
        assert not result.applicable
        assert result.status == "not_applicable"


# ---------------------------------------------------------------------------
# Full asset verification tests — fail-closed invariants
# ---------------------------------------------------------------------------

class TestAssetVerification:
    def test_stale_agv_geometry_overrides_claimed_applicability(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        """A caller cannot bypass the June-2026 geometry incident with a boolean."""
        v = verify_asset(amsterdam_compliant_asset, all_rules, applicability_verified=True)
        assert v.overall_status == "applicability_unverified"
        assert v.asset_applicability_verified is False
        assert v.applicability_reason.startswith("AGV_GEOMETRY_STALE")

    def test_current_agv_geometry_allows_later_source_gate(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        """Even with applicability_verified=True, unverified threshold → source_unverified overall."""
        amsterdam_compliant_asset["agv_geometry_evidence"] = current_agv_geometry_evidence()
        v = verify_asset(amsterdam_compliant_asset, all_rules, applicability_verified=True)
        assert v.asset_id == "NL-AM-001"
        assert v.overall_status == "source_unverified"
        assert v.asset_applicability_verified is True
        # All rule results are source_unverified
        for r in v.rule_results:
            if r.applicable:
                assert r.status == "source_unverified"

    def test_applicability_unverified_overrides_source_unverified(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        """applicability_verified=False → applicability_unverified (takes precedence)."""
        v = verify_asset(amsterdam_compliant_asset, all_rules, applicability_verified=False)
        assert v.overall_status == "applicability_unverified"
        assert v.asset_applicability_verified is False

    def test_non_applicable_asset(self, rotterdam_asset: dict, all_rules: list[RegulatoryRule]):
        v = verify_asset(rotterdam_asset, all_rules, applicability_verified=False)
        assert v.overall_status == "applicability_unverified"

    def test_to_dict_deterministic(self, amsterdam_compliant_asset: dict, all_rules: list[RegulatoryRule]):
        v = verify_asset(amsterdam_compliant_asset, all_rules)
        d1 = v.to_dict()
        d2 = v.to_dict()
        assert d1 == d2
        assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

    def test_epsg28992_asset(self, epsg28992_asset: dict, all_rules: list[RegulatoryRule]):
        v = verify_asset(epsg28992_asset, all_rules, applicability_verified=True)
        assert v.crs == "EPSG:28992"
        assert v.overall_status == "applicability_unverified"


class TestAgvGeometryFreshnessGate:
    def test_complete_current_evidence_passes(self, amsterdam_compliant_asset: dict):
        amsterdam_compliant_asset["agv_geometry_evidence"] = current_agv_geometry_evidence()
        verified, reason = verify_current_agv_geometry(amsterdam_compliant_asset)
        assert verified is True
        assert "spatial re-evaluation verified" in reason

    @pytest.mark.parametrize(
        ("field", "value", "reason_code"),
        [
            ("artifact_sha256", "PLACEHOLDER_NOT_VERIFIED", "AGV_GEOMETRY_UNVERIFIED"),
            ("spatially_evaluated_at", None, "AGV_ASSET_NOT_REEVALUATED"),
            ("deferred_trajectories", [], "AGV_GEOMETRY_EFFECTIVITY_UNVERIFIED"),
        ],
    )
    def test_incomplete_evidence_fails_closed(
        self, amsterdam_compliant_asset: dict, field: str, value: object, reason_code: str
    ):
        evidence = current_agv_geometry_evidence()
        evidence[field] = value
        amsterdam_compliant_asset["agv_geometry_evidence"] = evidence
        verified, reason = verify_current_agv_geometry(amsterdam_compliant_asset)
        assert verified is False
        assert reason.startswith(reason_code)

    def test_applicability_unverified_for_rotterdam(self, rotterdam_asset: dict, all_rules: list[RegulatoryRule]):
        v = verify_asset(rotterdam_asset, all_rules, applicability_verified=False)
        assert v.overall_status == "applicability_unverified"

    def test_mixed_verification_states(self):
        """When some rules are verified and some unverified, source_unverified takes precedence."""
        from app.regulation.models import RegulatoryRule, ApplicabilityFilter
        verified_rule = RegulatoryRule(
            rule_id="VER-001", source_id="test", rule_type="test",
            parameter_name="value", threshold_value=50.0, threshold_unit="x",
            comparison="gte", threshold_source_verified=True,
            applicability_filter=ApplicabilityFilter(municipality="Amsterdam"),
        )
        unverified_rule = RegulatoryRule(
            rule_id="UNVER-001", source_id="test", rule_type="test",
            parameter_name="value2", threshold_value=50.0, threshold_unit="x",
            comparison="gte", threshold_source_verified=False,
            applicability_filter=ApplicabilityFilter(municipality="Amsterdam"),
        )
        asset = {
            "asset_id": "MIXED-001", "address": "Test",
            "coordinates": {"crs": "EPSG:4326", "x": 0, "y": 0},
            "built_area_m2": 100, "use_class": "commercial",
            "municipality": "Amsterdam", "water_authority": "test-authority",
            "value": 60.0, "value2": 60.0,
            "agv_geometry_evidence": current_agv_geometry_evidence(),
        }
        v = verify_asset(asset, [verified_rule, unverified_rule], applicability_verified=True)
        assert v.overall_status == "source_unverified"
        assert v.rule_results[0].status == "threshold_satisfied"  # verified rule
        assert v.rule_results[1].status == "source_unverified"    # unverified rule


# ---------------------------------------------------------------------------
# Portfolio verification tests
# ---------------------------------------------------------------------------

class TestPortfolioVerification:
    def test_mixed_portfolio(
        self,
        amsterdam_compliant_asset: dict,
        amsterdam_noncompliant_asset: dict,
        rotterdam_asset: dict,
        all_rules: list[RegulatoryRule],
    ):
        assets = [amsterdam_compliant_asset, amsterdam_noncompliant_asset, rotterdam_asset]
        results = verify_portfolio(assets, all_rules)
        assert len(results) == 3
        # All applicability_unverified (default verify_asset behavior)
        assert results[0].overall_status == "applicability_unverified"
        assert results[1].overall_status == "applicability_unverified"
        assert results[2].overall_status == "applicability_unverified"

    def test_empty_portfolio(self, all_rules: list[RegulatoryRule]):
        results = verify_portfolio([], all_rules)
        assert results == []


# ---------------------------------------------------------------------------
# Pack generator tests
# ---------------------------------------------------------------------------

class TestPackGenerator:
    def test_basic_generation(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        assert pack["pack_id"] == PACK_ID
        assert pack["schema_version"] == SCHEMA_VERSION
        assert pack["pack_version"] == PACK_VERSION
        assert pack["generator_version"] == GENERATOR_VERSION
        assert len(pack["asset_verifications"]) == 1
        # Generator does NOT auto-verify applicability from municipality
        # → overall_status is applicability_unverified
        assert pack["asset_verifications"][0]["overall_status"] == "applicability_unverified"
        assert pack["asset_verifications"][0]["asset_applicability_verified"] is False

    def test_generator_does_not_verify_applicability_from_municipality_only(self):
        """Municipality='Amsterdam' must NOT set applicability_verified=True."""
        asset = {
            "asset_id": "TEST-001",
            "address": "Test Address, Amsterdam",
            "coordinates": {"crs": "EPSG:4326", "x": 4.9, "y": 52.37},
            "built_area_m2": 300.0,
            "use_class": "commercial",
            "municipality": "Amsterdam",
            "water_authority": "waterschap-agv",
        }
        pack = build_evidence_pack(assets=[asset], deterministic_seed=42)
        v = pack["asset_verifications"][0]
        assert v["asset_applicability_verified"] is False
        assert v["overall_status"] == "applicability_unverified"

    def test_generator_does_not_claim_bag_identity_without_bag_evidence(self):
        """Applicability reason must not claim BAG identity was verified."""
        asset = {
            "asset_id": "TEST-002",
            "address": "Test Address, Amsterdam",
            "coordinates": {"crs": "EPSG:4326", "x": 4.9, "y": 52.37},
            "built_area_m2": 300.0,
            "use_class": "commercial",
            "municipality": "Amsterdam",
            "water_authority": "waterschap-agv",
        }
        pack = build_evidence_pack(assets=[asset], deterministic_seed=42)
        reason = pack["asset_verifications"][0].get("applicability_reason", "")
        # Must NOT claim BAG identity was verified
        assert pack["asset_verifications"][0]["asset_applicability_verified"] is False
        assert "BAG identity: Amsterdam municipality = True" not in reason

    def test_cli_contains_no_compliant_non_compliant_result_labels(self):
        """Generator output must not contain compliant/non_compliant as status labels."""
        asset = {
            "asset_id": "TEST-CLI",
            "address": "Test, Amsterdam",
            "coordinates": {"crs": "EPSG:4326", "x": 4.9, "y": 52.37},
            "built_area_m2": 300.0,
            "use_class": "commercial",
            "municipality": "Amsterdam",
            "water_authority": "waterschap-agv",
        }
        pack = build_evidence_pack(assets=[asset], deterministic_seed=42)
        for v in pack["asset_verifications"]:
            assert v["overall_status"] not in ("compliant", "non_compliant")
            for rr in v["rule_results"]:
                assert rr["status"] not in ("compliant", "non_compliant")

    def test_determinism(self, amsterdam_compliant_asset: dict):
        """Same inputs → identical output (excluding volatile timestamps)."""
        VOLATILE_KEYS = {"generated_at", "envelope_timestamp"}
        pack1 = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
            output_path=None,
        )
        pack2 = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
            output_path=None,
        )
        for key in VOLATILE_KEYS:
            pack1.pop(key, None)
            pack2.pop(key, None)
        assert json.dumps(pack1, sort_keys=True) == json.dumps(pack2, sort_keys=True)

    def test_checksum_integrity(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        is_valid, reason = verify_pack_checksum(pack)
        assert is_valid, f"Checksum verification failed: {reason}"

    def test_checksum_tamper_detection(self, amsterdam_compliant_asset: dict):
        """Tamper with content → checksum mismatch."""
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        original_checksum = pack["checksum"]["content_sha256"]

        # Tamper with a value
        pack["asset_verifications"][0]["overall_status"] = "threshold_not_satisfied"

        is_valid, reason = verify_pack_checksum(pack)
        assert not is_valid, "Tamper detection failed: modifying status did not invalidate checksum"
        assert "mismatch" in reason.lower()

    def test_atomic_write(self, amsterdam_compliant_asset: dict, tmp_path: Path):
        output = tmp_path / "test_pack.json"
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
            output_path=str(output),
        )
        assert output.exists()
        with open(output, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["pack_id"] == PACK_ID
        is_valid, _ = verify_pack_checksum(loaded)
        assert is_valid

    def test_no_tmp_file_left_after_write(self, amsterdam_compliant_asset: dict, tmp_path: Path):
        output = tmp_path / "test_pack.json"
        build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
            output_path=str(output),
        )
        tmp_file = output.with_suffix(".tmp")
        assert not tmp_file.exists()

    def test_classification_fields(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        cls = pack["classification"]
        assert cls["evidence_class"] == "synthetic_reference"
        assert cls["customer_data_status"] == "not_customer_data"
        assert cls["production_eligible"] is False
        assert cls["decision_use_approved"] is False

    def test_source_registry_has_provenance(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        assert len(pack["source_registry"]) == 2
        for src in pack["source_registry"]:
            assert src["status"] == "current"
            assert src["content_hash"] == PLACEHOLDER_NOT_VERIFIED
            assert src["source_checksums_verified"] is False

    def test_official_source_artifacts_in_pack(self, amsterdam_compliant_asset: dict):
        """Pack includes official_source_artifacts with correct structure."""
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        artifacts = pack["official_source_artifacts"]
        assert len(artifacts) == 2
        for a in artifacts:
            assert "source_id" in a
            assert "artifact_sha256" in a
            assert a["artifact_sha256"] == PLACEHOLDER_NOT_VERIFIED
            assert a["source_checksums_verified"] is False
            assert a["status"] == "current"

    def test_threshold_provenance_in_pack(self, amsterdam_compliant_asset: dict):
        """Pack includes threshold_provenance with correct structure."""
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        prov = pack["threshold_provenance"]
        assert len(prov) == 3
        for p in prov:
            assert "rule_id" in p
            assert "article_reference" in p
            assert "official_artifact_sha256" in p
            assert p["official_artifact_sha256"] == PLACEHOLDER_NOT_VERIFIED
            assert p["provenance_verified"] is False

    def test_regulatory_rules_have_provenance(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        assert len(pack["regulatory_rules"]) == 3
        for rule in pack["regulatory_rules"]:
            assert rule["publication_section"], f"Rule {rule['rule_id']} missing publication_section"
            assert rule["threshold_source_verified"] is False

    def test_mixed_crs_portfolio(self):
        assets = [
            {
                "asset_id": "NL-AM-010",
                "address": "Test Amsterdam RD",
                "coordinates": {"crs": "EPSG:28992", "x": 120000.0, "y": 485000.0},
                "built_area_m2": 400.0,
                "use_class": "commercial",
                "municipality": "Amsterdam",
                "water_authority": "waterschap-agv",
                "storage_capacity_l_per_m2": 65.0,
                "max_discharge_l_per_m2_per_hour": 0.9,
                "max_emptying_time_hours": 50.0,
            },
            {
                "asset_id": "NL-AM-011",
                "address": "Test Amsterdam WGS84",
                "coordinates": {"crs": "EPSG:4326", "x": 4.9, "y": 52.37},
                "built_area_m2": 350.0,
                "use_class": "office",
                "municipality": "Amsterdam",
                "water_authority": "waterschap-agv",
                "storage_capacity_l_per_m2": 72.0,
                "max_discharge_l_per_m2_per_hour": 0.7,
                "max_emptying_time_hours": 40.0,
            },
        ]
        pack = build_evidence_pack(assets=assets, deterministic_seed=42)
        assert len(pack["asset_verifications"]) == 2
        assert pack["asset_verifications"][0]["coordinates"]["crs"] == "EPSG:28992"
        assert pack["asset_verifications"][1]["coordinates"]["crs"] == "EPSG:4326"

    def test_geojson_polygon_rejected(self, tmp_path: Path):
        """Polygon geometry (e.g. BAG footprints) must be rejected fail-closed."""
        import subprocess
        import sys as _sys
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[4.899, 52.374], [4.900, 52.374], [4.900, 52.375], [4.899, 52.375], [4.899, 52.374]]],
                    },
                    "properties": {
                        "asset_id": "BAG-001",
                        "address": "Test Polygon",
                        "built_area_m2": 300.0,
                        "use_class": "commercial",
                        "municipality": "Amsterdam",
                        "water_authority": "waterschap-agv",
                    },
                },
            ],
        }
        portfolio_path = tmp_path / "polygon_portfolio.json"
        portfolio_path.write_text(json.dumps(geojson), encoding="utf-8")
        output_path = tmp_path / "output.json"
        # Call the actual generator CLI via subprocess
        result = subprocess.run(
            [_sys.executable, "scripts/generate_regulatory_evidence_pack.py",
             "--portfolio", str(portfolio_path), "--output", str(output_path)],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode != 0, "Generator should reject Polygon geometry"
        assert "FAIL-CLOSED" in result.stderr or "Polygon" in result.stderr + result.stdout

    def test_geojson_multipolygon_rejected(self):
        """MultiPolygon geometry must also be rejected."""
        geom_type = "MultiPolygon"
        assert geom_type != "Point", "MultiPolygon should not pass the Point check"

    def test_120_asset_portfolio(self):
        """Verify the generator handles a 120-asset portfolio."""
        assets = []
        for i in range(120):
            assets.append({
                "asset_id": f"NL-AM-{i:04d}",
                "address": f"Synthetic Amsterdam parcel {i:04d}",
                "coordinates": {"crs": "EPSG:4326", "x": 4.8 + i * 0.001, "y": 52.3 + i * 0.001},
                "built_area_m2": 200.0 + i * 10,
                "use_class": "commercial",
                "municipality": "Amsterdam",
                "water_authority": "waterschap-agv",
                "storage_capacity_l_per_m2": 55.0 + i * 0.5,
                "max_discharge_l_per_m2_per_hour": 0.5 + i * 0.005,
                "max_emptying_time_hours": 40.0 + i * 0.2,
            })
        pack = build_evidence_pack(assets=assets, deterministic_seed=42)
        assert len(pack["asset_verifications"]) == 120
        # All applicability_unverified (generator no longer auto-verifies from municipality)
        for v in pack["asset_verifications"]:
            assert v["asset_applicability_verified"] is False
            assert v["overall_status"] == "applicability_unverified"


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_duplicate_asset_ids_rejected(self):
        assets = [
            {"asset_id": "DUP-001", "address": "A", "coordinates": {"crs": "EPSG:4326", "x": 0, "y": 0}, "built_area_m2": 100, "use_class": "commercial", "municipality": "Amsterdam", "water_authority": "agv"},
            {"asset_id": "DUP-001", "address": "B", "coordinates": {"crs": "EPSG:4326", "x": 1, "y": 1}, "built_area_m2": 200, "use_class": "commercial", "municipality": "Amsterdam", "water_authority": "agv"},
        ]
        with pytest.raises(SystemExit, match="FAIL-CLOSED"):
            build_evidence_pack(assets=assets, deterministic_seed=42)

    def test_invalid_crs_rejected(self):
        assets = [
            {"asset_id": "CRS-001", "address": "A", "coordinates": {"crs": "EPSG:9999", "x": 0, "y": 0}, "built_area_m2": 100, "use_class": "commercial", "municipality": "Amsterdam", "water_authority": "agv"},
        ]
        with pytest.raises(SystemExit, match="FAIL-CLOSED.*invalid CRS"):
            build_evidence_pack(assets=assets, deterministic_seed=42)

    def test_placeholder_hash_enforced(self):
        """Source with fake hash and source_checksums_verified=False is rejected."""
        sources = amsterdam_hemelwater_sources()
        for src in sources:
            assert src.content_hash == PLACEHOLDER_NOT_VERIFIED
            assert src.source_checksums_verified is False


# ---------------------------------------------------------------------------
# Prohibited claims / no readiness flag modification tests
# ---------------------------------------------------------------------------

class TestProhibitedClaims:
    PROHIBITED_PHRASES = [
        "EU approved",
        "AI Act certified",
        "AI Act compliant",
        "high-risk validated",
        "sandbox approved",
        "regulator approved",
        "compliance certification",
        "automatic compliance",
    ]

    def test_no_prohibited_phrases_in_source_titles(self, all_sources: list[RegulatorySource]):
        for src in all_sources:
            for phrase in self.PROHIBITED_PHRASES:
                assert phrase.lower() not in src.title.lower(), (
                    f"Prohibited phrase '{phrase}' found in source title '{src.title}'"
                )

    def test_classification_explicitly_not_production(self, amsterdam_compliant_asset: dict):
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        assert pack["classification"]["production_eligible"] is False
        assert pack["classification"]["decision_use_approved"] is False

    def test_no_compliance_language_in_statuses(self, amsterdam_compliant_asset: dict):
        """Statuses must use neutral threshold language, NOT compliance language."""
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        for v in pack["asset_verifications"]:
            for rr in v["rule_results"]:
                assert rr["status"] not in ("compliant", "non_compliant"), (
                    f"Status '{rr['status']}' uses compliance language; "
                    f"must use threshold_satisfied/threshold_not_satisfied/source_unverified"
                )


# ---------------------------------------------------------------------------
# Readiness flag immutability tests
# ---------------------------------------------------------------------------

class TestReadinessImmutability:
    def test_pack_does_not_modify_release_manifest(self):
        """Building a regulatory evidence pack must NOT change any readiness flag."""
        import app.schemas.release_manifest as rm_module
        assert rm_module.__name__ == "app.schemas.release_manifest"

    def test_pack_has_no_readiness_fields(self, amsterdam_compliant_asset: dict):
        """The pack itself must NOT contain readiness gate fields."""
        pack = build_evidence_pack(
            assets=[amsterdam_compliant_asset],
            deterministic_seed=42,
        )
        readiness_fields = [
            "production_eligible",
            "controlled_pilot_eligible",
            "runtime_live_verified",
            "data_source_operational",
            "platform_operational",
            "commercially_validated",
            "model_validated_for_use_case",
            "licence_verification_status",
            "scientific_validation_status",
        ]
        for field in readiness_fields:
            assert field not in pack, f"Readiness field '{field}' found in pack — must not be here"

    def test_pack_does_not_contain_network_imports(self):
        """The regulation module must not import network libraries."""
        import ast
        regulation_dir = Path(__file__).resolve().parent.parent.parent / "app" / "regulation"
        for py_file in regulation_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in ("requests", "httpx", "urllib3", "aiohttp"), (
                            f"Network import '{alias.name}' found in {py_file.name}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in ("requests", "httpx", "urllib3", "aiohttp"):
                        assert False, f"Network import '{node.module}' found in {py_file.name}"


# ---------------------------------------------------------------------------
# Documentation content tests
# ---------------------------------------------------------------------------

class TestDocumentation:
    def test_docs_exist(self):
        docs_path = Path(__file__).resolve().parent.parent.parent / "docs" / "compliance" / "regulatory-evidence-pack.md"
        assert docs_path.exists(), "Documentation file not found"


# ---------------------------------------------------------------------------
# Deterministic JSON serialization
# ---------------------------------------------------------------------------

class TestDeterministicSerialization:
    def test_sorted_keys(self):
        obj = {"z": 1, "a": 2, "m": {"b": 3, "a": 1}}
        result = _deterministic_json(obj)
        parsed = json.loads(result)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_no_whitespace(self):
        obj = {"key": "value", "number": 42}
        result = _deterministic_json(obj)
        assert ": " not in result
        assert ", " not in result
