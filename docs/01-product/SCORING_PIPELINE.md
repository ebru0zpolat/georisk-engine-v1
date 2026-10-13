# Scenario scoring pipeline (GEO-150)

**Canonical code:** `app/scoring/scenario_score.py`  
**Coefficients:** `app/scoring/data/scenario_coefficients_v1.json`  
**Architecture:** [docs/architecture/scenario-scoring-v1.md](../architecture/scenario-scoring-v1.md)  
**Golden tests:** `tests/scoring/test_scenario_scoring_golden.py` (merge-blocking)

---

## `apply_cap_pipeline()` — full spec

**Signature:**

```python
def apply_cap_pipeline(
    *,
    baseline_score: int,
    hev: HevScores,
    weighted_multiplier: float,
) -> CapPipelineResult
```

**Inputs**

| Field | Source |
|-------|--------|
| `baseline_score` | Core snapshot `overall_score` at score time (scenario-independent) |
| `hev` | H-E-V pillars from component dict via `hev_from_components()` |
| `weighted_multiplier` | Equal-weight mean of `hazard_driver_multipliers` for selected hazards |

**H-E-V mapping**

| Pillar | Component keys |
|--------|----------------|
| Hazard | `ocean`, `pollution`, `land` |
| Exposure | `industrial` |
| Vulnerability | `agriculture`, `sensitivity` |

**Constants**

- `WEIGHT_HAZARD = 0.55`, `WEIGHT_EXPOSURE = 0.25`, `WEIGHT_VULNERABILITY = 0.20`
- `SCENARIO_DELTA_CAP_POINTS = 25`
- `MAX_SCORE = 100`

**Four steps (testable)**

1. **Hazard saturation:** `raw_adjusted_hazard = hev.hazard × weighted_multiplier`; `adjusted_hazard_score = min(round(raw_adjusted_hazard), 100)`
2. **Raw composite:** `raw_scenario_score = 0.55×adjusted_hazard + 0.25×exposure + 0.20×vulnerability`
3. **Delta cap:** `raw_delta = raw_scenario_score - baseline_score`; `capped_delta = clamp(raw_delta, 0, 25)`; flag `scenario_delta_cap_applied` when cap binds
4. **Final ceiling:** `scenario_score = min(baseline + capped_delta, 100)`; flag `final_score_cap_applied` when ceiling binds

**Output:** `CapPipelineResult` with all intermediate floats/ints for audit templates.

---

## End-to-end: `compute_scenario_score()`

After cap pipeline:

- `asset_geometry_hash` = `derive_point_geometry_hash(latitude, longitude)` from **`app.geo.interfaces`** (GEO-189)
- `coefficient_table_version` + `coefficient_table_hash` from manifest
- `confidence` via `derive_confidence(DataQualityInputs(...))`
- Response includes `hazard_driver_multipliers`, `drivers` (top 3 keys)

**Determinism guarantee:** Identical output when all match:  
`asset_id`, `asset_geometry_hash`, `data_snapshot_id`, `model_version`, `scenario`, `horizon`, `coefficient_table_version`, `coefficient_table_hash`.

---

## Golden fixtures (merge-blocking)

| ID | Test | Assertion summary |
|----|------|-------------------|
| G-001 | *(reserved)* | Cap-pipeline unit tests in `tests/test_scenario_score_v1.py` — use G-002+ for integration |
| G-002 | `test_g002_ssp585_2050_all_sixty` | all components=60, SSP5-8.5, 2050 → score=72, delta=12, pct=20% |
| G-003 | `test_g003_saturation_no_overflow` | baseline=90, heat mult=1.9 → adjusted_hazard capped at 100, scenario_score ≤ 100 |
| G-004 | `test_g004_baseline_zero_delta_pct_null` | baseline=0 → `scenario_delta_pct` is null |
| G-005 | `test_g005_multi_hazard_weighted_multiplier` | multiplier = equal mean of driver mults |
| G-006 | `test_g006_thousand_run_determinism` | 1000 identical runs → byte-identical `ScenarioScoreResult` |
| G-007 | `test_g007_coefficient_table_hash_in_response` | hash matches `coefficient_table_hash()` from manifest |

**Before any PR touching scoring:** `python3 -m pytest tests/scoring/test_scenario_scoring_golden.py -q`

---

## DeerFlow boundary (do not cross)

| Layer | Owner |
|-------|-------|
| Deterministic scoring in `app/scoring/` | **GeoRisk Engine** |
| Scenario *explanation*, memos, QA prose | **DeerFlow** (`integrations/deerflow/`) |
| Coefficient table changes | Human review + version bump + golden tests |

DeerFlow MCP may call `POST /v1/scenario/run` but **must not** reimplement `apply_cap_pipeline` in skill code.

See: [deerflow-georisk-separation.md](../architecture/deerflow-georisk-separation.md)

---

## API surface

- `POST /v1/scenario/run` — `app/api/scenario.py` → `scenario_lab_service.py`
- UC-01 preview (separate path): `POST /v1/risk/preview` — indicative only, not regulatory proof
