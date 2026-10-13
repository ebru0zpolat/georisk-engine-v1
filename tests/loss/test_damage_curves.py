"""Versioned damage-curve artefact tests."""

from __future__ import annotations

from app.loss.damage_curves import (
    damage_curves_version,
    load_catalogue,
    mean_damage_ratio,
    select_curve,
)


def test_catalogue_is_labelled_synthetic_calibration() -> None:
    cat = load_catalogue()
    assert cat.synthetic is True
    assert "synthetic calibration" in cat.source
    assert cat.catalogue_id.startswith("stub_")
    assert all(c.curve_id.startswith("stub_") for c in cat.curves)


def test_select_curve_prefers_building_and_hazard_match() -> None:
    curve = select_curve(
        building_type="hotel",
        use_class="tourism",
        hazard_id="flood",
    )
    assert curve.curve_id == "stub_mdr_hotel_flood"
    assert curve.version == load_catalogue().version


def test_mean_damage_ratio_monotonic_in_intensity() -> None:
    low, _ = mean_damage_ratio(
        building_type="apartment",
        use_class="residential",
        intensity=0.2,
        hazard_id="flood",
    )
    high, _ = mean_damage_ratio(
        building_type="apartment",
        use_class="residential",
        intensity=0.8,
        hazard_id="flood",
    )
    assert 0.0 <= low < high <= 1.0


def test_damage_curves_version_includes_catalogue_id_and_version() -> None:
    version = damage_curves_version()
    cat = load_catalogue()
    assert version == f"{cat.catalogue_id}-v{cat.version}"
