"""Amsterdam Hemelwater (rainwater management) regulation rules.

Sources:
  - Omgevingsplan gemeente Amsterdam, Paragraaf 4.4.2
    "Hemelwaterafvoer bij bouwwerken" (current regulation;
    superseded Hemelwaterverordening Amsterdam expired 31 Oct 2024)
  - Waterschapsverordening Amstel, Gooi en Vecht (AGV)
    (successor to former Keur; effective under Omgevingswet)

This module encodes the **explicit numeric thresholds** from the
official publications.  It does NOT reproduce the full legal text;
for that, consult the source_registry entries.

ARCHITECTURAL NOTE — Two separate engines are needed:
  1. REGULATORY CAPACITY GATE (this module): evaluates three
     independent numeric thresholds:
       - storage_capacity_l_per_m2 >= 60 L/m² (minimum storage capacity)
       - max_discharge_l_per_m2_per_hour <= 1 L/m²/h (sewer discharge limit)
       - max_emptying_time_hours <= 60 h (drainage time limit)
     These are INDEPENDENT requirements — the 60 L/m² is a minimum
     storage capacity, NOT a net volume after discharge deduction.
     You cannot subtract discharge time from the storage requirement.
  2. HYDROLOGICAL STRESS MODEL (not yet implemented): simulates
     actual rainfall-runoff-storage dynamics using KNMI hyetographs,
     roof area, runoff coefficients, green-roof retention, and
     controlled discharge routing.

Classification: This is rule-engine input data, NOT a legal
interpretation.  Threshold values must be verified against the
current official publication before any production use.

Source provenance status:
  content_hash = PLACEHOLDER_NOT_VERIFIED for all sources.
  source_checksums_verified = False for all sources.
  artifact_sha256 = PLACEHOLDER_NOT_VERIFIED for all artifacts.
  These MUST be updated to real SHA-256 values and True only after
  an independent process has retrieved the official publication and
  computed a verified content hash.
"""

from __future__ import annotations

from app.regulation.models import (
    ApplicabilityFilter,
    Jurisdiction,
    OfficialSourceArtifact,
    PackClassification,
    RegulatoryRule,
    RegulatorySource,
    ThresholdProvenance,
)

# ---------------------------------------------------------------------------
# Sentinel for unverified source content hashes
# ---------------------------------------------------------------------------

PLACEHOLDER_NOT_VERIFIED = "PLACEHOLDER_NOT_VERIFIED"


# ---------------------------------------------------------------------------
# Official source artifact registry
# ---------------------------------------------------------------------------

def amsterdam_source_artifacts() -> dict[str, OfficialSourceArtifact]:
    """Return the official source artifact registry for Amsterdam hemelwater.

    All artifact_sha256 values are PLACEHOLDER_NOT_VERIFIED until the
    actual source artifacts have been independently retrieved from
    official publication domains and their raw bytes hashed.

    Provenance chain:
      official artifact bytes
        → source SHA256 (artifact_sha256)
        → article / paragraph / lid
        → threshold value
        → rule
        → asset applicability evidence
        → evidence pack
        → pack SHA256
    """
    artifacts = {
        "amsterdam-omgevingsplan-442": OfficialSourceArtifact(
            source_id="amsterdam-omgevingsplan-442",
            authority="Gemeente Amsterdam",
            official_publication_id="Omgevingsplan gemeente Amsterdam, Paragraaf 4.4.2",
            title="Omgevingsplan gemeente Amsterdam — Paragraaf 4.4.2 Hemelwaterafvoer bij bouwwerken",
            source_url="https://lokaleregelgeving.overheid.nl/DR000417648",
            retrieved_at="",
            effective_from="2024-01-01",
            mime_type="application/pdf",
            byte_length=0,
            artifact_sha256=PLACEHOLDER_NOT_VERIFIED,
            source_checksums_verified=False,
            status="current",
            notes=(
                "Consolidated Omgevingsplan text.  Artikel 4.116 contains "
                "three independent thresholds: ≥60 L/m² storage, ≤1 L/m²/h "
                "discharge, ≤60h emptying.  Hemelwaterverordening Amsterdam "
                "expired 31 Oct 2024."
            ),
        ),
        "agv-waterschapsverordening": OfficialSourceArtifact(
            source_id="agv-waterschapsverordening",
            authority="Waterschap Amstel, Gooi en Vecht",
            official_publication_id="Waterschapsverordening Amstel, Gooi en Vecht",
            title="Waterschapsverordening AGV — water system provisions",
            source_url="https://www.agv.nl/regelgeving",
            retrieved_at="",
            effective_from="2024-01-01",
            mime_type="application/pdf",
            byte_length=0,
            artifact_sha256=PLACEHOLDER_NOT_VERIFIED,
            source_checksums_verified=False,
            status="current",
            notes=(
                "The legal-text reference remains useful, but its associated "
                "pre-12-June-2026 work-area geometry is stale and must not "
                "establish asset applicability. Current geometry must be "
                "reacquired, versioned, hashed, and spatially evaluated. A709 "
                "Strandeiland is adopted but deferred until works complete. "
                "Contains water-system, surface "
                "water, groundwater, discharge permits, and area-specific "
                "rules (e.g. 300 m² hard surface threshold, 10% open water "
                "compensation).  NOT the source for 60/1/60 thresholds."
            ),
        ),
    }
    return artifacts


# ---------------------------------------------------------------------------
# Threshold provenance
# ---------------------------------------------------------------------------

def amsterdam_hemelwater_provenance() -> list[ThresholdProvenance]:
    """Return threshold provenance records for Amsterdam hemelwater rules.

    Each record connects a rule to the exact citation in the official
    publication.  provenance_verified is False until the full chain
    (artifact retrieval → SHA256 → article/lid mapping) is completed.

    Citation mapping:
      NL-AM-HW-STORAGE-001  → Artikel 4.116, lid 1(a), 60 L/m²
      NL-AM-HW-DISCHARGE-001 → Artikel 4.116, lid 1(b), 1 L/m²/h
      NL-AM-HW-EMPTYING-001  → Artikel 4.116, lid 1(c), 60 h
    """
    return [
        ThresholdProvenance(
            rule_id="NL-AM-HW-STORAGE-001",
            source_id="amsterdam-omgevingsplan-442",
            official_artifact_sha256=PLACEHOLDER_NOT_VERIFIED,
            article_reference="Artikel 4.116",
            paragraph_reference="Paragraaf 4.4.2",
            lid_reference="lid 1(a)",
            page_reference="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            provenance_verified=False,
        ),
        ThresholdProvenance(
            rule_id="NL-AM-HW-DISCHARGE-001",
            source_id="amsterdam-omgevingsplan-442",
            official_artifact_sha256=PLACEHOLDER_NOT_VERIFIED,
            article_reference="Artikel 4.116",
            paragraph_reference="Paragraaf 4.4.2",
            lid_reference="lid 1(b)",
            page_reference="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            provenance_verified=False,
        ),
        ThresholdProvenance(
            rule_id="NL-AM-HW-EMPTYING-001",
            source_id="amsterdam-omgevingsplan-442",
            official_artifact_sha256=PLACEHOLDER_NOT_VERIFIED,
            article_reference="Artikel 4.116",
            paragraph_reference="Paragraaf 4.4.2",
            lid_reference="lid 1(c)",
            page_reference="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            provenance_verified=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Legacy source registry (kept for backward compatibility)
# ---------------------------------------------------------------------------

def amsterdam_hemelwater_sources() -> list[RegulatorySource]:
    """Return the official source registry for Amsterdam hemelwater rules.

    All content_hash values are PLACEHOLDER_NOT_VERIFIED until the
    actual source artifacts have been independently retrieved and
    their content hashed.  source_checksums_verified is False for
    all entries.
    """
    return [
        RegulatorySource(
            source_id="amsterdam-omgevingsplan-442",
            authority="Gemeente Amsterdam",
            title="Omgevingsplan gemeente Amsterdam — Paragraaf 4.4.2 Hemelwaterafvoer bij bouwwerken",
            reference_url="https://lokaleregelgeving.overheid.nl/DR000417648",
            content_hash=PLACEHOLDER_NOT_VERIFIED,
            source_checksums_verified=False,
            status="current",
            effective_date="2024-01-01",
            publication_reference=(
                "Gemeenteblad Amsterdam, Paragraaf 4.4.2 "
                "'Hemelwaterafvoer bij bouwwerken'. "
                "Exact section/page to be verified against retrieved artifact."
            ),
        ),
        RegulatorySource(
            source_id="agv-waterschapsverordening",
            authority="Waterschap Amstel, Gooi en Vecht",
            title="Waterschapsverordening AGV — water system provisions",
            reference_url="https://www.agv.nl/regelgeving",
            content_hash=PLACEHOLDER_NOT_VERIFIED,
            source_checksums_verified=False,
            status="current",
            effective_date="2024-01-01",
            publication_reference=(
                "Waterschapsverordening Amstel, Gooi en Vecht "
                "(successor to former Keur). "
                "Exact section/page to be verified against retrieved artifact."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Jurisdiction
# ---------------------------------------------------------------------------

def amsterdam_hemelwater_jurisdiction() -> Jurisdiction:
    return Jurisdiction(
        level="municipal",
        name="Amsterdam",
        authority_ids=("gemeente-amsterdam", "waterschap-agv"),
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def amsterdam_hemelwater_classification() -> PackClassification:
    return PackClassification(
        evidence_class="synthetic_reference",
        customer_data_status="not_customer_data",
        production_eligible=False,
        decision_use_approved=False,
    )


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

def amsterdam_hemelwater_rules() -> list[RegulatoryRule]:
    """Return the Amsterdam hemelwater rule set.

    Three INDEPENDENT numeric thresholds from the official publications:

    1. **Storage requirement**: ≥ 60 L per m² built area
       (minimum storage capacity; NOT net volume after discharge)
    2. **Max public sewer discharge**: ≤ 1 L/m²/hour
       (sewer discharge limit)
    3. **Emptying requirement**: stored water must be drainable
       within 60 hours (drainage time limit)

    These are SEPARATE requirements — the 60 L/m² minimum storage
    is not reduced by allowing 2h of discharge.  Example:
    For a 2,500 m² building: V_required = 2,500 × 60 = 150,000 L.

    All three thresholds are from the Amsterdam Omgevingsplan
    (Paragraaf 4.4.2 / Artikel 4.116), NOT from the AGV
    Waterschapsverordening.  The AGV source is retained for
    future AGV-specific rules (e.g. sert yüzey kompanzasyon).

    Threshold provenance status:
      threshold_source_verified = False for all rules.
      publication_section, publication_page are indicative references
      that must be confirmed against the retrieved official text.
      Before any production use, each value must be independently
      verified by a qualified expert.
    """
    return [
        RegulatoryRule(
            rule_id="NL-AM-HW-STORAGE-001",
            source_id="amsterdam-omgevingsplan-442",
            rule_type="storage_requirement",
            parameter_name="storage_capacity_l_per_m2",
            threshold_value=60.0,
            threshold_unit="L/m²",
            comparison="gte",
            applicability_filter=ApplicabilityFilter(
                municipality="Amsterdam",
            ),
            publication_section="Artikel 4.116, lid 1(a) — minimale bergingscapaciteit",
            publication_page="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            threshold_source_verified=False,
        ),
        RegulatoryRule(
            rule_id="NL-AM-HW-DISCHARGE-001",
            source_id="amsterdam-omgevingsplan-442",
            rule_type="discharge_limit",
            parameter_name="max_discharge_l_per_m2_per_hour",
            threshold_value=1.0,
            threshold_unit="L/m²/h",
            comparison="lte",
            applicability_filter=ApplicabilityFilter(
                municipality="Amsterdam",
            ),
            publication_section="Artikel 4.116, lid 1(b) — lozingsnormering hemelwater",
            publication_page="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            threshold_source_verified=False,
        ),
        RegulatoryRule(
            rule_id="NL-AM-HW-EMPTYING-001",
            source_id="amsterdam-omgevingsplan-442",
            rule_type="emptying_requirement",
            parameter_name="max_emptying_time_hours",
            threshold_value=60.0,
            threshold_unit="h",
            comparison="lte",
            applicability_filter=ApplicabilityFilter(
                municipality="Amsterdam",
            ),
            publication_section="Artikel 4.116, lid 1(c) — ledigingstermijn",
            publication_page="(page to be verified against retrieved artifact)",
            effective_date="2024-01-01",
            threshold_source_verified=False,
        ),
    ]
