# LOI tracker — data partners & Series A

**Status:** Internal · 2026-06-16  
**Registry:** `app/core/data_source_registry.py` · Summary: [georisk_data_source_loi_summary.md](../georisk_data_source_loi_summary.md)

---

## Priority queue

| Partner | Type | Status | Next action |
|---------|------|--------|-------------|
| **Copernicus CDS** | Climate data (ORAS5, ERA5) | Intent | **Get API key today** — see § Copernicus |
| **Tomorrow.io** | Weather / hazard enrichment | Not contacted | **Send LOI email** — see § Tomorrow.io |
| **S&P Global** | Market / ESG crosswalk | Not contacted | Intro via warm path; template § S&P |
| Google Earth Engine | Production GEE | Active (project-bound) | `GEE_PROJECT` in `.env` |
| NASA VIIRS / Landsat | Audit scripts | Active | Operational |

---

## Copernicus CDS — 15-minute setup

1. Register: [https://cds.climate.copernicus.eu/](https://cds.climate.copernicus.eu/)
2. Profile → **API key** → copy UID:APIKEY token
3. Local `.env`:
   ```bash
   CDSAPI_URL=https://cds.climate.copernicus.eu/api
   CDSAPI_KEY=<your-token>
   # Optional — after Analysis Ready Data tab:
   ORAS5_ZARR_URL=<zarr-store-url>
   ```
4. Also set `COPERNICUS_CDS_API_KEY` if using GEO-191 raster (`app/core/config.py`)
5. Smoke: `python3 -m pytest tests/test_raster_access.py -q`
6. Live: `POST /v1/oras5/features` — confirm not `_fallback_features()`

**LOI posture:** Operate under CDS terms; no credentials in repo or docs.

---

## Tomorrow.io — outreach

**Why:** Hourly hazard context + institutional weather API credibility for pilot decks.

**Subject:** `GeoRisk Engine × Tomorrow.io — data partnership LOI (climate risk scoring)`

**Body (adapt):**

> Hi [Name],
>
> I'm building GeoRisk Engine — deterministic, IPCC-aligned climate risk scoring for banks and asset managers (auditable coefficient tables, SHA-256 governance).
>
> We're cataloguing production data partners under formal LOI and would like to explore Tomorrow.io weather/hazard layers as an enrichment input for our Scenario-Lab module (SSP2-4.5 / SSP5-8.5, 2030–2100 horizons).
>
> Proposed scope: non-exclusive LOI, API evaluation tier, joint pilot with 1–2 financial institution design partners in Q3 2026.
>
> Happy to share our data-source registry and methodology one-pager under NDA.
>
> Best,  
> [Founder]

**Follow-up:** Day 5 bump with link to public methodology / scorecard demo.

---

## S&P Global — outreach

**Angle:** SFDR PAI / TCFD scenario tables as downstream export; GeoRisk as deterministic scoring layer.

**Stage:** Wait for Tomorrow.io LOI or bank pilot LOI before cold outreach unless warm intro exists.

**Ask:** Data crosswalk workshop (30 min) + LOI template review.

---

## Series A checklist (LOI → deck)

- [ ] Copernicus CDS key live (ORAS5 or ERA5 path non-fallback)
- [ ] ≥1 signed or verbal LOI (Tomorrow.io or data partner)
- [ ] ≥1 financial institution pilot MOU or paid pilot ($12k tier)
- [ ] GEO-150 + validation API demo recorded
- [ ] 144+ pytest green on `main`
- [ ] PR #37 SEO merged + GSC property verified
- [ ] `coefficient_table_hash` reproducibility demo for auditors

---

## LOI document locations

| Asset | Path |
|-------|------|
| HTML LOI package | `docs/georisk_data_source_loi_package.html` (if present on branch) |
| Validation package | PR #32 |
| API listing | `GET /v1/data-sources` |
