# GeoRisk Engine — Agent-Native Discovery & Distribution Strategy

> **Operating reconciliation (25 August 2026):** Content and distribution execute under the
> [founder-autonomous roadmap](../00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md) and
> [machine-readable policy](../../config/automation-policy.yml). Routine editorial approval is
> removed; B1–B7 and deployed metadata checks govern AUTO-PASS, while unsupported topics are
> AUTO-BLOCKed and skipped. No workflow is operational merely because this policy is documented.


**Status:** Draft  
**Purpose:** Product / Engineering / Distribution Strategy  
**Scope:** AI-agent discovery, machine-readable trust, API accessibility, and agent-executable workflows

## 1. Objective

GeoRisk Engine should not treat AI visibility as a separate “AI SEO” project. The objective is to turn the existing API-first architecture into an **agent-native distribution channel** where AI systems can:

> **Discover → Understand → Verify → Execute**

GeoRisk should optimize for human visitors, search engines, and AI agents researching climate risk, geospatial analytics, physical-risk APIs, asset-level risk, and regulatory reporting solutions.

```text
Search / Agent
      ↓
Discovers GeoRisk
      ↓
Understands capabilities
      ↓
Verifies methodology + provenance
      ↓
Identifies appropriate API/tool
      ↓
Executes risk analysis
      ↓
Receives structured RiskScoreResponse
      ↓
Generates decision-support output
```

This is primarily a **distribution and interface problem**, not a content-generation problem.

## 2. Core principle

Do not build a superficial AI-SEO layer on top of GeoRisk. Reuse and expose the existing product architecture:

```text
Existing GeoRisk capability
        ↓
Machine-readable representation
        ↓
Agent discovery
        ↓
Agent verification
        ↓
Agent execution
```

Existing assets already provide much of the required foundation:

- API-first architecture;
- structured `RiskScoreResponse`;
- flood and heat risk scoring;
- multi-component physical-risk outputs;
- provenance controls and fail-closed data handling;
- methodology and licence/source metadata;
- risk-report and TCFD report generation; and
- `/v1/reports/tcfd` and `/v1/reports/risk`.

The goal is to make these capabilities **discoverable, understandable, trustworthy, and executable by machines**.

## 3. Agent-native distribution model

### Layer 1 — Discoverable

GeoRisk should be discoverable for high-intent queries such as:

```text
physical climate risk API
asset level climate risk API
flood risk API
heat risk API
geospatial risk intelligence platform
climate risk scoring API
portfolio physical risk assessment
industrial asset climate risk
data center climate risk assessment
CSRD physical climate risk
TCFD physical risk analytics
Netherlands flood risk API
climate risk due diligence API
```

Benchmark visibility across Google, Bing, Brave Search, ChatGPT, Claude, Gemini, Perplexity, and other relevant agent/search systems. The implementation must not assume that any AI product permanently uses a particular search provider.

#### Retrieval competitors

Traditional commercial competitors are also retrieval competitors.

| Competitor | Relevant retrieval category |
| --- | --- |
| Climate X | Asset-level climate risk |
| Jupiter Intelligence | Physical climate risk |
| Mitiga Solutions | Climate intelligence |
| Moody's RMS | Catastrophe / climate risk |
| Esri | Geospatial analytics |
| ICEYE | Flood / SAR intelligence |
| Planet | Earth observation |
| CoreLogic | Property risk |
| Tomorrow.io | Weather intelligence |
| ClimateCheck | Property climate risk |

Measure not only whether GeoRisk ranks above these companies, but whether it enters an agent's candidate set and supplies enough evidence for the agent to recommend or use it.

### Layer 2 — Understandable

Canonical positioning:

> **GeoRisk Engine is an API-first physical climate and geospatial risk intelligence platform that converts asset locations and hazard data into structured risk scores and decision-support outputs.**

Machine-readable capabilities should include:

- Asset Risk Scoring;
- Portfolio Risk Scoring;
- Flood Risk;
- Heat Risk;
- Physical Climate Risk;
- Geospatial Risk Intelligence;
- Risk Explanation;
- Data Provenance;
- Risk Reporting; and
- TCFD Reporting.

Agents must also be able to identify unsupported hazards, unavailable geographies, synthetic or fallback datasets, unverified observations, model limitations, licence restrictions, decision-support-only outputs, and non-production-eligible components. Uncertainty must be explicit rather than hidden in marketing language.

#### Canonical capability pages

Create stable, indexable pages for important concepts:

```text
/climate-risk-api
/physical-climate-risk
/flood-risk-api
/heat-risk-api
/asset-risk-scoring
/portfolio-risk
/geospatial-risk-intelligence
/data-centre-climate-risk
/tcfd-climate-risk
/csrd-physical-risk
/methodology
/data-sources
/provenance
/limitations
/api
/docs
```

These must not be thin keyword landing pages. Each page should answer:

1. What problem does this solve?
2. What inputs are required?
3. What output is produced?
4. Which datasets are used?
5. What methodology is applied?
6. What limitations exist?
7. Which API endpoint or tool performs the operation?
8. How can an agent or developer execute it?

### Layer 3 — Trustworthy

Expose the existing provenance architecture as a distribution asset. The target evidence chain is:

```text
Claim → Methodology → Data Source → Dataset Version → Licence
      → Retrieved Date → Transformation → Model → Risk Output → Limitations
```

An agent should be able to answer “Where did this score come from?” without relying on opaque marketing claims.

#### Machine-readable provenance

Where technically appropriate, risk outputs should expose structured provenance:

```json
{
  "hazard": "flood",
  "score": 72,
  "provider": "...",
  "dataset_id": "...",
  "dataset_version": "...",
  "retrieved_at": "...",
  "source_url": "...",
  "licence": "...",
  "licence_url": "...",
  "observation_or_scenario": "...",
  "native_crs": "...",
  "output_crs": "...",
  "verification_status": "...",
  "production_eligible": false
}
```

The precise schema should reuse existing GeoRisk contracts. Do not create a parallel SEO-specific provenance schema.

Publish stable `/methodology`, `/data-sources`, `/provenance`, `/limitations`, `/security`, and `/privacy` evidence pages. Where appropriate, expose dataset names, providers, licences, versions, retrieval dates, methodology and model versions, geographic and hazard coverage, known limitations, and verification status.

### Layer 4 — Executable

The highest-value stage is reached when an agent can move from retrieval to execution:

```text
Agent
  ↓
Discovers GeoRisk
  ↓
Reads capability definition and methodology/provenance
  ↓
Selects the appropriate tool
  ↓
Calls GeoRisk
  ↓
Receives a structured result
```

Existing APIs remain the source of truth. Agent protocols wrap those APIs rather than duplicate business logic.

## 4. Agent tool surface

Candidate tools:

```text
score_asset()
score_portfolio()
get_flood_risk()
get_heat_risk()
get_risk_explanation()
get_data_provenance()
generate_risk_report()
generate_tcfd_report()
```

For example, “Evaluate the physical climate risk of these 200 logistics assets and prepare a TCFD-compatible summary” maps to:

```text
score_portfolio() → get_data_provenance() → generate_tcfd_report()
```

Future hazards can extend this interface without changing the interaction model.

## 5. MCP layer

Evaluate an MCP server as an additional interface to the existing API:

```text
Claude / ChatGPT / Agent
          ↓
         MCP
          ↓
GeoRisk Agent Adapter
          ↓
Existing GeoRisk API
          ↓
Risk Engine
          ↓
RiskScoreResponse
```

> MCP must not become a second risk engine.

The adapter should translate tool calls into existing API operations, preserving one scoring implementation, validation layer, provenance model, authorization model, and audit path.

### Initial MCP tool contracts

| Tool | Input | Output / existing operation |
| --- | --- | --- |
| `score_asset` | `latitude`, `longitude`, `asset_type` | `RiskScoreResponse` |
| `score_portfolio` | `assets[]` | Portfolio summary, asset scores, hazard breakdown |
| `get_flood_risk` | Asset or location | Flood score, category, provenance, limitations |
| `get_heat_risk` | Asset or location | Heat score, category, provenance, limitations |
| `get_data_provenance` | Risk result or dataset | Provider, dataset, version, licence, retrieval date, verification status |
| `generate_tcfd_report` | Existing report request | Invoke `POST /v1/reports/tcfd` |

## 6. API documentation as distribution

Treat documentation as a customer-acquisition surface. Every important operation should publish its problem, input, endpoint, example request and response, methodology, data provenance, and limitations.

For example, a Flood Risk API page should explain its purpose and link directly to its methodology, data source, licence, limitations, and API specification. This creates an agent-readable evidence graph instead of isolated marketing pages.

## 7. Structured web metadata

Evaluate applicable metadata for:

- `Organization`;
- `SoftwareApplication`;
- `Dataset`;
- API documentation;
- FAQ;
- articles and technical methodology; and
- breadcrumb relationships.

Dataset pages should align with internal provenance contracts wherever practical. Structured-data claims must not exceed the underlying evidence.

## 8. Content strategy

Prioritize decision-intent and agent-retrieval queries rather than generic traffic.

| Cluster | Example targets |
| --- | --- |
| Climate risk APIs | Physical climate risk API, asset climate risk API, portfolio climate risk API |
| Hazard APIs | Flood risk API, heat risk API; add other hazards only when supported |
| Financial decision support | Climate risk for lenders/collateral, physical climate risk due diligence |
| Regulatory | TCFD physical risk assessment, CSRD physical climate risk, IFRS S2 physical climate risk |
| Geospatial intelligence | Geospatial risk intelligence, geospatial analytics API, location risk API |

Do not imply regulatory compliance where GeoRisk provides only decision-support inputs.

Create evidence-based comparison pages only where claims can be substantiated. Candidate dimensions include API availability, asset and portfolio analysis, supported hazards, provenance visibility, regulatory outputs, machine-readable output, agent integration, and pricing transparency. Do not publish unsupported competitor claims.

## 9. Agent visibility benchmark

Run a repeatable prompt suite periodically across relevant agent and search environments. Example prompts:

```text
What are the best APIs for physical climate risk?
Which platforms provide asset-level flood risk scoring?
What climate-risk APIs can banks use for collateral assessment?
What tools provide physical climate risk analytics for data centres?
What alternatives exist to Climate X?
Which APIs can generate TCFD physical-risk analysis?
What geospatial risk intelligence platforms expose developer APIs?
```

Record:

- whether GeoRisk is mentioned, cited, and linked;
- its position and competitors mentioned;
- the source used;
- whether the product and capabilities are described correctly;
- hallucinated capabilities;
- whether documentation and the API can be found; and
- whether the agent can execute the operation.

## 10. Distribution funnel and metrics

The traditional and agent-native funnels should coexist:

```text
Search → Website → Demo → Sales → API

Agent Question → Retrieval → GeoRisk Citation → Capability Understanding
               → Evidence Verification → Tool Discovery → API / MCP Execution
               → Qualified Usage → Commercial Conversion
```

Agent access does not replace enterprise sales, authentication, contractual controls, licensing restrictions, or human decision-making.

Track four metric families:

| Family | Measures |
| --- | --- |
| Discovery | Search visibility, indexed technical pages, agent mentions/citations, share of voice, competitor co-mentions |
| Understanding | Correct product classification, hazard/API identification, incorrect or hallucinated claims |
| Trust | Methodology, provenance, dataset, licence, and limitations retrieval |
| Execution | Documentation visits, API key requests, agent/MCP calls, successful scores, reports, portfolio analyses, conversions |

## 11. Implementation phases

### Phase 1 — Discovery foundation

- [ ] Define canonical positioning.
- [ ] Audit public crawlability and Google, Bing, and Brave visibility.
- [ ] Create a high-intent query benchmark.
- [ ] Benchmark retrieval competitors.
- [ ] Establish a ChatGPT, Claude, Gemini, and Perplexity baseline.

**Outcome:** measurable discovery baseline.

### Phase 2 — Machine-readable trust

- [ ] Publish canonical methodology, data-source registry, provenance, and limitations pages.
- [ ] Link product claims to evidence.
- [ ] Add appropriate structured metadata.
- [ ] Represent model and data versions consistently.

**Outcome:** agents can verify GeoRisk claims.

### Phase 3 — Capability graph

- [ ] Create climate-risk, flood-risk, heat-risk, asset-risk, portfolio-risk, and TCFD reporting pages.
- [ ] Connect pages to API documentation.
- [ ] Connect APIs to methodology and provenance.

**Outcome:** agents can understand what GeoRisk can actually do.

### Phase 4 — Agent execution

- [ ] Define the agent tool contract and evaluate MCP.
- [ ] Wrap existing endpoints for the initial tool surface.
- [ ] Add authentication, rate limits, and audit logging.
- [ ] Test fail-closed behaviour through the agent interface.

**Outcome:** agents can act on GeoRisk rather than merely mention it.

### Phase 5 — Agent distribution benchmark

- [ ] Run the standard prompt suite and record citation and competitor share.
- [ ] Test factual accuracy, API discoverability, and tool execution.
- [ ] Identify retrieval gaps and feed them into the backlog.

**Outcome:** agent distribution becomes measurable and continuously improvable.

## 12. Guardrails

Agent-native distribution must not weaken existing safety and evidence controls.

- Maintain `production_eligible=false` where production eligibility has not been independently established.
- Never present `LIVE_UNVERIFIED` as verified through a page or agent wrapper.
- Do not bypass authentication, entitlements, licence restrictions, provenance requirements, validation, geographic coverage restrictions, or fail-closed behaviour.
- Do not represent decision-support outputs as regulated professional advice.

## 13. Architectural principle

Prefer one core with multiple interfaces:

```text
                  ┌── Human UI
                  │
GeoRisk Core API ─┼── Developer API
                  │
                  └── Agent Interface / MCP
```

Do not create separate human, agent, SEO, and MCP products. There should remain one underlying GeoRisk intelligence engine: the interfaces change; the evidence standard does not.

## 14. Strategic position

GeoRisk should aim to become:

> **A climate and geospatial risk intelligence layer that both humans and AI agents can discover, verify, and execute.**

The stronger competitive position is:

```text
Mentionable → Citable → Verifiable → Callable → Commercially usable
```

The final objective is not **AI SEO**. It is **Agent-Native Distribution**: enabling autonomous and semi-autonomous agents to discover the platform, understand its capabilities and limitations, verify the evidence behind its outputs, and invoke those capabilities through controlled machine interfaces.

## 15. Autonomous publication operating contract

The complete content workflow is weekly evidence harvest → justified bilingual draft → claim ledger
→ B1 provenance, B2 prohibited claims, B3 licence/privacy, B4 schema/link, B5 build/accessibility,
B6 exact-head/security, B7 deployed smoke → safe merge/publication → sitemap, RSS, `llms.txt`,
canonical, hreflang and structured-data validation. Passing all checks is **AUTO-PASS** and requires
no routine editorial approval.

A missing source, unsupported legal conclusion, confidential datum, endorsement/readiness claim,
unverifiable figure, failed check/deploy or unavailable external service is **AUTO-BLOCK**. The topic
is skipped, one deduplicated issue is updated and unrelated content continues. Three consecutive
failures open the lane/topic circuit breaker. Potentially valuable prohibited topics may appear as
an optional Friday decision; external endorsement or regulated claims remain FOUNDER-DECISION.
