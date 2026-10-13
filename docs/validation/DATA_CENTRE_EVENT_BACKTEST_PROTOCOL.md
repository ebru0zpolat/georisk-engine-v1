# Data Centre Real-Event Backtest Protocol

**Status:** protocol only; no event, observed-loss dataset or result is claimed.

This protocol specialises the repository's general Gate-1 comparison harness for
the data-centre use case. It must not be executed until the study is frozen and a
licensed observed-loss/outage provider is configured.

**Shared harness (mandatory):** `app.validation.gate1.run_comparison`, invoked
only through `app.data_centres.gate1.run_data_centre_backtest`. Do not add a
second comparison engine, metric registry, or baseline selector. The default
provider is `UnlicensedObservedLossProvider` (fail-closed).

## Pre-registration fields

Freeze the following in a signed Git commit before examining results:

- named heat, flood or compound event and event dates;
- geographic sampling frame and facility inclusion criteria;
- exclusions, including facilities lacking minimum vulnerability fields;
- information cutoff and evidence retrieval rules (`information_cutoff` and
  observed-loss `retrieved_on` must be on or before the assessment
  `valuation_date`);
- primary target: observed outage hours, cooling derating or physical damage;
- named naive/incumbent baseline;
- primary metric and numerical success rule;
- uncertainty method and representativeness analysis;
- treatment of censored, confidential and zero-loss observations;
- reviewer discipline and independence criteria.

## Minimum observed evidence

Accepted records must be legally usable and traceable to facility/event level.
Possible record classes include operator incident reports, insurer claims,
engineering loss surveys and regulator/utility outage records. Public reporting
of an event does not by itself establish a licence to train or validate a model.

Each dataset must have a manifest containing source, version, commercial-use
licence decision, retrieval date and SHA-256 digest. Synthetic incidents and
unlicensed scraped incident lists are prohibited.

## Comparison rules

1. Use the same frozen sample and information cutoff for GeoRisk and the named
   baseline.
2. Prevent post-event or claim-settlement data from entering predictors.
3. Publish exclusions and reasons; do not silently drop facilities.
4. Report the primary metric regardless of pass/fail.
5. Report facility-type, cooling-type and geography representation.
6. Preserve the complete configuration and result hashes in the audit trail.

## Release gate

A passed numerical comparison is necessary but insufficient. Monetary outputs
remain blocked until an independent engineering reviewer approves the exact
methodology and a replayable, versioned monetary calculator is implemented.

## Current blockers

- Real event: not selected.
- Sampling/exclusion rules: not frozen.
- Licensed observed-loss/outage data: not obtained.
- External reviewer: unassigned.
- Data-centre monetary calculator: not implemented.
