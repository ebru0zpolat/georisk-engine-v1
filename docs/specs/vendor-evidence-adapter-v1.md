# Spec — third-party evidence adapter v1

**Status:** BINDING specification. Implementation target of WO-09/WO-10/WO-11.
**Version:** `vendor-adapter-v1` · **Date:** 19 September 2026
**Consumes:** a third-party physical-risk output · **Produces:** VERA-RAP `Evidence` + `Claim` objects and a
per-requirement evaluation, which [`defensibility-gap-report-v1.md`](defensibility-gap-report-v1.md) renders.

---

## 1. Scope and the honest limit

**In scope.** Reading a structured description of somebody else's physical-risk figures, binding each figure
to the evidence its producer supplied for it, evaluating that evidence against an enumerated requirement
catalogue, and reporting what is missing.

**Out of scope in v1, explicitly.**

- **PDF/XLSX parsing.** v1 takes a hand-filled JSON. Parsing vendor documents is an accuracy risk that would
  make the verifier itself unverifiable, and every parse error would read as a vendor defect. The transcription
  step is manual, attributed and hashed (§5).
- **Recomputation.** A vendor packet does not carry our `AuditTrailRecord`, so there is nothing to recompute.
  Recomputation is an *extension* (WO-16), attempted only when the third party publishes method and inputs,
  and never the basis of a verdict. This is the correction to the original two-week plan: the deliverable is
  **evidence sufficiency**, not recomputability.
- **Judging the vendor's model.** The adapter evaluates the *packet*, never the science behind it (INV-11).

## 2. Input contract — `third_party_report.json`

```jsonc
{
  "schema_version": "vendor-adapter-v1",
  "subject": {
    "producer": "string, the organisation whose output this is",
    "product": "string, the named output (report/model/dataset)",
    "product_version": "string | null",
    "as_of": "ISO-8601 date of the figures",
    "received_at": "ISO-8601 timestamp the artefact was received",
    "artefact_sha256": "hex64 of the source document as received",
    "transcribed_by": "identity of the person who filled this file",
    "transcription_note": "string — what was ambiguous in the source"
  },
  "figures": [
    {
      "figure_id": "string, unique in this file",
      "asset_ref": "string | null — opaque; never a personal identifier",
      "quantity": "expected_annual_loss | damage_ratio | hazard_intensity | exceedance_probability | return_period_level | risk_score | other",
      "value": 12345.67,
      "unit": "EUR | ratio | m | g | year | index | ...",
      "stated_claim": "verbatim wording the producer used about this figure",
      "evidence": [ /* §3 */ ]
    }
  ],
  "coverage": {
    "figures_supplied": 40,
    "assets_in_scope": 40,
    "assets_excluded_by_producer": 0,
    "exclusion_reasons_supplied": false
  },
  "boundary": {
    "data_boundary_agreed": true,
    "retention": "string — what happens to this file after the engagement",
    "may_be_quoted": false
  }
}
```

Rules:

- `artefact_sha256` is **mandatory**. A verdict about an unhashed artefact is unreproducible (INV-05/06).
- `stated_claim` is recorded verbatim. The verdict is about the claim the producer actually made, not about
  the claim we would have made.
- `asset_ref` is opaque. No address, name, coordinate or personal identifier enters this file.
- An empty `evidence` array is legal and meaningful: it yields `INSUFFICIENT_EVIDENCE` with every requirement
  as a blocker. That is a valid, common and saleable result.

## 3. Evidence item

```jsonc
{
  "evidence_id": "string, unique in this file",
  "requirement_id": "R-03",
  "kind": "source_identity | licence | semantics | datum | method | input_data | uncertainty | exclusion | aggregation | recency",
  "content": "verbatim or summarised statement supplied by the producer",
  "locator": "page / section / file the statement was taken from",
  "artefact_sha256": "hex64 | null — hash of the supporting artefact, if one was supplied",
  "producer_asserted": true,
  "independently_checkable": false,
  "independently_checked": false,
  "check_result": "null | passed | failed",
  "valid_until": "ISO-8601 | null"
}
```

`producer_asserted: true` with `independently_checked: false` maps to `VerificationStatus.UNVERIFIED` — the
producer's own word is evidence *that a claim was made*, not evidence that it holds. This distinction is the
adapter's core value and must never be collapsed.

## 4. Requirement catalogue v1

Derived from the gates this repository already enforces on its own numbers. Each requirement has a blocker
code (`MISSING_<ID>` unless stated) used identically by `app/resilience/triage.py` and the gap report.

| ID | Requirement | Blocker code | Applies to |
|---|---|---|---|
| R-01 | Hazard source identity **and** version named | `MISSING_SOURCE_IDENTITY` | all |
| R-02 | Licence / use-rights evidence for that source, independent of the producer's assertion | `MISSING_SOURCE_LICENCE` | all |
| R-03 | Quantity semantics stated: is the number a probability, a hydraulic load, a return-period level, an index? | `AMBIGUOUS_QUANTITY_SEMANTICS` | all |
| R-04 | Vertical datum, units and horizontal CRS declared for every spatial input | `MISSING_DATUM_DECLARATION` | spatial |
| R-05 | Differenceability: any depth derived by subtraction uses two sources in the same datum | `DATUM_MISMATCH` | depth |
| R-06 | Elevation source sealed and versioned | `MISSING_ELEVATION_SOURCE` | depth |
| R-07 | Vulnerability / damage function cited to a published source | `MISSING_VULNERABILITY_CITATION` | loss |
| R-08 | Asset value basis stated and not an indicative rate | `INDICATIVE_VALUE_BASIS` | money |
| R-09 | Method version recorded and stable | `MISSING_METHOD_VERSION` | all |
| R-10 | Inputs published sufficiently for an independent party to recompute | `NOT_RECOMPUTABLE` | all |
| R-11 | Uncertainty stated as a range or distribution, not a point | `MISSING_UNCERTAINTY` | all |
| R-12 | Forward horizons traced to a cited scenario, not an invented uplift | `UNCITED_HORIZON_FACTOR` | 2030/2050 |
| R-13 | Assets not analysed are listed with a reason | `SILENT_EXCLUSION` | portfolio |
| R-14 | Aggregation rule declared; claim states not averaged | `UNDECLARED_AGGREGATION` | portfolio |
| R-15 | As-of date present and within the producer's stated validity horizon | `STALE_AS_OF` | all |
| R-16 | Synthetic, modelled-default or fallback inputs disclosed as such | `UNDISCLOSED_SYNTHETIC_INPUT` | all |

**Applicability is evaluated before sufficiency.** A requirement that does not apply to a quantity is recorded
as `not_applicable` with the reason — never silently skipped (INV-02, and the same precedence discipline as
`app/regulation/verify.py`).

**R-16 is the requirement this repository is uniquely placed to judge**, because `STUBS.md` is an existing,
severity-graded inventory of exactly this failure in our own system.

## 5. Transcription integrity

The manual step is the weakest link, so it is fenced:

1. The source artefact is hashed **before** transcription; the hash is in `subject.artefact_sha256`.
2. `transcribed_by` and `transcription_note` are mandatory and appear in the gap report.
3. Every `evidence.locator` must point into the hashed artefact; a locator that cannot be resolved is a
   transcription defect, not a vendor defect, and is reported in a separate `transcription_findings` block.
4. Two transcriptions of the same artefact that disagree on any `stated_claim` block the report until resolved.

## 6. Module contract

```
app/verification/vendor_adapter.py      # input JSON  -> Evidence[] + Claim[]
app/verification/requirements.py        # R-01..R-16 catalogue, data only
app/verification/sufficiency.py         # Claim + Evidence -> ClaimEvaluationResult
```

- The adapter constructs VERA-RAP `Evidence`/`Claim` objects and nothing else; it computes no risk quantity.
- Earned `EpistemicState`s come only from `sufficiency.py` through the evaluation token — never constructed
  directly.
- Nothing under `app/verification/` may import `app.loss` except `claim_state`, or `app.services` at all
  (INV-07 independence, extended to this path).
- The requirement catalogue is data, loadable and diffable; its version is stamped into every report.

## 7. Worked expectations (the self-test corpus, WO-15)

| Fixture | Expected verdict | Why it is in the corpus |
|---|---|---|
| Our own golden qualified asset, packaged as a third-party input | Majority `SUPPORTED`; `NOT_RECOMPUTABLE` absent | Proves the standard is satisfiable at all |
| Our own synthetic-labelled asset (`stub_global_mdr`) | `UNDISCLOSED_SYNTHETIC_INPUT` **absent** (we disclose), claim ceiling `SYNTHETIC` | Proves disclosure changes the verdict, not the number |
| Amsterdam LIWO case | `AMBIGUOUS_QUANTITY_SEMANTICS` on the probability figure | The flagship finding, reached mechanically |

A change that alters any expected verdict in this corpus requires a decision record. The corpus is the
regression suite for the product's own honesty.
