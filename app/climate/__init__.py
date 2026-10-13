"""Compatibility shim — prefer ``engine.climate.cmip6_heat_adapter``."""

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
