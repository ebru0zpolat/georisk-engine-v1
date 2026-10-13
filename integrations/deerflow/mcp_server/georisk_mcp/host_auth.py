"""Adapter from FastMCP's verified bearer context to GeoRisk execution context."""

from __future__ import annotations

import time
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterator

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from georisk_mcp.authorization import (
    TrustedExecutionContext,
    bind_trusted_execution_context,
)

MECHANISM = "fastmcp_verified_bearer"


@dataclass(frozen=True)
class AuthenticationAudit:
    request_id: str
    mechanism: str
    authenticated: bool
    principal_id: str | None
    tenant_id: str | None
    failure_category: str | None
    authenticated_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "mechanism": self.mechanism,
            "authenticated": self.authenticated,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "failure_category": self.failure_category,
            "authenticated_at": self.authenticated_at,
        }


class HostAuthenticationError(Exception):
    def __init__(self, audit: AuthenticationAudit) -> None:
        self.audit = audit
        super().__init__(audit.failure_category or "authentication_failed")


class VerifiedMcpHostAuthenticationAdapter:
    """Trust only AccessToken objects installed by FastMCP auth middleware.

    The adapter does not parse bearer strings or verify JWTs itself. Authenticity must
    already have been established by FastMCP's configured ``TokenVerifier``.
    """

    def __init__(
        self,
        token_provider: Callable[[], AccessToken | None] = get_access_token,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._token_provider = token_provider
        self._clock = clock

    def verify(self, request_id: object) -> tuple[TrustedExecutionContext, AuthenticationAudit]:
        now = datetime.now(timezone.utc).isoformat()
        safe_request_id = str(request_id) if request_id is not None else "unavailable"
        try:
            token = self._token_provider()
        except Exception as exc:
            raise self._failure(safe_request_id, "verification_service_failure", now) from exc
        if token is None:
            raise self._failure(safe_request_id, "missing_verified_identity", now)
        if not isinstance(token, AccessToken):
            raise self._failure(safe_request_id, "unsupported_authentication_mechanism", now)
        if token.expires_at is not None and token.expires_at <= int(self._clock()):
            raise self._failure(safe_request_id, "expired_credentials", now)
        if not isinstance(token.client_id, str) or not token.client_id.strip():
            raise self._failure(safe_request_id, "missing_principal_claim", now)
        tenant_id = token.resource
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise self._failure(safe_request_id, "missing_tenant_claim", now)
        if not isinstance(token.scopes, list) or not token.scopes or not all(
            isinstance(scope, str) and scope.strip() for scope in token.scopes
        ):
            raise self._failure(safe_request_id, "missing_or_malformed_scopes", now)
        if not safe_request_id.strip() or safe_request_id == "unavailable":
            raise self._failure(safe_request_id, "missing_request_id", now)

        context = TrustedExecutionContext(
            principal_id=token.client_id.strip(),
            tenant_id=tenant_id.strip(),
            permissions=frozenset(scope.strip() for scope in token.scopes),
            request_id=safe_request_id,
        )
        audit = AuthenticationAudit(
            safe_request_id,
            MECHANISM,
            True,
            context.principal_id,
            context.tenant_id,
            None,
            now,
        )
        return context, audit

    @contextmanager
    def authenticated_request(self, request_id: object) -> Iterator[AuthenticationAudit]:
        context, audit = self.verify(request_id)
        binding = bind_trusted_execution_context(context)
        try:
            binding.__enter__()
        except Exception as exc:
            raise self._failure(
                audit.request_id,
                "context_binding_failure",
                datetime.now(timezone.utc).isoformat(),
            ) from exc
        try:
            yield audit
        finally:
            binding.__exit__(*sys.exc_info())

    @staticmethod
    def _failure(request_id: str, category: str, timestamp: str) -> HostAuthenticationError:
        return HostAuthenticationError(
            AuthenticationAudit(
                request_id,
                MECHANISM,
                False,
                None,
                None,
                category,
                timestamp,
            )
        )
