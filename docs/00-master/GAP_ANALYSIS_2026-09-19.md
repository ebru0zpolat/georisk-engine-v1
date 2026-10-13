# Gap analysis — 19 September 2026

**Purpose:** establish, from the code and not from the documentation, what exists for
[`PRODUCT_CHARTER_V2.md`](PRODUCT_CHARTER_V2.md) and what does not.
**Method:** repository inspection plus one full test run at the working-tree state below. Every claim in
§2–§6 names the file it was read from. Where the documentation and the code disagree, the code is recorded.

## 0. Measured baseline

| Item | Value |
|---|---|
| Branch / HEAD | `main` @ `3e2ee37` |
| Working tree | 53 dirty entries (13 modified, 40 untracked) — **most of the v2-relevant code is uncommitted** |
| Test suite | `PYTHONPATH=. pytest -q --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key` |
| Result | **2152 passed, 3 failed, 2 skipped, 1 deselected, 45.24s** |
| Readiness flags | all false (unchanged) |

**The three failures, exactly:**

| Test | Cause | Severity |
|---|---|---|
| `tests/crawl/test_promotion_gate.py::test_promotion_reject_missing_verified_by` | Test asserts `match="Invalid or corrupt manifest"`; `scripts/crawl/promote_evidence.py:38` raises `INVARIANT VIOLATION: Missing verified_by identity.` The gate behaves correctly; the test's expected message is wrong. | Low — test defect, untracked work |
| `tests/ops/test_geo62_security_hardening.py::TestWriteOnceAtomicity::test_temp_file_cleanup_on_success` | A `.tmp` directory survives in the target directory after a successful write-once operation. | **Medium — this is a write-once/atomicity invariant, not a cosmetic leak.** |
| `…::test_temp_file_cleanup_on_failure` | Same leftover `.tmp` on the failure path. | Medium, same |

No v2 work may be merged while the two `WriteOnce` failures stand: sealed-artifact atomicity is load-bearing
for every provenance claim the product makes. Tracked as **WO-00** in [`WORK_ORDERS.md`](WORK_ORDERS.md).

---

## 1. Summary table

| Capability the charter needs | State | Evidence |
|---|---|---|
| Conservative claim algebra | **Built** | `app/loss/claim_state.py` (untracked) |
| Fail-closed regulatory screening | **Built** | `app/regulation/verify.py` |
| Hash-chained append-only trail | **Built** | `app/services/audit_trail.py` |
| Independent recomputation of our own numbers | **Built** | `tests/verification/independent_eal.py`, `app/loss/expected_loss.py:800` |
| Source licence / use-rights qualification gate | **Built** | `app/loss/flood_source_qualification.py` |
| Datum-mismatch guard | **Built** | `app/loss/flood_hazard_map.py` (`assert_differenceable`, `FLOOD_DATUM_MISMATCH`) |
| Evidence/claim grammar with earned states | **Built, isolated** | `app/research/vera_rap/{evidence,claims}.py` |
| Cognitive trace | **Built, isolated** | `app/research/vera_rap/trace.py` |
| EvidenceBoundBench | **Built, isolated** | `benchmarks/vera_rap/` |
| Portfolio evidence-gap ranking (our own) | **Built, uncommitted, not wired** | `app/resilience/triage.py` |
| **Third-party report ingestion** | **ABSENT** | — |
| **Third-party claim binding / verdicts** | **ABSENT** | — |
| **Defensibility gap report artefact** | **ABSENT** | — |
| **Bridge between the two claim vocabularies** | **ABSENT** | — |
| **Verification API surface / CLI** | **ABSENT** | — |
| Buyer packet aimed at model validation | **ABSENT** (sustainability-team packet exists) | `docs/05-commercial/TSKB_ANADOLU_SIGORTA_OUTREACH_PACKET.md` |

---

## 2. What is genuinely built (keep, and make load-bearing)

### 2.1 Claim algebra — `app/loss/claim_state.py`
`ClaimState ∈ {NOT_QUALIFIED, SYNTHETIC, QUALIFIED}` with `weakest_claim()` taking the minimum over
dependencies, and `EvidenceLine` refusing fixture promotion: `synthetic` or `fixture_ids` set forces
`synthetic=true`, non-empty `fixture_ids`, and a non-`QUALIFIED` claim, by model validator. This is the
single most reusable asset in the repository and it is **untracked**.

### 2.2 Fail-closed screening — `app/regulation/verify.py`
Strictly ordered precedence: applicability → official source artifact → threshold source → engineered data
→ numeric comparison. An unverified source cannot be repaired by supplying data. Status vocabulary is
deliberately non-compliance language (`threshold_satisfied` ≠ compliant). This *is* the verification
posture the charter sells, already written down once.

### 2.3 Trail and independent verifier
`compute_record_hash(prev_hash, payload)` over canonical JSON, `verify_chain()`, disk tip as chaining
source of truth. `tests/verification/independent_eal.py` is a stdlib-only reimplementation carrying an
explicit prohibition on importing `app.loss` / `app.services`, updated from `METHODOLOGY.md` rather than
from pipeline code. That independence discipline is the thing that makes a verification product credible;
it must be extended to the third-party path, not re-derived.

### 2.4 VERA-RAP — `app/research/vera_rap/`
`VerificationStatus ∈ {UNVERIFIED, VERIFIED, REJECTED, STALE, CONTRADICTED}` and
`EpistemicState ∈ {OBSERVED, INFERRED, HYPOTHESISED, SUPPORTED, CONDITIONALLY_SUPPORTED, CONTRADICTED,
INSUFFICIENT_EVIDENCE, REJECTED}`, with declared vs **earned** states separated by an evaluation token, and
enums that raise on implicit string/bool coercion. Immutable frozen JSON. This is the right grammar for
third-party claims and it already exists.

### 2.5 Evidence-gap ranking — `app/resilience/triage.py`
Distinguishes `value_at_stake` (overlapping, not additive) from `sole_blocker_value` (additive, the real
decision key), reports `universal_blockers` when nothing unlocks alone, refuses to average claim states,
and raises on the contradiction "QUALIFIED asset carrying a blocker". Structurally this is *already* the
defensibility gap report — pointed at our own portfolio instead of somebody else's.

---

## 3. The four gaps that block the charter

### GAP-1 — No third-party input path
Nothing in the repository can read an output that this engine did not produce. `recompute_eal_from_trail_record`
requires **our** `AuditTrailRecord` schema (record id, sealed depth, curve id, value, method version). A vendor
PDF/XLSX has no such record, so the existing verifier has nothing to recompute and correctly returns nothing.

**Consequence for the plan:** "run a vendor report through the existing verifier and produce a recomputability
report" is not a short task but an impossible one as stated, because recomputation presupposes an artefact
the vendor does not ship. The "two weeks" estimate that carried it is withdrawn; no duration in this
repository stands without the evidence it rests on. The reachable near-term product is **evidence sufficiency**, not
recomputation: bind each vendor figure to the evidence it claims and report what is missing. Recomputation
becomes available only for the subset of vendors who publish method and inputs.

Needed: [`docs/specs/vendor-evidence-adapter-v1.md`](../specs/vendor-evidence-adapter-v1.md).

### GAP-2 — Two claim vocabularies, no bridge
`ClaimState` (3 states, money path) and `EpistemicState` (8 states, research path) are deliberately isolated —
`evidence.py` says so in its first line. For Track A they must meet, in **one** direction only: a VERA-RAP
evaluation may lower a `ClaimState`, never raise one. Without a written mapping, any implementation will
invent its own and the promotion ban becomes unenforceable.

Needed: [`docs/specs/claim-state-grammar-v1.md`](../specs/claim-state-grammar-v1.md).

### GAP-3 — No verdict artefact
There is no schema for "here is what we found about your number". `app/resilience/triage.py` emits the right
*shape* but over our own portfolio rows. The artefact has to be versioned, hash-chained, replayable, and carry
its own limits, or it is a consulting slide rather than a product output.

Needed: [`docs/specs/defensibility-gap-report-v1.md`](../specs/defensibility-gap-report-v1.md).

### GAP-4 — Buyer mismatch in the only live commercial asset
`docs/05-commercial/TSKB_ANADOLU_SIGORTA_OUTREACH_PACKET.md` is well built: a send gate that refuses outreach
without a rehearsal record at the delivery SHA (§0), a fixed eight-question discovery script (§2.1), an honesty
box (§4.3), prohibited claims (§4.4). Its eight questions already interrogate the *validation* function —
Q2 "who challenged those figures", Q3 "what do you hand them", Q4 "what did you do with assets you didn't
trust". Those questions survive the buyer change unchanged.

**The offer does not.** §3 offers a free analysis of 20–50 of their assets. To model validation that is one
more vendor output — an addition to the population they are paid to challenge. The offer for that seat must be
"we will produce the defensibility gap report on a number you already own", which also changes the §0 send
gate: the proof required is no longer "we recomputed our own golden portfolio", it is "we read somebody else's
artefact and produced a defensible gap list".

Needed: [`docs/05-commercial/MODEL_VALIDATION_BUYER_PACKET.md`](../05-commercial/MODEL_VALIDATION_BUYER_PACKET.md).

---

## 4. Structural debt that will obstruct v2

| # | Finding | Why it matters now |
|---|---|---|
| D-1 | 40 untracked files carry the charter's core assets (`claim_state.py`, `resilience/`, LDO/AHN/LIWO work, 9 new test modules). | Everything v2 builds on is unversioned. A branch loss deletes the thesis. **First action, before any new code.** |
| D-2 | Two same-day direction records now exist: [`docs/roadmap/georisk-resilience-analytics-v1.md`](../roadmap/georisk-resilience-analytics-v1.md) (Susurluk pivot, S1–S5) and this charter. | Left unreconciled, an agent will implement S2 (vendor Turkish flood levels) believing it is the priority. Reconciliation is written into [`ROADMAP_VERIFIER_V2.md`](ROADMAP_VERIFIER_V2.md) §7. |
| D-3 | `README.md` still leads with "from climate maps to financeable adaptation" and documents `/v1/risk/score`, whose every number is synthetic (`STUBS.md` #3). | The public artefact contradicts the charter. Rewritten in this change. |
| D-4 | `AGENTS.md` contains only Cursor Cloud service/env notes; no product or invariant rules. | Any coding agent handed this repo optimises for a running server, not for the invariants that are the product. Rewritten in this change. |
| D-5 | 30+ live stub rows in `STUBS.md`, several `output-shaping`. | Under v2 these stop being embarrassments and become **test fixtures for the verifier**: a known-synthetic input whose correct verdict is known in advance. Reframed, not deleted. |
| D-6 | `/v1/risk/score`, ORAS5, night-lights, NO₂ and the Scenario-Lab path remain on the public API and in the README. | Charter §4 demotes them. They must be either labelled as a separate industrial-audit product or removed from the main narrative — see [`PRUNE_LIST.md`](PRUNE_LIST.md). |
| D-7 | The VERA-RAP research tree is isolated by design and unused by any product path. | Its grammar is the Track-A engine. The isolation must be broken *deliberately and one-way* (GAP-2), not casually. |

---

## 5. What is worth more than it looks

- **`SEMANTICALLY_AMBIGUOUS` (Amsterdam / LIWO).** Under v1 framing this blocks the pilot. Under v2 it is the
  single best demonstration asset in the repository: a case where the honest verdict is "this cannot be read as
  a probability", reached mechanically. Every competitor returns a number here.
- **`app/loss/ldo_band_semantics.py`.** The undocumented `-999.999` secondary sentinel, found by sealed spatial
  co-location analysis and turned into a `value > 0.0` invariant. This is exactly the class of defect the
  verification product is supposed to catch in other people's pipelines, caught in a public dataset, with the
  analysis sealed. It is a demo, not a footnote.
- **`STUBS.md` severity taxonomy** (`output-shaping` / `data-fallback` / `presentation`). It is already the
  vocabulary needed to grade somebody else's synthetic inputs.

---

## 6. Explicit non-findings

- No Turkish hazard, elevation or seismic value exists in the repository. Nothing here changes that.
- No live-baseline experimental result exists for VERA-RAP; the comparison harness is a mechanism test over
  scripted fixtures.
- The 45-second test run does not exercise network connectors; connector health is not assessed here.
- `tests/ops/test_geo62_security_hardening.py` failures were observed on this working tree on macOS. Whether
  they reproduce on a clean `main` checkout in CI was not established — WO-00 establishes it before fixing.
