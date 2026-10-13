from __future__ import annotations

import json

import pytest

from georisk_mcp import authorization
from georisk_mcp.authorization import (
    CapabilityAuthorizationError,
    TrustedExecutionContext,
    authorize_capability,
)
from georisk_mcp.capability_registry import CAPABILITY_REGISTRY
from georisk_mcp import server
from georisk_mcp.host_auth import VerifiedMcpHostAuthenticationAdapter
from mcp.server.auth.provider import AccessToken


class FakeContext:
    request_id = "request-1"


def adapter(permission: str | None) -> VerifiedMcpHostAuthenticationAdapter:
    scopes = [] if permission is None else [permission]
    token = AccessToken(
        token="not-recorded",
        client_id="principal-a",
        scopes=scopes,
        resource="tenant-a",
    )
    return VerifiedMcpHostAuthenticationAdapter(lambda: token)


def context(*, tenant: str = "tenant-a", permissions: frozenset[str] = frozenset()) -> TrustedExecutionContext:
    return TrustedExecutionContext("principal-a", tenant, permissions, "request-1")


@pytest.mark.parametrize(
    ("capability", "permission"),
    [
        ("assess_asset", "asset:read"),
        ("compare_assets", "asset:read"),
        ("get_source_evidence", "evidence:read"),
        ("generate_evidence_pack", "evidence_pack:generate"),
    ],
)
def test_registry_permissions_allow_capabilities(capability: str, permission: str) -> None:
    decision = authorize_capability(capability, context=context(permissions=frozenset({permission})))
    assert decision.allowed is True
    assert decision.required_permissions == tuple(sorted(CAPABILITY_REGISTRY[capability].required_permissions))
    assert decision.canonical_api_dependency == CAPABILITY_REGISTRY[capability].canonical_dependency


@pytest.mark.parametrize(
    ("ctx", "reason"),
    [
        (None, "missing_or_malformed_context"),
        (TrustedExecutionContext("", "tenant-a", frozenset({"asset:read"}), "r"), "missing_principal"),
        (TrustedExecutionContext("p", "", frozenset({"asset:read"}), "r"), "missing_tenant"),
        (TrustedExecutionContext("p", "t", frozenset(), "r"), "missing_permissions"),
        (TrustedExecutionContext("p", "t", frozenset({"unrelated:read"}), "r"), "missing_required_permission"),
    ],
)
def test_authorization_fails_closed(ctx: TrustedExecutionContext | None, reason: str) -> None:
    with pytest.raises(CapabilityAuthorizationError) as captured:
        authorize_capability("assess_asset", context=ctx)
    assert captured.value.decision.allowed is False
    assert captured.value.decision.reason == reason
    assert captured.value.decision.as_dict()["capability_name"] == "assess_asset"


def test_unknown_capability_and_service_failure_are_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(CapabilityAuthorizationError, match="unknown_capability"):
        authorize_capability("not_registered", context=context(permissions=frozenset({"asset:read"})))
    monkeypatch.setattr(authorization, "get_capability_policy", lambda name: 1 / 0)
    with pytest.raises(CapabilityAuthorizationError) as captured:
        authorize_capability("assess_asset", context=context(permissions=frozenset({"asset:read"})))
    assert captured.value.decision.reason == "authorization_service_failure"


def test_malformed_context_fails_closed() -> None:
    malformed = TrustedExecutionContext("p", "t", None, "r")  # type: ignore[arg-type]
    with pytest.raises(CapabilityAuthorizationError) as captured:
        authorize_capability("assess_asset", context=malformed)
    assert captured.value.decision.reason == "missing_or_malformed_context"


def test_cross_tenant_denial_has_no_resource_disclosure() -> None:
    with pytest.raises(CapabilityAuthorizationError) as captured:
        authorize_capability(
            "assess_asset",
            context=context(tenant="tenant-a", permissions=frozenset({"asset:read"})),
            resource_tenant_id="tenant-b",
        )
    envelope = captured.value.decision.as_dict()
    assert envelope["reason"] == "cross_tenant_access"
    assert "tenant-b" not in json.dumps(envelope)


def test_same_tenant_resource_scope_is_allowed() -> None:
    decision = authorize_capability(
        "assess_asset",
        context=context(tenant="tenant-a", permissions=frozenset({"asset:read"})),
        resource_tenant_id="tenant-a",
    )
    assert decision.allowed is True


def test_mcp_argument_cannot_supply_tenant_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_client", lambda: pytest.fail("upstream client was invoked"))
    monkeypatch.setattr(server, "_auth_adapter", adapter("asset:read"))
    result = json.loads(
        server.compare_assets(
            [{"id": "a", "lat": 1.0, "lon": 2.0, "tenant_id": "tenant-b"}],
            ctx=FakeContext(),
        )
    )
    assert result["authorization"]["reason"] == "caller_supplied_authority"
    assert "tenant-b" not in json.dumps(result)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def score(self, body):
        self.calls.append("POST /v1/risk/score")
        return {"audit_id": "a1"}

    def batch_score(self, body):
        self.calls.append("POST /v1/risk/batch")
        return {"results": []}

    def source_evidence(self, source_id=None):
        self.calls.append("GET /v1/data-sources/validation")
        return {"evidence_version": "v1"}

    def report_markdown(self, body):
        self.calls.append("POST /v1/reports/risk")
        return "# Evidence"


@pytest.mark.parametrize(
    ("tool", "permission", "args", "endpoint"),
    [
        (server.assess_asset, "asset:read", ("A", 1.0, 2.0), "POST /v1/risk/score"),
        (server.compare_assets, "asset:read", ([{"id": "a", "lat": 1.0, "lon": 2.0}],), "POST /v1/risk/batch"),
        (server.get_source_evidence, "evidence:read", (), "GET /v1/data-sources/validation"),
        (server.generate_evidence_pack, "evidence_pack:generate", ("A", 1.0, 2.0), "POST /v1/reports/risk"),
    ],
)
def test_every_exposed_tool_authorizes_before_expected_api(
    monkeypatch: pytest.MonkeyPatch, tool, permission: str, args: tuple, endpoint: str
) -> None:
    fake = FakeClient()
    monkeypatch.setattr(server, "_client", lambda: fake)
    monkeypatch.setattr(server, "_auth_adapter", adapter(permission))
    result = json.loads(tool(*args, ctx=FakeContext()))
    assert fake.calls == [endpoint]
    assert result["authorization"]["allowed"] is True
    assert result["authorization"]["canonical_api_dependency"] == endpoint


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (server.assess_asset, ("A", 1.0, 2.0)),
        (server.compare_assets, ([{"id": "a", "lat": 1.0, "lon": 2.0}],)),
        (server.get_source_evidence, ()),
        (server.generate_evidence_pack, ("A", 1.0, 2.0)),
    ],
)
def test_denial_never_constructs_or_invokes_upstream_client(monkeypatch, tool, args) -> None:
    monkeypatch.setattr(server, "_client", lambda: pytest.fail("upstream client was invoked"))
    monkeypatch.setattr(server, "_auth_adapter", VerifiedMcpHostAuthenticationAdapter(lambda: None))
    result = json.loads(tool(*args, ctx=FakeContext()))
    assert result["error"] == "HOST_AUTHENTICATION_FAILED"
    assert result["authentication"]["authenticated"] is False


def test_mcp_arguments_cannot_override_trusted_tenant_identity() -> None:
    for tool in (server.assess_asset, server.compare_assets, server.get_source_evidence, server.generate_evidence_pack):
        assert "tenant_id" not in tool.__annotations__
        assert "organization_id" not in tool.__annotations__


def test_public_registry_and_mcp_tool_sets_match() -> None:
    exposed = set(server.mcp._tool_manager._tools)
    assert exposed == set(CAPABILITY_REGISTRY)
