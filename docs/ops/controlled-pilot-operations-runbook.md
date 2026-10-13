# Controlled-Pilot Operations Runbook

**Status:** Planned (GEO-62)
**Version:** 1.0
**Date:** 23 August 2026

> This runbook explains how to operate the controlled-pilot environment.
> It does not constitute production readiness.  `production_eligible`
> remains **false**.

---

## 1. Configuration

### Configuration Identifiers (Never Values)

| Identifier | Required | Purpose |
|-----------|----------|---------|
| `APP_ENV` | Yes | Environment name (`local`, `staging`, `pilot`) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `API_KEY_SALT` | Yes | Key derivation salt |
| `CORS_ORIGINS` | Yes | Allowed origins (JSON array) |
| `GEE_PROJECT` | Optional | Google Earth Engine project |
| `ORAS5_ZARR_URL` | Optional | ORAS5 Zarr store URL |
| `CDSAPI_KEY` | Optional | Copernicus CDS API key |

**Rules:**
- Never log, expose or commit actual values.
- Placeholder values (`changeme`, `placeholder`, `test`, etc.) are rejected.
- Missing required values fail closed.

### Configuration Evaluation

```python
from app.ops.config import evaluate_deploy_config, ConnectorConfig, ConfigState

result = evaluate_deploy_config(
    environment_name="pilot",
    connectors=[
        ConnectorConfig(
            name="database",
            enabled=True,
            required_env_vars=["DATABASE_URL"],
            state=ConfigState.REQUIRED,
        ),
    ],
)
assert result.complete  # False if any required var is missing or placeholder
```

---

## 2. Authenticated Smoke

### Prerequisites

- Approved HTTPS base URL
- Exact release commit SHA (40 lowercase hex chars)
- Explicit live-consent flag

### Invocation

```bash
python -m app.ops.smoke \
  --base-url https://approved-host.example \
  --release-sha <40-character-sha> \
  --explicit-live-consent
```

**Never run during pytest.**  **Never run automatically during deployment.**

### What the Smoke Checks

1. HTTPS connectivity to the approved host
2. `/v1/health` endpoint returns JSON with `status` field
3. Response within bounded size (1 MiB default)
4. No redirect to a different host
5. Bounded timeout (30s default) and retries (2 max)

### What the Smoke Does NOT Do

- Store response bodies
- Log authorization headers
- Set `runtime_live_verified=true`
- Set `production_eligible=true`
- Replace human release approval

---

## 3. Evidence Interpretation

### Evidence Record Fields

| Field | Meaning |
|-------|---------|
| `transport_verified` | HTTPS round-trip succeeded |
| `application_response_verified` | Valid JSON with `status` field received |
| `authentication_attempted` | Auth was attempted (if configured) |
| `authentication_succeeded` | Auth succeeded |
| `runtime_live_verified` | **Always false** — requires separate validation |
| `production_eligible` | **Always false** — requires all gates |

### Evidence Status Legend

| Status | Meaning |
|--------|---------|
| `persisted` | Evidence stored in durable retention |
| `pending` | Evidence created but not yet retained |
| `failed` | Retention failed |
| `unavailable` | No retention backend configured |

---

## 4. Retention States

| State | Meaning | Pilot Gate |
|-------|---------|------------|
| `persisted` | Evidence is write-once stored with checksum | ✅ Satisfied |
| `pending` | Created but not retained | ❌ Not satisfied |
| `failed` | Retention attempted but failed | ❌ Not satisfied |
| `unavailable` | No retention backend | ❌ Not satisfied |

**Retention failure must never be silently treated as persisted.**

---

## 5. Readiness Gates

| Gate | Description |
|------|-------------|
| `config_complete` | All required config present, no placeholders |
| `authenticated_smoke_passed` | Smoke command succeeded |
| `transport_verified` | HTTPS round-trip succeeded |
| `application_response_verified` | Valid app response received |
| `evidence_hash_verified` | Evidence SHA-256 matches recomputation |
| `durable_retention_verified` | Evidence persisted with checksum |
| `source_tree_clean` | No uncommitted changes at release time |
| `exact_release_sha_verified` | Release SHA matches actual commit |
| `human_release_approval` | Independent human review approved |

**All gates must pass.**  `human_release_approval` cannot be set by
environment variable, API request or automated test.

---

## 6. Incident / Rollback

| Action | Owner | Status |
|--------|-------|--------|
| Rollback decision | [PLACEHOLDER — deployment owner] | Not started |
| Evidence preservation | [PLACEHOLDER — ops owner] | Not started |
| Incident communication | [PLACEHOLDER — incident lead] | Not started |

---

## 7. What Remains Human / Deployment

- Configuration secrets must be provided through approved channels.
- Human release approval requires an independent reviewer.
- Actual smoke execution against production requires explicit consent.
- Retention backend selection requires an architecture decision.
- `production_eligible=true` requires all gates plus release authority.

---

## 8. Why Pytest Is Not Production Smoke

- Tests run against mocked or local endpoints.
- Tests do not validate real network connectivity.
- Tests do not prove the deployed service is operational.
- Tests do not carry release authority.
- Production smoke requires explicit opt-in against an approved URL.

---

## C2.5 composition note (2026-09-01)

This surface is the single controlled-pilot operations layer required by roadmap
task C2.5, composed from two independent PRs that were opened against the same
objective a day apart and shared no files:

| From | What it contributed |
|---|---|
| PR #139 | `app/ops/` — config, hardened smoke transport, evidence schema, retention contract, readiness gates, and the targeted test suite |
| PR #145 | The release gate (`.github/workflows/controlled-pilot.yml`), the three authenticated assertions, and durable S3 Object Lock retention |

Three things changed in the merge, and each is a deliberate decision rather than
a mechanical union:

**One smoke, not two.** Both PRs implemented a smoke. `app/ops/smoke.py` had the
security hardening — exact-host allowlist, `ipaddress` validation, redirects
disabled, bounded reads, header redaction — but, despite its module docstring,
never sent a credential: `authentication_attempted` and
`authentication_succeeded` were hardcoded `False`. PR #145's script had the three
assertions GEO-62 actually requires but none of the hardening. The assertions
were therefore ported into the hardened transport and
`scripts/controlled_pilot_smoke.py` was not carried over. Shipping both would
have left the pilot with two smoke implementations and no answer to which one's
evidence counts.

**Durable retention is code, not shell.** PR #145 performed the object-lock write
as inline `aws s3api` calls in the workflow — durable, but untestable and outside
the `EvidenceRetention` contract. It is now `S3ObjectLockRetention`, a fourth
backend behind the same ABC as `InMemoryRetention`, `TempDirRetention` and
`DisabledRetention`, exercised by tests with an injected fake client and no
network access. It is the only backend that satisfies
`durable_retention_verified`; the other three are write-once but not durable.

**No unpinned third-party action.** PR #145 used
`aws-actions/configure-aws-credentials@v4`. Every action in this repository is
pinned by commit SHA, so the workflow instead performs the OIDC exchange with
`aws sts assume-role-with-web-identity` using the preinstalled AWS CLI.

### What is still false

Landing this changes no flag. `AUTHENTICATED_SMOKE_PASSED`,
`DURABLE_RETENTION_VERIFIED`, `CONTROLLED_PILOT_ELIGIBLE`,
`RUNTIME_LIVE_VERIFIED` and `PRODUCTION_ELIGIBLE` all remain false. They move
only when the workflow runs against a real deployment with real secrets and
produces a real evidence record — C2.6 through C2.13. The code is the mechanism;
it is not the evidence.
