# Engineering invariants

**Status:** BINDING on every change, human or agent. A pull request that violates one of these is rejected
regardless of what it enables.
**Date:** 19 September 2026 · **Authority:** second only to [`PRODUCT_CHARTER_V2.md`](PRODUCT_CHARTER_V2.md).

Each invariant states: the rule, why it exists, how it is enforced, and what a violation looks like.
An invariant with no enforcing test is a wish. If you add one, add its test in the same change.

---

## INV-01 — Claims never promote

**Rule.** A derived value's claim is the *weakest* of its dependencies. No code path may raise a
`ClaimState`, ever, for any reason, including operator override.

**Why.** Every commercial statement the product makes rests on the assertion that a number cannot become
more trustworthy than its worst input. One promotion path anywhere destroys the whole claim.

**Enforcement.** `app/loss/claim_state.py::weakest_claim`; `EvidenceLine` model validator rejecting fixture
promotion; the S1 property test over the full state cross-product.

**Violation looks like.** A `max()` over claim states; a default of `QUALIFIED`; an `if override:` branch;
a fixture id list on a `QUALIFIED` row; a synthetic input whose output is not `SYNTHETIC` or lower.

---

## INV-02 — Fail closed, and say why

**Rule.** Missing, unqualified or unreadable evidence produces a refusal carrying an enumerated blocker
code. Silence, a default value, a zero or a `None` that reads as "fine" are all violations.

**Why.** A refusal that does not name its cause cannot be acted on, and the ranked-gap product is built
entirely out of named causes.

**Enforcement.** `app/regulation/verify.py` precedence ladder; `app/resilience/triage.py` raising on a
`NOT_QUALIFIED` row that names no blocker; the blocker-code registry (WO-08).

**Violation looks like.** `except Exception: return 0.0`; a fallback constant reached when a source is
absent; a refusal returned as an empty list.

---

## INV-03 — Precedence is ordered and unrepairable

**Rule.** Gates are evaluated in a fixed order and a failure at gate *n* blocks gates *n+1…*. A later
input may never compensate for an earlier failure.

**Why.** "We had no licence for the source, but the numbers matched" is not a verification result.

**Enforcement.** `app/regulation/verify.py` docstring ladder and its tests.

**Violation looks like.** Supplying engineered data to resolve `source_unverified`; scoring "partial
credit" across gates.

---

## INV-04 — Every synthetic input is labelled, listed and ceilinged

**Rule.** Any synthetic, fixture, seeded, mock or fallback value that can reach an output carries
`synthetic=true` (or a `stub_` identifier, or a source string containing `synthetic calibration`), has a row
in [`STUBS.md`](../../STUBS.md) with a severity and a specific replacement plan, and ceilings its output's
claim at `SYNTHETIC`.

**Why.** Under v2 these are not embarrassments — they are the verifier's own test corpus, with known-correct
verdicts. That only works if the labelling is exhaustive.

**Enforcement.** `STUBS.md` review checklist; `.cursor/rules/ci-stubs-honesty.mdc`; claim ceiling per INV-01.

**Violation looks like.** A new fixture file with no `STUBS.md` row; a replacement plan reading "TBD".

---

## INV-05 — Provenance travels with the number

**Rule.** Every persisted figure carries: source identity, source version, SHA-256 of the sealed artefact,
method version, and the claim state. No silent evidence loss at any boundary — serialisation, aggregation,
report rendering or API response.

**Why.** The product's entire value proposition is answering "where did this come from" mechanically.

**Enforcement.** `data_versions` collectors on the flood path; trail payload schema; report schema.

**Violation looks like.** An aggregation that drops per-row provenance; a report field whose value has no
traceable origin; a hash recorded for a file that is then mutated in place.

---

## INV-06 — Append-only, hash-chained, write-once

**Rule.** The audit trail is append-only and chained (`record_hash = SHA256(prev_hash ‖ canonical_json)`),
with the **disk tip** as the chaining source of truth. Sealed artefacts are written once, atomically, with no
residue on either the success or the failure path.

**Why.** A trail that can be rewritten, or an artefact that can be half-written, proves nothing.

**Enforcement.** `app/services/audit_trail.py::verify_chain`; `TestWriteOnceAtomicity` (**currently failing —
WO-00**).

**Violation looks like.** Chaining from in-memory state after a restart; an in-place edit of a sealed file;
a leftover `.tmp`.

---

## INV-07 — The verifier is independent

**Rule.** Any component that verifies an output must not import the component that produced it. Verifiers
are written from the published method note, never by copying pipeline code, and use the standard library
only where practical.

**Why.** A verifier that shares code with the pipeline reproduces the pipeline's bugs and verifies nothing.
This is the invariant a model-validation buyer will test first.

**Enforcement.** `tests/verification/independent_eal.py` module prohibition; extended to the third-party
path by WO-14.

**Violation looks like.** `from app.loss import ...` inside a verifier; a verifier updated by copying a
pipeline diff; a shared helper module between the two.

---

## INV-08 — Determinism and replayability

**Rule.** Same inputs plus same method version produce byte-identical outputs. Non-determinism (wall clock,
uncontrolled iteration order, unseeded randomness, locale, floating-point path changes) is a defect.

**Why.** "Run it again and show me" is the buyer's first request.

**Enforcement.** Canonical JSON everywhere a hash is taken; replay tests from trail records.

**Violation looks like.** `datetime.now()` inside a hashed payload; iteration over an unordered set feeding
output order; rounding applied at different points on two paths.

---

## INV-09 — One-way bridge between claim vocabularies

**Rule.** A VERA-RAP evaluation (`EpistemicState`, `VerificationStatus`) may **lower** a `ClaimState` and may
never raise one. The mapping lives in exactly one module and is defined in
[`claim-state-grammar-v1.md`](../specs/claim-state-grammar-v1.md).

**Why.** The research grammar is expressive; the money grammar is conservative. Connecting them in both
directions would let an expressive "SUPPORTED" manufacture a `QUALIFIED`.

**Enforcement.** WO-06/WO-07 bridge module and its property test.

**Violation looks like.** A second mapping written inline at a call site; `SUPPORTED → QUALIFIED` without
the full dependency check.

---

## INV-10 — No readiness flag changes without an explicit decision record

**Rule.** `Literal[False]` readiness flags, `production_eligible`, and `decision == "demo_only"` change only
through a dated decision record naming the evidence. No roadmap, charter, refactor or "cleanup" changes them.

**Why.** These flags are the last line between a demo and a misrepresentation.

**Enforcement.** Type-level `Literal[False]`; release-manifest checks in the rehearsal script.

---

## INV-11 — Verdicts about third parties are bounded

**Rule.** A gap report states only: what was supplied, what was checkable, what was checked, and what the
result was. It must carry its own limits and never assert that a third party's number is *wrong* — only that
it is, or is not, defensible **on the evidence supplied**.

**Why.** Legal exposure, and correctness: absence of evidence in a packet is not evidence the underlying
model is bad.

**Enforcement.** Report schema requires a `limits` block and a `scope_of_evidence_supplied` block; WO-11
verdict vocabulary contains no "incorrect" state.

**Violation looks like.** "Vendor X's number is wrong"; an implied assurance opinion; a verdict resting on
evidence the counter-party never supplied.

---

## INV-12 — Language discipline

**Rule.** `verified`, `qualified`, `validated`, `evidence-bound`, `production-eligible` and `compliant` mean
exactly their machine definitions in [`GLOSSARY.md`](GLOSSARY.md) and nowhere else. Neutral threshold
language over compliance language, always.

**Why.** Every word on this list has a regulatory meaning that a buyer's counsel will test.

**Enforcement.** `pack-tr` claim scanner; glossary; review.

---

## Change control

To change an invariant: open a dated decision record under `docs/decisions/` naming the invariant, the reason,
the risk accepted, and the tests being changed. Then change the tests in the same pull request. Never weaken an
invariant inside a feature change.
