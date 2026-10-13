"""Tests for GeoRisk MCP HTTP client (no MCP runtime required)."""

from __future__ import annotations

import httpx
import pytest

from georisk_mcp.client import (
    GeoRiskClient,
    GeoRiskClientError,
    build_preview_body,
    build_report_body,
    build_scenario_run_body,
    build_score_body,
)
from georisk_mcp.config import GeoRiskMcpSettings


def test_build_scenario_run_body() -> None:
    body = build_scenario_run_body(
        asset_id="00000000-0000-4000-8000-000000000001",
        workflow_id="deerflow-skill-exec-001",
    )
    assert body["scenario_config"]["model"] == "CMIP6"
    assert body["metadata"]["workflow_id"] == "deerflow-skill-exec-001"


def test_scenario_run_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/scenario/run"
        return httpx.Response(
            200,
            json={
                "scenario_id": "scen_8842_x",
                "status": "completed",
                "hazard_results": {
                    "flood": {
                        "severity_index": 0.72,
                        "affected_fraction": 0.15,
                        "return_periods": {"10y": 0.4, "50y": 0.65, "100y": 0.85},
                    }
                },
                "shocks": {
                    "correlated_events": ["supply_chain_disruption"],
                    "systemic_risk_score": 0.64,
                },
                "propagation": {
                    "node": "facility_a",
                    "impact_path": [
                        {"tier": "direct", "target": "production_capacity", "loss": 0.2}
                    ],
                },
                "scenario_scoring": {
                    "asset_id": "00000000-0000-4000-8000-000000000001",
                    "asset_geometry_hash": "abc",
                    "model_version": "v1.0.3",
                    "data_snapshot_id": "hazard_layers_2026_05",
                    "coefficient_table_version": "scenario_coefficients_v1.0",
                    "coefficient_table_hash": "9" * 64,
                    "baseline_score": 60,
                    "scenario": "SSP5-8.5",
                    "horizon": 2050,
                    "hazard_score": 60,
                    "exposure_score": 60,
                    "vulnerability_score": 60,
                    "hazard_multiplier": 1.3,
                    "hazard_multiplier_type": "weighted_effective",
                    "hazard_driver_multipliers": {"pluvial_flood": 1.3},
                    "raw_adjusted_hazard": 78.0,
                    "adjusted_hazard_score": 78,
                    "raw_scenario_score": 70.9,
                    "scenario_score": 70,
                    "scenario_delta_points": 10,
                    "scenario_delta_pct": 16.7,
                    "scenario_delta_cap_applied": False,
                    "confidence": "medium",
                    "confidence_reasons": ["full_component_vector"],
                    "drivers": ["pluvial_flood"],
                },
                "audit_context": {
                    "linked_audit_ids": ["AUD-2026-001"],
                    "disclaimer": "v1 Deterministic Engine",
                },
            },
        )

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        data = client.scenario_run(
            build_scenario_run_body(asset_id="00000000-0000-4000-8000-000000000001")
        )
    assert data["status"] == "completed"
    assert data["hazard_results"]["flood"]["severity_index"] == 0.72


def test_build_preview_body() -> None:
    body = build_preview_body(location="36.85, 30.75")
    assert body["location"] == "36.85, 30.75"
    assert body["radius_km"] == 10.0


def test_preview_scorecard_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/risk/preview"
        return httpx.Response(
            200,
            json={
                "indicative_climate_risk_score": 55,
                "risk_band": "moderate",
                "headline": "ok",
                "location_input": "x",
                "resolved": {
                    "latitude": 36.0,
                    "longitude": 30.0,
                    "radius_km": 10,
                    "asset_name": "A",
                    "sector": "industrial",
                    "resolution_method": "coordinates",
                },
                "components": [],
                "top_flags": [],
                "interpretation": "ok",
                "disclaimer": "indicative",
                "audit_id": "a1",
                "generated_at": "2026-05-17T00:00:00Z",
            },
        )

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        data = client.preview_scorecard(build_preview_body(location="36,30"))
    assert data["indicative_climate_risk_score"] == 55


def test_build_score_body_defaults() -> None:
    body = build_score_body(
        asset_name="Test",
        latitude=39.0,
        longitude=32.0,
    )
    assert body["include_industrial_verification_ref"] is False
    assert body["radius_km"] == 10.0
    assert body["sector"] == "industrial"


def test_build_report_body_industrial_on() -> None:
    body = build_report_body(
        asset_name="Test",
        latitude=39.0,
        longitude=32.0,
    )
    assert body["include_industrial_verification_ref"] is True


def test_health_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(
        base_url="http://test", timeout_seconds=5.0, api_key="secret", compress_tool_outputs=False
    )
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        data = client.health()
    assert data["status"] == "ok"


def test_score_sends_api_key_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["api_key"] = request.headers.get("X-API-Key", "")
        assert request.url.path == "/v1/risk/score"
        return httpx.Response(
            200,
            json={
                "asset_name": "X",
                "latitude": 39.0,
                "longitude": 32.0,
                "radius_km": 10,
                "sector": "industrial",
                "overall_score": 50,
                "risk_band": "moderate",
                "components": {
                    "industrial": 50,
                    "pollution": 50,
                    "land": 50,
                    "ocean": 50,
                    "agriculture": 50,
                    "sensitivity": 50,
                },
                "ocean_features": {},
                "gee_features": {},
                "flags": [],
                "interpretation": "ok",
                "audit_id": "aud-1",
                "generated_at": "2026-05-17T00:00:00Z",
            },
        )

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(
        base_url="http://test", timeout_seconds=5.0, api_key="secret", compress_tool_outputs=False
    )
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        body = build_score_body(asset_name="X", latitude=39.0, longitude=32.0)
        result = client.score(body)
    assert seen["api_key"] == "secret"
    assert result["audit_id"] == "aud-1"


def test_report_markdown_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/reports/risk"
        return httpx.Response(200, text="# Report\n\nBody")

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        text = client.report_markdown(
            build_report_body(asset_name="X", latitude=1.0, longitude=2.0)
        )
    assert "Report" in text


def test_report_pdf_base64() -> None:
    pdf_bytes = b"%PDF-1.4 fake"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/reports/risk/pdf"
        return httpx.Response(200, content=pdf_bytes)

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        b64 = client.report_pdf_base64(
            build_report_body(asset_name="X", latitude=1.0, longitude=2.0)
        )
    import base64

    assert base64.b64decode(b64) == pdf_bytes


def test_list_demos_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/demo/assets"
        return httpx.Response(200, json=[{"id": "demo1", "name": "Demo"}])

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        demos = client.list_demos()
    assert demos[0]["id"] == "demo1"


def test_client_error_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    settings = GeoRiskMcpSettings(base_url="http://test", timeout_seconds=5.0, api_key=None, compress_tool_outputs=False)
    with httpx.Client(transport=transport, base_url=settings.base_url) as http:
        client = GeoRiskClient(settings, client=http)
        with pytest.raises(GeoRiskClientError) as exc:
            client.health()
    assert exc.value.status_code == 404


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEORISK_BASE_URL", "http://example:9000/")
    monkeypatch.setenv("GEORISK_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("GEORISK_API_KEY", "k")
    s = GeoRiskMcpSettings.from_env()
    assert s.base_url == "http://example:9000"
    assert s.timeout_seconds == 30.0
    assert s.api_key == "k"
    assert s.compress_tool_outputs is False
