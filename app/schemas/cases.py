from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


NonEmptyStr = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(min_length=1, max_length=2000)]


class CaseStatus(str, Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    ESCALATED = "escalated"
    CLOSED = "closed"


class CaseSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CasePriority(str, Enum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


class CaseCreate(BaseModel):
    title: NonEmptyStr
    description: LongText | None = None
    asset_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    asset_name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    severity: CaseSeverity = CaseSeverity.MEDIUM
    priority: CasePriority = CasePriority.P3
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list)
    z_score: float | None = None
    anomaly_flag: bool = False

    @model_validator(mode="after")
    def require_asset_reference(self) -> "CaseCreate":
        if self.asset_id is None and self.asset_name is None:
            raise ValueError("Either asset_id or asset_name must be provided")
        return self


class CasePatch(BaseModel):
    title: NonEmptyStr | None = None
    description: LongText | None = None
    severity: CaseSeverity | None = None
    priority: CasePriority | None = None
    assigned_to: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] | None = None


class CaseTransitionRequest(BaseModel):
    note: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    assigned_to: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class CaseCloseRequest(BaseModel):
    resolution: Annotated[str, Field(min_length=1, max_length=1000)]


class CaseOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    asset_id: str | None = None
    asset_name: str | None = None
    severity: CaseSeverity
    priority: CasePriority
    status: CaseStatus
    assigned_to: str | None = None
    tags: list[str]
    triage_note: str | None = None
    escalation_note: str | None = None
    close_resolution: str | None = None
    z_score: float | None = None
    anomaly_flag: bool = False
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class CaseListResponse(BaseModel):
    cases: list[CaseOut]
    count: int
