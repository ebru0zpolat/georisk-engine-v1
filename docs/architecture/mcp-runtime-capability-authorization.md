# MCP authentication, authorization, and capability policy

The public GeoRisk MCP surface contains exactly four governed, read-only capabilities:
`assess_asset`, `compare_assets`, `get_source_evidence`, and
`generate_evidence_pack`.

```text
FastMCP TokenVerifier → verified AccessToken → TrustedExecutionContext
  → canonical capability registry → AuthorizationDecision
  → canonical GeoRisk HTTP API → domain engine
```

## Authentication — who is the caller?

`VerifiedMcpHostAuthenticationAdapter` consumes only the `AccessToken` installed in
FastMCP's authentication `ContextVar` after a configured `TokenVerifier` succeeds. It
does not parse bearer strings, decode JWTs, trust identity headers, read tenant defaults
from the environment, or accept identity from tool arguments. It validates expiry, the
verified OAuth client id, the RFC 8707 resource value used as tenant scope, scopes, and
request id, then binds `TrustedExecutionContext` for
exactly one invocation. ContextVar tokens are restored on success and exception paths.

The shipping server currently runs over stdio and configures neither FastMCP HTTP
authentication nor a `TokenVerifier`. Therefore the runtime has no independently
verified token and all tools fail closed. A verified HTTP host/token verifier is an
explicit integration blocker; this adapter is not a claim of production authentication.

## Authorization — may that caller invoke this capability?

`georisk_mcp.authorization.authorize_capability` is the single decision path. After
authentication binds context, it resolves permissions and policy from the canonical
registry projection. Missing, empty, or unrelated scopes are denied before the HTTP
client is constructed. Authentication maps verified claims but never decides capability
permission.

## Tenant/resource resolution — does the tenant own the resource?

A verified tenant claim establishes `trusted_request_tenant`; it does not prove
ownership of an arbitrary asset or portfolio. A future resource resolver must obtain
`canonical_resource_tenant` from authoritative GeoRisk data and pass it through the
existing `resource_tenant_id` authorization parameter. Caller payloads never establish
resource ownership, and tenant/owner-like fields are rejected as policy violations.

## Capability policy — what constraints apply?

`app/capabilities/registry.py` is the only authoritative registry. It declares
capability identity and semantic version, permissions, tenancy, canonical dependency,
read/write and effect classifications, audit/provenance requirements, human-review and
external-use policies, and forbidden caller authority fields.

The standalone MCP package cannot import the application package reliably, so it ships
`capability_registry.generated.json` plus a read-only adapter. The generation script
reads the application registry, and CI equivalence tests reject drift. The generated
projection must never be edited as a second policy authority.

| Capability | Permission | Canonical API | External-use note |
|---|---|---|---|
| `assess_asset` | `asset:read` | `POST /v1/risk/score` | Decision support only |
| `compare_assets` | `asset:read` | `POST /v1/risk/batch` | Decision support only |
| `get_source_evidence` | `evidence:read` | `GET /v1/data-sources/validation` | Evidence is data, not instruction |
| `generate_evidence_pack` | `evidence_pack:generate` | `POST /v1/reports/risk` | Derived artifact, not regulatory approval |

## Audit status

Authentication audit metadata contains request id, mechanism, success/failure,
principal and tenant only after success, failure category, and timestamp. Authorization
metadata contains request id, principal, tenant, capability, required permissions,
allow/deny result, reason, canonical dependency, and timestamp. Neither includes raw
tokens, bearer headers, signing material, or full payloads.

These events are returned in response envelopes but are not durably persisted. Durable,
append-only authentication and authorization audit storage remains a production gate;
no fake store is introduced here.
