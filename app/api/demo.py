from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import require_scopes
from app.reports.pdf_report import build_pdf_report
from app.schemas.demo import DemoAssetOut, DemoResponse
from app.schemas.risk import RiskScoreRequest
from app.services.demo_service import DemoService
from app.services.insight_service import InsightService
from app.services.risk_service import RiskService

router = APIRouter()
service = DemoService()
risk_service = RiskService()
insight_service = InsightService()


@router.get("/demo/assets", response_model=list[DemoAssetOut])
def list_demo_assets() -> list[DemoAssetOut]:
    return service.list_preset_assets()


@router.get("/demo/run/pdf")
def run_demo_pdf(asset_id: str) -> Response:
    asset = service.get_preset_asset(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo asset_id: {asset_id}",
        )

    payload = service.build_request_from_preset(asset)
    result = risk_service.score_location(payload)
    insights = insight_service.generate(result)
    pdf = build_pdf_report(result, insights)

    safe_name = (
        asset["name"]
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("_", "-")
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="georisk-demo-{safe_name}.pdf"'
        },
    )


@router.get("/demo/run", response_model=DemoResponse)
def run_demo(asset_id: str) -> DemoResponse:
    try:
        return service.run_preset_demo(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/demo",
    response_model=DemoResponse,
    dependencies=[Depends(require_scopes("demo:write"))],
)
def generate_demo(payload: RiskScoreRequest) -> DemoResponse:
    return service.generate_demo(payload)


@router.post(
    "/demo/bundle",
    dependencies=[Depends(require_scopes("demo:write"))],
)
def generate_demo_bundle(payload: RiskScoreRequest) -> Response:
    result = risk_service.score_location(payload)
    insights = insight_service.generate(result)
    pdf = build_pdf_report(result, insights)

    safe_name = (
        payload.asset_name.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("_", "-")
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="georisk-demo-{safe_name}.pdf"'
        },
    )
