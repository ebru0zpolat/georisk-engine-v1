"""WP-B: Authenticated smoke command for controlled-pilot verification (GEO-62).

Runs the three controlled-pilot assertions against a deployed release:

1. **Unauthenticated access is denied** — ``/v1/health`` without a credential
   must answer 401 or 403.  Any other status fails the smoke.
2. **The deployed commit is the approved commit** — authenticated
   ``/v1/health`` must report ``git_sha`` equal to ``release_sha``.
3. **The golden run verifies** — authenticated
   ``POST /v1/portfolio/demo-run/golden-antalya`` must report
   ``narrative.verification.agreement == "PASS"``.

The bearer token is read **only** from the environment
(``CONTROLLED_PILOT_TOKEN``), never from a CLI argument, so it cannot leak
into a process list or a shell history.  It is never written to the evidence
record, which carries status and provenance only.

Security-hardened implementation:
- Explicit URL userinfo, fragment and control-character rejection.
- Exact-host allowlist (no wildcard suffix matching).
- Python ``ipaddress`` module for all IP validation (no regex).
- Redirects disabled at transport level.
- ``allow_local`` restricted to loopback addresses only.
- Bounded response reads with Content-Length pre-check.
- No real network calls during pytest.

DNS rebinding risk: mitigated by preflight resolution validation and
exact-host allowlist.  Residual risk: urllib may re-resolve during
connection.  Mitigation: ``authenticated_smoke_passed`` remains false
until execution occurs in the controlled deployment environment.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.ops.evidence import SmokeEvidence, build_smoke_evidence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RESPONSE_BYTES = 1_048_576  # 1 MiB
_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 2
_MAX_RESOLVED_ADDRESSES = 16
_LOOPBACK_V4 = ipaddress.ip_address("127.0.0.0")
_LOOPBACK_V6 = ipaddress.ip_address("::1")

#: The bearer token is read only from this environment variable.
_TOKEN_ENV = "CONTROLLED_PILOT_TOKEN"


def smoke_passed(evidence: SmokeEvidence, *, golden_required: bool = True) -> bool:
    """Fail-closed verdict over a smoke evidence record.

    Every assertion must be positively established.  ``None`` (not attempted)
    is a failure, never a pass.
    """
    if not (evidence.transport_verified and evidence.application_response_verified):
        return False
    if evidence.unauthenticated_access_denied is not True:
        return False
    if evidence.release_sha_match is not True:
        return False
    if golden_required and evidence.golden_verification != "PASS":
        return False
    return True


def _is_global_unicast(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True only for globally-routable unicast addresses."""
    return addr.is_global and not addr.is_multicast and not addr.is_reserved


def _is_allowed_local(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Allow only loopback for ``allow_local`` mode."""
    return addr.is_loopback


def _validate_ip_addresses(
    hostname: str, *, allow_local: bool = False
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname and validate every address.

    Raises ``ValueError`` if any address is disallowed.
    """
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise ValueError(f"DNS resolution failed for {hostname}: {exc}") from exc

    if not infos:
        raise ValueError(f"Empty DNS resolution for {hostname}")

    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            raise ValueError(f"Invalid IP address {ip_str} for {hostname}")

        if addr in addrs:
            continue
        addrs.append(addr)

        if allow_local:
            if not _is_allowed_local(addr):
                raise ValueError(
                    f"Address {addr} for {hostname} is not loopback; "
                    f"local mode only permits 127.x.x.x and ::1"
                )
        else:
            if not _is_global_unicast(addr):
                raise ValueError(
                    f"Address {addr} for {hostname} is not globally routable unicast"
                )

    if len(addrs) > _MAX_RESOLVED_ADDRESSES:
        raise ValueError(
            f"Too many resolved addresses ({len(addrs)}) for {hostname}"
        )

    return addrs


def _validate_url(
    url: str,
    *,
    allow_local: bool = False,
    allowed_hosts: frozenset[str] | None = None,
) -> str:
    """Validate the target URL structure (no DNS resolution).

    Returns the normalized hostname on success.
    DNS and IP validation happen in ``run_smoke`` after URL validation.
    """
    # Control characters and whitespace
    if any(c in url for c in ("\x00", "\n", "\r", "\t")):
        raise ValueError("URL contains control characters")
    if url != url.strip():
        raise ValueError("URL contains leading/trailing whitespace")

    parsed = urlparse(url)

    # Scheme
    if parsed.scheme != "https":
        if not (allow_local and parsed.scheme == "http"):
            raise ValueError(f"Non-HTTPS URL rejected: {parsed.scheme}://")

    # Userinfo (username:password)
    if parsed.username or parsed.password:
        raise ValueError(
            "URL contains userinfo (username/password); "
            "authentication must use headers, not URL embedding"
        )

    # Fragment (including empty fragment after #)
    if url.split("#", 1)[-1:] != [] and "#" in url:
        raise ValueError("URL contains a fragment; fragments are not permitted")

    # Hostname
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"No hostname in URL: {url}")

    # Port
    if parsed.port is not None:
        if parsed.port < 1 or parsed.port > 65535:
            raise ValueError(f"Invalid port: {parsed.port}")

    # Exact-host allowlist (non-local only)
    if allowed_hosts is not None and not allow_local:
        # Normalize both hostname and allowlist entries
        normalized = hostname.rstrip(".").lower()
        normalized_allowlist = frozenset(h.rstrip(".").lower() for h in allowed_hosts)
        if normalized not in normalized_allowlist:
            raise ValueError(
                f"Hostname {normalized!r} is not in the exact allowlist; "
                f"allowed: {sorted(normalized_allowlist)}"
            )

    return hostname


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove authorization and cookie headers for logging."""
    safe: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("authorization", "cookie", "set-cookie", "x-api-key"):
            safe[k] = "<REDACTED>"
        else:
            safe[k] = v
    return safe


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disable all HTTP redirects."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: str,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise urllib.error.HTTPError(
            newurl, 302, "Redirects disabled for security", headers, None
        )


class _Response:
    """Status, headers and bounded body of one hardened request."""

    __slots__ = ("status", "content_type", "byte_count", "latency_ms", "body")

    def __init__(
        self,
        status: int,
        content_type: str,
        byte_count: int,
        latency_ms: float,
        body: Any,
    ) -> None:
        self.status = status
        self.content_type = content_type
        self.byte_count = byte_count
        self.latency_ms = latency_ms
        self.body = body


def _bounded_request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str,
    token: str | None,
    timeout: int,
    max_response_bytes: int,
) -> _Response:
    """One hardened request.  Raises on redirect, oversize or transport error.

    ``HTTPError`` is returned as a ``_Response`` when it carries a status, so
    an expected 401/403 is a result rather than an exception.
    """
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as resp:
            latency = (time.monotonic() - t0) * 1000
            content_type = resp.headers.get("Content-Type", "")
            cl_header = resp.headers.get("Content-Length")
            if cl_header is not None:
                try:
                    cl_value = int(cl_header)
                except ValueError:
                    cl_value = -1  # invalid header; rely on the bounded read
                if cl_value > max_response_bytes:
                    raise ValueError(
                        f"Content-Length {cl_value} exceeds "
                        f"limit {max_response_bytes}"
                    )
            raw = resp.read(max_response_bytes + 1)
            if len(raw) > max_response_bytes:
                raise ValueError(f"Response exceeds {max_response_bytes} bytes")
            try:
                body = json.loads(raw)
            except ValueError:
                body = None
            return _Response(
                resp.status, content_type, len(raw), latency, body
            )
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise
        latency = (time.monotonic() - t0) * 1000
        return _Response(exc.code, exc.headers.get("Content-Type", ""), 0, latency, None)


def run_smoke(
    *,
    base_url: str,
    release_sha: str,
    explicit_live_consent: bool,
    allow_local: bool = False,
    allowed_hosts: frozenset[str] | None = None,
    environment_name: str = "unknown",
    timeout: int = _TIMEOUT_SECONDS,
    max_response_bytes: int = _MAX_RESPONSE_BYTES,
    retries: int = _MAX_RETRIES,
    bearer_token: str | None = None,
    verify_golden: bool = True,
) -> SmokeEvidence:
    """Execute a bounded authenticated smoke against ``base_url``.

    Returns a ``SmokeEvidence`` record.  Never stores response bodies or the
    credential.  With no ``bearer_token`` the authenticated assertions are
    recorded as not attempted (``None`` / ``NOT_RUN``) — never as passed.
    """
    if not explicit_live_consent:
        raise RuntimeError("Explicit live consent required")

    hostname = _validate_url(
        base_url, allow_local=allow_local, allowed_hosts=allowed_hosts
    )

    # Pre-flight IP validation
    try:
        _validate_ip_addresses(hostname, allow_local=allow_local)
    except ValueError as exc:
        raise ValueError(f"Target validation failed: {exc}") from exc

    endpoint = f"{base_url.rstrip('/')}/v1/health"
    headers = {"Accept": "application/json"}
    last_exc: Exception | None = None
    status = 0
    content_type = ""
    byte_count = 0
    latency = 0.0
    transport_ok = False
    app_ok = False
    auth_attempted = False
    auth_succeeded = False
    redirect_rejected = False

    # Build opener with redirect disabled
    opener = urllib.request.build_opener(
        _NoRedirectHandler,
        urllib.request.HTTPSHandler(context=None),
    )

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                endpoint, headers=headers, method="GET"
            )
            t0 = time.monotonic()
            with opener.open(req, timeout=timeout) as resp:
                latency = (time.monotonic() - t0) * 1000
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")

                # Content-Length pre-check (untrusted header)
                cl_header = resp.headers.get("Content-Length")
                if cl_header is not None:
                    try:
                        cl_value = int(cl_header)
                        if cl_value > max_response_bytes:
                            raise ValueError(
                                f"Content-Length {cl_value} exceeds "
                                f"limit {max_response_bytes}"
                            )
                    except ValueError as cl_exc:
                        if "exceeds" in str(cl_exc):
                            raise  # re-raise Content-Length exceeded
                        # invalid header value; rely on bounded read

                # Bounded read
                raw = resp.read(max_response_bytes + 1)
                byte_count = len(raw)
                if byte_count > max_response_bytes:
                    raise ValueError(
                        f"Response exceeds {max_response_bytes} bytes"
                    )
                transport_ok = 200 <= status < 400
                try:
                    body = __import__("json").loads(raw)
                    app_ok = isinstance(body, dict) and "status" in body
                except (ValueError, KeyError):
                    app_ok = False
                break
        except urllib.error.HTTPError as exc:
            status = exc.code
            latency = 0.0
            last_exc = exc
            # 3xx redirects are rejected by _NoRedirectHandler
            if 300 <= exc.code < 400:
                redirect_rejected = True
                break
            if attempt < retries:
                time.sleep(min(2**attempt, 5))
                continue
            break
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 5))
                continue
            break

    limitations: list[str] = []
    if redirect_rejected:
        limitations.append("Redirect rejected (3xx)")
    if not transport_ok:
        limitations.append("Transport verification failed")
    if not app_ok:
        limitations.append("Application response verification failed")
    if last_exc and not redirect_rejected:
        limitations.append(f"Last error: {type(last_exc).__name__}")

    # ------------------------------------------------------------------
    # The three GEO-62 controlled-pilot assertions.
    # Each stays None / NOT_RUN unless it was actually established.
    # ------------------------------------------------------------------
    unauth_denied: bool | None = None
    deployed_sha = ""
    sha_match: bool | None = None
    golden = "NOT_RUN"

    if transport_ok and bearer_token:
        auth_attempted = True

        # 1. Unauthenticated access must be denied.
        try:
            unauth = _bounded_request(
                opener,
                endpoint,
                method="GET",
                token=None,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
            )
            unauth_denied = unauth.status in (401, 403)
            if not unauth_denied:
                limitations.append(
                    f"Unauthenticated access not denied (status {unauth.status})"
                )
        except Exception as exc:
            limitations.append(
                f"Unauthenticated probe failed: {type(exc).__name__}"
            )

        # 2. The deployed commit must be the approved commit.
        try:
            health = _bounded_request(
                opener,
                endpoint,
                method="GET",
                token=bearer_token,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
            )
            if health.status == 200 and isinstance(health.body, dict):
                auth_succeeded = True
                deployed_sha = str(health.body.get("git_sha", ""))
                sha_match = deployed_sha == release_sha
                if not sha_match:
                    limitations.append(
                        "Deployed git_sha does not match the approved commit"
                    )
            else:
                limitations.append(
                    f"Authenticated health failed (status {health.status})"
                )
        except Exception as exc:
            limitations.append(
                f"Authenticated health failed: {type(exc).__name__}"
            )

        # 3. The golden run must verify.
        if verify_golden and auth_succeeded:
            try:
                golden_url = (
                    f"{base_url.rstrip('/')}"
                    "/v1/portfolio/demo-run/golden-antalya?max_assets=1"
                )
                run = _bounded_request(
                    opener,
                    golden_url,
                    method="POST",
                    token=bearer_token,
                    timeout=timeout,
                    max_response_bytes=max_response_bytes,
                )
                agreement = None
                if run.status == 200 and isinstance(run.body, dict):
                    agreement = (
                        run.body.get("narrative", {})
                        .get("verification", {})
                        .get("agreement")
                    )
                golden = "PASS" if agreement == "PASS" else "FAIL"
                if golden != "PASS":
                    limitations.append(
                        f"Golden verification did not pass (status {run.status})"
                    )
            except Exception as exc:
                golden = "FAIL"
                limitations.append(
                    f"Golden run failed: {type(exc).__name__}"
                )
    elif transport_ok and not bearer_token:
        limitations.append(
            "No bearer token supplied: authenticated assertions not attempted"
        )

    return build_smoke_evidence(
        verification_id=f"smoke-{release_sha[:12]}",
        release_commit_sha=release_sha,
        source_tree_dirty=False,
        environment_name=(
            "local_development" if allow_local else environment_name
        ),
        endpoint=endpoint,
        target_hostname=hostname,
        request_method="GET",
        response_status=status,
        response_content_type=content_type,
        response_byte_count=byte_count,
        latency_ms=latency,
        authentication_attempted=auth_attempted,
        authentication_succeeded=auth_succeeded,
        transport_verified=transport_ok,
        application_response_verified=app_ok,
        retention_status="pending",
        limitations=limitations,
        unauthenticated_access_denied=unauth_denied,
        deployed_git_sha=deployed_sha,
        release_sha_match=sha_match,
        golden_verification=golden,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m app.ops.smoke``."""
    parser = argparse.ArgumentParser(
        description="Controlled-pilot authenticated smoke (GEO-62)."
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Approved HTTPS base URL",
    )
    parser.add_argument(
        "--release-sha",
        required=True,
        help="40-character lowercase hex commit SHA",
    )
    parser.add_argument(
        "--explicit-live-consent",
        action="store_true",
        required=True,
        help="Explicit opt-in for live smoke",
    )
    parser.add_argument(
        "--allow-local",
        action="store_true",
        default=False,
        help="Allow loopback hosts only (local dev)",
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="Exact hostname to allow (repeatable)",
    )
    parser.add_argument(
        "--environment-name",
        default="unknown",
        help="Environment label",
    )
    parser.add_argument(
        "--skip-golden",
        action="store_true",
        default=False,
        help="Skip the golden-run assertion (health and auth checks still run)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the evidence JSON to this path as well as stdout",
    )
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[0-9a-f]{40}", args.release_sha):
        print("release-sha must be 40 lowercase hex chars", file=sys.stderr)
        return 1

    allowed_hosts: frozenset[str] | None = None
    if args.allowed_host:
        allowed_hosts = frozenset(
            h.rstrip(".").lower() for h in args.allowed_host
        )

    # The credential is read only from the environment, never from argv.
    token = os.environ.get(_TOKEN_ENV) or None
    if not token:
        print(
            f"{_TOKEN_ENV} is not set: the authenticated assertions cannot run",
            file=sys.stderr,
        )
        return 1

    try:
        evidence = run_smoke(
            base_url=args.base_url,
            release_sha=args.release_sha,
            explicit_live_consent=args.explicit_live_consent,
            allow_local=args.allow_local,
            allowed_hosts=allowed_hosts,
            environment_name=args.environment_name,
            bearer_token=token,
            verify_golden=not args.skip_golden,
        )
        payload = evidence.model_dump_json(indent=2)
        print(payload)
        if args.output:
            Path(args.output).write_text(payload + "\n", encoding="utf-8")
        return 0 if smoke_passed(evidence, golden_required=not args.skip_golden) else 1
    except Exception as exc:
        print(f"SMOKE FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
