from datetime import datetime

from pydantic import BaseModel


class CaseEvent(BaseModel):
    timestamp: datetime
    status: str
    trigger_type: str
    description: str


class Case(BaseModel):
    id: str
    asset_id: str
    title: str
    status: str
    severity: str
    trigger_type: str
    created_at: datetime
    updated_at: datetime
    events: list[CaseEvent]


class CaseListResponse(BaseModel):
    asset_id: str
    open_count: int
    cases: list[Case]
