from datetime import date
from uuid import uuid4

from app.core.config import settings
from app.core.preset_registry import DEFAULT_PRESET_ID
from app.core.sector_registry import (
    AGRICULTURE_SECTOR_ID,
    DEFAULT_SECTOR_ID,
    IRON_STEEL_SECTOR_ID,
)
from app.schemas.demo import (
    DemoAsset,
    DemoAudit,
    DemoBaselines,
    DemoFeatures,
    DemoReport,
    DemoResponse,
    DemoSummary,
)
from app.schemas.risk import RiskScoreRequest
from app.services.insight_service import InsightService
from app.services.risk_service import RiskService


class DemoService:
    def __init__(
        self,
        risk_service: RiskService | None = None,
        insight_service: InsightService | None = None,
    ) -> None:
        self.risk_service = risk_service or RiskService()
        self.insight_service = insight_service or InsightService()

    def list_preset_assets(self) -> list[dict]:
        return [
            {
                "id": "coastal_industrial_med",
                "name": "Demo Coastal Industrial Facility",
                "sector": DEFAULT_SECTOR_ID,
                "latitude": 36.85,
                "longitude": 30.75,
                "radius_km": 10,
                "start_date": date(2023, 1, 1),
                "end_date": date(2024, 1, 1),
            },
            {
                "id": "anatolia_large_scale_crop",
                "name": "Demo — Büyük ölçekli tarla (İç Anadolu)",
                "sector": AGRICULTURE_SECTOR_ID,
                "latitude": 38.22,
                "longitude": 32.48,
                "radius_km": 10,
                "start_date": date(2023, 1, 1),
                "end_date": date(2024, 1, 1),
            },
            {
                "id": "thrace_grain_storage_processing",
                "name": "Demo — Tahıl silosu / işleme hattı (Trakya)",
                "sector": AGRICULTURE_SECTOR_ID,
                "latitude": 41.62,
                "longitude": 26.58,
                "radius_km": 10,
                "start_date": date(2023, 1, 1),
                "end_date": date(2024, 1, 1),
            },
            {
                "id": "marmara_integrated_steel_mill",
                "name": "Demo — Entegre demir-çelik tesisi (Marmara)",
                "sector": IRON_STEEL_SECTOR_ID,
                "preset_id": "iron_steel_v1",
                "latitude": 41.28,
                "longitude": 36.33,
                "radius_km": 12,
                "start_date": date(2023, 1, 1),
                "end_date": date(2024, 1, 1),
            },
        ]

    @staticmethod
    def build_request_from_preset(asset: dict) -> RiskScoreRequest:
        return RiskScoreRequest(
            asset_name=asset["name"],
            sector=asset["sector"],
            preset_id=asset.get("preset_id", DEFAULT_PRESET_ID),
            latitude=asset["latitude"],
            longitude=asset["longitude"],
            radius_km=asset["radius_km"],
            start_date=asset.get("start_date"),
            end_date=asset.get("end_date"),
            include_industrial_verification_ref=True,
        )

    def get_preset_asset(self, asset_id: str) -> dict | None:
        for asset in self.list_preset_assets():
            if asset["id"] == asset_id:
                return asset
        return None

    def run_preset_demo(self, asset_id: str) -> DemoResponse:
        asset = self.get_preset_asset(asset_id)

        if asset is None:
            raise ValueError(f"Unknown demo asset_id: {asset_id}")

        payload = self.build_request_from_preset(asset)

        return self.generate_demo(payload)

    def generate_demo(self, payload: RiskScoreRequest) -> DemoResponse:
        result = self.risk_service.score_location(payload)

        return DemoResponse(
            demo_id=str(uuid4()),
            asset=DemoAsset(
                name=result.asset_name,
                sector=result.sector,
                latitude=result.latitude,
                longitude=result.longitude,
                radius_km=result.radius_km,
            ),
            summary=DemoSummary(
                overall_score=result.overall_score,
                risk_band=result.risk_band,
                headline=self._headline(result.risk_band, result.flags),
            ),
            components=result.components,
            features=DemoFeatures(
                gee=result.gee_features,
                oras5=result.ocean_features.model_dump(),
            ),
            baselines=DemoBaselines(
                gee=result.gee_baseline,
            ),
            flags=result.flags,
            interpretation=result.interpretation,
            insights=self.insight_service.generate(result),
            report=DemoReport(
                available=True,
                pdf_endpoint="/v1/reports/risk/pdf",
                bundle_endpoint="/v1/demo/bundle",
            ),
            audit=DemoAudit(
                audit_id=result.audit_id,
                generated_at=result.generated_at,
                model_version=settings.risk_score_model_version,
            ),
            industrial_verification=result.industrial_verification,
            emission_zscore=result.emission_zscore,
            anomaly_flag=result.anomaly_flag,
            coastal_exposure_score=result.coastal_exposure_score,
            data_mode=result.data_mode,
            production_eligible=result.production_eligible,
        )

    @staticmethod
    def _headline(risk_band: str, flags: list[str]) -> str:
        if not flags:
            return f"{risk_band.title()} overall risk with no major component-level red flags."

        if risk_band in {"high", "critical"}:
            return f"{risk_band.title()} risk driven by {', '.join(flags[:2])}."

        return f"{risk_band.title()} risk with monitored signals: {', '.join(flags[:2])}."
