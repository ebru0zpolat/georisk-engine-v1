# UC-01: Get a 1-Minute Risk Scorecard

**Layer:** Agentic research & reporting (first use case)  
**Status:** v1 implemented  
**API:** `POST /v1/risk/preview`  
**Client:** `computePreviewRiskScore` (frontend), `georisk_preview_scorecard` (MCP)

---

## User story

As an analyst or DeerFlow agent, I enter a **coordinate or address** and receive an **indicative climate risk scorecard** in under a minute—composite score, component bars, flags, and disclaimer—without running a full DD report pipeline.

---

## Inputs

| Field | Required | Examples |
|-------|----------|----------|
| `location` | Yes | `36.85, 30.75` · `houston ship channel` · `coastal_industrial_med` |
| `asset_name` | No | Override display name |
| `radius_km` | No (default 10) | Assessment radius |
| `sector` | No (default `industrial`) | Sector label |

**Resolution order:** coordinates → demo asset id → curated address alias → optional Nominatim (`GEORISK_GEOCODER=nominatim`).

---

## Output (`PreviewRiskScorecard`)

| Field | Meaning |
|-------|---------|
| `indicative_climate_risk_score` | Composite 0–100 (indicative) |
| `risk_band` | low / moderate / high / critical |
| `components` | Six component scores with labels |
| `top_flags` | Up to five driver flags |
| `disclaimer` | Non-regulatory, non-advice framing |
| `audit_id` | Trace id for deep-dive endpoints |
| `deep_dive_endpoints` | `/v1/risk/score`, reports |

---

## Examples

```bash
curl -s -X POST http://localhost:8002/v1/risk/preview \
  -H "Content-Type: application/json" \
  -d '{"location": "39.97, 32.74"}' | jq '.indicative_climate_risk_score, .risk_band'
```

```typescript
import { computePreviewRiskScore } from "./computePreviewRiskScore";

const card = await computePreviewRiskScore({ location: "coastal_industrial_med" });
console.log(card.indicative_climate_risk_score, card.headline);
```

**DeerFlow prompt:** *Get a 1-minute risk scorecard for 36.85, 30.75 and summarize for a VC memo appendix.*

---

## Deep dive

After preview, call full score or report endpoints with resolved coordinates. Industrial verification bundle is **off** on preview for speed; enable on `POST /v1/risk/score` or reports.

---

## Related

- Implementation: `app/services/preview_risk_service.py`, `app/services/location_resolver.py`
- MCP: `integrations/deerflow/mcp_server`
