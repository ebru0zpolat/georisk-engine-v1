# ADR-0008 — Product family, own heat and extreme-precipitation indicator engines, and the P0 frontend

- **Status:** Proposed. Becomes Accepted when the founder merges the pull request that carries it; the merge
  commit is the dated source of record.
- **Opened:** 2026-10-13
- **Amends:** [`PRODUCT_CHARTER_V2.md`](../00-master/PRODUCT_CHARTER_V2.md) §1, §4 and §5;
  [`PRUNE_LIST.md`](../00-master/PRUNE_LIST.md) §2 (frontend row) and §3 ("Competing on hazard physics" row);
  [`AGENTS.md`](../../AGENTS.md) §3 and §5.
- **Does not amend:** [`ENGINEERING_INVARIANTS.md`](../00-master/ENGINEERING_INVARIANTS.md) — every invariant
  INV-01…INV-12 applies unchanged to everything this ADR admits. [`GLOSSARY.md`](../00-master/GLOSSARY.md) —
  unchanged; this ADR adds no claim word.
- **Changes no readiness flag.** `production_eligible=false` and every `Literal[False]` stay as they are (INV-10).

## Context

Charter v2 (19 September 2026) made verification of physical-risk numbers the product and demoted own-number
production to an input capability. Its argument rested on the market: an independent hazard model is an
acquisition target, and buyers are internalising production.

On 2026-10-13 the founder decided three things:

1. **Time-to-market is not a constraint.** The company is not racing a launch date, so building a slow,
   defensible own-indicator capability no longer competes with shipping the verifier.
2. **Own heat and extreme-precipitation engines will be built.** A verifier that has never had to make its own
   numbers survive its own gates is weaker evidence than one that has.
3. **The P0 design canvas (`.design/`) will be implemented** in `frontend/`, so that the evidence the engine
   already produces is visible to a reviewer.

The founder also set the product family for external positioning (investor and RVO material):

```
GeoRiskEngine
├─ GeoRisk Evidence   — the product: defensibility gap report, CRVA evidence pack,
│                       EU Taxonomy pack, Türkiye pack, later ESRS / bank policy packs
├─ GeoRisk Core       — qualified hazard inputs: public and vendor hazard qualified
│                       for use, plus our own heat and extreme-precipitation indicators
└─ GeoRisk Portfolio  — portfolio-level gap triage and API
```

## Decision

### D1. Evidence stays first; Core feeds it

The charter's one sentence stands: GeoRisk Engine establishes whether a physical-risk number can be defended.
Track A (verification) stays the primary track and its work orders keep their order and their gates.

Core is the input layer. It is a new Track C next to Track A, not a replacement for it. Its own indicators are
held to the same standard the verifier applies to third parties: an indicator that cannot pass our own
verifier is not shown as anything but `NOT_QUALIFIED` or `SYNTHETIC`.

Every pack in GeoRisk Evidence emits only the epistemic states in the glossary: `SUPPORTED`,
`CONDITIONALLY_SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, bridged one-way to `ClaimState` (INV-09).
**No `PARTIAL` state is introduced.** A pack never states that an activity or instrument *is* taxonomy-aligned
or compliant (charter §6; INV-11).

### D2. What an "own indicator engine" is permitted to be

An own indicator is a **published statistical index computed from a sealed, licence-qualified public climate
dataset by a published method**. It is not a physical hazard model.

| Permitted | Not permitted without a further ADR |
|---|---|
| ETCCDI / Climdex indices computed from CMIP6 or ERA5 daily series | Dynamical or statistical downscaling of our own |
| Heat: WSDI (primary), TX90p (diagnostic) — already approved in the [climate-data decision record](../methodology/CLIMATE_DATA_SOURCE_AND_METHODOLOGY_DECISION_RECORD.md) | Bias correction (the record's "none; `bias_corrected: false`" stands) |
| Heat, absolute: TXx, TR (tropical nights, TN > 20 °C), and a humid-heat index (wet-bulb or WBGT, see D4) | Converting a precipitation index into a flood depth, extent or probability |
| Extreme precipitation: Rx1day, Rx5day, R95pTOT, R99pTOT | Deriving our own annual flood probability (charter §4 stays in force) |
| Multi-year horizon windows (e.g. 2021–2040, 2041–2060) per scenario, single model/member per series | Single-year horizons; silent multi-model averaging |

An extreme-precipitation index is **not** a flood hazard and must never be labelled, charted or priced as one.
Pluvial flood remains an input to qualify (e.g. Klimaateffectatlas for NL, ADR-0007), not an output we derive.

### D3. Conditions every indicator must meet before it is shown above `NOT_QUALIFIED`

1. **Source gate.** Each input file is SHA-256-sealed; the model is on the versioned licence allowlist with
   commercial use permitted; free-text NetCDF licence attributes are insufficient. (Existing CLIM-03 contract.)
2. **Fail closed.** Missing years, partial years, non-finite values, out-of-domain coordinates, calendar or unit
   mismatches each refuse with a named blocker code from the registry (WO-08), never a fill value (INV-02).
3. **Provenance.** Dataset, model, member, scenario, baseline period, horizon window, method version and file
   hashes travel with every value (INV-05).
4. **Independent recomputation.** A stdlib-only verifier under `tests/verification/`, written from the method
   note and importing nothing from `engine.` or `app.`, recomputes every index on the sealed series and agrees
   byte-for-byte (INV-07, INV-08). Until it exists for an index, that index is capped at `NOT_QUALIFIED`.
5. **Limits ship with the number.** Single model/member, no bias correction, grid resolution and the
   distance from the asset to the grid-cell centre are stated in the output, not in a footnote.
6. **Stub inventory.** Any fixture series used in tests has a `STUBS.md` row (INV-04).

### D4. GCC applicability of the heat engine

The heat engine is global by construction (CMIP6 is global; the adapter's domain check is a bounds check, not
a European mask), so it runs for GCC coordinates. Its **current indicators are not sufficient there**, and the
output must say so:

- WSDI and TX90p are percentile-relative. In a climate whose baseline is already extreme, they measure change
  against that baseline; they do not measure absolute stress on people, cooling load or equipment.
- The material heat driver on the Gulf coast (Dubai, Abu Dhabi, Doha, Dammam, Kuwait City, Muscat) is
  **humid heat**, which needs humidity (`huss` or `hurs`) alongside `tasmax`. A humid-heat index (wet-bulb
  temperature or WBGT approximation) is therefore in scope for Track C, and a GCC heat output without it carries
  the blocker that it is missing.
- Phase 1 models (MPI-ESM1-2-HR/LR, ~100 km / ~200 km) place many coastal GCC assets in mixed land–sea cells.
  Land-fraction and cell-distance must be reported per asset; an asset whose cell is predominantly sea refuses.
- There is no GCC Country Pack. Until one exists, GCC outputs are physical indicators only, with no regulatory
  mapping, and every regulatory claim about them is `INSUFFICIENT_EVIDENCE`.

### D5. The P0 frontend

`frontend/` is re-admitted for feature work, limited to implementing the `.design/` P0 artboards (Track D).
Conditions:

1. Screens render engine output or an explicit empty / refused state. The sample figures in the artboards are
   design content and must not ship as values.
2. Chip strings are the glossary's machine terms, rendered verbatim; translation goes in the tooltip.
   The design brief's `VERIFIED` ("source verified, licence reviewed") is wider than the glossary's
   `VERIFIED` (evidence item passed its integrity check); WO-F1 reconciles this before any chip ships.
3. The page-level `NOT_ELIGIBLE` banner cannot be dismissed, on desktop or mobile.
4. The demoted synthetic score path (`/v1/risk/score`) is not a data source for any new screen.

### D6. Ordering

Track A, Track C and Track D proceed in parallel, each in its own work orders, one work order per pull request.
Track C and Track D work never weakens a Track A gate, and Track A never waits on them.

## Consequences

- The charter, prune list and `AGENTS.md` are amended in place with pointers to this ADR; nothing is deleted.
- New work orders WO-C01… (Track C) and WO-F01… (Track D) are added to
  [`WORK_ORDERS.md`](../00-master/WORK_ORDERS.md).
- External material may use the product-family names above. It may not describe any Core indicator as
  validated, calibrated, production-eligible, or as a flood hazard; the prohibited claims in charter §6 apply
  to Core and Evidence alike.

## What this ADR does not decide

- Which pluvial or fluvial flood source qualifies for any country beyond NL.
- Bias correction, downscaling, or multi-model ensembles.
- A GCC Country Pack, or which GCC regulation it would map.
- The status of the "24 September 2026" Türkiye taxonomy regulation cited in founder notes; the repository's
  Türkiye pack rests on SPK decision `i-SPK.128.29` of 13 August 2026 until a sourced record says otherwise.
