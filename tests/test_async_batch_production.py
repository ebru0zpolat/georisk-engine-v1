"""Production async batch plane: Redis-backed store + Celery task wiring."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.risk import RiskBatchAsset
from app.schemas.risk_async_batch import AsyncBatchFailedAsset, RiskBatchAsyncRequest
from app.services.async_batch_store import (
    RedisAsyncBatchTaskStore,
    get_async_batch_task_store,
    reset_store_cache_for_tests,
)


class _FakeRedis:
    """Minimal get/setex fake matching the calls RedisAsyncBatchTaskStore makes."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.data[key] = value
        self.ttls[key] = ttl


def test_redis_store_full_lifecycle() -> None:
    store = RedisAsyncBatchTaskStore(_FakeRedis())

    task_id = store.create_pending(total=3, callback_url="https://example.com/cb")
    rec = store.get(task_id)
    assert rec is not None
    assert rec.status == "PENDING"
    assert rec.progress_total == 3
    assert rec.callback_url == "https://example.com/cb"

    store.mark_processing(task_id)
    store.update_progress(task_id, 2)
    rec = store.get(task_id)
    assert rec is not None
    assert rec.status == "PROCESSING"
    assert rec.progress_processed == 2

    from app.schemas.risk import RiskBatchRequest
    from app.services.risk_service import RiskService

    result = RiskService().batch_score(
        RiskBatchRequest(
            preset_id="industrial_v1",
            assets=[RiskBatchAsset(id="R1", lat=41.0, lon=29.0)],
        )
    )
    store.complete(task_id, result, [AsyncBatchFailedAsset(asset_id="X", code="E", message="m")])
    rec = store.get(task_id)
    assert rec is not None
    assert rec.status == "COMPLETED"
    assert rec.progress_processed == 3
    assert rec.result is not None
    assert rec.result.summary.success_count == 1
    assert rec.failed_assets[0].asset_id == "X"


def test_redis_store_fail_and_missing_task() -> None:
    store = RedisAsyncBatchTaskStore(_FakeRedis())
    task_id = store.create_pending(total=1, callback_url=None)
    store.fail(task_id, "boom")
    rec = store.get(task_id)
    assert rec is not None
    assert rec.status == "FAILED"
    assert rec.error_message == "boom"
    assert store.get("nope") is None
    # No-ops on unknown ids must not raise.
    store.mark_processing("nope")
    store.fail("nope", "x")


def test_store_factory_defaults_to_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.async_batch_poc import async_batch_task_store

    reset_store_cache_for_tests()
    monkeypatch.setattr(settings, "redis_url", None)
    assert get_async_batch_task_store() is async_batch_task_store
    reset_store_cache_for_tests()


def test_celery_task_registered_and_runs_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Celery task is registered under a stable name and executes the batch pipeline."""
    from app.services.async_batch_poc import async_batch_task_store
    from app.workers.celery_app import celery_app
    from app.workers.tasks import risk_batch_score_task

    assert "georisk.risk_batch_score" in celery_app.tasks

    # Force the in-memory store so the direct task invocation is observable offline.
    reset_store_cache_for_tests()
    monkeypatch.setattr(settings, "redis_url", None)
    async_batch_task_store.clear_for_tests()

    body = RiskBatchAsyncRequest(
        preset_id="industrial_v1",
        assets=[RiskBatchAsset(id="CEL-1", lat=41.0, lon=29.0)],
    )
    task_id = async_batch_task_store.create_pending(total=1, callback_url=None)
    returned = risk_batch_score_task.run(task_id, body.model_dump(mode="json"))
    assert returned == task_id

    rec = async_batch_task_store.get(task_id)
    assert rec is not None
    assert rec.status == "COMPLETED"
    assert rec.result is not None
    assert rec.result.summary.success_count == 1
    async_batch_task_store.clear_for_tests()
    reset_store_cache_for_tests()
