from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CaseModel, CaseTransitionModel
from app.schemas.cases import (
    CaseCreate,
    CaseOut,
    CasePatch,
    CasePriority,
    CaseSeverity,
    CaseStatus,
)


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_cases(
        self, organisation_id: str, status: CaseStatus | None = None
    ) -> list[CaseOut]:
        query = (
            select(CaseModel)
            .where(CaseModel.organisation_id == organisation_id)
            .order_by(CaseModel.created_at.desc())
        )
        if status is not None:
            query = query.where(CaseModel.status == status.value)
        result = await self.session.execute(query)
        return [self._to_out(row) for row in result.scalars()]

    async def get_case(self, organisation_id: str, case_id: str) -> CaseModel | None:
        result = await self.session.execute(
            select(CaseModel).where(
                CaseModel.id == case_id, CaseModel.organisation_id == organisation_id
            )
        )
        return result.scalar_one_or_none()

    async def create_case(self, organisation_id: str, payload: CaseCreate) -> CaseOut:
        now = _now()
        case = CaseModel(
            id=f"case_{uuid4().hex[:12]}",
            organisation_id=organisation_id,
            title=payload.title,
            description=payload.description,
            asset_id=payload.asset_id,
            asset_name=payload.asset_name,
            severity=payload.severity.value,
            priority=payload.priority.value,
            status=CaseStatus.OPEN.value,
            tags=list(payload.tags),
            z_score=payload.z_score,
            anomaly_flag=payload.anomaly_flag,
            created_at=now,
            updated_at=now,
        )
        self.session.add(case)
        await self._record_transition(
            case_id=case.id,
            from_status=None,
            to_status=CaseStatus.OPEN.value,
            note="Case created",
        )
        await self.session.flush()
        return self._to_out(case)

    async def save_case(self, case: CaseModel) -> CaseOut:
        case.updated_at = _now()
        await self.session.flush()
        return self._to_out(case)

    async def record_transition(
        self,
        *,
        case_id: str,
        from_status: CaseStatus | None,
        to_status: CaseStatus,
        note: str | None = None,
        triggered_by: str = "MANUAL",
    ) -> None:
        await self._record_transition(
            case_id=case_id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            note=note,
            triggered_by=triggered_by,
        )

    async def _record_transition(
        self,
        *,
        case_id: str,
        from_status: str | None,
        to_status: str,
        note: str | None = None,
        triggered_by: str = "MANUAL",
    ) -> None:
        self.session.add(
            CaseTransitionModel(
                case_id=case_id,
                from_status=from_status,
                to_status=to_status,
                triggered_by=triggered_by,
                note=note,
            )
        )

    @staticmethod
    def _to_out(case: CaseModel) -> CaseOut:
        return CaseOut(
            id=case.id,
            title=case.title,
            description=case.description,
            asset_id=case.asset_id,
            asset_name=case.asset_name,
            severity=CaseSeverity(case.severity),
            priority=CasePriority(case.priority),
            status=CaseStatus(case.status),
            assigned_to=case.assigned_to,
            tags=list(case.tags or []),
            triage_note=case.triage_note,
            escalation_note=case.escalation_note,
            close_resolution=case.close_resolution,
            z_score=case.z_score,
            anomaly_flag=bool(case.anomaly_flag),
            created_at=case.created_at,
            updated_at=case.updated_at,
            closed_at=case.closed_at,
        )

    async def apply_patch(self, case: CaseModel, payload: CasePatch) -> CaseOut:
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field == "severity" and value is not None:
                case.severity = value.value
            elif field == "priority" and value is not None:
                case.priority = value.value
            elif field == "tags" and value is not None:
                case.tags = list(value)
            else:
                setattr(case, field, value)
        return await self.save_case(case)


def _now() -> datetime:
    return datetime.now(timezone.utc)
