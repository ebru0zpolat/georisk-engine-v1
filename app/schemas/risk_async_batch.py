"""Phase 2 PoC: async batch acceptance + task status (in-memory Scalability Engine skeleton)."""

from __future__ import annotations

from typing import Literal

from pydantic import AnyUrl, BaseModel, Field, model_validator

from app.core.preset_registry import is_preset_registered
from app.core.sector_registry import DEFAULT_SECTOR_ID
from app.schemas.risk import RiskBatchAsset, RiskBatchResponse


class RiskBatchAsyncRequest(BaseModel):
    """Enqueue a large batch; PoC executes in-process chunks (500 rows) behind ``task_id``."""

    preset_id: str = Field(..., min_length=1)
    assets: list[RiskBatchAsset] = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Up to **5000** assets per PoC request (chunked into sync batches of 500).",
    )
    sector: str = Field(default=DEFAULT_SECTOR_ID)
    radius_km: float = Field(default=10, gt=0, le=100)
    include_industrial_verification_ref: bool = Field(default=False)
    callback_url: AnyUrl | None = Field(
        default=None,
        description="Optional webhook; on COMPLETED the engine POSTs ``RiskBatchResponse`` JSON.",
    )

    @model_validator(mode="after")
    def preset_ok(self) -> RiskBatchAsyncRequest:
        if not is_preset_registered(self.preset_id):
            raise ValueError("Unknown preset_id")
        return self


class RiskBatchAsyncAcceptedResponse(BaseModel):
    task_id: str
    status_path: str = Field(
        ...,
        description="Relative URL for GET status polling (same host and ``/v1`` prefix).",
    )
    message: str = Field(default="accepted")


AsyncBatchTaskStatusLiteral = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


class AsyncBatchFailedAsset(BaseModel):
    asset_id: str
    code: str
    message: str


class RiskBatchAsyncTaskStatusResponse(BaseModel):
    task_id: str
    status: AsyncBatchTaskStatusLiteral
    progress_processed: int = Field(..., ge=0)
    progress_total: int = Field(..., ge=0)
    optimization_note: str = Field(
        default=(
            "Worker chunks assets into batches of 500 with spatial-cell coalesced bulk GEE/ORAS5 fetches; "
            "with REDIS_URL configured the batch runs on Celery workers over Redis, otherwise in-process."
        ),
    )
    callback_url: str | None = None
    download_url: str | None = None
    failed_assets: list[AsyncBatchFailedAsset] = Field(default_factory=list)
    result: RiskBatchResponse | None = None
    error_message: str | None = None
