# Data-provider LOI — category decision (F1.1)

**Version:** v0.1
**Date:** 2026-09-01
**Scope owner:** GEO-173
**Verdict class:** FOUNDER-DECISION (plan §11.8). The clause question below is
**decided**; the category question is recorded with a recommendation.

---

## The question

GEO-173 requires a countersigned LOI from a data provider. F1.1 asks which
*category* of provider to pursue. The right category is the one whose absence
actually blocks a gate — not the one that is easiest to contact.

## Evidence: what is blocking today

### The `data_source_operational` gate

`docs/data-source-operational-gate.md` defines four controls, all of which must
hold: `delivery_mode == "live"`, a commercial-use **licence** on file, a
fingerprinted **live-runtime evidence** sample, and a declared **retention**
policy.

The four are independent. Closing the licence control alone does not make a
source operational — retention (control 4) and a live-runtime capture (control 3)
are separately absent today and are not addressed by any provider conversation.
A licence unblocks the control that no amount of internal work can close; the
other three remain ours to do.

`config/data_source_operational.json` on `main` currently reads:

```json
{ "licences": [], "retentions": [] }
```

Both record lists are empty. **Every source in the registry therefore fails the
gate on control 2, and separately on control 4, before credentials are even
considered.** This is by design and is the honest state — but it means the
binding constraint is a licence record, which is exactly what an LOI produces.

### Registry composition (`app/core/data_source_registry.py`)

| Tier | Sources | Provider plane | `loi_status` |
|---|---|---|---|
| production | `oras5_ocean` | Copernicus CDS / ECMWF | `intent` |
| production | `gee_viirs_ntl`, `gee_s5p_no2` | Google Earth Engine (NASA/NOAA, Copernicus/ESA) | `active` |
| audit | `audit_landsat_thermal`, `audit_s5p_no2`, `audit_s5p_co`, `audit_viirs_dnb` | Google Earth Engine (USGS, Copernicus, NOAA) | `active` |
| roadmap | `roadmap_ndvi`, `roadmap_soil_moisture` | GEE (planned) | `planned` |

Nine registry entries reduce to **two provider planes**: Copernicus/ECMWF (CDS)
and Google Earth Engine.

### What the NL CRE pilot actually consumes

The NL pilot does not draw on the registry above. Its dependencies, by reference
frequency in `app/nl_pilot/` and `docs/nl_pilot/`, are: **BAG** (137), **PDOK**
(21), **AHN** (9), **Kadaster** (8), **BRO** (4), **LIWO** (1) — Dutch
public-authority geodata, plus KOOP/SRU for permit publication. ADR-0007
additionally mandates **Klimaateffectatlas** indicators for NL assets, which are
not yet implemented on `main` (see the 2026-09-01 execution record, finding
B1-F2).

---

## The three candidate categories

### Category 1 — NL public-authority geodata (PDOK/Kadaster, AHN, Klimaateffectatlas/Deltares, KOOP)

- **Blocks:** the NL CRE pilot, which is the only near-term revenue path.
- **Licence posture:** open data, largely CC BY 4.0. Commercial use is generally
  permitted under published terms.
- **What an LOI would buy:** *not* the right to use the data — that already
  exists. It would buy an SLA, change notification, bulk/programmatic access
  quotas, and a named contact. Useful for pilot reliability, weak as a
  commercial signal.
- **Risk if skipped:** low legally, moderate operationally. The pilot can run
  under published open terms recorded as a self-attested licence review (B1.5,
  B2.3–B2.4 pattern).

### Category 2 — Copernicus / ECMWF (CDS, ORAS5) and Google Earth Engine

- **Blocks:** `data_source_operational` for all nine registry sources, and
  therefore any claim that a credentialed connector is operational.
- **Licence posture:** `UNRESOLVED` — and that is the point. The registry has no
  licence field; the only licence store on `main`
  (`config/data_source_operational.json`) is empty. Two questions are open and
  neither has an answer on file: (a) what the Google Earth Engine platform terms
  require for our non-research, customer-facing use, and (b) what the Copernicus
  and dataset-owner attribution/redistribution terms require when derived values
  reach a paying customer. The underlying collections (NASA VIIRS, USGS Landsat,
  Copernicus S5P, ECMWF ORAS5) are openly published; the unresolved part is the
  access platform and the redistribution of derived output. Resolve by reading
  the current terms and recording source URL, terms version and access date —
  do not assume either answer.
- **What an LOI would buy — and what it would not.** GEO-173's LOI is an
  evaluation/partnership intent. Control 2 of the gate needs something stricter:
  a `LicenceRecord` (`app/core/data_source_operational_gate.py`) with
  `commercial_use=true`, a `licensor`, a `valid_from` and a validity window in
  effect at evaluation time. **An LOI does not by itself create that record.**
  So the ask must carry an explicit commercial-use grant — a binding licence
  clause inside the LOI, or a separate licence instrument alongside it — or
  F1.7 can be completed without unblocking a single source.
- **Risk if skipped:** high. Without this, every registry source stays
  non-operational indefinitely, and any customer-facing use of the TR/global
  scoring path rests on an unresolved commercial-use question.

### Category 3 — Commercial CRE / property data vendors

- **Blocks:** nothing today. The pilot takes the asset list from the customer.
- **What an LOI would buy:** portfolio enrichment we have not yet been asked for.
- **Risk if skipped:** none in this horizon.

---

## Decision — the LOI carries a binding commercial-use clause

**Decided 2026-09-01.** The LOI is not to be sent as intent alone. It must carry
a binding commercial-use clause, so that a countersigned LOI *is* by itself the
licence record the gate wants, rather than a step toward one.

This closes the gap between GEO-173's acceptance (F1.7 — a countersigned LOI) and
control 2 of the `data_source_operational` gate (a `LicenceRecord` in effect).
Without the clause the two are different milestones and F1.7 could complete with
no source unblocked; with it, they are the same milestone.

### What the clause must establish

The clause is binding on its own terms — not "the parties intend to negotiate a
licence" — and must yield every field the gate reads
(`app/core/data_source_operational_gate.py`):

| `LicenceRecord` field | What the clause must state |
|---|---|
| `licensor` | The legal entity granting the right |
| `commercial_use` | An express grant to use the data in a **commercial, customer-facing** product. Not research-only, not evaluation-only |
| `valid_from` | The date the grant takes effect |
| `valid_until` | The end date, or express perpetuity |
| `document_ref` | A citable reference to the countersigned instrument |

Two further points the clause must cover, which the record does not model but the
product needs:

1. **Redistribution of derived values.** We deliver derived outputs to a paying
   customer. A grant to *use* the data internally does not by itself permit that.
2. **Survival.** The grant must survive the LOI's exploratory phase — an LOI that
   lapses if no commercial agreement follows takes the licence with it.

### Consequences for GEO-173

GEO-173's current Done criteria accept "at least **one** provider acknowledgement
or signed LOI committed to `docs/legal/`". Under this decision an
*acknowledgement* is no longer sufficient, and neither is the alternative branch
in its Priority 1 checklist ("submit LOI to Copernicus Commercial Services **or**
document open-access terms as licensing basis"). Documenting open-access terms is
a self-attested licence review — worth doing, but it is not a grant from a
licensor and does not produce a `LicenceRecord`. GEO-173's acceptance should be
tightened to match this decision before outreach begins.

## Recommendation on category (still open)

**Category 2 first, Category 1 in parallel as a lightweight track, Category 3 not
in this horizon.** This aligns with GEO-173's own Priority 1 (Copernicus / ESA).

Reasoning: Category 2 is the only category whose absence produces a *false* state
in the product — nine registry sources that cannot become operational and a
`production_eligible` gate that cannot move for a reason we have not yet tried to
fix. Category 1 is operationally useful but legally already resolved by published
open terms, so an LOI there would be an SLA conversation, not a licence
unblock. Category 3 addresses a need no customer has expressed.

Category 1 still needs a *record*, just not an LOI: a self-attested licence
review capturing source URL, terms version and access date, per the B1.5 / B2.3
pattern. That is task-level work and does not wait on this decision.

Retention (control 4) is unblocked by neither category. It is an internal policy
decision plus a storage identifier, and it overlaps the durable-retention work in
GEO-62 / C2.11–C2.12. Do not let a provider conversation stand in for it.

## What this document does not establish

No provider has been contacted. No conversation, response, draft or countersigned
LOI exists. No `LicenceRecord` and no `RetentionPolicy` has been created for any
source; `config/data_source_operational.json` remains empty. The clause decision
above governs how the LOI is drafted — it is not itself a licence, and it grants
nothing until a licensor countersigns. GEO-173 stays open until a countersigned LOI is on file (F1.7); under
plan §12 a draft LOI or verbal interest is not a Done condition. Nothing here
changes `data_source_operational` for any source, and no licence record has been
created.
