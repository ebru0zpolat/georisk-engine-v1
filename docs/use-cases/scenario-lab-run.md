# UC-02: Scenario-Lab run (CMIP6 pathway stress)

**Layer:** Scenario-Lab (Layer 2)  
**API:** `POST /v1/scenario/run`  
**Prerequisite:** `asset_id` = `audit_id` from `POST /v1/risk/preview` or `POST /v1/risk/score`

---

## Request (contract)

```json
{
  "asset_id": "uuid-v4-string",
  "scenario_config": {
    "model": "CMIP6",
    "pathway": "SSP5-8.5",
    "target_year": 2050,
    "hazards": ["flood", "drought", "wildfire"]
  },
  "parameters": {
    "return_period": [10, 50, 100],
    "spatial_resolution": "100m"
  },
  "metadata": {
    "client_context": "tsrs-compliance-audit",
    "workflow_id": "deerflow-skill-exec-001"
  }
}
```

| Field | Notes |
|-------|--------|
| `asset_id` | GeoRisk Core `audit_id` (in-process snapshot registry in v1) |
| `scenario_config.model` | `CMIP6` only (v1) |
| `scenario_config.pathway` | `SSP1-2.6`, `SSP2-4.5`, `SSP5-8.5` |
| `scenario_config.hazards` | `flood`, `drought`, `wildfire`, `heat`, `storm_surge`, `cyclone` |
| `parameters.return_period` | Positive integers (e.g. 10, 50, 100) |
| `parameters.spatial_resolution` | Product label (e.g. `100m`) — indicative tier, not guaranteed grid |

---

## Deterministic scoring (`scenario_scoring`)

Versioned hazard-only SSP uplift — **not** a global `1.4×` on final baseline. See [scenario-scoring-v1.md](../architecture/scenario-scoring-v1.md).

Enterprise-facing fields: `baseline_score`, `scenario_score`, `scenario_delta_points`, `drivers`, `coefficient_table_version`.

## Response (contract)

Example: [`examples/scenario-run-response.json`](./examples/scenario-run-response.json) (agentic layer; add `scenario_scoring` from live API).

```json
{
  "scenario_id": "scen_8842_x",
  "status": "completed",
  "hazard_results": {
    "flood": {
      "severity_index": 0.72,
      "affected_fraction": 0.15,
      "return_periods": { "10y": 0.4, "50y": 0.65, "100y": 0.85 }
    }
  },
  "shocks": {
    "correlated_events": ["supply_chain_disruption", "energy_price_spike"],
    "systemic_risk_score": 0.64
  },
  "propagation": {
    "node": "facility_a",
    "impact_path": [
      { "tier": "direct", "target": "production_capacity", "loss": 0.20 },
      { "tier": "supply_chain_tier1", "target": "logistics_hub_istanbul", "loss": 0.08 }
    ]
  },
  "audit_context": {
    "linked_audit_ids": ["AUD-2026-XXXXXX"],
    "disclaimer": "v1 Deterministic Engine - Results based on core baseline snapshot."
  }
}
```

| Field | Notes |
|-------|--------|
| `scenario_id` | Run id (`scen_XXXX_x`) |
| `status` | `completed` for sync v1 |
| `hazard_results` | Map keyed by hazard id |
| `shocks.correlated_events` | Named systemic drivers |
| `propagation.impact_path` | Tiered loss chain |
| `audit_context.linked_audit_ids` | Labels derived from Core `audit_id` |

v1 engine is **deterministic stub** keyed off Core baseline score; replace with CMIP6 downscaling service in v2.

---

## Example flow

```bash
# 1) Core scorecard
AUDIT=$(curl -s -X POST http://localhost:8002/v1/risk/preview \
  -H "Content-Type: application/json" \
  -d '{"location": "36.85, 30.75"}' | jq -r '.audit_id')

# 2) Scenario-Lab
curl -s -X POST http://localhost:8002/v1/scenario/run \
  -H "Content-Type: application/json" \
  -d "{
    \"asset_id\": \"$AUDIT\",
    \"scenario_config\": {
      \"model\": \"CMIP6\",
      \"pathway\": \"SSP5-8.5\",
      \"target_year\": 2050,
      \"hazards\": [\"flood\", \"drought\", \"wildfire\"]
    },
    \"parameters\": { \"return_period\": [10, 50, 100], \"spatial_resolution\": \"100m\" },
    \"metadata\": { \"client_context\": \"tsrs-compliance-audit\", \"workflow_id\": \"deerflow-skill-exec-001\" }
  }" | jq '.scenario_id, .hazard_results.flood.severity_index, .shocks.systemic_risk_score'
```

---

## DeerFlow

MCP tool: `georisk_scenario_run` (pass `asset_id` + JSON fields). Compose with UC-01 preview, then narrate propagation for committee memos.
