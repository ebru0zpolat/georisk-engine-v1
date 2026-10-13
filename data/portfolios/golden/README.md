# Golden portfolios (Annex B.6)

Synthetic reference portfolios on **real geographies** with **fictional** asset values.
Used for discovery demos and CI regression (score/EAL drift fails the build).

Both goldens use the **same** labelled stub five-layer pipeline (flood, extreme heat,
wildfire and earthquake on `hazard-stub-v0.2`; global stub MDR v0.2.0). A second geography proves pipeline transfer — **not** Country Pack
calibration. `pack-nl` loader remains Phase B.

## Antalya (`golden-antalya-v1`)

| Artefact | Path |
|----------|------|
| Portfolio | `antalya_v1.geojson` (~100 assets, TRY, RE/tourism) |
| Baseline | `antalya_v1.baseline.json` |
| Loader | `app/portfolios/golden.py` |
| CI test | `tests/portfolios/test_golden_antalya_regression.py` |

**Valuation date:** `2021-07-01` (as-of for no-lookahead contract).

**Methodology document:** `georisk-methodology-v0.4.0` — [`docs/methodology/GEORISK_ENGINE_METHODOLOGY.md`](../../../docs/methodology/GEORISK_ENGINE_METHODOLOGY.md).

**Regenerate** after intentional methodology / damage-curve / catalogue changes:

```bash
PYTHONPATH=. python scripts/generate_golden_antalya_portfolio.py
```

Then commit both GeoJSON and baseline JSON together.

## Rotterdam port (`golden-rotterdam-port-v1`)

| Artefact | Path |
|----------|------|
| Portfolio | `rotterdam_port_v1.geojson` (~100 assets, EUR, port/logistics collateral) |
| Baseline | `rotterdam_port_v1.baseline.json` |
| Loader | `app/portfolios/golden.py` |
| CI test | `tests/portfolios/test_golden_rotterdam_port_regression.py` |

**Market:** `NL-Rotterdam-port` — Annex B.6 “NL next” golden ahead of pack-nl.
**Honesty:** same stub MDR / stub hazard as Antalya; `pack_nl_calibrated: false`.

**Valuation date:** `2021-07-01`.

```bash
PYTHONPATH=. python scripts/generate_golden_rotterdam_port_portfolio.py
```

Then commit both GeoJSON and baseline JSON together.
