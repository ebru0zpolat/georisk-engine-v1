# Scenario scoring v1 — hazard-only SSP uplift

**Status:** Implemented (`scenario_coefficients_v1.0`)  
**Pipeline:** `app/scoring/scenario_pipeline.py` (`apply_cap_pipeline` → dict)  
**Orchestration:** `app/scoring/scenario_score.py` (`compute_scenario_score`)  
**Guarantee (GEO-150):** Identical output when all match:

`asset_id` + `asset_geometry_hash` + `data_snapshot_id` + `model_version` + `scenario` + `horizon` + `coefficient_table_version` + `coefficient_table_hash`

Golden fixtures: `tests/scoring/test_scenario_scoring_golden.py` (G-002 … G-007, merge-blocking).

---

## Design principle

| Concept | v1 policy |
|---------|-----------|
| `baseline_score` | Scenario-independent Core snapshot (`overall_score` at score time) |
| SSP pathway | Modifies **hazard component only**, not exposure / vulnerability |
| Final composition | `0.55×hazard + 0.25×exposure + 0.20×vulnerability` |
| Global `SSP5-8.5 = 1.4× final` | **Rejected** — causes saturation and weak explainability |
| Scenario delta cap | **+25 points** max vs baseline |

---

## Formula

```
raw_adjusted_hazard = hazard_score × weighted_effective_multiplier
adjusted_hazard_score = min(raw_adjusted_hazard, 100)
raw_scenario_score = 0.55×adjusted_hazard + 0.25×exposure + 0.20×vulnerability
capped_delta = clamp(raw_scenario_score - baseline, 0, 25)
scenario_score = min(baseline + capped_delta, 100)
```

`hazard_multiplier` = **weighted_effective** (equal mean of `hazard_driver_multipliers`). Per-driver table in response; Template A requires driver breakdown, Template B one-line note only.

**H-E-V mapping (from Core components):**

| Pillar | Components |
|--------|------------|
| Hazard | `ocean`, `pollution`, `land` |
| Exposure | `industrial` |
| Vulnerability | `agriculture`, `sensitivity` |

---

## Coefficient table

File: `app/scoring/data/scenario_coefficients_v1.json`  
Version label: `scenario_coefficients_v1.0`

Default horizon bands (when hazard-specific row missing): 2030 / 2050 / 2100 with SSP2-4.5 and SSP5-8.5 uplifts. Per-hazard rows for `heat`, `flood`, `wildfire`, `drought`, `storm_surge`, `cyclone`.

**DeerFlow:** May *propose* coefficient research updates; production merge requires human review, tests, and `coefficient_table_version` bump.

---

## API surface

`POST /v1/scenario/run` returns `scenario_scoring` alongside agentic `hazard_results` / `propagation`:

```json
{
  "scenario_scoring": {
    "asset_id": "...",
    "model_version": "risk-score-v0.1",
    "data_snapshot_id": "hazard_layers_2026_05",
    "coefficient_table_version": "scenario_coefficients_v1.0",
    "baseline_score": 60,
    "scenario": "SSP5-8.5",
    "horizon": 2050,
    "hazard_score": 60,
    "exposure_score": 60,
    "vulnerability_score": 60,
    "hazard_multiplier": 1.35,
    "adjusted_hazard_score": 81,
    "scenario_score": 72,
    "scenario_delta_points": 12,
    "scenario_delta_pct": 20.0,
    "confidence": "medium",
    "drivers": ["pluvial_flood", "drought_stress", "wildfire"]
  }
}
```

---

## Product narrative (enterprise / VC)

> V1 keeps baseline as a deterministic, scenario-independent snapshot. SSP pathways apply versioned, horizon-specific uplifts to the **hazard** pillar only. For 2050, SSP5-8.5 typically moves the hazard multiplier into the **1.25×–1.45×** band (default blend up to **1.35×** via coefficient table). Expected final-score spread vs baseline is often **+5 to +15 points** because exposure and vulnerability stay fixed in v1.

Buyers see **decision signals** (baseline vs scenario scores, spread, drivers), not raw multipliers alone.

---

## DeerFlow vs Core (process fit)

| Process | DeerFlow? | Core? |
|---------|-----------|-------|
| Climate / IPCC / CMIP6 literature research | Yes | No |
| Geospatial data QA | Yes | No |
| Scenario coefficient *proposal* | Yes (human approval to merge) | Table in repo |
| Customer risk report automation | Yes | PDF/MD from API |
| Sales / investor memo / market map | Yes | No |
| **Final risk / scenario score** | **No** | **Yes** |
| Pricing / underwriting decision engine | Explain only | Deterministic service |

See also: [deerflow-georisk-separation.md](./deerflow-georisk-separation.md).

---

## v2 roadmap

- CMIP6 grid-based hazard deltas per asset AOI  
- Persistent snapshot store (not process-local)  
- Response pillar and adaptation terms
