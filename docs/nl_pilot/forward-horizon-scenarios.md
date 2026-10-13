# Forward-horizon scenarios (2030 / 2050)

> Status: **real source shape built + wired to the EAL engine**; authentic
> CMIP6/CORDEX/KNMI'23 factors land via one vendor step. Closes the "forward
> horizons disabled" gap (`STUBS.md #16b`).

## Why

The expected-loss engine already consumes `horizon_2030` / `horizon_2050`
intensity maps and emits `scenario_eal`. What was missing was a **versioned
scenario source** — the old fallback invented `current × 0.95 / 1.05` with no
provenance and was disabled. Climate risk is fundamentally forward-looking, so
this is the output a regulated buyer / VC most wants to see.

## What shipped

- `app/loss/horizon_scenarios.py` — `HorizonScenarioCatalogue`: per-hazard
  uplift factors for a named scenario. `horizon intensity = clamp(current ×
  factor, 0, 1)` — the current intensity projected by a **real, cited** scenario
  multiplier, never a manufactured constant. `build_horizon_maps(current)` →
  `(horizon_2030, horizon_2050)` the EAL engine already accepts. Fail-closed when
  unpopulated.
- `app/loss/curves/horizon_scenario_fixture_v0.1.json` — labelled SYNTHETIC
  fixture (`synthetic=true`) so it runs offline; never real values (STUBS #28).
- `scripts/vendor_horizon_scenarios.py` — seals authentic factors from a
  normalized CSV + provenance (the scenario cited).
- `scripts/run_horizon_scenario_demo.py` — current / 2030 / 2050 EAL over the
  five real Amsterdam assets.
- `tests/loss/test_horizon_scenarios.py` — projection/clamp, fail-closed,
  validation, and the end-to-end `scenario_eal` monotonicity.

## Vendoring authentic factors (egress-free)

Extract per-hazard 2030/2050 uplift factors for a scenario from the cited source
(CMIP6/CORDEX multi-model medians, or KNMI'23), then:

```bash
PYTHONPATH=. python scripts/vendor_horizon_scenarios.py --from-csv factors.csv \
    --scenario "SSP2-4.5" --source "CMIP6 multi-model median, <region>, <ref>"
PYTHONPATH=. python scripts/run_horizon_scenario_demo.py \
    --scenario-catalogue app/loss/curves/horizon_scenario_v1.0.json
```

CSV: `hazard_id,horizon,factor` (horizon ∈ {2030, 2050}).

## Honesty & limitations

- The uplift-factor form is a **first-order** projection (a scenario multiplier
  on today's intensity), not a full re-run of the hazard model under future
  climate. It's the defensible v0.1 shape; a downscaled per-asset CMIP6/CORDEX
  intensity field is the higher-fidelity successor.
- Fixture factors are labelled synthetic and never presented as real.
- Flood intensities already near saturation (NL low elevation) clamp under
  uplift, so heat carries most of the horizon delta there — the correct
  behaviour, and a reminder that magnitude waits on calibration (P3 / the roadmap Stage 5 real-event
  validation gate, which has no Linear issue yet; GEO-105 closed as the self-attested
  MVP tier and does not cover it).
