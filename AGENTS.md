# AGENTS.md

Binding instructions for any coding agent working in this repository (Claude Code, Codex, Cursor, or a human
following the same rules). This file is the **single rule surface**. `.cursor/rules/` and
`.agents/skills/georisk-engine/SKILL.md` are implementation detail and defer to this file and the documents it
links; where they disagree with the documents below, the documents win.

---

## 1. What this repository is, in one paragraph

GeoRisk Engine establishes whether a physical-risk number can be defended — its own, or somebody else's. It is
**not** a hazard model and does not compete on hazard physics. Its value is in its refusals: a conservative
claim algebra, fail-closed source gates, sealed provenance, an independently implemented verifier, and a
machine-readable statement of exactly what evidence is missing. A change that makes a number *better* but
harder to defend is a regression.

Read before non-trivial work, in this order:

1. [`docs/00-master/PRODUCT_CHARTER_V2.md`](docs/00-master/PRODUCT_CHARTER_V2.md) — product identity (binding)
2. [`docs/00-master/ENGINEERING_INVARIANTS.md`](docs/00-master/ENGINEERING_INVARIANTS.md) — INV-01…INV-12 (binding)
3. [`docs/00-master/ROADMAP_VERIFIER_V2.md`](docs/00-master/ROADMAP_VERIFIER_V2.md) — stages and gates
4. [`docs/00-master/WORK_ORDERS.md`](docs/00-master/WORK_ORDERS.md) — the task you were handed
5. [`docs/00-master/GLOSSARY.md`](docs/00-master/GLOSSARY.md) — words with machine meanings

## 2. The rules, compressed

These are the full invariants in short form. The long form, with enforcement and violation examples, is in
[`ENGINEERING_INVARIANTS.md`](docs/00-master/ENGINEERING_INVARIANTS.md). **Never weaken one inside a feature change.**

| # | Rule |
|---|---|
| INV-01 | Claims never promote. A derived value's claim is the weakest of its dependencies. No override exists |
| INV-02 | Fail closed, and name the blocker. A silent refusal is a defect |
| INV-03 | Gate precedence is ordered; a later input never repairs an earlier failure |
| INV-04 | Every synthetic input is labelled, listed in `STUBS.md` with a severity, and ceilings its output at `SYNTHETIC` |
| INV-05 | Provenance travels with the number: source, version, SHA-256, method version, claim state |
| INV-06 | Trail is append-only and hash-chained; sealed artefacts are written once, atomically, with no residue |
| INV-07 | A verifier must not import what it verifies. Written from the method note, never copied from the pipeline |
| INV-08 | Determinism: same inputs + same method version → byte-identical output |
| INV-09 | The claim-vocabulary bridge lowers a `ClaimState` and never raises one; it lives in exactly one module |
| INV-10 | Readiness flags and `production_eligible` change only through a dated decision record |
| INV-11 | Verdicts about third parties are bounded: never "wrong", only "not defensible on the evidence supplied" |
| INV-12 | Language discipline: the words in the glossary mean exactly what the glossary says |

## 3. Never do these

- Introduce a path that raises a claim state, for any reason, including an explicit operator flag.
- Return a default, a zero, or an empty result where evidence is missing. Refuse, with a code.
- Add a fixture, stub or fallback without a `STUBS.md` row carrying a severity and a specific replacement plan.
- Copy pipeline code into a verifier, or import `app.loss` / `app.services` from one.
- Change a `Literal[False]`, a readiness flag or `production_eligible`.
- Present any output of this engine as validated, calibrated, production-eligible, bank-grade or compliant.
- Write a second copy of the claim-state mapping or a blocker code string inline at a call site.
- Start a product-scope hazard-modelling effort (deriving our own flood probability) — charter §4. Published
  heat and extreme-precipitation indicators within the limits of
  [`ADR-0008`](docs/decisions/ADR-0008-product-family-and-own-indicator-engines.md) D2–D4 are Track C, not this.
- Label, chart or price an extreme-precipitation index as a flood hazard (ADR-0008 D2).
- Batch several work orders into one pull request.
- Delete a document to resolve a contradiction. Mark it superseded in place, with a pointer.

## 4. Commands

```bash
source .venv/bin/activate                     # Python 3.12; always activate first
PYTHONPATH=. pytest -q --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key
```

The deselected test opens a live connection to `cds.climate.copernicus.eu` and hangs on a network-restricted
machine. **Do not hardcode a test count in any document** — it was wrong for months. Record pass/fail counts in
a PR description with the SHA they were measured at.

Baseline measured 19 September 2026 on a dirty working tree: **2152 passed, 3 failed, 2 skipped, 45s**. The
three failures are characterised in [`GAP_ANALYSIS_2026-09-19.md`](docs/00-master/GAP_ANALYSIS_2026-09-19.md) §0
and owned by WO-00.

Other checks:

```bash
cd frontend && npx eslint . && npx tsc -b     # only if you touched frontend/
```

## 5. Repository map — what matters for Track A

| Area | Path | Note |
|---|---|---|
| Claim algebra | `app/loss/claim_state.py` | The grammar every verdict speaks |
| Fail-closed ladder | `app/regulation/verify.py` | Reference implementation of ordered precedence |
| Trail | `app/services/audit_trail.py` | `compute_record_hash`, `verify_chain` |
| Independent verifier (own numbers) | `tests/verification/independent_eal.py` | Stdlib only; must not import `app.loss` |
| Source qualification | `app/loss/flood_source_qualification.py` | Licence/datum/coverage evidence, fail-closed |
| Datum guard | `app/loss/flood_hazard_map.py` | `assert_differenceable`, `FLOOD_DATUM_MISMATCH` |
| Band semantics | `app/loss/ldo_band_semantics.py` | `-9999.0` / `-999.999` sentinels; `value > 0.0` invariant |
| Evidence + claims grammar | `app/research/vera_rap/` | Isolated by design; bridged one-way only (INV-09) |
| Benchmark | `benchmarks/vera_rap/` | EvidenceBoundBench |
| Gap ranking | `app/resilience/triage.py` | `sole_blocker_value` is the primary key; never sum `value_at_stake` |
| Verification (to be built) | `app/verification/` | WO-06 onward; import restrictions in the specs |
| Stub inventory | `STUBS.md` | Also the verifier's own test corpus |

Demoted, and not to be extended: `/v1/risk/score` and `app/scoring/` (every number synthetic — `STUBS.md` #3),
Scenario-Lab, ORAS5, night-lights/NO₂ audits, and `frontend/` except the P0 design canvas work re-admitted by
ADR-0008 D5 (Track D). See
[`PRUNE_LIST.md`](docs/00-master/PRUNE_LIST.md).

## 6. Pull-request checklist

- [ ] One work order, one PR. The WO id is in the title
- [ ] Full suite green with the deselect above; counts and SHA in the description
- [ ] Invariants touched are named in the description
- [ ] Every new invariant has a test that fails when the invariant is removed
- [ ] New synthetic inputs have a `STUBS.md` row with severity and a specific replacement plan
- [ ] No readiness flag, `Literal[False]` or `production_eligible` changed
- [ ] No new claim-promotion path; no silent refusal
- [ ] Documents contradicted by this change are updated or banner-marked in the same PR

## 7. Scope notes

- Third-party scraping stacks are out of scope. Use official APIs, or user-approved tools outside the repo;
  respect robots.txt and terms of service.
- Turkish methodology and disclaimers under `docs/turkiye/` stay conservative: satellite proxies are not
  regulatory proof. No Turkish hazard value exists in this repository; every Turkish output is `NOT_QUALIFIED`.
- Country-specific data, curves, regulation mapping and templates live in versioned Country Packs, never
  hard-coded into the core.

---

## 8. Environment and services (unchanged, carried from the previous AGENTS.md)

### Services overview

| Service | Port | Command |
|---------|------|---------|
| FastAPI backend | 8002 | `source .venv/bin/activate && uvicorn app.main:app --reload --port 8002` |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev` |
| Streamlit dashboard (optional) | 8501 | `source .venv/bin/activate && streamlit run dashboard/streamlit_app.py` |

### Key dev environment notes

- **Python venv**: always `source .venv/bin/activate` before backend, tests or scripts.
- **Tests**: `PYTHONPATH=. pytest` from the workspace root. No env vars needed — `tests/conftest.py` defaults
  `DATABASE_URL` to in-memory SQLite.
- **Database is optional, not absent**: scoring is stateless and the API starts with no database (`/health`
  reports `db: "skipped"` when `database_url` is unset — `app/main.py:117-126`). A SQLAlchemy async layer does
  exist (`app/db/`, `app/storage/case_repository.py`) with an Alembic migration; `/v1/cases` requires a session.
- **No Docker required**: no Dockerfiles exist; the app runs directly on the host.

### Gotchas

- `.env` `CORS_ORIGINS` must be a JSON array (`["http://localhost:5173"]`), not comma-separated —
  pydantic-settings v2 parsing for `list[str]`.
- `httpx` is required for `starlette.testclient.TestClient` tests; pinned in `requirements.txt`.
- GEE and ORAS5 connectors fall back to built-in placeholders when credentials are absent, in
  `APP_ENV` local/dev/test/demo only. Production refuses the stub (`CONNECTOR_STUB_PROHIBITED`), stub responses
  set `data_mode=stub`, `production_eligible=false`.
- ORAS5: set `ORAS5_ZARR_URL` (and optionally `ORAS5_ZARR_OPERATIONAL_URL`); both require `CDSAPI_KEY`. GEE:
  `GEE_PROJECT` + `GEE_ENABLED=true`, optionally `GEE_SERVICE_ACCOUNT_JSON`. Never commit project ids or keys.
- WeasyPrint PDF generation needs `libpango` / `libcairo`; the PDF endpoint falls back to a simple text PDF.
