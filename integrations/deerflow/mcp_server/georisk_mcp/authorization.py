"""Runtime authorization boundary for GeoRisk MCP capabilities.

Authentication is intentionally not implemented here. A verified MCP host/auth adapter
must bind a trusted context for each invocation; absent context fails closed.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from georisk_mcp.capability_registry import get_capability_policy


@dataclass(frozen=True)
class TrustedExecutionContext:
    principal_id: str
    tenant_id: str
    permissions: frozenset[str]
    request_id: str


@dataclass(frozen=True)
class AuthorizationDecision:
    request_id: str
    principal_id: str | None
    tenant_id: str | None
    capability_name: str
    required_permissions: tuple[str, ...]
    allowed: bool
    reason: str
    canonical_api_dependency: str | None
    decided_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "capability_name": self.capability_name,
            "required_permissions": list(self.required_permissions),
            "allowed": self.allowed,
            "reason": self.reason,
            "canonical_api_dependency": self.canonical_api_dependency,
            "decided_at": self.decided_at,
        }


class CapabilityAuthorizationError(Exception):
    def __init__(self, decision: AuthorizationDecision) -> None:
        self.decision = decision
        super().__init__(decision.reason)


_execution_context: ContextVar[TrustedExecutionContext | None] = ContextVar(
    "georisk_mcp_execution_context", default=None
)


@contextmanager
def bind_trusted_execution_context(
    context: TrustedExecutionContext,
) -> Iterator[None]:
    """Bind context supplied by a verified host/auth adapter for one invocation."""
    token = _execution_context.set(context)
    try:
        yield
    finally:
        _execution_context.reset(token)


def current_execution_context() -> TrustedExecutionContext | None:
    return _execution_context.get()


def authorize_capability(
    capability_name: str,
    *,
    context: TrustedExecutionContext | None = None,
    resource_tenant_id: str | None = None,
    invocation_arguments: object | None = None,
) -> AuthorizationDecision:
    """Make the single registry-backed authorization decision; raise on denial."""
    ctx = context if context is not None else current_execution_context()
    now = datetime.now(timezone.utc).isoformat()
    request_id = ctx.request_id if isinstance(ctx, TrustedExecutionContext) else "unavailable"
    principal_id = ctx.principal_id if isinstance(ctx, TrustedExecutionContext) else None
    tenant_id = ctx.tenant_id if isinstance(ctx, TrustedExecutionContext) else None
    try:
        policy = get_capability_policy(capability_name)
    except Exception as exc:
        decision = AuthorizationDecision(
            request_id=request_id,
            principal_id=principal_id,
            tenant_id=tenant_id,
            capability_name=capability_name,
            required_permissions=(),
            allowed=False,
            reason="authorization_service_failure",
            canonical_api_dependency=None,
            decided_at=now,
        )
        raise CapabilityAuthorizationError(decision) from exc
    required = tuple(sorted(policy.required_permissions)) if policy else ()
    dependency = policy.canonical_dependency if policy else None

    reason = "allowed"
    if policy is None:
        reason = "unknown_capability"
    elif not isinstance(ctx, TrustedExecutionContext):
        reason = "missing_or_malformed_context"
    elif not (
        isinstance(ctx.principal_id, str)
        and isinstance(ctx.tenant_id, str)
        and isinstance(ctx.request_id, str)
        and isinstance(ctx.permissions, frozenset)
        and all(isinstance(permission, str) for permission in ctx.permissions)
    ):
        reason = "missing_or_malformed_context"
    elif not ctx.principal_id.strip():
        reason = "missing_principal"
    elif policy.tenant_scoped and not ctx.tenant_id.strip():
        reason = "missing_tenant"
    elif not ctx.request_id.strip():
        reason = "missing_request_id"
    elif not ctx.permissions:
        reason = "missing_permissions"
    elif not policy.required_permissions.issubset(ctx.permissions):
        reason = "missing_required_permission"
    elif resource_tenant_id is not None and resource_tenant_id != ctx.tenant_id:
        reason = "cross_tenant_access"
    elif _contains_forbidden_authority(
        invocation_arguments, policy.forbidden_authority_fields
    ):
        reason = "caller_supplied_authority"

    decision = AuthorizationDecision(
        request_id=request_id,
        principal_id=principal_id,
        tenant_id=tenant_id,
        capability_name=capability_name,
        required_permissions=required,
        allowed=reason == "allowed",
        reason=reason,
        canonical_api_dependency=dependency,
        decided_at=now,
    )
    if not decision.allowed:
        raise CapabilityAuthorizationError(decision)
    return decision


def _contains_forbidden_authority(value: object, forbidden: frozenset[str]) -> bool:
    if isinstance(value, dict):
        if forbidden.intersection(str(key) for key in value):
            return True
        return any(_contains_forbidden_authority(item, forbidden) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_authority(item, forbidden) for item in value)
    return False
