from __future__ import annotations

import base64
from typing import Any

import httpx

from georisk_mcp.config import GeoRiskMcpSettings


class GeoRiskClientError(Exception):
    """HTTP or API error from GeoRisk Engine."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeoRiskClient:
    """Thin HTTP client for GeoRisk Engine (testable without MCP runtime)."""

    def __init__(
        self,
        settings: GeoRiskMcpSettings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or GeoRiskMcpSettings.from_env()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        if self._settings.api_key:
            return {"X-API-Key": self._settings.api_key}
        return {}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GeoRiskClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _merge_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged = dict(self._headers())
        if headers:
            merged.update(headers)
        return merged

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        detail = response.text[:500] if response.text else response.reason_phrase
        raise GeoRiskClientError(
            f"GeoRisk API {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    def health(self) -> dict[str, Any]:
        response = self._client.get("/health", headers=self._merge_headers())
        self._raise_for_status(response)
        return response.json()

    def score(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/v1/risk/score", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return response.json()

    def batch_score(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/v1/risk/batch", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return response.json()

    def source_evidence(self, source_id: str | None = None) -> dict[str, Any]:
        path = (
            f"/v1/data-sources/{source_id}/validation"
            if source_id
            else "/v1/data-sources/validation"
        )
        response = self._client.get(path, headers=self._merge_headers())
        self._raise_for_status(response)
        return response.json()

    def report_markdown(self, body: dict[str, Any]) -> str:
        response = self._client.post(
            "/v1/reports/risk", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return response.text

    def report_pdf_base64(self, body: dict[str, Any]) -> str:
        response = self._client.post(
            "/v1/reports/risk/pdf", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return base64.b64encode(response.content).decode("ascii")

    def scenario_run(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/v1/scenario/run", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return response.json()

    def preview_scorecard(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/v1/risk/preview", json=body, headers=self._merge_headers()
        )
        self._raise_for_status(response)
        return response.json()

    def list_demos(self) -> list[dict[str, Any]]:
        response = self._client.get("/v1/demo/assets", headers=self._merge_headers())
        self._raise_for_status(response)
        data = response.json()
        if not isinstance(data, list):
            raise GeoRiskClientError("Expected list from /v1/demo/assets")
        return data


def build_score_body(
    *,
    asset_name: str,
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    sector: str = "industrial",
    include_industrial_verification_ref: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    baseline_start_date: str | None = None,
    baseline_end_date: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "asset_name": asset_name,
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "sector": sector,
        "include_industrial_verification_ref": include_industrial_verification_ref,
    }
    if start_date is not None:
        body["start_date"] = start_date
    if end_date is not None:
        body["end_date"] = end_date
    if baseline_start_date is not None:
        body["baseline_start_date"] = baseline_start_date
    if baseline_end_date is not None:
        body["baseline_end_date"] = baseline_end_date
    return body


def build_batch_score_body(
    *,
    assets: list[dict[str, Any]],
    preset_id: str = "industrial_v1",
    sector: str = "industrial",
    radius_km: float = 10.0,
    valuation_date: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "preset_id": preset_id,
        "assets": assets,
        "sector": sector,
        "radius_km": radius_km,
        "include_industrial_verification_ref": False,
    }
    if valuation_date is not None:
        body["valuation_date"] = valuation_date
    return body


def build_scenario_run_body(
    *,
    asset_id: str,
    pathway: str = "SSP5-8.5",
    target_year: int = 2050,
    hazards: list[str] | None = None,
    return_period: list[int] | None = None,
    spatial_resolution: str = "100m",
    client_context: str | None = None,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "asset_id": asset_id,
        "scenario_config": {
            "model": "CMIP6",
            "pathway": pathway,
            "target_year": target_year,
            "hazards": hazards or ["flood", "drought", "wildfire"],
        },
        "parameters": {
            "return_period": return_period or [10, 50, 100],
            "spatial_resolution": spatial_resolution,
        },
        "metadata": {},
    }
    if client_context:
        body["metadata"]["client_context"] = client_context
    if workflow_id:
        body["metadata"]["workflow_id"] = workflow_id
    return body


def build_preview_body(
    *,
    location: str,
    asset_name: str | None = None,
    radius_km: float = 10.0,
    sector: str = "industrial",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "location": location,
        "radius_km": radius_km,
        "sector": sector,
    }
    if asset_name is not None:
        body["asset_name"] = asset_name
    return body


def build_report_body(
    *,
    asset_name: str,
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    sector: str = "industrial",
    include_industrial_verification_ref: bool = True,
    start_date: str | None = None,
    end_date: str | None = None,
    baseline_start_date: str | None = None,
    baseline_end_date: str | None = None,
) -> dict[str, Any]:
    return build_score_body(
        asset_name=asset_name,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        sector=sector,
        include_industrial_verification_ref=include_industrial_verification_ref,
        start_date=start_date,
        end_date=end_date,
        baseline_start_date=baseline_start_date,
        baseline_end_date=baseline_end_date,
    )
