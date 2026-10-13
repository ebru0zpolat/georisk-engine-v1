"""Client IP resolution for rate limiting (trusted-proxy aware)."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

from app.core.config import settings

# Edge-internal peers when ``TRUST_PRIVATE_PROXY_PEERS`` is on: RFC1918,
# loopback, link-local, and RFC 6598 CGNAT (Railway edge). Do not use
# ``ipaddress.is_private`` for XFF hops: on Python 3.13+ that flag also covers
# documentation ranges (TEST-NET), which are valid synthetic client identities
# in tests and must not be skipped as proxies. CGNAT is intentionally *not*
# always trusted — only via the private-peer opt-in (or an exact TRUSTED_PROXY_IPS
# entry).
_EDGE_INTERNAL_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),  # RFC 6598 Shared Address Space
)


def _is_ip(value: str) -> bool:
    """True for a bare IPv4/IPv6 address (no port, no brackets required)."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _is_edge_internal(value: str) -> bool:
    """True for addresses that may appear as Railway/private edge hops.

    Includes RFC1918, loopback, link-local, and RFC 6598 CGNAT ``100.64.0.0/10``.
    Callers must gate this behind ``trust_private_proxy_peers`` (or exact IP
    allowlists) — never treat these ranges as trusted for unauthenticated peers.
    """
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    if addr.is_loopback or addr.is_link_local:
        return True
    if isinstance(addr, ipaddress.IPv6Address):
        return addr.is_private  # ULA etc.
    return any(addr in net for net in _EDGE_INTERNAL_NETWORKS)


def _peer_is_trusted(peer: str | None) -> bool:
    """Whether the immediate TCP peer may supply forwarded client headers."""
    if not peer:
        return False
    trusted = {ip.strip() for ip in settings.trusted_proxy_ips if ip.strip()}
    if peer in trusted:
        return True
    if not settings.trust_private_proxy_peers:
        return False
    return _is_edge_internal(peer)


def _header_ips(value: str | None) -> list[str]:
    if not value or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split(",") if part.strip() and _is_ip(part.strip())]


def _x_real_ip_tokens(request: Request) -> list[str]:
    """Flatten all ``X-Real-IP`` fields and comma tokens in wire order (trimmed)."""
    tokens: list[str] = []
    for field in request.headers.getlist("x-real-ip"):
        for part in str(field).split(","):
            tokens.append(part.strip())
    return tokens


def _real_ip_from_headers(request: Request) -> str | None:
    """Return edge ``X-Real-IP`` only when ``TRUST_X_REAL_IP`` is enabled.

    Requires a separate opt-in from peer trust: ``TRUSTED_PROXY_IPS`` /
    ``TRUST_PRIVATE_PROXY_PEERS`` alone must not honour client-supplied
    ``X-Real-IP`` (proxies that only sanitize XFF may forward it unchanged).

    Duplicate header fields are flattened via ``getlist``; only the globally
    rightmost token is considered. If that token is missing, empty, has a
    port, or is otherwise not a bare IPv4/IPv6 address, the entire
    ``X-Real-IP`` source is rejected (no backward scan to earlier tokens).
    """
    if not settings.trust_x_real_ip:
        return None

    tokens = _x_real_ip_tokens(request)
    if not tokens:
        return None

    candidate = tokens[-1]
    if not candidate or not _is_ip(candidate):
        return None

    if settings.trust_private_proxy_peers and _is_edge_internal(candidate):
        # Edge-internal "real IP" is not a stable client identity (CGNAT peers
        # rotate). Fall through to XFF walk / peer.
        return None
    return candidate


def _client_from_xff(request: Request, peer: str | None) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    hops = _header_ips(forwarded)
    if not hops:
        return None

    trusted = {ip.strip() for ip in settings.trusted_proxy_ips if ip.strip()}
    for hop in reversed(hops):
        if hop == peer or hop in trusted:
            continue
        if settings.trust_private_proxy_peers and _is_edge_internal(hop):
            continue
        return hop
    return None


def resolve_client_ip(request: Request) -> str:
    """Return the rate-limit identity for ``request``.

    Precedence (fail-closed):

    1. Untrusted peer → ``request.client.host`` (ignore ``X-Real-IP`` / XFF).
    2. Trusted peer + ``TRUST_X_REAL_IP`` + valid rightmost ``X-Real-IP`` → that IP.
    3. Else trusted XFF chain (right-to-left, skipping peer / trusted / edge hops).
    4. Fallback ``request.client.host``.

    ``TRUSTED_PROXY_IPS`` / ``TRUST_PRIVATE_PROXY_PEERS`` only establish peer
    trust for forwarded headers; they do **not** enable ``X-Real-IP``. Enable
    ``TRUST_X_REAL_IP`` only after confirming the edge overwrites or strips
    inbound client ``X-Real-IP``.
    """
    peer = request.client.host if request.client else None
    if not _peer_is_trusted(peer):
        return peer or "unknown"

    real_ip = _real_ip_from_headers(request)
    if real_ip is not None:
        return real_ip

    from_xff = _client_from_xff(request, peer)
    if from_xff is not None:
        return from_xff

    return peer or "unknown"
