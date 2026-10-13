# Snapshot Audit — ISSUE_4C: Chain-Derived Pilot Assets

**Date:** 2026-08-28
**START_HEAD:** `bddda7d9294963a0f6406b4d058d48e0a0d15a65`
**Audit scope:** Replace hard-coded `pilot_assets()` with 5 `RealAmsterdamAsset` records derived from sealed Adres → VBO → PAND evidence chains.

---

## ISSUE_4C — CHAIN-DERIVED ASSET REPLACEMENT

**SOURCE_SET:** amsterdam-v1
**TARGET_CHAINS:** 5
**ASSET_ID_PREFIX:** NL-AM-CHAIN

### Chain-to-Asset Mapping

| Chain | Asset ID | Address | Pand | VBO |
|-------|----------|---------|------|-----|
| chain-1 | NL-AM-CHAIN-001 | Eerste Anjeliersdwarsstraat 1, Amsterdam | 0363100012174784 | 0363010000543292 |
| chain-2 | NL-AM-CHAIN-002 | Eerste Anjeliersdwarsstraat 17, Amsterdam | 0363100012174317 | 0363010000543308 |
| chain-3 | NL-AM-CHAIN-003 | Eerste Anjeliersdwarsstraat 18, Amsterdam | 0363100012174320 | 0363010000543309 |
| chain-4 | NL-AM-CHAIN-004 | Eerste Anjeliersdwarsstraat 36, Amsterdam | 0363100012174231 | 0363010000543325 |
| chain-5 | NL-AM-CHAIN-005 | Oostenburgervoorstraat 88, Amsterdam | 0363100012164933 | 0363010000544122 |

### Per-Chain Field Verification

For every chain:

```
Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS

Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS

Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

Adres.bronhouder_identificatie
    == "0363"                                   PASS

Adres.bronhouder_naam
    == "Amsterdam"                              PASS

VBO pand.href UUID
    == Pand feature.id                          PASS
```

### Attribute Source Verification

| Field | Source | chain-1 | chain-2 | chain-3 | chain-4 | chain-5 |
|-------|--------|---------|---------|---------|---------|---------|
| bouwjaar | Pand.properties.bouwjaar | 1916 | 1989 | 1922 | 1875 | 1994 |
| gebruiksdoel | VBO.properties.gebruiksdoel | winkelfunctie | winkelfunctie | bijeenkomstfunctie | winkelfunctie | overige gebruiksfunctie |
| oppervlakte | VBO.properties.oppervlakte | 30.0 | 98.0 | 83.0 | 140.0 | 1.0 |
| coordinates | VBO.geometry.coordinates | 4.8835, 52.3782 | 4.8836, 52.3781 | 4.8834, 52.3780 | 4.8835, 52.3779 | 4.9247, 52.3698 |

### Gate Results

```
CHAIN_DERIVED_ASSETS=5
HARD_CODED_ASSETS_REMOVED=true

OLD_PAND_IDS_REMOVED=5
OLD_VBO_IDS_REMOVED=5

CHAIN_ASSET_ID_FORMAT=PASS
CHAIN_PAND_ID_MATCH=PASS
CHAIN_VBO_ID_MATCH=PASS
CHAIN_BOUWJAAR_MATCH=PASS
CHAIN_GEBRUIKSDOEL_MATCH=PASS
CHAIN_OPPERVLAKTE_MATCH=PASS
CHAIN_COORDINATES_FROM_VBO=PASS

CHAIN_ASSET_IDENTITY_VERIFIED=true
CHAIN_ASSET_APPPLICABILITY_VERIFIED=false
CHAIN_ASSET_ENGINEERING_VERIFIED=false
CHAIN_ASSET_PRODUCTION_ELIGIBLE=false

RAW_ADRES_BYTES_PRESERVED=true
ADRES_RAW_HASHES_VERIFIED=true
VBO_PAGE_RAW_HASHES_VERIFIED=true
PAND_RAW_HASHES_VERIFIED=true
RAW_DERIVED_SEPARATION=PASS
SYNTHETIC_FALLBACK_USED=false

BAG_IDENTITY_CHAIN_VERIFIED=true

ASSET_APPLICABILITY_VERIFIED=false
ENGINEERING_CAPACITY_VERIFIED=false
PRODUCTION_ELIGIBLE=false
EXTERNAL_USE_APPROVED=false

ISSUE_4C=PASS
```

### What Changed

1. **`app/nl_pilot/real_assets.py`** — `pilot_assets()` now returns 5 `RealAmsterdamAsset` records with:
   - `bag_pand_id` = chain `pand_identificatie`
   - `bag_verblijfsobject_id` = chain `vbo_identificatie`
   - `bouwjaar` = Pand source data
   - `gebruiksdoel` = VBO source data
   - `oppervlakte_m2` = VBO source data
   - `coordinates` = VBO centroid geometry (CRS84/WGS84)
   - `asset_id` = `NL-AM-CHAIN-001` through `NL-AM-CHAIN-005`

2. **Old fixtures removed:** Damrak 1, Leidseplein 5, Rokin 50, Vijzelstraat 68, Zeedijk 100 (pand IDs 36320619, 36319427, 36321855, 36320193, 36322419)

3. **Tests updated:** `test_all_assets_are_commercial` → `test_all_assets_are_non_residential` (chain-3 has bijeenkomstfunctie, chain-5 has overige gebruiksfunctie)

4. **New tests:** `TestChainDerivedAssets` class with 17 tests verifying chain derivation, manifest consistency, and absence of old hard-coded data.

5. **Manifest updated:** Added `issue_4c` section documenting the chain mapping and source derivation.

### What Did NOT Change

- `RealAmsterdamAsset` dataclass shape
- `amsterdam_source.py` thresholds/URLs
- `pilot_evidence_pack.py` classification logic
- `pilot_gates` or acceptance contract semantics
- `ASSET_APPLICABILITY_VERIFIED=false`, `PRODUCTION_ELIGIBLE=false` etc.
- All ISSUE_4B evidence artifacts and verification status
