# TR Sustainable Finance Evidence Pack

| Field | Value |
|---|---|
| Document ID | `tr-sustainable-finance-evidence-pack-v0.2` |
| Status | Regulatory analysis and product/evidence specification — not a compliance determination |
| Jurisdiction | Türkiye |
| Regulatory cut-off | 14 August 2026 |
| Applicable decision | `i-SPK.128.29` — 13 August 2026, decision no. `49/1500` |
| Product owner | GeoRisk Engine |
| Country-pack location | `pack-tr` regulation and report-template layer (implemented under `app/packs/tr/sustainable_finance/`) |
| Primary GeoRisk scope | Asset-level physical climate risk and adaptation evidence |

> This document is the human-readable specification for the `pack-tr` sustainable-finance
> evidence layer. The controlling machine-readable constants live in
> `app/packs/tr/sustainable_finance/regulatory_source.py`. Where the two disagree, the
> current official Turkish texts of the guidelines prevail over both.

---

## Part I — Regulation Explained

### A. Executive conclusion

The Capital Markets Board of Türkiye (CMB/SPK) adopted two separate guidelines through
Principle Decision `i-SPK.128.29`, dated 13 August 2026 and numbered `49/1500`:

1. the **Guideline on Green, Sustainable and Social Capital Market Instruments** (the
   Use-of-Proceeds Guideline); and
2. the **Guideline on Sustainability-Linked Capital Market Instruments** (the
   Sustainability-Linked Guideline).

The first guideline replaces the 2022 Guideline on Green and Sustainable Debt Instruments
and Lease Certificates for new applications. It expands the use-of-proceeds framework to
social instruments and a wider set of capital-market instruments. The second guideline
introduces a separate domestic framework for instruments whose financial or structural
characteristics change according to the issuer's performance against predefined key
performance indicators (KPIs) and sustainability performance targets (SPTs).

The regulatory opportunity for GeoRisk Engine is real but narrower than a general claim
that the guidelines require physical climate-risk data:

- physical-risk evidence is directly relevant to climate-adaptation, flood-reduction,
  resilient-building, water-management, climate-observation and early-warning projects
  under the Use-of-Proceeds Guideline;
- physical-risk analysis may inform a sustainability-linked KPI or SPT only where the
  resulting metric is material, substantially within issuer control, consistently
  measurable, comparable and externally verifiable; and
- a pure external hazard metric normally fails the issuer-control test and should not be
  used as an instrument trigger.

GeoRisk should therefore operate as a technical data, methodology and evidence-packaging
provider. It must not present itself as the issuer's legal decision-maker, framework
approver, second-party opinion provider, verifier, assurance provider or CMB-authorised
certifier under the current product and organisational model.

### B. Legal status, effective date, transition and fees

| Topic | Regulatory position | Evidence-pack consequence |
|---|---|---|
| Legal basis | Both guidelines rely on Articles 1 and 128/1(e) of Capital Markets Law No. 6362 and state that they have the force of a CMB decision | Record the decision identifier and applicable source version in every pack |
| Adoption | Principle Decision `i-SPK.128.29`, dated 13 August 2026, decision no. `49/1500` | Use 13 August 2026 as the decision date; verify the applicable publication/application date for each mandate |
| 2022 framework | The new Use-of-Proceeds Guideline was adopted to replace Principle Decision `i-SPK.128.18` and its 2022 guideline | Do not reuse a pre-2026 framework as if it automatically complies with the new guideline |
| New use-of-proceeds applications | The new Use-of-Proceeds Guideline applies to issuance applications made after its publication | Store the application date and legal cut-off |
| Existing sustainability-linked issuances | An issuance made under a CMB-approved ceiling before publication and declared sustainability-linked by the issuer is expressly outside the new Sustainability-Linked Guideline | Store the ceiling approval date and grandfathering determination made by legal advisers |
| Separate issuance ceiling | Each domestic and foreign issuance route under the guidelines requires a separate issuance ceiling under which only instruments of the relevant labelled type are issued | Include the ceiling reference and prevent mixing ordinary instruments into the labelled ceiling record |
| CMB fee | A 50% discount applies to CMB fees charged under the relevant capital-markets rules for instruments within the two guidelines | Treat as issuance metadata, not as a GeoRisk-calculated or guaranteed saving |
| Lease certificates | The 50% discount is additional to the discount granted by the CMB decision dated 24 June 2016 and numbered `20/710` | Do not calculate the final effective fee without the applicable CMB fee methodology and adviser confirmation |
| Signatory liability | Persons signing, or legal persons on whose behalf the documents are signed, are responsible under Article 32 of the Capital Markets Law | Preserve authorship, approval and responsibility records; do not obscure the source of issuer statements |

The 50% discount is not entirely new. The 2022 decision already provided a 50% CMB fee
discount for the then-covered green and sustainable instruments. The 2026 decision
continues and extends the incentive across the expanded instrument scope and the new
sustainability-linked route.

### C. The two regulatory models

| Feature | Use-of-proceeds model | Sustainability-linked model |
|---|---|---|
| Regulatory question | Where are proceeds used and what impact do the financed projects create? | Did the issuer achieve predefined sustainability performance and what happens to the instrument if it did or did not? |
| Label basis | Exclusive allocation to qualifying green and/or social projects | Issuer performance against predefined KPI(s) and SPT(s) |
| Main unit of analysis | Project, project portfolio and proceeds account | Issuer or defined issuer boundary and performance metric |
| Core components | Use of proceeds; project evaluation and selection; management of proceeds; reporting | KPI selection; SPT calibration; instrument characteristics; reporting; verification |
| Pre-issuance external work | Second-party opinion on the framework and guideline alignment | Second-party opinion on the framework, KPI relevance/reliability and SPT rationale/ambition |
| Post-issuance external work | Mandatory verification of the final allocation report and internal tracking method; impact-report review optional | Mandatory independent verification of performance against each KPI/SPT |
| Financial/structural consequence | Not a defining requirement | A defining feature of the instrument |

A sustainable use-of-proceeds instrument is not a generic ESG-labelled instrument. Under
the Use-of-Proceeds Guideline, it funds projects that combine environmental and social
positive effects. A sustainability-linked instrument is governed by a separate
issuer-performance model and does not derive its status merely from allocating proceeds to
a project.

#### C.1 Defined-term glossary

| Term | Meaning in the guidelines |
|---|---|
| Framework document | Board-adopted issuer document stating that the relevant instrument complies with the applicable guideline and describing the required issuance architecture |
| Second-party opinion | Independent pre-issuance external review assessing whether the issuance and framework align with the applicable guideline; under the sustainability-linked route it also examines KPI/SPT design |
| Verification | Post-issuance external review providing assurance or attestation over proceeds tracking/allocation or KPI performance against SPTs, depending on the route |
| Green instrument | Instrument whose proceeds are used exclusively for qualifying projects with positive environmental effects |
| Social instrument | Instrument whose proceeds are used exclusively for qualifying projects addressing a social problem and/or producing positive outcomes for an identified target population |
| Sustainable instrument | Use-of-proceeds instrument financing projects that combine positive environmental and social effects |
| Sustainability-linked instrument | Instrument whose financial and/or structural characteristics change according to performance against predefined environmental, social and/or governance objectives |
| KPI | Metric used to measure performance of the selected indicator |
| SPT | Measurable improvement the issuer commits to achieve in the KPI within a predefined timeline |
| Target measurement date | Date on which KPI performance is evaluated against the SPT |
| Benchmark | Basis used to measure or compare performance |
| Reference value | Fixed starting point used to measure SPT performance |
| Triggering event | Result of the KPI/SPT assessment that can cause a change in the instrument's financial and/or structural characteristics |

### D. Guideline on Green, Sustainable and Social Capital Market Instruments

The guideline seeks to increase transparency, integrity, consistency and comparability in
the financing of projects that contribute to environmental and/or social objectives in
line with Türkiye's net-zero objective and Long-Term Climate Strategy. It was prepared with
reference to the ICMA Green Bond Principles, Sustainability Bond Guidelines, Social Bond
Principles, ICMA guidance for green/social/sustainability sukuk and Regulation (EU)
2023/2631 on European Green Bonds.

Its express scope includes green, sustainable and social forms of debt instruments; lease
certificates; covered bonds and mortgage-covered securities; asset-backed and
mortgage-backed securities; project-backed securities; real-estate certificates; and other
capital-market instruments that meet the guideline conditions. Blue capital-market
instruments are treated as green capital-market instruments.

The four mandatory components are **use of proceeds**, **project evaluation and
selection**, **management of proceeds** and **reporting**. The twelve non-exhaustive green
project categories and seven social project categories (with target-population examples)
are encoded in `regulatory_source.py`. Categories 8 (sustainable water and wastewater
management, incl. flood-reduction infrastructure) and 9 (climate-change adaptation, incl.
climate observation and early-warning) are the primary GeoRisk-relevant categories.

Until a Türkiye Green Taxonomy is established, issuers may use other internationally
accepted taxonomies, including the EU Taxonomy, to determine project eligibility. The
guideline permits this use; it does not automatically import all EU Taxonomy technical
screening criteria, do-no-significant-harm tests or minimum safeguards into every issuance.

Reporting calendar (use-of-proceeds route): allocation reporting starts on the first
tranche issuance date, updates at least annually until full allocation, requires a revised
report within a maximum of six weeks after a material development, and requires a final
allocation report plus mandatory independent verification of the final allocation report
and internal tracking method within three months after full allocation. The impact report
is due within three months after full allocation; external review of the impact report is
optional. Verification of the final allocation report is mandatory — the pack must never
merge these two conclusions.

### E. Guideline on Sustainability-Linked Capital Market Instruments

The five mandatory components are **KPI selection**, **SPT calibration**, **financial
and/or structural characteristics of the instrument**, **reporting** and **verification**.

A KPI must relate to a material issue for the issuer's core sustainability and business
strategy, be under issuer management and control, be measurable on a consistent
methodological basis, be externally verifiable, and be comparable. Where a KPI has not
previously been disclosed, the issuer should provide, to the extent possible, at least
three years of externally verified historical values.

An SPT must represent material progress in the linked KPI, go beyond business as usual, be
compared with a benchmark or external reference where possible, be consistent with the
issuer's strategy, and be established before or at issuance. Verification is mandatory and
must provide limited or reasonable assurance.

### F. Changes from the 2022 guideline

| Area | 2022 position | 2026 position |
|---|---|---|
| Product scope | Primarily green/sustainable debt instruments and lease certificates | Broader set of green, sustainable and social capital-market instruments plus a separate sustainability-linked guideline |
| Social instruments | No full standalone social-instrument architecture | Social instruments, social-project categories and target populations expressly regulated |
| Sustainability-linked instruments | Expressly outside the 2022 guideline | Separate five-component guideline introduced |
| External review types | Second-party opinion, verification, certification and green rating/scoring | Only second-party opinion and verification remain |
| Allocation reporting | Annual from issuance; material developments without a fixed deadline | Starts with first tranche; material update within a maximum of six weeks; final reporting and verification within three months after full allocation |
| Fee discount | 50% for then-covered instruments | 50% continued and extended; lease-certificate treatment remains additional to the 2016 discount |

### G. Interpretation points requiring legal confirmation

The following are recorded as `INTERPRETATION_FLAGS` in `regulatory_source.py` and must be
surfaced to capital-markets counsel before an external pack is released: replacement versus
repeal of the 2022 framework; domestic KAP wording; use-of-proceeds verifier eligibility
(authorised independent audit firm); sustainability-linked second-party expertise for
social/governance-only structures; the financial-consequence requirement; impact-report
recurrence; hybrid instruments; cumulative fee effect; and the fact that the
Sustainability-Linked Guideline does not require a physical-risk KPI by name.

### H. GeoRisk Engine regulatory relevance

GeoRisk can support the evidence base for climate-adaptation, flood-reduction, resilient
buildings, water management, and climate-observation / early-warning projects under the
Use-of-Proceeds Guideline. `project_eligible` must never be set to `true` by GeoRisk;
eligibility depends on issuer governance, the chosen taxonomy/standard, project facts,
legal analysis and the independent second-party opinion.

For the sustainability-linked route, physical hazard is generally external to issuer
control. A KPI such as "reduce flood hazard by 20%" is normally unsuitable. Defensible
candidates instead measure issuer-controlled resilience (see the physical-risk KPI policy
in Section 8). Modelled EAL, downtime or monetary loss must not be used as a coupon or
structural trigger while the loss pathway remains synthetic or lacks empirical backtesting
and independent scientific challenge.

---

## Part II — GeoRisk Evidence Pack Product Specification

### 1. Purpose

This document defines the evidence contract for a GeoRisk Engine output package intended to
support selected technical evidence needs arising under the two CMB/SPK guidelines. The
pack converts a controlled GeoRisk computation record into a reviewer-oriented bundle
covering physical climate-risk baselines, project-selection evidence, impact metrics,
KPI/SPT design inputs, methodology, data lineage, uncertainty, limitations and change
history.

It is a **support product**. It does not determine legal eligibility, approve an issuance,
provide a second-party opinion, perform assurance or verification, certify compliance,
replace the issuer's governance, or replace advice from capital-markets counsel, an
authorised investment firm, an independent auditor or another external-review provider
accepted by the CMB.

### 2. Regulatory sources and reading rule

- The current official Turkish texts prevail over this specification.
- A mandatory statement in a guideline must not be downgraded to an optional field.
- A recommendation in a guideline must not be represented as a statutory obligation.
- The guideline effective on the issuance-application date must be recorded in the pack manifest.
- Later CMB decisions, communiques, disclosure rules or guidance must be checked before an external pack is released.
- The 50% CMB fee discount is an issuance-process fact, not a GeoRisk calculation.

### 3. Product boundary and role separation

`app/packs/tr/sustainable_finance/routes.py` and `schemas.py` encode what GeoRisk may and
must not provide, and the engagement roles (issuer, capital-markets/legal advisers,
framework adviser, GeoRisk Engine, second-party opinion provider, verifier). For the same
framework, an external-review provider may provide only one external-review service type,
and the framework-preparation adviser may not provide external review for that framework.
The pack keeps issuer-side technical work, second-party opinion work and verification
evidence logically separable.

### 4. Route selection

Every engagement must select exactly one primary regulatory route (`use_of_proceeds` or
`sustainability_linked`) before calculations are packaged. A use-of-proceeds impact metric
is not automatically an eligible sustainability-linked KPI, and a sustainability-linked KPI
does not establish project eligibility.

### 5. Common pack manifest

See `PackManifest` in `schemas.py`. Missing mandatory provenance, methodology, licence or
responsibility fields must cause generation to fail closed.

### 6–8. Route evidence contracts and physical-risk KPI policy

- **Use-of-proceeds** (`ProjectEligibilityRecord`, `PhysicalAdaptationEvidence`):
  `project_eligible` is never set by GeoRisk; permitted values are
  `technical_evidence_complete`, `technical_evidence_incomplete`, `outside_georisk_scope`,
  `requires_issuer_determination`, `requires_external_review`.
- **Sustainability-linked** (`KPIRecord`, `SPTRecord`): a candidate KPI reaches
  `reviewer_ready` only if all admission gates in Section 7.2 pass.
- **Physical-risk KPI policy** (`physical_risk.py`): the suitability matrix defaults a pure
  external-hazard metric to `reject` and a modelled EAL/downtime/monetary-loss trigger to
  `not_available_for_trigger_use`. The constant-hazard rule locks the hazard reference for
  before/after resilience comparisons; scientific updates are shown through a controlled
  bridge calculation, never a silent overwrite.

### 9. Technical evidence and provenance

Every calculation is traceable to its `analysis_run_id`, data source, licence, retrieval
date, model/scenario/horizon, methodology versions and input/output hashes. Connector
fallback values, synthetic portfolio values and synthetic damage curves must be explicitly
identified and must not be included in an external KPI baseline, SPT calculation, impact
conclusion or coupon-trigger computation.

### 10. Evidence bundle structure

The deterministic builder (`builder.py`) emits the following, omitting files that do not
apply to the selected route:

```text
tr-sustainable-finance-evidence-pack/
  manifest.json
  executive-summary.md
  regulatory-route.md
  responsibility-matrix.json
  framework-crosswalk.md
  project-register.json                 # use-of-proceeds route
  proceeds-data-interface.json          # issuer-supplied; no GeoRisk assurance
  impact-metrics.json                   # use-of-proceeds route
  kpi-register.json                     # sustainability-linked route
  spt-register.json                     # sustainability-linked route
  instrument-effects.json               # issuer/adviser supplied
  performance-report-crosswalk.md
  data-lineage.json
  methodology-and-assumptions.md
  uncertainty-and-limitations.md
  recalculation-policy.md
  external-review-index.md
  claims-register.json
  audit/
    run-index.json
    hashes.sha256
    change-log.json
```

### 11. Claims control

`claims.py` scans generated text for prohibited terms (e.g. "CMB compliant", "second-party
opinion", "guaranteed"), permitting them only inside quotations or control tables.
Automated claim scanning fails the build when prohibited terms appear outside a quotation
or control table.

### 12. Lifecycle states and sign-offs

`draft` → `technical_evidence_complete` → `reviewer_ready` → `issuer_approved` →
`second_party_opinion_received` → `verification_received` → `superseded`. GeoRisk may assign
only the first three states; later states require documentary evidence supplied by the
responsible issuer or external-review provider.

### 13. Fail-closed release gates

`gates.py` blocks `reviewer_ready` when any release-gate condition in Section 13 of the
source specification holds (missing guideline version/cut-off, unresolved route, missing
issuer field, unlabelled fallback/synthetic/unlicensed input, forward-looking result
without a real scenario source, missing hashes, failing KPI/SPT gates, missing
recalculation policy, EAL/downtime/loss proposed as a trigger, suppressed uncertainty,
prohibited claims, unseparated review roles, or non-reproducible evidence).

### 14. Current GeoRisk maturity constraint

This specification does not upgrade the scientific maturity of the underlying model. The
pack inherits the status of every source calculation. Monetary EAL, downtime and
avoided-loss outputs must not be used as verified performance facts or instrument triggers
until the relevant real-event backtest, observed-loss comparison, uncertainty analysis and
independent challenge are completed. The claim boundary in
`docs/methodology/GEORISK_ENGINE_METHODOLOGY.md`, `STUBS.md` and
`GEORISK_ENGINE_REPOSITIONING.md` remains controlling.

### 15. Implementation backlog

**P0 — specification and control contract**

- [x] Define the two regulatory routes and their evidence boundaries.
- [x] Define KPI/SPT admission gates and physical-risk KPI policy.
- [x] Define claim, provenance, lifecycle and fail-closed controls.
- [ ] Obtain Turkish capital-markets legal review of the crosswalk.
- [ ] Obtain external-review-provider feedback on evidence usability.

**P1 — schemas and deterministic builder**

- [x] Add pack-tr regulatory source manifest for `i-SPK.128.29`.
- [x] Implement project, KPI, SPT, responsibility and external-review schemas.
- [x] Implement deterministic evidence-bundle generation from immutable run records.
- [x] Add checksum sealing and pack-diff output.
- [x] Add prohibited-claim scanning.
- [x] Add fail-closed tests for fallback, synthetic, missing-licence and missing-provenance inputs.
- [x] Add constant-hazard comparison and recalculation bridge tests.

**P2 — issuer and reviewer workflow**

- [ ] Add issuer-supplied proceeds and instrument-effects interfaces.
- [ ] Add CMB framework-document crosswalk exports.
- [ ] Add performance and impact report crosswalk exports.
- [ ] Add reviewer comment and evidence-response workflow.
- [ ] Pilot the pack with a Turkish issuer and an eligible independent external-review provider.

### 16. Definition of done

The TR Sustainable Finance Evidence Pack is implementation-ready when: the same sealed
inputs reproduce the same pack and hashes; no country-specific regulatory rule is
hard-coded into georisk-core; the selected route exposes every mandatory evidence field
without implying legal sufficiency; synthetic, fallback, missing-licence and unsupported
scenario inputs fail closed; the pack separates issuer statements, GeoRisk calculations and
external-review conclusions; KPI/SPT calculations preserve history and show controlled
recalculations; every external number links to its methodology, data source, licence,
version and uncertainty; and a second-party opinion provider or verifier can inspect the
evidence without treating GeoRisk as the assurance provider.
