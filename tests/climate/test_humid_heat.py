"""humid-heat-v1 method core (WO-C05) — docs/specs/humid-heat-indicator-v1.md.

All series here are synthetic arrays built in the test; they exercise the method,
they are not climate data and no value from them leaves the test.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from engine.climate import humid_heat as hh
from engine.climate.humid_heat import (
    DailySeries,
    GridCell,
    HumidHeatError,
    assess,
    count_errors,
    daily_max_tw,
    era5_daily_tw,
    sampling_error,
    saturation_adjust,
    load_thresholds,
    saturation_vapour_pressure_hpa,
    specific_humidity_from_e,
    wet_bulb_c,
    window_indicators,
)

P0 = 101325.0


def _q(t_c: float, rh: float, p_pa: float = P0) -> float:
    e = rh / 100.0 * float(saturation_vapour_pressure_hpa(t_c))
    return float(specific_humidity_from_e(e, p_pa / 100.0))


def _tw(t_c: float, rh: float, p_pa: float = P0) -> float:
    return float(wet_bulb_c(t_c + 273.15, _q(t_c, rh, p_pa), p_pa))


def _stull(t: float, rh: float) -> float:
    """Stull (2011), used only as an independent sanity bound and to document its rejection."""
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


# -- wet-bulb temperature (§4.4) --------------------------------------------


@pytest.mark.parametrize("t_c,rh", [(20.0, 50.0), (25.0, 60.0), (15.0, 80.0)])
def test_tw_agrees_with_stull_in_moderate_conditions(t_c: float, rh: float) -> None:
    assert abs(_tw(t_c, rh) - _stull(t_c, rh)) < 0.4


def test_stull_overestimates_hot_dry_which_is_why_it_is_rejected() -> None:
    assert _stull(45.0, 20.0) - _tw(45.0, 20.0) > 1.0


def test_saturated_air_has_tw_equal_to_t() -> None:
    assert _tw(25.0, 100.0) == pytest.approx(25.0, abs=1e-6)


def test_tw_between_dewpoint_and_dry_bulb_on_a_grid() -> None:
    temps = np.linspace(-5.0, 48.0, 25)
    rhs = np.linspace(2.0, 99.0, 25)
    t, rh = np.meshgrid(temps, rhs)
    e = rh / 100.0 * saturation_vapour_pressure_hpa(t)
    q = specific_humidity_from_e(e, P0 / 100.0)
    tw = wet_bulb_c(t + 273.15, q, np.full_like(t, P0))
    td = hh.dewpoint_c(e)
    assert (tw >= td - 1e-6).all() and (tw <= t + 1e-6).all()


def test_tw_increases_with_humidity() -> None:
    values = [_tw(38.0, rh) for rh in (10, 30, 50, 70, 90)]
    assert values == sorted(values) and len(set(values)) == 5


def test_tw_is_deterministic_bytewise() -> None:
    t = np.linspace(290.0, 318.0, 50)
    q = np.linspace(0.005, 0.025, 50)
    p = np.full(50, P0)
    assert wet_bulb_c(t, q, p).tobytes() == wet_bulb_c(t, q, p).tobytes()


@pytest.mark.parametrize(
    "t,q,p",
    [(np.nan, 0.01, P0), (300.0, 0.0, P0), (300.0, -0.001, P0), (300.0, 0.01, 20000.0), (500.0, 0.01, P0)],
)
def test_nonphysical_input_refuses_with_code(t: float, q: float, p: float) -> None:
    with pytest.raises(HumidHeatError) as err:
        wet_bulb_c(t, q, p)
    assert err.value.code == hh.HUMID_HEAT_INPUT_NONPHYSICAL


def test_supersaturated_input_refuses_out_of_bounds() -> None:
    q_super = _q(30.0, 100.0) * 1.2
    with pytest.raises(HumidHeatError) as err:
        wet_bulb_c(303.15, q_super, P0)
    assert err.value.code == hh.HUMID_HEAT_TW_OUT_OF_BOUNDS


def test_unregistered_blocker_code_cannot_be_raised() -> None:
    with pytest.raises(ValueError):
        HumidHeatError("MADE_UP_CODE", "x")


# -- saturation tolerance (§4.4, decision D3) ----------------------------------


def _q_with_dewpoint(t_k: float, td_k: float, p_pa: float = P0) -> float:
    e = float(saturation_vapour_pressure_hpa(td_k - 273.15))
    return float(specific_humidity_from_e(e, p_pa / 100.0))


def test_dewpoint_within_tolerance_is_treated_as_saturation_and_counted() -> None:
    t = np.array([303.15, 303.15])
    q = np.array([_q_with_dewpoint(303.15, 303.15 + 0.005), _q_with_dewpoint(303.15, 295.0)])
    q_adj, n, max_excess = saturation_adjust(t, q, np.full(2, P0))
    assert n == 1 and max_excess == pytest.approx(0.005, abs=1e-4)
    assert float(wet_bulb_c(t[0], q_adj[0], P0)) == pytest.approx(30.0, abs=1e-6)
    assert q_adj[1] == q[1]


def test_dewpoint_beyond_tolerance_refuses() -> None:
    q = _q_with_dewpoint(303.15, 303.15 + 0.05)
    with pytest.raises(HumidHeatError) as err:
        saturation_adjust(np.array([303.15]), np.array([q]), np.array([P0]))
    assert err.value.code == hh.HUMID_HEAT_TW_OUT_OF_BOUNDS


def _q_with_rh(t_k: float, rh: float, p_pa: float = P0) -> float:
    e = rh * float(saturation_vapour_pressure_hpa(t_k - 273.15))
    return float(specific_humidity_from_e(e, p_pa / 100.0))


def test_model_supersaturation_up_to_110_percent_is_saturation_and_reported() -> None:
    """Decision D4: CMIP6 humidity up to 110 % RH (Bolton) is saturation; count and largest excess are kept."""
    t = np.array([278.15] * 8)  # a cold humid night, where real model output exceeds Bolton saturation
    q = np.array([_q_with_rh(278.15, 1.06)] + [_q_with_rh(278.15, 0.5)] * 7)
    tw, n, max_excess = daily_max_tw(t, q, np.full(8, P0))
    assert n == 1 and 0.5 < max_excess < 1.5
    assert tw[0] == pytest.approx(5.0, abs=1e-6)  # the saturated sample sets Tw = T, the day's maximum


def test_model_supersaturation_above_110_percent_refuses() -> None:
    t = np.full(8, 278.15)
    q = np.array([_q_with_rh(278.15, 1.12)] + [_q_with_rh(278.15, 0.5)] * 7)
    with pytest.raises(HumidHeatError) as err:
        daily_max_tw(t, q, np.full(8, P0))
    assert err.value.code == hh.HUMID_HEAT_TW_OUT_OF_BOUNDS


def test_era5_keeps_its_encoding_tolerance_not_the_model_one() -> None:
    q = _q_with_rh(278.15, 1.06)  # fine for a model sample, far beyond 0.01 K for ERA5
    with pytest.raises(HumidHeatError):
        saturation_adjust(np.array([278.15]), np.array([q]), np.array([P0]))


# -- 3-hourly daily maximum (§4.5, decision D1) --------------------------------


def test_daily_max_from_eight_samples() -> None:
    t = np.tile(np.array([300, 302, 306, 310, 312, 309, 304, 301], float), 2)
    q = np.full(16, 0.015)
    tw, n, max_excess = daily_max_tw(t, q, np.full(16, P0))
    assert tw.shape == (2,) and n == 0 and max_excess == 0.0
    assert tw[0] == pytest.approx(float(wet_bulb_c(312.0, 0.015, P0)), abs=1e-12)


def test_partial_day_of_samples_refuses() -> None:
    with pytest.raises(HumidHeatError) as err:
        daily_max_tw(np.full(12, 305.0), np.full(12, 0.015), np.full(12, P0))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


# -- ERA5 hourly (§4.5, §5) -------------------------------------------------


def _hourly_day(t_max_c: float, td_c: float, n_days: int = 3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hours = np.arange(24)
    t = t_max_c - 8.0 + 8.0 * np.sin(np.pi * (hours - 6) / 12.0).clip(0) + 273.15
    t = np.tile(t, (n_days, 1))
    d = np.full_like(t, td_c + 273.15)
    p = np.full_like(t, P0)
    return t, d, p


def test_era5_true_max_and_sampled_max() -> None:
    t, d, p = _hourly_day(40.0, 24.0)
    true_max, sampled, n = era5_daily_tw(t, d, p, (0, 3, 6, 9, 12, 15, 18, 21))
    assert true_max.shape == sampled.shape == (3,) and n == 0
    # the diurnal peak is at 12 UTC, one of the sample hours
    assert sampled == pytest.approx(true_max, abs=1e-12)
    off_peak = era5_daily_tw(t, d, p, (1, 4, 7, 10, 13, 16, 19, 22))[1]
    assert (off_peak < true_max).all()


def test_era5_missing_hour_refuses() -> None:
    t, d, p = _hourly_day(40.0, 24.0)
    t[1, 5] = np.nan
    with pytest.raises(HumidHeatError) as err:
        era5_daily_tw(t, d, p, (0, 12))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_era5_partial_day_refuses() -> None:
    t, d, p = _hourly_day(40.0, 24.0)
    with pytest.raises(HumidHeatError) as err:
        era5_daily_tw(t[:, :23], d[:, :23], p[:, :23], (0, 12))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


# -- windows and indicators (§7) --------------------------------------------


def _years(start: int, end: int, calendar: str = "standard") -> np.ndarray:
    return np.concatenate([np.full(hh._days_in_year(y, calendar), y) for y in range(start, end + 1)])


def _series(start: int, end: int, base: float, step_per_year: float = 0.0, calendar: str = "standard"):
    years = _years(start, end, calendar)
    doy = np.concatenate([np.arange(hh._days_in_year(y, calendar)) for y in range(start, end + 1)])
    tw = base + 6.0 * np.sin(2 * np.pi * (doy - 100) / 365.0) + step_per_year * (years - start)
    return years, tw


def test_window_indicators_count_exactly() -> None:
    years = _years(2001, 2002)
    tw = np.full(years.shape, 20.0)
    tw[:10] = 31.0  # 10 days in 2001 at exactly the primary threshold
    tw[365:365 + 4] = 35.5  # 4 days in 2002
    out = window_indicators(years, tw, (2001, 2002), thresholds_c=[31.0, 35.0])
    assert out["TwD31"] == 7.0  # (10 + 4) / 2
    assert out["TwD35"] == 2.0  # (0 + 4) / 2
    assert out["TwX"] == round((31.0 + 35.5) / 2, 2)


def test_threshold_file_defines_the_default_counts_and_what_they_do_not_mean() -> None:
    data = load_thresholds()
    assert all(row["does_not_mean"] for row in data["thresholds"])
    years, tw = _series(2001, 2002, 25.0)
    keys = set(window_indicators(years, tw, (2001, 2002)))
    assert {"TwD28", "TwD31", "TwD33", "TwD35"} <= keys


def test_incomplete_year_refuses() -> None:
    years, tw = _series(2001, 2003, 25.0)
    keep = ~((years == 2002) & (np.arange(years.size) % 50 == 0))
    with pytest.raises(HumidHeatError) as err:
        window_indicators(years[keep], tw[keep], (2001, 2003))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_single_year_window_refuses() -> None:
    years, tw = _series(2001, 2002, 25.0)
    with pytest.raises(HumidHeatError) as err:
        window_indicators(years, tw, (2001, 2001))
    assert err.value.code == hh.HUMID_HEAT_WINDOW_INCOMPLETE


def test_noleap_calendar_accepted() -> None:
    years, tw = _series(2000, 2001, 25.0, calendar="noleap")
    assert "TwX" in window_indicators(years, tw, (2000, 2001), calendar="noleap")


# -- gates (§5, §6, §7.4) ---------------------------------------------------


def test_sampling_error_needs_enough_hot_days() -> None:
    true_max = np.full(100, 20.0)
    assert "median_c" not in sampling_error(true_max, true_max)
    true_max[:40] = 30.0
    err = sampling_error(true_max, true_max - 0.5)
    assert err == {"hot_days": 40, "median_c": -0.5, "p95_c": -0.5}


def test_count_errors_measure_each_threshold_on_its_own() -> None:
    years = _years(2001, 2002)
    true_max = np.full(years.shape, 25.0)
    true_max[:40] = 31.5  # 40 true days >= 31
    sampled = true_max.copy()
    sampled[:10] = 30.5  # sampling misses 10 of them
    out = count_errors(years, true_max, sampled, (2001, 2002), thresholds_c=[31.0, 35.0])
    assert out["TwD31"] == {"true_days": 40, "sampled_days": 30, "relative_error": -0.25}
    assert out["TwD35"] == {"true_days": 0, "sampled_days": 0}  # too few true days: unmeasured


def test_sea_cell_refuses_and_land_cell_reports_distance() -> None:
    with pytest.raises(HumidHeatError) as err:
        GridCell(25.0, 55.0, land_fraction=0.3, resolution_deg=0.9375).check(25.2, 55.3)
    assert err.value.code == hh.HUMID_HEAT_SEA_CELL
    info = GridCell(25.0, 55.0, land_fraction=0.8, resolution_deg=0.9375).check(25.0, 56.0)
    assert info["cell_distance_km"] == pytest.approx(100.9, abs=0.5)


THRESHOLDS = [28.0, 31.0]


def _assessment(model_offset: float = 0.0, sampled_shift: float = -0.1, miss_hot: int = 0,
                licence: bool = True) -> dict:
    years_m, tw_m = _series(1991, 2060, 26.0 + model_offset, step_per_year=0.03)
    years_e, tw_e = _series(1991, 2020, 26.0)
    sampled = tw_e + sampled_shift
    if miss_hot:  # sampling drops the first `miss_hot` true Tw >= 31 days below the threshold
        idx = np.flatnonzero(tw_e >= 31.0)[:miss_hot]
        sampled[idx] = 30.9
    model = DailySeries(
        years=years_m, tw_c=tw_m, calendar="standard",
        identity={"model_id": "MPI-ESM1-2-HR", "member_id": "r1i1p1f1", "scenario_id": "ssp585"},
        pressure_source="ps", files=({"file_name": "x.nc", "file_sha256": "0" * 64},), licence_verified=licence,
        sample_hours=(0, 3, 6, 9, 12, 15, 18, 21),
    )
    era5 = DailySeries(years=years_e, tw_c=tw_e, calendar="standard", identity={}, pressure_source="sp",
                       licence_verified=licence)
    return assess(
        asset_lat=25.2, asset_lon=55.3,
        model_cell=GridCell(25.0, 55.0, land_fraction=0.8, resolution_deg=0.9375, orog_m=5.0),
        model=model, era5=era5, era5_sampled_c=sampled, thresholds_c=THRESHOLDS,
    )


def test_record_always_carries_the_recomputation_blocker_and_limitations() -> None:
    rec = _assessment()
    assert hh.HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED in rec["blockers"]
    assert "thermodynamic wet-bulb temperature, not WBGT" in rec["limitations"]
    assert rec["windows"]["2041-2060"]["TwD31"] >= 0.0
    assert rec["refused"] == {}


def test_model_baseline_bias_refuses_absolute_values_but_keeps_change() -> None:
    rec = _assessment(model_offset=1.5)
    assert rec["baseline_bias_c"] > hh.BASELINE_BIAS_LIMIT_C
    assert hh.HUMID_HEAT_MODEL_BASELINE_BIAS in rec["blockers"]
    horizon = rec["windows"]["2041-2060"]
    assert set(horizon) == {"dTwX"}
    assert rec["refused"]["2041-2060:TwX"] == hh.HUMID_HEAT_MODEL_BASELINE_BIAS


def test_count_error_above_limit_refuses_only_that_count() -> None:
    """Decision D2: each threshold count is gated on its own measured count error."""
    rec = _assessment(miss_hot=400)
    err = rec["approx_error"]["counts"]["TwD31"]
    assert err["relative_error"] < -hh.COUNT_ERROR_LIMIT
    horizon = rec["windows"]["2041-2060"]
    assert "TwD31" not in horizon and "TwD28" in horizon and "TwX" in horizon
    assert rec["refused"]["2041-2060:TwD31"] == hh.HUMID_HEAT_APPROX_ERROR_EXCEEDED


def test_temperature_sampling_error_above_limit_refuses_twx_and_p95() -> None:
    rec = _assessment(model_offset=-1.4, sampled_shift=-1.4)  # same shift: no model bias, only sampling error
    horizon = rec["windows"]["2041-2060"]
    assert "TwX" not in horizon and "Tw_dmax_p95" not in horizon
    assert rec["refused"]["2041-2060:TwX"] == hh.HUMID_HEAT_APPROX_ERROR_EXCEEDED


def test_bias_is_measured_against_era5_sampled_like_the_model() -> None:
    rec = _assessment(sampled_shift=-0.5)
    assert rec["baseline_bias_c"] == pytest.approx(
        rec["windows"]["1991-2020"]["TwX"] - rec["era5_baseline_sampled"]["TwX"], abs=0.011)
    assert rec["sampling"]["model_sample_hours_utc"] == [0, 3, 6, 9, 12, 15, 18, 21]


def test_unverified_licence_is_a_named_blocker() -> None:
    assert hh.SOURCE_LICENCE_UNVERIFIED in _assessment(licence=False)["blockers"]


def test_record_never_names_wbgt_or_flood_as_a_quantity() -> None:
    rec = _assessment()
    keys = json.dumps({k: v for k, v in rec.items() if k != "limitations"}).lower()
    assert "wbgt" not in keys and "flood" not in keys


def test_record_is_deterministic() -> None:
    assert json.dumps(_assessment(), sort_keys=True) == json.dumps(_assessment(), sort_keys=True)


# -- agreement with the published Davies-Jones (2008) implementation --------
#
# Reference values computed by subroutine Wet_Bulb of HumanIndexMod (Buzan et al. 2015, the
# Davies-Jones 2008 implementation used in CLM5), github.com/jrbuzan/HumanIndexMod_2020 at
# commit d86e6f23d15fd68a5cb9bf0e61f3d70f6092f447 (2026-09-03), compiled with gfortran, single
# precision. The reference code is GPL-3 and is not part of this repository; only its outputs
# are recorded. Over a 2160-point grid (T 15–50 °C, RH 5–100 %, p 900–1013 hPa) the maximum
# absolute difference was 0.000145 °C — see the spec §4.6.

DAVIES_JONES_REFERENCE = [
    # (T °C, RH %, p Pa, Tw °C from HumanIndexMod)
    (30.0, 50.0, 101325.0, 21.959354),
    (35.0, 75.0, 101325.0, 30.952459),
    (40.0, 60.0, 100000.0, 32.535519),
    (45.0, 40.0, 95000.0, 31.544039),
    (50.0, 45.0, 90000.0, 37.024296),
    (25.0, 100.0, 101325.0, 24.999912),
]


@pytest.mark.parametrize("t_c,rh,p,tw_ref", DAVIES_JONES_REFERENCE)
def test_agrees_with_davies_jones_reference_implementation(t_c: float, rh: float, p: float, tw_ref: float) -> None:
    assert _tw(t_c, rh, p) == pytest.approx(tw_ref, abs=0.001)
