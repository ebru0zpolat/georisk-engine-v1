# ICP scoring rubric — NL CRE pilot (E4.1)

**Version:** v1.0 — frozen 2026-09-01
**Scope owner:** GEO-181 / GEO-209
**Relationship to [`ICP.md`](./ICP.md):** `ICP.md` describes the long-run ICP across
banking, asset management and insurance in the EU/TR/UK/US. This rubric is narrower
on purpose: it scores accounts for the **NL CRE pilot** defined in
[`PILOT_PACKAGE_OVERVIEW.md`](./PILOT_PACKAGE_OVERVIEW.md) (50–500 Dutch CRE assets).
Where the two disagree, this rubric governs pilot account selection and `ICP.md`
governs the longer-term segment view.

**Freeze rule.** This rubric is frozen for the first 50 accounts (E4.2–E4.6). Scores
assigned under v1.0 are not re-scored under a later version; a change of weights
opens v1.1 and applies to accounts scored after it.

---

## Dimensions and weights

Six dimensions, 100 points total. Each is scored 0 / 1 / 2 / 3 and multiplied by its
weight. Every score must cite a source (document, URL, filing, or a dated
conversation) — an uncited dimension scores **0**, never a guess.

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| D1 | Portfolio fit | 25 | NL CRE assets in the 50–500 band |
| D2 | Regulatory pressure | 20 | A dated obligation that makes physical-climate evidence due |
| D3 | Evidence burden | 20 | Someone must currently defend these numbers to a third party |
| D4 | Buyer accessibility | 15 | A named role exists and is reachable |
| D5 | Data readiness | 10 | They can hand over an asset list we can resolve |
| D6 | Reference value | 10 | A logo/reference that makes account 11 easier |

### D1 — Portfolio fit (×25)

The bands are exhaustive over portfolio size — every count from 0 upward falls in
exactly one row.

| Score | Criterion |
|---|---|
| 3 | 50–500 NL commercial assets, single owner/manager, addresses obtainable |
| 2 | 50–500 NL commercial assets but split across entities or mandates; **or** 20–49 or 501–2,000 assets under a single owner/manager (adjacent to the pilot band — scope is negotiable in one step) |
| 1 | 20–49 or 501–2,000 assets split across entities or mandates; **or** any NL CRE count outside 20–2,000 (<20 or >2,000) |
| 0 | No NL CRE, or residential-only, or NL exposure is indirect |

The pilot scope is 50–500 assets ([`PILOT_PACKAGE_OVERVIEW.md`](./PILOT_PACKAGE_OVERVIEW.md)).
20–49 and 501–2,000 score 2 rather than 3 because they are one scope conversation
away from the pilot, not because a smaller or larger engagement is impossible.

### D2 — Regulatory pressure (×20)

| Score | Criterion |
|---|---|
| 3 | A dated obligation in the next 12 months that requires physical-climate disclosure on these assets |
| 2 | Obligation applies but the deadline is beyond 12 months |
| 1 | Voluntary framework or investor pressure only |
| 0 | No identified obligation |

Cite the instrument and the date. "ESG-minded" is not a score.

### D3 — Evidence burden (×20)

| Score | Criterion |
|---|---|
| 3 | Published or filed physical-climate figures they must be able to defend, and a named reviewer/auditor who challenges them |
| 2 | Internal reporting to a risk or investment committee on these assets |
| 1 | Numbers produced ad hoc for a single stakeholder |
| 0 | No one currently asks them for this |

D3 is the dimension the product actually addresses. An account scoring 0 here should
not enter the queue even with a strong D1.

### D4 — Buyer accessibility (×15)

| Score | Criterion |
|---|---|
| 3 | Named individual, role confirmed, warm path (introduction, prior contact, shared network) |
| 2 | Named individual, role confirmed, cold path only |
| 1 | Role exists but the individual is not identified |
| 0 | No identifiable owner of this problem |

### D5 — Data readiness (×10)

| Score | Criterion |
|---|---|
| 3 | Asset list exists with addresses or BAG identifiers, and they can share it |
| 2 | List exists; sharing needs an NDA or internal approval |
| 1 | List would have to be assembled |
| 0 | Cannot or will not share asset-level data |

### D6 — Reference value (×10)

| Score | Criterion |
|---|---|
| 3 | Recognised NL market name, references publicly |
| 2 | Recognised, references privately |
| 1 | Credible but low visibility |
| 0 | No reference value, or reference would be counterproductive |

---

## Scoring and banding

`Total = Σ (dimension score × weight)`, maximum 300, normalised to 100 as
`Total / 3`.

| Band | Normalised score | Action |
|---|---|---|
| **A — Priority** | ≥ 70 | Enters the first 10 (E4.2). Full research: buyer role, trigger, hypothesis |
| **B — Queue** | 50–69 | Enters the next 40 (E4.6) in later parties |
| **C — Park** | 30–49 | Recorded, not worked. Re-score only on a new trigger |
| **D — Out** | < 30 | Out of scope for the pilot. Do not contact |

**Hard disqualifiers** — irrespective of score:

- no NL CRE exposure (D1 = 0);
- no one currently accountable for physical-climate evidence (D3 = 0);
- we would need data we are not licensed to hold, or they are not licensed to give.

---

## Recording format

One row per account in the target list. All eight fields are required.

| Field | Rule |
|---|---|
| Account | Legal entity name |
| D1…D6 | Score 0–3, each with a source citation |
| Normalised score | Computed, not asserted |
| Band | Derived from the table above |
| Buyer role | E4.3 — the role, not a guess at a person |
| Climate-risk trigger | E4.4 — the dated event that makes this due |
| Contact hypothesis | E4.5 — one sentence: why them, why now |
| Scored on / by | Date and reviewer |

---

## Claim discipline

A score in this rubric is an internal prioritisation estimate. It is not traction,
not a pipeline, not a qualified lead, and not evidence of demand. Under the plan's
closing rules, "traction" may only be claimed from recorded conversations (E4.10),
and GEO-209 discovery output is the only thing that upgrades a hypothesis into a
finding. A high-scoring account list with zero conversations held is a research
artefact and must be described as one.
