# Synthetic Reference Portfolio ("Golden Portfolio" fixture)

## What this is

A **deterministic, schema-conformant synthetic reference portfolio** for testing
and demonstration: a Python generator plus a committed 120-asset sample dataset of
fictional Dutch commercial properties.

> **This is not a "gold-standard" dataset.** Despite the informal "Golden
> Portfolio" name, it contains no scientific gold-standard, ground-truth, or
> survey data. It exists solely to exercise schemas, dry-runs, demos and CI.

## Claim boundary

This change provides a deterministic, schema-conformant synthetic reference
portfolio for testing and demonstration. It does not contain real customer
assets, authoritative valuations, surveyed coordinates, ground-truth hazard
outcomes, or evidence authorizing controlled-pilot, decision, or production use.

## Components

| Path | Purpose |
|------|---------|
| `scripts/generate_synthetic_reference_portfolio.py` | Deterministic CLI generator (fail-closed) |
| `data/portfolios/synthetic/synthetic_reference_portfolio_v1.json` | Generated 120-asset sample |
| `tests/portfolios/test_synthetic_reference_portfolio.py` | Focused behavioural tests |

## Regenerating the sample

```bash
PYTHONPATH=. python scripts/generate_synthetic_reference_portfolio.py \
    --output data/portfolios/synthetic/synthetic_reference_portfolio_v1.json
```

CLI parameters: `--output PATH`, `--count N` (50–500 enforced; default **120**),
`--seed S` (default **20260825**, documented fixed seed).

Identical inputs produce byte-for-byte identical output. The committed fixture
must always equal a fresh regeneration at the default parameters — this equality
is asserted in tests.

## Schema binding

There is no separate JSON Schema file. The canonical portfolio contract is the
Pydantic model pair `PortfolioUploadRequest` / `UniversalAsset` in
`app/schemas/portfolio.py`. The generator validates every record against these
models before writing, and records a SHA-256 of the module source inside the
fixture metadata (`schema_binding.source_sha256`) so silent schema drift is
detected as a checksum change rather than silently accepted.

## Checksum semantics

```
content_checksum = sha256( UTF-8( json.dumps(document["dataset"],
                     sort_keys=True, separators=(",", ":"), ensure_ascii=False) ) )
```

- Covers the portfolio payload, supplements and metadata.
- Excludes the `integrity` block itself.
- Contains **no timestamps**: deterministic content identity has no run-envelope
  component. If a generation-run envelope is ever needed, it must be stored
  outside the checksummed content and documented separately.

## Dataset shape

- Exactly 120 assets by default: Amsterdam 25, Rotterdam 31, The Hague 22,
  Utrecht 14, Eindhoven 28.
- CRS split exactly 60/60 using exact identifiers: EPSG:28992 and EPSG:4326.
- The canonical ingest payload is WGS84-only, using the canonical named fields
  `latitude`/`longitude` (axis order fixed by field names, never positional).
  EPSG:28992 coordinates live in `supplements.rd_coordinates`, clearly marked as
  non-canonical synthetic geometry, validated against documented NL RD domain
  bounds x∈[10 000, 278 000], y∈[300 000, 625 000].
- Valuations are uniform random draws in EUR 1 500 000 – 45 000 000, labelled
  `synthetic_unverified`. No target total portfolio value is forced.
- Addresses use real city names with explicitly synthetic parcels
  ("Synthetisch perceel …") and format-valid Dutch postcodes. **Postcode-format
  validity does not imply any address corresponds to a real property.**

## Coordinate plausibility vs positional accuracy

Generated coordinates are plausible points near real city centroids, produced by
a published polynomial approximation for RD conversion. They carry **no survey
accuracy**, no millimetric or even cadastral claim, and must not be interpreted
as measured building locations. `survey_accuracy_verified=false`,
`coordinate_source=synthetically_generated`.

## Permitted use

- Canonical-schema conformance testing
- Deterministic dry-runs and pipeline plumbing checks
- Demos and UI development
- CI regression fixtures

## Prohibited use

- Customer decisions or client reporting
- Valuation, pricing, or underwriting judgements
- Scientific validation or empirical calibration claims
- Flood-loss, damage, or EAL claims presented as observed outcomes
- Readiness, controlled-pilot, or production evidence of any kind

## Relationship to connectors and pilots

Using this fixture together with PDOK or other data connectors inside a pilot
flow requires separately approved orchestration and integration work (see PR
#141 pilot protocol and follow-on orchestration/integration PRs). This fixture
changes no readiness state: `decision_use_approved`,
`controlled_pilot_eligible`, `customer_pilot_verified`,
`runtime_live_verified`, and `production_eligible` are all `false` and remain
governed exclusively by the release manifest, not by this dataset's metadata.
