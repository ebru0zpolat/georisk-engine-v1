# Humid-heat indicator — method specification v1

- **Status:** Draft. Normative once [ADR-0008](../decisions/ADR-0008-product-family-and-own-indicator-engines.md)
  is accepted. This is the humid-heat part of the WO-C01 method note; WO-C05 implements it and WO-C06 writes the
  independent verifier **from this document alone** (INV-07).
- **Opened:** 2026-10-13
- **Method version:** `humid-heat-v1`
- **Revised:** 2026-10-13, decisions D1–D3 (§5.2) and D4–D5 (§5.4) accepted by the founder after the real-data
  measurements of §5.1 and §5.3.
  `humid-heat-v1` had produced no published output before the revision, so the version label is kept.
- **Changes no readiness flag.** Every output is capped at `NOT_QUALIFIED` until the independent recomputation
  in §9 exists and agrees.

## 1. Why this exists

Percentile-relative heat indices (WSDI, TX90p) measure warming against a location's own past. On the Gulf coast
(Dubai, Abu Dhabi, Doha, Dammam, Kuwait City, Muscat) the material heat driver is the joint effect of temperature
and humidity, and the baseline is already extreme, so a relative index says little about stress on people,
cooling load or outdoor work. ADR-0008 D4 requires a humid-heat index before any GCC heat output can be
presented without a blocker.

## 2. What this indicator is, and is not

It **is** a thermodynamic wet-bulb temperature (Tw) computed from near-surface temperature, specific humidity
and surface pressure, and threshold-day counts over Tw, from sealed public data by a published algorithm.

It **is not**:

- a WBGT. WBGT needs radiation and wind; it is deferred to v2 (§10). No v1 output is labelled WBGT, and no v1
  output is compared with a WBGT threshold (e.g. Qatar's 32.1 °C work-stop rule) as if it were one;
- a mortality, morbidity or labour-productivity estimate;
- a building-level or microclimate value. It is a grid-cell value with stated resolution;
- bias-corrected or downscaled (ADR-0008 D2).

## 3. Inputs

### 3.1 Future and model-baseline series — CMIP6 3-hourly (decision D1)

| Variable | CMIP6 table / name | Units | Use |
|---|---|---|---|
| Near-surface air temperature | `3hr` / `tas` | K | Temperature at each sample time |
| Near-surface specific humidity | `3hr` / `huss` | kg kg⁻¹ (dimensionless 1) | Moisture at each sample time |
| Surface air pressure | `3hr` / `ps` | Pa | Pressure at each sample time |
| Land-area fraction | `fx` / `sftlf` | % | Coastal-cell gate (§6) |
| Surface altitude | `fx` / `orog` | m | Reported |

Each UTC day must hold exactly 8 samples, on whole hours, at the same hours every day; anything else refuses
(`HUMID_HEAT_WINDOW_INCOMPLETE` or `HUMID_HEAT_GRID_MISMATCH`). One exception, found on real files (§5.3):
CMIP6 `3hr` point series run 03:00 to 00:00 (file names such as `201001010300-201501010000`), so the first and
last UTC day of a series are partial. Those two edge days only are trimmed and the trimmed sample count is
reported (`model_edge_samples_trimmed`); a partial day anywhere inside the series refuses. A trimmed day that
falls inside a window makes that year incomplete, so the window refuses. Coordinates of files of the same model
may differ by floating-point noise (1e-14° between MPI-ESM1-2-LR `fx` and `3hr` latitudes); axes equal within
1e-6° are one grid, anything more refuses. The sample hours are reported and are the hours
at which ERA5 is sampled for the §5 gates. Whether a model's `3hr` fields are instantaneous or 3-hour means is
read from the files when they are retrieved and recorded; it is not assumed.

**Daily fields are not used.** The superseded v1 draft paired daily `tasmax` with daily-mean `huss`; §5.1
measured that pairing on real Gulf data and found it undercounts Tw ≥ 31 °C days by 75 % per cell at the
median. Relative humidity (`hurs`) is not used at any frequency.

Licence and integrity follow the existing CLIM-03 contract unchanged: per-file SHA-256, the versioned model
licence allowlist (`engine/climate/cmip6_model_licences_v1.json`), deterministic historical+SSP merge,
complete-year windows, in-domain coordinates only. A model enters this indicator only when **all** of `tas`,
`huss`, `ps` (`3hr`) and `sftlf`, `orog` (`fx`) are published for the same model, member and grid; partial
variable sets refuse (`HUMID_HEAT_VARIABLE_SET_INCOMPLETE`).

**Catalogue check, 2026-10-13** (ESGF search, `esgf-data.dkrz.de`, `latest=true`, `distrib=true`, member
`r1i1p1f1`; experiments historical, ssp245, ssp585 for both models):

| Model | `3hr` published | `day` published (not used) | `fx` published |
|---|---|---|---|
| MPI-ESM1-2-HR | `tas`, `huss`, `ps` | `tasmax`, `huss`, `psl`, `hurs` (no `ps`) | `sftlf`, `orog` |
| MPI-ESM1-2-LR | `tas`, `huss`, `ps` | `tasmax`, `huss`, `psl`, `hurs` (no `ps`) | `sftlf`, `orog` |

The catalogue check confirms publication only; the files themselves are sealed and hashed when retrieved.

### 3.2 Observational baseline — ERA5 hourly

| Variable | ERA5 name | Units |
|---|---|---|
| 2 m temperature | `t2m` | K |
| 2 m dewpoint temperature | `d2m` | K |
| Surface pressure | `sp` | Pa |
| Land–sea mask | `lsm` | 0–1 |

ERA5 is hourly, so it yields a true daily maximum Tw. It is used for the baseline climatology (§7.1), and,
sampled at the model's sample hours, to measure the sampling error (§5) and the model's baseline bias (§7.4).

**Licence.** `engine/climate/era5_licence_v1.json` records ERA5 as CC BY 4.0 with commercial use permitted.
The CDS dataset page's Terms of use state "This dataset is released for use under the CC-BY licence", with the
CC BY 4.0 legal code as the full text (retrieved by the founder, 2026-10-13; `verified: true`). The change from
the earlier Licence to use Copernicus Products took effect on 2 July 2025 (ECMWF announcement). A record whose
ERA5 licence entry is not verified carries `SOURCE_LICENCE_UNVERIFIED`.

**Citation and attribution** (retrieved from the CDS dataset page by the founder, 2026-10-13): users must cite
the CDS catalogue entry (DOI `10.24381/cds.adbb2d47`) and give clear, visible attribution to the Copernicus
programme. The licence record holds the catalogue citation, the data citation (Hersbach et al. 2023) and the
Copernicus notice; every assessment record carries them, with the download date taken from the ERA5
manifest's mandatory `accessed_on` field. A manifest without it refuses.

## 4. Algorithm

### 4.1 Vapour pressure from specific humidity

```latex
e = \frac{q \, p}{\varepsilon + (1 - \varepsilon)\, q}, \qquad \varepsilon = 0.622
```

For ERA5, `e` is the saturation vapour pressure at the dewpoint `d2m` (§4.2 formula evaluated at `d2m`).

### 4.2 Saturation vapour pressure

Bolton (1980) over liquid water, `T` in °C, `e_s` in hPa:

```latex
e_s(T) = 6.112 \, \exp\!\left( \frac{17.67\, T}{T + 243.5} \right)
```

### 4.3 Surface pressure

Taken directly from `ps` (CMIP6 `3hr`) and `sp` (ERA5). The superseded draft's reduction of daily `psl` with
`orog` is no longer used (decision D1).

### 4.4 Wet-bulb temperature

**Definition:** Tw is the temperature, at the parcel's pressure `p`, of the saturated state on the
pseudo-adiabat that carries the parcel's equivalent potential temperature θE. This is the quantity Davies-Jones
(2008), *An efficient and accurate method for computing the wet-bulb temperature along pseudoadiabats*, Monthly
Weather Review 136, approximates.

θE of any state (T in K, p and e in hPa) is Bolton (1980) eq. 39, evaluated through the dry-air potential
temperature at the LCL, θ_DL (Bolton eq. 24), with the mixing ratio `r = 1000 ε e / (p − e)` in g kg⁻¹ and the
lifting-condensation temperature `T_L` from Bolton eq. 22 with relative humidity `U = e / e_s(T)` taken against
§4.2. The same formula is used for the parcel and for the saturated state (`e = e_s(T)`, so `U = 1` and
`T_L = T`), so saturated air returns `Tw = T` exactly:

```latex
T_L = \frac{1}{\dfrac{1}{T - 55} - \dfrac{\ln U}{2840}} + 55,
\qquad
\theta_{DL} = T \left(\frac{1000}{p - e}\right)^{0.2854} \left(\frac{T}{T_L}\right)^{0.28\times10^{-3}\, r},
\qquad
\theta_E = \theta_{DL} \exp\!\left[\left(\frac{3.036}{T_L} - 0.00178\right) r \,(1 + 0.448\times10^{-3}\, r)\right]
```

**Solver:** `θE_sat(x, p) = θE_parcel` solved for `x` by bisection on `[T_d, T]`, exactly 64 halvings, result the
midpoint of the final interval. A fixed step count makes the result deterministic and removes any
convergence branch. Davies-Jones's fast first guess and Newton steps are not used: speed is not a
constraint here, and bisection on the stated definition is simpler to reimplement independently (§9).

**Input range (refuses `HUMID_HEAT_INPUT_NONPHYSICAL`):** non-finite values; T outside 150–350 K; q outside
(0, 0.1) kg kg⁻¹; p outside 300–1100 hPa.

**Rejected:** the Stull (2011) empirical formula. Published comparisons report it overestimates Tw by more than
1 °C at high temperatures — exactly the regime this indicator exists for. It may appear in tests as a sanity
bound, never as an output.

**Physical check:** every computed Tw must satisfy `T_d ≤ Tw ≤ T` (dewpoint ≤ wet-bulb ≤ dry-bulb). A violation
refuses (`HUMID_HEAT_TW_OUT_OF_BOUNDS`); it indicates a unit or input error, not a hot day. A θE target not
bracketed by `[T_d, T]` refuses with the same code.

**Saturation tolerance (decisions D3, D4).** A sample whose dewpoint is above its temperature is treated as
saturated (`e = e_s(T)`, so `Tw = T`) within a source-specific tolerance, and refuses beyond it
(`HUMID_HEAT_TW_OUT_OF_BOUNDS`):

| Source | Tolerance | Why |
|---|---|---|
| ERA5 | `T_d − T ≤ 0.01 K` (D3) | Float32 encoding alone; §5.1 measured at most 0.0004 K |
| CMIP6 | relative humidity against §4.2 `≤ 110 %` (D4) | Model output exceeds Bolton saturation on cold, humid nights (own saturation formulation, ice, fog); §5.3 measured at most 109.5 % RH, 1.29 K |

The number of adjusted samples and the largest excess `T_d − T` are carried in the record per source. Both
tolerances are parameters of the method version.

### 4.5 Daily value

- CMIP6: `Tw_dmax(day) = max` of Tw over the day's 8 three-hourly samples (decision D1).
- ERA5, true: `max` over the day's 24 hourly Tw values.
- ERA5, sampled: `max` over the hourly Tw values at the model's sample hours only (§5, §7.4).

A day with any missing sample refuses its year (§3.1 completeness rule applies).

### 4.6 Agreement with the published Davies-Jones implementation (measured 2026-10-13)

Before any further work, the engine's Tw was compared with subroutine `Wet_Bulb` of HumanIndexMod
(Buzan et al. 2015), the Davies-Jones (2008) implementation used in the Community Land Model 5, at
`github.com/jrbuzan/HumanIndexMod_2020` commit `d86e6f23d15fd68a5cb9bf0e61f3d70f6092f447` (2026-09-03), compiled
with gfortran in single precision. The reference code is GPL-3 and is not part of this repository; six of its
outputs are pinned in `tests/climate/test_humid_heat.py`.

| Grid | Points | Max \|engine − reference\| | In the Tw 31–40 °C band |
|---|---|---|---|
| T 15–50 °C step 1, RH 5–100 % step 5, p ∈ {1013.25, 950, 900} hPa | 2160 | 0.000145 °C | 0.000121 °C (366 points) |

The residual is at the reference's own convergence tolerance (1 × 10⁻⁴ K) and single-precision arithmetic.

The first measurement found a defect, recorded here because it is the reason this section exists: the initial
implementation used Bolton's simpler eq. 43 form of θE while labelling it eq. 39. With eq. 43 the maximum difference
was 0.022 °C, largest at high temperature (−0.010 °C mean in the Tw 35–40 °C band). The pinned reference test fails
with eq. 43, so the defect cannot return silently.

What this establishes: the engine computes the same wet-bulb temperature as the reference Davies-Jones
implementation. What it does not establish: that Davies-Jones Tw computed from daily CMIP6 fields is accurate at an
asset. That is what §5 and §7.4 measure. Davies-Jones (2008) is not calibrated for Tw above 40 °C; the grid above
does not exceed it.

## 5. Measured sampling error (shipped with the number)

Eight samples a day can miss the hour of the true maximum. The error this causes is measured per asset cell, on
the baseline window, from ERA5: the true daily maximum (§4.5, 24 hours) against the daily maximum at the
model's sample hours. Two gates use it.

**Temperature gate — `TwX`, `Tw_dmax_p95`.** The record carries the median and 95th percentile of
`sampled − true` on days with true Tw ≥ 26 °C, and the count of such days. Fewer than 30 such days: both
indicators refuse (`HUMID_HEAT_APPROX_ERROR_UNMEASURED`). Absolute median above 1.0 °C: both refuse
(`HUMID_HEAT_APPROX_ERROR_EXCEEDED`).

**Count gate — each `TwD<t>` on its own (decision D2).** For each threshold the record carries the number of
baseline days at or above it by the true and by the sampled maximum, and their relative difference. Fewer than
30 true days: that count refuses (`HUMID_HEAT_APPROX_ERROR_UNMEASURED`). Relative difference beyond ±20 %: that
count refuses (`HUMID_HEAT_APPROX_ERROR_EXCEEDED`). A temperature gate does not protect a count indicator
(§5.1), so counts are gated on count error and nothing else of §5.

The 1.0 °C and ±20 % limits and the 30-day minimums are parameters of the method version, not validated
tolerances.

### 5.1 Measured on real ERA5 data — Gulf, July–August 2023 (2026-10-13)

**Sample.** ERA5 hourly single levels (`t2m`, `d2m`, `sp`), 2023-07-01 00 UTC to 2023-08-31 23 UTC, area
N 27 / W 50 / S 24 / E 57 at 0.25° (13 × 29 cells: Dammam, Doha, Abu Dhabi, Dubai), NetCDF, downloaded from the
CDS by the founder on 2026-10-13 (date from the file's own `history` attribute). SHA-256
`8f5b97385800933dd9e4f727a87b919c5e14879818ce5aab7557a53b9a65e845`. The file is not in the repository;
`scripts/humid_heat_era5_sample_check.py <file> <sha256>` reproduces every number below. No land–sea mask was
downloaded, so the §6 gate was not exercised on ERA5. Two summer months are a test of the method, not a
climatology: none of the numbers below is a humid-heat-v1 indicator. ERA5 citation and attribution: §3.2.

**Format.** The adapter's readers accept the CDS file unchanged: `valid_time` axis, descending latitude, an
`expver` coordinate, whole contiguous UTC days, all values finite.

**Supersaturation.** 3 of 560,976 cell-hours have `d2m > t2m`, by at most 0.0004 K — the size of float32
encoding error, not a physical state. Under the draft's §4.4 each of those three cells refused entirely; under
decision D3 they are treated as saturation and counted (3 samples, re-run through the engine's own ERA5 path).

**The daily approximation fails where it matters.** Against the hourly daily-maximum Tw on hot days
(true Tw ≥ 26 °C):

| Estimate | Median error | 5th percentile | Cells failing the §5 median gate | Tw ≥ 31 °C day-count error per cell (median / within ±20 %) | Tw ≥ 28 °C (median / within ±20 %) |
|---|---|---|---|---|---|
| Daily: `tasmax` + daily-mean `huss` (superseded draft) | −0.52 °C | −1.80 °C | 25 / 348 | **−75 %** / 0 of 218 | −6 % / 263 of 360 |
| 3-hourly samples, 00–21 UTC (method after D1) | −0.04 °C | −0.52 °C | 0 / 348 | −12 % / 167 of 218 | 0 % / 340 of 360 |

City cells, daily vs 3-hourly median error: Dammam −1.14 / −0.12 °C, Doha −0.55 / −0.14 °C, Abu Dhabi
−0.56 / −0.07 °C, Dubai −0.61 / −0.06 °C. All 2023 daily-maximum Tw at these cells stayed below 32 °C.

Three conclusions, each contradicting an assumption of the superseded draft:

1. The daily pairing is **biased low**, not merely noisy: on the Gulf coast the moist air that sets the daily
   Tw maximum is not captured by a daily-mean humidity.
2. The draft's gate (median error ≤ 1.0 °C) **does not protect threshold counts**: 323 of 348 cells pass it while
   their Tw ≥ 31 °C counts are undercounted by 75 % at the median. A gate on the median temperature error is
   the wrong gate for a count indicator.
3. Both errors undercount risk, which is the unsafe direction for this indicator.

With 3-hourly sampling, Tw ≥ 31 °C counts are still undercounted by 12 % at the median and 51 of 218 cells fall
outside the ±20 % count gate; those cells' `TwD31` refuses rather than being reported low.

### 5.2 Decisions taken from §5.1 (accepted by the founder, 2026-10-13)

| # | Finding | Decision, as implemented |
|---|---|---|
| D1 | Daily pairing undercounts threshold days | CMIP6 3-hourly `tas`, `huss`, `ps` (§3.1); daily maximum Tw = maximum over the 8 samples (§4.5); `psl` reduction removed (§4.3) |
| D2 | Median-error gate does not protect counts | Each threshold count gated on its own measured count error, limit ±20 %, and that error shipped with the count (§5); model bias measured against ERA5 sampled the same way (§7.4) |
| D3 | float32 `d2m > t2m` by < 0.001 K refused whole cells | Excess up to 0.01 K treated as saturation and counted in the record; larger excess refuses (§4.4) |

### 5.3 Measured on real CMIP6 3-hourly files — Gulf, 2010–2014 (2026-10-13)

**Data.** MPI-ESM1-2-LR and MPI-ESM1-2-HR, historical, `r1i1p1f1`, `3hr` `tas`, `huss`, `ps` (files
`*_201001010300-201501010000.nc`) and `fx` `sftlf`, `orog`, subset to the Gulf through CEDA's OPeNDAP service
(LR 22–30°N 48–58°E, 4 × 5 cells; HR 22–30.5°N 46–58°E, 9 × 12 cells). Source file names, their ESGF SHA-256
and the SHA-256 of each subset were recorded at retrieval; the subsets are not in the repository. All three
variables are `time: point` (instantaneous) in both models. ERA5 for the same years was not available, so this
exercises the CMIP6 side end to end; it is not a full assessment (no §5 or §7.4 gate could run).

Retrieval record:

| Model | Variable | Source file | Source SHA-256 (ESGF) | Subset SHA-256 |
|---|---|---|---|---|
| LR | `tas` | `tas_3hr_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `c011396a439640f0… (prefix)` | `5b9e9959fd3363ef21fd7db97e5050348f9b17797d97c99865568d7537dad46c` |
| LR | `huss` | `huss_3hr_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `67e86b70123f153e… (prefix)` | `5a4390b0dfdb9a5766481e87df7ce544391d45e848b919c56cbc52a3d1a24964` |
| LR | `ps` | `ps_3hr_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `c2cf37ac6ee3dc56… (prefix)` | `271e427691a539726a058cb2b7855e9f29d6342a3571daa5e8a123cbc8decc3e` |
| LR | `sftlf` | `sftlf_fx_MPI-ESM1-2-LR_historical_r1i1p1f1_gn.nc` | `92d5f000f84832e9… (prefix)` | `a59fd3c6cd2c9dd4f98a1820cf42e791e18fe4c9c5f0b985bebdd05291a5e911` |
| LR | `orog` | `orog_fx_MPI-ESM1-2-LR_historical_r1i1p1f1_gn.nc` | `a42bffe4c2eb71a3… (prefix)` | `b3f12633768291a2411743613ed1d7a34bec6ed0a4eaf366cdcde9ba89ec6dee` |
| HR | `tas` | `tas_3hr_MPI-ESM1-2-HR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `b7469788ae3401ec148e477b25a53c7d4c6553596d1353f91bb102818efa185c` | `a69130db8605f0ecfba26df54d77e3fef243447a51e580674c29f18949c8ff4b` |
| HR | `huss` | `huss_3hr_MPI-ESM1-2-HR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `050ae3098d8eea3565e2d3ac935b66081b7e446370cf741c6c76bb8cdb9714bb` | `2a22df00f904dc761a1052fef591901ba61192468d6761cd054d575af726066a` |
| HR | `ps` | `ps_3hr_MPI-ESM1-2-HR_historical_r1i1p1f1_gn_201001010300-201501010000.nc` | `3206f477cdef3078e3ca9dbd57693e1dba415bab50fdc6d170ab40603e97bfb3` | `e583fdeabe4746dc3434cd7160dd4319a69a16fa2b2a250edd18bd85ef7c3059` |
| HR | `sftlf` | `sftlf_fx_MPI-ESM1-2-HR_historical_r1i1p1f1_gn.nc` | `8b800dc4d72db2d611c5d39c165b6b13c1b5d6e34e5372b7fb93591e667278b9` | `47e1a37b4e5620d06658b9979ec030f9c2d40ef9271723942c37a952c9baf761` |
| HR | `orog` | `orog_fx_MPI-ESM1-2-HR_historical_r1i1p1f1_gn.nc` | `4d94f21fd0e2ea4126e4ea652d178eeb88f7a1207cb8c0ce26df392f19481dd3` | `7764d3b16e3780ee12ee54e4d5d5993a010915ab852ff6bc3eb0283d68430c6e` |

**What the adapter met, and what changed:**

| Real-file property | Before | After |
|---|---|---|
| `fx` and `3hr` latitudes differ by 1e-14° | Refused as a different grid | One grid within 1e-6° (§3.1) |
| Series run 03:00 → 00:00, so edge days are partial | Refused every series | Edge days trimmed and counted (8 samples per series); inner partial days still refuse |
| `domain` global attribute absent | Refused (identity incomplete) | Unchanged: supplied in the manifest, as for the heat adapter |

**Results at city cells (2011–2014, nearest cell):**

| Location | LR (1.875°) | HR (0.9375°) |
|---|---|---|
| Dammam | Sea cell — refused | Land cell (26.65, 49.69): TwX 29.67 °C, TwD28 9.5 d/yr, TwD31 0 |
| Doha | Land cell (25.18, 50.63), on the Bahrain–Saudi side: TwX 27.11 °C | Sea cell — refused |
| Abu Dhabi | Sea cell — refused | Sea cell — refused |
| Dubai | Sea cell — refused | Refused: dewpoint above temperature by 0.17 K |
| Kuwait City | outside subset | Land cell (29.45, 47.81): TwX 28.78 °C, TwD28 1.75 d/yr |
| Al Ahsa (inland) | Refused: dewpoint above temperature by 0.44 K | Land cell (25.71, 49.69): TwX 29.78 °C, TwD28 7.25 d/yr |

**Supersaturation in model output.** Model `huss` sometimes exceeds saturation as computed by §4.2:

| Model | Samples | Td − T > 0.01 K | > 0.5 K | Max excess | Max RH (Bolton) | Cells with any |
|---|---|---|---|---|---|---|
| LR | 292,160 | 136 | 14 | 0.83 K | 106.0 % | 16 of 20 |
| HR | 1,577,664 | 1,228 | 53 | 1.29 K | 109.5 % | 46 of 108 |

In LR every such sample is in November–April, mostly 21–06 UTC, at −5 to 19 °C: cold, humid nights, where the
model's own saturation formulation (including over ice) and fog differ from Bolton's liquid-water `e_s`. These
samples cannot set a summer Tw maximum, but under §4.4 a single one refuses its cell for every window. Over a
30-year baseline nearly every cell would refuse.

### 5.4 Decisions taken from §5.3 (accepted by the founder, 2026-10-13)

| # | Finding | Decision, as implemented |
|---|---|---|
| D4 | Model supersaturation (≤ 1.29 K, RH ≤ 109.5 %) refused most cells | CMIP6 samples up to 110 % RH (Bolton) are saturation, counted with their largest excess; above 110 % refuses; ERA5 keeps 0.01 K (§4.4) |
| D5 | Gulf-coast cities fall in sea cells, even at 0.9375° | §6 unchanged: the nearest in-domain cell is used and a sea-dominated one refuses. Choosing an inland land cell would understate coastal humidity, the unsafe direction. A finer-resolution source for the coast is a separate decision |

Re-run on the same real subsets after D4: every land cell now passes (LR 15 of 15, HR 82 of 82); only sea cells
refuse (LR 5, HR 26). Samples adjusted to saturation: LR 121, HR 1,230; largest excess 0.82 K and 1.29 K. At
city cells (HR, 2011–2014): Dubai's nearest cell (24.78, 55.31) now passes, TwX 29.40 °C, TwD28 13.0 d/yr, two
samples adjusted (largest excess 0.17 K); Doha and Abu Dhabi refuse as sea cells; Dammam, Al Ahsa and Kuwait City
unchanged.

## 6. Coastal cells

- Each asset is bound to the nearest grid cell **inside the domain** (no edge snap; CLIM-03).
- Reported per asset: grid resolution, distance from asset to cell centre (km), cell land fraction.
- Land fraction below **50 %** (`sftlf < 50`, ERA5 `lsm < 0.5`) refuses (`HUMID_HEAT_SEA_CELL`). A
  sea-dominated cell's humidity is the sea's, not the asset's.
- v1 does not search neighbouring land cells (decision D5, §5.4). Choosing a different cell than the nearest is
  a spatial method change and needs a method-version bump. At 0.9375° (MPI-ESM1-2-HR) Doha and Abu Dhabi
  refuse for this reason (§5.3); a finer-resolution source for coastal assets is a separate, open decision.

## 7. Indicators

All indicators are computed per series (one model, one member, one scenario) and per window: baseline
1991–2020 and horizon windows 2021–2040 and 2041–2060 (ADR-0008 D2; single years forbidden).

### 7.1 Primary

| Id | Definition | Unit |
|---|---|---|
| `TwX` | Window mean of the annual maximum of daily Tw | °C |
| `Tw_dmax_p95` | 95th percentile of daily Tw over the window, linear interpolation between order statistics | °C |
| `TwD31` | Window mean of annual count of days with daily Tw ≥ 31 °C | days yr⁻¹ |

### 7.2 Diagnostic

| Id | Definition | Unit |
|---|---|---|
| `TwD28` | As `TwD31`, threshold 28 °C | days yr⁻¹ |
| `TwD33` | As `TwD31`, threshold 33 °C | days yr⁻¹ |
| `TwD35` | As `TwD31`, threshold 35 °C | days yr⁻¹ |
| `dTwX` | `TwX(horizon) − TwX(model baseline)`, same series | °C |

### 7.3 Thresholds are data, with citations

Thresholds live in a versioned JSON file (`engine/climate/humid_heat_thresholds_v1.json`), each with its source
and what it does **not** mean:

| Threshold | Source as cited in the literature | Does not mean |
|---|---|---|
| 35 °C | Theoretical upper limit of human heat dissipation (Sherwood & Huber 2010; used by Raymond et al. 2020) | A safe level below it |
| 31 °C | Laboratory-measured compensability limit for young, healthy adults, reported at about 30–31 °C (Vecellio et al.) | A limit for the elderly or the working population, which is lower |
| 28 °C, 33 °C | Diagnostic steps for distribution shape | Any physiological or regulatory boundary |

### 7.4 Model-baseline gate (no bias correction)

Absolute counts from a non-bias-corrected model are only as good as the model's humidity and temperature
climate at that cell. Without bias correction (out of scope, ADR-0008 D2), v1 handles this by gating, not
adjusting:

- For each cell, compare the model's `TwX` over 1991–2020 with ERA5's `TwX` over the same window, ERA5 sampled
  at the model's sample hours, so that sampling is not counted as model bias. The true ERA5 `TwX` is also
  reported.
- If `|TwX_model − TwX_ERA5,sampled| > 1.0 °C`, the model's **absolute** indicators (`TwX`, `Tw_dmax_p95`, all `TwD*`)
  refuse for that cell (`HUMID_HEAT_MODEL_BASELINE_BIAS`). The **change** indicator `dTwX` is still reported,
  with the baseline bias attached.
- The baseline bias is reported for every cell, pass or fail.

This is the main design choice that separates this indicator from an un-gated model output: where the model
cannot reproduce the observed humid-heat climate of a place, we do not report its absolute numbers there.

## 8. Refusals (blocker codes to register under WO-08)

| Code | Condition |
|---|---|
| `HUMID_HEAT_VARIABLE_SET_INCOMPLETE` | Any required variable or fixed field missing for the model/member/grid |
| `HUMID_HEAT_UNIT_MISMATCH` | Unit not in the accepted set or inconsistent across files |
| `HUMID_HEAT_GRID_MISMATCH` | Variables on different grids or calendars |
| `HUMID_HEAT_SEA_CELL` | Land fraction < 50 % (§6) |
| `HUMID_HEAT_INPUT_NONPHYSICAL` | Input outside the physical range of §4.4 |
| `HUMID_HEAT_TW_OUT_OF_BOUNDS` | `T_d ≤ Tw ≤ T` violated, supersaturation beyond the source tolerance (ERA5 0.01 K, CMIP6 110 % RH), or θE not bracketed (§4.4) |
| `HUMID_HEAT_WINDOW_INCOMPLETE` | A year in a window is incomplete, a day lacks a sample (CMIP6: 8, ERA5: 24), or a single-year window was requested |
| `HUMID_HEAT_GRID_MISMATCH` (also) | CMIP6 sample times not on whole hours, or not the same hours every day (§3.1) |
| `HUMID_HEAT_APPROX_ERROR_EXCEEDED` | Sampling error above limit: temperature median > 1.0 °C (`TwX`, p95) or count error beyond ±20 % (that `TwD`) (§5) |
| `HUMID_HEAT_APPROX_ERROR_UNMEASURED` | Fewer than 30 baseline hot days (`TwX`, p95) or fewer than 30 true threshold days (that `TwD`) (§5) |
| `HUMID_HEAT_MODEL_BASELINE_BIAS` | Model baseline outside ±1.0 °C of ERA5 (§7.4) |
| `HUMID_HEAT_NOT_INDEPENDENTLY_RECOMPUTED` | Always present until WO-C06's verifier agrees; carries the `NOT_QUALIFIED` cap |
| `SOURCE_LICENCE_UNVERIFIED` | Source not on a verified licence allowlist with commercial use |

Existing CLIM-03 refusals (hash mismatch, incomplete year, non-finite value, out-of-domain coordinate, calendar)
apply unchanged. No refusal is replaced by a fill value (INV-02).

## 9. Independent recomputation (WO-C06)

`tests/verification/independent_humid_heat.py`, standard library only, importing nothing from `engine.` or
`app.`, implements §4–§7 from this document. It agrees with the engine on every count exactly and on every
temperature after rounding to the reported precision of 0.01 °C. (Exact float equality between two
independently written iterative solvers is not a meaningful requirement; agreement at reported precision is.
WO-C06's "byte-for-byte" applies to the reported, rounded values.)

## 10. v2: WBGT (not in v1)

WBGT is what occupational rules and part of the market use (Qatar Ministerial Decision 17 of 2021 stops all
outdoor work above WBGT 32.1 °C year-round; vendor products report days above WBGT 32 °C and 35 °C). It needs
solar radiation, wind and the sun's position at sub-daily resolution:

- **Method:** Liljegren et al. (2008), or the zero-iteration analytic approximation of Kong & Huber (2024),
  reported within 1 °C of Liljegren in 99 % of cases over 93 % of global land.
- **Inputs:** 3-hourly `tas`, `huss`, `ps`, `rsds`, `sfcWind` and cosine of solar zenith angle; only models
  publishing all of them at 3-hourly frequency qualify.
- **Rejected for any output:** simplified shade-only formulas (ABM / ACSM87 / "sWBGT"). Published work reports
  ACSM87 is not an adequate approximation and that the simplified-versus-physical gap grows in a warmer climate.
- v2 needs its own method note and its own entry in this specification series.

## 11. Output record (per asset, series, window)

`method_version`, `algorithm`, `dataset_id`, `model_id`, `member_id`, `scenario_id`,
`window`, file SHA-256s (`algorithm` = `bolton1980-eq39-thetae-pseudoadiabat-bisection`), licence ids, `grid_resolution_deg`, `cell_distance_km`, `cell_land_fraction`,
`pressure_source` (`ps`), `orog_m`, `sampling` (model sample hours UTC, edge samples trimmed,
saturation-adjusted sample counts and largest excess per source, tolerances), the §7 indicators, `era5_baseline` and `era5_baseline_sampled`, `approx_error`
(`temperature` and per-threshold `counts`, §5), `baseline_bias_c` (§7.4), `refused`, `blockers[]`,
`limitations[]` (always including: single model/member, no bias correction, grid-cell value, CMIP6 daily maximum
from 8 samples, not WBGT), the ERA5 licence record with citations and attribution (§3.2). The claim state is
carried by the blockers until WO-C07 wires the claim algebra.

## Appendix A — How others compute humid heat (market scan, 2026-10-13)

Sources are search results; the primary pages could not be opened from the build environment, and vendor
methodology documents were mostly not public. Treat every row as "reported", not verified.

| Producer | What is reported | Method disclosed? |
|---|---|---|
| Jupiter Intelligence (ClimateScore Global) | Days above WBGT 32 °C ("high") and 35 °C ("dangerously high"); also days above 35 °C / 38 °C air temperature, heating/cooling degree days; custom thresholds | WBGT formula not found in public material |
| First Street (US only) | Heat index ("feels like"); a property's local hottest 7 days and how many such days occur 30 years out; 30 m land-surface-temperature model; RCP 4.5 | Model described at overview level |
| ClimateCheck (US) | Combines dry-bulb and wet-bulb extreme-heat day counts into a 1–100 rating | Overview only |
| CarbonPlan (open research) | WBGT in the shade with a post-hoc sun adjustment; states shade WBGT understates impacts | Open |
| Academic CMIP6 dataset (Scientific Data, 2025) | Bias-corrected, 16 models, 0.25°, 3-hourly Tw and WBGT across 1–4 °C warming levels; Tw by Davies-Jones; notes Stull overestimates by > 1 °C at high temperature | Open |
| Moody's / XDI / MSCI / S&P / Climate X | — | No public humid-heat methodology found |

What this specification does that the scan did not find elsewhere: the algorithm is named and public; the
sampling error of every indicator, counts included, is measured per cell against hourly data and shipped; sea-dominated coastal cells refuse; and absolute
values refuse where the model cannot reproduce the observed baseline.

### Sources (search results, 2026-10-13)

- Scientific Data (2025), global bias-corrected CMIP6 heat-stress dataset: https://www.nature.com/articles/s41597-025-04527-6
- PNAS (2023), lower empirically determined moist-heat tolerance: https://www.pnas.org/doi/10.1073/pnas.2305427120
- Arabian Peninsula present and future wet-bulb temperatures (ERL): https://iopscience.iop.org/article/10.1088/1748-9326/ac507c
- Raymond et al. (2020), Science Advances: https://pmc.ncbi.nlm.nih.gov/articles/PMC7209987
- Kong & Huber (2024), zero-iteration WBGT, GeoHealth: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GH001068
- Simplified vs physics-based WBGT in a warmer climate (WCE 2024): https://www.sciencedirect.com/science/article/pii/S2212094724000380
- Brimicombe et al. (2023), WBGT on a global grid: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9941479/
- CarbonPlan extreme-heat explainer: https://carbonplan.org/research/extreme-heat-explainer
- thermofeel (ECMWF, Apache-2.0): https://thermofeel.readthedocs.io/
- Jupiter Intelligence megaprojects analysis: https://www.jupiterintel.com/blog/us-megaprojects-climate-change-threatens-americas-manufacturing-boom
- PwC UK / Jupiter physical climate analytics: https://www.pwc.co.uk/services/sustainability-climate-change/insights/physical-climate-analytics-tool-powered-by-jupiter-intelligence.html
- First Street Heat Factor methodology: https://help.firststreet.org/hc/en-us/articles/7928501959447-The-methodology-behind-the-model-used-by-Heat-Factor
- ClimateCheck wet-bulb vs dry-bulb: https://climatecheck.com/risks/heat/web-bulb-vs-dry-bulb-temperature-measurements
- ILO on Qatar's heat-stress decision: https://www.ilo.org/resource/qatars-ministerial-decision-heat-stress
- CEDA record, MPI-ESM1-2-HR variables and frequencies: https://catalogue.ceda.ac.uk/uuid/348138bb004242238bfc6979e8b8e55f/
