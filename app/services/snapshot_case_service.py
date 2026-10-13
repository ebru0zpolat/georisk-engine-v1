from datetime import timedelta

from app.schemas.case import Case, CaseEvent, CaseListResponse
from app.schemas.risk import RiskScoreResponse

FLAG_TITLES = {
    "elevated_industrial": "Elevated industrial activity anomaly",
    "elevated_pollution": "NO2 emission anomaly detected",
    "elevated_ocean": "Sea level / SST anomaly detected",
    "elevated_land": "Land surface change detected",
    "elevated_agriculture": "Agriculture signal anomaly",
    "elevated_sensitivity": "Sensitivity threshold exceeded",
}


class SnapshotCaseService:
    """Derives case records and audit-log timelines from a risk assessment result."""

    def list_cases_for_result(self, asset_id: str, result: RiskScoreResponse) -> CaseListResponse:
        cases: list[Case] = []

        for index, flag in enumerate(result.flags):
            title = FLAG_TITLES.get(flag, flag.replace("_", " ").title())
            created_at = result.generated_at - timedelta(days=index + 1)
            opened_at = created_at
            reviewed_at = created_at + timedelta(hours=6)
            updated_at = reviewed_at if result.risk_band in {"low", "medium"} else opened_at

            status = "open" if result.risk_band in {"high", "critical"} else "closed"
            severity = (
                "critical"
                if result.risk_band == "critical"
                else "elevated"
                if result.risk_band == "high"
                else "normal"
            )

            events = [
                CaseEvent(
                    timestamp=opened_at,
                    status="opened",
                    trigger_type="AUTO",
                    description=f"{title} — case opened from automated risk assessment.",
                ),
                CaseEvent(
                    timestamp=reviewed_at,
                    status="under_review" if status == "open" else "closed",
                    trigger_type="AUTO" if status == "open" else "MANUAL",
                    description="Reviewed against latest satellite baseline."
                    if status == "open"
                    else "Resolved — signal returned within normal range.",
                ),
            ]

            cases.append(
                Case(
                    id=f"{asset_id}-case-{index + 1}",
                    asset_id=asset_id,
                    title=title,
                    status=status,
                    severity=severity,
                    trigger_type="AUTO",
                    created_at=created_at,
                    updated_at=updated_at,
                    events=events,
                )
            )

        open_count = sum(1 for case in cases if case.status == "open")
        return CaseListResponse(asset_id=asset_id, open_count=open_count, cases=cases)
