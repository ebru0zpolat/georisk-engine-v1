"""Async batch task status stores: shared Redis (production) or in-memory (PoC).

``get_async_batch_task_store()`` picks the backend from ``settings.redis_url``:
when set, task state lives in Redis so the API process and Celery workers see
the same records; otherwise the existing in-memory store keeps the offline
BackgroundTasks path working (tests, local runs without infra).
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.core.config import settings
from app.core.security import DEFAULT_ORGANISATION_ID
from app.schemas.risk import RiskBatchResponse
from app.schemas.risk_async_batch import AsyncBatchFailedAsset

_REDIS_KEY_PREFIX = "georisk:async_batch:"
_REDIS_TTL_SECONDS = 24 * 3600


class AsyncBatchTaskStoreProtocol(Protocol):
    def create_pending(
        self,
        *,
        total: int,
        callback_url: str | None,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
    ) -> str: ...

    def get(self, task_id: str) -> Any | None: ...

    def mark_processing(self, task_id: str) -> None: ...

    def update_progress(self, task_id: str, processed: int) -> None: ...

    def complete(
        self,
        task_id: str,
        result: RiskBatchResponse,
        failed_assets: list[AsyncBatchFailedAsset],
    ) -> None: ...

    def fail(self, task_id: str, message: str) -> None: ...


class _RedisTaskRecord:
    """Attribute view over the Redis JSON payload (same surface as ``_TaskRecord``)."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.status: str = raw["status"]
        self.progress_processed: int = raw["progress_processed"]
        self.progress_total: int = raw["progress_total"]
        self.callback_url: str | None = raw.get("callback_url")
        #: Owning organisation; a record without one matches no caller.
        self.organisation_id: str | None = raw.get("organisation_id")
        self.error_message: str | None = raw.get("error_message")
        self.result: RiskBatchResponse | None = (
            RiskBatchResponse.model_validate(raw["result"]) if raw.get("result") else None
        )
        self.failed_assets: list[AsyncBatchFailedAsset] = [
            AsyncBatchFailedAsset.model_validate(f) for f in raw.get("failed_assets", [])
        ]


class RedisAsyncBatchTaskStore:
    """Task status store backed by Redis; safe across API and Celery worker processes."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    @staticmethod
    def _key(task_id: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{task_id}"

    def _load(self, task_id: str) -> dict[str, Any] | None:
        raw = self._redis.get(self._key(task_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _save(self, task_id: str, payload: dict[str, Any]) -> None:
        self._redis.setex(self._key(task_id), _REDIS_TTL_SECONDS, json.dumps(payload))

    def create_pending(
        self,
        *,
        total: int,
        callback_url: str | None,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
    ) -> str:
        import uuid

        task_id = str(uuid.uuid4())
        self._save(
            task_id,
            {
                "status": "PENDING",
                "progress_processed": 0,
                "progress_total": total,
                "callback_url": callback_url,
                "organisation_id": organisation_id,
                "result": None,
                "failed_assets": [],
                "error_message": None,
            },
        )
        return task_id

    def get(self, task_id: str) -> _RedisTaskRecord | None:
        payload = self._load(task_id)
        return _RedisTaskRecord(payload) if payload is not None else None

    def mark_processing(self, task_id: str) -> None:
        payload = self._load(task_id)
        if payload is None:
            return
        payload["status"] = "PROCESSING"
        self._save(task_id, payload)

    def update_progress(self, task_id: str, processed: int) -> None:
        payload = self._load(task_id)
        if payload is None:
            return
        payload["progress_processed"] = processed
        self._save(task_id, payload)

    def complete(
        self,
        task_id: str,
        result: RiskBatchResponse,
        failed_assets: list[AsyncBatchFailedAsset],
    ) -> None:
        payload = self._load(task_id)
        if payload is None:
            return
        payload["status"] = "COMPLETED"
        payload["result"] = result.model_dump(mode="json")
        payload["failed_assets"] = [f.model_dump(mode="json") for f in failed_assets]
        payload["progress_processed"] = payload["progress_total"]
        self._save(task_id, payload)

    def fail(self, task_id: str, message: str) -> None:
        payload = self._load(task_id)
        if payload is None:
            return
        payload["status"] = "FAILED"
        payload["error_message"] = message
        self._save(task_id, payload)


_cached_store: AsyncBatchTaskStoreProtocol | None = None
_cached_redis_url: str | None = None


def get_async_batch_task_store() -> AsyncBatchTaskStoreProtocol:
    """Redis-backed store when ``REDIS_URL`` is configured, in-memory PoC store otherwise."""
    global _cached_store, _cached_redis_url

    if _cached_store is not None and _cached_redis_url == settings.redis_url:
        return _cached_store

    if settings.redis_url:
        import redis

        _cached_store = RedisAsyncBatchTaskStore(redis.Redis.from_url(settings.redis_url))
    else:
        from app.services.async_batch_poc import async_batch_task_store

        _cached_store = async_batch_task_store
    _cached_redis_url = settings.redis_url
    return _cached_store


def reset_store_cache_for_tests() -> None:
    global _cached_store, _cached_redis_url
    _cached_store = None
    _cached_redis_url = None


__all__ = [
    "AsyncBatchTaskStoreProtocol",
    "RedisAsyncBatchTaskStore",
    "get_async_batch_task_store",
    "reset_store_cache_for_tests",
]
