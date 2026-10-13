from __future__ import annotations

from app.schemas.preview import (
    PreviewRiskScoreRequest,
    PreviewRiskScorecard,
    ScorecardComponent,
)
from app.schemas.risk import RiskScoreRequest
from app.services.demo_service import DemoService
from app.services.location_resolver import LocationResolver
from app.services.risk_service import RiskService

INDICATIVE_DISCLAIMER = (
    "Indicative climate risk score from satellite and climate proxies. "
    "Not investment advice, underwriting binding, or regulatory proof. "
    "Use /v1/reports/risk for a fuller due-diligence narrative."
)

_COMPONENT_LABELS: dict[str, str] = {
    "industrial": "Industrial activity",
    "pollution": "Pollution proxy",
    "land": "Land transformation",
    "ocean": "Ocean / climate stress",
    "agriculture": "Agriculture surface",
    "sensitivity": "Environmental sensitivity",
    "flood": "Flood hazard",
    "heat": "Heat hazard",
}


class PreviewRiskService:
    def __init__(
        self,
        resolver: LocationResolver | None = None,
        risk: RiskService | None = None,
        demo: DemoService | None = None,
    ) -> None:
        self._resolver = resolver or LocationResolver()
        self._risk = risk or RiskService()
        self._demo = demo or DemoService()

    def compute_preview_risk_score(self, body: PreviewRiskScoreRequest) -> PreviewRiskScorecard:
        resolved = self._resolver.resolve(
            body.location,
            asset_name=body.asset_name,
            radius_km=body.radius_km,
            sector=body.sector,
        )
        score_request = RiskScoreRequest(
            asset_name=resolved.asset_name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
            radius_km=resolved.radius_km,
            sector=resolved.sector,
            include_industrial_verification_ref=False,
        )
        if resolved.resolution_method == "demo_asset" and resolved.resolution_detail:
            preset = self._demo.get_preset_asset(resolved.resolution_detail)
            if preset:
                score_request = self._demo.build_request_from_preset(preset)
                score_request = score_request.model_copy(
                    update={"include_industrial_verification_ref": False}
                )

        result = self._risk.score(score_request)
        components = [
            ScorecardComponent(
                id=name,
                label=_COMPONENT_LABELS.get(name, name.replace("_", " ").title()),
                score=getattr(result.components, name),
            )
            for name in result.components.model_fields
        ]
        headline = self._demo._headline(result.risk_band, result.flags)

        return PreviewRiskScorecard(
            indicative_climate_risk_score=result.overall_score,
            risk_band=result.risk_band,
            headline=headline,
            location_input=body.location.strip(),
            resolved=resolved,
            components=components,
            top_flags=result.flags[:5],
            interpretation=result.interpretation,
            disclaimer=INDICATIVE_DISCLAIMER,
            audit_id=result.audit_id,
            generated_at=result.generated_at,
        )
