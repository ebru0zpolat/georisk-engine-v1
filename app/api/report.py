from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response

from app.api.deps import require_scopes
from app.reports.pdf_report import build_pdf_report
from app.reports.risk_report import build_markdown_report
from app.reports.tcfd import build_tcfd_report
from app.schemas.risk import RiskReportRequest
from app.services.insight_service import InsightService
from app.services.risk_service import RiskService

router = APIRouter()
service = RiskService()
insight_service = InsightService()


@router.post(
    "/reports/risk",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_scopes("reports:write"))],
)
def generate_risk_report(payload: RiskReportRequest) -> str:
    result = service.score(payload)
    return build_markdown_report(result)


@router.post(
    "/reports/tcfd",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_scopes("reports:write"))],
)
def generate_tcfd_report(payload: RiskReportRequest) -> str:
    result = service.score(payload)
    return build_tcfd_report(result)


@router.post(
    "/reports/risk/pdf",
    dependencies=[Depends(require_scopes("reports:write"))],
)
def generate_risk_pdf(payload: RiskReportRequest) -> Response:
    result = service.score_location(payload)
    insights = insight_service.generate(result)
    pdf = build_pdf_report(result, insights)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="georisk-report.pdf"'
        },
    )
