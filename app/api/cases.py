from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, require_scopes
from app.core.security import Principal
from app.db.session import get_db
from app.schemas.cases import (
    CaseCloseRequest,
    CaseCreate,
    CaseListResponse as PersistedCaseListResponse,
    CaseOut,
    CasePatch,
    CaseStatus,
    CaseTransitionRequest,
)
from app.services.demo_service import DemoService
from app.services.persisted_case_service import PersistedCaseService
from app.services.snapshot_case_service import SnapshotCaseService

router = APIRouter()
demo_service = DemoService()
snapshot_case_service = SnapshotCaseService()


def get_persisted_case_service(
    session: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> PersistedCaseService:
    return PersistedCaseService(session, principal.organisation_id)


@router.get("/cases")
async def list_cases(
    asset_id: str | None = None,
    status: CaseStatus | None = None,
    service: PersistedCaseService = Depends(get_persisted_case_service),
):
    """Snapshot derive-on-read when ``asset_id`` is set; otherwise list persisted cases."""
    if asset_id is not None:
        asset = demo_service.get_preset_asset(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Unknown asset_id: {asset_id}")

        payload = demo_service.build_request_from_preset(asset)
        result = demo_service.risk_service.score_location(payload)
        return snapshot_case_service.list_cases_for_result(asset_id, result)

    cases = await service.list_cases(status=status)
    return PersistedCaseListResponse(cases=cases, count=len(cases))


@router.post(
    "/cases",
    response_model=CaseOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("cases:write"))],
)
async def create_case(
    payload: CaseCreate,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.create_case(payload)


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: str,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.get_case(case_id)


@router.patch(
    "/cases/{case_id}",
    response_model=CaseOut,
    dependencies=[Depends(require_scopes("cases:write"))],
)
async def patch_case(
    case_id: str,
    payload: CasePatch,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.patch_case(case_id, payload)


@router.patch(
    "/cases/{case_id}/triage",
    response_model=CaseOut,
    dependencies=[Depends(require_scopes("cases:write"))],
)
async def triage_case(
    case_id: str,
    payload: CaseTransitionRequest,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.triage_case(case_id, payload)


@router.patch(
    "/cases/{case_id}/escalate",
    response_model=CaseOut,
    dependencies=[Depends(require_scopes("cases:write"))],
)
async def escalate_case(
    case_id: str,
    payload: CaseTransitionRequest,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.escalate_case(case_id, payload)


@router.patch(
    "/cases/{case_id}/close",
    response_model=CaseOut,
    dependencies=[Depends(require_scopes("cases:write"))],
)
async def close_case(
    case_id: str,
    payload: CaseCloseRequest,
    service: PersistedCaseService = Depends(get_persisted_case_service),
) -> CaseOut:
    return await service.close_case(case_id, payload)
