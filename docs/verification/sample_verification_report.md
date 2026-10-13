# EAL reproducibility verification report

- **Generated (UTC):** 2026-08-05T14:32:51.112263+00:00
- **Commit / seed SHA:** `1c37037fba2f3474b50503a5ffe314f368621ff9`
- **Portfolio:** `verification-v1`
- **Assets verified:** 5
- **Shared catalogue:** `stub_global_mdr` v0.1.0
- **Methodology:** `tests/verification/METHODOLOGY.md` (expected-loss-v0.3)

Each page below recomputes the Phase A scenario damage proxy (labelled EAL) from trail inputs and the curve catalogue using the **code-isolated** verifier (no shared code with the pipeline). **PASS = reproducibility** within the cents rounding policy — not observational validation of model accuracy.

---

# Asset `vf-005-industrial`

- **Valuation date:** 2024-12-31
- **Asset value:** 3,500,000.00
- **Building / use:** industrial / industrial
- **Curve catalogue (pipeline = verifier):** `stub_global_mdr` v0.1.0 (synthetic calibration)
- **Record catalogue params:** `stub_global_mdr` v0.1.0
- **Catalogue path:** `/Users/macbookpro/Projects/georisk-engine/app/loss/curves/stub_global_mdr_v0.1.json`
- **Trail record id:** `atr_7a9cebfc21a5494cb337749194d37d76`
- **Trail record hash:** `d8f3cf1031030bc58aecf5d166ed4da8e12728503d5f78c6c80af692d5749295`
- **Agreement:** PASS

## Vulnerability

`vuln = max(0.05, 1.0 × (1 − 0.2)) = 0.8`

## Current-climate hazard steps

- **Combined MDR:** 0.497068

| Hazard | Intensity | Curve id | Exponent | Scale | MDR | Attribution share (info) | Notional loss |
|---|---:|---|---:|---:|---:|---:|---:|
| flood | 0.42 | `stub_mdr_industrial_flood` | 1.25 | 0.9 | 0.304302 | 0.43299 | 852,045.60 |
| extreme_heat | 0.55 | `stub_mdr_industrial_extreme_heat` | 1.25 | 0.585 | 0.277083 | 0.56701 | 775,832.40 |

### Per-hazard formulas

- **flood:** `notional 3500000.0 × 0.304302 × 0.8` → loss **852,045.60** (curve `stub_mdr_industrial_flood`, catalogue v0.1.0)
- **extreme_heat:** `notional 3500000.0 × 0.277083 × 0.8` → loss **775,832.40** (curve `stub_mdr_industrial_extreme_heat`, catalogue v0.1.0)

## Results

| Field | Pipeline | Independent |
|---|---:|---:|
| EAL absolute | 1391790.4 | 1391790.4 |
| EAL % value | 39.76544 | 39.76544 |
| EAL 2030 | 1619688.0 | 1619688.0 |
| EAL 2050 | 2013494.0 | 2013494.0 |

**Independent EAL:** 1,391,790.40 (39.76544% of value)
**Pipeline EAL:** 1,391,790.40 (39.76544% of value)

---

# Asset `vf-006-residential`

- **Valuation date:** 2024-12-31
- **Asset value:** 320,000.00
- **Building / use:** residential / residential
- **Curve catalogue (pipeline = verifier):** `stub_global_mdr` v0.1.0 (synthetic calibration)
- **Record catalogue params:** `stub_global_mdr` v0.1.0
- **Catalogue path:** `/Users/macbookpro/Projects/georisk-engine/app/loss/curves/stub_global_mdr_v0.1.json`
- **Trail record id:** `atr_945908ea834646a88905f84df8881171`
- **Trail record hash:** `f7a86b46c7e1901fe6b76623f038f01212cbdf38159566e349da8ed34a584d2b`
- **Agreement:** PASS

## Vulnerability

`vuln = max(0.05, 1.0 × (1 − 0.0)) = 1.0`

## Current-climate hazard steps

- **Combined MDR:** 0.334914

| Hazard | Intensity | Curve id | Exponent | Scale | MDR | Attribution share (info) | Notional loss |
|---|---:|---|---:|---:|---:|---:|---:|
| flood | 0.5 | `stub_mdr_residential_flood` | 1.45 | 0.72 | 0.263535 | 0.666667 | 84,331.20 |
| storm | 0.25 | `stub_mdr_default_storm` | 1.4 | 0.675 | 0.096921 | 0.333333 | 31,014.72 |

### Per-hazard formulas

- **flood:** `notional 320000.0 × 0.263535 × 1.0` → loss **84,331.20** (curve `stub_mdr_residential_flood`, catalogue v0.1.0)
- **storm:** `notional 320000.0 × 0.096921 × 1.0` → loss **31,014.72** (curve `stub_mdr_default_storm`, catalogue v0.1.0)

## Results

| Field | Pipeline | Independent |
|---|---:|---:|
| EAL absolute | 107172.48 | 107172.48 |
| EAL % value | 33.4914 | 33.4914 |
| EAL 2030 | 131531.2 | 131531.2 |
| EAL 2050 | 171544.64 | 171544.64 |

**Independent EAL:** 107,172.48 (33.4914% of value)
**Pipeline EAL:** 107,172.48 (33.4914% of value)

---

# Asset `vf-007-hotel-inland`

- **Valuation date:** 2024-12-31
- **Asset value:** 1,800,000.00
- **Building / use:** hotel / tourism
- **Curve catalogue (pipeline = verifier):** `stub_global_mdr` v0.1.0 (synthetic calibration)
- **Record catalogue params:** `stub_global_mdr` v0.1.0
- **Catalogue path:** `/Users/macbookpro/Projects/georisk-engine/app/loss/curves/stub_global_mdr_v0.1.json`
- **Trail record id:** `atr_e66e4281946e4a2093f5eb4a268e27f3`
- **Trail record hash:** `aa6803610ffd2caae9c6bbd84607704f830449831fe2fa6b7a794d648a072454`
- **Agreement:** PASS

## Vulnerability

`vuln = max(0.05, 0.9 × (1 − 0.25)) = 0.675`

## Current-climate hazard steps

- **Combined MDR:** 0.375755

| Hazard | Intensity | Curve id | Exponent | Scale | MDR | Attribution share (info) | Notional loss |
|---|---:|---|---:|---:|---:|---:|---:|
| flood | 0.2 | `stub_mdr_hotel_flood` | 1.35 | 0.85 | 0.096785 | 0.235294 | 117,593.78 |
| extreme_heat | 0.65 | `stub_mdr_hotel_extreme_heat` | 1.35 | 0.5525 | 0.308863 | 0.764706 | 375,268.55 |

### Per-hazard formulas

- **flood:** `notional 1800000.0 × 0.096785 × 0.675` → loss **117,593.78** (curve `stub_mdr_hotel_flood`, catalogue v0.1.0)
- **extreme_heat:** `notional 1800000.0 × 0.308863 × 0.675` → loss **375,268.55** (curve `stub_mdr_hotel_extreme_heat`, catalogue v0.1.0)

## Results

| Field | Pipeline | Independent |
|---|---:|---:|
| EAL absolute | 456542.33 | 456542.33 |
| EAL % value | 25.363463 | 25.363463 |
| EAL 2030 | 538986.15 | 538986.15 |
| EAL 2050 | 678305.34 | 678305.34 |

**Independent EAL:** 456,542.33 (25.363463% of value)
**Pipeline EAL:** 456,542.33 (25.363463% of value)

---

# Asset `vf-002-apartment`

- **Valuation date:** 2024-12-31
- **Asset value:** 480,000.00
- **Building / use:** apartment / residential
- **Curve catalogue (pipeline = verifier):** `stub_global_mdr` v0.1.0 (synthetic calibration)
- **Record catalogue params:** `stub_global_mdr` v0.1.0
- **Catalogue path:** `/Users/macbookpro/Projects/georisk-engine/app/loss/curves/stub_global_mdr_v0.1.json`
- **Trail record id:** `atr_9605315075e94499bac6a7d22eec8062`
- **Trail record hash:** `cd9c3aabb2169ba60aea71d5dc8bee297695224dffa2d098317c1009b491913e`
- **Agreement:** PASS

## Vulnerability

`vuln = max(0.05, 1.05 × (1 − 0.05)) = 0.9974999999999999`

## Current-climate hazard steps

- **Combined MDR:** 0.312898

| Hazard | Intensity | Curve id | Exponent | Scale | MDR | Attribution share (info) | Notional loss |
|---|---:|---|---:|---:|---:|---:|---:|
| flood | 0.35 | `stub_mdr_apartment_flood` | 1.45 | 0.75 | 0.163667 | 0.411765 | 78,363.76 |
| extreme_heat | 0.5 | `stub_mdr_apartment_extreme_heat` | 1.45 | 0.4875 | 0.178435 | 0.588235 | 85,434.68 |

### Per-hazard formulas

- **flood:** `notional 480000.0 × 0.163667 × 0.9974999999999999` → loss **78,363.76** (curve `stub_mdr_apartment_flood`, catalogue v0.1.0)
- **extreme_heat:** `notional 480000.0 × 0.178435 × 0.9974999999999999` → loss **85,434.68** (curve `stub_mdr_apartment_extreme_heat`, catalogue v0.1.0)

## Results

| Field | Pipeline | Independent |
|---|---:|---:|
| EAL absolute | 149815.56 | 149815.56 |
| EAL % value | 31.211575 | 31.211575 |
| EAL 2030 | 185438.76 | 185438.76 |
| EAL 2050 | 246216.2 | 246216.2 |

**Independent EAL:** 149,815.56 (31.211575% of value)
**Pipeline EAL:** 149,815.56 (31.211575% of value)

---

# Asset `vf-001-hotel-coast`

- **Valuation date:** 2024-12-31
- **Asset value:** 2,500,000.00
- **Building / use:** hotel / tourism
- **Curve catalogue (pipeline = verifier):** `stub_global_mdr` v0.1.0 (synthetic calibration)
- **Record catalogue params:** `stub_global_mdr` v0.1.0
- **Catalogue path:** `/Users/macbookpro/Projects/georisk-engine/app/loss/curves/stub_global_mdr_v0.1.json`
- **Trail record id:** `atr_286b4ba12408472089cd5959a4a7e8d2`
- **Trail record hash:** `66e9d480ea4f2c8b79c4eadee455bb900e2f1773e6dfe1b7390ee5de6f13f2ee`
- **Agreement:** PASS

## Vulnerability

`vuln = max(0.05, 1.0 × (1 − 0.1)) = 0.9`

## Current-climate hazard steps

- **Combined MDR:** 0.478785

| Hazard | Intensity | Curve id | Exponent | Scale | MDR | Attribution share (info) | Notional loss |
|---|---:|---|---:|---:|---:|---:|---:|
| flood | 0.55 | `stub_mdr_hotel_flood` | 1.35 | 0.85 | 0.379235 | 0.578947 | 853,278.75 |
| extreme_heat | 0.4 | `stub_mdr_hotel_extreme_heat` | 1.35 | 0.5525 | 0.160366 | 0.421053 | 360,823.50 |

### Per-hazard formulas

- **flood:** `notional 2500000.0 × 0.379235 × 0.9` → loss **853,278.75** (curve `stub_mdr_hotel_flood`, catalogue v0.1.0)
- **extreme_heat:** `notional 2500000.0 × 0.160366 × 0.9` → loss **360,823.50** (curve `stub_mdr_hotel_extreme_heat`, catalogue v0.1.0)

## Results

| Field | Pipeline | Independent |
|---|---:|---:|
| EAL absolute | 1077266.25 | 1077266.25 |
| EAL % value | 43.09065 | 43.09065 |
| EAL 2030 | 1258839.0 | 1258839.0 |
| EAL 2050 | 1544350.5 | 1544350.5 |

**Independent EAL:** 1,077,266.25 (43.09065% of value)
**Pipeline EAL:** 1,077,266.25 (43.09065% of value)

---
