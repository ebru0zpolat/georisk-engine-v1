# NL CRE pilot — one-page overview

**Version:** v0.1 draft (E1.1)
**Date:** 2026-09-01
**Status:** internal draft. Not reviewed (E1.9 open), not used with any prospect (E1.10 open).
**Scope owner:** GEO-178

---

## What the pilot is

A fixed-scope, time-boxed evaluation of GeoRisk Engine over a Dutch commercial
real-estate portfolio. The customer supplies an asset list; we return a
per-asset physical-climate risk evidence pack and a resolution queue that names,
asset by asset, exactly which regulatory and hazard facts are established and
which are still unresolved.

The differentiator is not the score. It is that every number is reproducible from
a sealed snapshot and a recorded method version, and that anything we cannot
establish from an authoritative source stays visibly unresolved instead of being
filled with a plausible default.

## Who it is for

Dutch CRE owners, managers and lenders carrying 50–500 buildings who need
physical-climate evidence that survives review — by an auditor, a regulator, or
their own risk committee.

## Scope

| Dimension | Pilot scope |
|---|---|
| Portfolio size | 50–500 NL CRE assets (customer-provided CSV) |
| Geography | Netherlands (European NL only) for hazard and asset identity; see the regulatory-frame row for the narrower Article 4.113 scope |
| Asset identity | BAG / Kadaster resolution per asset |
| Hazards | Physical climate hazards material to NL buildings, per the NL pilot hazard set |
| Regulatory frame | Article 4.113 applicability evaluation — **Amsterdam only** (Amsterdam Omgevingsplan, CVDR696291/15). From 14 October 2026, Gemeenteblad 2026, 430670 supersedes `/15`, and a pack pinned to `/15` fails closed for current-law claims until the successor version is sealed ([source currency](../nl_pilot/amsterdam-omgevingsplan-source-currency.md)). Assets in other municipalities return `OUTSIDE_JURISDICTION` |
| Duration | Fixed window agreed at kickoff |
| Delivery | Evidence pack + resolution queue + walkthrough session |

## Deliverables — the closed list

1. **Per-asset evidence pack** — hazard values, source authority, snapshot id and
   method version for every value.
2. **Resolution queue (CSV)** — every unresolved fact with its `required_record`
   and `source_authority`, prioritised by trigger family. Article 4.113 rows are
   produced for Amsterdam assets; assets elsewhere are returned as
   `OUTSIDE_JURISDICTION`, not as unresolved.
3. **Portfolio summary** — coverage, resolution rate, unresolved-reason breakdown.
4. **Reproducibility record** — the exact commit SHA, snapshot hashes and method
   versions the delivery was produced from.
5. **One walkthrough session** with the risk owner.

Nothing outside this list is in the pilot.

## Success metrics

Agreed with the customer at kickoff and measured at close:

| Metric | Definition |
|---|---|
| Asset identity resolution rate | % of supplied assets resolved to a BAG identity |
| Trigger closure rate | % of Article 4.113 triggers moved out of `UNRESOLVED` from sealed data, over the Amsterdam subset of the portfolio |
| Reproducibility | Independent re-run at the recorded SHA is byte-identical |
| Evidence-gap actionability | Every unresolved item names a specific obtainable record and its authority |
| Reviewer verdict | The customer's own risk reviewer states whether the pack is usable as input |

Note: none of these is an accuracy claim about hazard values. They measure
coverage, closure and reproducibility.

## Exclusions

The pilot does **not** include:

- production deployment, an SLA, or an always-on service;
- integration into the customer's systems;
- valuation, loss, EAL, downtime or insurance-pricing output;
- legal or regulatory compliance determination;
- assurance over customer-supplied data;
- Article 4.113 evaluation outside Amsterdam — no other municipality's
  omgevingsplan is implemented, and none may be implied;
- any hazard or jurisdiction outside the agreed NL scope;
- data the customer is not licensed to give us, or that we are not licensed to use.

## Prohibited claims

Neither party may describe pilot output as any of the following, and our own
material must not either:

- "certified", "approved", "accredited", "EU approved", "AI Act certified",
  "sandbox accepted";
- regulatory compliance, or evidence of compliance;
- an audit, an assurance opinion, or independent scientific validation;
- production-grade or production-eligible output;
- a basis for investment, lending, underwriting or engineering decisions
  without the customer's own review.

Pilot output is decision-support input. `production_eligible=false` and
`controlled_pilot_eligible` is governed by the release manifest, not by this
document.

## What has to be true before this is sent to a customer

| Gate | Task | State |
|---|---|---|
| Demo deck | E1.6 | open |
| Reproducible demo runbook | E1.7 | open |
| Pilot FAQ | E1.8 | open |
| Internal self-attested review | E1.9 | open |
| Pricing agreed | E2 | open |
| Pilot agreement drafted | E3 | open |
| Controlled-pilot operations evidence | C2 | open |

Until C2 produces a real authenticated smoke and durable retention record, this
package describes a scope we intend to deliver, not one we have demonstrated
end-to-end for an external party.
