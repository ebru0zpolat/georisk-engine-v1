"""In-process fixed-window rate limiter for the public demo API.

No external dependency. Suitable for a single Railway replica; multi-replica
deployments need a shared store (Redis) — out of scope for Phase A.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core import error_codes as codes
from app.core.client_ip import resolve_client_ip
from app.core.config import settings

_EXEMPT_PREFIXES = (
    "/health",
    "/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
)


class _FixedWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1.0, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                retry = int(max(1, self.window_seconds - (now - q[0])))
                return False, 0, retry
            q.append(now)
            remaining = self.limit - len(q)
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = _FixedWindowLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


def reset_rate_limiter_for_tests() -> None:
    """Clear in-memory counters (tests only)."""
    global _limiter
    _limiter = _FixedWindowLimiter(
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )


def client_key(request: Request) -> str:
    """Rate-limit key: trusted-proxy-aware client IP (see ``client_ip``)."""
    return resolve_client_ip(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Cheap public abuse surface: mutate + compute endpoints.
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        key = client_key(request)
        allowed, remaining, retry_after = _limiter.allow(key)
        if not allowed:
            body = {
                "error": {
                    "code": codes.RATE_LIMIT_EXCEEDED,
                    "message": (
                        f"Rate limit exceeded ({settings.rate_limit_requests} "
                        f"requests / {int(settings.rate_limit_window_seconds)}s). "
                        "Retry later."
                    ),
                    "details": {
                        "limit": settings.rate_limit_requests,
                        "window_seconds": settings.rate_limit_window_seconds,
                        "retry_after_seconds": retry_after,
                    },
                }
            }
            return JSONResponse(
                status_code=429,
                content=body,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.rate_limit_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
