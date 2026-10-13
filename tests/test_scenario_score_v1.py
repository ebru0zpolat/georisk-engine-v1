from __future__ import annotations

from app.scoring.scenario_score import compute_scenario_score, hev_from_components


def test_hev_decomposition_all_sixty() -> None:
    components = {
        "industrial": 60,
        "pollution": 60,
        "land": 60,
        "ocean": 60,
        "agriculture": 60,
        "sensitivity": 60,
    }
    hev = hev_from_components(components)
    assert hev.hazard == 60
    assert hev.exposure == 60
    assert hev.vulnerability == 60


def test_scenario_spread_2050_flood_only() -> None:
    components = {k: 60 for k in ("industrial", "pollution", "land", "ocean", "agriculture", "sensitivity")}
    base = dict(
        asset_id="test",
        model_version="v1.0.3",
        data_snapshot_id="hazard_layers_2026_05",
        baseline_score=60,
        components=components,
        horizon=2050,
        uses_connector_fallback=False,
    )
    ssp245 = compute_scenario_score(**base, pathway="SSP2-4.5", hazards=["flood"])
    ssp585 = compute_scenario_score(**base, pathway="SSP5-8.5", hazards=["flood"])
    assert ssp245.hazard_multiplier == 1.12
    assert ssp585.hazard_multiplier == 1.3
    assert ssp585.scenario_score > ssp245.scenario_score


def test_scenario_reproducibility() -> None:
    components = {k: 50 for k in ("industrial", "pollution", "land", "ocean", "agriculture", "sensitivity")}
    kwargs = dict(
        asset_id="a1",
        model_version="v1.0.3",
        data_snapshot_id="hazard_layers_2026_05",
        baseline_score=50,
        components=components,
        pathway="SSP5-8.5",
        horizon=2050,
        hazards=["heat", "flood"],
        uses_connector_fallback=False,
    )
    assert compute_scenario_score(**kwargs) == compute_scenario_score(**kwargs)
