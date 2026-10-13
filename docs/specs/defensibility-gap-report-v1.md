# Spec — defensibility gap report v1

**Status:** BINDING specification. Implementation target of WO-12/WO-13/WO-14.
**Version:** `gap-report-v1` · **Date:** 19 September 2026
**Consumes:** the evaluation from [`vendor-evidence-adapter-v1.md`](vendor-evidence-adapter-v1.md)
**Governs:** the single artefact the product sells.

---

## 1. What this artefact is, and is not

**Is:** a reproducible statement of which claims in a supplied packet are defensible **on the evidence
supplied**, which are not, what is missing for each, and which single missing item would unlock the most.

**Is not:** an audit opinion, an assurance engagement, a certification, a compliance statement, or an
assertion that any number is wrong. There is no `INCORRECT` verdict in the vocabulary, by design (INV-11).

## 2. Verdict vocabulary

Exactly five, mapped from `EpistemicState` through [`claim-state-grammar-v1.md`](claim-state-grammar-v1.md):

| Verdict | Meaning | Ceiling |
|---|---|---|
| `DEFENSIBLE` | Every applicable requirement met with independently checkable evidence | `QUALIFIED` |
| `DEFENSIBLE_ON_DISCLOSED_SYNTHETIC` | As above, but a disclosed synthetic/modelled-default input contributes | `SYNTHETIC` |
| `CONDITIONALLY_DEFENSIBLE` | Met subject to named unverified conditions | `NOT_QUALIFIED` |
| `NOT_DEFENSIBLE_ON_EVIDENCE_SUPPLIED` | One or more applicable requirements unmet | `NOT_QUALIFIED` |
| `INTERNALLY_INCONSISTENT` | Supplied evidence contradicts itself or the stated claim | `NOT_QUALIFIED` |

`INTERNALLY_INCONSISTENT` is the only verdict that says something about the packet's *content* rather than its
completeness, and it must cite both sides of the contradiction.

## 3. Artefact schema

```jsonc
{
  "schema_version": "gap-report-v1",
  "grammar_version": "claim-grammar-v1",
  "requirements_version": "requirements-v1",
  "engine_commit_sha": "hex40",
  "produced_at": "ISO-8601",
  "subject": {
    "producer": "…", "product": "…", "product_version": "…", "as_of": "…",
    "artefact_sha256": "hex64",
    "transcribed_by": "…", "transcription_note": "…"
  },
  "scope_of_evidence_supplied": {
    "figures_assessed": 40,
    "evidence_items_supplied": 96,
    "evidence_items_independently_checkable": 11,
    "evidence_items_independently_checked": 11,
    "requirements_not_applicable": 22,
    "note": "Absence of evidence in this packet is not evidence about the underlying model."
  },
  "verdicts": [
    {
      "figure_id": "F-014",
      "quantity": "expected_annual_loss",
      "stated_claim": "verbatim",
      "verdict": "NOT_DEFENSIBLE_ON_EVIDENCE_SUPPLIED",
      "claim_ceiling": "NOT_QUALIFIED",
      "requirements": [
        {"requirement_id": "R-02", "status": "unmet", "blocker": "MISSING_SOURCE_LICENCE",
         "evidence_ids": [], "note": "Producer asserts a licence; no artefact supplied."},
        {"requirement_id": "R-05", "status": "met", "evidence_ids": ["E-07", "E-08"]},
        {"requirement_id": "R-12", "status": "not_applicable", "reason": "no forward horizon claimed"}
      ]
    }
  ],
  "gaps": [
    {
      "blocker": "MISSING_SOURCE_LICENCE",
      "requirement_id": "R-02",
      "figures_affected": 38,
      "value_at_stake": 41200000.0,
      "sole_blocker_value": 0.0,
      "what_would_resolve_it": "The licence or use-rights artefact for the named hazard source, hashed."
    }
  ],
  "universal_blockers": ["MISSING_SOURCE_LICENCE", "MISSING_UNCERTAINTY"],
  "readiness": {
    "defensible_value": 0.0,
    "total_value_assessed": 41200000.0,
    "distribution": {"DEFENSIBLE": 0, "DEFENSIBLE_ON_DISCLOSED_SYNTHETIC": 0,
                     "CONDITIONALLY_DEFENSIBLE": 2, "NOT_DEFENSIBLE_ON_EVIDENCE_SUPPLIED": 38,
                     "INTERNALLY_INCONSISTENT": 0}
  },
  "transcription_findings": [],
  "limits": [
    "Assessed on the evidence supplied in the named artefact only.",
    "No recomputation was attempted; inputs sufficient for recomputation were not published.",
    "This is not an audit opinion, assurance engagement or certification.",
    "Verdicts are not comparable across grammar or requirements versions."
  ],
  "trail": {"record_id": "…", "record_hash": "hex64", "prev_hash": "hex64"}
}
```

## 4. Ranking rules (reused from `app/resilience/triage.py`, not reimplemented)

- `value_at_stake` overlaps across gaps and **must never be summed**. The renderer states this on the page.
- `sole_blocker_value` is additive and is the **primary ranking key** — it answers "what does closing this
  unlock", which is the only question a budget holder asks.
- When every blocked figure carries several blockers, every `sole_blocker_value` is zero. That is a real
  answer, not an empty one, and `universal_blockers` carries it: the packet's mandatory floor.
- Claim states and verdicts are **never averaged**. The portfolio carries the weakest plus the distribution.
- A figure with no value (`value: null`, e.g. a hazard intensity) counts in `figures_affected` and never in
  the money fields.

## 5. Reproducibility requirements

1. Same input file + same three versions (`schema`, `grammar`, `requirements`) → byte-identical report except
   `produced_at`, which is excluded from the hashed payload.
2. The report is appended to the hash-chained trail; the record replays into the identical report (INV-06/08).
3. Verdicts are re-derived by an **independent** checker that may not import `app.verification` (INV-07,
   WO-14) — same discipline as `tests/verification/independent_eal.py`.
4. A mutation test deletes one evidence item at a time and asserts that exactly the dependent verdicts flip.

## 6. Rendering

Two renderings, one source of truth:

- **`report.json`** — the artefact. Everything else is derived.
- **`report.md`** — deterministic Markdown, generated from the JSON, no sentence that is not present as data.
  No narrative, no recommendation, no adjective.

A PDF or slide rendering is **not** in v1. Anything that cannot be generated deterministically from the JSON
is a consulting product, not this product.

## 7. Delivery conditions (non-negotiable, ship with the artefact)

1. The counter-party's artefact is not retained beyond the engagement unless retention is written in
   `boundary.retention`.
2. No producer is named in any public material without written consent (`boundary.may_be_quoted`).
3. The report carries its own version set and its `limits` block in every rendering. A report circulated with
   the limits removed is a misrepresentation.
4. If the engine cannot produce a report, it produces the reason. It never produces a partial report that
   reads as complete.
