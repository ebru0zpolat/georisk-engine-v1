# GEO RISK ENGINE B.V. — RVO CURRENT-STATE ASSESSMENT AND REVISED BUSINESS PLAN

**Assessment date:** 6 August 2026  
**Repository assessed:** `ebru0zpolat/georisk-engine`  
**Main reference:** commit `95560fc4c63418b221946e22d7093462d3b97f32`  
**Applicant:** [Full legal name]  
**Nationality:** Turkish  
**Proposed company:** Geo Risk Engine B.V.  
**Proposed location:** Netherlands — Amsterdam/Rotterdam region  
**Sector:** Climate Risk Analytics / FinTech / RegTech / Climate Adaptation Technology

---

## Assessment notes (repo fact-check, 6 August 2026)

Material claims were checked against commit `95560fc` on `main`. Minimal body edits below reflect only where the repository contradicted or sharpened the draft.

| Claim | Result | Evidence |
|---|---|---|
| Five-layer portfolio workflow, EAL, adaptation, avoided loss | **Pass** | `app/pipeline/`, `app/loss/`, `app/adaptation/evidence.py`, `frontend/src/pages/PortfolioDemoPage.tsx` |
| `valuation_date` / no-lookahead | **Pass (nuance)** | Required on portfolio / five-layer path (`app/schemas/portfolio.py`, `app/schemas/five_layer.py`); optional on legacy score batch (`app/schemas/risk.py`); heat path rejects post–valuation-date assessment (`app/hazards/extreme_heat.py`) |
| Hash-chained audit trail + Railway persistence | **Pass (nuance)** | Mechanism in `app/services/audit_trail.py`; Railway volume applies to workflows using configured `get_audit_trail()` (e.g. `/v1/portfolio/analyze`). Recommended `/v1/portfolio/demo-run*` uses a separate unconfigured `AppendOnlyAuditTrail()` — demo audit IDs are not evidenced as durable across restarts (STUBS.md #20; `docs/08-ops/API_DEPLOY.md`) |
| Independent EAL verifier code-isolated | **Pass** | `tests/verification/independent_eal.py` (stdlib only; must not import `app.loss` / `app.services`) |
| Golden Antalya ~100 synthetic assets | **Pass (exact)** | `data/portfolios/golden/antalya_v1.geojson` has **100** features; CI in `tests/portfolios/test_golden_antalya_regression.py` |
| Methodology v0.3.1 preliminary / synthetic | **Pass (nuance)** | Document id `georisk-methodology-v0.3.1` in `docs/methodology/GEORISK_ENGINE_METHODOLOGY.md`; runtime IDs remain `five-layer-eal-v0.3` / `expected-loss-v0.3` (v0.3.1 is a documentation amendment only) |
| Legacy `/v1/risk/score` synthetic | **Pass** | STUBS.md #3 |
| GEE/ORAS5 fallbacks, Scenario Lab heuristic, synthetic damage curves | **Pass** | STUBS.md #1, #2, #11, #16 |
| Demo 2030/2050 horizons are synthetic internal scales | **Pass (nuance)** | Recommended demo accepts assets + `valuation_date`; `ExpectedLossFinancialTranslation.run` builds horizons as `current × 0.95` / `current × 1.05` (`app/loss/expected_loss.py`) — not caller-supplied or externally sourced climate projections |
| Demo prices synthetic wildfire despite methodology flood/heat scope | **Open discrepancy** | `StubHazard` emits wildfire; `stub_global_mdr_v0.1.json` has a wildfire curve; combined demo loss can include wildfire. Public methodology v0.3.1 focuses on flood and extreme heat — disclose; do not treat wildfire as validated |
| Address geocoding not in portfolio demo | **Pass** | STUBS.md #19; `PortfolioDemoPage.tsx` copy |
| Public `/methodology` under PR #80 | **Pass — still open** | https://github.com/ebru0zpolat/georisk-engine/pull/80 — state `OPEN`, not merged as of assessment date (CI checks green) |
| Railway controls + `TRUST_PRIVATE_PROXY_PEERS` | **Pass** | `docs/08-ops/API_DEPLOY.md`; `app/core/client_ip.py`; HEAD = merge of #82 |
| Claim control: stale marketing language | **Pass — still present** | `frontend/index.html` still contains 47M+, GraphQL/webhooks, real-time, “validated”, &lt;200ms claims; README Current API section is cleaner |

**Housekeeping (not a product gap in this assessment):** `STUBS.md` “Pending on open branches” still lists five-layer (#66) and portfolio demo (#71); both are **merged** on the assessed `main`.

**Post-merge documentation qualifications (Codex P1 on PR #85):** Assessment date and repository cut-off above are unchanged. Body wording in §§3.1, 3.3, 4.4 and §7 was tightened so scenario-horizon provenance, demo audit-trail persistence and the wildfire methodology–runtime discrepancy match the cut-off codebase (`ExpectedLossFinancialTranslation.run`, `run_portfolio_demo`, `StubHazard` / `stub_global_mdr_v0.1.json`).

No fabricated RVO/IND numeric scores are used in this document.

---

## 1. EXECUTIVE STATUS

Geo Risk Engine has progressed beyond a concept-stage MVP. The repository now contains a working technical validation product that can ingest portfolio data, run a five-layer physical-climate-risk workflow, calculate scenario-based Expected Annual Loss (EAL), produce adaptation and avoided-loss outputs, record financial results in a hash-chained audit trail (durable on configured shared-trail paths), and independently recompute selected EAL results.

The current product should be described as:

> **A technical-validation MVP for asset-level physical climate risk and financial-impact assessment, with a functioning portfolio workflow, versioned preliminary methodology, synthetic calibration, reproducibility controls and an evidence-led path to Dutch market validation.**

It should not yet be described as:

- a production-calibrated climate loss model;
- a bank-grade or insurance-grade model;
- an independently validated model;
- a regulatory-compliant solution in itself;
- a platform using fully live hazard data for every output;
- a proven Dutch commercial business;
- an audit-assured or certified system;
- a model that predicts actual credit or insurance losses.

### Current stage conclusion

| Dimension | Current stage | Evidence / limitation |
|---|---|---|
| Product concept | Completed | Clear positioning: physical climate risk to financial impact and adaptation evidence |
| Technical MVP | Substantially completed | Portfolio ingest, five-layer demo, EAL, adaptation, avoided loss and verification walkthrough exist |
| Methodology specification | Preliminary, versioned | `georisk-methodology-v0.3.1`; intentionally described as preliminary and synthetic-calibrated |
| Reproducibility | Demonstrated technically | Independent code-isolated recomputation and hash-chained audit trail (persistence path-dependent; see §3.1) |
| Live data integration | Partial | Current score path and several connector fallbacks remain synthetic or proxy-based |
| Calibration | Not completed | Global synthetic damage curves; no Dutch calibrated vulnerability curves demonstrated |
| Empirical validation | Not completed | No historical-event loss backtest or observed-loss benchmark demonstrated |
| Independent validation | Not completed | Recalculation proves reproducibility, not accuracy; independent model challenge remains future work |
| Deployment | Demo deployment stage | Vercel preview available; Railway controls merged, but post-deployment smoke evidence remains operationally relevant |
| Dutch market validation | Not evidenced by repository | Dutch pilot, paid customer, signed LOI and local design-partner evidence must be supplied separately |
| Commercial readiness | Pre-pilot | Pricing and positioning work exist; procurement-grade sales evidence remains incomplete |
| RVO readiness | Evidence-building stage | Technical case materially stronger; commercial, Dutch nexus and financial evidence remain gating items |

**Overall classification:** **Technical-validation MVP / pre-pilot**, not production and not yet RVO submission-ready.

---

## 2. IMPORTANT LEGAL AND APPLICATION POSITION

The application must not use a standard `245/300`, `90-point minimum`, or category-score narrative. For a Turkish national, the case should be structured around the applicable EU–Türkiye Association-law treatment and the business’s genuine, sustainable and evidenced contribution to the Dutch economy.

The business plan must therefore establish:

1. a genuine business activity rather than a residence-driven arrangement;
2. an operational product and credible delivery capability;
3. realistic demand from Dutch or EU customers;
4. sufficient financing and sustainable founder income;
5. identifiable activities to be performed in the Netherlands;
6. local expenditure, partnerships, knowledge contribution and staged employment;
7. consistency between the repository, website, contracts, financial model, CV and supporting documents.

No RVO or IND success probability should be expressed as a fabricated score.

---

## 3. REPOSITORY-BASED PRODUCT EVIDENCE

### 3.1 What is demonstrably built

The current repository supports the following evidence-led claims:

- A portfolio data contract accepting JSON, CSV and GeoJSON inputs.
- A required `valuation_date` on the portfolio / five-layer path, supporting a no-lookahead control (optional only on the legacy score batch schema).
- A five-layer product contract:
  - hazard;
  - exposure;
  - vulnerability;
  - financial translation / EAL;
  - adaptation evidence.
- Expected Annual Loss expressed as an absolute amount and as a proportion of asset value.
- Scenario-related 2030 and 2050 output fields on the recommended portfolio demo. The demo accepts portfolio assets and a `valuation_date`. The recommended portfolio demo exposes 2030 and 2050 fields as synthetic sensitivity outputs generated internally from current intensity using fixed scaling factors (`0.95×` and `1.05×`). These fields demonstrate scenario-contract structure; they are not caller-supplied, externally sourced or empirically calibrated climate projections. They must not be represented as validated forward-looking climate estimates.
- Adaptation recommendations, avoided loss and residual EAL in the demo narrative.
- A hash-chained append-only audit-trail mechanism is implemented. Railway volume persistence currently applies only to workflows using the configured shared audit-trail instance (including the applicable `/v1/portfolio/analyze` path). The recommended portfolio demo creates a separate unconfigured trail; its returned audit identifiers are therefore not yet evidenced as durable or retrievable across requests or restarts. Wiring the demo into the configured persistent trail remains an implementation gap.
- A code-isolated verification process that recomputes selected EAL results without importing the production loss implementation.
- A golden Antalya reference portfolio of 100 synthetic assets on real geography.
- CI regression controls over methodology and expected-loss outputs.
- Explicit separation of real functionality, synthetic calibration, fallbacks and roadmap items through `STUBS.md`.
- Public methodology work for a bilingual `/methodology` page under PR #80.

### 3.2 What the repository does not yet substantiate

The following claims must not be made without additional evidence:

- Full use of live, authoritative hazard data across the public scoring path.
- Dutch property-level integration with Kadaster.
- Production KNMI, PDOK or AHN integrations unless the exact connector and runtime evidence are produced.
- Proprietary and empirically calibrated Dutch building vulnerability curves.
- Accuracy against observed Dutch flood or heat loss events.
- Credit-loss prediction, probability of default, loss-given-default or regulatory capital outputs.
- Insurance-pricing adequacy or actuarial certification.
- ISO 27001, ISO 14001, SOC 2 or other certification/alignment claims without a completed control mapping and evidence pack.
- “Audit-grade,” “bank-grade,” “validated,” “real-time,” “global coverage,” “47M+ locations,” or sub-200ms performance claims without controlled evidence.
- A signed Hong Kong customer, Dutch LOIs or paid pilots unless contracts, invoices and receipts are submitted.

### 3.3 Key model limitations that must be disclosed

The current repository explicitly shows that:

- every number on the legacy `/v1/risk/score` path is generated from deterministic synthetic components;
- GEE and ORAS5 connectors may return labelled fallback values;
- flood and heat paths can rely on proxy or mock inputs;
- the documented v0.3.1 proxy scope focuses on flood and extreme heat. The current demo runtime nevertheless emits a synthetic wildfire intensity and applies a stub wildfire damage curve, so wildfire can affect combined loss. This is an open methodology–implementation discrepancy; wildfire results are not evidenced or validated and should not be relied upon until the runtime is narrowed or the methodology is formally extended;
- Scenario Lab remains a deterministic heuristic layer rather than a downscaled climate scenario model;
- demo 2030/2050 intensity fields on the recommended portfolio path are fixed internal scales of current intensity, not externally sourced climate projections;
- the current damage-curve catalogue is a synthetic global stub;
- the verification and golden portfolios are synthetic;
- address geocoding is not implemented in the portfolio demo;
- EAL agreement demonstrates computational reproducibility, not empirical loss accuracy;
- audit identifiers from the recommended portfolio demo must not be described as durable, restart-persistent or independently retrievable after the response.

For banks, insurers and RVO evaluators, demonstrations should therefore use the labelled five-layer portfolio workflow and not the legacy `/v1/risk/score` endpoint, with the scenario-horizon, wildfire and demo-audit-persistence qualifications above disclosed.

---

## 4. REVISED BUSINESS PLAN

## 4.1 Executive Summary

Geo Risk Engine B.V. will develop and commercialise asset-level physical climate risk and financial-impact assessment technology from the Netherlands.

The platform is designed to convert geospatial hazard information and customer-supplied asset data into structured outputs for financial and operational decision-making. These outputs include exposure indicators, hazard intensities (including synthetic scenario-horizon sensitivity fields on the current demo), preliminary Expected Annual Loss estimates, portfolio concentration views, adaptation measures, avoided-loss estimates and traceable methodology evidence.

The initial product is a technical-validation MVP. It demonstrates that the complete workflow can operate in software and that financial outputs can be reproduced from recorded inputs, parameters and methodology versions. Current loss curves and parts of the hazard input layer are synthetic or proxy-based. The first Dutch phase will therefore focus on local data integration, empirical calibration, historical-event backtesting and design-partner validation rather than presenting the present model as production-ready.

The Netherlands is an appropriate base because it combines:

- significant physical climate and flood exposure;
- world-leading water-management and geospatial expertise;
- a concentrated banking, insurance, pension and infrastructure market;
- strong research and innovation institutions;
- a policy environment focused on climate adaptation and financial resilience;
- access to Dutch and European climate, elevation, property and environmental data;
- the applicant’s financial-sector, audit, governance and regulatory experience.

The company’s immediate commercial objective is to complete one or more paid Dutch design-partner pilots for real-estate, mortgage, commercial-collateral or infrastructure portfolios. Those pilots will test the usefulness of the outputs, data availability, model assumptions, governance expectations and willingness to pay.

## 4.2 Founder Profile

The applicant has more than 16 years of experience across banking, credit monitoring, internal audit, financial regulation, compliance, governance, risk management and financial technology.

The applicant holds a BSc in Statistics, supporting quantitative analysis, probability, risk measurement and model-governance work.

Relevant capability includes:

- portfolio and credit-risk monitoring;
- internal audit and control testing;
- governance, methodology documentation and evidence design;
- regulatory change and licensing programmes;
- design of risk, compliance and reporting processes;
- audit and inspection readiness;
- senior responsibility in regulated financial and crypto-asset environments;
- development of technology-enabled risk and compliance products.

The founder’s principal advantage is not a claim to be a climate scientist or software engineer. It is the ability to translate model outputs into controlled financial-sector workflows with documented assumptions, limitations, data lineage, validation expectations and decision governance.

All job titles, employment periods, locations and responsibilities will match official employment records. The application will not use `Chief Compliance Officer`, `former ING Netherlands compliance officer`, `C-level P&L responsibility` or similar language unless each statement is supported by formal evidence.

## 4.3 Problem Definition

Climate and geospatial information is often delivered as maps, scientific datasets or broad scores. Financial institutions and asset owners require a different output: they need to understand which assets are exposed, how assumptions affect estimated loss, how results change under scenarios, which adaptation measures may reduce exposure, and whether the analysis can be reproduced and challenged.

The problem is therefore not simply lack of climate data. It is the operational gap between climate data and controlled financial decision-making.

Target users include:

- mortgage and commercial real-estate risk teams;
- bank credit, collateral and portfolio-risk functions;
- insurers and reinsurers assessing location concentration and underwriting exposure;
- pension funds, infrastructure funds and asset managers;
- industrial and infrastructure asset owners;
- advisers supporting climate-risk, resilience and reporting programmes.

CSRD and ESRS E1 remain relevant use cases, including material physical-risk and anticipated-financial-effect assessment. They are not the sole market premise. Following the narrowing of CSRD scope, the business will also serve prudential risk, collateral monitoring, underwriting, acquisition due diligence, portfolio resilience and adaptation-investment decisions.

## 4.4 Product

The product is structured around five layers:

1. **Hazard intelligence** — physical hazard inputs by location, scenario and horizon.
2. **Asset exposure** — location, value, building type, use class and other portfolio attributes.
3. **Vulnerability** — the relationship between hazard intensity and potential damage, subject to modelled assumptions.
4. **Financial translation** — preliminary EAL and related financial-impact indicators.
5. **Adaptation evidence** — candidate measures, estimated avoided loss, residual loss and prioritisation.

Product interfaces include:

- portfolio upload through CSV or GeoJSON;
- a single-screen portfolio demo;
- API endpoints;
- downloadable or reviewable methodology and verification artefacts;
- audit-trail identifiers and versioned evidence (durable only where the configured shared trail is used; see §3.1);
- future Country Packs for jurisdiction-specific data, curves, regulation mapping and report templates.

### Current methodology status

The current public methodology document is `georisk-methodology-v0.3.1`. It should be described as a preliminary scenario-loss proxy using synthetic calibration focused on flood and extreme heat. Its purpose is to demonstrate method structure, traceability and reproducibility before empirical calibration. Runtime pipeline and expected-loss identifiers remain `five-layer-eal-v0.3` and `expected-loss-v0.3` (v0.3.1 is a documentation amendment only; no arithmetic change).

Separately, the current demo runtime also emits and prices wildfire through a stub intensity and stub MDR curve, so wildfire can affect combined loss despite being outside the documented flood-and-heat methodology scope. Wildfire output is synthetic and unevidenced and must not be presented as methodologically validated. A separate technical decision is required: remove wildfire from the calculation or formally extend and evidence the methodology.

### Planned Dutch Country Pack

Subject to data licensing and technical feasibility, the Dutch Country Pack will seek to integrate relevant Dutch and European sources for:

- flood and water-system exposure;
- elevation and terrain;
- heat and climate observations;
- building and land characteristics;
- historical events and damage evidence;
- Dutch reporting and decision templates.

No source will be represented as integrated until the connector, licence basis, version, coverage and runtime evidence are documented in a source registry.

## 4.5 Innovation and Differentiation

The innovation claim should be limited to the integration of existing technical disciplines into a controlled financial-risk workflow.

Geo Risk Engine’s intended differentiation is:

- financial translation rather than hazard-map presentation alone;
- transparent versioning of methodology, curves and source data;
- explicit separation of synthetic, proxy and live inputs;
- a reproducible EAL computation with an independent checker;
- a hash-chained evidence trail;
- adaptation and avoided-loss framing;
- modular Country Packs rather than hard-coded national logic;
- a founder-led governance and regulatory perspective suited to regulated buyers.

The company will not claim to be the only provider. Competitors include global climate-risk analytics firms, catastrophe-model vendors, ratings/data providers, consultancies and Dutch scientific institutions. Competitive analysis will compare actual features, coverage, validation status, deployment model and price based on dated public evidence or direct procurement findings.

## 4.6 Target Market and Beachhead

The first commercial vertical is:

> **Real estate, mortgage and commercial collateral portfolios.**

The initial pilot size is expected to be approximately 50–500 assets, allowing a buyer to assess portfolio coverage, data gaps, EAL methodology, asset ranking and adaptation evidence without requiring immediate enterprise-wide deployment.

The Netherlands beachhead will prioritise:

1. specialist real-estate lenders and mortgage-risk teams;
2. insurers with property or commercial-location portfolios;
3. infrastructure and real-estate asset managers;
4. climate-risk and engineering advisers seeking an API/evidence layer;
5. regional or sector-focused institutions able to run a controlled design-partner pilot.

Named institutions may be listed as target accounts, not as customers or partners, unless written evidence exists.

## 4.7 Commercial Model

Planned revenue streams are:

| Revenue stream | Commercial basis | Evidence required before submission |
|---|---|---|
| Paid validation pilot | Fixed scope, portfolio size, deliverables and validation questions | Signed SOW/LOI, price and contact person |
| SaaS subscription | Annual or monthly access based on assets, modules and users | Customer interviews and pricing evidence |
| API licence | Usage- or volume-based access | Working API, service definition and unit economics |
| Professional services | Implementation, data mapping and methodology configuration | Scope controls to avoid becoming a consultancy-only business |
| Country Pack / enterprise licence | Data, reporting and governance configuration | Data licensing and maintenance-cost model |

Earlier prices such as €2,000–€5,000 per month, €500–€1,000 per day or per-asset API fees should be treated as hypotheses until supported by customer interviews, pilot proposals or competitor benchmarks.

## 4.8 Go-to-Market Plan

### Phase 1 — Evidence and design partners (0–6 months)

> **Correction (13 August 2026):** For execution, the 0–6 month window is now governed by three sequential, time-boxed gates with evidence-based exit criteria — scientific validation (Months 0–2), demand validation (Months 2–4) and recurring-product validation (Months 4–6). See [`SIX_MONTH_VALIDATION_GATES.md`](SIX_MONTH_VALIDATION_GATES.md). The bullets below remain the planning intent; the gates document is the pass/fail authority.


- Finalise the public v0.3.1 methodology page.
- Create a Dutch pilot package with problem statement, data requirements, deliverables, limitations and success criteria.
- Conduct structured discovery interviews with at least 15 Dutch/EU prospects.
- Obtain at least two substantive LOIs or one paid pilot.
- Complete a Dutch data-source and commercial-use licence matrix.
- Establish independent technical and climate-domain review relationships.
- Produce one controlled portfolio case study.

### Phase 2 — Calibration and conversion (6–12 months)

- Integrate selected Dutch live data sources.
- Build and document historical flood/heat event datasets.
- Backtest model outputs against observable event or damage evidence.
- Introduce uncertainty and confidence indicators.
- Deliver the first paid Dutch pilot.
- Convert validated pilot demand into an annual subscription proposal.

### Phase 3 — Repeatability and scale (12–36 months)

- Add further Dutch and EU customers.
- Expand Country Packs where customer demand justifies maintenance cost.
- Add technical staff and climate-data expertise.
- Establish adviser and implementation channels.
- Complete independent model challenge and remediation before controlled production claims.

## 4.9 Netherlands Operations and Added Value

The Dutch business will perform or govern:

- product ownership and roadmap decisions;
- Dutch customer discovery, contracting and delivery;
- Dutch Country Pack development and source governance;
- methodology governance, model-risk controls and validation planning;
- collaboration with climate, water, geospatial and academic specialists;
- privacy, security and customer evidence controls;
- commercial partnerships and EU expansion.

Potential Dutch economic contribution includes:

- founder capital committed to a Netherlands-based technology company;
- expenditure on Dutch legal, accounting, cloud, data and specialist services;
- paid work for Dutch climate-data, model-validation and software specialists;
- staged employment as recurring revenue develops;
- development of exportable climate-risk software and methodology from a Dutch base;
- improved climate-risk and adaptation decision evidence for Dutch financial and asset-owning institutions.

Employment forecasts must be conditional and linked to revenue milestones. They must not be presented as guaranteed jobs.

## 4.10 Operating Model

### Year 1

- Founder-led Dutch entity.
- Part-time or project-based engineering support.
- External climate-science/model-validation adviser.
- Dutch professional-service providers.
- Priority on one paid pilot, data licensing and calibration evidence.

### Year 2

- Full-stack/geospatial engineering hire subject to recurring revenue.
- Climate-data/model-validation capability.
- Customer implementation support.

### Year 3

- Customer success or enterprise sales role.
- Additional data-science or regulatory-risk support.

The legal structure is expected to be a Dutch B.V., but formation should be shown as pending until completed. The proposed city should follow customer access, facilitator support, cost and hiring considerations; Amsterdam or Rotterdam should not be claimed as final without an address or establishment plan.

## 4.11 Technology, Data Governance and Security

The existing technology base includes a Python backend, a React frontend, API services, portfolio ingestion, versioned methodology artefacts, automated tests and deployment configurations.

Before enterprise use, the company will implement:

- a complete data-source register;
- commercial-use and redistribution rights analysis;
- source versioning and lineage;
- environment-specific controls preventing synthetic fallbacks from being mistaken for production data;
- EU data-hosting and GDPR controls;
- role-based access and tenant separation;
- secure secret management;
- backup, recovery and audit-trail retention;
- incident response and vulnerability management;
- controlled release and model-change governance;
- customer-facing limitations and acceptable-use terms.

Certification will be considered based on customer procurement requirements. No certification will be claimed in advance.

## 4.12 Validation Roadmap

| Release theme | Objective | Current status |
|---|---|---|
| v0.3.1 | Correct methodology positioning and evidence level | Implemented in normative documents; public page PR remains open |
| v0.4 | Freeze hazard-specific EAL and loss-channel specification | Not completed |
| v0.5 | Expand technical verification, replay tolerances and checker coverage | Partially completed |
| v0.6 | Historical flood and heat event dataset design | Not completed |
| v0.7 | Controlled design-partner pilot | Not evidenced |
| v0.8 | Calibration, benchmarking and uncertainty bands | Not completed |
| v0.9 | Independent challenge and remediation | Not completed |
| v1.0 | Controlled production release after thresholds and governance | Not completed |

## 4.13 Financial Plan Requirements

The previous three-year figures must not be reused without reconstruction. In particular, $5,000 per month equals $60,000 per year, not €80,000. Any conversion to euros must use a stated exchange-rate assumption and date.

The final financial model must be monthly for at least 36 months and include:

- opening cash;
- founder investment;
- signed recurring revenue;
- pilot revenue by contract and payment month;
- subscription revenue by customer cohort;
- direct cloud, data and delivery costs;
- gross profit;
- salaries and contractor cost;
- legal, accounting, insurance and establishment cost;
- sales and marketing;
- tax and social-cost assumptions;
- founder remuneration or drawings;
- capital expenditure;
- working capital;
- closing cash and runway.

Three scenarios are mandatory:

| Scenario | Minimum assumption |
|---|---|
| Downside | No Dutch pilot conversion; any existing customer terminates; delayed data integration |
| Base case | One paid pilot and measured conversion to recurring revenue |
| Upside | Multiple pilots convert; additional enterprise subscription or Country Pack revenue |

The base and downside cases must show whether the founder can meet the applicable IND income requirement and maintain the business without relying on unsigned contracts, speculative grants or uncommitted funding.

No “HK contract” income may be included as contracted revenue unless supported by the agreement, invoices, receipts, termination provisions and customer identity evidence.

## 4.14 Risk Analysis

| Risk | Current exposure | Mitigation |
|---|---|---|
| Synthetic/proxy outputs mistaken for real risk | High | Separate demo and production routes; visible badges; source registry; disable fallbacks in controlled production |
| Lack of empirical calibration | High | Historical-event datasets, observed-loss comparison, Dutch specialist review |
| No Dutch commercial validation | High | 15+ interviews, two substantive LOIs or one paid pilot before submission |
| Single-customer dependence | Unknown | Contract review, revenue diversification and six-month reserve |
| Data licensing | High | Commercial-use matrix before integration or sales commitments |
| Model misuse | High | Limitations, permitted-use terms, human oversight and no sole-basis decisions |
| Competition | Medium-high | Focus on transparent financial translation, modular pilots and governance evidence |
| CSRD scope reduction | Medium | Broader collateral, underwriting, resilience and adaptation use cases |
| Cybersecurity and availability | Medium-high | Environment controls, persistent storage, monitoring, backups and security roadmap |
| Founder concentration | High | Documented processes, contractor bench, staged technical hire and advisory support |
| Financial runway | Unknown | 36-month monthly model, downside case and committed funding evidence |

---

## 5. CURRENT RVO GAP ANALYSIS

### 5.1 Material strengths now available

1. The product narrative is coherent and focused on financial impact rather than generic ESG or mapping.
2. A functioning portfolio workflow exists.
3. The five-layer architecture is implemented in demonstrable form.
4. EAL, adaptation, avoided loss and residual loss are visible in the product flow.
5. Methodology and audit evidence are versioned.
6. Independent recomputation demonstrates reproducibility.
7. Synthetic inputs and limitations are explicitly inventoried rather than concealed.
8. CI and regression controls increase technical credibility.
9. Deployment and public methodology work demonstrate execution capacity.

### 5.2 Submission blockers

| Priority | Blocker | Required closure evidence |
|---:|---|---|
| P0 | No evidenced Dutch customer validation | One paid Dutch pilot or two substantive signed LOIs with scope, contact and intended timeline |
| P0 | No defensible 36-month financial model | Monthly downside/base/upside workbook plus assumptions and runway |
| P0 | Founder income sustainability not demonstrated | Accountant-reviewed forecast and committed funding / contracted revenue evidence |
| P0 | Live-data and calibration gap | Dutch source registry, licence review, connector/runtime evidence and calibration plan |
| P0 | No empirical backtest | At least one historical flood/heat validation pack with documented limitations |
| P1 | Public methodology PR not merged | Complete visual/manual gate and merge PR #80 |
| P1 | Website/repository claim inconsistency | Remove stale performance, coverage, GraphQL/webhook, AI and real-time claims not supported by the product |
| P1 | Legacy synthetic score path remains public | Separate or de-emphasise it; use five-layer demo for institutional evidence (with horizon / wildfire / demo-audit qualifications in §3) |
| P1 | Recommended demo audit trail not on Railway volume | Wire `run_portfolio_demo` to the configured shared `get_audit_trail()` path (separate engineering PR) |
| P1 | Wildfire priced in demo outside documented flood/heat scope | Remove wildfire from demo calculation **or** formally extend and evidence the methodology (separate technical decision) |
| P1 | Independent challenge absent | Named external reviewer/adviser and validation scope |
| P1 | Dutch operating plan not evidenced | Address/facilitator plan, service providers, activities and implementation calendar |
| P1 | Founder CV claims need reconciliation | Official titles, dates, role descriptions and reference letters |
| P2 | B.V. not formed | Formation plan or incorporation documents at the appropriate application stage |
| P2 | Team and hiring projections uncommitted | Role descriptions, timing and revenue-linked hiring triggers |

---

## 6. EVIDENCE PACK

### 6.1 Founder evidence

- Passport and Turkish nationality evidence.
- Degree certificate and transcript.
- Complete CV with official titles.
- Employment records and employer letters.
- Evidence of ING experience stated accurately by entity and location.
- References supporting relevant risk, audit and governance responsibilities.
- Evidence of entrepreneurial projects, including VaultScope and incubation participation.

### 6.2 Product evidence

- Live demo URL and dated screenshots.
- Architecture diagram.
- API and portfolio-upload demonstration.
- `georisk-methodology-v0.3.1` document.
- EAL independent verification report.
- Golden portfolio regression evidence.
- `STUBS.md` limitations inventory.
- Security and deployment overview.
- Product roadmap from v0.3.1 to controlled v1.0.
- GitHub commit/PR history evidencing founder-led execution.

### 6.3 Commercial evidence

- Signed customer contracts.
- Invoices and matching bank receipts.
- Dutch customer interview log.
- Signed LOIs with named use case, scope and timing.
- Paid-pilot SOW and acceptance criteria.
- Pricing interviews or written price feedback.
- Dated competitor analysis.

### 6.4 Netherlands evidence

- Dutch establishment and address plan.
- Dutch facilitator/incubator correspondence.
- Adviser, university or research collaboration evidence.
- Dutch data-source and licensing matrix.
- Dutch professional-service quotations or engagement letters.
- Three-year local spending and hiring plan.
- Explanation of why the activities must be performed from the Netherlands.

### 6.5 Financial evidence

- 36-month monthly financial statements.
- Downside, base and upside scenarios.
- Founder investment evidence.
- Personal living-cost and liquidity evidence.
- Contracted revenue schedule.
- Data/cloud/personnel cost quotations.
- Exchange-rate assumptions.
- Accountant review or compilation statement where feasible.

---

## 7. CLAIM CONTROL TABLE

| Claim | Permitted wording now | Prohibited wording now |
|---|---|---|
| Product stage | Technical-validation MVP / pre-pilot | Production-ready / bank-grade |
| Methodology | Versioned preliminary scenario-loss proxy | Validated climate loss model |
| Calibration | Synthetic calibration, clearly labelled | Proprietary Dutch calibrated curves |
| Verification | Independent code-isolated recomputation proves reproducibility | Independently validated accuracy |
| Audit | Hash-chained audit trail; Railway persistence only for configured shared-trail workflows | Durable / restart-persistent demo audit IDs; statutory audit-grade / assured |
| Scenario horizons (2030/2050) | Synthetic sensitivity fields (`0.95×` / `1.05×` of current) demonstrating contract structure | Caller-supplied, externally sourced or empirically calibrated climate projections |
| Implemented perils (demo) | Documented proxy scope: flood and extreme heat; disclose synthetic wildfire runtime discrepancy | Validated multi-peril (incl. wildfire) climate loss model |
| Financial impact | Preliminary scenario-based EAL under documented assumptions | Prediction of actual losses |
| Regulatory use | Supports selected evidence and risk workflows | Ensures CSRD/ECB/AFM/DNB compliance |
| Customer status | Named only with contract/LOI evidence | “Existing client” based on discussion |
| Data | Specific live source only with runtime and licence evidence | Fully live global authoritative coverage |
| Netherlands | Planned Dutch Country Pack and validation programme | Existing Kadaster/KNMI integration without proof |

---

## 8. 90-DAY RVO READINESS PLAN

### Days 1–30 — Technical and claim closure

- Merge and publish the v0.3.1 methodology page after the manual visual gate.
- Reconcile README, website, API description, pricing copy and RVO plan.
- Produce a single source registry identifying live, fallback, staged and roadmap data.
- Prepare a Dutch pilot data template for 50–500 assets.
- Document the historical-event backtest design.
- Finalise the 36-month financial-model structure.

### Days 31–60 — Dutch validation

- Complete at least 15 structured prospect interviews.
- Secure two substantive LOIs or negotiate one paid pilot.
- Obtain a Dutch climate/geospatial adviser review of methodology and data plan.
- Confirm commercial-use rights for priority Dutch data sources.
- Produce one Dutch sample portfolio case, clearly labelled where synthetic.

### Days 61–90 — Application evidence

- Execute or contract the first paid pilot where possible.
- Complete the first historical-event validation pack.
- Finalise downside/base/upside financial projections.
- Assemble founder, product, commercial and Dutch nexus evidence.
- Conduct a full cross-document claim audit.
- Obtain legal/accounting review of the immigration and financial submission package.

---

## 9. FINAL ASSESSMENT

Geo Risk Engine now has a materially stronger RVO case than the earlier business-plan draft suggested. The repository demonstrates genuine technical execution, a coherent regulated-market problem, a functioning end-to-end portfolio workflow and unusually transparent treatment of methodology limitations.

The decisive weakness is no longer whether an MVP exists. The decisive weaknesses are:

1. empirical accuracy and calibration have not yet been established;
2. live Dutch data use is not yet evidenced sufficiently;
3. Dutch customer demand is not evidenced through a paid pilot or substantive LOIs;
4. sustainable founder income and runway are not demonstrated through a coherent monthly financial model;
5. website and repository claims still require complete alignment with the as-built system.

Accordingly, the correct application status is:

> **RVO evidence-building stage: technical MVP substantially demonstrated; commercial validation, Dutch-specific calibration, financial sustainability and local economic nexus still require closure before submission.**

The next milestone is not “add more features.” It is to convert the existing technical MVP into an evidenced Dutch pilot proposition and complete the financial and local-economy proof package.

