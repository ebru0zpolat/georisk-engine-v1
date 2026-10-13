# GeoRisk Engine

**Can this number be defended?**

GeoRisk Engine establishes whether a physical-risk figure can be defended — its own, or somebody else's. It is
not a hazard model, and it does not compete on hazard physics.

Binding product identity: [`docs/00-master/PRODUCT_CHARTER_V2.md`](docs/00-master/PRODUCT_CHARTER_V2.md).
Rules for contributors and coding agents: [`AGENTS.md`](AGENTS.md).

---

## What it does

Three questions, in increasing order of commercial value:

| | Question | Subject | Status |
|---|---|---|---|
| **Q1** | Can this number be **recomputed** from its own sealed inputs? | our own outputs | shipping |
| **Q2** | Where a number cannot be defended, **what evidence is missing** — per asset, machine-readably — and which single gap unlocks the most value? | our own portfolio | shipping |
| **Q3** | Given **somebody else's** physical-risk output, which of its claims are defensible on the evidence supplied, and what is missing for the rest? | a third-party report | in build |

Q3 is the product. Q1 and Q2 are the machinery it is built from.

## What makes it different

Most physical-risk systems return a number for every asset. This one returns a **refusal with a reason**
whenever the evidence does not support a number, and the refusals are the point:

- **Claims never promote.** A derived figure's claim state is the weakest of its dependencies. There is no
  override — `app/loss/claim_state.py`.
- **Ordered, unrepairable gates.** Applicability → source artefact → threshold source → data → comparison. A
  later input never repairs an earlier failure — `app/regulation/verify.py`.
- **Sealed provenance.** Source identity, version, SHA-256, method version and claim state travel with every
  persisted figure. The trail is append-only and hash-chained — `app/services/audit_trail.py`.
- **An independent verifier.** The recomputation check is a stdlib-only reimplementation written from the
  method note, forbidden from importing the pipeline it verifies — `tests/verification/independent_eal.py`.
- **Silent-error guards.** A NAP water level is never differenced against an EGM2008 elevation
  (`FLOOD_DATUM_MISMATCH`); an undocumented `-999.999` sentinel in a public flood raster is treated as invalid
  rather than as a depth (`app/loss/ldo_band_semantics.py`).
- **Every synthetic input is labelled and listed**, with a severity and a replacement plan — [`STUBS.md`](STUBS.md).

The flagship result so far is a refusal: for the Amsterdam pilot, the Dutch exceedance quantity resolves to
`SEMANTICALLY_AMBIGUOUS` — it cannot be read as an annual event probability without
`faalkans × P(scenario | breach)`. Competitors return a number here. This is the finding, not a defect.

## Honest status

- **Every readiness flag is false.** Nothing here is production-eligible, validated, calibrated or bank-grade.
- Every number on the `/v1/risk/score` path is synthetic ([`STUBS.md`](STUBS.md) #3). That path is retained for
  API compatibility and is **never shown to a regulated buyer**.
- No Turkish hazard, elevation or seismic value exists in this repository. Every Turkish output is
  `NOT_QUALIFIED`.
- The third-party verification path (Q3) is specified and not yet built. See
  [`docs/00-master/GAP_ANALYSIS_2026-09-19.md`](docs/00-master/GAP_ANALYSIS_2026-09-19.md).

Words like *verified*, *qualified* and *defensible* have exact machine meanings here:
[`docs/00-master/GLOSSARY.md`](docs/00-master/GLOSSARY.md).

## Documents that bind

| Document | Role |
|---|---|
| [`PRODUCT_CHARTER_V2.md`](docs/00-master/PRODUCT_CHARTER_V2.md) | Product identity. Highest authority |
| [`ENGINEERING_INVARIANTS.md`](docs/00-master/ENGINEERING_INVARIANTS.md) | INV-01…INV-12, enforced on every change |
| [`ROADMAP_VERIFIER_V2.md`](docs/00-master/ROADMAP_VERIFIER_V2.md) | Stages and gates. No dates, by design |
| [`WORK_ORDERS.md`](docs/00-master/WORK_ORDERS.md) | One work order, one pull request |
| [`GAP_ANALYSIS_2026-09-19.md`](docs/00-master/GAP_ANALYSIS_2026-09-19.md) | What exists, what does not, measured |
| [`PRUNE_LIST.md`](docs/00-master/PRUNE_LIST.md) | Keep / demote / cut |
| [`GLOSSARY.md`](docs/00-master/GLOSSARY.md) | Words with machine meanings |
| [`claim-state-grammar-v1.md`](docs/specs/claim-state-grammar-v1.md) | The one-way bridge between claim vocabularies |
| [`vendor-evidence-adapter-v1.md`](docs/specs/vendor-evidence-adapter-v1.md) | Third-party input contract and requirement catalogue |
| [`defensibility-gap-report-v1.md`](docs/specs/defensibility-gap-report-v1.md) | The artefact the product sells |
| [`STUBS.md`](STUBS.md) | Every synthetic input, with severity and replacement plan |

Earlier directives ([`GEORISK_ENGINE_REPOSITIONING.md`](GEORISK_ENGINE_REPOSITIONING.md),
[`GEORISK_PRODUCTION_ROADMAP_2026.md`](GEORISK_PRODUCTION_ROADMAP_2026.md),
[`docs/roadmap/georisk-resilience-analytics-v1.md`](docs/roadmap/georisk-resilience-analytics-v1.md)) remain
readable history; where they conflict with the charter, the charter wins.

## Running it

```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key
```

The deselected test opens a live connection to the Copernicus CDS and hangs on a network-restricted machine.

```bash
source .venv/bin/activate && uvicorn app.main:app --reload --port 8002   # API
cd frontend && npm install && npm run dev                                 # UI (not under active development)
```

Demonstrations worth running:

```bash
PYTHONPATH=. python scripts/run_resilience_triage_demo.py                 # portfolio readiness + ranked evidence gaps
PYTHONPATH=. python scripts/run_flood_source_qualification_demo.py        # fail-closed source qualification
PYTHONPATH=. python scripts/run_flood_reference_demo.py --mode qualified  # refuses without sealed real sources
```

The triage demo reports **zero decision-ready value** against the shipped synthetic verification portfolio.
That is the correct answer for a portfolio labelled `synthetic: true`, and it is a fair picture of where the
engine stands.

## Architecture

```text
Third-party output ─┐
                    ├─→ evidence adapter ─→ claim grammar ─→ defensibility gap report   (Track A, in build)
Own pipeline ───────┘                            ▲
                                                 │
   connectors → hazard → exposure → vulnerability → expected loss   (Track B, reference implementation)
                                                 │
                              sealed provenance · hash-chained trail · independent verifier
```

Country-specific data, damage curves, regulation mapping and templates live in versioned **Country Packs**,
never hard-coded into the core.

## Operational reference

Connector configuration (ORAS5 Zarr, Earth Engine), debug-route registration by `APP_ENV`, sector registry,
report and PDF paths, the industrial operational-audit scripts, and the optional DeerFlow / Headroom
integrations are documented in [`AGENTS.md`](AGENTS.md) §8 and under `docs/`. The industrial operational audit
(Landsat thermal, S5P NO₂) is a **separate small product** and is deliberately outside the physical-risk
narrative — see [`PRUNE_LIST.md`](docs/00-master/PRUNE_LIST.md) §2.
