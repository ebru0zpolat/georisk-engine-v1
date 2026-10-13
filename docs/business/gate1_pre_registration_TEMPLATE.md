# Gate 1 Pre-Registration — Scientific Validation Study

> **Purpose:** Satisfies exit criterion **1.2** of [`SIX_MONTH_VALIDATION_GATES.md`](SIX_MONTH_VALIDATION_GATES.md) — sampling frame, inclusion/exclusion rules and analysis plan committed **before** any result is computed.
>
> **Binding rule:** This document must be filled in, frozen and timestamped (§10) **before** the model or baseline is run on the event data. Once the timestamp is set, sections 1–8 are locked. Any change after that point voids Gate 1 and requires a fresh, re-timestamped pre-registration and a new event or held-out data. Compute nothing on the observed-loss data until §10 is signed.

**Study title:** _[short name]_
**Author(s):** _[name(s)]_
**Draft date:** _[YYYY-MM-DD]_
**Status:** ☐ Draft · ☐ Frozen (locked at §10)

---

## 1. Hazard event (criterion 1.1)

| Field | Value |
|-------|-------|
| Hazard type | ☐ Heat · ☐ Flood |
| Event name / description | _[e.g. July 2019 Western Europe heatwave]_ |
| Location(s) / spatial extent | _[bounding box, admin regions, or asset set]_ |
| Event dates (start–end) | _[YYYY-MM-DD – YYYY-MM-DD]_ |
| Why this event | _[real, documented, non-synthetic; relevance to target buyer]_ |
| Event source(s) | _[authoritative record(s) confirming the event occurred]_ |

**Single-event constraint:** exactly one real event is in scope for this study. Additional events require separate pre-registrations.

---

## 2. Data sources

| Role | Dataset | Provider | Version / access date | Provenance note |
|------|---------|----------|-----------------------|-----------------|
| Hazard / model input | _[e.g. ERA5, CORDEX tasmax]_ | _[Copernicus CDS]_ | _[…]_ | _[live vs fallback — must be live]_ |
| Observed-loss (ground truth) | _[dataset]_ | _[provider]_ | _[…]_ | _[see §3 licence]_ |
| Auxiliary / covariates | _[…]_ | _[…]_ | _[…]_ | _[…]_ |

---

## 3. Observed-loss data licence (criterion 1.3)

| Field | Value |
|-------|-------|
| Dataset | _[name]_ |
| Licence type | _[commercial-use terms]_ |
| Licence holder / grant | _[who holds it, reference/ID]_ |
| Commercial use permitted | ☐ Yes · ☐ No |
| Licence artefact location | _[path / link to licence on file]_ |
| Matrix entry | _[link into data-source / LOI licence matrix]_ |

**Gate rule:** if commercial use is not on file, criterion 1.3 is not passable and the study must not proceed on this dataset.

---

## 4. Sampling frame and unit of analysis

| Field | Value |
|-------|-------|
| Population being represented | _[what the single event's sample stands for]_ |
| Unit of analysis | _[asset / grid cell / parcel / admin unit]_ |
| Sampling frame | _[the full set from which units are drawn]_ |
| Sampling method | _[census / random / stratified — with strata]_ |
| Target sample size (n) | _[number, with basis]_ |

---

## 5. Inclusion and exclusion rules

State every rule **now**, before seeing results. Post-hoc exclusions are not permitted.

**Inclusion rules:**
- _[e.g. assets within the event extent with complete hazard + loss records]_

**Exclusion rules:**
- _[e.g. units with >X% missing loss data; units outside licensed coverage]_

**Missing-data handling:**
- _[imputation / listwise deletion / etc. — fixed here]_

**Expected exclusions:** _[rough count/fraction anticipated, to detect surprises later]_

---

## 6. Model, baseline and cutoff (criterion 1.4)

| Field | Value |
|-------|-------|
| Model under test | _[name + methodology version, e.g. expected-loss-v0.3.x]_ |
| Coefficient table / config hash | _[SHA-256 if applicable]_ |
| Named baseline | _[the naive comparator — must be named before results]_ |
| Baseline rationale | _[why this is a fair, defensible naive comparator]_ |
| Information cutoff | _[single cutoff applied identically to model and baseline]_ |
| Cutoff enforcement | _[how leakage past the cutoff is prevented]_ |

**Baseline examples (pick and justify one):** climatological mean; persistence/last-value; simple hazard-threshold rule; published sector loss ratio. The baseline is frozen here and may not be re-chosen after results.

---

## 7. Primary metric and success rule

| Field | Value |
|-------|-------|
| Primary metric | _[e.g. MAE / RMSE / skill score vs baseline]_ |
| Direction of "better" | _[lower / higher]_ |
| Pre-stated success threshold | _[what result would count as beating the baseline]_ |
| Secondary metrics | _[list — reported, not decisive]_ |

**Success rule (one sentence, fixed now):** _[e.g. "Model passes if its RMSE is at least 15% lower than the named baseline's on the included sample under the stated cutoff."]_

---

## 8. Uncertainty and representativeness (criterion 1.5)

| Field | Value |
|-------|-------|
| Uncertainty method | _[bootstrap / analytic CI / etc. — fixed before results]_ |
| Confidence level | _[e.g. 95%]_ |
| Representativeness statement plan | _[how §4 population claim will be evaluated]_ |
| Known limits to declare | _[single event, region, period — what it does NOT represent]_ |

---

## 9. External challenge (criterion 1.6)

| Field | Value |
|-------|-------|
| Independent reviewer | _[name / affiliation]_ |
| Independence basis | _[no stake in outcome]_ |
| Challenge scope | _[event choice, sampling, baseline, metric, uncertainty]_ |
| Report location | _[path once produced]_ |
| Response log | _[link — each material objection answered]_ |

---

## 10. Freeze and timestamp (locks §§1–8)

By signing, the author confirms sections 1–8 are complete and that **no model or baseline result has yet been computed on the observed-loss data**.

| Field | Value |
|-------|-------|
| Frozen by | _[name]_ |
| Freeze timestamp (UTC) | _[YYYY-MM-DDThh:mm:ssZ]_ |
| Commit hash at freeze | _[git commit recording this frozen file]_ |

> Recommended freeze mechanism: fill this file, commit it with message `chore(gate1): freeze pre-registration <study>`, and record the resulting commit hash above in a follow-up commit. The commit timestamp is the auditable freeze point. Only after this may results be computed.

---

## 11. Post-freeze results log (append-only, after §10)

Do not edit §§1–8 below this line. Record deviations honestly; any deviation from the frozen plan is a reportable limitation, not a silent fix.

| Date | Event | Result vs success rule | Deviations from plan | Link |
|------|-------|------------------------|----------------------|------|
| _[…]_ | _[…]_ | _[…]_ | _[…]_ | _[…]_ |
