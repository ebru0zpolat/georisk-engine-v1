# ADR-0007 — Replace Aqueduct 4.0 water stress with Klimaateffectatlas indicators for NL assets

- **Status:** Accepted
- **Accepted:** 2026-08-30
- **Committed to the repository:** 2026-09-01
- **Scope:** Netherlands asset report only
- **Supersedes:** the Aqueduct NL water-stress pack (PR #132, closed unmerged 2026-08-30)

## Record of provenance

This ADR was accepted on 2026-08-30 and, until 2026-09-01, existed only as the
closing comment on PR #132
([#issuecomment-5468246064](https://github.com/ebru0zpolat/georisk-engine/pull/132#issuecomment-5468246064),
author `ebruozpolat`, association MEMBER). This file commits that decision to the
repository unchanged in substance; the comment remains the dated source of record.

The numbering follows the project's existing decision log. ADR-0001 to ADR-0006
are not in the repository; this is the first ADR committed here.

## Context

The NL asset report carried WRI Aqueduct 4.0 Baseline Water Stress as a
context indicator. Aqueduct is openly published under CC BY 4.0 and the
engineering around the pack was sound — a vector contract, a two-stage
boundary-inclusive query, source and licence checksums, and zero-ambiguity
verification. The indicator itself is what this decision rejects, not the work
that produced it.

## Decision

Remove the Aqueduct baseline water-stress indicator from the NL asset report,
on three grounds.

**Wrong quantity.** Aqueduct baseline water stress is a withdrawals-to-supply
ratio. It answers "is this basin over-abstracted", not "is this building exposed
to a climate hazard". For a commercial building in the Rhine–Meuse delta, water
scarcity is not a material physical-risk driver.

**Wrong resolution.** Aqueduct is scored at hydrological-basin scale. There is
no meaningful variation between two assets in the Randstad, so the indicator
cannot discriminate within any realistic NL portfolio.

**Wrong signal.** A global basin-scale indicator applied to a Dutch asset reads
to a Dutch risk reviewer as a global template pasted onto a local problem, and
it displaces the hazards that are material here.

Aqueduct is replaced, for NL assets, by Klimaateffectatlas (CC BY 4.0)
indicators covering:

1. pluvial flooding;
2. heat stress;
3. subsidence;
4. lowest average groundwater level;
5. flood probability / depth exceedance.

## Implementation note

Delete the Aqueduct adapter and its configuration block. Do **not** leave it
behind a feature flag.

## Consequences

### What this ADR removes

- `app/nl_pilot/water_stress.py` — the NL-scoped Aqueduct BWS adapter
  (`aqueduct-bws-v0.1`, sealed snapshot `aqueduct-amsterdam-v1`), together with
  its `synthetic_fixture_snapshot` fallback (STUBS.md #27).
- `scripts/vendor_aqueduct_water_stress.py`, `scripts/run_water_stress_demo.py`.
- `tests/nl_pilot/test_water_stress.py`, `docs/nl_pilot/water-stress-context.md`.
- The `WRI Aqueduct 4.0` entry in the frontend evidence manifest, which asserted
  a source the engine no longer produces any value from.

Closing PR #132 unmerged was itself part of this deletion: the pack it carried
never reached `main`, so there was nothing there to revert.

### What this ADR deliberately does not touch

- `app/services/validation_service.py` — Aqueduct appears there as a comparison
  reference for a Turkish asset (Erdemir reports against Aqueduct itself). That
  is outside this ADR's NL scope and is unchanged.
- `app/data_centres/water_stress.py` — an unconfigured provider seam with no
  built-in score and no synthetic fallback. It is not an Aqueduct adapter.
- The generic `water_stress` compound driver in `app/scoring/risk_score.py` and
  `app/schemas/risk.py`, which is derived from land/ocean/agriculture components
  and has never been an Aqueduct quantity.
- The `feat/geo-61-aqueduct-nl-vector-pack` branch, retained as the reference
  implementation should the Aqueduct pack ever be wanted for a non-NL portfolio.

### What this ADR does not yet deliver

Klimaateffectatlas is **not implemented**. No connector, snapshot, licence record
or indicator exists for it. See
[`docs/nl_pilot/klimaateffectatlas-indicators.md`](../nl_pilot/klimaateffectatlas-indicators.md)
for the scope of that workstream and its open gates. Until it lands, the NL asset
report carries no water-related chronic indicator at all — an absence, not a
fallback. No synthetic or substitute value may be emitted in its place.

This ADR changes no readiness flag. `production_eligible=false` and
`controlled_pilot_eligible=false` are unaffected.
