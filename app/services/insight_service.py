from app.schemas.insights import Insight
from app.schemas.risk import RiskScoreResponse


class InsightService:
    def generate(self, result: RiskScoreResponse) -> list[Insight]:
        insights: list[Insight] = []

        gee = result.gee_features
        ocean = result.ocean_features

        if result.components.industrial >= 65:
            insights.append(
                Insight(
                    category="industrial_activity",
                    severity="high",
                    message="Industrial activity signal is elevated relative to the configured baseline.",
                )
            )

        if result.components.pollution >= 65:
            insights.append(
                Insight(
                    category="pollution",
                    severity="high",
                    message="NO₂ proxy indicates sustained atmospheric pollution pressure in the selected area.",
                )
            )

        if result.components.ocean >= 65:
            insights.append(
                Insight(
                    category="climate_ocean",
                    severity="medium",
                    message=(
                        f"Ocean climate signal shows SST trend of "
                        f"{ocean.sst_trend_c_per_decade:.2f}°C per decade "
                        f"and sea-level trend of {ocean.sea_level_trend_mm_per_year:.2f} mm/year."
                    ),
                )
            )

        if result.overall_score >= 70:
            insights.append(
                Insight(
                    category="overall_risk",
                    severity="high",
                    message="Overall risk score suggests enhanced due diligence is recommended before investment, underwriting, or credit decisioning.",
                )
            )

        if not insights:
            insights.append(
                Insight(
                    category="overall_risk",
                    severity="low",
                    message="No material elevated signal was detected under the current scoring model.",
                )
            )

        return insights
