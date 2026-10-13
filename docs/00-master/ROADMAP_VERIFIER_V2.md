# Roadmap — the verification product (Track A)

**Status:** BINDING execution plan.
**Date:** 19 September 2026
**Derives from:** [`PRODUCT_CHARTER_V2.md`](PRODUCT_CHARTER_V2.md) · **Enforced by:** [`ENGINEERING_INVARIANTS.md`](ENGINEERING_INVARIANTS.md)
**Task-level detail:** [`WORK_ORDERS.md`](WORK_ORDERS.md) — this file has stages and gates; work orders have acceptance criteria.

**Changes no readiness flag.** No stage here makes any output production-eligible.

---

## 1. No calendar

This roadmap carries **no dates, no week numbers and no deadline**. There is no external event forcing a
delivery date, the realistic horizon is measured in quarters and may run twelve to eighteen months, and a
manufactured deadline would buy exactly one thing: a reason to weaken a gate.

Sequence is real; duration is not asserted. A stage is open when the previous gate has passed and closed when
its own has. If a stage takes four times longer than it looks, the gate is still the gate.

**Where "two weeks" came from.** It was in the founding note as the estimate for a vendor-verification demo.
It is withdrawn: §4 explains why the demo as originally described (recomputing a vendor's number) is not a
short task but an impossible one as stated, and what replaces it. Any duration estimate that reappears in this
repository needs the evidence it rests on.

```
S0 Custody  →  S1 Grammar bridge  →  S2 Adapter + gap report  →  S3 Live counter-party
```

A gate is a **machine-checkable artefact**, never a judgement: if you cannot name the file or the test that
proves it, the gate has not passed.

---

## 2. S0 — Custody (blocks everything)

The charter's core assets are untracked. Nothing else starts.

| Step | Detail | WO |
|---|---|---|
| Fix the atomicity failures | `TestWriteOnceAtomicity` leftover `.tmp`; first establish whether it reproduces on clean `main` in CI | WO-00 |
| Commit the claim algebra | `app/loss/claim_state.py` + `tests/loss/test_m1_*.py` | WO-01 |
| Commit the triage layer | `app/resilience/`, `tests/resilience/`, `scripts/run_resilience_triage_demo.py` | WO-02 |
| Commit the NL spatial foundation | `ldo_band_semantics.py`, `ahn_elevation.py`, `ldo_probability_guards.py`, LIWO/AHN catalogues and tests | WO-03 |
| Land the governance set | charter, invariants, this roadmap, specs, `README.md`, `AGENTS.md` | WO-04 |

**Gate S0:** `git status --porcelain` lists no untracked file under `app/`, `tests/`, `scripts/` or `docs/`;
full suite green (`--deselect` the one non-hermetic live-connector test); every new module has a test that
fails if its invariant is removed.

---

## 3. S1 — The grammar bridge

Make the two claim vocabularies meet, one-way.

| Step | Detail | WO |
|---|---|---|
| Write the mapping | `EpistemicState`/`VerificationStatus` → `ClaimState`, monotone downward only | WO-05 |
| Implement it | `app/verification/claim_bridge.py`, pure, no I/O, no pipeline import | WO-06 |
| Property-test it | promotion impossible by construction, not by review | WO-07 |
| Blocker-code registry | one enumerated set of codes shared by triage and the gap report | WO-08 |

**Gate S1:** a property test over the full cross-product of `EpistemicState × VerificationStatus × ClaimState`
proves no input combination yields a higher `ClaimState` than its weakest dependency; the blocker registry is
the single source of the codes used by `app/resilience/triage.py`.

---

## 4. S2 — Adapter and gap report (the demonstrable core)

**Correction carried from the founding note.** "Run a vendor report through the existing verifier and produce a
recomputability report" cannot be done at any duration: recomputation needs our `AuditTrailRecord` — sealed
inputs, curve id, method version — and a vendor packet does not contain one
([`GAP_ANALYSIS_2026-09-19.md`](GAP_ANALYSIS_2026-09-19.md) GAP-1). What is reachable, and worth more, is
**evidence sufficiency**: bind each supplied figure to the evidence its producer gave for it and report what is
missing. Recomputation stays as an extension for the minority of producers who publish method and inputs.

| Step | Detail | WO |
|---|---|---|
| Input contract | A neutral, hand-fillable `third_party_report.json` — the adapter never parses a PDF in v1 | WO-09 |
| Adapter | third-party figures → VERA-RAP `Evidence` + `Claim` objects | WO-10 |
| Sufficiency evaluator | per-claim verdicts, each citing the requirement it met or failed | WO-11 |
| Gap report | versioned artefact per [`defensibility-gap-report-v1.md`](../specs/defensibility-gap-report-v1.md), reusing `sole_blocker_value` ranking | WO-12 |
| Trail + replay | recorded in the hash-chained trail; replay reproduces it byte-identically | WO-13 |
| Independent checker | stdlib-only re-derivation that must not import `app.verification` | WO-14 |
| Self-test corpus | three fixtures with known-correct verdicts | WO-15 |
| Optional recomputation | only where the producer publishes method and inputs; an extension, never the basis of a verdict | WO-16 |

**Gate S2:** `python -m app.verification.report --input <file>` produces a gap report for all three corpus
fixtures; verdicts reproduce byte-identically from the trail record; the independent checker agrees on every
verdict; a mutation test (delete one evidence field) flips exactly the verdicts that depend on it.

**Demonstration asset at this gate:** the Amsterdam case, verdict "cannot be read as an annual probability",
reached mechanically and cited.

---

## 5. S3 — Live counter-party

Engineering stops being the constraint here; the thesis is.

| Step | Detail | WO |
|---|---|---|
| Rewrite the offer | model-validation packet, send gate restated for the new deliverable | WO-17 |
| Run discovery | the existing eight questions, unchanged, to validation/internal audit — five conversations | WO-18 |
| One real artefact | a gap report on a third-party output an institution actually holds, under an explicit data boundary | WO-19 |
| Structured feedback | 90 minutes from the person who has to defend the number; record every verdict they reject | WO-20 |
| Decision | continue / reposition / stop, written, with the evidence | WO-21 |

**Gate S3 (the only gate that decides anything):** one model-validation or internal-audit function outside this
company has run the report against a number they own and stated in writing what it got wrong. A gap report
nobody outside has challenged is an unvalidated product, regardless of test coverage.

---

## 6. Explicitly not in this plan

- Deriving an original flood probability (`faalkans × P(scenario | breach)`) — charter §4.
- Vendoring Turkish flood/elevation/seismic sources (the v1 record's S2–S4). Deferred, not cancelled; see §7.
- Any promotion of `expected-loss-v0.4` from opt-in to default.
- `/v1/risk/score`, Scenario-Lab, ORAS5, night-lights, NO₂ — see [`PRUNE_LIST.md`](PRUNE_LIST.md).
- Frontend work of any kind. The first deliverable is a JSON artefact and a CLI.

---

## 7. Reconciliation with `georisk-resilience-analytics-v1.md`

Both records are dated 19 September 2026 and agree on the diagnosis. They differ on the object.

| v1 record | This roadmap | Resolution |
|---|---|---|
| §4 triage module shipped | S0/WO-02 commits it; S2 reuses its ranking | **Adopted unchanged** |
| §5 S1 "expose triage on the portfolio path" | S2/WO-12 generalises it to third-party subjects | **Superseded by generalisation** — do the general case and the portfolio path falls out |
| §5 S2–S4 Susurluk vendoring → first Turkish `QUALIFIED` loss | Not in Track A | **Deferred.** It produces our own number, which the charter demotes to Track B. Revisit after Gate S3 |
| §5 S5 resilience investment analytics | Not in Track A | Deferred with S2–S4 |
| §3 geographic pivot to Türkiye | Neutral | The verification product is country-agnostic; the buyer, not the basin, decides the geography |
| §6 claims control | Unchanged and still binding | **Adopted verbatim** |

Where the two conflict, this roadmap wins for Track A work; the v1 record remains authoritative for the
resilience-analytics framing it introduced. Neither licenses a readiness-flag change.

---

## 8. Review cadence

Reviewed when a gate closes, and on a fixed rhythm in between so that a stalled stage is visible rather than
silent. Three lines, no prose:

1. `git status --porcelain | wc -l` (target 0 after Gate S0) and full-suite pass/fail counts.
2. Open stage, open gate, and the one artefact that would close it.
3. Discovery conversations completed against the fixed script (five before Gate S3), and how many said nobody
   is accountable for defending the number — that answer is a finding, not a failure.

A review that reports no movement twice running is a signal to re-scope the open work order, not to extend it.

## 9. Kill criteria

Stop Track A and say so plainly if, at Gate S3:

- no validation function will share an artefact even under an NDA-equivalent boundary — the deliverable has no
  legitimate input supply; or
- three or more reviewers say the gap report tells them only what they already knew — the finding is real but
  not a product; or
- a reviewer demonstrates that a verdict is wrong in a way the grammar cannot express — the grammar is
  incomplete, and that must be fixed before any further selling.
