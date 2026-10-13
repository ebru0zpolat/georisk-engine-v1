# Harvey Gate-1 data contract (FEMA NFIP Claims v3)

**Status:** draft; `demo_only`. Do not inspect Harvey outcomes or set a validation
flag until the pre-registration, baseline value, source hash, licence record and
USGS coverage qualification have been frozen.

**Canonical contract:** this dictionary documents fields only. The single
canonical protocol (study ID, event window 2017-08-25…2017-09-01, Harris County
evaluation frame, seeded bootstrap 10,000 / 20170825, dedupe and
no-imputation/no-winsorisation rules, and clause provenance across PRs #116/#187/
#191) is
[`HARVEY_CANONICAL_PROTOCOL.md`](./HARVEY_CANONICAL_PROTOCOL.md).

## Pinned sources and scope

- Claims endpoint: OpenFEMA `NfipClaims` **v3**. The retired
  `FimaNfipClaims` v2 endpoint is prohibited for this study.
- Event: Hurricane Harvey, with Harris County eligibility rules to be finalized
  before outcome access.
- Hazard observations: USGS Harvey flood-inundation/depth package. Qualification
  is outcome-blind and requires coverage of at least 95% of candidate locations.
- Target: event-conditional paid building loss, not annual expected loss (EAL).

## Canonical field mapping

| Canonical field | OpenFEMA v3 source | Use |
|---|---|---|
| `claim_id` | provider claim identifier | deterministic deduplication only |
| `date_of_loss` | loss date | event eligibility |
| `county_code` | county/FIPS field | Harris County eligibility |
| `latitude`, `longitude` | privacy-treated coordinates | USGS coverage and cluster assignment |
| `buildingClaimPaymentAmount` | `amountPaidOnBuildingClaim` through the explicit schema adapter | **withheld outcome** |
| `total_building_insurance_coverage` | `totalBuildingInsuranceCoverage` | frozen baseline input |

The acquisition manifest must retain the exact API query, retrieval timestamp,
record count, raw SHA-256, normalized SHA-256, field mapping version, OpenFEMA
terms/licence snapshot and USGS CC0 record. Schema drift or an undocumented
field substitution stops the experiment.

`netBuildingPaymentAmount` and `buildingDamageAmount` are different concepts and
must never be used as fallbacks. Both baseline calibration and the later Harvey
evaluation must consume the canonical `buildingClaimPaymentAmount` produced by
the same adapter.

## Estimand boundary

The registered estimand is `nfip_claim_conditional_building_payment_v1`: the
event-conditional building payment for an observed NFIP claim record that passes
the eligibility rules. Claims data do not represent the policy universe. This
study therefore cannot validate event frequency, claim-filing probability,
portfolio loss ratios, uninsured loss, annual EAL, or Dutch CRE loss.

## Frozen decision rule

`Skill = 1 - MAE(model) / MAE(baseline)`. Passing requires all of: at least 200
eligible claims; at least 30 independent location clusters; skill at least 0.10;
the lower bound of a 10,000-repeat location-cluster bootstrap 95% confidence
interval above zero; normalized absolute mean bias no greater than 0.05; written
data-use authorization; independent reviewer approval; and no material protocol
deviation. `zero_loss` is secondary diagnostic output only.

Harvey evidence may support only `harvey_event_loss_method_validated` and
`us_harvey_flood_hazard_verified`. It cannot set Dutch hazard, Dutch CRE
transferability, or `model_validated_for_nl_cre_use_case` status.
