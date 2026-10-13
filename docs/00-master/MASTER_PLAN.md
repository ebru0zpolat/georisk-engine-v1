# GeoRisk Engine — Master Plan

> **Canonical execution model (25 August 2026):**
> [`FOUNDER_AUTOMATION_OPERATING_ROADMAP.md`](FOUNDER_AUTOMATION_OPERATING_ROADMAP.md) replaces daily
> founder actions, manual status copying and routine PR approval. This snapshot is a projection of
> repository evidence; until the phased workflows exist and have verified default-branch runs,
> reconciliation remains documented rather than operational.


**Version:** 2026-08-21 (workstream rows and test bar re-verified against `main` at `836a55a`)  
**Rule:** Every Claude / Cursor session starts here. Do not open PRs or edit production paths without checking workstream status below.

---

## Workstream status (snapshot)

| ID | Workstream | Status | Branch / PR | Owner tool |
|----|------------|--------|-------------|------------|
| WS-01 | Scenario scoring (GEO-150) | **Done on `main`** | PR #23 merged | — |
| WS-02 | Geospatial epic (GEO-188–192) | **Done on `main`** | #34–36 merged | Claude Code |
| WS-03 | Validation layer (VAL-005/006) | **Done on `main`** | merged via val branch | Claude Code |
| WS-04 | Frontend SEO + FAQ | **Done on `main`** | #37 closed unmerged; `llms.txt`, `robots.txt`, `sitemap.xml` shipped separately | Cursor |
| WS-05 | Data source LOI package | **Done on `main`** | #30 closed unmerged; `app/core/data_source_registry.py` + `GET /v1/data-sources` are live | Human + Claude |
| WS-06 | Copernicus CDS live ORAS5 | **Blocked — human** | `.env` only | **You (15 min)** |
| WS-07 | Partner LOI (Tomorrow.io, S&P) | **Not sent** | — | **You** |
| WS-08 | Vercel production deploy | Config present | `vercel.json` | CI + human |
| WS-09 | Linear board sync | **Synced 21 Aug 2026** | Connector authorized; see [LINEAR_RECONCILIATION.md](LINEAR_RECONCILIATION.md) | Claude Code |

**Test bar on `main`:** `PYTHONPATH=. pytest` → **831 passed, 1 deselected in ~11s** at `836a55a`.
The deselected test is the non-hermetic live-CDS one; see [AGENTS.md](../../AGENTS.md). CI runs the
full suite on Python 3.12 and is green on `836a55a`.

---

## Critical path — next 30 days

| Day | Milestone | Action | Doc |
|-----|-----------|--------|-----|
| **D0** | CDS credentials | Register at CDS, copy API key → `.env` `CDSAPI_KEY`, optional `ORAS5_ZARR_URL` | [README § ORAS5](../../README.md), [08-ops/CI_RULES.md](../08-ops/CI_RULES.md) |
| **D0** | LOI outreach | Send Tomorrow.io LOI email (template in LOI_TRACKER) | [04-investor/LOI_TRACKER.md](../04-investor/LOI_TRACKER.md) |
| **D0–1** | SEO verify | ~~Merge PR #37~~ — closed unmerged, SEO artifacts already on `main`. Verify JSON-LD + FAQ in the production build | [07-seo/KEYWORD_MAP.md](../07-seo/KEYWORD_MAP.md) |
| **D1–3** | ORAS5 live smoke | `POST /v1/oras5/features` with real Zarr URL (not fallback) | `app/connectors/cds_oras5.py` |
| **D3–7** | GSC baseline | Submit sitemap, validate FAQ rich results | KEYWORD_MAP |
| **D7–14** | Pilot LOI close | Tomorrow.io + 1 bank/asset-manager intro | LOI_TRACKER, [05-commercial/ICP.md](../05-commercial/ICP.md) |
| **D14–21** | Institution tier demo | Scenario-Lab + validation API walkthrough | SCORING_PIPELINE, scenario-lab docs |
| **D21–30** | Series A materials | Update deck with live CDS + 2 LOI letters | LOI_TRACKER checklist |

---

## Tool assignment

| Task type | Tool | Notes |
|-----------|------|-------|
| Spec-first backend PRs | **Claude Code** | Read `01-product/SCORING_PIPELINE.md` before touching `app/scoring/` |
| Frontend marketing / SEO | **Cursor** | Read `03-frontend/APP_TSX_MAP.md` — avoid demo-widget logic |
| Copernicus CDS signup | **Human** | Secrets never committed; `.env.example` only |
| LOI / investor email | **Human** | Templates in `04-investor/` |
| pytest / mypy CI | **Claude Code or CI** | Gates in `08-ops/CI_RULES.md` |
| DeerFlow narratives | **DeerFlow MCP** | **Never** duplicate scoring — see `docs/architecture/deerflow-georisk-separation.md` |

---

## Context file index

| Path | Purpose |
|------|---------|
| [01-product/SCORING_PIPELINE.md](../01-product/SCORING_PIPELINE.md) | `apply_cap_pipeline()`, golden G-002→G-007, DeerFlow boundary |
| [03-frontend/LANDING_MAP.md](../03-frontend/LANDING_MAP.md) | Landing map — what serves `/`, claim chips, hero scorecard, breakpoints |
| [04-investor/LOI_TRACKER.md](../04-investor/LOI_TRACKER.md) | Tomorrow.io, S&P, Copernicus, Series A |
| [05-commercial/ICP.md](../05-commercial/ICP.md) | ICP, 5-touch sequence, 50-account plan |
| [07-seo/KEYWORD_MAP.md](../07-seo/KEYWORD_MAP.md) | H1/H2, FAQ pairs, GSC checklist |
| [08-ops/CI_RULES.md](../08-ops/CI_RULES.md) | Merge gates, Vercel deploy, smoke script |

---

## Top 3 actions right now

1. **Copernicus CDS key (~15 min)** — [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu/) → Profile → API key → `.env` as `CDSAPI_KEY`. Enables ERA5/raster live path in GEO-191.
2. **LOI email to Tomorrow.io** — Draft in `04-investor/LOI_TRACKER.md` § Tomorrow.io; send from founder inbox this week.
3. **GEO-150 merge** — **Already on `main`** (PR #23 merged). No action unless regressions appear — re-run `tests/scoring/test_scenario_scoring_golden.py`.

---

## Automated session contract

- Read this file and the canonical operating roadmap.
- Confirm the exact target-branch head; stale-head work AUTO-BLOCKs.
- Run required checks and retain SHA-bound evidence automatically.
- Project verified repository status to this plan and Linear; do not copy it manually.
- Apply the low-risk auto-merge allowlist or queue one protected founder decision; never push
  secrets or infer permission.
