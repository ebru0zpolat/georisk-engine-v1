# Real hazard → EAL pipeline (Amsterdam pilot)

> Status: **real connector → real hazard → real EAL engine**, end-to-end, over
> real Amsterdam BAG assets. Damage curves and monetary asset value are
> synthetic-**labelled** (permitted for a five-layer demo). Hazard **magnitude**
> is not yet calibrated — see [Honesty & limitations](#honesty--limitations).

This converts the pilot from "every score is SHA-256 synthetic" (STUBS #3/#16a)
to **at least one path where the hazard layer is genuine measured/reanalysis
data** flowing into the real expected-loss engine.

## What is real vs. labelled

| Layer | Basis | Real? |
|---|---|---|
| Hazard — extreme heat | ERA5 daily `temperature_2m_max`, 95th-percentile climatology (Open-Meteo Archive; ERA5 © Copernicus/ECMWF) | ✅ real |
| Hazard — flood | Copernicus DEM GLO-90 orthometric ground elevation (low-elevation exposure proxy) | ✅ real data, proxy method |
| Exposure — location/geometry | Sealed, hash-verified BAG Adres→VBO→Pand (Kadaster/PDOK, Public Domain) | ✅ real |
| Exposure — monetary value | Floor area × labelled €/m² (`value_basis=synthetic_indicative_value_eur_per_m2_v0.1`, STUBS #23) | ⚠️ synthetic-labelled |
| Vulnerability | Heuristic v0.1 (construction year, use class) | ⚠️ heuristic |
| Financial — EAL | `expected-loss-v0.3` engine (real math) | ✅ real engine |
| Damage curves | `stub_global_mdr` v0.1.x (source: synthetic calibration, STUBS #16) | ⚠️ synthetic-labelled |
| Adaptation | Catalogue v0.1 | ⚠️ heuristic |

## Architecture

```
scripts/capture_real_hazard_snapshots.py   (one networked step)
   Open-Meteo ERA5 archive  ─┐
   Open-Meteo elevation DEM ─┴─→ derive point stats → seal JSON + SHA-256 manifest
                                    data/nl_pilot/snapshots/hazard/hazard-amsterdam-v1.json
                                    data/nl_pilot/provenance-manifest-hazard-v1.json
                                              │  (deterministic, offline from here on)
app/nl_pilot/hazard_snapshot.py  ── verifies SHA-256 (fail-closed) ──┐
                                                                     ▼
app/hazards/flood.py  +  app/hazards/extreme_heat.py   (injected raster = sealed snapshot)
                                                                     ▼
app/nl_pilot/real_five_layer.py  → run_five_layer(hazard=<real layer>)
   real BAG assets (load_pilot_assets) ─────────────────────────────┘
                                                                     ▼
   app/loss/expected_loss.py (EAL) + audit trail + evidence bundle
```

Key files:
- `app/connectors/open_meteo.py` — keyless real connector + pure derivations.
- `app/nl_pilot/hazard_snapshot.py` — sealed-snapshot adapter satisfying the flood/heat raster protocols; fail-closed on missing/tampered/uncovered points.
- `app/services/five_layer_pipeline.py` — `run_five_layer(..., hazard=...)` injects the real Hazard layer; the stub path is unchanged when `hazard=None`.
- `app/nl_pilot/real_five_layer.py` — orchestration + evidence bundle with honesty labels.

## Running it

**Now, offline (labelled synthetic fixture — proves wiring/output shape):**
```bash
PYTHONPATH=. python scripts/run_real_hazard_demo.py --fixture
```

**Real data (needs egress):** this repo's default remote environment blocks
external climate APIs (egress allowlist → 403). Run the capture where the
allowlist admits these two hosts:

- `archive-api.open-meteo.com` — ERA5 daily Tmax
- `api.open-meteo.com` — Copernicus DEM elevation

```bash
PYTHONPATH=. python scripts/capture_real_hazard_snapshots.py    # seals the real snapshot
PYTHONPATH=. python scripts/run_real_hazard_demo.py             # real EAL, deterministic
```

After capture, replay needs no network and is byte-reproducible (SHA-256 sealed).

## Honesty & limitations

- **Not a valuation.** Monetary value is indicative (STUBS #23). EAL scales with
  it linearly — treat absolute € as illustrative until client collateral values
  or a licensed AVM replace it.
- **Flood magnitude is uncalibrated.** DEM elevation is a *low-elevation
  exposure proxy*, not an annual flood exceedance probability, and the global
  `stub_global_mdr` curve barely discriminates across the Netherlands' 0–5 m
  band (intensities cluster ~0.95). So flood **EAL magnitude is not
  meaningful yet** — the real signal is real, the calibration is not. The NL
  Country Pack (AHN high-res DTM referenced to NAP + local flood-defence
  standards / return-period curves) is the concrete next step; real-event
  backtesting is the roadmap Stage 5 real-event validation gate (unowned, no Linear
  issue yet; GEO-105 closed 2026-08-31 as the self-attested MVP tier and does not
  satisfy it).
- **Heat has genuine spatial spread** from real ERA5 climatology and is the
  more defensible of the two magnitudes at v0.1.
- **Fail-closed, always.** Missing snapshot, hash mismatch, or an uncovered
  coordinate raises — never a silent synthetic fallback (contrast STUBS #16a).

## Tests

`tests/nl_pilot/test_real_hazard_pipeline.py` — derivations, fail-closed
invariants, hazard injection, and end-to-end over the five real BAG assets.
