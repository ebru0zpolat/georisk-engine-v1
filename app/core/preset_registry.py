"""Execution-level preset ids (API ``preset_id``).

Presets select compound driver weights; they are separate from ``sector`` labels.
"""

from __future__ import annotations

DEFAULT_PRESET_ID = "industrial_v1"

REGISTERED_PRESET_IDS: frozenset[str] = frozenset(
    {
        DEFAULT_PRESET_ID,
        "agriculture_v1",
        "transformer_v1",
        "iron_steel_v1",
    }
)


def is_preset_registered(preset_id: str) -> bool:
    return preset_id in REGISTERED_PRESET_IDS


__all__ = ["DEFAULT_PRESET_ID", "REGISTERED_PRESET_IDS", "is_preset_registered"]
