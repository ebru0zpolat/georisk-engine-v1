"""ASGI body-size gate for multipart upload routes.

Runs before Starlette parses ``multipart/form-data``, counting ASGI
``http.request`` chunks so missing / forged ``Content-Length`` cannot bypass
the limit. Does not buffer the full body in memory.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import error_codes as codes
from app.core.config import settings

# Paths whose *entire* request body is capped (multipart upload surface).
_UPLOAD_BODY_LIMIT_PATHS = frozenset({"/v1/portfolio/upload"})


class _BodyTooLarge(Exception):
    """Internal signal: stop feeding the app and emit HTTP 413."""


def _max_bytes() -> int:
    return int(settings.portfolio_upload_max_bytes)


def _envelope(max_bytes: int) -> bytes:
    payload = {
        "error": {
            "code": codes.VALIDATION_ERROR,
            "message": (
                f"Upload exceeds maximum size of {max_bytes} bytes "
                f"({max_bytes // 1_000_000} MB)."
            ),
            "details": {"max_bytes": max_bytes},
        }
    }
    return json.dumps(payload).encode("utf-8")


async def _send_413(send: Send, max_bytes: int) -> None:
    body = _envelope(max_bytes)
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class RequestBodyLimitMiddleware:
    """Pure ASGI middleware — must sit outside Starlette's request body readers."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        paths: Iterable[str] | None = None,
    ) -> None:
        self.app = app
        self.paths = frozenset(paths) if paths is not None else _UPLOAD_BODY_LIMIT_PATHS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path") not in self.paths:
            await self.app(scope, receive, send)
            return
        if scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        max_bytes = _max_bytes()
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    await _send_413(send, max_bytes)
                    return
            except ValueError:
                pass

        received = 0
        rejected = False
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if rejected:
                # Suppress whatever the inner app emits after we decide 413.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def receive_wrapper() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] != "http.request":
                return message
            chunk: bytes = message.get("body", b"") or b""
            received += len(chunk)
            if received > max_bytes:
                rejected = True
                raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except _BodyTooLarge:
            pass

        if rejected and not response_started:
            await _send_413(send, max_bytes)
