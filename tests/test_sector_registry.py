"""Registered sector ids and demo preset alignment."""

from __future__ import annotations

from app.core.sector_registry import (
    AGRICULTURE_SECTOR_ID,
    DEFAULT_SECTOR_ID,
    IRON_STEEL_SECTOR_ID,
    REGISTERED_SECTOR_IDS,
    is_sector_registered,
)
from app.services.demo_service import DemoService


def test_default_sector_registered() -> None:
    assert DEFAULT_SECTOR_ID in REGISTERED_SECTOR_IDS
    assert is_sector_registered(DEFAULT_SECTOR_ID) is True


def test_unknown_sector_not_registered() -> None:
    assert is_sector_registered("unregistered_mining") is False


def test_agriculture_registered() -> None:
    assert AGRICULTURE_SECTOR_ID in REGISTERED_SECTOR_IDS
    assert is_sector_registered(AGRICULTURE_SECTOR_ID) is True


def test_iron_steel_registered() -> None:
    assert IRON_STEEL_SECTOR_ID in REGISTERED_SECTOR_IDS
    assert is_sector_registered(IRON_STEEL_SECTOR_ID) is True


def test_demo_presets_use_only_registered_sectors() -> None:
    for asset in DemoService().list_preset_assets():
        assert is_sector_registered(asset["sector"]), asset


def test_demo_includes_iron_steel_preset() -> None:
    ids = {a["id"] for a in DemoService().list_preset_assets()}
    assert "marmara_integrated_steel_mill" in ids
