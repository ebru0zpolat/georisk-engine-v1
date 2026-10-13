"""Guard landing Data Infrastructure claims against the source register."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.core.data_source_registry import DATA_SOURCE_REGISTRY, list_data_sources

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "data-sources.md"
LANDING = ROOT / "frontend" / "index.html"
SPEC = ROOT / "data-claims-spec.md"

EXPECTED_TIER_COUNTS = {
    "production": 3,
    "audit": 4,
    "roadmap": 2,
}

BANNED_LANDING_PHRASES = (
    "We integrate 9 registered data streams",
    "9 registered data streams",
    "reconciled against independent sources",
    "cross-validated for accuracy",
    "30+ authoritative",
    '6hr</span><span class="data-meta-key">Pipeline ingest</span>',
    '6hr</span><span class="data-meta-key">Refresh</span>',
    'Weekly</span><span class="data-meta-key">Pipeline ingest</span>',
)

HEADER_REQUIRED_PREFIX = "Registry catalogs"
HEADER_REQUIRED_COUNT = "9 production, audit and roadmap entries"
HEADER_TIER_BREAKDOWN = "3 production · 4 audit · 2 roadmap"


def _landing_html() -> str:
    return LANDING.read_text(encoding="utf-8")


def _data_section(html: str) -> str:
    match = re.search(
        r'<section id="data">(.*?)</section>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert match, 'landing page missing <section id="data">'
    return match.group(1)


def _parse_data_cards(section: str) -> list[dict[str, str]]:
    """Split on data-card openings so nested </div> tags do not truncate bodies."""
    chunks = re.split(r'<div class="data-card"', section)
    cards: list[dict[str, str]] = []
    for chunk in chunks[1:]:
        attrs_end = chunk.find(">")
        assert attrs_end != -1
        attrs = chunk[:attrs_end]
        body = chunk[attrs_end + 1 :]
        # Drop trailing markup after the card (footnote starts after the grid).
        body = re.split(r'<p class="data-footnote"', body, maxsplit=1)[0]
        tier_m = re.search(r'data-tier="([^"]+)"', attrs)
        reg_m = re.search(r'data-registry-id="([^"]+)"', attrs)
        src_m = re.search(r'data-landing-source="([^"]+)"', attrs)
        name_m = re.search(
            r'<div class="data-source-name">(.*?)</div>',
            body,
            flags=re.DOTALL,
        )
        cite_m = re.search(
            r'<p class="data-source-cite">(.*?)</p>',
            body,
            flags=re.DOTALL,
        )
        assert tier_m, f"data-card missing data-tier: {attrs[:120]}"
        assert src_m, f"data-card missing data-landing-source: {attrs[:120]}"
        assert name_m, "data-card missing data-source-name"
        cards.append(
            {
                "tier": tier_m.group(1),
                "registry_id": reg_m.group(1) if reg_m else "",
                "landing_source": src_m.group(1),
                "name": re.sub(r"\s+", " ", name_m.group(1)).strip(),
                "cite": cite_m.group(1) if cite_m else "",
                "body": body,
            }
        )
    return cards


def test_registry_tier_breakdown() -> None:
    counts = Counter(e.tier for e in DATA_SOURCE_REGISTRY)
    assert len(DATA_SOURCE_REGISTRY) == 9
    assert dict(counts) == EXPECTED_TIER_COUNTS
    for tier, expected in EXPECTED_TIER_COUNTS.items():
        assert len(list_data_sources(tier=tier)) == expected


def test_data_sources_md_table_rows_match_registry() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    assert f"**{len(DATA_SOURCE_REGISTRY)}**" in text
    assert "3 production" in text and "4 audit" in text and "2 roadmap" in text
    row_ids = re.findall(
        r"^\|\s*\d+\s*\|\s*`([a-z0-9_]+)`\s*\|",
        text,
        flags=re.MULTILINE,
    )
    assert len(row_ids) == len(DATA_SOURCE_REGISTRY)
    assert set(row_ids) == {e.id for e in DATA_SOURCE_REGISTRY}
    for entry in DATA_SOURCE_REGISTRY:
        assert f"| {entry.tier} |" in text
        assert entry.id in text


def test_landing_header_is_tier_aware_not_integrate_claim() -> None:
    section = _data_section(_landing_html())
    assert HEADER_REQUIRED_PREFIX in section
    assert HEADER_REQUIRED_COUNT in section
    assert HEADER_TIER_BREAKDOWN in section
    for phrase in BANNED_LANDING_PHRASES:
        assert phrase not in section, f"banned phrase still present: {phrase!r}"


def test_landing_cards_align_with_registry_or_roadmap() -> None:
    section = _data_section(_landing_html())
    cards = _parse_data_cards(section)
    assert len(cards) >= 8, "expected Data Infrastructure cards"

    registry_by_id = {e.id: e for e in DATA_SOURCE_REGISTRY}
    production_ids = {e.id for e in list_data_sources(tier="production")}

    for card in cards:
        tier = card["tier"]
        assert tier in {"production", "audit", "roadmap"}, card
        tag_region = card["body"].split("data-source-name")[0]
        if tier in {"production", "audit"}:
            rid = card["registry_id"]
            assert rid, f"{card['landing_source']} ({tier}) must set data-registry-id"
            entry = registry_by_id.get(rid)
            assert entry is not None, f"unknown registry id {rid}"
            assert entry.tier == tier, f"{rid} tier mismatch: registry={entry.tier} card={tier}"
            assert "Roadmap" not in tag_region
        else:
            assert "Roadmap" in tag_region or "Roadmap" in card["body"]
            if card["registry_id"]:
                entry = registry_by_id[card["registry_id"]]
                assert entry.tier == "roadmap"

    shown_production = {c["registry_id"] for c in cards if c["tier"] == "production"}
    assert shown_production == production_ids


def test_landing_numeric_claims_have_provider_citation_links() -> None:
    section = _data_section(_landing_html())
    cards = _parse_data_cards(section)
    for card in cards:
        assert 'href="http' in card["cite"], (
            f"{card['landing_source']} missing provider citation link"
        )


def test_no_unsupported_optical_pipeline_ingest_or_reconciliation() -> None:
    section = _data_section(_landing_html())
    assert "Pipeline ingest" not in section
    assert "reconciled against" not in section.lower()
    assert "cross-validated" not in section.lower()
    assert "5d / 16d" in section
    assert "Native GSD" in section


def test_data_claims_spec_bans_unimplemented_pipeline_ingest() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "Do not display `PIPELINE INGEST` unless implemented" in spec
    assert "unless a cited methodology page documents the process" in spec


# Affirmative marketing phrases banned page-wide (denials like "no GraphQL" are OK).
BANNED_PAGEWIDE_SUBSTRINGS = (
    "47M+",
    "47M",
    "Locations Indexed",
    "Countries Covered",
    "30+ authoritative",
    "We integrate 30+",
    "<200ms",
    "&lt;200ms",
    "p99 latency",
    "bank-grade",
    "audit-grade",
    "independently validated",
    "AI Risk Scoring",
    "140+ risk factors",
    "45-year hindcast validated",
    "Transformer-based ensemble",
    "REST and GraphQL",
    "REST + GraphQL",
    "GraphQL endpoints",
    "webhook support",
    "Webhooks</button>",
    "Live API credentials in 60 seconds",
    "Real-time risk scores",
    "/v2/score",
    "99.9% uptime SLA",
    "Uptime SLA",
    "api.georiskengine.com",
    "gre_sk_",
)


def test_landing_page_bans_unsupported_performance_and_coverage_claims() -> None:
    html = _landing_html()
    for phrase in BANNED_PAGEWIDE_SUBSTRINGS:
        assert phrase not in html, f"banned marketing phrase still present: {phrase!r}"
    # GraphQL / webhooks may appear only as explicit non-availability statements.
    for line in html.splitlines():
        lower = line.lower()
        if "graphql" in lower:
            assert "no graphql" in lower or "not graphql" in lower, line.strip()
        if "webhook" in lower:
            assert "no webhook" in lower or "not webhook" in lower, line.strip()


def test_landing_hero_states_registry_count_not_fabricated_index() -> None:
    html = _landing_html()
    assert "Technical-validation MVP" in html or "Portfolio climate-risk API" in html
    assert f"{len(DATA_SOURCE_REGISTRY)}" in html
    assert "hash-chained" in html.lower() or "Audit" in html


def _docs_section(html: str) -> str:
    match = re.search(
        r'<section id="docs"(.*?)</section>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert match, 'landing page missing <section id="docs">'
    return match.group(0)


def test_docs_section_is_substantive_and_verified() -> None:
    html = _landing_html()
    section = _docs_section(html)
    assert "api-production-5880.up.railway.app" in section
    assert "/v1/risk/score" in section
    assert "asset_name" in section
    assert "latitude" in section
    assert "longitude" in section
    assert "RATE_LIMIT_EXCEEDED" in section or "429" in section
    assert "413" in section
    assert 'href="/methodology"' in section
    assert 'href="/demo"' in section
    assert "api-production-5880.up.railway.app/docs" in section
    assert 'href="#api"' not in section  # no circular "docs → api only" stub
    assert "api.georiskengine.com" not in section
    assert "gre_sk_" not in section
    assert "Bearer" not in section
    assert "/v2/score" not in section
    # Fixed-nav offset for #docs (and other section anchors)
    assert "scroll-margin-top" in html


def test_api_section_does_not_advertise_unresolved_host_or_fake_auth() -> None:
    html = _landing_html()
    match = re.search(
        r'<section id="api"(.*?)</section>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert match, 'landing page missing <section id="api">'
    api = match.group(0)
    assert "api.georiskengine.com" not in api
    assert "gre_sk_" not in api
    assert "api-production-5880.up.railway.app" in api
    assert "asset_name" in api
