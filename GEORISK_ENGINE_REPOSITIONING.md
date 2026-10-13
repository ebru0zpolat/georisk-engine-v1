# GeoRisk Engine — Strategic Repositioning & Development Directive

> **Superseded in product-identity scope (19 September 2026).** Sections 1 (product identity) and 3
> (priority vertical) are superseded by [`docs/00-master/PRODUCT_CHARTER_V2.md`](docs/00-master/PRODUCT_CHARTER_V2.md).
> The five-layer contract and Country Pack architecture below remain accurate and are now Track B — the
> reference implementation, not the product. Retained as history; where it conflicts, the charter wins.

> **Version:** 1.0 — 3 August 2026
> **Status:** BINDING for all development work. Read fully before writing any code.
> **Context:** This document translates the August 2026 strategy decision (COP31 / Türkiye / Netherlands growth analysis + Jean Monnet report v2.1) into engineering direction. It supersedes any earlier "climate map" framing.

---

## 1. Product identity (INVIOLABLE)

GeoRisk Engine is:

> **Asset-level physical climate risk intelligence and financial impact assessment for regulated institutions, infrastructure owners and investors.**

GeoRisk Engine is NOT:

- ❌ A climate data map or hazard visualisation tool ("where can it flood?" is an input, never the product)
- ❌ An ESG reporting SaaS or emissions calculator
- ❌ An engineering/hardware product (no turbine design, no cooling systems, no materials science)
- ❌ A Netherlands-specific tool (the core stays global; countries are packs)

The real product is a **decision and evidence engine**: it converts location-level climate hazards into asset exposure, expected financial loss, adaptation options and **auditable evidence**.

**Elevator line (use verbatim in README, landing page, API docs):**
"From climate maps to financeable adaptation: converting location-level climate hazards into asset exposure, financial loss and investment priorities."

---

## 2. Core architecture: Global Core + Country Packs

**Fundamental rule: never hard-code country-specific logic into the core.** Every country-dependent element lives in a versioned Country Pack loaded at runtime.

### 2.1 GeoRisk Core (country-agnostic)

| Component | Responsibility |
|---|---|
| Hazard modelling framework | Pluggable hazard modules: flood (fluvial/pluvial/coastal), extreme heat, wildfire, drought, storm/wind, landslide, water stress |
| Climate scenario engine | CMIP6/CORDEX-based scenarios; standard horizons **2030 / 2050 / 2100**; SSP/RCP selectable per analysis |
| Asset & portfolio data model | Universal asset schema (see §3) + portfolio aggregation |
| Risk scoring methodology | Hazard × Exposure × Vulnerability → risk score (versioned methodology, WCI-compatible) |
| Expected loss model | Expected Annual Loss (EAL), damage curves, business interruption, value-at-risk sensitivity |
| Vulnerability adjustment | Structure type, age, use, protection level, adaptation capacity modifiers |
| Adaptation evidence module | Measure catalogue → cost → risk reduction → residual risk → payback / avoided loss |
| Audit trail | Every score traceable: input data version, methodology version, pack version, timestamp, parameters. Append-only log |
| Reporting engine | PDF report, API response, and **audit evidence export** from the same computation record |
| API | REST; bulk upload (CSV/GeoJSON); portfolio endpoints |

### 2.2 Country Pack interface (what a pack must provide)

```
country_pack/
  manifest.yaml          # pack id, version, jurisdiction, data licences, valid-from
  terrain/               # elevation / DEM sources & resolution config
  hydrology/             # water management model, flood defence standards
  cadastre/              # building & parcel data adapters
  climate/               # localised scenario downscaling
  damage/                # local damage curves, insurance loss data (if licensed)
  regulation/            # applicable disclosure/prudential rules mapping
  templates/             # report templates, language, valuation conventions
  adaptation/            # local measure catalogue with costs
```

Planned packs: **Türkiye Climate Pack** (proving ground) → **Netherlands Climate Pack** (first EU validation market) → Mediterranean Wildfire & Water Pack (ES/IT/GR/PT) → North Sea Offshore Infrastructure Pack (NL/UK/DE/DK) → Germany (river flood, industry, supply chain) → UK (flood, mortgage, offshore wind) → Gulf (extreme heat, water, data centres) → Southeast Asia (coastal flood, supply chain). The Netherlands is a validation market, **not the destination**: any design decision that only works for NL is an architecture bug. A new pack must be addable by writing data adapters + config only — zero core changes. Treat that as an acceptance test.

### 2.3 The five mandatory layers

Every analysis pipeline MUST traverse all five layers — a result that stops at layer 1–2 is a map, not a product:

1. **Hazard intelligence** — multi-hazard, multi-scenario, multi-horizon
2. **Asset exposure** — geocoded asset/collateral location + value + type + use
3. **Vulnerability** — structure-specific fragility and adaptation capacity
4. **Financial translation** — EAL, value impairment, business interruption, credit-risk impact
5. **Adaptation evidence** — measures, costs, risk reduction, residual risk, investment priority

Value chain to encode as the pipeline contract:
`Hazard × Exposure × Vulnerability → Expected Loss → Adaptation Investment → Avoided Loss`

### 2.4 Global market matrix (drives hazard-module priority, NOT country coupling)

The product serves one problem everywhere: **converting climate hazard into financial and operational decisions.** Markets differ only in dominant hazards and buyer type — both are pack/config concerns:

| Market | Dominant hazards | Use case (same core pipeline) |
|---|---|---|
| Türkiye | Wildfire, flood, heat, water stress, landslide | Bank portfolios, municipal adaptation demos |
| Netherlands | Flood, heavy rainfall, drought, subsidence | RE/collateral risk, offshore resilience |
| Germany | River flood, industrial exposure | Corporate asset & supplier risk |
| Benelux | Finance, insurance, ports, logistics | Portfolio risk, critical infrastructure |
| UK | Flood, mortgage exposure, offshore wind | Collateral & energy asset risk |
| Gulf | Extreme heat, water scarcity | Data centre & critical facility resilience |
| Southern Europe | Wildfire, drought, heat | Tourism, agriculture, insurance, RE |
| Southeast Asia | Coastal flood, supply chain | Facility & supplier disruption risk |

**Engineering consequence:** prioritise hazard modules by how many target markets need them (flood and heat serve all eight; subsidence serves one). Build the widely-shared hazards first, market-specific ones inside packs.

---

## 3. Priority vertical: Real Estate, Mortgage & Commercial Collateral (P0)

**This is the first and only commercial vertical until it ships.** Rationale: standardisable data, directly expressible financial outcome, sellable to banks/insurers/asset managers in both Türkiye and NL, and aligned with the founder's financial-regulation expertise.

### 3.1 Input schema (portfolio upload)

Required per asset: address or lat/lon · asset value · building type · use class.
Optional (improves vulnerability layer): construction year · floors · insurance coverage · existing adaptation measures · loan/collateral linkage (LTV context).

Support **50–500 asset portfolios** as the design target for the first demos; architecture must scale beyond, but do not optimise prematurely.

### 3.2 Output contract (per asset AND portfolio-aggregated)

- Risk score per hazard and composite (methodology-versioned)
- Expected Annual Loss (absolute + % of asset value)
- Scenario deltas: 2030 / 2050 (2100 optional for real estate)
- Collateral value sensitivity indicator
- Insurability indicator (insured / insurable-with-conditions / protection gap)
- Recommended adaptation measures with cost and avoided-loss estimate
- Post-adaptation residual risk
- **Evidence pack**: exportable, audit-ready bundle referencing data sources, versions and methodology (ESRS/CSRD physical-risk disclosure structure; EU Taxonomy adaptation / DNSH assessment fields)

### 3.3 Explicit non-goals for P0

- Municipal adaptation planning workspace (third vertical — build only as thin demo for COP31, never as revenue assumption)
- Offshore wind / thermal resilience modules (second vertical — consortium-only, do not start solo)
- Any UI feature whose only output is a coloured map without financial translation

---

## 4. Delivery roadmap (aligned with COP31 & Jean Monnet timelines)

### Phase A — August–October 2026 (HARD DEADLINE: end of October)

> ⚠️ **Freeze rule:** COP31 runs 9–20 Nov 2026 and collides with the Jean Monnet application window. ALL Phase A deliverables must be complete by 31 Oct. No new GeoRisk workstreams open in November.

- [ ] Remove all "general climate map" narrative from code, README, UI copy
- [ ] Implement the five-layer pipeline contract end-to-end for ONE portfolio type
- [ ] Build sample portfolio: **Antalya** (heat/wildfire/flash-flood/tourism assets) or **İstanbul** (urban flood/heat/commercial RE) — pick one, not both
- [ ] Demo flow: upload portfolio → hazard → expected loss → adaptation → avoided loss (single screen narrative)
- [ ] Publish English methodology note (versioned, citable — this doubles as academic evidence for the Jean Monnet file)
- [ ] Produce the measurable **COP31 case study** (EN): portfolio, findings, adaptation ROI

### Phase B — December 2026–February 2027 (first international pack + pack framework)

- [ ] **Pack framework first:** implement the Country Pack loader/interface generically, proven by running the SAME portfolio pipeline against both `pack-tr` and `pack-nl`
- [ ] Netherlands Climate Pack v0 as the first international instance: consume Dutch public climate/water data as **inputs** (Climate Adaptation Platform tools, public flood/subsidence layers) — never compete with them
- [ ] 50–500 asset Dutch RE/collateral sample portfolio
- [ ] Discovery-ready demo reusable for ANY market's bank / insurer / mortgage provider / asset manager (NL conversations first, but the demo must be pack-parameterised, not NL-hard-coded)
- [ ] Scope stub manifests for the next two packs (Mediterranean, Germany or UK) to validate the pack interface against real data-source diversity
- [ ] Draft offshore/thermal resilience project proposal for a Dutch hogeschool/research partner (proposal only — no code)

### Phase C — March–July 2027 (commercial validation + scale-out)

- [ ] First paid pilot (NL is the primary candidate; a strong TR bank/insurer pilot counts equally)
- [ ] ESRS/CSRD evidence export (production quality — applies EU-wide, not NL-specific)
- [ ] EU Taxonomy adaptation & DNSH assessment module
- [ ] Portfolio API (external consumers)
- [ ] Adaptation cost–benefit module
- [ ] Third pack kickoff based on pilot traction (Mediterranean / Germany / UK)
- [ ] Offshore wind consortium project as a SEPARATE repo/track (GeoRisk contributes the climate/geo/financial risk layer only)

---

## 5. Regulatory anchoring (drives the evidence pack design)

Evidence outputs are **intended to support selected physical-risk assessment and evidence requirements** relevant to the frameworks below. They are **not** a complete compliance solution. Regulatory coverage remains subject to institution-specific materiality, governance, scenario-analysis and disclosure requirements.

| Framework | GeoRisk output mapping (support, not compliance claim) |
|---|---|
| ECB climate stress testing / prudential expectations | Selected portfolio-level physical risk exposure & scenario loss proxies |
| EBA ESG risk guidelines | Selected asset-level physical risk identification and quantification inputs |
| CSRD / ESRS (E1 physical risk) | Materiality-aware disclosure fields: hazard, vulnerability, adaptation measures — vulnerability-adjusted, per EC/JRC direction (hazard alone is insufficient) |
| EU Taxonomy (adaptation, DNSH) | Adaptation measure evidence + residual risk fields |
| Türkiye: İklim Kanunu / yerel iklim eylem planları (2027 deadline) | Municipal demo alignment (COP31 case study only) |
| TSRS 2 | Physical-risk evidence fields for TR disclosure workflows (Phase C template) |

Design principle: **a regulator or auditor must be able to reproduce any number the platform outputs** from the audit trail (**reproducibility**). That is distinct from **validation** against observed losses and from full **model assurance**. Treat the audit trail as a first-class feature, not logging. Preferred public phrasing: see `docs/methodology/GEORISK_ENGINE_METHODOLOGY.md` §9.

## 6. Engineering constraints & conventions

- **Stack continuity:** keep the existing Supabase backbone and graph intelligence layer; new work extends Phases 0–4, does not rewrite them.
- **Methodology versioning:** semantic-versioned methodology documents; every stored result references the methodology version it was computed with. Changing a damage curve = new minor version.
- **Data provenance:** every dataset entry carries source, licence, retrieval date, resolution. No unlicensed insurance/damage data.
- **Language:** code, API, docs in English. Report templates localised per Country Pack (TR/EN first, NL later).
- **Naming:** product name is **GeoRisk Engine**. Module names: `georisk-core`, `pack-tr`, `pack-nl`, `pack-<iso2>` for all future packs. Do not brand modules with ozDNA/complyDNA/originDNA names — separate product families.
- **No blockchain anchoring.** Audit trail is a hash-chained append-only log, consistent with the originDNA design philosophy but implemented independently.

## 7. Definition of done for the repositioning

The repositioning is complete when BOTH hold:

1. A cold viewer of the repo/demo answers "what does this do?" with *"it tells a bank what climate change costs their collateral portfolio and what fixing it is worth"* — and NOT *"it shows climate risk on a map."*
2. Adding a hypothetical third country requires only a new `pack-<iso2>` directory — no edits to `georisk-core`. If it doesn't, the Netherlands (or any country) has leaked into the core and must be refactored out.

---

## Annex B — Product-strengthening initiatives (approved Aug 2026)

Seven initiatives that convert the founder's audit/compliance background into product moats. Priority tags: **[A/B]** = build within Phase A/B, **[C]** = Phase C, **[NOW]** = immediate cheap win, **[SCHEMA]** = data-model decision only, build later.

### B.1 Backtesting / historical validation module [A/B]

The #1 sales objection will be "does your model actually work?" Validation events must match **active modules** (Phase A: **flood** and **extreme heat**).

**In scope:** 2021 Western Black Sea floods (flood); a documented extreme-heat / heatwave episode with observable asset or productivity loss (heat).  
**Out of scope until wired:** 2021 Manavgat wildfires (wildfire module not active) — do not cite as a product backtest while wildfire is roadmap. Post-2023 earthquake climate-driven losses are not a Phase A module test.

Each backtesting unit must show: pre-event prediction (as-of `valuation_date`) → observed hazard intensity → observed damage → predicted damage → error metric. Single disasters alone are insufficient for EAL validation.

- Output: a versioned **Validation Report** — becomes the strongest section of the methodology note and a first-meeting sales asset.
- Engineering: the pipeline must accept a `valuation_date` parameter so any analysis can be computed "as of" a past date with only then-available data (no lookahead leakage). This is a core requirement — retrofit is expensive.

### B.2 Model Risk Management pack — product feature, not documentation [A/B]

Regulated buyers must onboard third-party models into their model inventory and defend them to auditors (SR 11-7 / ECB model-risk logic).

- Ship a customer-facing **Model Validation Pack** per methodology version: assumptions, limitations, sensitivity analyses, data lineage, known failure modes.
- Auto-generate from the audit trail + methodology docs; export alongside the evidence pack.
- Positioning: competitors sell a risk score; GeoRisk also does the buyer's internal model-governance homework.

### B.3 Uncertainty as a feature [C]

Single-number outputs ("EAL: €142K") collapse under audit. Every output must carry:

- Confidence interval / range on EAL and scores.
- **Uncertainty attribution**: which input contributes most (e.g. "60% of uncertainty from terrain data resolution — reducible with dataset X").
- This creates the upsell path (better data → narrower interval) and satisfies ESRS/prudential expectations of honest uncertainty treatment.

### B.4 Insurance protection-gap report as standalone output [C]

Insurance coverage is already an optional input. Add a portfolio-level report: share of assets uninsured/underinsured against material hazards ("23% of your portfolio carries uninsured physical risk").

- One board-slide output; TR angle: non-DASK perils; NL angle: flood insurance debate.
- Low build cost — aggregation over existing fields — high commercial salience.

### B.5 TSRS bridge (Türkiye) [C — start template in B if COP31 traction]

The ESRS export engine gains a **TSRS template** (Türkiye Sürdürülebilirlik Raporlama Standartları, physical-risk disclosures) as a `pack-tr` report template.

- Small delta over ESRS mapping; opens sales to KGK-scope Turkish corporates ahead of competitors.
- Reinforces the pack principle: disclosure frameworks are templates, never core logic.

### B.6 Golden portfolios [NOW]

One realistic **synthetic** reference portfolio (~100 assets) per active market (TR first, NL next).

- Dual use: live 15-minute discovery demo without waiting for customer data, AND regression-test fixture run on every release (score drift beyond tolerance fails CI).
- Synthetic but plausible: real geographies, fictional assets/values. No real customer or personal data.

### B.7 Adaptation outcome data — the long-term moat [SCHEMA]

Track the loop: recommended measure → implemented (customer-confirmed) → realised risk reduction. Aggregated and anonymised, this becomes a dataset nobody else has: **realised ROI of adaptation investments**.

- Action now: add `measure_status`, `implemented_date`, `post_implementation_review` fields and consent/anonymisation flags to the adaptation schema. Collection and analytics come later; the schema cannot be retrofitted cheaply.

### Annex B guardrails

- None of these override Phase A deadlines: B.1's `valuation_date` parameter and B.7's schema fields are the only Annex items allowed to touch Phase A scope.
- B.3–B.5 must not start before the P0 vertical ships end-to-end.
- Every Annex feature obeys the five-layer contract and the audit-trail reproducibility test.
