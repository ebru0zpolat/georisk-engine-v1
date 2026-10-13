import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
# The in-memory sqlite above is per-connection, so the sync snapshot backend
# could not share it; the suite uses the process-memory snapshot fixture.
os.environ.setdefault("SNAPSHOT_STORE_BACKEND", "memory")
# Public demo rate limits must not flake the suite; tests opt in explicitly.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Production refuses connector stubs at startup; the suite is a local/test env.
os.environ.setdefault("APP_ENV", "local")

import asyncio
import json as json_module
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

from app.core.config import settings
from app.core.rate_limit import reset_rate_limiter_for_tests
from app.db.session import init_db
from app.main import app


@pytest.fixture(autouse=True)
def _disable_rate_limit_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    reset_rate_limiter_for_tests()


@dataclass
class SimpleResponse:
    status_code: int
    content: bytes
    headers: dict[str, str]

    def json(self):
        return json_module.loads(self.content)


class SimpleClient:
    def get(self, path: str, headers: dict[str, str] | None = None) -> SimpleResponse:
        return asyncio.run(self._request("GET", path, headers=headers))

    def post(
        self, path: str, json: dict | None = None, headers: dict[str, str] | None = None
    ) -> SimpleResponse:
        return asyncio.run(self._request("POST", path, json=json, headers=headers))

    def patch(
        self, path: str, json: dict | None = None, headers: dict[str, str] | None = None
    ) -> SimpleResponse:
        return asyncio.run(self._request("PATCH", path, json=json, headers=headers))

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> SimpleResponse:
        url = urlsplit(path)
        messages: list[dict] = []
        body = b"" if json is None else json_module.dumps(json).encode()
        raw_headers: list[tuple[bytes, bytes]] = []
        if json is not None:
            raw_headers.append((b"content-type", b"application/json"))
        for name, value in (headers or {}).items():
            raw_headers.append((name.lower().encode(), value.encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode(),
            "query_string": url.query.encode(),
            "root_path": "",
            "headers": raw_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }

        async def receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict) -> None:
            messages.append(message)

        await app(scope, receive, send)

        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        headers = {
            name.decode().lower(): value.decode()
            for name, value in start.get("headers", [])
        }
        return SimpleResponse(status_code=start["status"], content=body, headers=headers)


@pytest.fixture(scope="session", autouse=True)
def setup_case_database() -> None:
    asyncio.run(init_db())


@pytest.fixture
def client() -> SimpleClient:
    return SimpleClient()
