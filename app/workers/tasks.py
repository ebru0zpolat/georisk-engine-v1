"""Celery tasks for the async batch plane."""

from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="georisk.risk_batch_score", bind=True, max_retries=0)
def risk_batch_score_task(self, task_id: str, body: dict) -> str:  # noqa: ANN001
    """Score an async batch on a Celery worker.

    Task state (progress / result / failures) is written to the shared Redis
    store, so ``GET /v1/risk/batch/status/{task_id}`` reads it from any API
    process. The payload is the JSON dump of ``RiskBatchAsyncRequest``.
    """
    from app.schemas.risk_async_batch import RiskBatchAsyncRequest
    from app.services.async_batch_poc import run_async_batch_poc_task

    run_async_batch_poc_task(task_id, RiskBatchAsyncRequest.model_validate(body))
    return task_id


__all__ = ["risk_batch_score_task"]
