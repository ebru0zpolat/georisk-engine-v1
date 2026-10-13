#!/usr/bin/env python3
"""
scripts/crawl_loi_targets.py
============================
LOI target research + competitor intelligence crawler.
Run locally (not in CI — Playwright is too heavy for prod).

Usage:
    pip install -r requirements-dev.txt
    crawl4ai-setup          # first time only
    python scripts/crawl_loi_targets.py

Output:
    data/crawl/<name>.md    — raw markdown per target
    data/crawl/summary.md   — combined, ready to paste into Claude.ai
                              for LOI personalization prompt

GeoRisk boundary:
    This script is ops/research only.
    Never feeds scores. Lives in scripts/, not app/.
    Primary data sources (CDS, GEE) are unaffected.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "crawl"

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

LOI_TARGETS = {
    # Tomorrow.io — primary LOI target this week
    "tomorrow_io_api": "https://www.tomorrow.io/weather-api/",
    # /enterprise/ 404'd; homepage is the current Resilience Platform enterprise pitch
    "tomorrow_io_enterprise": "https://www.tomorrow.io/",
    "tomorrow_io_blog": "https://www.tomorrow.io/blog/",
    # S&P — www.spglobal.com paths hit Akamai; subdomain hub works
    "sp_commodity_insights": "https://commodityinsights.spglobal.com/climate-sustainability-hub.html",
    "sp_press": "https://press.spglobal.com/",
}

COMPETITOR_TARGETS = {
    # Old /our-solutions/.../climate-value-at-risk 404'd; scenario-analysis is the live VaR page
    "msci_climate_var": "https://www.msci.com/data-and-analytics/climate-solutions/climate-data-and-metrics/scenario-analysis",
    "moodys_esg": "https://www.moodys.com/web/en/us/esg/products/climate-risk.html",
}

REGULATORY_TARGETS = {
    # ESMA policy pages are JS-heavy; disclosures hub + EUR-Lex fallbacks
    "esma_sfdr": (
        "https://www.esma.europa.eu/policy-activities/sustainable-finance/"
        "sustainable-finance-disclosures"
    ),
    "tcfd_status": "https://www.fsb-tcfd.org/recommendations/",
    "eu_taxonomy": "https://finance.ec.europa.eu/sustainable-finance/tools-and-standards/eu-taxonomy-sustainable-activities_en",
}

# Fallback URLs tried in order when primary fetch fails or content is junk
TARGET_FALLBACKS: dict[str, list[str]] = {
    "tomorrow_io_enterprise": [
        "https://www.tomorrow.io/weather-intelligence-platform/",
        "https://www.tomorrow.io/solutions/",
    ],
    "sp_commodity_insights": [
        "https://www.spglobal.com/commodityinsights/en/ci/products/climate-and-sustainability-hub.html",
        "https://www.spglobal.com/esg/solutions/company-analytics-climate-analytics",
    ],
    "msci_climate_var": [
        "https://www.msci.com/data-and-analytics/climate-solutions",
        "https://www.msci.com/data-and-analytics/climate-solutions/climate-data-and-metrics",
    ],
    "esma_sfdr": [
        (
            "https://www.esma.europa.eu/policy-activities/sustainable-finance/"
            "sustainable-finance-disclosures-regulation-sfdr"
        ),
        "https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/sfdr",
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019R2088",
    ],
    "moodys_esg": [
        "https://www.moodys.com/web/en/us/capabilities/climate-risk.html",
    ],
}

# Per-target crawl tuning (slow JS hydration, cookie walls, etc.)
TARGET_CRAWL_OVERRIDES: dict[str, dict[str, float | int]] = {
    "moodys_esg": {"delay_before_return_html": 5.0},
    "esma_sfdr": {"delay_before_return_html": 4.0},
}

MIN_CONTENT_CHARS = 500
JUNK_MARKERS = (
    "document not found",
    "page not found",
    "404 error",
    "akamai block",
    "page not found | finance",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _browser_config():
    from crawl4ai import BrowserConfig

    return BrowserConfig(headless=True, enable_stealth=True)


def _crawl_config(name: str | None = None):
    from crawl4ai import CrawlerRunConfig

    kwargs: dict = {
        "remove_overlay_elements": True,
        "word_count_threshold": 15,
        "excluded_tags": ["nav", "footer", "script", "style", "aside"],
        "simulate_user": True,
        "magic": True,
        "page_timeout": 60_000,
        "delay_before_return_html": 2.0,
    }
    if name:
        kwargs.update(TARGET_CRAWL_OVERRIDES.get(name, {}))
    return CrawlerRunConfig(**kwargs)


def _is_usable(markdown: str | None) -> bool:
    if not markdown or len(markdown.strip()) < MIN_CONTENT_CHARS:
        return False
    low = markdown.lower()
    return not any(marker in low for marker in JUNK_MARKERS)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def _fetch_one(crawler, config, url: str) -> str:
    r = await crawler.arun(url=url, config=config)
    if _is_usable(r.markdown):
        return r.markdown or ""
    err = getattr(r, "error_message", None) or "empty or blocked content"
    print(f"      ↳ skip ({err[:80]})")
    return ""


async def crawl_targets(
    crawler,
    targets: dict[str, str],
    label: str,
) -> dict[str, str]:
    """Crawl a dict of {name: url}, return {name: markdown}."""
    results: dict[str, str] = {}
    for name, url in targets.items():
        urls = [url, *TARGET_FALLBACKS.get(name, [])]
        print(f"  [{label}] crawling {name} → {url}")
        markdown = ""
        target_config = _crawl_config(name)
        for attempt_url in urls:
            if attempt_url != url:
                print(f"      fallback → {attempt_url}")
            try:
                markdown = await _fetch_one(crawler, target_config, attempt_url)
                if markdown:
                    print(f"    ✓ {len(markdown):,} chars")
                    break
            except Exception as e:
                print(f"    ✗ error: {e}")
        if not markdown:
            print(f"    ✗ all attempts failed for {name}")
        results[name] = markdown
    return results


def save_results(results: dict[str, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, markdown in results.items():
        if markdown:
            path = OUTPUT_DIR / f"{name}.md"
            path.write_text(markdown, encoding="utf-8")
            print(f"  saved → {path.relative_to(REPO_ROOT)}")


def build_summary(all_results: dict[str, dict[str, str]]) -> str:
    """Build a single markdown file ready to paste into Claude.ai."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# GeoRisk Engine — Crawl Summary\n> Generated: {ts}\n",
        "Paste this into Claude.ai with the prompt at the bottom.\n",
        "---\n",
    ]
    for label, results in all_results.items():
        lines.append(f"## {label}\n")
        for name, markdown in results.items():
            if markdown:
                preview = markdown[:800].strip()
                lines.append(f"### {name}\n```\n{preview}\n...\n```\n")
    lines.append(
        """
---

## Claude.ai Prompt (copy-paste after this file)

You are helping draft a partnership LOI email for GeoRisk Engine (georiskengine.com),
a deterministic climate risk scoring platform for financial institutions (IPCC AR6-aligned,
SHA-256 audit governance, TCFD/SFDR ready).

Using the crawled content above:
1. Identify 2-3 specific things Tomorrow.io is emphasizing right now
   (product launches, enterprise push, SFDR/climate angle, named clients)
2. Write a 3-sentence personalization opening for our LOI email that references
   something specific from their current messaging — not generic flattery
3. Identify any shared regulatory angle (SFDR, TCFD, climate disclosure) we can reference
4. Flag any competitive overlap or positioning risk

Keep it factual, institutional tone. No buzzwords.
"""
    )
    return "\n".join(lines)


async def main() -> int:
    from crawl4ai import AsyncWebCrawler

    print("=== GeoRisk Engine — Crawl4AI Research Runner ===\n")

    browser = _browser_config()
    all_results: dict[str, dict[str, str]] = {}

    async with AsyncWebCrawler(config=browser) as crawler:
        print("[ LOI Targets ]")
        all_results["LOI Targets"] = await crawl_targets(crawler, LOI_TARGETS, "LOI")
        save_results(all_results["LOI Targets"])

        print("\n[ Competitor Targets ]")
        all_results["Competitor Intelligence"] = await crawl_targets(
            crawler, COMPETITOR_TARGETS, "competitor"
        )
        save_results(all_results["Competitor Intelligence"])

        print("\n[ Regulatory Tracker ]")
        all_results["Regulatory Updates"] = await crawl_targets(
            crawler, REGULATORY_TARGETS, "regulatory"
        )
        save_results(all_results["Regulatory Updates"])

    summary = build_summary(all_results)
    summary_path = OUTPUT_DIR / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")
    print(f"\n✓ Summary written → {summary_path.relative_to(REPO_ROOT)}")
    print("  Paste data/crawl/summary.md into Claude.ai Project for LOI drafting.\n")
    return 0


if __name__ == "__main__":
    try:
        import crawl4ai  # noqa: F401
    except ImportError:
        print(
            "crawl4ai not installed. Run: pip install -r requirements-dev.txt && crawl4ai-setup",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(asyncio.run(main()))
