"""Reference / golden portfolios for demos and CI regression."""

from app.portfolios.golden import (
    GOLDEN_ANTALYA_ID,
    GOLDEN_ANTALYA_VALUATION_DATE,
    GOLDEN_ROTTERDAM_PORT_ID,
    GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
    load_golden_antalya_assets,
    load_golden_antalya_baseline,
    load_golden_rotterdam_port_assets,
    load_golden_rotterdam_port_baseline,
)

__all__ = [
    "GOLDEN_ANTALYA_ID",
    "GOLDEN_ANTALYA_VALUATION_DATE",
    "GOLDEN_ROTTERDAM_PORT_ID",
    "GOLDEN_ROTTERDAM_PORT_VALUATION_DATE",
    "load_golden_antalya_assets",
    "load_golden_antalya_baseline",
    "load_golden_rotterdam_port_assets",
    "load_golden_rotterdam_port_baseline",
]
