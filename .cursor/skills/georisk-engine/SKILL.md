---
name: georisk-engine
description: >-
  FastAPI GeoRisk Engine — physical climate risk scoring and financial-impact
  workflows (ORAS5 / Zarr + GEE fallbacks), industrial_verification bundle,
  Markdown/HTML/PDF reports, CCO operational audits (Landsat + S5P), Streamlit
  audit dashboard, docs/turkiye methodology, examples under docs/turkiye/examples,
  pytest/CI hygiene. Use for any work in this repo: API, connectors, scripts,
  frontend, documentation, PR prep, or Earth Engine audit code.
---

# GeoRisk Engine (single workspace skill)

This file consolidates **implementation** conventions for this codebase (layout, APIs, connectors, tests). Product identity and architecture constraints are **not** restated here — follow the binding sources below.

## Binding product & architecture (do not duplicate)

- Full directive: [`GEORISK_ENGINE_REPOSITIONING.md`](../../../GEORISK_ENGINE_REPOSITIONING.md)
- Always-apply Cursor rule: [`.cursor/rules/georisk-repositioning.mdc`](../../rules/georisk-repositioning.mdc)

Read those before large tasks. When they conflict with older docs or copy in this skill’s scope areas, the directive and rule win.

Third-party scraping stacks are **out of scope** here — use official APIs (CDS, EE, internal HTTP), MCP `web_fetch`, or user-approved tools outside the repo when public web capture is needed; respect robots.txt and ToS.

## DeerFlow boundary (VC-builder)

- **GeoRisk core (this repo):** deterministic, versioned, auditable scoring in `app/` — `audit_id`, `app/scoring/`, connectors, `/v1/risk/*`, `/v1/scenario/run`.
- **DeerFlow (external):** SuperAgent harness for research, memos, QA, client output, scenario *explanation* — `integrations/deerflow/` ships MCP + skill only; never duplicate scoring in skill code.
- Canonical separation: `docs/architecture/deerflow-georisk-separation.md`.

## Scope

- **Backend:** Python **FastAPI** + **Pydantic** under `app/`.
- **Docs / tone:** Turkish methodology and disclaimers under `docs/turkiye/` — conservative legal framing; satellite proxies are **not** regulatory proof.
- **Sectors:** `app/core/sector_registry.py` lists **registered** ids; follow **`docs/turkiye/sector-extensions.md`** when adding a sector (registry + demo preset + tests + docs in one slice). The API still accepts any `sector` string for forward compatibility.

## Layout (high signal)

| Area | Path |
|------|------|
| API routers | `app/api/` — `risk.py`, `report.py`, `demo.py`, `health.py`, `gee.py`, `oras5.py` |
| Config | `app/core/config.py` — GEE, ORAS5 Zarr URL, CORS, `industrial_verification_max_match_km`, … |
| Sector registry | `app/core/sector_registry.py` — `REGISTERED_SECTOR_IDS`, `DEFAULT_SECTOR_ID` |
| Sector extension checklist | `docs/turkiye/sector-extensions.md` |
| Risk scoring | `app/services/risk_service.py`, `app/scoring/` — `risk_score.calibrate_component_vector` + `_SECTOR_COMPONENT_MULTIPLIERS`; `agriculture_surface.attach_agriculture_proxies_to_gee_dict` fills `GeeFeatures.ndvi_mean` / `soil_moisture_proxy` (stub until GEE) |
| Industrial bundle | `app/services/industrial_verification_ref.py`, `app/schemas/industrial_verification.py` |
| Report output | `app/reports/markdown.py`, `pdf_report.py`, `templates/risk_report.html` |
| Operational audit (CCO) | `scripts/run_audit.py`, `run_integrated_audit.py`, `report_engine.py`, `landsat_thermal_audit.py`, `s5p_no2_audit.py` |
| Templates / snippets | `docs/turkiye/templates/`, `docs/turkiye/snippets/` |
| Committed samples | `docs/turkiye/examples/` — e.g. regenerate `cimsa_afyon_*_operational_plus_risk_bundle.md` via `scripts/generate_docs_operational_risk_bundle_example.py` |
| Dashboard | `scripts/audit_dashboard.py` (Streamlit + PyDeck); `dashboard/` helpers |
| Frontend | `frontend/` — npm toolchain separate from Python |

## API product rules

- **`POST /v1/risk/score`:** `RiskScoreRequest` — `include_industrial_verification_ref` default **false**.
- **`POST /v1/reports/risk`** and **`POST /v1/reports/risk/pdf`:** `RiskReportRequest` — same body shape; `include_industrial_verification_ref` default **true** (client may set `false` to omit from report).
- **`industrial_verification.linked_audit_id`** must equal **`audit_id`** on the same `RiskScoreResponse`.
- Nearest Primary Audit: `docs/turkiye/transformers/primary_audit_facilities.geojson` + `settings.industrial_verification_max_match_km`; pipeline list is static catalog text, not an extra EE call.

## Connectors and data planes

### ORAS5 / Zarr (`app/connectors/cds_oras5.py`)

- If **`ORAS5_ZARR_URL`** (or configured equivalent) is **unset**, the connector returns **`_fallback_features()`** in `APP_ENV` local/dev/test/demo — tests and local runs work without network; scores are still coherent for CI. Stub API responses set `data_mode=stub`, `production_eligible=false`. **`APP_ENV=production` refuses this path** (startup reject + `CONNECTOR_STUB_PROHIBITED`).
- When wiring real Zarr: variable names may need alignment with the actual CDS store schema after inspection — follow existing `_find_var` patterns; do not hardcode secrets or full URLs into committed prose.

### Earth Engine (`app/connectors/gee.py`, audit scripts)

- If GEE is **disabled** or **project id missing**, **`_fallback_features()`** is used in local/dev/test/demo — **never assume** live EE in CI or agent sandboxes. Production refuses the stub (`CONNECTOR_STUB_PROHIBITED`).
- **Identity:** read `GEE_PROJECT` / `GEE_PROJECT_ID` from environment only; **do not** commit project IDs into the repo.
- **New EE logic:** prefer extending **existing** patterns in `gee.py`, `landsat_thermal_audit.py`, `s5p_no2_audit.py` rather than new ad-hoc `ee.*` modules — keeps mask policies and date semantics aligned with `docs/turkiye/cco-audit-methodology.md`.
- **Offline audit demos:** `AUDIT_USE_MOCK=true` skips EE RPC; thermal/NO₂ mocks live in the respective audit modules.

## Operational reports and PDF

- **Markdown body:** `scripts/report_engine.render_cimsa_afyon_report` + optional methodology footer from `docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md`.
- **Operational PDF:** pandoc + TeX path (see `scripts/report_engine.py` docstring); `REPORT_ENGINE_SKIP_PDF` / `REPORT_ENGINE_PDF_ENGINE` env vars.
- **API PDF:** `app/reports/pdf_report.py` — WeasyPrint when available; **`_build_simple_pdf_report`** fallback must stay in sync when response fields change.

## Streamlit dashboard

- Entry: `streamlit run scripts/audit_dashboard.py` (see `scripts/README.md`).
- Respect existing tabs (CCO map, whitepaper link, transformer sealed paths); heavy new UI should match current layout/spacing patterns.
- `dashboard/` loaders parse `reports/output/*.md` when present — changing Markdown table shapes may require parser updates.

## Frontend

- `cd frontend && npm install && npm run dev` — keep `index.html` / `src/heroScorecard.ts` in sync when `RiskScoreResponse` or preview payloads gain fields.

## Tests, PRs, and change hygiene

```bash
PYTHONPATH=. pytest
```

- Run **pytest** (and any project lint/typecheck the team uses) before considering a change merge-ready.
- Prefer **small, reviewable PRs**: split unrelated concerns (e.g. risk API vs operational audit script vs `frontend/` vs large `docs/turkiye` rewrites).
- **Focused diffs** — match existing naming, imports, and Pydantic v2 style in `app/schemas/`.
- When response shapes change: update **OpenAPI-visible schemas**, **report Markdown/HTML/PDF**, **demo** preset if applicable, and **tests** in one pass.

## Documentation and language

- **Single source for legal/methodology tone:** `docs/turkiye/cco-audit-methodology.md`, sealed / closed-loop publishing notes, sector priorities — if disclaimer language changes, update **source doc first**, then snippets/templates/examples (`docs/turkiye/snippets/`, `docs/turkiye/examples/`, report footers).
- **Language:** match the file being edited (EN code/comments vs TR customer-facing Markdown as already established).

## Archives and immutability

- Quarterly / QOR layout and policies: `data/archive/`, `docs/standards/github-archive-and-immutability.md` — copy, do not rewrite sealed artefacts in place.

## Cursor rules vs this skill

- **This skill:** workflow + architecture context for the agent in-repo.
- **`.cursor/rules` or `AGENTS.md`:** one-line always-on constraints (e.g. “never commit `GEE_PROJECT`”). Add rules when the same reminder repeats across sessions.
