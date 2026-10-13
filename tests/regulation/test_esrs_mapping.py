"""Tests for the ESRS Evidence Mapping layer.

Covers:
- Versioned instrument definitions (2023 in-force, 2026 adopted-not-in-force)
- Corrected semantic concept mappings per official ESRS standard
- Disclosure requirement mapping
- Fail-closed: unknown instrument rejection
- Fail-closed: not_in_force enforcement (mapping_mode gate)
- Neutral terminology (no compliance/alignment language)
- Financial value provenance (carrying_value + reconciled + reporting_date)
- Adaptation action evidence separation from threshold results
- Evidence status propagation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.regulation.esrs_mapping import (
    ESRSDisclosureMapping,
    ESRSEvidenceStatus,
    ESRSInstrument,
    ESRSMappingResult,
    ESRSMappingStatus,
    DisclosureRequirement,
    FinancialValue,
)
from app.regulation.esrs_registry import (
    esrs_2023_in_force,
    esrs_2026_adopted,
    esrs_e1_disclosure_requirements_2023,
    esrs_e1_disclosure_requirements_2026,
    get_esrs_instrument,
    map_georisk_to_esrs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_force_instrument() -> ESRSInstrument:
    return esrs_2023_in_force()


@pytest.fixture
def adopted_instrument() -> ESRSInstrument:
    return esrs_2026_adopted()


@pytest.fixture
def drs_2023() -> list[DisclosureRequirement]:
    return esrs_e1_disclosure_requirements_2023()


@pytest.fixture
def drs_2026() -> list[DisclosureRequirement]:
    return esrs_e1_disclosure_requirements_2026()


@pytest.fixture
def sample_asset_verifications() -> list[dict]:
    return [
        {
            "asset_id": "NL-AM-001",
            "overall_status": "applicability_unverified",
            "rule_results": [
                {"rule_id": "NL-AM-HW-STORAGE-001", "status": "source_unverified"},
                {"rule_id": "NL-AM-HW-DISCHARGE-001", "status": "source_unverified"},
            ],
        },
    ]


@pytest.fixture
def verified_asset_verifications() -> list[dict]:
    return [
        {
            "asset_id": "NL-AM-001",
            "overall_status": "source_unverified",
            "rule_results": [
                {"rule_id": "NL-AM-HW-STORAGE-001", "status": "threshold_satisfied"},
                {"rule_id": "NL-AM-HW-DISCHARGE-001", "status": "source_unverified"},
            ],
        },
    ]


@pytest.fixture
def full_carrying_value() -> FinancialValue:
    return FinancialValue(
        amount=25_000_000,
        value_basis="carrying_value",
        reporting_date="2026-12-31",
        financial_statement_reconciled=True,
    )


# ---------------------------------------------------------------------------
# Instrument version tests
# ---------------------------------------------------------------------------

class TestESRSInstrumentVersions:
    def test_2023_is_in_force(self, in_force_instrument: ESRSInstrument):
        assert in_force_instrument.instrument_id == "ESRS-2023-2772"
        assert in_force_instrument.legal_state == "current_in_force"

    def test_2026_is_adopted_not_in_force(self, adopted_instrument: ESRSInstrument):
        assert adopted_instrument.instrument_id == "ESRS-2026-REVISION"
        assert adopted_instrument.legal_state == "adopted_not_in_force"


# ---------------------------------------------------------------------------
# 2023 semantic mapping correctness (CORRECTED)
# ---------------------------------------------------------------------------

class TestESRS2023SemanticMapping:
    def test_e1_1_is_transition_plan(self, drs_2023: list[DisclosureRequirement]):
        """E1-1 = transition_plan_climate_mitigation, NOT climate_risk_identification."""
        e1_1 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-1")
        assert e1_1.semantic_concept == "transition_plan_climate_mitigation"

    def test_esrs2_iro1_is_risk_identification(self, drs_2023: list[DisclosureRequirement]):
        """Climate risk identification comes from ESRS 2 IRO-1, not E1-1."""
        iro1 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "ESRS2-IRO1/E1")
        assert iro1.semantic_concept == "climate_risk_identification"

    def test_e1_2_is_policies(self, drs_2023: list[DisclosureRequirement]):
        e1_2 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-2")
        assert e1_2.semantic_concept == "climate_policies"

    def test_e1_3_is_actions(self, drs_2023: list[DisclosureRequirement]):
        e1_3 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-3")
        assert e1_3.semantic_concept == "climate_actions_and_resources"

    def test_e1_6_is_ghg_emissions(self, drs_2023: list[DisclosureRequirement]):
        e1_6 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-6")
        assert e1_6.semantic_concept == "ghg_emissions"

    def test_e1_7_is_ghg_removals(self, drs_2023: list[DisclosureRequirement]):
        """E1-7 = ghg_removals_and_carbon_credits, NOT mitigation initiatives."""
        e1_7 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-7")
        assert e1_7.semantic_concept == "ghg_removals_and_carbon_credits"

    def test_e1_8_is_internal_carbon_pricing(self, drs_2023: list[DisclosureRequirement]):
        e1_8 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-8")
        assert e1_8.semantic_concept == "internal_carbon_pricing"

    def test_e1_9_is_financial_effects(self, drs_2023: list[DisclosureRequirement]):
        e1_9 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-9")
        assert e1_9.semantic_concept == "anticipated_financial_effects"

    def test_no_e1_1_as_risk_identification(self, drs_2023: list[DisclosureRequirement]):
        """E1-1 must NOT be mapped to climate_risk_identification."""
        e1_1 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-1")
        assert e1_1.semantic_concept != "climate_risk_identification"

    def test_no_e1_7_as_mitigation_initiatives(self, drs_2023: list[DisclosureRequirement]):
        """E1-7 must NOT be mapped to ghg_mitigation_initiatives."""
        e1_7 = next(dr for dr in drs_2023 if dr.disclosure_requirement == "E1-7")
        assert e1_7.semantic_concept != "ghg_mitigation_initiatives"

    def test_2023_has_10_requirements(self, drs_2023: list[DisclosureRequirement]):
        assert len(drs_2023) == 10  # E1-1 through E1-9 plus ESRS2-IRO1/E1


# ---------------------------------------------------------------------------
# 2026 semantic mapping correctness
# ---------------------------------------------------------------------------

class TestESRS2026SemanticMapping:
    def test_e1_1_is_transition_plan(self, drs_2026: list[DisclosureRequirement]):
        e1_1 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-1")
        assert e1_1.semantic_concept == "transition_plan_climate_mitigation"

    def test_e1_2_is_risk_identification(self, drs_2026: list[DisclosureRequirement]):
        e1_2 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-2")
        assert e1_2.semantic_concept == "climate_risk_identification"

    def test_e1_3_is_climate_resilience(self, drs_2026: list[DisclosureRequirement]):
        """E1-3 in 2026 is climate_resilience (new concept)."""
        e1_3 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-3")
        assert e1_3.semantic_concept == "climate_resilience"

    def test_e1_4_is_policies(self, drs_2026: list[DisclosureRequirement]):
        e1_4 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-4")
        assert e1_4.semantic_concept == "climate_policies"

    def test_e1_5_is_actions(self, drs_2026: list[DisclosureRequirement]):
        e1_5 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-5")
        assert e1_5.semantic_concept == "climate_actions_and_resources"

    def test_e1_8_is_ghg_emissions(self, drs_2026: list[DisclosureRequirement]):
        e1_8 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-8")
        assert e1_8.semantic_concept == "ghg_emissions"

    def test_e1_11_is_financial_effects(self, drs_2026: list[DisclosureRequirement]):
        e1_11 = next(dr for dr in drs_2026 if dr.disclosure_requirement == "E1-11")
        assert e1_11.semantic_concept == "anticipated_financial_effects"

    def test_2026_has_7_requirements(self, drs_2026: list[DisclosureRequirement]):
        assert len(drs_2026) == 7


# ---------------------------------------------------------------------------
# Semantic concept cross-version stability
# ---------------------------------------------------------------------------

class TestSemanticConceptStability:
    def test_concepts_that_change_numbering(self, drs_2023: list[DisclosureRequirement], drs_2026: list[DisclosureRequirement]):
        """Some concepts change numbering between versions; others don't."""
        concepts_2023 = {dr.semantic_concept: dr.disclosure_requirement for dr in drs_2023}
        concepts_2026 = {dr.semantic_concept: dr.disclosure_requirement for dr in drs_2026}
        shared = set(concepts_2023) & set(concepts_2026)

        # These concepts CHANGED numbering
        changed = {
            "climate_policies",          # E1-2 → E1-4
            "climate_actions_and_resources",  # E1-3 → E1-5
            "ghg_emissions",             # E1-6 → E1-8
            "anticipated_financial_effects",  # E1-9 → E1-11
        }
        for concept in changed:
            assert concept in shared, f"Expected '{concept}' in shared concepts"
            assert concepts_2023[concept] != concepts_2026[concept], (
                f"'{concept}' should have different DR numbers: "
                f"{concepts_2023[concept]} vs {concepts_2026[concept]}"
            )

        # transition_plan_climate_mitigation keeps E1-1 in both versions
        assert concepts_2023["transition_plan_climate_mitigation"] == "E1-1"
        assert concepts_2026["transition_plan_climate_mitigation"] == "E1-1"

    def test_adaptation_actions_numbering(self, drs_2023, drs_2026):
        concept = "climate_actions_and_resources"
        assert next(dr for dr in drs_2023 if dr.semantic_concept == concept).disclosure_requirement == "E1-3"
        assert next(dr for dr in drs_2026 if dr.semantic_concept == concept).disclosure_requirement == "E1-5"

    def test_financial_effects_numbering(self, drs_2023, drs_2026):
        concept = "anticipated_financial_effects"
        assert next(dr for dr in drs_2023 if dr.semantic_concept == concept).disclosure_requirement == "E1-9"
        assert next(dr for dr in drs_2026 if dr.semantic_concept == concept).disclosure_requirement == "E1-11"

    def test_ghg_emissions_numbering(self, drs_2023, drs_2026):
        concept = "ghg_emissions"
        assert next(dr for dr in drs_2023 if dr.semantic_concept == concept).disclosure_requirement == "E1-6"
        assert next(dr for dr in drs_2026 if dr.semantic_concept == concept).disclosure_requirement == "E1-8"

    def test_policies_numbering(self, drs_2023, drs_2026):
        concept = "climate_policies"
        assert next(dr for dr in drs_2023 if dr.semantic_concept == concept).disclosure_requirement == "E1-2"
        assert next(dr for dr in drs_2026 if dr.semantic_concept == concept).disclosure_requirement == "E1-4"


# ---------------------------------------------------------------------------
# Unknown instrument rejection (FAIL-CLOSED)
# ---------------------------------------------------------------------------

class TestUnknownInstrumentRejection:
    def test_unknown_instrument_raises_valueerror(self):
        unknown = ESRSInstrument(
            instrument_id="ESRS-FAKE-2099",
            title="Fake",
            official_identifier="fake",
            legal_state="current_in_force",
        )
        with pytest.raises(ValueError, match="Unknown ESRS instrument_id"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=0,
                instrument=unknown,
            )

    def test_known_instruments_accepted(self):
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=0,
            instrument=esrs_2023_in_force(),
        )
        assert result.instrument_id == "ESRS-2023-2772"


# ---------------------------------------------------------------------------
# Not-in-force enforcement (FAIL-CLOSED)
# ---------------------------------------------------------------------------

class TestNotInForceEnforcement:
    def test_2026_rejected_for_current_reporting(self):
        """2026 instrument + current_reporting → ValueError."""
        with pytest.raises(ValueError, match="cannot be used for current reporting"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=0,
                instrument=esrs_2026_adopted(),
                mapping_mode="current_reporting",
            )

    def test_2026_accepted_with_prospective_analysis(self):
        """2026 instrument + prospective_analysis → allowed, with prospective_only=True."""
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=0,
            instrument=esrs_2026_adopted(),
            mapping_mode="prospective_analysis",
        )
        assert result.instrument_id == "ESRS-2026-REVISION"
        assert result.prospective_only is True
        assert "prospective_analysis" in result.notes

    def test_2023_prospective_analysis_still_not_prospective(self):
        """2023 in-force instrument is always non-prospective."""
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=0,
            instrument=esrs_2023_in_force(),
            mapping_mode="prospective_analysis",
        )
        assert result.prospective_only is False

    def test_default_mapping_mode_is_current_reporting(self):
        """Default mapping_mode rejects non-current instruments."""
        with pytest.raises(ValueError, match="cannot be used for current reporting"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=0,
                instrument=esrs_2026_adopted(),
            )


# ---------------------------------------------------------------------------
# Financial provenance enforcement
# ---------------------------------------------------------------------------

class TestFinancialProvenance:
    def test_no_financial_value_gives_insufficient(self, sample_asset_verifications):
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications,
            total_assets=1,
            financial_value=None,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
        assert fin_dr.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_user_supplied_not_reconciled_with_evidence_gives_caveats(self):
        """user_supplied + evidence_ids → PARTIALLY_MAPPED (provenance caveat)."""
        fv = FinancialValue(amount=1000, value_basis="user_supplied", financial_statement_reconciled=False)
        asset = {
            "asset_id": "FP-001",
            "overall_status": "threshold_satisfied",
            "rule_results": [{"rule_id": "R-001", "status": "threshold_satisfied"}],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.mapping_status == ESRSMappingStatus.PARTIALLY_MAPPED
        assert any("incomplete financial provenance" in c.lower() for c in fin_dr.caveats)

    def test_carrying_value_without_reporting_date_with_evidence_gives_caveats(self):
        """carrying_value + reconciled + evidence but NO reporting_date → partial."""
        fv = FinancialValue(
            amount=1000, value_basis="carrying_value",
            financial_statement_reconciled=True, reporting_date="",
        )
        asset = {
            "asset_id": "FP-002",
            "overall_status": "threshold_satisfied",
            "rule_results": [{"rule_id": "R-001", "status": "threshold_satisfied"}],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.mapping_status == ESRSMappingStatus.PARTIALLY_MAPPED
        assert any("reporting_date missing" in c for c in fin_dr.caveats)

    def test_market_value_with_evidence_gives_caveats(self):
        """market_value + evidence_ids → partial (need carrying_value)."""
        fv = FinancialValue(amount=1000, value_basis="market_value", financial_statement_reconciled=True, reporting_date="2026-12-31")
        asset = {
            "asset_id": "FP-003",
            "overall_status": "threshold_satisfied",
            "rule_results": [{"rule_id": "R-001", "status": "threshold_satisfied"}],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.mapping_status == ESRSMappingStatus.PARTIALLY_MAPPED
        assert any("carrying_value" in c for c in fin_dr.caveats)

    def test_user_supplied_no_risk_evidence_gives_insufficient(self):
        """user_supplied financial + no evidence_ids → INSUFFICIENT."""
        fv = FinancialValue(amount=1000, value_basis="user_supplied")
        asset = {
            "asset_id": "FIN-U",
            "overall_status": "source_unverified",
            "rule_results": [],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
        assert fin_dr.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_market_value_no_risk_evidence_gives_insufficient(self):
        """market_value financial + no evidence_ids → INSUFFICIENT."""
        fv = FinancialValue(amount=1000, value_basis="market_value")
        asset = {
            "asset_id": "FIN-M",
            "overall_status": "source_unverified",
            "rule_results": [],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
        assert fin_dr.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_carrying_value_without_risk_evidence_gives_insufficient(self, full_carrying_value):
        """carrying_value + no evidence_ids → INSUFFICIENT (risk linkage before provenance)."""
        asset = {
            "asset_id": "FIN-001",
            "overall_status": "source_unverified",
            "rule_results": [],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1,
            financial_value=full_carrying_value,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.evidence_status == ESRSEvidenceStatus.INSUFFICIENT_EVIDENCE
        assert fin_dr.mapping_status == ESRSMappingStatus.UNMAPPED
        assert any("No verified physical-risk evidence" in c for c in fin_dr.caveats)

    def test_user_supplied_with_risk_evidence_gives_partial(self):
        """user_supplied + verified evidence_ids → PARTIALLY_MAPPED (provenance caveat)."""
        fv = FinancialValue(amount=1000, value_basis="user_supplied")
        asset = {
            "asset_id": "FIN-P",
            "overall_status": "threshold_satisfied",
            "rule_results": [
                {"rule_id": "R-001", "status": "threshold_satisfied"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1, financial_value=fv,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        # user_supplied + reconciled=False → risk linkage passes (evidence_ids exist)
        # but provenance incomplete → PARTIALLY_MAPPED
        assert fin_dr.mapping_status == ESRSMappingStatus.PARTIALLY_MAPPED
        assert fin_dr.evidence_status == ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS
        assert any("incomplete financial provenance" in c.lower() for c in fin_dr.caveats)

    def test_carrying_value_with_risk_evidence_gives_partial(self, full_carrying_value):
        """carrying_value + verified evidence_ids → PARTIALLY_MAPPED."""
        asset = {
            "asset_id": "FIN-002",
            "overall_status": "threshold_satisfied",
            "rule_results": [
                {"rule_id": "R-001", "status": "threshold_satisfied"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset], total_assets=1,
            financial_value=full_carrying_value,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.mapping_status == ESRSMappingStatus.PARTIALLY_MAPPED
        assert fin_dr.evidence_status == ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS
        assert len(fin_dr.supporting_evidence_ids) > 0

    def test_e1_9_never_gets_mapped(self, full_carrying_value):
        """E1-9 should never reach MAPPED status."""
        asset = {
            "asset_id": "FIN-003",
            "overall_status": "threshold_satisfied",
            "rule_results": [
                {"rule_id": "R-001", "status": "threshold_satisfied"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset],
            total_assets=1,
            financial_value=full_carrying_value,
        )
        fin_dr = next(dm for dm in result.disclosure_mappings
                       if dm.semantic_concept == "anticipated_financial_effects")
        assert fin_dr.mapping_status != ESRSMappingStatus.MAPPED


# ---------------------------------------------------------------------------
# Adaptation action evidence separation
# ---------------------------------------------------------------------------

class TestAdaptationActionEvidenceSeparation:
    def test_threshold_results_not_used_as_adaptation_evidence(
        self, verified_asset_verifications
    ):
        """Threshold results are regulatory screening, NOT adaptation action evidence."""
        result = map_georisk_to_esrs(
            asset_verifications=verified_asset_verifications,
            source_unverified_count=0,
            total_assets=1,
        )
        # Find the climate_actions_and_resources DR
        actions_dr = next(
            dm for dm in result.disclosure_mappings
            if dm.semantic_concept == "climate_actions_and_resources"
        )
        # Must NOT be mapped — threshold results don't prove adaptation actions
        assert actions_dr.mapping_status == ESRSMappingStatus.UNMAPPED
        assert actions_dr.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        # Must have caveat explaining the distinction
        assert any("NOT adaptation action evidence" in c for c in actions_dr.caveats)

    def test_threshold_satisfied_does_not_produce_action_evidence(self):
        """Even with all thresholds satisfied, no adaptation action evidence."""
        asset = {
            "asset_id": "SAT-001",
            "overall_status": "threshold_satisfied",
            "rule_results": [
                {"rule_id": "R-001", "status": "threshold_satisfied"},
                {"rule_id": "R-002", "status": "threshold_satisfied"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset],
            total_assets=1,
        )
        actions_dr = next(
            dm for dm in result.disclosure_mappings
            if dm.semantic_concept == "climate_actions_and_resources"
        )
        assert actions_dr.mapping_status == ESRSMappingStatus.UNMAPPED


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_empty_portfolio_gives_not_assessed(self):
        result = map_georisk_to_esrs(asset_verifications=[], total_assets=0)
        assert result.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert result.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_no_assets_no_evidence_gives_not_assessed(self):
        """No verifications + total_assets=1 → NOT_ASSESSED."""
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=1,
        )
        assert result.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert result.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_source_unverified_is_not_evidence(self, sample_asset_verifications):
        """source_unverified_count > 0 must NOT produce evidence support."""
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications,
            source_unverified_count=1,
            total_assets=1,
        )
        # source_unverified rules have no evidence_ids → overall NOT_ASSESSED
        assert result.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert result.mapping_status == ESRSMappingStatus.UNMAPPED


# ---------------------------------------------------------------------------
# Neutral terminology
# ---------------------------------------------------------------------------

class TestNeutralTerminology:
    def test_no_compliance_in_status_enums(self):
        for member in ESRSEvidenceStatus:
            assert "compliant" not in member.value.lower()
            assert "aligned" not in member.value.lower()
            assert "eligible" not in member.value.lower()
        for member in ESRSMappingStatus:
            assert "compliant" not in member.value.lower()
            assert "aligned" not in member.value.lower()

    def test_prohibited_claims_flag(self, sample_asset_verifications):
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications, total_assets=1
        )
        assert result.prohibited_claims_applied is True

    def test_notes_say_not_compliance(self, sample_asset_verifications):
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications, total_assets=1
        )
        assert "NOT a compliance verdict" in result.notes


# ---------------------------------------------------------------------------
# Instrument metadata spoofing defense
# ---------------------------------------------------------------------------

class TestInstrumentSpoofingDefense:
    def test_forged_legal_state_rejected(self):
        """ESRS-2026-REVISION + legal_state='current_in_force' → rejected."""
        from dataclasses import replace
        forged = replace(
            esrs_2026_adopted(),
            legal_state="current_in_force",
        )
        with pytest.raises(ValueError, match="does not match canonical registry"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=1,
                instrument=forged,
            )

    def test_forged_adoption_date_rejected(self):
        """Forged adoption_date → rejected."""
        from dataclasses import replace
        forged = replace(
            esrs_2023_in_force(),
            adoption_date="2099-01-01",
        )
        with pytest.raises(ValueError, match="does not match canonical registry"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=1,
                instrument=forged,
            )

    def test_canonical_instrument_accepted(self):
        """Canonical instrument from get_esrs_instrument → accepted."""
        canonical = get_esrs_instrument("ESRS-2023-2772")
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=0,
            instrument=canonical,
        )
        assert result.instrument_id == "ESRS-2023-2772"

    def test_unknown_instrument_still_rejected(self):
        unknown = ESRSInstrument(
            instrument_id="ESRS-FAKE-2099",
            title="Fake",
            official_identifier="fake",
            legal_state="current_in_force",
        )
        with pytest.raises(ValueError, match="Unknown ESRS instrument_id"):
            map_georisk_to_esrs(
                asset_verifications=[],
                total_assets=0,
                instrument=unknown,
            )

    def test_get_esrs_instrument_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown ESRS instrument_id"):
            get_esrs_instrument("ESRS-NONEXISTENT")

    def test_get_esrs_instrument_returns_canonical(self):
        inst = get_esrs_instrument("ESRS-2023-2772")
        assert inst == esrs_2023_in_force()
        assert inst.amendment_ids == ("EU-2025-1416",)


class TestOverallEvidenceAggregation:
    """Regression: overall status must be computed from child results."""

    def test_empty_verifications_with_assets_gives_not_assessed(self):
        """No verifications + total_assets=1 → NOT_ASSESSED (no actual evidence)."""
        result = map_georisk_to_esrs(
            asset_verifications=[],
            total_assets=1,
        )
        assert result.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert result.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_asset_without_rules_gives_not_assessed(self):
        """Asset with no rule results → NOT_ASSESSED (no evidence)."""
        asset = {
            "asset_id": "NA-001",
            "overall_status": "source_unverified",
            "rule_results": [],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset],
            total_assets=1,
        )
        assert result.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert result.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_source_unverified_count_not_evidence_for_risk_identification(self):
        """source_unverified > 0 with no evidence_ids → NOT_ASSESSED for risk identification."""
        asset = {
            "asset_id": "SU-001",
            "overall_status": "source_unverified",
            "rule_results": [
                {"rule_id": "R-001", "status": "source_unverified"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset],
            source_unverified_count=1,
            total_assets=1,
        )
        risk_dr = next(
            dm for dm in result.disclosure_mappings
            if dm.semantic_concept == "climate_risk_identification"
        )
        assert risk_dr.evidence_status == ESRSEvidenceStatus.NOT_ASSESSED
        assert risk_dr.mapping_status == ESRSMappingStatus.UNMAPPED

    def test_any_mapped_child_gives_partially_mapped(self):
        """When any DR has evidence → overall EVIDENCE_SUPPORTED_WITH_CAVEATS."""
        asset = {
            "asset_id": "MAP-001",
            "overall_status": "source_unverified",
            "rule_results": [
                {"rule_id": "R-001", "status": "threshold_satisfied"},
            ],
        }
        result = map_georisk_to_esrs(
            asset_verifications=[asset],
            total_assets=1,
        )
        # climate_risk_identification should have evidence → overall changes
        assert result.evidence_status in (
            ESRSEvidenceStatus.EVIDENCE_SUPPORTED_WITH_CAVEATS,
            ESRSEvidenceStatus.NOT_ASSESSED,
        )


class TestVersionMetadataHardening:
    def test_2023_has_amendment_lineage(self):
        inst = esrs_2023_in_force()
        assert "EU-2025-1416" in inst.amendment_ids

    def test_2026_has_transitional_application(self):
        inst = esrs_2026_adopted()
        assert inst.transitional_application_from == "2026-01-01"
        assert inst.application_from == "2027-01-01"

    def test_canonical_registry_has_amendment_ids(self):
        inst = get_esrs_instrument("ESRS-2023-2772")
        assert inst.amendment_ids == ("EU-2025-1416",)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_deterministic(self, sample_asset_verifications):
        r1 = map_georisk_to_esrs(asset_verifications=sample_asset_verifications, total_assets=1)
        r2 = map_georisk_to_esrs(asset_verifications=sample_asset_verifications, total_assets=1)
        assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)

    def test_to_dict_has_prospective_only(self, sample_asset_verifications):
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications, total_assets=1
        )
        d = result.to_dict()
        assert "prospective_only" in d
        assert d["prospective_only"] is False

    def test_2026_prospective_has_prospective_only_true(self, sample_asset_verifications):
        result = map_georisk_to_esrs(
            asset_verifications=sample_asset_verifications,
            total_assets=1,
            instrument=esrs_2026_adopted(),
            mapping_mode="prospective_analysis",
        )
        d = result.to_dict()
        assert d["prospective_only"] is True
