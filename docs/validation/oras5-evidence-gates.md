# ORAS5 evidence gates — canonical state record

Audit-correct status record for the İsdemir ORAS5 marine-context validation.
This file is the single source of truth for what is proven and what is not.
Do not mark a gate closed without evidence in `data/validation/` and a
corresponding update here.

## Declaration (v1, locked)

The real-asset declaration is **immutable v1**: point **36.725833, 36.186111**
(İsdemir / Payas, İskenderun Bay), declaration file SHA-256
`8bc533c23f77067e0c232df20d360bf5c0876c9a9c10555c12f353ad69579579` — carried
verbatim into every evidence record; the file itself is external (not in this
repo) and is never regenerated here. The fixture, tests and the validation
script are bound to this exact coordinate. `36.7333, 36.2` is **not** the
declared point — even though both round to grid indices (507, 865) on the
ORAS5 0.25° grid, the v1 hash only recognises the exact declared coordinate as
pre-declared (locked by `test_legacy_isdemir_coordinate_is_not_predeclared`).
A different point, if ever needed, ships as a separate v2 file; the v1 result
is never overwritten after it is seen.

- `scripts/validate_isdemir_marine.py` — evidence generation (offline stub / live fetch)
- `scripts/era5_retrieve_smoke.py` — ERA5 retrieve operational evidence
- `data/validation/` — evidence records (JSON + Markdown), never rewritten in place

## The eight gates

| # | Gate | Status |
|---|------|--------|
| 1 | Real marine asset declaration (`real_asset_declaration`) | **Closed** — immutable v1, `36.725833, 36.186111`, hash-locked |
| 1b | Fixture coordinate selection (`fixture_coordinate_selection`) | **Closed** — canonical offline fixture below |
| 2 | Actual ORAS5 grid selection (`actual_oras5_grid_selection`) | Open |
| 3 | Independent live CDS CSV–Zarr parity | Open |
| 4 | Cross-product homogeneity | Open |
| 5 | Calibrated variability / scaling | Open |
| 6 | Railway production provisioning and endpoint smoke | Open |
| 7 | Durable raw-evidence storage and retention | Open |
| 8 | ORAS5-to-asset-loss pathway | Open |

## Evidence classification

| Evidence | Status |
|----------|--------|
| `real_asset_declaration` | passed |
| `fixture_coordinate_selection` | passed |
| `offline_pipeline_parity` | passed |
| `deterministic_fixture_selection` | passed |
| `credential_contract` | passed |
| `dimensionality_controls` | passed |
| `fail_closed_behavior` | passed |
| `actual_oras5_grid_selection` | pending |
| `live_source_parity` | pending |
| `cross_product_homogeneity` | pending |
| `scaling_calibration` | pending |
| `production_smoke` | pending |
| `durable_retention` | pending |
| `asset_loss_pathway` | not_established |
| `production_eligible` | **false** |

## Canonical offline fixture (expected_fixture_*)

| Field | Value |
|-------|-------|
| Declared point | `36.725833, 36.186111` |
| Geometric cell | `[507, 865]` → `36.75, 36.25`, snap `6.2955 km` |
| Expected ocean neighbour | `[507, 864]` → `36.75, 36.0`, snap `16.8005 km` (< 20 km) |
| Ocean-snap limit | `20.0 km` |

Live runs write store values to `verified_live_*` fields and never overwrite
`expected_fixture_*`. `live_fixture_match` is a comparison result only.

**Controlled fail:** if the verified grid index does not match the fixture, or
the verified ocean neighbour differs, or the ocean snap exceeds the 20 km
limit, the run is a controlled failure — `run_status=failed`, observed values
preserved in `verified_live_*`, `production_eligible=false`, and the failure
is recorded as an open gate failure (script exits nonzero but still writes the
evidence record for the audit trail).

## Honest labels (open doors)

- **Grid index:** `(507, 865)` is only an `expected_fixture_grid_index`
  (regular-grid formula) — NOT NEMO tripolar grid proof. Live records read the
  index from the store coordinate arrays and store it as
  `verified_live_grid_index`; on mismatch both values are kept and the live
  index is never forced onto the fixture.
- **CSV–Zarr parity:** the synthetic round-trip proves
  `offline_pipeline_parity = passed`; `live_source_parity` stays pending until
  an independent live CDS CSV and a live Zarr fetch of the same cell and period
  are compared (`csv_zarr_same_cell_period_comparison`).
- **Homogeneity:** the `>3σ` jump diagnostic is a heuristic, not a Pettitt or
  SNHT change-point test.
- **Scaling:** the 1.0 clamp and range sanity check are not calibration;
  `production_eligible = false`.
- **Retention:** 24/36-month completeness is series completeness, not durable
  object-store retention.
- **Loss:** an empty series yielding 0.0 is fail-closed input handling, not an
  EAL / downtime pathway.
- **1991–2020 series:** the consolidated+operational merge is a
  `provisional_cross_product_series`, `production_eligible = false`.

## Operational evidence (does NOT close gates 2–8)

Successful runs of `scripts/era5_retrieve_smoke.py` and the live İsdemir fetch
record operational evidence (`data/validation/era5_smoke_*_evidence.json`,
`isdemir_marine_*_evidence.json`) — authenticated Zarr data access and a real
CDS retrieve. They are recorded as operational evidence only; none of them
closes the homogeneity, calibration, retention or loss-pathway gates. An
unauthenticated 401 demonstrates only the auth requirement, not a close.

## Summary (Linear / PR)

> One of eight ORAS5 evidence gates is closed: the immutable real-asset
> declaration. Offline implementation and fail-closed controls are verified,
> but synthetic tests do not substitute for live-source, scientific-calibration,
> production, retention or loss-pathway evidence.

## Security notes

- CDS token: enter directly into Keys/Secrets (or the gitignored `.env.local`);
  never paste into chat. The smoke/validation scripts use it raw and never
  print it (no token, no Authorization header, no raw exception text).
- If the GEE service-account JSON was ever pasted into a chat field, revoke it
  in GCP and create a new key before production use.
