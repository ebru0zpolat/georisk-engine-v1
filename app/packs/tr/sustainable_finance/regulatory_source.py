"""``pack-tr`` regulatory source manifest for CMB/SPK decision ``i-SPK.128.29``.

This module is the controlling machine-readable record of the two guidelines adopted by
Principle Decision ``i-SPK.128.29`` (13 August 2026, no. ``49/1500``). The current official
Turkish texts prevail over this module; where a value here is uncertain it is recorded as
an interpretation flag rather than asserted as settled law.

Country-specific content lives here so that no regulatory rule leaks into georisk-core.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping

PACK_ID = "pack-tr"
PACK_VERSION = "0.2.0"
EVIDENCE_PACK_FORMAT_VERSION = "tr-sustainable-finance-evidence-pack-v0.2"

# --- Decision identity -------------------------------------------------------------------

DECISION_ID = "i-SPK.128.29"
DECISION_DATE = "2026-08-13"
DECISION_NUMBER = "49/1500"
LEGAL_BASIS = "Capital Markets Law No. 6362, Articles 1 and 128/1(e)"

# The 2022 framework this decision replaces for new applications.
SUPERSEDED_DECISION_ID = "i-SPK.128.18"

# Lease-certificate fee discount is additional to this earlier CMB decision.
LEASE_CERTIFICATE_PRIOR_DISCOUNT_DECISION = "24 June 2016, no. 20/710"
CMB_FEE_DISCOUNT_FRACTION = 0.50  # Issuance-process fact — NOT a GeoRisk-calculated saving.


class Guideline(str, Enum):
    """The two guidelines adopted under the single principle decision."""

    use_of_proceeds = "green_sustainable_social"
    sustainability_linked = "sustainability_linked"


# Primary sources to record in / verify before releasing a pack (spec §2.1).
PRIMARY_SOURCES: tuple[str, ...] = (
    "CMB announcement dated 13 August 2026",
    "Guideline on Green, Sustainable and Social Capital Market Instruments — official full text",
    "Guideline on Sustainability-Linked Capital Market Instruments — official full text",
    "CMB Bulletin 2026/51",
    "Superseded 2022 guideline and decision i-SPK.128.18",
)

# International references the guidelines were prepared with reference to.
INTERNATIONAL_REFERENCES: tuple[str, ...] = (
    "ICMA Green Bond Principles",
    "ICMA Sustainability Bond Guidelines",
    "ICMA Social Bond Principles",
    "ICMA guidance for green/social/sustainability sukuk",
    "ICMA Sustainability-Linked Bond Principles",
    "Regulation (EU) 2023/2631 on European Green Bonds",
)

# --- Mandatory components (must never be downgraded to optional pack fields, spec §2.2) ---

USE_OF_PROCEEDS_COMPONENTS: tuple[str, ...] = (
    "use_of_proceeds",
    "project_evaluation_and_selection",
    "management_of_proceeds",
    "reporting",
)

SUSTAINABILITY_LINKED_COMPONENTS: tuple[str, ...] = (
    "kpi_selection",
    "spt_calibration",
    "instrument_characteristics",
    "reporting",
    "verification",
)

# Instrument types in scope for both guidelines.
INSTRUMENT_SCOPE: tuple[str, ...] = (
    "debt_instruments",
    "lease_certificates",
    "covered_bonds_and_mortgage_covered_securities",
    "asset_backed_and_mortgage_backed_securities",
    "project_backed_securities",
    "real_estate_certificates",
    "other_capital_market_instruments",
)

# --- Green project categories (non-exhaustive, spec §D.4) --------------------------------
# Keyed by category number as it appears in the guideline. The ``georisk_relevant`` flag
# marks categories for which asset-level physical-risk / adaptation evidence is directly
# useful — it does NOT assert eligibility.

_GREEN_CATEGORIES: dict[int, dict[str, object]] = {
    1: {"label": "Renewable energy", "georisk_relevant": False},
    2: {"label": "Energy efficiency", "georisk_relevant": False},
    3: {"label": "Pollution prevention and control", "georisk_relevant": False},
    4: {"label": "Material recovery and circular-economy waste facilities", "georisk_relevant": False},
    5: {
        "label": "Environmentally sustainable management of living natural resources and land use",
        "georisk_relevant": False,
    },
    6: {"label": "Terrestrial and aquatic biodiversity conservation", "georisk_relevant": False},
    7: {"label": "Clean transportation", "georisk_relevant": False},
    8: {
        "label": "Sustainable water and wastewater management (incl. sustainable flood-reduction infrastructure)",
        "georisk_relevant": True,
    },
    9: {
        "label": "Climate-change adaptation (climate observation, early-warning, resilient infrastructure)",
        "georisk_relevant": True,
    },
    10: {
        "label": "Eco-efficient and/or circular products, production technologies and processes",
        "georisk_relevant": False,
    },
    11: {"label": "Green buildings", "georisk_relevant": True},
    12: {"label": "Climate-change mitigation", "georisk_relevant": False},
}

GREEN_PROJECT_CATEGORIES: Mapping[int, Mapping[str, object]] = MappingProxyType(
    {k: MappingProxyType(v) for k, v in _GREEN_CATEGORIES.items()}
)

GEORISK_RELEVANT_GREEN_CATEGORIES: tuple[int, ...] = tuple(
    sorted(k for k, v in _GREEN_CATEGORIES.items() if v["georisk_relevant"])
)

# --- Social project categories & target populations (non-exhaustive, spec §D.5) ---------

SOCIAL_PROJECT_CATEGORIES: tuple[str, ...] = (
    "accessible_basic_infrastructure",
    "access_to_essential_services",
    "affordable_housing",
    "employment_generation_and_just_transition",
    "food_security_and_sustainable_food_systems",
    "socioeconomic_advancement_and_empowerment",
    "accessible_psychosocial_support",
)

SOCIAL_TARGET_POPULATIONS: tuple[str, ...] = (
    "below_poverty_line",
    "excluded_persons_or_communities",
    "persons_with_disabilities",
    "migrants_or_displaced_persons",
    "low_educational_attainment",
    "underserved_lacking_essential_access",
    "unemployed_or_climate_affected_workers",
    "women_and_children",
    "ageing_populations",
    "vulnerable_young_people",
    "other_vulnerable_groups",
)

# --- Recognised external-review service types (spec §D.9 / §E.9) -------------------------
# Note: 2022's certification and green rating/scoring are NO LONGER guideline review types.

EXTERNAL_REVIEW_TYPES: tuple[str, ...] = ("second_party_opinion", "verification")

# Refinancing look-back guidance.
RECOMMENDED_LOOKBACK_MONTHS = 36

# Reporting deadlines (use-of-proceeds route), in the guideline's own units.
MATERIAL_DEVELOPMENT_MAX_WEEKS = 6
FINAL_REPORTING_MAX_MONTHS_AFTER_FULL_ALLOCATION = 3
MIN_HISTORICAL_KPI_YEARS = 3  # Where a KPI has not previously been disclosed (spec §E.4).

# --- Interpretation flags (spec §G) -----------------------------------------------------
# Each must be surfaced to capital-markets counsel before an EXTERNAL pack is released.

INTERPRETATION_FLAGS: tuple[dict[str, str], ...] = (
    {
        "id": "replacement_vs_repeal",
        "issue": "New use-of-proceeds guideline replaces the 2022 guideline rather than a universal repeal clause.",
        "control": "Apply the new guideline to post-publication applications; get advice for existing ceilings.",
    },
    {
        "id": "domestic_kap_wording",
        "issue": "Domestic provisions require website and KAP publication without the 'if a KAP member' qualifier.",
        "control": "Treat domestic KAP publication as mandatory unless the CMB confirms otherwise.",
    },
    {
        "id": "uop_verifier_eligibility",
        "issue": "Verification definition refers to capital-markets independent audit firms.",
        "control": "Use an authorised independent audit firm for final allocation verification unless the CMB confirms another provider.",
    },
    {
        "id": "sll_second_party_expertise",
        "issue": "One definition refers to environmental-sustainability expertise although scope includes E, S and G targets.",
        "control": "Require expertise matching the actual KPI/SPT subject; seek adviser confirmation for social/governance-only structures.",
    },
    {
        "id": "financial_consequence_form",
        "issue": "Instrument definition requires characteristics that change with performance; detailed provisions mention coupon or other changes.",
        "control": "Include a clear, enforceable financial/structural effect; do not assume a coupon step-up is the only model.",
    },
    {
        "id": "impact_report_recurrence",
        "issue": "New text requires the impact report within three months after full allocation but does not clearly create a recurring annual cycle.",
        "control": "Treat the three-month report as mandatory; get advice if ongoing reporting is promised.",
    },
    {
        "id": "hybrid_instruments",
        "issue": "The two guidelines do not expressly set out a combined use-of-proceeds plus sustainability-linked procedure.",
        "control": "Keep the routes separate; require capital-markets legal advice before packaging a hybrid structure.",
    },
    {
        "id": "cumulative_fee_effect",
        "issue": "Lease-certificate discount is additional to the 2016 discount but no final mathematical fee is stated.",
        "control": "Do not publish an effective fee calculation without CMB/adviser confirmation.",
    },
    {
        "id": "physical_risk_kpi_not_named",
        "issue": "The Sustainability-Linked Guideline does not require a physical-risk KPI by name.",
        "control": "Describe physical-risk use as a product inference and technical use case, not a direct statutory mandate.",
    },
)


def regulatory_source_manifest() -> dict[str, object]:
    """Machine-readable regulatory-source block for the pack manifest (spec §5)."""
    return {
        "regulatory_source_id": DECISION_ID,
        "decision_date": DECISION_DATE,
        "decision_number": DECISION_NUMBER,
        "legal_basis": LEGAL_BASIS,
        "superseded_decision_id": SUPERSEDED_DECISION_ID,
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "evidence_pack_format_version": EVIDENCE_PACK_FORMAT_VERSION,
        "guidelines": [g.value for g in Guideline],
        "primary_sources": list(PRIMARY_SOURCES),
        "external_review_types": list(EXTERNAL_REVIEW_TYPES),
        "cmb_fee_discount_fraction": CMB_FEE_DISCOUNT_FRACTION,
        "interpretation_flag_ids": [f["id"] for f in INTERPRETATION_FLAGS],
    }


__all__ = [
    "CMB_FEE_DISCOUNT_FRACTION",
    "DECISION_DATE",
    "DECISION_ID",
    "DECISION_NUMBER",
    "EVIDENCE_PACK_FORMAT_VERSION",
    "EXTERNAL_REVIEW_TYPES",
    "FINAL_REPORTING_MAX_MONTHS_AFTER_FULL_ALLOCATION",
    "GEORISK_RELEVANT_GREEN_CATEGORIES",
    "GREEN_PROJECT_CATEGORIES",
    "Guideline",
    "INSTRUMENT_SCOPE",
    "INTERNATIONAL_REFERENCES",
    "INTERPRETATION_FLAGS",
    "LEASE_CERTIFICATE_PRIOR_DISCOUNT_DECISION",
    "LEGAL_BASIS",
    "MATERIAL_DEVELOPMENT_MAX_WEEKS",
    "MIN_HISTORICAL_KPI_YEARS",
    "PACK_ID",
    "PACK_VERSION",
    "PRIMARY_SOURCES",
    "RECOMMENDED_LOOKBACK_MONTHS",
    "SOCIAL_PROJECT_CATEGORIES",
    "SOCIAL_TARGET_POPULATIONS",
    "SUPERSEDED_DECISION_ID",
    "SUSTAINABILITY_LINKED_COMPONENTS",
    "USE_OF_PROCEEDS_COMPONENTS",
    "regulatory_source_manifest",
]
