"""Celery application for the production async batch plane.

Broker and result backend both come from ``REDIS_URL``. Start a worker with:

    celery -A app.workers.celery_app:celery_app worker --loglevel=info

Without ``REDIS_URL`` the API falls back to the in-process BackgroundTasks
path, so this module is only exercised in deployments with Redis.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "georisk",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

__all__ = ["celery_app"]
