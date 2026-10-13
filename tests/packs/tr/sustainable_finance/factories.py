"""Shared valid-pack factories for the ``pack-tr`` sustainable-finance tests.

Each factory returns a pack that passes all release gates. Individual tests then break
exactly one field to prove the corresponding gate fails closed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.packs.tr.sustainable_finance.routes import (
    EngagementRole,
    PackStatus,
    RegulatoryRoute,
)
from app.packs.tr.sustainable_finance.schemas import (
    EvidencePackInput,
    ExternalReviewRoles,
    ImpactMetric,
    KPIHistoryPoint,
    KPIRecord,
    PackManifest,
    PhysicalAdaptationEvidence,
    ProjectEligibilityRecord,
    ProvenanceRecord,
    RoleAssignment,
    SPTRecord,
)

FIXED_TS = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def valid_provenance(run_id: str = "run-1") -> ProvenanceRecord:
    return ProvenanceRecord(
        analysis_run_id=run_id,
        source_dataset_id="dataset-1",
        provider="Copernicus",
        licence="Copernicus licence",
        retrieval_date=date(2026, 8, 1),
        source_checksum="c" * 64,
        methodology_versions={"hazard": "flood-v1"},
        input_hash="a" * 64,
        output_hash="b" * 64,
    )


def valid_manifest(
    route: RegulatoryRoute,
    *,
    status: PackStatus = PackStatus.reviewer_ready,
    run_ids: tuple[str, ...] = ("run-1",),
) -> PackManifest:
    return PackManifest(
        pack_id="pack-tr-sf-test",
        regulatory_route=route,
        status=status,
        regulatory_cutoff_date=date(2026, 8, 14),
        issuer_legal_name="Test Issuer A.Ş.",
        responsibility_map=[
            RoleAssignment(
                role=EngagementRole.issuer,
                party_name="Test Issuer A.Ş.",
                responsibility="Owns framework, disclosures and issuance terms.",
            ),
            RoleAssignment(
                role=EngagementRole.georisk_engine,
                party_name="GeoRisk Engine",
                responsibility="Technical data, calculations and evidence packaging.",
            ),
        ],
        framework_document_id="FW-2026-01",
        authorised_body_decision_ref="BOARD-2026-07",
        issuance_ceiling_ref="CEILING-2026-99",
        analysis_run_ids=list(run_ids),
        methodology_versions={"hazard": "flood-v1", "vulnerability": "vuln-v1"},
        external_review_roles=ExternalReviewRoles(
            framework_adviser="Adviser Ltd",
            second_party_opinion_provider="SPO Ltd",
            verifier="Audit Firm Ltd",
        ),
        generated_at=FIXED_TS,
        generated_by="tr-sf-tests",
    )


def valid_kpi(kpi_id: str = "KPI-1") -> KPIRecord:
    return KPIRecord(
        kpi_id=kpi_id,
        name="Percentage of material assets meeting the flood resilience threshold",
        strategy_materiality_link="core real-estate collateral resilience strategy",
        material_sector_issue="physical climate risk to mortgage collateral",
        controlled_management_lever="asset-level retrofit capital programme",
        boundary="Türkiye-owned material assets",
        inclusions=["owned assets > 5m TRY"],
        exclusions=["leased assets"],
        coverage_pct=92.0,
        unit="percent",
        numerator="assets meeting threshold",
        denominator="material assets",
        baseline_value=42.0,
        baseline_reference_date=date(2025, 1, 1),
        baseline_evidence_status="externally verified",
        history=[
            KPIHistoryPoint(year=2022, value=30.0, externally_verified=True),
            KPIHistoryPoint(year=2023, value=35.0, externally_verified=True),
            KPIHistoryPoint(year=2024, value=42.0, externally_verified=True),
        ],
        external_benchmark="sector best-in-class 75%",
        methodology_versions={"resilience": "resilience-v1"},
        dataset_versions={"cadastre": "cadastre-v2"},
        data_owner="Risk team",
        source_system_owner="GeoRisk Engine",
        measurement_frequency="annual",
        reporting_frequency="annual",
        verification_evidence="auditor workpapers 2025",
        responsible_external_reviewer="Audit Firm Ltd",
        recalculation_policy="restate baseline on acquisition/disposal > 5% of material assets",
        uncertainty="±3 percentage points from terrain resolution",
        physical_risk_candidate_id="pct_material_assets_meeting_resilience_threshold",
    )


def valid_spt(spt_id: str = "SPT-1", kpi_id: str = "KPI-1") -> SPTRecord:
    return SPTRecord(
        spt_id=spt_id,
        linked_kpi_id=kpi_id,
        target_value=75.0,
        target_date=date(2030, 12, 31),
        observation_frequency="annual",
        materiality_explanation="closes the resilience gap on material collateral",
        beyond_bau_explanation="exceeds trend extrapolation of historical retrofit rate",
        issuer_history_used=True,
        peer_or_sector_comparison="sector best-in-class 75%",
        science_based_reference="national adaptation plan targets",
        starting_reference_value=42.0,
        reference_verification_status="externally verified",
        action_plan="phased retrofit programme 2026-2030",
        quantified_contributions="+7pp per year",
        factors_outside_control=["hazard intensity change"],
        trigger_event="coupon step-up of 25bps if SPT not met at target date",
        financial_or_structural_consequence="issuer/adviser supplied coupon step-up",
        fallback_if_not_calculable="use last externally verified KPI value",
        exceptional_event_rules="recalc on material M&A",
        spo_refresh_trigger="material change in KPI methodology",
        performance_report_calendar="annual, verified",
    )


def valid_uop_pack(status: PackStatus = PackStatus.reviewer_ready) -> EvidencePackInput:
    return EvidencePackInput(
        manifest=valid_manifest(RegulatoryRoute.use_of_proceeds, status=status),
        provenance=[valid_provenance()],
        projects=[
            ProjectEligibilityRecord(
                project_id="PRJ-1",
                owner="Test Issuer A.Ş.",
                green_category=9,
                objective="climate-change adaptation of coastal facilities",
                benefit_measures=["reduced flood downtime"],
                evidence_run_ids=["run-1"],
            )
        ],
        adaptation_evidence=[
            PhysicalAdaptationEvidence(
                project_id="PRJ-1",
                material_hazards=["fluvial_flood"],
                adaptation_measure="flood barrier",
                implementation_status="planned",
            )
        ],
        impact_metrics=[
            ImpactMetric(
                metric_id="IMP-1",
                project_id="PRJ-1",
                description="expected reduction in flood downtime hours",
                value=120.0,
                unit="hours/year",
                methodology_and_assumptions="constant-hazard before/after",
                evidence_run_id="run-1",
            )
        ],
        uncertainty_and_limitations=(
            "Vulnerability curves are preliminary and labelled synthetic where used; "
            "monetary loss proxies are not for trigger use."
        ),
    )


def valid_sll_pack(status: PackStatus = PackStatus.reviewer_ready) -> EvidencePackInput:
    return EvidencePackInput(
        manifest=valid_manifest(RegulatoryRoute.sustainability_linked, status=status),
        provenance=[valid_provenance()],
        kpis=[valid_kpi()],
        spts=[valid_spt()],
        uncertainty_and_limitations=(
            "KPI improvement depends on issuer capital programme; hazard reference held "
            "constant; historical values externally verified."
        ),
    )
