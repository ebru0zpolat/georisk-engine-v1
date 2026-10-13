# CI rules, merge gates & deploy

> **Automation policy (25 August 2026):** The canonical execution classes, exact-head
> requirements, allowlist/exclusions, retry/timeout/evidence controls and notification behaviour
> are defined in [`config/automation-policy.yml`](../../config/automation-policy.yml) and the
> [founder-autonomous roadmap](../00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md). These rules
> are documented, not operational, until the corresponding default-branch workflow has a verified
> controlled or scheduled run.

**Applies to:** `main` branch · all PRs

---

## Merge gates (required)

| Gate | Command | Must pass |
|------|---------|-----------|
| Python tests | `python3 -m pytest -q` | All collected hermetic tests |
| Geo golden | `python3 -m pytest tests/scoring/test_scenario_scoring_golden.py -q` | All G-002→G-007 |
| Portfolio golden (Antalya) | `python3 -m pytest tests/portfolios/test_golden_antalya_regression.py -q` | 100 assets; EAL/score within baseline tolerances |
| Portfolio golden (Rotterdam port) | `python3 -m pytest tests/portfolios/test_golden_rotterdam_port_regression.py -q` | 100 assets; EUR; same stub pipeline; not pack-nl |
| Geo import boundary | `python3 -m pytest tests/test_geo_import_boundary.py -q` | No external concrete geo imports |
| mypy (geo) | `python3 -m mypy app/geo` | Clean (strict) |
| Coefficient hash | `python3 scripts/verify_coefficient_hash.py` | Manifest match |

Antalya and Rotterdam-port golden artefacts live under `data/portfolios/golden/`. After intentional methodology changes regenerate with `PYTHONPATH=. python scripts/generate_golden_antalya_portfolio.py` and/or `PYTHONPATH=. python scripts/generate_golden_rotterdam_port_portfolio.py` and commit GeoJSON + baseline together.

**Optional but recommended before frontend PR:**

```bash
cd frontend && npm ci && npm run build
```

---

## PR hygiene

- Branch prefix: `cursor/<descriptive-name>-2a31`
- No secrets in commits (`.env`, CDS keys, GEE project IDs)
- Scoring changes require `coefficient_table_version` bump if JSON changes
- Frontend marketing: read `docs/03-frontend/APP_TSX_MAP.md` first

---

## Vercel deploy checklist

Config: [`vercel.json`](../../vercel.json)

| Step | Action |
|------|--------|
| 1 | Connect repo to Vercel project |
| 2 | Root directory: repo root (build uses `--prefix frontend`) |
| 3 | Env vars (if preview calls API): `VITE_API_BASE` or proxy to backend |
| 4 | Production domain: `georiskengine.com` |
| 5 | Post-deploy: run smoke script below |
| 6 | Confirm `frontend/index.html` meta + App bundle both served |

**Install/build commands (from vercel.json):**

- `npm ci --prefix frontend`
- `npm run build --prefix frontend`
- Output: `frontend/dist`

---

## Smoke test script

Run after deploy or local `npm run build`:

```bash
#!/usr/bin/env bash
# scripts/smoke_frontend.sh
set -euo pipefail

BASE="${1:-http://localhost:4173}"
echo "Smoke testing ${BASE}"

# 1. HTML shell
curl -fsS "${BASE}/" | grep -q "GeoRisk Engine"

# 2. Built assets exist (production)
if [[ -d frontend/dist ]]; then
  test -f frontend/dist/index.html
  echo "OK: dist/index.html present"
fi

# 3. API health (if backend running)
API="${API_BASE:-http://127.0.0.1:8002}"
if curl -fsS "${API}/health" >/dev/null 2>&1; then
  curl -fsS "${API}/health" | grep -q '"status"'
  curl -fsS "${API}/openapi.json" | grep -q '/v1/risk/score'
  curl -fsS "${API}/openapi.json" | grep -q '/v1/scenario/run'
  echo "OK: API health + openapi"
else
  echo "SKIP: API not reachable at ${API}"
fi

# 4. pytest quick gate (CI)
python3 -m pytest tests/scoring/test_scenario_scoring_golden.py -q --tb=no

echo "Smoke passed."
```

Make executable: `chmod +x scripts/smoke_frontend.sh`

**Local preview:**

```bash
cd frontend && npm run build && npm run preview
# other terminal:
./scripts/smoke_frontend.sh http://localhost:4173
```

---

## Failure response

| Failure | Action |
|---------|--------|
| Golden test red | Do not merge; fix scoring or revert coefficient change |
| Import boundary violation | Import from `app.geo.interfaces` only |
| Vercel build fail | Check Node version; run `npm ci --prefix frontend` locally |
| API smoke skip | Expected if backend not deployed; run full pytest locally |

Failures are **AUTO-BLOCK**: use bounded retry, upsert one deduplicated blocker and continue
unrelated lanes. They do not request immediate founder review. Routine allowlisted changes may be
**AUTO-PASS** only after all policy gates pass against the exact head. Protected paths and
boundaries are **FOUNDER-DECISION** because they alter security, scientific, legal, privacy,
financial, customer, production or control-plane risk; they are bundled into the Friday digest.
