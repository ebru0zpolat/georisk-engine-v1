"""Synchronous batch: per-row validation, score with SLA timeout, partial success, aggregate."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone

from app.core import error_codes as codes
from app.core.exceptions import GeoRiskApiError
from app.schemas.risk import (
    RiskBatchCoordinates,
    RiskBatchMeta,
    RiskBatchRequest,
    RiskBatchResponse,
    RiskBatchResultRow,
    RiskBatchRowErrorBody,
    RiskBatchSummary,
    RiskScoreRequest,
    RiskScoreResponse,
)

logger = logging.getLogger(__name__)


def _wgs84_ok(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _row_error(code: str, message: str, details: dict | None = None) -> RiskBatchRowErrorBody:
    return RiskBatchRowErrorBody(code=code, message=message, details=details or {})


def _aggregate(
    results: list[RiskBatchResultRow],
    scores: list[int],
    preset_id: str,
) -> tuple[RiskBatchSummary, RiskBatchMeta]:
    total = len(results)
    success_count = sum(1 for r in results if r.success)
    failed_count = total - success_count
    if not scores:
        summary = RiskBatchSummary(
            total_assets=total,
            success_count=success_count,
            failed_count=failed_count,
            avg_risk=None,
            min_risk=None,
            max_risk=None,
            high_risk_ratio=None,
        )
    else:
        avg = sum(scores) / len(scores)
        high = sum(1 for s in scores if s >= 67) / len(scores)
        summary = RiskBatchSummary(
            total_assets=total,
            success_count=success_count,
            failed_count=failed_count,
            avg_risk=round(avg, 4),
            min_risk=min(scores),
            max_risk=max(scores),
            high_risk_ratio=round(high, 6),
        )
    meta = RiskBatchMeta(
        preset_id=preset_id,
        processed_at=datetime.now(timezone.utc),
    )
    return summary, meta


def execute_sync_batch(
    batch: RiskBatchRequest,
    score_one: Callable[[RiskScoreRequest], RiskScoreResponse],
    *,
    row_timeout_seconds: float,
) -> RiskBatchResponse:
    """Validate coordinates per asset; tolerate row failures."""
    results: list[RiskBatchResultRow] = []
    success_scores: list[int] = []

    for asset in batch.assets:
        loc = RiskBatchCoordinates(lat=asset.lat, lon=asset.lon)
        if not _wgs84_ok(asset.lat, asset.lon):
            results.append(
                RiskBatchResultRow(
                    id=asset.id,
                    location=loc,
                    success=False,
                    error=_row_error(
                        codes.INVALID_COORDINATES,
                        "Latitude or longitude is outside WGS84 bounds.",
                    ),
                )
            )
            continue

        req = RiskScoreRequest(
            asset_name=asset.id,
            latitude=asset.lat,
            longitude=asset.lon,
            radius_km=batch.radius_km,
            sector=batch.sector,
            preset_id=batch.preset_id,
            include_industrial_verification_ref=batch.include_industrial_verification_ref,
        )

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(score_one, req)
                r = fut.result(timeout=row_timeout_seconds)
        except FuturesTimeoutError:
            logger.warning("Batch row %s exceeded score timeout (%.1fs)", asset.id, row_timeout_seconds)
            results.append(
                RiskBatchResultRow(
                    id=asset.id,
                    location=loc,
                    success=False,
                    error=_row_error(
                        codes.TIMEOUT_ERROR,
                        "Scoring exceeded the configured time limit for this asset.",
                        details={"timeout_seconds": row_timeout_seconds},
                    ),
                )
            )
            continue
        except GeoRiskApiError as exc:
            # Typed connector/service failure (e.g. per-point ORAS5 data gap from
            # bulk prefetch): surface the stable code + sanitized message on this
            # row only, keeping the rest of the batch partially successful.
            logger.warning("Batch row %s failed: %s (%s)", asset.id, exc.code, exc.message)
            results.append(
                RiskBatchResultRow(
                    id=asset.id,
                    location=loc,
                    success=False,
                    error=_row_error(exc.code, exc.message, exc.details),
                )
            )
            continue
        except Exception:
            logger.exception("Batch row %s scoring failed", asset.id)
            results.append(
                RiskBatchResultRow(
                    id=asset.id,
                    location=loc,
                    success=False,
                    error=_row_error(
                        codes.INTERNAL_ERROR,
                        "Scoring failed for this asset.",
                    ),
                )
            )
            continue

        results.append(
            RiskBatchResultRow(
                id=asset.id,
                location=loc,
                success=True,
                risk=r.overall_score,
                risk_score=r.risk_score,
                risk_band=r.risk_band,
                sector=r.sector,
                preset_id=r.preset_id,
            )
        )
        success_scores.append(r.overall_score)

    summary, meta = _aggregate(results, success_scores, batch.preset_id)
    return RiskBatchResponse(summary=summary, results=results, meta=meta)


def merge_risk_batch_chunk_responses(parts: list[RiskBatchResponse], *, preset_id: str) -> RiskBatchResponse:
    """Merge chunked synchronous batch results (same ``preset_id``)."""
    rows: list[RiskBatchResultRow] = []
    scores: list[int] = []
    for part in parts:
        rows.extend(part.results)
        for row in part.results:
            if row.success and row.risk is not None:
                scores.append(row.risk)
    summary, meta = _aggregate(rows, scores, preset_id)
    return RiskBatchResponse(summary=summary, results=rows, meta=meta)


__all__ = ["execute_sync_batch", "merge_risk_batch_chunk_responses"]
