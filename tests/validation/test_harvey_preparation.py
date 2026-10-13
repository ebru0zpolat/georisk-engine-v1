from datetime import date

import pytest

from app.validation.harvey import (
    BaselineCalibrationSpec,
    DataUseManifest,
    HARVEY_ESTIMAND_ID,
    adapt_fema_v3_record,
    calibrate_historical_baseline,
    qualify_outcome_blind_coverage,
    validate_harvey_claim,
)

SHA = "a" * 64


def _spec() -> BaselineCalibrationSpec:
    return BaselineCalibrationSpec(
        geography=("TX",),
        start_date=date(2000, 1, 1),
        cutoff=date(2017, 8, 24),
        occupancy_types=("RES1",),
        include_zero_payments=True,
        denominator_field="totalBuildingInsuranceCoverage",
        numerator_field="buildingClaimPaymentAmount",
        exclude_missing_or_zero_coverage=True,
        outlier_policy="retain_all_eligible_records",
        minimum_sample_size=200,
        bootstrap_repetitions=10_000,
        bootstrap_seed=20170825,
        estimand_id=HARVEY_ESTIMAND_ID,
    )


def test_baseline_uses_ratio_of_sums_and_keeps_zero_payments() -> None:
    rows = [
        {
            "dateOfLoss": "2016-01-01",
            "eventName": "Other",
            "state": "TX",
            "occupancyType": "RES1",
            "totalBuildingInsuranceCoverage": 100,
            "amountPaidOnBuildingClaim": 10 if i < 100 else 0,
        }
        for i in range(200)
    ]
    artifact = calibrate_historical_baseline(
        rows,
        spec=_spec(),
        query_parameters={"state": "TX", "$filter": "dateOfLoss le 2017-08-24"},
        source_data_sha256=SHA,
        calculation_code_commit="b" * 40,
        created_at="2026-09-04T00:00:00Z",
    )
    assert artifact.ratio == pytest.approx(0.05)
    assert artifact.sample_size == 200
    assert artifact.query_fingerprint.startswith("sha256:")
    assert artifact.outcome_accessed_for_evaluation is False
    assert artifact.estimand_id == HARVEY_ESTIMAND_ID
    assert artifact.diagnostics["counts_by_year"] == {"2016": 200}
    assert artifact.diagnostics["zero_payment_fraction"] == pytest.approx(0.5)
    assert artifact.diagnostics["bootstrap"]["repetitions"] == 10_000


def test_baseline_rejects_harvey_or_post_cutoff_rows() -> None:
    base = {
        "dateOfLoss": "2017-08-20",
        "eventName": "Hurricane Harvey",
        "state": "TX",
        "occupancyType": "RES1",
        "totalBuildingInsuranceCoverage": 100,
        "amountPaidOnBuildingClaim": 10,
    }
    with pytest.raises(ValueError, match="excluded event"):
        calibrate_historical_baseline(
            [base],
            spec=_spec(),
            query_parameters={},
            source_data_sha256=SHA,
            calculation_code_commit="b" * 40,
            created_at="now",
        )
    with pytest.raises(ValueError, match="outside"):
        calibrate_historical_baseline(
            [{**base, "eventName": "Other", "dateOfLoss": "2017-08-25"}],
            spec=_spec(),
            query_parameters={},
            source_data_sha256=SHA,
            calculation_code_commit="b" * 40,
            created_at="now",
        )


def test_licence_manifest_fails_closed_without_approval_and_hashes() -> None:
    manifest = DataUseManifest(
        endpoint="https://www.fema.gov/api/open/v3/NfipClaims",
        data_version="v3",
        schema_sha256=SHA,
        query_parameters={},
        retrieval_timestamp="now",
        raw_response_sha256=(SHA,),
        terms_archive_sha256=SHA,
        commercial_use_assessment="Permitted",
        assessed_by="Reviewer",
        licence_status="pending",
        retention_policy="90 days",
        access_restrictions="least privilege",
        field_mapping={
            "amountPaidOnBuildingClaim": "buildingClaimPaymentAmount",
            "totalBuildingInsuranceCoverage": "totalBuildingInsuranceCoverage",
        },
    )
    assert manifest.permits_real_provider() is False
    object.__setattr__(manifest, "licence_status", "approved")
    assert manifest.permits_real_provider() is True


def test_fema_v3_mapping_has_no_payment_or_damage_fallback() -> None:
    canonical = adapt_fema_v3_record(
        {
            "amountPaidOnBuildingClaim": 125.0,
            "netBuildingPaymentAmount": 999.0,
            "buildingDamageAmount": 888.0,
        }
    )
    assert canonical["buildingClaimPaymentAmount"] == 125.0
    with pytest.raises(ValueError, match="not substitutes"):
        adapt_fema_v3_record(
            {"netBuildingPaymentAmount": 999.0, "buildingDamageAmount": 888.0}
        )


def test_estimand_rejects_eal_and_nl_cre_claims() -> None:
    validate_harvey_claim(HARVEY_ESTIMAND_ID, "harvey_event_loss_method_validated")
    with pytest.raises(ValueError, match="outside"):
        validate_harvey_claim(HARVEY_ESTIMAND_ID, "annual_eal_validated")
    with pytest.raises(ValueError, match="outside"):
        validate_harvey_claim(HARVEY_ESTIMAND_ID, "model_validated_for_nl_cre_use_case")


def test_coverage_gate_rejects_outcomes_and_reports_all_stop_rules() -> None:
    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [{"location_cluster": "a", "usgs_covered": True, "observed_loss": 1}],
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )
    result = qualify_outcome_blind_coverage(
        [
            {"location_cluster": str(i % 10), "usgs_covered": i < 180}
            for i in range(199)
        ],
        usgs_artifact_sha256=SHA,
        crs="EPSG:4326",
        depth_unit="m",
        nodata_policy="uncovered",
    )
    assert result.qualified is False
    assert (
        result.stop_reason
        == "sample_size_below_200,location_clusters_below_30,usgs_coverage_below_0.95"
    )


def test_coverage_gate_passes_at_frozen_thresholds() -> None:
    result = qualify_outcome_blind_coverage(
        [
            {"location_cluster": str(i % 30), "usgs_covered": i < 190}
            for i in range(200)
        ],
        usgs_artifact_sha256=SHA,
        crs="EPSG:4326",
        depth_unit="metre",
        nodata_policy="uncovered",
    )
    assert result.qualified is True
    assert result.coverage_fraction == pytest.approx(0.95)


@pytest.mark.parametrize(
    "field",
    [
        "amountPaidOnBuildingClaim",
        "buildingClaimPaymentAmount",
        "netBuildingPaymentAmount",
        "buildingDamageAmount",
        "observed_loss",
    ],
)
def test_post_event_outcome_fields_cannot_be_predictor_inputs(field: str) -> None:
    """An outcome is a scoring target only; it is never a predictor or coverage input."""
    rows = [{"location_cluster": "a", "usgs_covered": True, field: 1000}]
    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            rows,
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


@pytest.mark.parametrize(
    "alias",
    [
        "building_claim_payment_amount",
        "building_claim_payment",
        "BuildingClaimPaymentAmount",
        "building-claim-payment-amount",
        "net_building_payment_amount",
        "total_claim_payment_amount",
    ],
)
def test_outcome_aliases_are_refused_after_normalisation(alias: str) -> None:
    """A case/separator variant of an outcome name is the same outcome (P1-03)."""
    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [{"location_cluster": "a", "usgs_covered": True, alias: 1000}],
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"provider": {"buildingClaimPaymentAmount": 1000}},
        {"derived": {"observed_loss": 1000}},
        {"claim": {"buildingDamageAmount": 2000}},
        {"rows": [{"net_building_payment_amount": 1000}]},
        {"a": [{"nested": {"amount_paid_on_building_claim": 1000}}]},
    ],
)
def test_nested_outcome_information_is_rejected(payload: dict) -> None:
    """Nesting must not hide an outcome from the leakage guard (P1-03 + P1-07)."""
    row = {"location_cluster": "a", "usgs_covered": True, **payload}
    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [row],
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


def test_outcome_paths_are_named_in_the_refusal() -> None:
    with pytest.raises(ValueError, match=r"provider\.buildingClaimPaymentAmount"):
        qualify_outcome_blind_coverage(
            [
                {
                    "location_cluster": "a",
                    "usgs_covered": True,
                    "provider": {"buildingClaimPaymentAmount": 1000},
                }
            ],
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


def test_explicit_false_coverage_string_is_not_counted_as_covered() -> None:
    """``bool("false")`` is True, which would score absent hazard data as covered (P1-04)."""
    rows = [
        {"location_cluster": str(i % 30), "usgs_covered": i < 180}
        for i in range(200)
    ] + [{"location_cluster": str(i % 30), "usgs_covered": "false"} for i in range(20)]
    result = qualify_outcome_blind_coverage(
        rows,
        usgs_artifact_sha256=SHA,
        crs="EPSG:4326",
        depth_unit="m",
        nodata_policy="uncovered",
    )
    assert result.qualified is False
    assert result.coverage_fraction == pytest.approx(180 / 220)
    assert "usgs_coverage_below_0.95" in result.stop_reason


@pytest.mark.parametrize("value", ["1x", "yes", "no", 2, 0.0, None, "", "1"])
def test_ambiguous_coverage_flag_fails_closed(value: object) -> None:
    rows = [{"location_cluster": "a", "usgs_covered": value}]
    with pytest.raises(ValueError, match="usgs_covered must be"):
        qualify_outcome_blind_coverage(
            rows,
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


def test_absent_coverage_flag_is_not_evidence_of_coverage() -> None:
    with pytest.raises(ValueError, match="missing the usgs_covered flag"):
        qualify_outcome_blind_coverage(
            [{"location_cluster": "a"}],
            usgs_artifact_sha256=SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


@pytest.mark.parametrize(
    ("endpoint", "approved"),
    [
        ("https://www.fema.gov/api/open/v3/NfipClaims", True),
        ("https://fema.gov/api/open/v3/NfipClaims", True),
        ("https://www.fema.gov/api/open/v3/NfipClaims/", True),
        ("https://www.fema.gov:443/api/open/v3/NfipClaims", True),
        ("http://www.fema.gov/api/open/v3/NfipClaims", False),
        ("https://evil.invalid/x/open/v3/NfipClaims", False),
        ("https://www.fema.gov.evil.invalid/api/open/v3/NfipClaims", False),
        ("https://attacker@www.fema.gov/api/open/v3/NfipClaims", False),
        ("https://www.fema.gov:8443/api/open/v3/NfipClaims", False),
        ("https://www.fema.gov/api/open/v3/OtherClaims", False),
        ("https://www.fema.gov/open/v3/NfipClaims", False),
    ],
)
def test_endpoint_origin_must_be_the_approved_fema_api(
    endpoint: str, approved: bool
) -> None:
    """A suffix match would accept any host ending the same way (P1-05)."""
    manifest = DataUseManifest(
        endpoint=endpoint,
        data_version="v3",
        schema_sha256=SHA,
        query_parameters={},
        retrieval_timestamp="now",
        raw_response_sha256=(SHA,),
        terms_archive_sha256=SHA,
        commercial_use_assessment="Permitted",
        assessed_by="Reviewer",
        licence_status="approved",
        retention_policy="90 days",
        access_restrictions="least privilege",
        field_mapping={
            "amountPaidOnBuildingClaim": "buildingClaimPaymentAmount",
            "totalBuildingInsuranceCoverage": "totalBuildingInsuranceCoverage",
        },
    )
    assert manifest.permits_real_provider() is approved
