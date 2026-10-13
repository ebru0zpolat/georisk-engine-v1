"""Representative data-centre facility test cases (Workstream 2 acceptance).

Four compliant facilities covering the design space (water-cooled hyperscale,
air-cooled edge, flood-exposed colocation, minimal air-cooled) plus one
deliberately deficient partial submission used to demonstrate the fail-closed
rules.

**Honesty labelling.** These are SYNTHETIC facility profiles built to exercise
the contract — they are not real client facilities and must never be used as
production evidence. The attached ``engineering_review`` records are fixture
records too: they let the fixtures demonstrate the full contract, but a real
profile is blocked until a signed external review is attached. See
``docs/dc-vulnerability/dc-vulnerability-contract.md`` and ``STUBS.md`` #22.
"""

from __future__ import annotations

from datetime import date

from app.schemas.dc_vulnerability import (
    BasementExposure,
    CoolingArchitecture,
    DataCentreVulnerabilityProfile,
    DesignConditionBasis,
    EconomiserConfig,
    ElevationDatum,
    EngineeringReview,
    EvidenceVerificationStatus,
    FuelResupplyAssumption,
    MaintenanceStatus,
    ProtectionCondition,
    RedundancyConfig,
    SubstationDependency,
    SupplyRestriction,
    TelecommunicationRedundancy,
    WaterSourceType,
)

_VALUATION_CUTOFF = date(2026, 6, 30)

#: Synthetic review record — NOT a real sign-off (see module docstring).
_FIXTURE_REVIEW = EngineeringReview(
    reviewer="synthetic fixture reviewer — NOT a real sign-off (STUBS.md #22)",
    report_reference="STUBS.md #22 fixture review record",
    review_date=date(2026, 6, 30),
    git_commit="fixture (not tied to a real review)",
    approved=True,
    notes=(
        "Synthetic record so the fixture exercises the full contract; real "
        "profiles are blocked until a signed external review is attached."
    ),
)


def _hyperscale_water_cooled() -> DataCentreVulnerabilityProfile:
    return DataCentreVulnerabilityProfile(
        facility_id="DC-HYP-001",
        facility_name="NL-AMS-HYP hyperscale campus",
        valuation_cutoff=_VALUATION_CUTOFF,
        evidence_source="client_submission",
        evidence_source_document="Client engineering pack (spec + plant schedule)",
        evidence_document_date=date(2026, 5, 20),
        evidence_effective_date=date(2026, 6, 30),
        evidence_verification_status=EvidenceVerificationStatus.self_declared,
        evidence_reviewer="client-submitted, not yet surveyed",
        engineering_review=_FIXTURE_REVIEW,
        cooling=dict(
            cooling_architecture=CoolingArchitecture.chilled_water_water_cooled,
            primary_cooling_system="Water-cooled chilled-water plant with cooling towers",
            installed_cooling_capacity_kw=24000.0,
            peak_thermal_load_kw=18000.0,
            thermal_headroom_pct=33.3,
            cooling_redundancy=RedundancyConfig.two_n,
            dry_bulb_design_limit_c=33.0,
            wet_bulb_design_limit_c=24.0,
            design_condition_basis=DesignConditionBasis.coincident_extremes,
            economiser_config=EconomiserConfig.water_side,
            economiser_operating_limit_c=12.0,
            equipment_design_standard="ASHRAE TC 9.9 A3",
            commissioning_year=2021,
        ),
        water=dict(
            water_source_mix=[WaterSourceType.municipal, WaterSourceType.reclaimed_water],
            peak_cooling_water_demand_m3h=900.0,
            annual_cooling_water_demand_m3=6_500_000.0,
            on_site_water_storage_hours=12.0,
            alternative_supply_available=True,
            supply_restrictions=[SupplyRestriction.drought_restriction],
            max_inlet_water_temperature_c=28.0,
            inlet_water_quality_limits="TSS <= 10 mg/L; Cl- <= 250 mg/L",
            reclaimed_water_capable=True,
        ),
        electrical=dict(
            grid_feed_count=2,
            grid_feed_independent=True,
            grid_feed_independence_verified=False,  # client-declared only
            substation_dependency=SubstationDependency.dedicated_owned,
            ups_autonomy_minutes=10.0,
            generator_backup=True,
            generator_autonomy_hours=24.0,
            on_site_fuel_capacity_litres=200_000.0,
            fuel_resupply_assumption=FuelResupplyAssumption.contracted,
            fuel_resupply_verified=False,  # client-declared only
            fuel_resupply_detail="72-hour contracted resupply",
            critical_load_coverage_pct=100.0,
            electrical_redundancy_config=RedundancyConfig.two_n,
        ),
        flood=dict(
            flood_exposed=False,
            elevation_datum=ElevationDatum.nap,
            finished_floor_elevation_m=2.5,
        ),
        operational=dict(
            recovery_time_objective_hours=4.0,
            maximum_tolerable_outage_hours=8.0,
            telecommunications_redundancy=TelecommunicationRedundancy.dual_provider_diverse,
            critical_third_party_utilities=["utility_power", "municipal_water"],
            maintenance_or_impairment_status=MaintenanceStatus.normal,
        ),
    )


def _edge_air_cooled() -> DataCentreVulnerabilityProfile:
    return DataCentreVulnerabilityProfile(
        facility_id="DC-EDG-002",
        facility_name="TR-IST-EDG edge facility",
        valuation_cutoff=_VALUATION_CUTOFF,
        evidence_source="engineering_survey",
        evidence_source_document="Site engineering survey 2026-06",
        evidence_document_date=date(2026, 6, 1),
        evidence_effective_date=date(2026, 6, 30),
        evidence_verification_status=EvidenceVerificationStatus.site_inspected,
        evidence_reviewer="fixture-surveyor (synthetic)",
        engineering_review=_FIXTURE_REVIEW,
        cooling=dict(
            cooling_architecture=CoolingArchitecture.air_cooled_dx,
            primary_cooling_system="Air-cooled DX with air-side economiser",
            installed_cooling_capacity_kw=900.0,
            peak_thermal_load_kw=700.0,
            thermal_headroom_pct=28.6,
            cooling_redundancy=RedundancyConfig.n_plus_1,
            dry_bulb_design_limit_c=40.0,
            design_condition_basis=DesignConditionBasis.coincident_extremes,
            economiser_config=EconomiserConfig.air_side,
            economiser_operating_limit_c=15.0,
            equipment_design_standard="ASHRAE TC 9.9 A2",
            commissioning_year=2023,
        ),
        electrical=dict(
            grid_feed_count=2,
            grid_feed_independent=True,
            grid_feed_independence_verified=True,  # independently verified
            substation_dependency=SubstationDependency.utility_network,
            ups_autonomy_minutes=10.0,
            generator_backup=True,
            generator_autonomy_hours=12.0,
            on_site_fuel_capacity_litres=40_000.0,
            fuel_resupply_assumption=FuelResupplyAssumption.contracted,
            fuel_resupply_verified=True,  # independently verified
            critical_load_coverage_pct=95.0,
            electrical_redundancy_config=RedundancyConfig.n_plus_1,
        ),
        flood=dict(
            flood_exposed=False,
            elevation_datum=ElevationDatum.msl,
            finished_floor_elevation_m=5.0,
        ),
        operational=dict(
            recovery_time_objective_hours=2.0,
            maximum_tolerable_outage_hours=4.0,
            telecommunications_redundancy=TelecommunicationRedundancy.dual_provider_diverse,
            critical_third_party_utilities=["utility_power", "municipal_water"],
            maintenance_or_impairment_status=MaintenanceStatus.normal,
        ),
    )


def _flood_exposed_colocation() -> DataCentreVulnerabilityProfile:
    return DataCentreVulnerabilityProfile(
        facility_id="DC-FLD-003",
        facility_name="NL-RTM-COL flood-exposed colocation",
        valuation_cutoff=_VALUATION_CUTOFF,
        evidence_source="engineering_survey",
        evidence_source_document="Site engineering survey + flood-risk assessment 2026-05",
        evidence_document_date=date(2026, 5, 15),
        evidence_effective_date=date(2026, 6, 30),
        evidence_verification_status=EvidenceVerificationStatus.independently_verified,
        evidence_reviewer="fixture-surveyor (synthetic)",
        engineering_review=_FIXTURE_REVIEW,
        cooling=dict(
            cooling_architecture=CoolingArchitecture.chilled_water_air_cooled,
            primary_cooling_system="Air-cooled chilled-water plant",
            installed_cooling_capacity_kw=3200.0,
            peak_thermal_load_kw=2400.0,
            thermal_headroom_pct=33.3,
            cooling_redundancy=RedundancyConfig.n_plus_1,
            dry_bulb_design_limit_c=31.0,
            design_condition_basis=DesignConditionBasis.design_document,
            economiser_config=EconomiserConfig.none,
            equipment_design_standard="ASHRAE TC 9.9 A2",
            commissioning_year=2018,
        ),
        electrical=dict(
            grid_feed_count=2,
            grid_feed_independent=True,
            grid_feed_independence_verified=True,  # independently verified
            substation_dependency=SubstationDependency.shared_campus,
            ups_autonomy_minutes=30.0,
            generator_backup=False,
            critical_load_coverage_pct=100.0,
            electrical_redundancy_config=RedundancyConfig.two_n,
        ),
        flood=dict(
            flood_exposed=True,
            elevation_datum=ElevationDatum.nap,
            finished_floor_elevation_m=6.5,
            lowest_critical_equipment_elevation_m=6.5,
            basement_exposure=BasementExposure.none,
            flood_defence_height_m=7.0,
            flood_defence_design_return_period_years=100,
            drainage_pumping_capacity_m3h=8000.0,
            flood_barrier_deployment_dependency=False,
            protection_inspection_date=date(2026, 5, 15),
            protection_condition=ProtectionCondition.good,
            flood_protection_verified=True,  # independently verified
        ),
        operational=dict(
            recovery_time_objective_hours=0.5,
            maximum_tolerable_outage_hours=2.0,
            telecommunications_redundancy=TelecommunicationRedundancy.dual_provider_shared,
            critical_third_party_utilities=["utility_power"],
            maintenance_or_impairment_status=MaintenanceStatus.planned_maintenance,
        ),
    )


def _minimal_air_cooled() -> DataCentreVulnerabilityProfile:
    return DataCentreVulnerabilityProfile(
        facility_id="DC-MIN-004",
        facility_name="DE-FRA-MIN minimal compliant",
        valuation_cutoff=_VALUATION_CUTOFF,
        evidence_source="client_submission",
        evidence_source_document="Client facility questionnaire 2026-06",
        evidence_document_date=date(2026, 6, 1),
        evidence_effective_date=date(2026, 6, 30),
        evidence_verification_status=EvidenceVerificationStatus.self_declared,
        evidence_reviewer="client-submitted, not yet surveyed",
        engineering_review=_FIXTURE_REVIEW,
        cooling=dict(
            cooling_architecture=CoolingArchitecture.free_cooling_only,
            primary_cooling_system="Free-cooling with air-side economiser",
            installed_cooling_capacity_kw=500.0,
            peak_thermal_load_kw=380.0,
            thermal_headroom_pct=31.6,
            cooling_redundancy=RedundancyConfig.n,
            dry_bulb_design_limit_c=28.0,
            design_condition_basis=DesignConditionBasis.coincident_extremes,
            economiser_config=EconomiserConfig.air_side,
            economiser_operating_limit_c=12.0,
            equipment_design_standard="ASHRAE TC 9.9 A1",
            commissioning_year=2024,
        ),
        electrical=dict(
            grid_feed_count=1,
            grid_feed_independent=False,
            substation_dependency=SubstationDependency.utility_network,
            ups_autonomy_minutes=5.0,
            generator_backup=False,
            critical_load_coverage_pct=60.0,
            electrical_redundancy_config=RedundancyConfig.n,
        ),
        flood=dict(
            flood_exposed=False,
            elevation_datum=ElevationDatum.other,
            finished_floor_elevation_m=4.0,
        ),
        operational=dict(
            recovery_time_objective_hours=0.5,
            maximum_tolerable_outage_hours=1.0,
            telecommunications_redundancy=TelecommunicationRedundancy.single_provider,
            critical_third_party_utilities=[],
            maintenance_or_impairment_status=MaintenanceStatus.normal,
        ),
    )


def _deficient_partial_submission() -> DataCentreVulnerabilityProfile:
    """Deliberately incomplete submission — exercises every conditional rule."""
    return DataCentreVulnerabilityProfile(
        facility_id="DC-DEF-005",
        facility_name="XX-UNK-005 deficient partial submission",
        valuation_cutoff=_VALUATION_CUTOFF,
        evidence_source="client_submission",
        # provenance (DC-049..DC-052) and engineering_review (DC-053) absent
        cooling=dict(
            cooling_architecture=CoolingArchitecture.evaporative_direct,
            installed_cooling_capacity_kw=1500.0,
            peak_thermal_load_kw=2000.0,  # also triggers DC-W01
            thermal_headroom_pct=0.0,
            cooling_redundancy=RedundancyConfig.n_plus_1,
            dry_bulb_design_limit_c=35.0,
            # wet_bulb_design_limit_c missing → DC-007
            # design_condition_basis missing → DC-045
            economiser_config=EconomiserConfig.air_side,
            # economiser_operating_limit_c missing → DC-017
        ),
        water={
            # water_source_mix / demands / storage / restrictions / limits missing → DC-008..DC-016
            "alternative_supply_available": False,
        },
        electrical=dict(
            grid_feed_count=1,
            grid_feed_independent=False,
            substation_dependency=SubstationDependency.utility_network,
            ups_autonomy_minutes=5.0,
            generator_backup=True,
            # generator autonomy / fuel / resupply missing → DC-023..DC-025
            # fuel_resupply_verified missing → DC-048
            critical_load_coverage_pct=80.0,
            electrical_redundancy_config=RedundancyConfig.n_plus_1,
        ),
        flood=dict(
            flood_exposed=True,
            finished_floor_elevation_m=1.2,
            # elevation_datum missing → DC-044
            # equipment elevation / defences / inspection missing → DC-030..DC-037
            # flood_protection_verified missing → DC-047
        ),
        operational=dict(
            # RTO / MTO / telecom / utilities / maintenance missing → DC-038..DC-042
        ),
    )


def representative_facilities() -> list[DataCentreVulnerabilityProfile]:
    """All representative facilities in canonical order."""
    return [
        _hyperscale_water_cooled(),
        _edge_air_cooled(),
        _flood_exposed_colocation(),
        _minimal_air_cooled(),
        _deficient_partial_submission(),
    ]


def facility_by_id(facility_id: str) -> DataCentreVulnerabilityProfile | None:
    for facility in representative_facilities():
        if facility.facility_id == facility_id:
            return facility
    return None


__all__ = ["facility_by_id", "representative_facilities"]
