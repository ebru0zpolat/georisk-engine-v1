"""Connector package.

Lazily re-exports the heavier connectors so importing one lightweight submodule
(e.g. ``app.connectors.open_meteo``) does not force optional heavy dependencies
(pandas for ORAS5, earthengine-api for GEE) to import. Attribute access resolves
on demand via PEP 562.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CDSOras5Connector",
    "Oras5PointRequest",
    "GeeConnector",
    "GeePointRequest",
]

_LAZY = {
    "CDSOras5Connector": ("app.connectors.cds_oras5", "CDSOras5Connector"),
    "Oras5PointRequest": ("app.connectors.cds_oras5", "Oras5PointRequest"),
    "GeeConnector": ("app.connectors.gee", "GeeConnector"),
    "GeePointRequest": ("app.connectors.gee", "GeePointRequest"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    import importlib

    return getattr(importlib.import_module(module_name), attr)


def __dir__() -> list[str]:
    return sorted(__all__)
