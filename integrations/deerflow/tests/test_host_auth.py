from __future__ import annotations

import asyncio
import inspect
import json

import pytest
from mcp.server.auth.provider import AccessToken

from app.capabilities.registry import registry_projection
from georisk_mcp import server
from georisk_mcp.authorization import current_execution_context
from georisk_mcp.capability_registry import CAPABILITY_REGISTRY
from georisk_mcp import capability_registry as mcp_registry_adapter
from georisk_mcp.host_auth import (
    HostAuthenticationError,
    VerifiedMcpHostAuthenticationAdapter,
)
from georisk_mcp import host_auth


def token(
    *, subject: str = "principal-a", tenant: str = "tenant-a",
    scopes: list[str] | None = None, expires_at: int | None = None,
) -> AccessToken:
    return AccessToken(
        token="secret-must-not-appear",
        client_id=subject,
        scopes=scopes or ["asset:read"],
        expires_at=expires_at,
        resource=tenant,
    )


def test_verified_fastmcp_identity_binds_and_restores_context() -> None:
    adapter = VerifiedMcpHostAuthenticationAdapter(lambda: token())
    assert current_execution_context() is None
    with adapter.authenticated_request("request-1") as audit:
        context = current_execution_context()
        assert context is not None
        assert (context.principal_id, context.tenant_id) == ("principal-a", "tenant-a")
        assert context.permissions == frozenset({"asset:read"})
        assert audit.authenticated is True
        assert "secret" not in json.dumps(audit.as_dict())
    assert current_execution_context() is None


@pytest.mark.parametrize(
    ("provider", "reason"),
    [
        (lambda: None, "missing_verified_identity"),
        (lambda: {"tenant_id": "caller-controlled"}, "unsupported_authentication_mechanism"),
        (lambda: token(expires_at=1), "expired_credentials"),
        (lambda: token(subject=""), "missing_principal_claim"),
        (lambda: AccessToken(token="x", client_id="p", scopes=["asset:read"]), "missing_tenant_claim"),
        (lambda: AccessToken(token="x", client_id="p", scopes=[], resource="t"), "missing_or_malformed_scopes"),
    ],
)
def test_authentication_failures_are_controlled_and_bind_nothing(provider, reason: str) -> None:
    adapter = VerifiedMcpHostAuthenticationAdapter(provider, clock=lambda: 10)
    with pytest.raises(HostAuthenticationError) as captured:
        with adapter.authenticated_request("request-1"):
            pytest.fail("authentication unexpectedly succeeded")
    assert captured.value.audit.failure_category == reason
    assert captured.value.audit.principal_id is None
    assert captured.value.audit.tenant_id is None
    assert current_execution_context() is None


def test_exception_path_restores_previous_context() -> None:
    adapter = VerifiedMcpHostAuthenticationAdapter(lambda: token())
    with pytest.raises(RuntimeError):
        with adapter.authenticated_request("request-1"):
            raise RuntimeError("boom")
    assert current_execution_context() is None


def test_context_binding_failure_is_controlled(monkeypatch) -> None:
    class BrokenBinding:
        def __enter__(self):
            raise RuntimeError("binding unavailable")

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(host_auth, "bind_trusted_execution_context", lambda context: BrokenBinding())
    adapter = VerifiedMcpHostAuthenticationAdapter(lambda: token())
    with pytest.raises(HostAuthenticationError) as captured:
        with adapter.authenticated_request("request-1"):
            pass
    assert captured.value.audit.failure_category == "context_binding_failure"


def test_previous_identity_does_not_survive_unauthenticated_request() -> None:
    valid = VerifiedMcpHostAuthenticationAdapter(lambda: token())
    with valid.authenticated_request("request-1"):
        assert current_execution_context() is not None
    invalid = VerifiedMcpHostAuthenticationAdapter(lambda: None)
    with pytest.raises(HostAuthenticationError):
        with invalid.authenticated_request("request-2"):
            pass
    assert current_execution_context() is None


def test_missing_authentication_precedes_authorization_and_client(monkeypatch) -> None:
    monkeypatch.setattr(server, "_auth_adapter", VerifiedMcpHostAuthenticationAdapter(lambda: None))
    monkeypatch.setattr(server, "authorize_capability", lambda name: pytest.fail("authorization invoked"))
    monkeypatch.setattr(server, "_client", lambda: pytest.fail("client constructed"))
    result = json.loads(server.assess_asset("A", 1.0, 2.0, ctx=type("C", (), {"request_id": "r"})()))
    assert result["error"] == "HOST_AUTHENTICATION_FAILED"


def test_valid_identity_with_insufficient_scope_reaches_authorization_only(monkeypatch) -> None:
    adapter = VerifiedMcpHostAuthenticationAdapter(
        lambda: token(scopes=["unrelated:read"])
    )
    monkeypatch.setattr(server, "_auth_adapter", adapter)
    monkeypatch.setattr(server, "_client", lambda: pytest.fail("client constructed"))
    result = json.loads(server.assess_asset("A", 1.0, 2.0, ctx=type("C", (), {"request_id": "r"})()))
    assert result["error"] == "CAPABILITY_AUTHORIZATION_DENIED"
    assert result["authentication"]["authenticated"] is True
    assert result["authorization"]["reason"] == "missing_required_permission"


def test_parallel_request_contexts_are_isolated() -> None:
    async def run(principal: str, tenant: str, ready: asyncio.Event) -> tuple[str, str]:
        adapter = VerifiedMcpHostAuthenticationAdapter(
            lambda: token(subject=principal, tenant=tenant)
        )
        with adapter.authenticated_request(f"request-{principal}"):
            ready.set()
            await asyncio.sleep(0)
            context = current_execution_context()
            assert context is not None
            return context.principal_id, context.tenant_id

    async def scenario() -> list[tuple[str, str]]:
        first, second = asyncio.Event(), asyncio.Event()
        return await asyncio.gather(
            run("principal-a", "tenant-a", first),
            run("principal-b", "tenant-b", second),
        )

    assert asyncio.run(scenario()) == [
        ("principal-a", "tenant-a"),
        ("principal-b", "tenant-b"),
    ]
    assert current_execution_context() is None


def test_generated_mcp_projection_exactly_matches_authoritative_registry() -> None:
    projected = json.loads(json.dumps(registry_projection()))
    adapted = {
        name: {
            **vars(policy),
            "required_permissions": sorted(policy.required_permissions),
            "forbidden_authority_fields": sorted(policy.forbidden_authority_fields),
        }
        for name, policy in sorted(CAPABILITY_REGISTRY.items())
    }
    assert adapted == projected
    assert set(server.mcp._tool_manager._tools) == set(projected)


def test_mcp_registry_adapter_contains_no_manual_capability_declarations() -> None:
    source = inspect.getsource(mcp_registry_adapter)
    for capability_name in registry_projection():
        assert f'"{capability_name}"' not in source
