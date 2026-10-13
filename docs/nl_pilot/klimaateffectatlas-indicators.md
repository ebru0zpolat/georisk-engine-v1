# Klimaateffectatlas indicators — NL workstream scope

> **Status: NOT_IMPLEMENTED.** No connector, no snapshot, no licence record, no
> indicator value. This document opens the workstream mandated by
> [ADR-0007](../decisions/ADR-0007-klimaateffectatlas-replaces-aqueduct-nl.md);
> it does not describe shipped behaviour.

**Opened:** 2026-09-01
**Supersedes:** the Aqueduct NL water-stress indicator, removed by ADR-0007

## Why this exists

ADR-0007 removed WRI Aqueduct baseline water stress from the NL asset report —
wrong quantity (a basin withdrawals-to-supply ratio, not a building hazard),
wrong resolution (no discrimination inside a Randstad portfolio), wrong signal.
It named Klimaateffectatlas as the replacement.

Until this workstream lands, the NL asset report carries **no** water-related
chronic indicator. That is an absence, not a fallback. Per ADR-0007's
implementation note there is no feature flag and no substitute value; per the
repository's standing rule there is no synthetic fallback for a missing real
source.

## Indicators in scope

The five indicators ADR-0007 names, each independent and separately gated:

| # | Indicator | Quantity it answers | Status |
|---|---|---|---|
| 1 | Pluvial flooding | Surface-water inundation from intense rainfall at the asset | NOT_IMPLEMENTED |
| 2 | Heat stress | Urban heat exposure at the asset | NOT_IMPLEMENTED |
| 3 | Subsidence | Ground settlement affecting the structure | NOT_IMPLEMENTED |
| 4 | Lowest average groundwater level | Groundwater drawdown (foundation risk driver in NL) | NOT_IMPLEMENTED |
| 5 | Flood probability / depth exceedance | Return-period flood probability and depth | NOT_IMPLEMENTED |

Indicators 1 and 5 are, unlike Aqueduct, asset-discriminating at the resolution
an NL portfolio needs. Indicators 3 and 4 address the NL-specific foundation and
settlement pathway that a global template omits entirely — the "wrong signal"
ground in ADR-0007.

## Open gates — none of these is closed

Each must be closed with recorded evidence before any indicator emits a value.

| Gate | What closes it | State |
|---|---|---|
| **G-1 Licence** | Klimaateffectatlas terms read at a dated access, with source URL and terms version recorded; commercial-use and attribution position self-attested. ADR-0007 states CC BY 4.0 — that is the expectation to verify, not a verified fact on file | open |
| **G-2 Source identity** | The exact publishing authority, dataset identifiers and versions for each of the five indicators | open |
| **G-3 Access path** | Whether each indicator is retrievable programmatically (WMS/WCS/API/bulk), and at what resolution and CRS | open |
| **G-4 Semantic validation** | CRS, units, nodata semantics and value ranges per indicator, verified against the published documentation — not inferred from the data | open |
| **G-5 Snapshot contract** | Sealed, hash-verified snapshot with provenance, on the pattern the NL pilot already uses (deterministic replay; fail-closed on missing or tampered artefacts) | open |
| **G-6 Claim boundary** | For each indicator, whether it is a context indicator or an EAL term. An indicator without a defensible transfer function stays a context indicator and is never priced | open |
| **G-7 Retention** | Retention horizon and storage identifier for captured evidence | open |

## Claim boundary, fixed now

Set before implementation so it cannot drift during it:

- An indicator with no transfer function is a **context indicator** and must
  never be priced into EAL. This is the same rule that governed the removed
  Aqueduct indicator, and the reason it was never an EAL term.
- No indicator may emit a value from a synthetic, interpolated or default source.
  Missing coverage fails closed and is reported as missing.
- Nothing in this workstream changes `production_eligible` or
  `controlled_pilot_eligible`; both remain false.
- Implementing an indicator is not evidence that it is correct for the NL
  portfolio. G-4 and G-6 are the checks that establish that, and both are open.

## Not in scope

- Anything outside NL assets. ADR-0007 is NL-scoped; the Turkish comparison
  reference in `app/services/validation_service.py` and the unconfigured
  provider seam in `app/data_centres/water_stress.py` are untouched.
- Reinstating Aqueduct under any name. The reference implementation is retained
  on `feat/geo-61-aqueduct-nl-vector-pack` for a possible non-NL portfolio only.
