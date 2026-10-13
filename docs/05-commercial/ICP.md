# Ideal customer profile (ICP) & outreach

**Version:** 2026-06-16  
**Product tiers reference:** pricing section in `frontend/index.html`

---

## ICP (primary)

| Attribute | Target |
|-----------|--------|
| **Industry** | Banking (climate risk / ESG risk), asset management, insurance (P&C climate) |
| **Geo** | EU (SFDR/TCFD), Turkey (TSRS), UK/US expansion |
| **Size** | 500+ monitored physical assets OR $5B+ AUM with climate mandate |
| **Buyer** | Head of Climate Risk, CRO office, ESG investment lead |
| **Pain** | Non-reproducible vendor scores; audit failures on scenario analysis; manual TSRS/TCFD tables |
| **Win theme** | Deterministic scoring — `coefficient_table_version`, `asset_geometry_hash`, `data_snapshot_id` |

**Anti-ICP:** Retail climate apps, pure offset/marketplace, teams wanting black-box AI scores without audit trail.

---

## 50-account strategy

**Tier A (10 accounts)** — Design partners  
EU banks with published TCFD + steel/energy exposure (e.g. institutions already using scenario analysis in annual reports).

**Tier B (20 accounts)** — Asset managers  
SFDR Article 8/9 funds with physical climate KPI in pre-contractual disclosures.

**Tier C (20 accounts)** — Insurers / reinsurers  
P&C with coastal/industrial portfolio concentration in Med, US Gulf, APAC.

**Sourcing:** LinkedIn Sales Navigator, TCFD report PDF mining, SFDR registry, conference attendee lists (RiskMinds, Climate Risk Summit).

---

## 5-touch outreach sequence (full text)

### Touch 1 — LinkedIn connect (Day 0)

> Hi [Name] — I lead GeoRisk Engine, building IPCC-aligned deterministic climate risk scores for [Bank/AM name]-type portfolios. Would value connecting given your work on [specific TCFD/scenario mention from their profile].

### Touch 2 — Value email (Day 2)

**Subject:** Reproducible climate scenario scores (audit-ready)

> [Name],
>
> Quick note: we help institutions replace opaque climate scores with a 4-step deterministic pipeline (hazard multiplier → capped scenario delta +25pts max → full audit trail).
>
> 1-minute indicative scorecard: [demo URL]
>
> Worth 15 minutes to compare against your current scenario tooling?

### Touch 3 — Proof point (Day 7)

> Following up — we benchmark reported TSRS metrics vs independent GeoRisk signals (steel sector Erdemir case, 10-field validation trail). Happy to share the methodology summary under NDA.

### Touch 4 — Pilot offer (Day 14)

> We’re opening 3 Q3 pilot slots ($12k/year, up to 1,000 assets, SSP2-4.5). Includes Scenario-Lab API + validation evidence export. Interested in a technical walkthrough with your risk team?

### Touch 5 — Breakup / redirect (Day 21)

> I’ll pause outreach unless timing improves. If climate scenario reproducibility becomes a 2026 priority, reply “scenario” and I’ll send the coefficient governance one-pager.

---

## Pricing anchors (outreach consistency)

| Tier | Price | Includes |
|------|-------|----------|
| Pilot | $12,000/yr | ≤1,000 assets, SSP2-4.5 |
| Institution | $48,000/yr | 10,000 assets, SSP5-8.5, Scenario-Lab |
| Enterprise | Custom | API SLA, custom coefficients |

Align with the pricing section in `frontend/index.html`.

---

## Collateral to attach

1. One-minute scorecard demo (`#scorecard`)
2. `docs/architecture/scenario-scoring-v1.md` (technical)
3. Validation summary (`data/evidence/erdemir_2024_evidence.md`) — under NDA only
