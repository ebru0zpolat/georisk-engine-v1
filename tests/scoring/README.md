# Scenario scoring golden fixtures (GEO-150)

Merge-blocking tests: `test_scenario_scoring_golden.py`

| Fixture | Description |
|---------|-------------|
| **G-002** | All components 60, SSP5-8.5, 2050, hazards flood+drought+wildfire → `scenario_score=72`, `delta=12`, `pct=20%`. Weighted multiplier = mean(1.30, 1.35, 1.45) ≈ 1.367. |
| **G-003** | Baseline 90, heat @ 2100 SSP5-8.5 (mult 1.90) → `raw_scenario_score=95.5`, `adjusted_hazard_score=100` (no overflow). |
| **G-004** | `baseline_score=0` → `scenario_delta_pct=null`. |
| **G-005** | `hazard_multiplier_type=weighted_effective`, per-driver map in `hazard_driver_multipliers`. |
| **G-006** | 1000 identical `compute_scenario_score` calls → byte-identical result. |
| **G-007** | `coefficient_table_hash` in response matches `scenario_coefficients_v1.manifest.json`. |

## Determinism key

Identical output requires all of:

`asset_id` + `asset_geometry_hash` + `data_snapshot_id` + `model_version` + `scenario` + `horizon` + `coefficient_table_version` + `coefficient_table_hash`

## Coefficient CI

```bash
python scripts/verify_coefficient_hash.py
```

Also enforced by `tests/test_verify_coefficient_hash.py`.

## GEO-151 propagation fixtures

`test_propagation.py` — actor-tree BFS (`app/scoring/propagation.py`):

| Case | Description |
|------|-------------|
| Linear chain | Downstream hops capped at `max_hops_downstream=2`. |
| Diamond graph | Multi-path max-`attenuated_delta` dedup. |
| Cycle guard | Revisiting nodes on a path is blocked; BFS terminates. |
| Zero-weight edge | `dependency_weight=0` → zero propagated delta. |
| Calibration | hop-1: `12 × 0.55 × 0.8 = 5.28 ± 0.1`. |
