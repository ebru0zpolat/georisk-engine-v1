# Product

## Register

brand

## Users

**Primary:** Institutional risk, ESG, and operations teams at insurance carriers, real-estate investors, infrastructure operators, and public-sector agencies.

**Context:** They evaluate physical assets and portfolios under time pressure — underwriting renewals, acquisition screening, committee packs, regulatory disclosure, or due diligence. They need **location-specific**, **reproducible** signals, not country-level aggregates or black-box scores.

**Secondary:** Sustainability analysts, portfolio managers, and technical evaluators who consume API outputs, sealed audit reports, or demo scorecards before procurement.

## Product Purpose

GeoRisk Engine converts satellite, climate, and geospatial data into **auditable location-based risk intelligence** — composite scores (0–100), component breakdowns, trend context, and board-ready exports tied to traceable `audit_id` metadata.

Success looks like: a buyer can explain *why* a coordinate scored as it did, reproduce the run, and attach outputs to internal models or disclosure workflows without treating satellite proxies as regulatory proof.

The platform is **API-first** (`POST /v1/risk/score`, reports, industrial verification bundles) with a **public marketing surface** (Vercel landing) and **self-serve demo** (React app) as the top-of-funnel proof point.

## Brand Personality

**Precise · Authoritative · Calm**

- Speaks like an intelligence product, not a generic SaaS startup.
- Confidence comes from methodology transparency, audit trails, and conservative legal framing — not hype or urgency theater.
- Technical depth is visible (data sources, baselines, flags) but legible to non-specialists in summaries and reports.

## Anti-references

- Generic **cream / sand SaaS landing pages** with hero metrics, identical feature cards, and tiny uppercase eyebrows on every section.
- **Purple-gradient dark mode**, neon accent overload, decorative glassmorphism, gradient text on headings.
- **"AI made this"** geospatial clichés: globe spinners as the only proof, vague "powered by AI" without data lineage.
- **Regulatory overclaim** — presenting satellite proxies as certified emissions or ground-truth production measurements.
- **Light gray body text on tinted near-white** for "elegance" at the expense of readability.

## Design Principles

1. **Show the lineage.** Every score should trace to sources, baselines, and version metadata — design surfaces make auditability obvious, not buried.
2. **Expert confidence, not sales panic.** Urgency comes from risk substance, not countdown timers or fear-mongering climate imagery.
3. **Practice what you preach.** Public UI quality should match the rigor promised in methodology docs and sealed reports.
4. **Conservative legal framing.** Turkish and English customer-facing copy preserves "decision-support / proxy / not regulatory proof" posture consistently.
5. **One coherent public identity.** Marketing landing (`frontend/index.html`, React demo) carries the dark geospatial intelligence aesthetic; legacy light SaaS shells (`app/static`) are not the design north star.

## Accessibility & Inclusion

- Target **WCAG 2.1 AA** for public marketing and demo surfaces.
- Body text **≥ 4.5:1** contrast against backgrounds; large headings **≥ 3:1**.
- All motion respects **`prefers-reduced-motion: reduce`** — crossfade or instant state changes as fallback.
- Do not rely on color alone for risk bands or flags; pair with labels or patterns.
- Form inputs and demo controls must be keyboard-operable with visible focus states.
