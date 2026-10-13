---
name: georisk-vc-builder
description: Build venture-capital and due-diligence memos with GeoRisk Engine physical-risk scores. Use when the user asks for VC memos, physical risk due diligence, asset-level ESG scoring, GeoRisk, facility coordinates (lat/lon), or appendix PDFs for investment materials.
---

# GeoRisk VC Builder

## Role in the stack (read first)

You operate in the **DeerFlow analyst layer**, not the scoring core.

| You (DeerFlow + this skill) | GeoRisk core (MCP `georisk_*` only) |
|-----------------------------|-------------------------------------|
| Research, data QA, narrative | Deterministic scores & scenario JSON |
| Investor memo, market map, client pack | Versioned `audit_id`, reports, disclaimers |
| Scenario **explainability** | Scenario **computation** (`georisk_scenario_run`) |

**MUST NOT** invent `overall_score`, component values, or scenario metrics. **MUST NOT** implement `derive_confidence()` or edit coefficient tables without CI hash bump. **MUST** call tools for every number.

Repo separation doc (if available in sandbox): `docs/architecture/deerflow-georisk-separation.md`.

## Overview

Produce a **VC-style physical-risk appendix** by calling GeoRisk MCP tools (`georisk_*`). GeoRisk Engine is the source of truth; do not invent scores.

## Prerequisites

- GeoRisk API running (default `http://127.0.0.1:8002`)
- MCP server `georisk-engine` enabled in DeerFlow `extensions_config.json`
- Tool reference: `references/api_fields.md`

## UC-01: 1-minute scorecard (first agentic use case)

When the user asks for a quick / indicative / 1-minute scorecard:

1. Call `georisk_preview_scorecard` with `location` (lat,lon · alias · demo id).
2. Present `indicative_climate_risk_score`, `components`, `top_flags`, and `disclaimer`.
3. Offer deep dive via `georisk_score` or `georisk_report_markdown` with resolved coordinates.

Spec: repo `docs/use-cases/one-minute-risk-scorecard.md`.

## UC-02: Scenario-Lab (CMIP6 pathway)

After UC-01 (or full score), call `georisk_scenario_run` with `asset_id` = prior `audit_id`:

```json
{
  "asset_id": "<audit_id>",
  "scenario_config": { "model": "CMIP6", "pathway": "SSP5-8.5", "target_year": 2050, "hazards": ["flood", "drought", "wildfire"] },
  "parameters": { "return_period": [10, 50, 100], "spatial_resolution": "100m" },
  "metadata": { "client_context": "tsrs-compliance-audit", "workflow_id": "deerflow-skill-exec-001" }
}
```

Response: `scenario_scoring` (deterministic — **never recalculate**). Show **baseline_score → scenario_score**, `scenario_delta_points`; if `scenario_delta_pct` is null use **N/A** (Template A/C) or omit row (Template B). `hazard_multiplier_type` is `weighted_effective`; Template A needs `hazard_driver_multipliers` table. Low `confidence` → amber banner (B) or disclosure (C). Report templates: `docs/use-cases/scenario-report-templates.md`.

## Workflow

1. **Collect inputs:** asset name, latitude, longitude; optional sector (`industrial`, `agriculture`), radius_km, language (EN default, TR for customer-facing).
2. **Connectivity:** call `georisk_health`.
3. **Score:** call `georisk_score` with `include_industrial_verification_ref: true` for packaged DD unless the user opts out.
4. **Narrative:** call `georisk_report_markdown` with the same location (industrial bundle on by default).
5. **Optional PDF:** call `georisk_report_pdf`, decode `content_base64`, write under user output dir.
6. **Compose memo:** fill `assets/vc_memo_template.md` using `references/vc_memo_outline.md` and fields from `references/api_fields.md`.
7. **Legal tone:** never claim satellite proxies are regulatory proof. For TR outputs, reference disclaimer in repo path `docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md`.

## Demos

If the user has no coordinates, call `georisk_list_demos` and offer a preset (e.g. `coastal_industrial_med`).

## Bundle script

For deterministic fetch in sandbox:

```bash
python scripts/fetch_georisk_bundle.py \
  --asset-name "Demo Asset" \
  --latitude 36.5 --longitude 35.0 \
  --output-dir /mnt/user-data/outputs/georisk-bundle
```

Requires `GEORISK_BASE_URL` and `httpx` in the sandbox.

## Multi-site portfolios

Loop MCP calls per asset; summarize in a table. Do not average scores without explicit user methodology.
