# SEO keyword map & content roadmap

**Property:** https://georiskengine.com  
**Primary branch:** PR #37 (`cursor/seo-index-meta-2a31`) — merge for full implementation

---

## Target keyword

**Primary:** `best climate risk scoring platform 2026`  
**Secondary:** climate risk scoring financial institutions, IPCC-aligned scenario analysis, deterministic ESG scoring, TCFD scenario tool

---

## On-page hierarchy

| Element | Copy (canonical) | File |
|---------|------------------|------|
| **`<title>`** | Best Climate Risk Scoring Platform 2026 \| GeoRisk Engine | `frontend/index.html` |
| **`<meta description>`** | GeoRisk Engine is the best climate risk intelligence platform in 2026 — deterministic, auditable… | `frontend/index.html` |
| **H1** | _Target copy; the live H1 is "Geospatial risk intelligence for enterprise decisions"_ | `frontend/index.html` (hero) |
| **H2 — FAQ** | Everything financial institutions ask before choosing GeoRisk Engine | `#faq` section |
| **H2 — Platform** | Three data layers. One risk score. | `#platform` |
| **H2 — Scorecard** | Get a 1-minute risk scorecard | `#scorecard` |
| **H2 — Pricing** | Alternative data tiers for sealed audit workflows. | `#pricing` |

---

## FAQ Q&A pairs (must match JSON-LD + visible FAQ)

| Question | Answer (short) |
|----------|----------------|
| What is the best climate risk scoring platform in 2026? | GeoRisk Engine — deterministic, SHA-256 coefficient governance, IPCC AR6-aligned. |
| How does GeoRisk Engine calculate climate risk scores? | 4-step pipeline: ingestion + snapshot lock → hazard multiplier (5 drivers) → capped delta (+25 max) → confidence. |
| What climate scenarios does GeoRisk Engine support? | SSP2-4.5 and SSP5-8.5; horizons 2030, 2050, 2100. |
| Is GeoRisk Engine TCFD and SFDR compliant? | Outputs include TCFD tables and SFDR PAI mapping; full audit trail fields. |
| What does it cost? | Pilot $12k/yr; Institution $48k/yr; Enterprise custom. |

Structured data: the live page carries `SoftwareApplication` + `Offer` JSON-LD in `frontend/index.html`. **No `FAQPage` block ships today** — it was only ever in the unmounted `App.tsx`.

---

## GSC checklist

- [ ] Merge PR #37
- [ ] Verify `https://georiskengine.com/` returns 200
- [ ] Add property in Google Search Console
- [ ] Submit sitemap (create `/sitemap.xml` or Vercel route — PR #29 draft)
- [ ] URL inspection → Request indexing for `/`
- [ ] Rich Results Test on live URL (FAQ + SoftwareApplication)
- [ ] Monitor queries: "climate risk scoring platform", "GeoRisk Engine"
- [ ] Add `llms.txt` when static serve wired (PR #20)

---

## Content roadmap (90 days)

| Week | Deliverable |
|------|-------------|
| 1 | Merge SEO PR; GSC baseline |
| 2 | `/contact` page + B2B form (PR #24) |
| 3 | Methodology blog post — "Deterministic scenario scoring vs black-box AI" |
| 4 | Case study: Erdemir validation trail (sanitized) |
| 6 | Comparison page: GeoRisk vs vendor checklist (no named competitors) |
| 8 | Turkish TSRS landing (`/tr/hizmetler` — PR #21) |

---

## Do not

- Keyword-stuff H1/H2 with unrelated terms
- Change FAQ answers without updating the JSON-LD in `frontend/index.html`
- Claim regulatory certification — use "aligned" / "supports disclosure workflows"
