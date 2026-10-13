"""Golden portfolio loaders (Annex B.6).

Synthetic assets on real geographies — no real customer or personal data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.schemas.portfolio import UniversalAsset
from app.services.portfolio_ingest import parse_portfolio_geojson

GOLDEN_ANTALYA_ID = "golden-antalya-v1"
GOLDEN_ANTALYA_VALUATION_DATE = date(2021, 7, 1)

GOLDEN_ROTTERDAM_PORT_ID = "golden-rotterdam-port-v1"
GOLDEN_ROTTERDAM_PORT_VALUATION_DATE = date(2021, 7, 1)

_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = _ROOT / "data" / "portfolios" / "golden"
ANTALYA_GEOJSON_PATH = GOLDEN_DIR / "antalya_v1.geojson"
ANTALYA_BASELINE_PATH = GOLDEN_DIR / "antalya_v1.baseline.json"
ROTTERDAM_PORT_GEOJSON_PATH = GOLDEN_DIR / "rotterdam_port_v1.geojson"
ROTTERDAM_PORT_BASELINE_PATH = GOLDEN_DIR / "rotterdam_port_v1.baseline.json"


def load_golden_antalya_assets() -> list[UniversalAsset]:
    """Load the Antalya golden portfolio (~100 synthetic RE/tourism assets)."""
    if not ANTALYA_GEOJSON_PATH.is_file():
        raise FileNotFoundError(f"Missing golden portfolio: {ANTALYA_GEOJSON_PATH}")
    raw = ANTALYA_GEOJSON_PATH.read_text(encoding="utf-8")
    portfolio = parse_portfolio_geojson(
        raw,
        valuation_date=GOLDEN_ANTALYA_VALUATION_DATE,
        portfolio_id=GOLDEN_ANTALYA_ID,
    )
    return list(portfolio.assets)


def load_golden_antalya_baseline() -> dict:
    """Load CI regression baseline for the Antalya golden portfolio."""
    if not ANTALYA_BASELINE_PATH.is_file():
        raise FileNotFoundError(f"Missing golden baseline: {ANTALYA_BASELINE_PATH}")
    return json.loads(ANTALYA_BASELINE_PATH.read_text(encoding="utf-8"))


def load_golden_rotterdam_port_assets() -> list[UniversalAsset]:
    """Load Rotterdam port/logistics golden (~100 synthetic collateral assets)."""
    if not ROTTERDAM_PORT_GEOJSON_PATH.is_file():
        raise FileNotFoundError(f"Missing golden portfolio: {ROTTERDAM_PORT_GEOJSON_PATH}")
    raw = ROTTERDAM_PORT_GEOJSON_PATH.read_text(encoding="utf-8")
    portfolio = parse_portfolio_geojson(
        raw,
        valuation_date=GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
        portfolio_id=GOLDEN_ROTTERDAM_PORT_ID,
    )
    return list(portfolio.assets)


def load_golden_rotterdam_port_baseline() -> dict:
    """Load CI regression baseline for the Rotterdam port golden portfolio."""
    if not ROTTERDAM_PORT_BASELINE_PATH.is_file():
        raise FileNotFoundError(f"Missing golden baseline: {ROTTERDAM_PORT_BASELINE_PATH}")
    return json.loads(ROTTERDAM_PORT_BASELINE_PATH.read_text(encoding="utf-8"))


__all__ = [
    "ANTALYA_BASELINE_PATH",
    "ANTALYA_GEOJSON_PATH",
    "GOLDEN_ANTALYA_ID",
    "GOLDEN_ANTALYA_VALUATION_DATE",
    "GOLDEN_DIR",
    "GOLDEN_ROTTERDAM_PORT_ID",
    "GOLDEN_ROTTERDAM_PORT_VALUATION_DATE",
    "ROTTERDAM_PORT_BASELINE_PATH",
    "ROTTERDAM_PORT_GEOJSON_PATH",
    "load_golden_antalya_assets",
    "load_golden_antalya_baseline",
    "load_golden_rotterdam_port_assets",
    "load_golden_rotterdam_port_baseline",
]
