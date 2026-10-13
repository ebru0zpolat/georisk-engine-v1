# Crawl4AI — GeoRisk Engine Ops Recipes

> `scripts/crawl_loi_targets.py` · `data/crawl/` · NOT in CI · NOT in `app/`

---

## What it is

Async Python web crawler (Playwright-based). Produces LLM-ready markdown.
68K GitHub stars. `pip install crawl4ai && crawl4ai-setup`.

## Boundary Rule

- Lives in `scripts/` only — never in `app/`
- Never feeds risk scores. Ops/research tool.
- Primary data (CDS, GEE, ERA5) are unaffected
- Add to `requirements-dev.txt`, not `requirements.txt`
- Do NOT add to CI — Playwright browser download is too heavy

---

## 5 Use Cases → Repo Mapping

### 1. LOI Target Research (this week)

Run `scripts/crawl_loi_targets.py` → `data/crawl/summary.md`  
Paste summary into Claude.ai: *"Extract SFDR/TCFD angle for LOI personalization"*

Targets: `tomorrow.io/weather-api/`, `tomorrow.io/` (enterprise), S&P Climate Hub

### 2. Competitor Intelligence (weekly)

Same script, `--competitors` flag  
Output → `docs/04-investor/` context for "Best 5" list maintenance  
Claude.ai prompt: *"What changed vs last week? Update our competitive positioning."*

### 3. Regulatory Change Tracker (weekly cron — future)

Targets: ESMA SFDR page, FSB-TCFD, EU Taxonomy  
Diff markdown vs previous crawl → if delta > threshold → open Linear issue via MCP  
Future: GitHub Action on schedule

### 4. Erdemir / TSRS Company Reports (GEO-125)

Borsa Istanbul + CDP company pages → sustainability report PDFs  
Feed to `app/validation/` pipeline (pdf-reading skill in Claude.ai for extraction)  
Covers: Aksa, Kardemir, Petkim, Çimsa, Akçansa

### 5. Competitor llms.txt audit (SEO)

Crawl `msci.com/llms.txt`, `spglobal.com/llms.txt` etc. (most won't exist)  
Compare to our `frontend/public/llms.txt` → identify gaps

---

## Anti-bot Config (use this always)

```python
from crawl4ai import BrowserConfig, CrawlerRunConfig

BROWSER_CFG = BrowserConfig(headless=True, enable_stealth=True)
CRAWL_CFG = CrawlerRunConfig(
    remove_overlay_elements=True,   # kills cookie banners
    word_count_threshold=15,        # removes nav/footer noise
    excluded_tags=["nav", "footer", "script", "style", "aside"],
    simulate_user=True,             # human-like timing
    magic=True,                     # stealth mode
    page_timeout=60_000,
    delay_before_return_html=2.0,
)
```

### URL notes (verified 2026-06)

| Target key | Primary URL | Notes |
|------------|-------------|-------|
| `tomorrow_io_enterprise` | `https://www.tomorrow.io/` | `/enterprise/` returns 404; fallbacks: platform + solutions |
| `sp_commodity_insights` | `commodityinsights.spglobal.com/.../climate-sustainability-hub.html` | `www.spglobal.com` paths often Akamai-blocked |
| `msci_climate_var` | `.../climate-data-and-metrics/scenario-analysis` | old `/our-solutions/.../climate-value-at-risk` 404 |
| `esma_sfdr` | `.../sustainable-finance-disclosures` | regulation-sfdr page is flaky; EUR-Lex CELEX fallback |

## Known Blocked Domains (cloud agent environments)

Running from restricted cloud egress → many partner sites fail.  
Run `scripts/crawl_loi_targets.py` **locally** in the repo, not via cloud agents.

| Domain | Status |
|--------|--------|
| tomorrow.io | Often blocked (egress) + anti-bot 403 |
| docs.tomorrow.io | Often blocked (egress) |
| spglobal.com | Check robots.txt before crawling |
| msci.com | Check ToS |

---

## Workflow: LOI Research

```bash
# In repo root, locally:
pip install -r requirements-dev.txt
crawl4ai-setup          # one time

python scripts/crawl_loi_targets.py
# → data/crawl/tomorrow_io_api.md (and other targets)
# → data/crawl/summary.md

# Then paste summary.md into Claude.ai Project with the prompt at the bottom of the file
```

Runs **LOI + competitor + regulatory** targets in one pass (no flags).

---

## .gitignore

Crawl output under `data/crawl/` is gitignored (except `.gitkeep`).
