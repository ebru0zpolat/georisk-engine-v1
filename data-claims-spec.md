# Data Infrastructure — Claims Accuracy Spec

**Scope:** `Data Infrastructure` section of the GeoRisk Engine landing page (source cards + section header).
**Status:** Corrective / binding for CI (`tests/test_data_claims_landing.py`).
**Principle:** Every number shown on a source card must be traceable to that source's published specification. If we cannot cite it, we do not display it. Registry tier language must not overstate operational coverage.

---

## 1. The core rule

Two different quantities must never be collapsed into one label (`REFRESH`):

| Quantity | What it is | Whose fact it is |
|---|---|---|
| **Revisit** | How often the sensor observes the same location | The data provider's |
| **Ingest cadence** | How often our pipeline polls, fetches and processes new scenes | Ours |

**Ingest cadence must never be displayed as `REFRESH` on a card headed by a sensor name.**

**Do not display `PIPELINE INGEST` unless implemented and documented in-repo.** This repository uses on-demand connectors with labelled stub fallbacks — there is no six-hour optical ingestion job. Advertising `6hr` pipeline ingest is banned.

---

## 2. Registry honesty (header)

Canonical catalog: `app/core/data_source_registry.py` + `docs/data-sources.md`.

Current tier breakdown (must stay in sync):

| Tier | Count |
|------|------:|
| production | 3 |
| audit | 4 |
| roadmap | 2 |
| **Total** | **9** |

**Required header form:**

> Registry catalogs **9 production, audit and roadmap entries** (3 production · 4 audit · 2 roadmap).

**Banned:**

- “We integrate 9 registered data streams” (implies operational integration of all nine)
- “reconciled against independent sources…” / “cross-validated for accuracy” unless a cited methodology page documents the process
- “30+ authoritative data streams” without a matching register

Landing cards that are **not** registry rows must set `data-tier="roadmap"` and show a Roadmap status/tag. Production/audit cards must set `data-registry-id` to a matching registry entry.

---

## 2b. Page-wide marketing bans (entire `frontend/index.html`)

Beyond the Data Infrastructure section, the homepage must not assert unsupported scale, performance, validation or API surface. Ban (affirmative use):

| Banned claim | Why |
|---|---|
| `47M+` / “Locations Indexed” / “180 Countries” | No global index product in-repo |
| `<200ms` / p99 latency / invented uptime SLA | No published latency/SLA evidence |
| GraphQL / webhooks as available products | REST/OpenAPI only |
| “AI Risk Scoring”, transformer ensembles, “140+ risk factors” | Deterministic scoring; no such model |
| “bank-grade” / “audit-grade” / “independently validated” | Reproducibility ≠ accuracy validation |
| “Real-time risk scores” / live ticker as telemetry | Demo/sample UI only |
| Free-trial “credentials in 60 seconds” | Manual sandbox provisioning |

Denials such as “no GraphQL” are allowed. Keep live / stub / roadmap sources distinct via registry tiers. NL sources (KNMI, Open-Meteo, PDOK AHN, LIWO, Waterinfo) must not be advertised as universally live on this page until those registry rows are merged to `main`.

### Docs section (`#docs`) — binding

The homepage `#docs` section must be a usable documentation overview, not a heading-only stub that loops back to `#api`.

| Required | Rule |
|---|---|
| Base URL | Document the live Railway host `https://api-production-5880.up.railway.app` until a verified custom API hostname resolves |
| Examples | Request/response shapes must match `RiskScoreRequest` / `RiskScoreResponse` (or another live route) |
| Auth | Do not show Bearer/`gre_sk_*` keys unless a production auth gate exists |
| OpenAPI | Linking `…/docs` is allowed while that UI returns HTTP 200 publicly |
| Status labels | Use live / demo / planned; mark `/v1/risk/score` as demo when synthetic/fallback scoring applies |

| Banned in `#docs` / `#api` examples | Why |
|---|---|
| `api.georiskengine.com` as a working base URL | DNS does not resolve today |
| `POST …/v2/score` | Route does not exist |
| Instant API keys / SLA / SDK availability | Not verified |

---

## 3. Verified source specifications (examples)

### Sentinel-2 (Copernicus / ESA) — landing: Roadmap
- **Revisit:** 10 days per satellite; **5 days** constellation at the equator, 2–3 days at mid/high latitudes.
- **Spatial resolution:** 10 / 20 / 60 m.
- **Coverage:** Global land — not open ocean.
- **Spec:** https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-2

### Landsat-9 (NASA / USGS) — thermal audit is registered; optical marketing card is Roadmap
- **Revisit:** 16 days (8 days with Landsat-8).
- **Spec:** https://www.usgs.gov/landsat-missions/landsat-9

### Production registry cards
- ORAS5 — Copernicus CDS
- VIIRS night-time lights — GEE `NASA/VIIRS/002/VNP46A2`
- Sentinel-5P NO₂ — GEE `COPERNICUS/S5P/OFFL/L3_NO2`

---

## 4. Required card shape

```html
<div class="data-card" data-tier="production|audit|roadmap" data-registry-id="…" data-landing-source="…">
  …
  <p class="data-source-cite"><a href="https://…">Provider spec</a></p>
</div>
```

- `data-tier` required on every card.
- `data-registry-id` required when tier is `production` or `audit`.
- `data-source-cite` must include at least one `http(s)` provider link for cards that show numeric provider stats.
- `ingestCadence` / `PIPELINE INGEST` may never render under `REVISIT` / `REFRESH`, and must not appear at all until an ingest job exists.

---

## 5. Acceptance criteria

- [x] No card displays a refresh/revisit figure faster than the named sensor's published revisit.
- [x] No unsupported `6hr` / weekly pipeline-ingest claim on the landing Data section.
- [x] Header uses tier-aware registry language (not “we integrate 9”).
- [x] Unregistered landing sources are labelled Roadmap (or added to the registry with tier + citations).
- [x] No reconciliation / cross-validation claim without methodology citation.
- [x] `/docs/data-sources.md` table row count and tier breakdown match `DATA_SOURCE_REGISTRY`.
- [x] CI enforces the above via `tests/test_data_claims_landing.py`.

---

## 6. Why this matters commercially

A geospatially literate evaluator checks revisit and integration claims in seconds. Inflating “9 streams” or inventing a six-hour optical ingest invites discounting of every other figure. Conservative, citable, tier-aware numbers are the asset; the platform's value is the risk model and audit trail, not an overstated ingest rate.
