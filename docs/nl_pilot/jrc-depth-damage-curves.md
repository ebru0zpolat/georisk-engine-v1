# JRC depth-damage curves (real flood damage functions)

> Status: **engine built + tested**; authentic JRC values land via one vendor
> step; real activation on assets is coupled to a real inundation **depth**
> (AHN follow-on). This is the P1 replacement path for `STUBS.md #16`.

## Why

The legacy flood damage function (`stub_global_mdr`, STUBS #16) is a labelled
synthetic power law: `MDR = scale · intensity^exponent`, where `intensity∈[0,1]`
is not a physical quantity. A regulated buyer's first question — *"what are your
damage functions based on?"* — has no good answer for a fitted power curve.

The literature-standard answer is a **depth–damage** curve: inundation depth in
metres → damage fraction, tabulated per occupancy. The reference open dataset is
**JRC's Global flood depth-damage functions** (Huizinga, de Moel, Szewczyk,
2017; EUR 28552 EN, JRC105688), openly published and redistributable. This turns
the financial layer's curve from *invented* to *literature-cited*.

## What shipped

- `app/loss/depth_damage_curves.py` — the engine: schema, load, **monotonic
  linear interpolation**, occupancy×continent selection, and fail-closed guards
  (an unpopulated real catalogue cannot emit a number).
- `app/loss/curves/jrc_depth_damage_fixture_v0.1.json` — a JRC-**shaped**
  SYNTHETIC-FIXTURE (`synthetic=true`) so the engine runs offline; never JRC
  values (STUBS #25).
- `scripts/vendor_jrc_depth_damage.py` — seals authentic JRC values from a
  normalized CSV into `jrc_global_depth_damage_v1.0.json` (`synthetic=false,
  populated=true`) + a provenance sidecar (SHA-256, licence, source citation).
- `tests/loss/test_depth_damage_curves.py` — interpolation, clamping,
  monotonicity/shape validation, occupancy mapping, continent preference,
  fail-closed-on-unpopulated, and a vendor round-trip.

## Vendoring the authentic curves (no credentials, egress-free)

1. Get the JRC 2017 database (EUR 28552 EN) and its depth-damage sheet.
2. Convert the relevant rows to the normalized CSV:
   ```csv
   continent,occupancy,depth_m,damage_ratio
   Europe,residential,0.0,0.00
   Europe,residential,0.5,0.25
   Europe,residential,1.0,0.40
   ...
   ```
   `continent` may be `*` (global default); `occupancy ∈ {residential,
   commercial, industrial, agriculture, infrastructure, transport}`.
3. Seal it:
   ```bash
   PYTHONPATH=. python scripts/vendor_jrc_depth_damage.py --from-csv jrc.csv
   ```
   The engine then selects real JRC curves; the fixture is never chosen for a
   real number.

## The depth bridge (now shipped) and its coupling

A depth–damage curve needs a **depth**. `app/loss/flood_depth.py` supplies it:

    inundation_depth = max(0, reference_level − ground_elevation)

composed end-to-end in `scripts/run_depth_damage_demo.py` (real elevation →
depth → JRC damage fraction → indicative loss) over the five real Amsterdam
assets. Depth-based JRC damage **discriminates by elevation** — below-NAP
assets flood, higher ground stays dry — unlike the flat ~0.95 intensity proxy.

Real inputs to the bridge:

1. **AHN elevation** — NAP-referenced, authoritative. Vendor real point
   elevations with `scripts/vendor_ahn_elevation.py --from-csv ahn.csv`
   (PDOK is egress-only; sealing is egress-free). Copernicus DEM (P0) is the
   keyless fallback.
2. **Reference water level** — the one synthetic term (`REFERENCE_LEVEL_BASIS`,
   STUBS #26), a labelled placeholder until return-period flood-hazard maps
   (NL LIWO / pack flood extent) supply per-asset levels.
3. **`expected-loss-v0.4`** wiring — **shipped (opt-in).** The depth path is
   selectable in the audited engine (`compute_expected_loss(...,
   methodology_version="expected-loss-v0.4", depths=..., depth_catalogue=...)`):
   flood MDR from the JRC curve, everything else v0.3. Trail-persisted,
   replay-dispatched, and checked by the code-isolated verifier
   (`eal_from_trail(record, curves_path, depth_curves_path)`). The v0.3 default
   is untouched (golden baselines unchanged). Demo:
   `PYTHONPATH=. python scripts/run_audited_depth_eal_demo.py` (real assets →
   v0.4 audited EAL → independent verify ALL PASS). Remaining: real
   return-period reference levels, then promoting v0.4 to the flood default.

Water stress is independent of this chain, and for NL assets the Aqueduct
indicator was removed by ADR-0007 (`docs/decisions/ADR-0007-klimaateffectatlas-replaces-aqueduct-nl.md`).

### Compose it now (offline)

```bash
PYTHONPATH=. python scripts/run_depth_damage_demo.py --fixture
# real elevation + real curves once vendored:
PYTHONPATH=. python scripts/run_depth_damage_demo.py \
    --ahn data/nl_pilot/snapshots/hazard/ahn-elevation-amsterdam-v1.json \
    --jrc app/loss/curves/jrc_global_depth_damage_v1.0.json --reference-level 1.5
```

## Honesty

- The engine is real and tested; the **fixture numbers are labelled synthetic**
  and fail-safe (the real catalogue ships separately, `populated=true`).
- No JRC value is authored by hand — authentic numbers only enter through the
  vendor CSV from the JRC source.
- Until depth + v0.4 wiring land, the real-asset flood EAL still uses the
  labelled `stub_global_mdr` power curve; nothing here silently changes an
  audited number.
