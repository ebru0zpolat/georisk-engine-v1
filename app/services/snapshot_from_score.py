from __future__ import annotations

from app.core.config import settings
from app.schemas.risk import RiskScoreResponse
from app.geo.interfaces import derive_point_geometry_hash
from app.services.asset_snapshot_store import AssetSnapshot, register_snapshot

DEFAULT_DATA_SNAPSHOT_ID = "hazard_layers_2026_05"


def register_score_snapshot(result: RiskScoreResponse) -> None:
    register_snapshot(
        AssetSnapshot(
            audit_id=result.audit_id,
            asset_name=result.asset_name,
            latitude=result.latitude,
            longitude=result.longitude,
            radius_km=result.radius_km,
            sector=result.sector,
            overall_score=result.overall_score,
            components=result.components.model_dump(),
            model_version=settings.risk_score_model_version,
            data_snapshot_id=DEFAULT_DATA_SNAPSHOT_ID,
            asset_geometry_hash=derive_point_geometry_hash(
                latitude=result.latitude,
                longitude=result.longitude,
            ),
            uses_connector_fallback=True,
        )
    )
