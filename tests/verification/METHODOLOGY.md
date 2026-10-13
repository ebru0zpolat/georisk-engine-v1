# Code-isolated EAL verifier — methodology note

This note is the **source of truth for the verifier formula**. When the pipeline
financial-translation formula changes, update this note and
`independent_eal.py` in the **same PR** from this text — never by copying
pipeline source.

Aligned with `app/loss/METHODOLOGY.md` **expected-loss-v0.3** (current).
Superseded pipeline versions (e.g. v0.2) remain documented in that note for
trail replay; this verifier targets the live CI formula only unless a
version-specific verifier entry is added.

## What this verifier claims

| Claim | Status |
|-------|--------|
| **Reproducibility** — recompute EAL from trail inputs + catalogue using this note, without importing `app.loss` / `app.services` | **Yes** (CI) |
| **Validation** — agreement with observed losses | **No** |
| **Independent model assurance** — separate org, sampling design, error taxonomy, release gates | **No** — target architecture (Model Validation Pack) |

PASS/FAIL in demo and CI means **numeric agreement within the cents rounding policy**, not predictive validity. A wrong but deterministic model can also PASS.

Prefer the phrase **code-isolated / first-principles recompute** over “fully independent validator” in buyer-facing copy until assurance controls exist.

## Rounding

Round once, at the output boundary — intermediate values carry full precision.
An intermediate `round()` in a computation path is a bug. Final EAL (and
scenario EALs) round to cents; step-table display fields may round at emit.

## Mean damage ratio (MDR)

Curves are power curves from the catalogue JSON (`exponent`, `scale`):

`MDR(i) = min(1, max(0, scale × i^exponent))` for intensity `i ∈ [0, 1]`
(full precision — no intermediate round).

Intensities are scenario indices, **not** annual exceedance probabilities
(see `app/loss/METHODOLOGY.md` § “What Phase A EAL is”).

## Curve selection

Among catalogue rows whose `hazard_id`, `building_type`, and `use_class` each
equal the asset values or `"*"`:

- exact `hazard_id` scores +4 (wildcard +0)
- exact `building_type` scores +2
- exact `use_class` scores +1

Pick the highest score. Ties: first in catalogue order.

## Vulnerability

`vuln = max(0.05, fragility_factor × (1 − adaptation_capacity_factor))`

## Expected loss proxy (current climate) — v0.3

Let `S = sum(i_h)` over hazards in the intensity map.

1. If `S = 0`: **EAL = 0** (no hazard → no loss).
2. Compute `MDR_h` for each hazard from the catalogue.
3. **Combined damage (Phase A independent-peril union, full precision):**  
   `combined_MDR = 1 − ∏_h (1 − MDR_h)`  
   (assumptions/limitations: `app/loss/METHODOLOGY.md`).
4. **Hard cap at asset value; cents-round only the emitted EAL:**  
   `EAL = min(V, round(V × combined_MDR × vuln, 2))`  
   so EAL never exceeds `V`.
5. **`attribution_share_h = i_h / S` when `S > 0`** — informational only; does not enter EAL. Must sum to 1.
6. Notional per-hazard loss for the step table (display boundary):  
   `loss_h = round(V × MDR_h × vuln, 2)` (may sum above EAL; expected).

Scenario horizons (2030 / 2050) use the same formula on that horizon’s
intensity map.

## Expected loss — v0.4 (opt-in hybrid depth/intensity)

Identical to v0.3 **except** a hazard that carries an inundation `depth`
(trail `inputs.depths[hazard_id]`) and has a depth-damage catalogue
(`parameters.depth_catalogue_id` / `_version`) takes its `MDR` from the JRC
depth curve instead of the power curve:

- **Occupancy:** map `building_type` → residential / commercial / industrial
  (apartment→residential; hotel/office/retail/other→commercial;
  industrial→industrial). Select the occupancy curve with continent `*`.
- **Depth→damage:** monotonic linear interpolation of the curve’s
  `(depth_m, damage_ratio)` points; clamp below the first point and above the
  last (full precision).

Everything else — `vuln`, `combined_MDR = 1 − ∏(1 − MDR_h)`, hard cap, cents
rounding, `attribution_share`, risk score, horizons (intensity path) — is v0.3
unchanged. The verifier reads the power catalogue **and** the depth catalogue
(`eal_from_trail(record, curves_path, depth_curves_path)`).

## Inputs

Verifier reads **trail record JSON** (asset + hazard intensities) and the
**curve catalogue JSON** path (must match the portfolio / record catalogue
id+version). It must not import `app.loss` or `app.services`.
