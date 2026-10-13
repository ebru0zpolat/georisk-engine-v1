# Expected Annual Loss — methodology note

**Current version:** `expected-loss-v0.3`  
**Status:** Phase A library formula (synthetic curve catalogues labelled in `STUBS.md`)  
**Companion note:** [`docs/methodology/GEORISK_ENGINE_METHODOLOGY.md`](../../docs/methodology/GEORISK_ENGINE_METHODOLOGY.md) (`georisk-methodology-v0.4.0`)

**Schema (trail output keys across versions):** v0.2: `attribution_weights` (renamed to `attribution_share` in v0.3, semantics unchanged: informational only).

Changing a formula requires:

1. Adding a **new** frozen function + `FORMULAS` registry entry (never edit superseded versions).
2. Bumping `EXPECTED_LOSS_METHODOLOGY_VERSION` to that new id.
3. Updating any independent verifier from **this note** for the version it targets — never by copying pipeline code (see `.cursor/rules/ci-stubs-honesty.mdc`).

Replay / verify paths must dispatch on the trail record’s `methodology_version`. Silent fallback to the current formula is a correctness bug.

---

## What Phase A “EAL” is — and is not

### Normative definition (Phase A)

Phase A **does not** implement classical actuarial Expected Annual Loss
\(\mathbb{E}[L] = \int \mathrm{Loss}(i)\,dF(i)\) over an exceedance / return-period distribution.

It implements a **scenario damage proxy** under caller-supplied intensity indices:

\[
\mathrm{EAL}_{\mathrm{PhaseA}}
  = \min\bigl(V,\ \mathrm{round}(V \times \mathrm{combined\_MDR}(\mathbf{i}) \times \mathrm{vuln},\ 2)\bigr)
\]

where \(\mathbf{i} = \{i_h\}\) are deterministic hazard intensities in \([0,1]\) for a named horizon
(current / 2030 / 2050), **not** annual exceedance probabilities.

| Classical EAL component | Phase A status |
|-------------------------|----------------|
| Hazard annual occurrence / exceedance probability | **Not modelled** — intensities are scenario indices |
| Severity–frequency (loss curve vs return period) | **Not modelled** |
| Return-period framing | **Not modelled** (roadmap / Country Pack) |
| Integration of damage curves against a probability measure | **Not modelled** |
| Explicit direct damage vs business-interruption split | **Not modelled** — single structural MDR channel |
| Credit translation (PD / LGD / collateral haircut) | **Not modelled** (Phase C+) |

**Implication for readers:** the engine currently produces **scenario-conditional damage proxies** that are **reproducible** under a frozen formula and synthetic curves. It does **not** yet claim observationally validated annualised expected loss.

When a calibrated frequency model exists, a future methodology minor (e.g. `expected-loss-v0.4`) must introduce an explicit probability measure and redefine the symbol; do not silently reinterpret \(i_h\) as annual rates.

### Rounding (general rule)

**Round once, at the output boundary — intermediate values carry full precision. An intermediate `round()` in a computation path is a bug.**

- `MDR_h`, `combined_MDR`, uncapped loss, and other mid-formula quantities stay full float precision.
- Round **final EAL** (and scenario EALs) to cents (`round(…, 2)`) only when emitting the result.
- Other display fields (`EAL%`, risk score, collateral, notional per-hazard breakdown) may round at the same output boundary.
- **Cents rounding is a reproducibility / presentation policy**, not a claim of model accuracy. Agreement “to the cent” between pipeline and verifier proves **reproducibility**, not **validation**.

## Inputs (all versions)

- Asset: `asset_value` \(V > 0\), `building_type`, `use_class`, fragility / adaptation →  
  \(\mathrm{vuln} = \max(0.05,\ \mathrm{fragility}\times(1-\mathrm{adaptation\_capacity}))\)
- Per-hazard current intensities \(i_h \in [0,1]\) are required. 2030 / 2050 maps are optional and must be caller- or pack-supplied from a versioned climate-scenario source; no lookahead vs `valuation_date`.
- Versioned damage-curve catalogue → mean damage ratio \(\mathrm{MDR}_h(i_h) \in [0,1]\)

---

## Formula (v0.3) — current

Let \(S = \sum_h i_h\).

1. If \(S = 0\): **EAL = 0** (no hazard signal → no loss). Do **not** invent shares or loss.
2. Per-hazard MDR from the catalogue: \(\mathrm{MDR}_h = \mathrm{MDR}_h(i_h)\).
3. **Combined damage (chosen Phase A form — full precision; do not round here):**  
   \[
   \mathrm{combined\_MDR} = 1 - \prod_h (1 - \mathrm{MDR}_h)
   \]
   so \(\mathrm{combined\_MDR} \in [0,1]\) even when several hazards are high.
4. Uncapped loss at full precision, then **hard cap at asset value** and **cents-round only the emitted EAL** (required because \(\mathrm{vuln}\) may exceed 1):  
   \[
   \mathrm{EAL}_{\mathrm{full}} = \min\bigl(V,\ V \times \mathrm{combined\_MDR} \times \mathrm{vuln}\bigr)
   \]
   \[
   \mathrm{EAL} = \min\bigl(V,\ \mathrm{round}(V \times \mathrm{combined\_MDR} \times \mathrm{vuln},\ 2)\bigr)
   \]
   Therefore **EAL never exceeds \(V\)**. The difference \(|\mathrm{EAL} - \mathrm{EAL}_{\mathrm{full}}| < 0.005\) (cents rounding only).
5. **Attribution share (informational only — does not enter EAL):** when \(S > 0\),  
   \[
   \mathrm{attribution\_share}_h = \frac{i_h}{S}
   \]
   with \(\sum_h \mathrm{attribution\_share}_h = 1\). Renamed from “weight”; never used to scale sibling hazards.
6. Notional per-hazard loss (audit / display breakdown; may sum above EAL) — full precision internally, cents at output:  
   \[
   L_h^{\mathrm{notional}} = \mathrm{round}(V \times \mathrm{MDR}_h \times \mathrm{vuln},\ 2)
   \]
7. Scenario EALs (2030 / 2050) use the same formula only when both horizon-specific intensity maps are supplied. Current-only runs emit no forward-looking loss values; they never derive horizons from current intensity.
8. \(\mathrm{EAL\%} = 100 \times \mathrm{EAL} / V\) (display-rounded at output).

### Multi-hazard combination — scope and assumptions

The product form \(1 - \prod_h (1 - \mathrm{MDR}_h)\) is the **independent-peril union** of mean damage ratios. It is a **Phase A engineering choice**, not an empirically validated joint-loss model.

**Assumptions (explicit):**

1. Per-hazard MDRs are treated as if damage mechanisms combine like independent “failure” probabilities on the same damage-ratio scale.
2. No correlation structure between hazards (flood ↔ heat, concurrent vs sequential events).
3. Direct structural damage and non-structural / interruption losses are **not** separated before combination — all channels collapse into one MDR per hazard.
4. Simultaneous and consecutive events are **not** distinguished.

**Known limitations (must surface in buyer materials):**

- Flood and extreme heat do not share the same damage mechanism; independence is a modelling convenience.
- Hazards may be positively correlated in space/time; independence can under- or over-state joint loss.
- Combining heterogeneous loss bases (structure vs productivity) on one MDR scale is methodologically weak until separate channels exist.
- A future version should either (a) keep hazards additive with an explicit copula / dependence model, or (b) report per-hazard losses without a single combined MDR.

**Invariants (CI property tests):**

1. Adding a zero-intensity hazard never changes EAL.
2. Increasing any single \(i_h\) never decreases EAL.
3. When \(S > 0\), attribution shares sum to 1.
4. **EAL never exceeds asset value** for any valid input.

### Extreme heat — financial transfer channel (Phase A honesty)

For **flood**, interpreting \(\mathrm{MDR} \times V\) as a structural damage fraction of asset value is conventional (within curve quality limits).

For **extreme heat**, realised financial impact often runs through energy use, equipment efficiency, labour productivity, operational interruption, cooling cost, and asset life — not only fabric damage. Phase A still applies the **same** \(\mathrm{MDR}_h(i_h) \times V \times \mathrm{vuln}\) structural channel to heat as a **placeholder intensity→loss mapping**.

Until heat-specific transfer functions exist (pack or core minor version), heat contributions to EAL are **indicative structural proxies**, not productivity / BI estimates. Do not present them as calibrated heat-loss economics.

---

## Formula (v0.4) — opt-in hybrid depth/intensity

**Version id:** `expected-loss-v0.4` · **Status:** opt-in, **not** the default (v0.3 stays default so existing callers and golden baselines are unchanged).

Selected only when a caller passes `methodology_version=expected-loss-v0.4` with a per-hazard `depths` map and a depth-damage (JRC) catalogue. Then a hazard **with a depth** takes its \(\mathrm{MDR}\) from the JRC `depth→damage` curve (`app/loss/depth_damage_curves.py`) instead of the intensity power law; every other hazard keeps the v0.3 power curve. `combined_MDR`, `vuln`, the hard cap, rounding, `attribution_share`, risk score and the horizon (intensity) path are v0.3 **unchanged**.

- **Occupancy map:** apartment→residential; hotel/office/retail/other→commercial; industrial→industrial. Curve selected at continent `*` (vendored catalogues must carry `*` defaults; continent-aware selection is a later minor).
- **Depth→damage:** monotonic linear interpolation of `(depth_m, damage_ratio)`, clamped outside the range (full precision; round only at output).
- **Trail / replay:** `inputs.depths` and `parameters.depth_catalogue_id`/`_version` are persisted; replay dispatches on `methodology_version` and reloads the depth catalogue by id+version (fail-closed, never a default). Verifier: `eal_from_trail(record, curves_path, depth_curves_path)`.
- **Depth provenance:** the inundation depth is `max(0, water_surface_elevation − ground_surface_elevation)` (`app/loss/flood_depth.py`). The reference (water-surface) level comes from a versioned, SHA-256-provenanced **return-period flood-hazard map** (`app/loss/flood_hazard_map.py`) — `reference_level_at(lat, lon, T)`, per-asset and per-return-period, fail-closed on an uncovered cell/period. Differencing two elevations is guarded by more than a datum *name*: an `ElevationProfile` carries the ground source's vertical datum, units, horizontal CRS, value semantics, source/version, datum transformation and resolution, and `assert_differenceable` fails closed (`FLOOD_DATUM_MISMATCH`) unless it lines up with the map — so a NAP water level is never silently differenced against an EGM2008 (Copernicus DEM) elevation, a foot-unit source, or an already-computed depth. On the map path, provenance is **mandatory**: a `data_versions` collector must be supplied, and the record carries the map id, SHA-256 checksum, source type, datum, resolved cell id, return period and synthetic status plus the elevation source — no silent evidence loss. With a vendored map (`scripts/vendor_flood_hazard_map.py`) *and* a real, sealed NAP elevation source (e.g. AHN) the depth path is fully real; absent either, a single labelled synthetic scalar is the fail-closed default (STUBS #26) and the demo's `--mode qualified` returns `NOT_QUALIFIED` rather than falling back to synthetic.

---

## Formula (v0.2) — superseded (FROZEN for replay)

**Version id:** `expected-loss-v0.2`  
**Status:** superseded by v0.3; implementation in `_compute_core_v0_2` must not be edited.

Let \(S = \sum_h i_h\).

1. If \(S = 0\): **EAL = 0** (no hazard signal → no loss). Do **not** assign uniform weights and do **not** manufacture loss.
2. Attribution weights (must sum to 1 when \(S > 0\)):  
   \[
   w_h = \frac{i_h}{S}
   \]
   These weights describe intensity share for audit breakdown. They are **not** used to competitively re-scale sibling hazards (that form is non-monotonic and rejected).  
   Trail / replay field name: **`attribution_weights`** (v0.3 renamed the live field to `attribution_share`; frozen replay must keep the v0.2 key).
3. Per-hazard loss and composite EAL (independent perils):  
   \[
   L_h = V \times \mathrm{MDR}_h(i_h) \times \mathrm{vuln}
   \]
   \[
   \mathrm{EAL} = \sum_h L_h
   \]
   (With power-curve MDRs, \(i_h = 0 \Rightarrow L_h = 0\), so adding a zero-intensity hazard leaves EAL unchanged.)  
   **Note:** the sum is **not** capped at \(V\); EAL may exceed asset value when \(\mathrm{vuln} > 1\) or multiple hazards are high.
4. Scenario EALs (2030 / 2050) use the same formula on the corresponding intensity maps.
5. \(\mathrm{EAL\%} = 100 \times \mathrm{EAL} / V\).

**v0.2 → v0.3:** v0.2 summed independent \(V \times \mathrm{MDR}_h \times \mathrm{vuln}\) (could exceed \(V\)). v0.3 aggregates MDRs with the union formula and hard-caps EAL at \(V\); renames intensity shares to `attribution_share`.

**v0.1 → v0.2:** removed mean-based weights and uniform \(1/n\) fallback that invented loss when \(S = 0\). (`expected-loss-v0.1` is **not** in the formula registry.)

---

## Audit trail (file-backed)

- Every successful computation appends a hash-chained JSONL record **before** return.
- Record stores `methodology_version`; replay selects `FORMULAS[methodology_version]`.
- **Single-writer-per-file** semantics: on append, acquire an exclusive file lock (`fcntl`), **re-read the tip hash from disk**, chain to that tip, write, release. The in-memory tip is a cache only — never the source of truth for `prev_hash`.
- Multi-worker / multi-host deployments are out of scope for the local JSONL store; the storage interface anticipates a shared store (e.g. Supabase) later.

## Curve artefacts

Catalogue JSON under `app/loss/curves/`. A curve change bumps catalogue `version` (methodology minor). Stubs use `curve_id` prefix `stub_`, `synthetic: true`, `source: "synthetic calibration"`.
