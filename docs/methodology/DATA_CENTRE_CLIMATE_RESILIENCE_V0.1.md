# Data Centre Physical-Climate Resilience Methodology v0.1

**Status:** controlled decision-support contract; not empirically validated for
monetary loss estimation.

## 1. Product boundary

This module is an adjacent use case under the active commercial real-estate,
mortgage and collateral P0 vertical. It does not reposition GeoRisk Engine as a
sovereign-AI, data-centre engineering or regulatory-reporting product.

The module helps lenders, insurers, infrastructure investors and technical due-
diligence teams identify traceable physical-climate pathways at data-centre
assets. It is not an availability guarantee, engineering certification or
substitute for a site engineer.

## 2. Required evidence

An assessment requires one scenario horizon shared by:

1. heat evidence: dry-bulb, wet-bulb and/or WSDI evidence;
2. flood evidence: maximum site water depth, flood type and return period where
   available;
3. water-stress/drought evidence: provider classification, metric and versioned
   threshold reference;
4. optional power-continuity evidence: maximum climate-related outage duration.

Every evidence object carries a source, dataset id, version, licence,
commercial-use decision, retrieval date and SHA-256 digest. Synthetic or
unlicensed evidence is accepted only to expose a blocked result; it cannot open
a production-readiness gate.

Each request declares a versioned `country_pack_id` and `valuation_date`.
Hazard manifests, observed-loss manifests, backtest `information_cutoff` and
external-review `signed_on` dates after the valuation cutoff are rejected.
External-review `valid_until` is assessed against both `valuation_date` and the
assessment `as_of` date: a review that expired before the information cutoff, or
before the assessment is run, cannot open the monetary gate. A review signed
after `as_of` is also rejected at the monetary gate. The response contains
a deterministic SHA-256 assessment identifier and the evidence manifest hashes
needed to reconstruct the request context; persistence remains the responsibility
of the shared append-only audit service when this vertical is promoted beyond the
controlled API contract.

There is no global built-in water-stress score. `pack-<iso2>` or an approved
due-diligence provider must implement the water-stress provider seam. The
unconfigured provider raises an explicit error instead of returning a fallback.
`not_classified` water-stress evidence blocks readiness. `POST /v1/risk/data-centre/assess`
is behind `DATA_CENTRE_ASSESS_ENABLED` (default off). Enabling the flag never
releases downtime hours or monetary/EAL outputs.

## 3. Vulnerability contract

The canonical engineering contract is `DataCentreVulnerabilityProfile`
(`app/schemas/dc_vulnerability.py`) evaluated by
`evaluate_dc_vulnerability_readiness`. The assessment completeness gate
consumes that result. It does not maintain a second, independent field
checklist.

When `vulnerability_profile` is present it is the sole completeness and
pathway authority. Overlapping flat fields must match the profile or the
request is rejected; they are never silently ignored. A single resolver
(`resolved_vulnerability_inputs`) feeds `_cooling_trigger`, `_flood_trigger`
and `_power_trigger`. The flat object is the pathway input only when no
profile is supplied (lossy-bridge completeness path). Unmapped facts stay
unknown; they are never defaulted. A 15-field screening payload is therefore
incomplete against DC-001..DC-052 and cannot open decision-support readiness.

`DataCentreAssessmentRequest.no_lookahead_evidence()` requires
`vulnerability_profile.valuation_cutoff` ≤ `valuation_date`. Every dated
profile component, including `engineering_review.review_date`, must also be
≤ `valuation_date`. The profile schema separately requires
`engineering_review.review_date` ≤ the profile’s own cutoff. Older profiles
may still open decision-support readiness; the response then exposes
`vulnerability_profile_cutoff` and `vulnerability_evidence_stale=true`.
Production eligibility requires the profile cutoff to equal
`valuation_date`. No processing date substitutes for the request cutoff.

The lossy bridge copies declared same-system facts only. `power_redundancy`
maps to `electrical.electrical_redundancy_config` as declared legacy
evidence, never to `cooling.cooling_redundancy`.

WUE, design PUE and rack density stay on the screening object as optional
context. They are EU 2024/1364 operational KPIs / extras, not DC-xxx
completeness fields.

DC-053 (approved signed engineering review) is production eligibility, not
decision-support completeness. `decision_support_only` can open without a
signed review; `production_release` remains `none` until a separately
versioned monetary calculator exists.

Liquid and immersion cooling still reject heat to ambient, but this contract
has no field for whether that loop is dry or adiabatic. Any declared dry- or
wet-bulb design limit is therefore compared as a **provisional proxy**. At
least one of the two limits is required for completeness. This proxy makes
the cooling pathway decidable; it is not engineering validation, does not
release monetary outputs, and does not change `production_release=none`.
The follow-up reconciliation must add an explicit heat-rejection-loop field
to `DataCentreVulnerabilityProfile` so this proxy can be retired.

## 4. Non-monetary loss pathways

The v0.1 pathway graph evaluates:

`heat / water stress -> cooling derating -> downtime -> business interruption`

`flood depth / floor elevation -> downtime -> business interruption`

`climate-related outage / backup duration -> power curtailment -> downtime`

`triggered pathway -> adaptation investigation`

Results are limited to `triggered`, `not_triggered` or `indeterminate` with
reasons. A cooling-type-required comparison that cannot run (missing dry-bulb,
wet-bulb or classified water-stress) is `indeterminate` unless another completed
comparison already triggers. Liquid and immersion sites compare every declared
design limit via that provisional proxy. Unknown water dependency is treated
as potentially water-dependent: it requires usable water-stress evidence and
cannot clear the cooling pathway when that evidence is synthetic, unlicensed,
or unclassified. Synthetic or unlicensed evidence short-circuits each affected
pathway to `indeterminate`; downtime and business interruption cannot become
concrete from blocked inputs alone. The graph does not produce outage hours,
EAL, business-interruption loss or adaptation cost.

## 5. Monetary-output gate

The following are all required before a separately versioned monetary calculator
may be introduced:

- a frozen pre-registration commit executed by `app.validation.gate1.run_comparison`;
- commercially licensed observed-loss/outage evidence;
- model and named baseline evaluated on the same sample and cutoff;
- a passed pre-registered comparison rule;
- representativeness and uncertainty analysis;
- an independent engineering review tied to the exact methodology version;
- a versioned calculator with replay and audit tests.

Even when documentary evidence is supplied to v0.1, monetary fields remain null
because no validated data-centre monetary calculator is configured.

## 6. Regulation (EU) 2024/1364 boundary

Commission Delegated Regulation (EU) 2024/1364 defines a data-centre
sustainability reporting scheme and operational KPIs, including energy
consumption, power utilisation, temperature set points, waste-heat utilisation
and water indicators.

GeoRisk's v0.1 assessment can support physical-climate site screening and
vulnerability evidence. It does not measure the Regulation's operational KPIs
and must not be described as establishing compliance with the Regulation.

## 7. Permitted and prohibited wording

Permitted:

> Traceable decision-support evidence for heat, flood, water-stress and related
> data-centre vulnerability pathways.

Prohibited:

- “EU 2024/1364 compliant”;
- “engineering-certified uptime”;
- “validated data-centre EAL”;
- “validated downtime or business-interruption loss”;
- “sovereign-AI compliance”.

## 8. Follow-on work (out of this contract)

This v0.1 slice hardens the decision-support contract only. It does not
implement, and must not be described as implementing:

1. a licensed water-stress provider and `pack-nl` Country Pack wiring;
2. independent engineering vulnerability validation;
3. a preregistered real-event Gate-1 backtest (licensed observed-loss provider
   calling `app.validation.gate1.run_comparison`);
4. a downtime-hours model;
5. a monetary loss / EAL model.

Each item is a separate, later PR. Enabling `DATA_CENTRE_ASSESS_ENABLED` does
not advance any of those items.
