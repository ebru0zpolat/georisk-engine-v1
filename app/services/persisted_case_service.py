from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cases import (
    CaseCloseRequest,
    CaseCreate,
    CaseOut,
    CasePatch,
    CaseStatus,
    CaseTransitionRequest,
)
from app.storage.case_repository import CaseRepository


class PersistedCaseService:
    def __init__(self, session: AsyncSession, organisation_id: str) -> None:
        self.repo = CaseRepository(session)
        self.session = session
        self.organisation_id = organisation_id

    async def list_cases(self, status: CaseStatus | None = None) -> list[CaseOut]:
        return await self.repo.list_cases(self.organisation_id, status=status)

    async def create_case(self, payload: CaseCreate) -> CaseOut:
        case = await self.repo.create_case(self.organisation_id, payload)
        await self.session.commit()
        return case

    async def get_case(self, case_id: str) -> CaseOut:
        case = await self.repo.get_case(self.organisation_id, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"Unknown case_id: {case_id}")
        return self.repo._to_out(case)

    async def patch_case(self, case_id: str, payload: CasePatch) -> CaseOut:
        case = await self._get_model(case_id)
        if case.status == CaseStatus.CLOSED.value:
            raise HTTPException(status_code=409, detail="Closed cases cannot be modified")

        if not payload.model_dump(exclude_unset=True):
            return self.repo._to_out(case)

        updated = await self.repo.apply_patch(case, payload)
        await self.session.commit()
        return updated

    async def triage_case(self, case_id: str, payload: CaseTransitionRequest) -> CaseOut:
        case = await self._get_model(case_id)
        self._require_status(case, {CaseStatus.OPEN}, "triage")
        case.status = CaseStatus.TRIAGED.value
        case.triage_note = payload.note
        if payload.assigned_to is not None:
            case.assigned_to = payload.assigned_to
        await self.repo.record_transition(
            case_id=case.id,
            from_status=CaseStatus.OPEN,
            to_status=CaseStatus.TRIAGED,
            note=payload.note,
        )
        updated = await self.repo.save_case(case)
        await self.session.commit()
        return updated

    async def escalate_case(self, case_id: str, payload: CaseTransitionRequest) -> CaseOut:
        case = await self._get_model(case_id)
        self._require_status(case, {CaseStatus.TRIAGED}, "escalate")
        case.status = CaseStatus.ESCALATED.value
        case.escalation_note = payload.note
        if payload.assigned_to is not None:
            case.assigned_to = payload.assigned_to
        await self.repo.record_transition(
            case_id=case.id,
            from_status=CaseStatus.TRIAGED,
            to_status=CaseStatus.ESCALATED,
            note=payload.note,
        )
        updated = await self.repo.save_case(case)
        await self.session.commit()
        return updated

    async def close_case(self, case_id: str, payload: CaseCloseRequest) -> CaseOut:
        case = await self._get_model(case_id)
        self._require_status(
            case,
            {CaseStatus.OPEN, CaseStatus.TRIAGED, CaseStatus.ESCALATED},
            "close",
        )
        previous = CaseStatus(case.status)
        case.status = CaseStatus.CLOSED.value
        case.close_resolution = payload.resolution
        case.closed_at = _now()
        await self.repo.record_transition(
            case_id=case.id,
            from_status=previous,
            to_status=CaseStatus.CLOSED,
            note=payload.resolution,
        )
        updated = await self.repo.save_case(case)
        await self.session.commit()
        return updated

    async def _get_model(self, case_id: str):
        case = await self.repo.get_case(self.organisation_id, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"Unknown case_id: {case_id}")
        return case

    @staticmethod
    def _require_status(case, allowed: set[CaseStatus], action: str) -> None:
        current = CaseStatus(case.status)
        if current not in allowed:
            allowed_values = ", ".join(sorted(status.value for status in allowed))
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot {action} case {case.id} from status {current.value}; "
                    f"allowed status: {allowed_values}"
                ),
            )


def _now() -> datetime:
    return datetime.now(timezone.utc)
