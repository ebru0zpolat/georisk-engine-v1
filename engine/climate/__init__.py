"""Climate-scenario adapters (CLIM-03 / WP-08).

Canonical import::

    from engine.climate.cmip6_heat_adapter import Cmip6HeatAdapter
"""

from __future__ import annotations

from engine.climate.cmip6_heat_adapter import (
    SUPPORTED_CALENDARS,
    SUPPORTED_UNITS,
    SUPPORTED_VARIABLE,
    Cmip6AdapterError,
    Cmip6HeatAdapter,
)

__all__ = [
    "SUPPORTED_CALENDARS",
    "SUPPORTED_UNITS",
    "SUPPORTED_VARIABLE",
    "Cmip6AdapterError",
    "Cmip6HeatAdapter",
]
