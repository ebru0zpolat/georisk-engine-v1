"""Validation layer: schema, service, and API tests (Erdemir 2024 fixture)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.main import app
from app.schemas.validation import (
    AMBER_THRESHOLD_PCT,
    RED_THRESHOLD_PCT,
    BenchmarkRequest,
    ValidationFlag,
    ValidationResult,
    ValidationSummary,
    flag_for_divergence,
)
from app.services.validation_service import ValidationService


# --- schema layer ---------------------------------------------------------


def test_flag_for_divergence_thresholds() -> None:
    assert flag_for_divergence(0) is ValidationFlag.GREEN
    assert flag_for_divergence(AMBER_THRESHOLD_PCT) is ValidationFlag.GREEN
    assert flag_for_divergence(-AMBER_THRESHOLD_PCT) is ValidationFlag.GREEN
    assert flag_for_divergence(AMBER_THRESHOLD_PCT + 0.1) is ValidationFlag.AMBER
    assert flag_for_divergence(-RED_THRESHOLD_PCT) is ValidationFlag.AMBER
    assert flag_for_divergence(RED_THRESHOLD_PCT + 0.1) is ValidationFlag.RED


def test_validation_result_accepts_persisted_flag() -> None:
    result = ValidationResult(
        validation_id="X-1",
        reported_metric={
            "field": "scope_1_emissions",
            "value": 100.0,
            "source": "src",
            "assurance": "none",
        },
        georisk_signal={
            "type": "proxy",
            "value": 200.0,
            "source": "src",
            "source_version": "2024.1",
            "confidence": 0.5,
        },
        divergence_pct=4.67,
        flag=ValidationFlag.AMBER,
        explanation="directional inconsistency despite small magnitude",
        georisk_version="0.1.0",
        data_source_version="2024.1",
        generated_at="2025-05-03T09:00:00+00:00",
    )
    assert result.flag is ValidationFlag.AMBER


def test_georisk_signal_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        BenchmarkRequest(company_id="erdemir", reporting_year=1999, sector="steel")


def test_summary_from_results_counts() -> None:
    service = ValidationService()
    report = service.get_report("erdemir", 2024)
    summary = ValidationSummary.from_results(report.results)
    assert summary.total == len(report.results)
    assert (
        summary.flagged_green + summary.flagged_amber + summary.flagged_red
        == summary.total
    )


# --- service / validator layer --------------------------------------------


def test_benchmark_loads_erdemir_fixture() -> None:
    service = ValidationService()
    report = service.benchmark(
        BenchmarkRequest(company_id="erdemir", reporting_year=2024, sector="steel")
    )
    assert report.company_id == "erdemir"
    assert report.reporting_year == 2024
    assert len(report.results) >= 8
    assert report.summary.flagged_amber == 5
    assert report.summary.flagged_green == 5
    assert report.summary.flagged_red == 0


def test_get_report_matches_benchmark() -> None:
    service = ValidationService()
    report = service.get_report("erdemir", 2024)
    assert report.summary.total == len(report.results)
    assert report.results[0].validation_id == "ERD-2024-PROD-001"


def test_get_evidence_returns_single_record() -> None:
    service = ValidationService()
    result = service.get_evidence("ERD-2024-INT-001")
    assert result.validation_id == "ERD-2024-INT-001"
    assert result.flag is ValidationFlag.AMBER
    assert result.reported_metric.source.startswith("Erdemir")


def test_get_report_unknown_company_raises() -> None:
    from app.core.exceptions import GeoRiskApiError

    service = ValidationService()
    with pytest.raises(GeoRiskApiError) as exc:
        service.get_report("unknown", 2024)
    assert exc.value.status_code == 404


def test_get_evidence_unknown_id_raises() -> None:
    from app.core.exceptions import GeoRiskApiError

    service = ValidationService()
    with pytest.raises(GeoRiskApiError) as exc:
        service.get_evidence("DOES-NOT-EXIST")
    assert exc.value.status_code == 404


# --- API layer ------------------------------------------------------------


def test_post_benchmark_erdemir_2024() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/validation/benchmark",
        json={"company_id": "erdemir", "reporting_year": 2024, "sector": "steel"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["flagged_amber"] == 5
    assert data["summary"]["flagged_green"] == 5
    assert len(data["results"]) >= 8


def test_get_benchmark_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/validation/benchmark/erdemir/2024")
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == "erdemir"
    assert "summary" in data


def test_get_evidence_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/validation/evidence/ERD-2024-INT-001")
    assert r.status_code == 200
    data = r.json()
    assert data["validation_id"] == "ERD-2024-INT-001"
    assert data["flag"] == "amber"
    assert data["georisk_signal"]["confidence"] == 0.72


def test_get_evidence_endpoint_404() -> None:
    client = TestClient(app)
    r = client.get("/v1/validation/evidence/NOPE")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "validation_evidence_not_found"


def test_openapi_documents_validation_endpoints() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/v1/validation/benchmark" in paths
    assert "/v1/validation/benchmark/{company_id}/{year}" in paths
    assert "/v1/validation/evidence/{validation_id}" in paths


def test_existing_risk_and_report_endpoints_unaffected() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/v1/risk/score" in spec["paths"]
    assert "/v1/reports/risk" in spec["paths"]
