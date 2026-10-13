"""Build ``RiskScoreRequest`` from GET ``/v1/risk/score`` query parameters."""

from __future__ import annotations

from app.core.preset_registry import DEFAULT_PRESET_ID
from app.core.sector_registry import DEFAULT_SECTOR_ID
from app.schemas.risk import RiskScoreRequest


def risk_score_request_from_get(
    *,
    lat: float,
    lon: float,
    preset_id: str = DEFAULT_PRESET_ID,
    asset_name: str = "asset",
    sector: str = DEFAULT_SECTOR_ID,
    radius_km: float = 10.0,
    include_industrial_verification_ref: bool = False,
) -> RiskScoreRequest:
    return RiskScoreRequest(
        asset_name=asset_name,
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
        preset_id=preset_id,
        sector=sector,
        include_industrial_verification_ref=include_industrial_verification_ref,
    )
