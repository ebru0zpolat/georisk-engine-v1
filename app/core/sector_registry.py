"""Registered ``sector`` ids for product surfaces (demo presets, docs, future weighting).

The Risk API still accepts any non-empty string on ``RiskScoreRequest.sector`` for forward
compatibility; this module is the **single checklist** for first-class supported sectors.
"""

from __future__ import annotations

DEFAULT_SECTOR_ID = "industrial"
AGRICULTURE_SECTOR_ID = "agriculture"
IRON_STEEL_SECTOR_ID = "iron_steel"

# Add new first-class sectors here when presets / methodology / UI ship together.
REGISTERED_SECTOR_IDS: frozenset[str] = frozenset(
    {
        DEFAULT_SECTOR_ID,
        AGRICULTURE_SECTOR_ID,
        IRON_STEEL_SECTOR_ID,
    }
)


def is_sector_registered(sector: str) -> bool:
    return sector in REGISTERED_SECTOR_IDS
