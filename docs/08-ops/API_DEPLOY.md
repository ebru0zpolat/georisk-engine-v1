# FastAPI backend deploy

Vercel serves **frontend only**. The demo at `/demo` needs `VITE_API_BASE_URL` pointing at this API.

## Live Railway host

| Item | Value |
|------|--------|
| Project / service | `georisk-api` / `api` |
| Public URL | `https://api-production-5880.up.railway.app` |
| Health | `GET /v1/health` → `{"status":"ok","service":"georisk-engine","git_sha":"<sha\|unknown>","app_env":"demo|production|…","connector_stubs_permitted":true\|false}` |
| Audit trail volume | Mounted at `/data/audit_trail` (STUBS.md #20) |
| `GEORISK_AUDIT_TRAIL_PATH` | `/data/audit_trail/expected_loss.jsonl` |
| Shared trail consumers | `/v1/portfolio/analyze` **and** `/v1/portfolio/demo-run*` (`run_portfolio_demo` → `get_audit_trail()`) |

## Required variables

| Variable | Value |
|----------|--------|
| `APP_ENV` | **`demo`** on the current Railway host (labelled connector stubs permitted). Use **`production` only** when presenting endpoints as production asset-risk scoring — that class rejects missing Zarr / live-source configuration at startup and refuses `_fallback_features`. |
| `GIT_SHA` | Optional explicit commit SHA for `/v1/health`. When unset, the API reads Railway's `RAILWAY_GIT_COMMIT_SHA`. Local/dev without either → `"unknown"`. Do not invent a SHA. |
| `CORS_ORIGINS` | JSON array: `["https://georiskengine.com","https://www.georiskengine.com"]` (defaults also include these plus localhost) |
| `CORS_ORIGIN_REGEX` | Anchored HTTPS Vercel hosts only — default `https://([a-zA-Z0-9-]+\.)+vercel\.app` (set `none` to disable) |
| `GEE_ENABLED` | `false` for demo. Production scoring requires `true` plus `GEE_PROJECT`. |
| `GEORISK_AUDIT_TRAIL_PATH` | `/data/audit_trail/expected_loss.jsonl` (with volume) |
| `PORTFOLIO_UPLOAD_MAX_BYTES` | default `2000000` (2 MB) — ASGI body limit on `POST /v1/portfolio/upload` **before** multipart parse |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | default `60` / `60` (POST/PUT/PATCH/DELETE per effective client IP) |
| `TRUST_PRIVATE_PROXY_PEERS` | **`true` on Railway** — trusts direct peers in RFC1918, loopback, link-local, **and RFC 6598 CGNAT `100.64.0.0/10`** so the edge may supply `X-Forwarded-For` (parsed from the **right**; clients cannot spoof on a direct connection). Leave `false` on hosts that do not sit behind a private/CGNAT edge. Does **not** enable `X-Real-IP`. |
| `TRUSTED_PROXY_IPS` | Optional comma/JSON list of exact proxy peer IPs (in addition to private-peer opt-in). Does **not** enable `X-Real-IP`. |
| `TRUST_X_REAL_IP` | Default **`false`**. When `true` **and** the TCP peer is trusted, honour the globally rightmost `X-Real-IP` token for rate-limit identity. Enable **only** after confirming the edge overwrites or removes inbound client `X-Real-IP`. Separate from `TRUSTED_PROXY_IPS` / `TRUST_PRIVATE_PROXY_PEERS`. |

### Connector stubs vs production

| Environment | Required behavior |
|-------------|-------------------|
| Test / local / demo (`APP_ENV` in `local`, `dev`, `test`, `demo`) | Deterministic `_fallback_features` permitted and labelled (`data_mode=stub`, `production_eligible=false`) |
| Production (`APP_ENV=production`) | Missing live configuration must fail closed |
| API response using a stub | `data_mode=stub`, `production_eligible=false` |
| Production startup | Reject missing `ORAS5_ZARR_URL` (and CDS Bearer when the URL is ARCO), plus live GEE (`GEE_ENABLED`, `GEE_PROJECT`) |

The current Railway host is a **demo**. Keep `APP_ENV=demo` until endpoints are presented as production asset-risk scoring. Setting `APP_ENV=production` without the live sources above refuses process start (`ProductionLiveSourceError`) and request-time stubs return `CONNECTOR_STUB_PROHIBITED` (503).

### Deploy provenance (`git_sha`)

`GET /v1/health` returns `git_sha` so operators can confirm which commit is live. Resolution order:

1. `GIT_SHA` (explicit override)
2. `RAILWAY_GIT_COMMIT_SHA` (Railway injects this on deploy)
3. `"unknown"` (local/dev)

Health must not expose unrelated build metadata (project IDs, service IDs, secrets).

### Railway peer trust (CGNAT)

Railway's edge connects to the container from **`100.64.0.0/10`** (RFC 6598 Shared Address Space / CGNAT), not classic RFC1918. Set `TRUST_PRIVATE_PROXY_PEERS=true` so that range is treated as a trusted **direct peer** (and equivalent hops are skipped when walking XFF).

Do **not** blindly honour `X-Forwarded-For` from every peer, and do **not** trust all public peers. Without the opt-in (or an exact `TRUSTED_PROXY_IPS` entry), forged XFF must not choose the rate-limit key.

### Railway `X-Real-IP` (separate opt-in)

Client-IP precedence for rate limiting:

1. Untrusted peer → `request.client.host` (ignore `X-Real-IP` and XFF)
2. Trusted peer + `TRUST_X_REAL_IP=true` + valid rightmost `X-Real-IP` → that IP
3. Else trusted XFF chain (right-to-left)
4. Fallback `request.client.host`

`TRUSTED_PROXY_IPS` and `TRUST_X_REAL_IP` are **independent**. Exact peer allowlisting alone must not honour client-supplied `X-Real-IP` — many proxies sanitize only XFF and leave `X-Real-IP` under client control.

**Railway production settings** (restore the previous live behaviour of preferring edge `X-Real-IP` over forged XFF):

- `TRUST_PRIVATE_PROXY_PEERS=true`
- `TRUST_X_REAL_IP=true` — **only if** Railway is verified to set/overwrite `X-Real-IP` to the connecting client (and not merely forward a client-supplied value). If that is not verified, leave `TRUST_X_REAL_IP=false` and rely on XFF right-to-left walk from the trusted CGNAT peer.

Duplicate `X-Real-IP` header fields are flattened in wire order; only the globally rightmost token is validated as a bare IPv4/IPv6 address (no port). A missing/malformed rightmost token rejects the entire `X-Real-IP` source (no backward scan).

## Public API abuse controls

- **Upload size:** ASGI middleware rejects `POST /v1/portfolio/upload` bodies above `PORTFOLIO_UPLOAD_MAX_BYTES` with HTTP 413 (standard error envelope) using `Content-Length` when valid **and** by counting ASGI body chunks (chunked / missing / forged length). Endpoint-level file read remains as defense in depth. JSON `/v1/portfolio/assets` is not subject to this multipart body gate.
- **Rate limit:** Mutating methods limited per resolved client IP (HTTP 429, `RATE_LIMIT_EXCEEDED`). Health/docs exempt. In-process only (single replica). Forwarded client identity is honoured only when the TCP peer is trusted (exact `TRUSTED_PROXY_IPS` and/or `TRUST_PRIVATE_PROXY_PEERS`, which includes Railway CGNAT). `X-Real-IP` is consulted only with `TRUST_X_REAL_IP=true` on a trusted peer, preferring the edge-set value over client-influenced `X-Forwarded-For` so forged left XFF hops cannot rotate the rate-limit key when the edge overwrites `X-Real-IP`.

## CORS behaviour (code-backed)

- Explicit allowlist via `CORS_ORIGINS` (JSON array or comma-separated).
- Optional `allow_origin_regex` from `CORS_ORIGIN_REGEX` (Starlette `fullmatch`). Default matches only `https://*.vercel.app` style hosts — not `http://`, not `vercel.app` apex, not lookalike suffixes.
- Empty / `none` / `false` disables the regex.

## Smoke

1. `GET /v1/health` → 200 with `git_sha` matching the intended deploy commit (not `"unknown"` in production). Demo host: `app_env=demo`, `connector_stubs_permitted=true`. Production host: `app_env=production`, `connector_stubs_permitted=false`.
2. Golden Antalya demo-run → verification PASS
3. Oversized upload → 413; 61st mutating POST from same IP → 429 (forged rotating `X-Forwarded-For` must not bypass when Railway appends the real client)
4. OPTIONS preflight from `https://georiskengine.com` and a `*.vercel.app` preview → ACAO echo; lookalike origins → no ACAO

## Controlled-pilot release gate

Use the manually dispatched **Controlled pilot release** workflow
(`.github/workflows/controlled-pilot.yml`) for a pilot that contains customer
data or is represented as access-controlled. The `controlled-pilot` GitHub
Environment must require a human reviewer and must hold these secrets
(environment secrets, not repository variables):

- `RAILWAY_TOKEN`, `RAILWAY_SERVICE_ID`
- `PILOT_BASE_URL`, `CONTROLLED_PILOT_TOKEN`
- `PILOT_EVIDENCE_BUCKET`, `PILOT_EVIDENCE_AWS_ROLE_ARN`,
  `PILOT_EVIDENCE_AWS_REGION`

The AWS role is obtained through GitHub OIDC — the workflow exchanges the
Actions ID token with `aws sts assume-role-with-web-identity` using the
preinstalled AWS CLI, so no third-party action and no long-lived AWS access-key
secret is involved. Restrict the role's trust policy to this repository and the
`controlled-pilot` environment, and scope its permissions to the named evidence
bucket and the object-lock/versioning calls the workflow makes.

Before dispatch, provision the evidence bucket with **versioning and S3 Object
Lock enabled**. `app.ops.retention.S3ObjectLockRetention` reads both back before
writing anything, refuses a retention horizon below 365 days, writes each record
write-once under a `verification_id` key in `COMPLIANCE` mode, then reads the
stored version back and fails if its lock mode is not `COMPLIANCE` or its
retain-until is earlier than requested. A normal GitHub artifact is also
uploaded for convenience; it is **not** the durable record.

Dispatch with the full, reviewed 40-character commit SHA. The gate checks out
that exact commit, fails closed if any deploy secret is absent — before
deploying, not after — deploys it, then proves all of the following before
retaining evidence:

1. an unauthenticated `/v1/health` request is rejected (401/403);
2. the same request succeeds with the environment bearer token;
3. `/v1/health` reports the approved commit SHA; and
4. the golden Antalya independent verification reports `PASS`.

Each assertion is recorded separately in the evidence record. An assertion that
was not attempted stays `null` / `NOT_RUN` and fails the verdict exactly like an
assertion that was refuted — `app.ops.smoke.smoke_passed` never treats absence
as success.

The bearer token is read only from the `CONTROLLED_PILOT_TOKEN` environment
variable — never a command-line argument, so it cannot reach a process list —
and never enters the evidence record, which carries status and provenance only.
Rotate the Railway and pilot credentials after a pilot, and remove the
environment reviewer when no release window is active.

A green run does not make the pilot eligible. `controlled_pilot_eligible` and
`production_eligible` are governed by the release manifest and by human
approval, not by this workflow.
