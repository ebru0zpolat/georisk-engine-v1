# Work orders — Track A

**Status:** BINDING task list for [`ROADMAP_VERIFIER_V2.md`](ROADMAP_VERIFIER_V2.md).
**Date:** 19 September 2026
**How to use this file:** one work order = one pull request. Hand an agent the WO id and nothing else;
everything it needs is in the row and the specs it links. Do not batch work orders. Do not start a WO whose
`Depends on` is not merged.

**Universal acceptance criteria — apply to every WO below, never restated:**

- Full suite green: `PYTHONPATH=. pytest -q --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key`
- No readiness flag, `production_eligible` value or `Literal[False]` changed (INV-10)
- Every new invariant has a test that fails when the invariant is removed
- Any new synthetic input has a `STUBS.md` row with severity and a specific replacement plan (INV-04)
- No new claim-promotion path (INV-01); no silent refusal (INV-02)
- PR description names the invariants the change touches

---

## S0 — Custody

### WO-00 · Fix write-once atomicity
**Depends on:** nothing. **Blocks:** everything.
**Problem:** `tests/ops/test_geo62_security_hardening.py::TestWriteOnceAtomicity::{test_temp_file_cleanup_on_success,
test_temp_file_cleanup_on_failure}` fail — a `.tmp` path survives in the target directory on both paths.
**Steps:** (1) establish whether this reproduces on a clean `main` checkout and in CI, or is macOS/working-tree
specific — record the answer in the PR; (2) fix the writer so no residue exists on either path; (3) add a test
asserting the directory is byte-for-byte unchanged after a failed write.
**Accept:** both tests pass; the new test fails if the cleanup is removed.
**Why it blocks:** sealed-artifact atomicity is load-bearing for every provenance claim (INV-06).

### WO-01 · Commit the claim algebra
**Depends on:** WO-00. **Files:** `app/loss/claim_state.py`, `tests/loss/test_m1_*.py`, `tests/test_m1_portfolio_claims.py`.
**Accept:** files tracked; a test asserts `weakest_claim` returns the minimum over every 3³ combination; a test
asserts `EvidenceLine` rejects a `QUALIFIED` row carrying `fixture_ids`.

### WO-02 · Commit the triage layer
**Depends on:** WO-01. **Files:** `app/resilience/`, `tests/resilience/`, `scripts/run_resilience_triage_demo.py`.
**Accept:** tracked; tests cover the two documented raise conditions (`QUALIFIED` + blocker; `NOT_QUALIFIED` +
no blocker) and the all-zero `sole_blocker_value` → `universal_blockers` case.

### WO-03 · Commit the NL spatial foundation
**Depends on:** WO-01. **Files:** `app/loss/ldo_band_semantics.py`, `app/loss/ahn_elevation.py`,
`app/nl_pilot/ldo_probability_guards.py`, `tests/nl_pilot/*`, `tests/loss/test_ldo_band_semantics.py`,
`tests/loss/test_liwo_composite_guard.py`, `data/nl_spatial_foundation/`, the `docs/nl_pilot/*` records.
**Accept:** tracked; a test asserts `-999.999` and `-9999.0` are both invalid and that the `value > 0.0`
invariant holds for depth- and velocity-like bands; the Amsterdam `SEMANTICALLY_AMBIGUOUS` resolution is
covered by a test that fails if it silently becomes `VALID_DATA`.
**Note:** this is a demonstration asset, not a pilot deliverable (see [`PRUNE_LIST.md`](PRUNE_LIST.md) §3).

### WO-04 · Land the governance set
**Depends on:** WO-00. **Files:** the charter, invariants, roadmap, prune list, glossary, three specs,
`README.md`, `AGENTS.md`, this file.
**Accept:** superseded documents carry an in-place banner pointing at the charter; `.cursor/rules/` and
`.agents/skills/georisk-engine/SKILL.md` point at `AGENTS.md` rather than restating rules.

---

## S1 — Grammar bridge

### WO-05 · Write the mapping (documentation only)
**Depends on:** WO-04. **Deliverable:** [`claim-state-grammar-v1.md`](../specs/claim-state-grammar-v1.md) reviewed
and any cell disagreement resolved **before** code exists.
**Accept:** every cell of the §3 ceiling table has a one-line justification; footnotes ¹²³ are accepted or amended.

### WO-06 · Implement `claim_bridge`
**Depends on:** WO-05. **Files:** `app/verification/__init__.py`, `app/verification/claim_bridge.py`.
**Accept:** exports exactly `BridgeResult`, `bridge`, `CEILING_TABLE`; import restrictions of the spec §6 hold
(assert with an import-linting test); no I/O, no clock.

### WO-07 · Property-test the bridge
**Depends on:** WO-06. **Files:** `tests/verification/test_claim_bridge.py`.
**Accept:** the full 240-combination cross-product is enumerated, not sampled; the five properties in spec §5
are each a named test; a deliberately introduced promotion in a scratch branch makes the suite fail (state this
was checked in the PR).

### WO-08 · Blocker-code registry
**Depends on:** WO-06. **Files:** `app/verification/requirements.py` (data only), refactor
`app/resilience/triage.py` to consume it.
**Accept:** exactly one definition of each blocker code in the repository; a test asserts no code string is
constructed inline anywhere under `app/` (grep-based test is acceptable and preferred for being blunt).

---

## S2 — Adapter and gap report

### WO-09 · Input contract
**Depends on:** WO-08. **Files:** `app/verification/schemas/third_party_report.py`,
`docs/specs/vendor-evidence-adapter-v1.md` (already written), `data/verification/examples/*.json`.
**Accept:** pydantic model with `extra="forbid"`; `artefact_sha256` mandatory and validated as hex64; an empty
`evidence` array is accepted and produces every requirement as a blocker; a figure with a personal identifier
in `asset_ref` is rejected by a validator.

### WO-10 · Adapter
**Depends on:** WO-09. **Files:** `app/verification/vendor_adapter.py`, `tests/verification/test_vendor_adapter.py`.
**Accept:** produces VERA-RAP `Evidence`/`Claim` objects only; computes no risk quantity (test: no arithmetic on
`figures[].value`); `producer_asserted && !independently_checked` maps to `UNVERIFIED` — a test asserts this is
never collapsed to `VERIFIED`.

### WO-11 · Sufficiency evaluator
**Depends on:** WO-10. **Files:** `app/verification/sufficiency.py`, `tests/verification/test_sufficiency.py`.
**Accept:** applicability evaluated before sufficiency, with `not_applicable` carrying a reason; earned
`EpistemicState`s are produced only through the evaluation token; every unmet requirement emits its registry
blocker code; there is no verdict meaning "incorrect" (INV-11) — a test asserts the vocabulary is exactly the
five in the report spec §2.

### WO-12 · Gap report
**Depends on:** WO-11. **Files:** `app/verification/report.py`, `tests/verification/test_report.py`.
**Accept:** emits the schema in [`defensibility-gap-report-v1.md`](../specs/defensibility-gap-report-v1.md) §3;
ranking calls the triage implementation rather than reimplementing it; `limits` and `scope_of_evidence_supplied`
are non-optional (test: removing either fails validation); `value_at_stake` carries its non-additive note.

### WO-13 · Trail and replay
**Depends on:** WO-12. **Files:** `app/verification/report.py`, `tests/verification/test_report_replay.py`.
**Accept:** report appended to the hash-chained trail; replay from the record reproduces it byte-identically
with `produced_at` excluded from the hashed payload; `verify_chain()` passes after N reports.

### WO-14 · Independent checker
**Depends on:** WO-12. **Files:** `tests/verification/independent_gap_report.py` (stdlib only).
**Accept:** module docstring carries the same prohibition as `independent_eal.py`; an import test asserts it
imports nothing from `app.`; it re-derives every verdict in the corpus from the input JSON + the published
requirement catalogue and agrees with the engine.

### WO-15 · Self-test corpus
**Depends on:** WO-12. **Files:** `data/verification/corpus/{golden_qualified,synthetic_labelled,amsterdam_ambiguous}.json`,
`tests/verification/test_corpus.py`.
**Accept:** the three expected verdicts in the adapter spec §7 are asserted; a mutation test deletes one
evidence item at a time and asserts exactly the dependent verdicts flip; changing an expected verdict requires a
`docs/decisions/` record (stated in the test's docstring).

### WO-16 · Optional recomputation extension
**Depends on:** WO-15. **Files:** `app/verification/recompute.py`.
**Accept:** attempted **only** when `R-10` is met; agreement or disagreement is reported as an additional finding
and **never** changes a verdict's ceiling by itself; when inputs are insufficient the result is
`NOT_RECOMPUTABLE`, not a failure.
**Guard:** this is where the product would quietly turn back into a hazard model. It computes nothing that is not
already published by the producer.

---

## S3 — Live counter-party

### WO-17 · Model-validation buyer packet
**Depends on:** WO-15. **Files:** [`docs/05-commercial/MODEL_VALIDATION_BUYER_PACKET.md`](../05-commercial/MODEL_VALIDATION_BUYER_PACKET.md).
**Accept:** §0 send gate restated for the new deliverable (corpus passing at the delivery SHA, not the portfolio
rehearsal); prohibited claims carried over; TR and EN drafts present and unsent.

### WO-18 · Discovery, five conversations
**Depends on:** WO-17. **Deliverable:** notes against the fixed eight-question script, segment and role recorded.
**Accept:** five completed; each records who is accountable for defending the number; "nobody is" is recorded as
a finding, not a failed call.

### WO-19 · One real artefact
**Depends on:** WO-18 and an explicit founder decision on the data boundary.
**Accept:** a gap report produced on a third-party output an institution actually holds; boundary terms written
before receipt; the producer is not named publicly without consent.

### WO-20 · Structured feedback
**Depends on:** WO-19. **Accept:** 90 minutes with the person who has to defend the number; every verdict they
reject is recorded verbatim, including the ones we think are right.

### WO-21 · Decision
**Depends on:** WO-20. **Accept:** a dated decision record: continue, reposition or stop, naming the evidence
and testing it against the kill criteria in the roadmap §9.

---

## Track C — Core indicators ([ADR-0008](../decisions/ADR-0008-product-family-and-own-indicator-engines.md) D2–D4)

Parallel to Track A; never blocks it and never weakens one of its gates. The universal acceptance criteria apply.
Every index here is capped at `NOT_QUALIFIED` until WO-C06 recomputes it independently.

### WO-C01 · Method note (documentation only)
**Depends on:** nothing. **Deliverable:** `docs/specs/core-indicators-v1.md`.
**Accept:** normative definitions of Rx1day, Rx5day, R95pTOT, R99pTOT, TXx, TR (TN > 20 °C) and one humid-heat index
(wet-bulb or WBGT approximation, choice justified); input variables and units per index; baseline 1991–2020 and
multi-year horizon windows as in the climate-data decision record; every refusal named as a blocker code to be
registered in WO-08; the note is sufficient for WO-C06 to be written from it alone.

### WO-C02 · Extreme-precipitation indices
**Depends on:** WO-C01. **Files:** `engine/climate/indices_etccdi_precip.py`, `tests/climate/test_indices_precip.py`.
**Accept:** the four precipitation indices as pure numpy functions over daily series; wet-day threshold 1 mm;
non-finite or negative input refuses; leap-day and `noleap` calendars covered; a test asserts no output field or
docstring calls the result a flood quantity.

### WO-C03 · CMIP6 precipitation adapter
**Depends on:** WO-C02. **Files:** `engine/climate/cmip6_precip_adapter.py`, tests.
**Accept:** the CLIM-03 contract of the heat adapter holds unchanged (per-file SHA-256, licence allowlist,
deterministic historical+SSP merge, complete-year windows, in-domain only); `pr` in kg m⁻² s⁻¹ converted to
mm/day with the unit checked, not assumed; shared code is factored out of the heat adapter only if the heat
adapter's tests pass byte-identically.

### WO-C04 · Absolute heat indices
**Depends on:** WO-C01. **Files:** `engine/climate/indices_etccdi.py`, heat adapter, tests.
**Accept:** TXx and TR added beside WSDI/TX90p; TR requires `tasmin` and refuses without it; existing WSDI/TX90p
outputs are unchanged.

### WO-C05 · Humid heat and coastal cells (GCC applicability)
**Status:** slice 1 (method core, `engine/climate/humid_heat.py`) and slice 2 (CMIP6/ERA5 file adapters,
`engine/climate/humid_heat_adapter.py`, CLIM-03 contract reused) landed; Tw agrees with the Davies-Jones reference
implementation to 0.000145 °C (spec §4.6). Measured on real ERA5 Gulf data (spec §5.1), which showed the daily
pairing undercounts Tw ≥ 31 °C days by 75 %; decisions D1–D3 (spec §5.2, accepted 2026-10-13) moved CMIP6 to 3-hourly
`tas`/`huss`/`ps` (published by both allowlisted models), gate each threshold count on its own measured count error
(±20 %), and treat dewpoint excess ≤ 0.01 K as saturation, counted. ERA5 licence CC BY 4.0 verified; citation and
attribution travel with every record. Real CMIP6 3hr files (MPI-ESM1-2-LR/HR, Gulf, 2010–2014) run end to end
(spec §5.3); two adapter fixes followed (coordinate noise, partial edge days). D4 (CMIP6 supersaturation up to
110 % RH is saturation, counted) and D5 (§6 unchanged; sea cells refuse) accepted 2026-10-13, spec §5.4. Open: a
finer-resolution source for Gulf-coast assets (Doha, Abu Dhabi refuse at 0.9375°); a full assessment needs ERA5
for years overlapping a model window.
Depends on WO-C04 relaxed: humid heat uses none of TXx/TR.
**Depends on:** WO-C04. **Spec:** [`humid-heat-indicator-v1.md`](../specs/humid-heat-indicator-v1.md). **Files:** humid-heat index module, adapter changes, tests.
**Accept:** every section of the spec implemented as written: Davies-Jones Tw from 3-hourly `tas`, `huss` and `ps` (`hurs` not used);
the measured approximation error (§5) and model-baseline gate (§7.4) ship with every value; every asset output reports grid-cell
land fraction and distance to cell centre; an asset in a predominantly sea cell refuses with a named blocker; a
heat output for a location where humid heat is not computed carries that absence as a blocker.

### WO-C06 · Independent recomputation
**Depends on:** WO-C02, WO-C04. **Files:** `tests/verification/independent_etccdi.py` (stdlib only), tests.
**Accept:** written from WO-C01's note; an import test asserts it imports nothing from `engine.` or `app.`; it
recomputes every Track C index on the sealed test series and agrees exactly on every reported (rounded) value
and every count; for iterative algorithms the precision is fixed by the method note (humid heat: 0.01 °C).

### WO-C07 · Claim wiring
**Depends on:** WO-01, WO-08, WO-C06. **Accept:** indicator results carry provenance (INV-05) and a `ClaimState`
from the claim algebra; a test asserts no Track C path yields a stronger claim than its weakest input (INV-01).

---

## Track D — P0 frontend ([ADR-0008](../decisions/ADR-0008-product-family-and-own-indicator-engines.md) D5)

Implements the `.design/` artboards against [`MVP_P0_DESIGN_REQUIREMENTS.md`](../03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md).
Additional acceptance for every Track D WO: `cd frontend && npx eslint . && npx tsc -b` clean; no sample figure from
the artboards ships as a value; the page-level `NOT_ELIGIBLE` banner cannot be dismissed; `/v1/risk/score` is not
a data source.

### WO-F01 · Tokens and chip dictionary
**Depends on:** nothing. **Files:** `frontend/src/` token stylesheet, chip component, a claim-control test.
**Accept:** the design brief's `VERIFIED` reconciled with the glossary's `VERIFIED` (record the resolution); the
brief's open questions on `blocked` and `not-validated` answered in writing; the font conflict between the brief
(Inter) and the canvas notes (IBM Plex) resolved against `frontend/src/index.css`; a test fails if a chip string
is not in the dictionary.

### WO-F02 · Portfolio upload and triage (P0-3)
**Depends on:** WO-F01. **Accept:** coverage count always clickable; every excluded asset listed with its reason;
no asset drops silently; batch and size limits shown when exceeded.

### WO-F03 · Asset detail (P0-4)
**Depends on:** WO-F01. **Accept:** portfolio → asset → evidence path unbroken; every waterfall step labelled with
its chip; horizon switch changes waterfall, band and drivers together.

### WO-F04 · Evidence viewer (P0-2)
**Depends on:** WO-F01. **Accept:** opened by `audit_id`; identity, source manifest, integrity and limitation panels
rendered from the API; missing or blocked evidence weakens the displayed claim without hiding the result.

### WO-F05 · Mobile snapshot and field triage
**Depends on:** WO-F03. **Accept:** responsive web at 390×844; read-only snapshot; triage corrections queue on the
device and re-runs stay on desktop.

### WO-F06 · Cloudflare Pages hosting
Hosting, not an artboard: the static marketing pages and the P0 shell need a deploy target after Vercel blocked the
account. Linear [GEO-221](https://linear.app/georiskengine/issue/GEO-221) carries the cut-over steps and the
post-deploy `curl` checks.
**Depends on:** nothing. **Files:** `frontend/public/_redirects`, `frontend/scripts/flatten-clean-urls.mjs`,
`frontend/scripts/verify-public-assets.mjs`, `frontend/package.json`, `frontend/vite.config.ts`, CI `frontend` job.
**Accept:** every clean-URL page builds to `dist/<page>.html` and is served at its canonical URL without a trailing-
slash redirect; `_redirects` holds the legacy TSRS 301 and no SPA catch-all; CI fails if a directory index is left
for a clean-URL page, if the catch-all returns, or if `dist/404.html` exists; canonicals and `sitemap.xml` unchanged.

---

## Sequencing summary

```
WO-00 ─┬─ WO-01 ─┬─ WO-02 ─────────────────────────────┐
       │         └─ WO-03                              │
       └─ WO-04 ── WO-05 ── WO-06 ─┬─ WO-07            │
                                    └─ WO-08 ── WO-09 ─┴─ WO-10 ── WO-11 ── WO-12 ─┬─ WO-13
                                                                                    ├─ WO-14
                                                                                    └─ WO-15 ─┬─ WO-16
                                                                                              └─ WO-17 ── WO-18 ── WO-19 ── WO-20 ── WO-21
```
