"""Upload size, rate-limit identity, and CORS guards for the public demo API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import portfolio as portfolio_mod
from app.core import error_codes as codes
from app.core.client_ip import resolve_client_ip
from app.core.config import settings
from app.core.rate_limit import reset_rate_limiter_for_tests
from app.main import app

_ASSET_PAYLOAD = {
    "valuation_date": "2020-01-01",
    "assets": [
        {
            "asset_id": "A1",
            "latitude": 41.0,
            "longitude": 29.0,
            "asset_value": 1000,
            "building_type": "office",
            "use_class": "commercial",
        }
    ],
}


def _request(
    *,
    client_host: str,
    xff: str | None = None,
    x_real_ip: str | None = None,
    x_real_ip_headers: list[str] | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode("latin-1")))
    if x_real_ip_headers is not None:
        for value in x_real_ip_headers:
            headers.append((b"x-real-ip", value.encode("latin-1")))
    elif x_real_ip is not None:
        headers.append((b"x-real-ip", x_real_ip.encode("latin-1")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_portfolio_upload_rejects_oversized_file_before_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "portfolio_upload_max_bytes", 64)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    hits = {"n": 0}

    async def boom(*_a: Any, **_k: Any) -> None:
        hits["n"] += 1
        raise AssertionError("endpoint must not run for oversized bodies")

    monkeypatch.setattr(portfolio_mod, "parse_portfolio_csv_bytes", boom)
    monkeypatch.setattr(portfolio_mod, "parse_portfolio_geojson", boom)

    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/upload",
        data={"valuation_date": "2020-01-01"},
        files={"file": ("big.csv", b"a" * 128, "text/csv")},
    )
    assert r.status_code == 413
    body = r.json()
    assert body["error"]["code"] == codes.VALIDATION_ERROR
    assert body["error"]["details"]["max_bytes"] == 64
    assert hits["n"] == 0


def test_content_length_header_rejects_before_body_read(monkeypatch) -> None:
    monkeypatch.setattr(settings, "portfolio_upload_max_bytes", 100)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    hits = {"n": 0}

    async def boom(*_a: Any, **_k: Any) -> None:
        hits["n"] += 1
        raise AssertionError("endpoint must not run")

    monkeypatch.setattr(portfolio_mod, "parse_portfolio_csv_bytes", boom)

    async def _run() -> dict[str, Any]:
        status: dict[str, Any] = {}
        out = b""

        async def receive() -> dict[str, Any]:
            # Body never needed — Content-Length alone must reject.
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal out
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            elif message["type"] == "http.response.body":
                out += message.get("body", b"")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/portfolio/upload",
            "raw_path": b"/v1/portfolio/upload",
            "query_string": b"",
            "headers": [
                (b"content-type", b"multipart/form-data; boundary=foo"),
                (b"content-length", b"999999"),
            ],
            "client": ("9.9.9.9", 123),
            "server": ("test", 80),
        }
        await app(scope, receive, send)
        return {"status": status["code"], "body": json.loads(out.decode())}

    result = asyncio.run(_run())
    assert result["status"] == 413
    assert result["body"]["error"]["code"] == codes.VALIDATION_ERROR
    assert hits["n"] == 0


def test_chunked_body_without_content_length_cannot_bypass_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "portfolio_upload_max_bytes", 50)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    hits = {"n": 0}

    async def boom(*_a: Any, **_k: Any) -> None:
        hits["n"] += 1
        raise AssertionError("endpoint must not run")

    monkeypatch.setattr(portfolio_mod, "parse_portfolio_csv_bytes", boom)
    monkeypatch.setattr(portfolio_mod, "parse_portfolio_geojson", boom)

    async def _run() -> int:
        status = {"code": 0}
        # No Content-Length. First chunk alone exceeds the limit so the ASGI
        # gate rejects before multipart parsing can consume/fail the stream.
        chunks = [b"x" * 60, b"y" * 10]  # 60 > 50; reject on first chunk
        idx = {"i": 0}

        async def receive() -> dict[str, Any]:
            i = idx["i"]
            if i >= len(chunks):
                return {"type": "http.request", "body": b"", "more_body": False}
            chunk = chunks[i]
            idx["i"] = i + 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": i + 1 < len(chunks),
            }

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/portfolio/upload",
            "raw_path": b"/v1/portfolio/upload",
            "query_string": b"",
            "headers": [(b"content-type", b"multipart/form-data; boundary=foo")],
            "client": ("9.9.9.9", 123),
            "server": ("test", 80),
        }
        await app(scope, receive, send)
        return int(status["code"])

    assert asyncio.run(_run()) == 413
    assert hits["n"] == 0


def test_chunked_body_cumulative_over_chunks_rejects(monkeypatch) -> None:
    """Count across ASGI chunks when each chunk alone is under the limit."""
    monkeypatch.setattr(settings, "portfolio_upload_max_bytes", 50)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    hits = {"n": 0}

    async def boom(*_a: Any, **_k: Any) -> None:
        hits["n"] += 1
        raise AssertionError("endpoint must not run")

    monkeypatch.setattr(portfolio_mod, "parse_portfolio_csv_bytes", boom)

    async def _run() -> int:
        status = {"code": 0}
        # Valid multipart framing so the parser keeps reading past chunk 1.
        boundary = "----georisk"
        head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="b.csv"\r\n'
            f"Content-Type: text/csv\r\n\r\n"
        ).encode()
        pad = b"z" * (50 - len(head) + 1)  # force cumulative > 50 on chunk 2
        chunks = [head, pad]
        idx = {"i": 0}

        async def receive() -> dict[str, Any]:
            i = idx["i"]
            if i >= len(chunks):
                return {"type": "http.request", "body": b"", "more_body": False}
            chunk = chunks[i]
            idx["i"] = i + 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": i + 1 < len(chunks),
            }

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/portfolio/upload",
            "raw_path": b"/v1/portfolio/upload",
            "query_string": b"",
            "headers": [
                (
                    b"content-type",
                    f"multipart/form-data; boundary={boundary}".encode(),
                ),
            ],
            "client": ("9.9.9.9", 123),
            "server": ("test", 80),
        }
        await app(scope, receive, send)
        return int(status["code"])

    assert asyncio.run(_run()) == 413
    assert hits["n"] == 0


def test_json_portfolio_endpoint_not_body_limited_like_multipart(monkeypatch) -> None:
    """Normal JSON ingest stays available; ASGI body gate is upload-path only."""
    monkeypatch.setattr(settings, "portfolio_upload_max_bytes", 32)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    client = TestClient(app)
    # Compact JSON still larger than 32 bytes — must succeed on /portfolio/assets.
    r = client.post("/v1/portfolio/assets", json=_ASSET_PAYLOAD)
    assert r.status_code == 200, r.text


def _auth_request(key: str, client_host: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/portfolio/assets",
        "raw_path": b"/v1/portfolio/assets",
        "query_string": b"",
        "headers": [(b"authorization", f"Bearer {key}".encode())],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_rate_limit_bucket_ignores_unverified_api_keys(monkeypatch) -> None:
    """A fresh random key per request must not open a fresh bucket.

    The middleware runs before authentication, so a presented key is unverified
    there; bucketing on it would let a caller rotate keys to escape the limit.
    """
    from app.core.rate_limit import client_key

    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    rotated = {client_key(_auth_request(f"grk_random{i}", "198.51.100.1")) for i in range(5)}
    assert rotated == {client_key(_request(client_host="198.51.100.1"))}


def test_forged_xff_ignored_without_trusted_proxy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60.0)
    reset_rate_limiter_for_tests()
    client = TestClient(app)

    for i in range(2):
        r = client.post(
            "/v1/portfolio/assets",
            json=_ASSET_PAYLOAD,
            headers={"X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert r.status_code == 200, r.text
    limited = client.post(
        "/v1/portfolio/assets",
        json=_ASSET_PAYLOAD,
        headers={"X-Forwarded-For": "198.51.100.99"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == codes.RATE_LIMIT_EXCEEDED


def test_trusted_proxy_parses_xff_from_right(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["10.0.0.1"])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    req = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
    )
    assert resolve_client_ip(req) == "203.0.113.10"

    # Untrusted peer: XFF ignored.
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    req2 = _request(client_host="203.0.113.50", xff="198.51.100.1")
    assert resolve_client_ip(req2) == "203.0.113.50"

    # Empty / malformed XFF from trusted peer → peer fallback.
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["10.0.0.1"])
    assert resolve_client_ip(_request(client_host="10.0.0.1", xff="")) == "10.0.0.1"
    assert resolve_client_ip(_request(client_host="10.0.0.1", xff="not-an-ip")) == "10.0.0.1"


def test_private_peer_trust_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", True)
    req = _request(client_host="192.168.1.5", xff="203.0.113.77, 192.168.1.5")
    assert resolve_client_ip(req) == "203.0.113.77"


def test_cgnat_peer_trust_opt_in(monkeypatch) -> None:
    """Railway edge peers are RFC 6598 CGNAT; gated by TRUST_PRIVATE_PROXY_PEERS."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", True)
    req = _request(client_host="100.64.1.5", xff="203.0.113.77, 100.64.1.5")
    assert resolve_client_ip(req) == "203.0.113.77"

    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    req_off = _request(client_host="100.64.1.5", xff="203.0.113.77, 100.64.1.5")
    assert resolve_client_ip(req_off) == "100.64.1.5"

    # Untrusted public peer: forged XFF must not choose the rate-limit key.
    req_public = _request(client_host="203.0.113.50", xff="198.51.100.1")
    assert resolve_client_ip(req_public) == "203.0.113.50"


def test_x_real_ip_preferred_over_forged_xff_for_cgnat_peer(monkeypatch) -> None:
    """With TRUST_X_REAL_IP, edge X-Real-IP beats forged XFF behind CGNAT peer."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", True)
    monkeypatch.setattr(settings, "trust_x_real_ip", True)
    req = _request(
        client_host="100.64.0.7",
        xff="198.51.100.1",
        x_real_ip="203.0.113.50",
    )
    assert resolve_client_ip(req) == "203.0.113.50"

    # Untrusted peer: ignore both forwarded headers even if TRUST_X_REAL_IP.
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    req_public = _request(
        client_host="203.0.113.9",
        xff="198.51.100.1",
        x_real_ip="198.51.100.2",
    )
    assert resolve_client_ip(req_public) == "203.0.113.9"


def test_trusted_proxy_ips_alone_does_not_honour_x_real_ip(monkeypatch) -> None:
    """P1: TRUSTED_PROXY_IPS must not silently enable X-Real-IP trust."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["10.0.0.1"])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    monkeypatch.setattr(settings, "trust_x_real_ip", False)
    req = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip="198.51.100.1",
    )
    assert resolve_client_ip(req) == "203.0.113.10"

    monkeypatch.setattr(settings, "trust_x_real_ip", True)
    req_on = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip="198.51.100.1",
    )
    assert resolve_client_ip(req_on) == "198.51.100.1"


def test_private_peer_alone_does_not_honour_x_real_ip(monkeypatch) -> None:
    """TRUST_PRIVATE_PROXY_PEERS without TRUST_X_REAL_IP falls through to XFF."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", True)
    monkeypatch.setattr(settings, "trust_x_real_ip", False)
    req = _request(
        client_host="100.64.0.7",
        xff="203.0.113.77, 100.64.0.7",
        x_real_ip="198.51.100.9",
    )
    assert resolve_client_ip(req) == "203.0.113.77"


def test_duplicate_x_real_ip_uses_globally_rightmost_token(monkeypatch) -> None:
    """P2: getlist + flatten; only the final token is validated."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["10.0.0.1"])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    monkeypatch.setattr(settings, "trust_x_real_ip", True)
    req = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip_headers=["198.51.100.1, 198.51.100.2", "203.0.113.50"],
    )
    assert resolve_client_ip(req) == "203.0.113.50"

    req_ipv6 = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip_headers=["198.51.100.1", "2001:db8::50"],
    )
    assert resolve_client_ip(req_ipv6) == "2001:db8::50"


def test_malformed_rightmost_x_real_ip_rejects_entire_source(monkeypatch) -> None:
    """Do not scan backward when the rightmost X-Real-IP token is invalid."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["10.0.0.1"])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    monkeypatch.setattr(settings, "trust_x_real_ip", True)

    # Valid earlier token, malformed rightmost → fall through to XFF.
    req_bad = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip_headers=["203.0.113.99", "not-an-ip"],
    )
    assert resolve_client_ip(req_bad) == "203.0.113.10"

    # Port in rightmost token → reject source.
    req_port = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip="203.0.113.99:8080",
    )
    assert resolve_client_ip(req_port) == "203.0.113.10"

    # Comma list whose rightmost token is bad → reject (no leftward scan).
    req_comma = _request(
        client_host="10.0.0.1",
        xff="203.0.113.10, 10.0.0.1",
        x_real_ip="203.0.113.99, 198.51.100.1:443",
    )
    assert resolve_client_ip(req_comma) == "203.0.113.10"


def test_rotating_forged_xff_same_real_ip_still_rate_limits(monkeypatch) -> None:
    """Edge-set X-Real-IP keeps one key while client rotates forged XFF."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", ["testclient"])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", True)
    monkeypatch.setattr(settings, "trust_x_real_ip", True)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 3)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60.0)
    reset_rate_limiter_for_tests()
    client = TestClient(app)
    for i in range(3):
        r = client.post(
            "/v1/portfolio/assets",
            json=_ASSET_PAYLOAD,
            headers={
                "X-Forwarded-For": f"198.51.100.{i}",
                "X-Real-IP": "203.0.113.50",
            },
        )
        assert r.status_code == 200, r.text
    limited = client.post(
        "/v1/portfolio/assets",
        json=_ASSET_PAYLOAD,
        headers={
            "X-Forwarded-For": "198.51.100.99",
            "X-Real-IP": "203.0.113.50",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == codes.RATE_LIMIT_EXCEEDED


def test_rotating_both_forged_headers_still_rate_limits(monkeypatch) -> None:
    """Same source rotating both X-Real-IP and XFF cannot bypass the limiter."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    monkeypatch.setattr(settings, "trust_x_real_ip", False)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 60)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60.0)
    reset_rate_limiter_for_tests()
    client = TestClient(app)
    for i in range(60):
        r = client.post(
            "/v1/portfolio/assets",
            json=_ASSET_PAYLOAD,
            headers={
                "X-Forwarded-For": f"198.51.100.{i % 250}",
                "X-Real-IP": f"203.0.113.{i % 250}",
            },
        )
        assert r.status_code == 200, f"request {i + 1}: {r.text}"
    limited = client.post(
        "/v1/portfolio/assets",
        json=_ASSET_PAYLOAD,
        headers={
            "X-Forwarded-For": "198.51.100.250",
            "X-Real-IP": "203.0.113.250",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == codes.RATE_LIMIT_EXCEEDED


def test_rate_limit_61st_mutating_post_same_ip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 60)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60.0)
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "trust_private_proxy_peers", False)
    reset_rate_limiter_for_tests()
    client = TestClient(app)
    for i in range(60):
        r = client.post("/v1/portfolio/assets", json=_ASSET_PAYLOAD)
        assert r.status_code == 200, f"request {i + 1}: {r.text}"
    limited = client.post("/v1/portfolio/assets", json=_ASSET_PAYLOAD)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == codes.RATE_LIMIT_EXCEEDED


def test_health_exempt_from_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60.0)
    reset_rate_limiter_for_tests()
    client = TestClient(app)
    assert client.get("/v1/health").status_code == 200
    assert client.get("/v1/health").status_code == 200


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://georiskengine.com", True),
        ("https://www.georiskengine.com", True),
        ("https://georisk-engine-abc123-ebruozpolats-projects.vercel.app", True),
        ("https://evil.vercel.app.attacker.example", False),
        ("http://georisk-engine.vercel.app", False),
        ("https://evil.example.com", False),
        ("https://vercel.app", False),
    ],
)
def test_cors_origins(monkeypatch, origin: str, allowed: bool) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    # Rebuild CORS middleware settings are read at app init — CORSMiddleware
    # already holds compiled regex from import-time settings. For regex cases we
    # exercise the compiled pattern on the live app (defaults match production).
    client = TestClient(app)
    r = client.options(
        "/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    acao = r.headers.get("access-control-allow-origin")
    if allowed:
        assert r.status_code == 200
        assert acao == origin
    else:
        assert acao != origin
        assert acao is None or acao == "null" or origin not in (acao or "")
