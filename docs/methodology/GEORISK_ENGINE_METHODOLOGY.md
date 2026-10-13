# GeoRisk Engine — Methodology Note

| Field | Value |
|-------|--------|
| **Document version** | `georisk-methodology-v0.4.0` |
| **Status** | Phase A (Real Estate / Mortgage / Commercial Collateral) |
| **Effective date** | 2026-09-04 |
| **Language** | English |
| **Pipeline contract** | `five-layer-eal-v0.4` |
| **Expected-loss formula** | `expected-loss-v0.3` (unchanged) |
| **Damage-curve catalogue** | `stub_global_mdr-v0.2.0` (synthetic) |
| **Adaptation catalogue** | `adaptation-catalogue-v0.2` (synthetic) |
| **Adaptation evidence** | `adaptation-evidence-v0.1` |
| **Calibration label** | `synthetic calibration v0.2` |

**How to cite:** GeoRisk Engine (2026). *Methodology Note* (`georisk-methodology-v0.4.0`). https://github.com/ebru0zpolat/georisk-engine/blob/main/docs/methodology/GEORISK_ENGINE_METHODOLOGY.md

This note is the citable Phase A description of how location-level climate hazards become asset exposure, expected financial loss, and adaptation investment evidence. Formula detail for the financial-translation layer lives in [`app/loss/METHODOLOGY.md`](../../app/loss/METHODOLOGY.md); the reproducibility verifier follows [`tests/verification/METHODOLOGY.md`](../../tests/verification/METHODOLOGY.md).

**v0.3.1 → v0.4.0:** two hazard modules brought into scope **together with their curves**, as §2 has always required: **wildfire** (`wildfire-hazard-v0.1`, climate peril, fire-danger index driver with a labelled ERA5 temperature proxy until a FWI raster is wired) and **earthquake** (`earthquake-hazard-v0.1`, geophysical peril, PGA driver; fail-closed without a seismic source, labelled `SyntheticSeismicSource` for demos). `stub_global_mdr` v0.2.0 adds synthetic wildfire and earthquake curve families (flood / heat rows byte-identical to v0.1.1); the stub hazard path emits four perils (`hazard-stub-v0.2`); the adaptation catalogue v0.2 adds seismic retrofit and defensible space; the horizon fixture carries a climate uplift for wildfire and a **stationary factor of 1.0 for earthquake**. Pipeline contract bumps to `five-layer-eal-v0.4`; `expected-loss-v0.3` arithmetic is unchanged. Golden baselines regenerated. Earthquake is **not a climate hazard** and is reported with `hazard_class: geophysical`; nothing in this version calibrates either peril to observed losses.

**v0.3 → v0.3.1:** documentation amendment only — clarifies that Phase A “EAL” is a scenario damage proxy (not classical annualised expected loss), documents multi-hazard and heat-channel assumptions, separates reproducibility from validation, softens regulatory and independent-verifier claims, and aligns the backtesting programme with active modules (flood / extreme heat). **No change** to `expected-loss-v0.3` arithmetic.

---

## 1. Product scope

GeoRisk Engine converts **asset-level physical climate risk** into **financial impact** and **adaptation evidence** for banks, infrastructure owners, and investors.

It is **not** a climate map product, an ESG reporting SaaS, or a country-specific tool. Hazard visualisation is an input; the product is the five-layer financial and evidence chain.

**P0 vertical (Phase A):** Real estate / mortgage / commercial collateral portfolios (design target 50–500 assets).

**Elevator line:** *From climate maps to financeable adaptation: converting location-level climate hazards into asset exposure, financial loss and investment priorities.*

Binding product directive: [`GEORISK_ENGINE_REPOSITIONING.md`](../../GEORISK_ENGINE_REPOSITIONING.md).

---

## 2. Five-layer pipeline

Every analysis traverses all five layers in order. Skipping a layer is a contract violation.

```
Hazard → Exposure → Vulnerability → Financial translation (EAL) → Adaptation evidence
```

Contract version id: **`five-layer-eal-v0.4`** (`app/schemas/five_layer.py`).

| Layer | Role | Phase A implementation |
|-------|------|------------------------|
| 1. Hazard | Per-hazard intensities \(i_h \in [0,1]\): current required; 2030 / 2050 optional | Deterministic current-only stub intensities keyed by lat/lon + `valuation_date` (`hazard-stub-v0.2`); **active modules: flood, extreme heat, wildfire (climate) and earthquake (geophysical)** — each with a pluggable module under `app/hazards/` and a curve family in the catalogue. Forward horizons are omitted unless a versioned climate-scenario source supplies them |
| 2. Exposure | Asset identity, value \(V\), building type, use class, coordinates | Taken from the uploaded / golden UniversalAsset row |
| 3. Vulnerability | Fragility and adaptation capacity | Deterministic from building type, age, floors, existing measures |
| 4. Financial translation | Scenario damage proxy labelled EAL, scenario horizons, display risk index | **`expected-loss-v0.3`** — see §4 and `app/loss/METHODOLOGY.md` |
| 5. Adaptation evidence | Catalogue measures → cost → risk reduction → avoided loss → residual | **`adaptation-evidence-v0.1`** — see §5 |

`valuation_date` is mandatory. Hazard inputs must not look ahead of that date (Annex B.1).

**Roadmap hazards** (drought, storm, landslide, water stress, etc.) must not be presented as active financial modules until wired with curves and pack data. **Active-module honesty:** wildfire and earthquake became active in v0.4.0 on *synthetic* intensities and curves; "active" means priced end-to-end and independently reproducible, not calibrated. The earthquake module refuses to run without a seismic-hazard source (AFAD TDTH / GEM); demos use a labelled synthetic PGA field. Earthquake intensities are stationary across climate horizons by construction.

---

## 3. Honesty and stub governance

Phase A numbers that are not from a calibrated observational source are labelled:

- catalogue / curve ids with prefix `stub_`, and/or
- field `synthetic: true`, and
- source / badge containing **`synthetic calibration`** (demo badge: `synthetic calibration v0.2`).

Inventory and replacement plans: root [`STUBS.md`](../../STUBS.md).

**Regulated-buyer demos must not use** the SHA-256 seeded `/v1/risk/score` path (`STUBS.md` #3). Demo only the five-layer pipeline (`/v1/portfolio/demo-run*`).

**Coverage:** portfolio aggregation never silently drops rows. Analyzed vs excluded counts and per-row reasons are always returned (`coverage.excluded[]`). Zero analyzable rows → HTTP 422 with the exclusion list.

**Scenario horizons (2030 / 2050):** Horizon losses are calculated only when a hazard module supplies both versioned, horizon-specific intensity maps. Phase A current-only adapters do not manufacture future values. Their demo response and audit parameters stamp `horizon_method: not_available_without_climate_scenario_data` and omit 2030/2050 loss fields. CMIP6/CORDEX, NGFS or another declared climate-scenario source must be integrated before forward-looking outputs are presented.

---

## 4. Expected Annual Loss (`expected-loss-v0.3`)

Canonical formulas, rounding rule, multi-hazard assumptions, and heat-channel limits: [`app/loss/METHODOLOGY.md`](../../app/loss/METHODOLOGY.md).

### 4.1 Phase A meaning of “EAL”

**Phase A EAL is a scenario-conditional damage proxy**, not classical actuarial expected annual loss.

Classical EAL requires at least: (i) annual occurrence / exceedance probabilities, (ii) a severity–frequency relationship, (iii) return-period framing, (iv) integration of the damage curve against a probability measure, (v) scenario and horizon adjustments under that measure, and (vi) separation of direct damage vs business interruption where material. **None of (i)–(vi) are implemented in `expected-loss-v0.3`.**

What *is* implemented:

1. If \(\sum_h i_h = 0\): EAL = 0 (no invented loss).
2. Per-hazard mean damage ratio \(\mathrm{MDR}_h(i_h)\) from the versioned catalogue, where \(i_h\) is a **deterministic intensity index** in \([0,1]\) for a named horizon — **not** an annual rate.
3. Combined damage (independent-peril union, full precision):  
   \(\mathrm{combined\_MDR} = 1 - \prod_h (1 - \mathrm{MDR}_h)\).
4. \(\mathrm{EAL} = \min\bigl(V,\ \mathrm{round}(V \times \mathrm{combined\_MDR} \times \mathrm{vuln},\ 2)\bigr)\) with  
   \(\mathrm{vuln} = \max(0.05,\ \mathrm{fragility}\times(1-\mathrm{adaptation\_capacity}))\).
5. Attribution shares \(i_h / \sum i\) are **informational only** (trail key `attribution_share`).

**MDR → EAL bridge (Phase A):**  
\(\mathrm{MDR}_h\) maps intensity → fractional structural damage; the product with \(V\) and \(\mathrm{vuln}\) yields a **money amount under that intensity scenario**. There is **no** multiplication by event probability and **no** integral over a loss exceedance curve. Callers and demos must not describe this as “true annualised expected loss” until a probability measure is versioned in.

### 4.2 Multi-hazard formula

The union form assumes independent combination of per-hazard MDRs on a shared damage-ratio scale. Scope, correlation gaps, and concurrent/sequential-event limits are normative in `app/loss/METHODOLOGY.md` § “Multi-hazard combination”. Present `combined_MDR` as a **Phase A combined damage ratio under independence**, never as an empirically fitted joint loss model.

### 4.3 Extreme heat

Heat uses the same structural \(\mathrm{MDR}\times V\) channel as flood in Phase A. Heat’s dominant financial channels (energy, productivity, BI, cooling, asset life) are **not** modelled. See `app/loss/METHODOLOGY.md` § “Extreme heat”.

### 4.4 Rounding and display precision

**Rounding:** round once at the output boundary. Intermediate MDR / combined MDR stay full precision; money rounds to cents only when emitted.

Cents-level agreement is a **reproducibility** check (same inputs + versions → same outputs within the rounding policy). It is **not** evidence of predictive accuracy. Prefer stating the policy (“round to 2 decimal places at emit; intermediate full precision”) over marketing phrases such as “accurate to the penny.”

**Formula registry:** live path always uses the latest registered id; replay / verify dispatches on the trail record’s `methodology_version` via `FORMULAS` — never on current defaults.

**Schema note (trail keys):** v0.2: `attribution_weights` (renamed to `attribution_share` in v0.3, semantics unchanged: informational only).

---

## 5. Adaptation evidence (`adaptation-evidence-v0.1`)

For each catalogue measure \(m\):

1. \(\mathrm{cost}_m = \mathrm{round}(V \times \mathrm{cost\_fraction}_m,\ 2)\).
2. Effective reduction = catalogue risk-reduction fraction × hazard-relevance boost (capped at 1).
3. \(\mathrm{avoided\_loss}_m = \mathrm{round}(\mathrm{EAL} \times \mathrm{reduction}_m,\ 2)\).
4. \(\mathrm{residual\_EAL}_m = \max(0,\ \mathrm{EAL} - \mathrm{avoided\_loss}_m)\).
5. Investment priority signal: \(\mathrm{ROI}_m = \mathrm{avoided\_loss}_m / \mathrm{cost}_m\) (when cost > 0).

The recommended measure is the catalogue entry with the highest ROI. Catalogue version is recorded on every audit-trail write (`adaptation_catalogue`).

Measure catalogue artefacts are synthetic in Phase A and must remain labelled as such until replaced by pack-local or empirically calibrated costs/reductions.

---

## 6. Audit trail, reproducibility, and verification

### 6.1 Audit trail

Every successful EAL and adaptation computation appends a **hash-chained** JSONL audit record **before** return (methodology version, data versions, parameters, inputs, outputs, timestamp).

### 6.2 Three distinct claims (do not conflate)

| Claim | Meaning | Phase A status |
|-------|---------|----------------|
| **Reproducibility** | Same inputs + methodology/catalogue versions → same numeric outputs (within rounding policy) | **Implemented** — trail + formula registry + CI |
| **Validation** | Outputs agree with observed losses within declared error metrics | **Not implemented** — programme design in §8; synthetic curves only |
| **Model assurance** | Independent review of methodology, data, controls, and change management | **Target architecture** — Model Validation Pack (Annex B.2), not shipped |

### 6.3 Code-isolated verifier (reproducibility aid)

A **code-isolated** EAL verifier (`tests/verification/independent_eal.py`) recomputes EAL from the methodology note **without importing** `app.loss` or `app.services`. Pipeline formula changes update this note’s referenced EAL section **and** the verifier in the same PR.

This is **not** yet a complete “fully independent validation function.” Code isolation alone does not provide: separate reference specifications beyond this note, sampling design for test cases, coverage ratios, error taxonomy, release-blocking gates on validation failure, or independent human / organisational sign-off. Those are **target controls** for the Model Validation Pack; until then, describe the verifier as a **first-principles reproducibility check**, not as independent model validation.

Demo walkthrough: featured asset trail vs recompute (PASS/FAIL = reproducibility agreement), sample report at [`docs/verification/sample_verification_report.md`](../verification/sample_verification_report.md).

---

## 7. Golden portfolios (Annex B.6)

| Artefact | Path |
|----------|------|
| Antalya portfolio | `data/portfolios/golden/antalya_v1.geojson` (~100 synthetic RE/tourism assets, real Antalya geographies, fictional TRY values) |
| Antalya baseline | `data/portfolios/golden/antalya_v1.baseline.json` |
| Antalya regenerator | `scripts/generate_golden_antalya_portfolio.py` |
| Antalya CI | `tests/portfolios/test_golden_antalya_regression.py` |
| Rotterdam port portfolio | `data/portfolios/golden/rotterdam_port_v1.geojson` (~100 synthetic port/logistics collateral assets, real Rotterdam geographies, fictional EUR values) |
| Rotterdam baseline | `data/portfolios/golden/rotterdam_port_v1.baseline.json` |
| Rotterdam regenerator | `scripts/generate_golden_rotterdam_port_portfolio.py` |
| Rotterdam CI | `tests/portfolios/test_golden_rotterdam_port_regression.py` |

**Valuation date:** `2021-07-01` for both. Intentional methodology / catalogue bumps require regenerating and committing GeoJSON + baseline together. Drift beyond committed tolerances fails CI.

Rotterdam is the Annex B.6 **NL-next** golden for geographic generalisation. It uses the **same** global stub hazard + stub MDR pipeline as Antalya and is **not** pack-nl calibrated (Country Pack loader is Phase B). Both goldens price the four active modules, including a synthetic earthquake and wildfire signal that is a pipeline-transfer test, not a hazard statement about either geography.

---

## 8. Backtesting / historical validation (programme design)

Active hazard modules: **flood**, **extreme heat**, **wildfire** and **earthquake**. Validation events must match that scope, and a module being active does not make an event a backtest until the module runs on real hazard data with calibrated curves.

| Candidate event | Hazard fit | Status |
|-----------------|------------|--------|
| 2021 Western Black Sea floods (Türkiye) | Flood | **In scope** for flood backtesting design |
| Extreme-heat / heatwave episodes with documented asset or productivity losses (TR or pack geography) | Extreme heat | **In scope** — select a documented heat event/dataset; do not substitute wildfire |
| 2021 Manavgat wildfires | Wildfire | **Candidate** — module and curves shipped in v0.4.0; a backtest additionally needs a real fire-danger / burn-scar dataset and WUI loss records. Not citable as a product backtest until then |
| 2023 Kahramanmaraş earthquakes | Earthquake | **Candidate** — module shipped in v0.4.0; a backtest needs AFAD TDTH PGA (or recorded ground motion) and damage-assessment records. Non-climate event; must be reported separately from climate backtests |

Single disaster case studies are **not** sufficient as EAL validation. A backtesting unit must show:

```
pre-event prediction (as-of valuation_date)
  → observed hazard intensity
  → observed damage / loss
  → predicted damage / loss
  → error metric (and taxonomy)
```

with no lookahead leakage. Delivery: versioned Validation Report (Annex B.1) — **not yet produced** for Phase A synthetic curves.

---

## 9. Regulatory evidence posture

Evidence outputs are **intended to support selected physical-risk assessment and evidence requirements** relevant to ECB/EBA supervisory expectations, ESRS E1, EU Taxonomy climate-adaptation assessment, and TSRS 2. **Regulatory coverage remains subject to institution-specific materiality, governance, scenario-analysis and disclosure requirements.**

GeoRisk does **not** claim to be a complete compliance solution for those frameworks. In particular:

- EBA ESG risk guidelines require institution-wide identification, measurement, management and monitoring of ESG risks — an asset loss proxy can supply only selected inputs.
- ESRS E1 covers materiality, strategy, financial effects, policies, actions and targets — not physical risk scores alone.
- ECB climate stress work links climate to credit losses via PD, LGD, collateral and macro channels — Phase A does **not** yet document asset damage → PD/LGD/collateral transfer.
- EU Taxonomy adaptation / DNSH and TSRS 2 need governance and disclosure context beyond EAL.

Preferred public phrasing (English):

> The outputs are intended to support selected physical-risk assessment and evidence requirements relevant to ECB/EBA supervisory expectations, ESRS E1, EU Taxonomy climate-adaptation assessment and TSRS 2. Regulatory coverage remains subject to institution-specific materiality, governance, scenario-analysis and disclosure requirements.

Avoid: “meets / satisfies / complies with ECB, EBA, ESRS, Taxonomy, TSRS” as a product claim.

---

## 10. Versioning policy

Changing a formula or damage curve requires:

1. A **new** frozen function + `FORMULAS` entry (never edit superseded versions), **or** a new catalogue version id.
2. Bumping the relevant methodology / catalogue version constant.
3. Updating this document’s version table and the EAL note / verifier as applicable.
4. Regenerating the golden Antalya baseline when aggregates change.

Document version bumps:

| Document version | Pipeline | Expected loss | Notes |
|------------------|----------|---------------|-------|
| `georisk-methodology-v0.3` | `five-layer-eal-v0.3` | `expected-loss-v0.3` | Combined MDR + EAL ≤ V; round-once; formula registry |
| `georisk-methodology-v0.3.1` | `five-layer-eal-v0.3` | `expected-loss-v0.3` | Scope honesty: scenario proxy EAL; multi-hazard/heat assumptions; reproducibility ≠ validation; regulatory softener; backtesting scope |
| `georisk-methodology-v0.4.0` | `five-layer-eal-v0.4` | `expected-loss-v0.3` | Wildfire + earthquake modules and curves (`stub_global_mdr-v0.2.0`, `hazard-stub-v0.2`, `adaptation-catalogue-v0.2`); earthquake stationary across horizons; goldens regenerated |

Superseded formula versions remain replayable from trail records; see `app/loss/METHODOLOGY.md` for v0.2.

---

## 11. What this note does not claim

- Phase A current-only adapters emit **no 2030/2050 loss values**. Forward-looking outputs require versioned horizon intensity maps from a declared climate-scenario source.
- Phase A hazard intensities and damage curves are **synthetic calibration**, not observationally calibrated physical-risk estimates.
- Phase A “EAL” is **not** classical annualised expected loss under an exceedance distribution.
- Outputs are decision-support evidence, not legal certification, insurance pricing, or regulatory proof / full compliance.
- Country Pack hazard layers and geocoding of address-only rows are roadmap (address-only uploads are excluded with reason until then).
- Credit-risk transfer (PD/LGD/collateral) is out of scope for Phase A.
- Wildfire and earthquake are active modules on synthetic intensities and curves; neither is calibrated to observed losses, and earthquake results are not climate results. Drought, storm and other non-wired perils are not active financial modules.

---

## 12. Evidence gaps before v1.0 / bank pilot

Minimum topics to add or close before calling a release bank-pilot ready:

| # | Topic | Phase A today |
|---|-------|---------------|
| 1 | Data sources and licences | Partial register (`docs/data-sources.md`); expand citations |
| 2 | Spatial resolution and geocoding error tolerance | Not yet specified as product policy |
| 3 | Climate scenarios used (NGFS / SSP / RCP selection) | No forward horizon is emitted from current-only data; a live, versioned CMIP6/CORDEX subset remains required |
| 4 | Historical baseline period | Config default 1991–2020 where applicable; not wired through EAL v0.3 |
| 5 | Return period / event probability approach | **Absent** — see §4.1 |
| 6 | Damage-curve sources and calibration | Synthetic stubs only |
| 7 | Full mathematical EAL definition under a probability measure | Documented as **not yet**; scenario proxy only |
| 8 | Inter-hazard dependence assumptions | Independence disclosed; not estimated |
| 9 | Uncertainty intervals and sensitivity analysis | Phase C (Annex B.3) |
| 10 | Backtesting sample and error metrics | Programme design §8; no completed report |
| 11 | Model change / approval mechanism | Versioning policy §10; org approval process not shipped |
| 12 | Override, exception, and data-quality controls | Partial (coverage exclusions); expand |
| 13 | Asset damage → PD/LGD/collateral transfer | Not modelled |
| 14 | Intended-use / misuse limitations | This §11–12; keep in buyer packs |

---

## 13. Related artefacts

| Artefact | Path |
|----------|------|
| EAL formulas (normative for layer 4) | `app/loss/METHODOLOGY.md` |
| Reproducibility verifier note | `tests/verification/METHODOLOGY.md` |
| Stub inventory | `STUBS.md` |
| Product / architecture directive | `GEORISK_ENGINE_REPOSITIONING.md` |
| Sample verification report | `docs/verification/sample_verification_report.md` |
| Data source register | `docs/data-sources.md` |
| Demo API | `POST /v1/portfolio/demo-run`, `POST /v1/portfolio/demo-run/golden-antalya` |
