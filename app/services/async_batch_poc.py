"""In-memory async batch PoC: 202 + status polling; chunked sync scoring."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

from app.core.security import DEFAULT_ORGANISATION_ID
from app.schemas.risk import RiskBatchRequest, RiskBatchResponse
from app.schemas.risk_async_batch import AsyncBatchFailedAsset, RiskBatchAsyncRequest
from app.services.risk_batch_pipeline import merge_risk_batch_chunk_responses
from app.services.risk_service import RiskService

logger = logging.getLogger(__name__)

ASYNC_BATCH_CHUNK_SIZE = 500


@dataclass
class _TaskRecord:
    status: str
    progress_processed: int
    progress_total: int
    callback_url: str | None = None
    organisation_id: str = DEFAULT_ORGANISATION_ID
    result: RiskBatchResponse | None = None
    failed_assets: list[AsyncBatchFailedAsset] = field(default_factory=list)
    error_message: str | None = None


class AsyncBatchTaskStore:
    """Thread-safe PoC store (replace with Redis/DB for production Phase 2)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, _TaskRecord] = {}

    def create_pending(
        self,
        *,
        total: int,
        callback_url: str | None,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
    ) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = _TaskRecord(
                status="PENDING",
                progress_processed=0,
                progress_total=total,
                callback_url=callback_url,
                organisation_id=organisation_id,
            )
        return task_id

    def get(self, task_id: str) -> _TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def mark_processing(self, task_id: str) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = "PROCESSING"

    def update_progress(self, task_id: str, processed: int) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].progress_processed = processed

    def complete(
        self,
        task_id: str,
        result: RiskBatchResponse,
        failed_assets: list[AsyncBatchFailedAsset],
    ) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return
            t = self._tasks[task_id]
            t.status = "COMPLETED"
            t.result = result
            t.failed_assets = failed_assets
            t.progress_processed = t.progress_total

    def fail(self, task_id: str, message: str) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return
            t = self._tasks[task_id]
            t.status = "FAILED"
            t.error_message = message

    def clear_for_tests(self) -> None:
        with self._lock:
            self._tasks.clear()


async_batch_task_store = AsyncBatchTaskStore()


def _fire_callback(url: str, merged: RiskBatchResponse) -> None:
    data = json.dumps(merged.model_dump(mode="json")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        logger.warning("callback_url POST failed for async batch", exc_info=True)


def run_async_batch_poc_task(
    task_id: str,
    body: RiskBatchAsyncRequest,
    *,
    risk_service: RiskService | None = None,
) -> None:
    """Background entry: chunk → ``RiskBatchRequest`` (≤500) → merge → optional callback.

    Runs against the configured task store (Redis when ``REDIS_URL`` is set,
    in-memory otherwise), so the same pipeline serves both the BackgroundTasks
    PoC path and Celery workers.
    """
    from app.services.async_batch_store import get_async_batch_task_store

    store = get_async_batch_task_store()
    store.mark_processing(task_id)
    svc = risk_service or RiskService()
    chunks_out: list[RiskBatchResponse] = []
    try:
        assets = body.assets
        total = len(assets)
        processed = 0
        for i in range(0, total, ASYNC_BATCH_CHUNK_SIZE):
            chunk = assets[i : i + ASYNC_BATCH_CHUNK_SIZE]
            sync_req = RiskBatchRequest(
                preset_id=body.preset_id,
                assets=chunk,
                sector=body.sector,
                radius_km=body.radius_km,
                include_industrial_verification_ref=body.include_industrial_verification_ref,
            )
            chunks_out.append(svc.batch_score(sync_req))
            processed = min(total, i + len(chunk))
            store.update_progress(task_id, processed)

        merged = merge_risk_batch_chunk_responses(chunks_out, preset_id=body.preset_id)
        failed = [
            AsyncBatchFailedAsset(
                asset_id=row.id,
                code=row.error.code if row.error else "INTERNAL_ERROR",
                message=row.error.message if row.error else "Scoring failed for this asset.",
            )
            for row in merged.results
            if not row.success
        ]
        store.complete(task_id, merged, failed)
        if body.callback_url is not None:
            _fire_callback(str(body.callback_url), merged)
    except Exception as exc:
        logger.exception("Async batch task %s failed", task_id)
        store.fail(task_id, str(exc) or "Async batch failed.")


__all__ = ["ASYNC_BATCH_CHUNK_SIZE", "async_batch_task_store", "run_async_batch_poc_task"]
