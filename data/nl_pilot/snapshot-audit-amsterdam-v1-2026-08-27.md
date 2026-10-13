# Amsterdam v1 Snapshot Audit — ISSUE_4B-R2

**Date:** 2026-08-27
**Commit:** 91eec895220f90481486dc16d0274a3900743bce
**Base:** 379888fd069e5b6d35881e750ed356da41c060fd (ISSUE_4B-R1)

## Scope

This audit evaluates the **amsterdam-v1** evidence set only. It does not
modify or replace the historical ISSUE_4A audit (`snapshot-audit-2026-08-27.md`)
which documents the earlier `bag-{adres,vbo,pand}.raw.json` 20-feature set
and its `AMSTERDAM_COMPLETE_CHAINS=0` result.

## What changed in R2

R1 verified address joins from VBO authoritative data only — no independent
Adres collection fetch existed. R2 fetches each of the 5 Adres features
directly from PDOK's `/collections/adres/items` endpoint using the official
`identificatie` query parameter and saves them as committed raw artifacts.

## Filter method

PDOK BAG OGC API v2 advertises an `identificatie` query parameter:

```
GET /collections/adres/items?identificatie=<BAG-identificatie>&limit=10
```

Parameter spec (from PDOK OpenAPI):
```json
{
  "description": "Filter features by this property",
  "explode": false,
  "in": "query",
  "name": "identificatie",
  "required": false,
  "schema": { "type": "string" },
  "style": "form"
}
```

This is NOT `/collections/adres/items/<featureId>` — the path parameter
identifies an OGC feature by its UUID, not by BAG `properties.identificatie`.

---

## Gate report

```
ISSUE_4B-R2 — INDEPENDENT BAG ADRES VERIFICATION

SOURCE_SET=amsterdam-v1
TARGET_CHAINS=5

ADRES_COLLECTION_RAW_ARTIFACTS=5
ADDRESS_FEATURES_RESOLVED=5
COMPLETE_ADRES_VBO_PAND_CHAINS=5
```

### Per-chain verification

For every chain:

```
chain-1: Eerste Anjeliersdwarsstraat 1

  Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS
    (0363200000006110 == 0363200000006110)

  Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS
    (0363010000543292 == 0363010000543292)

  Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

  Adres.bronhouder_identificatie
    == "0363"                                   PASS

  Adres.bronhouder_naam
    == "Amsterdam"                              PASS

  VBO pand.href UUID
    == Pand feature.id                          PASS
    (dd867efb-bdbb-59e2-a114-86f1c9efb2d5)
```

```
chain-2: Eerste Anjeliersdwarsstraat 17

  Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS
    (0363200000403263 == 0363200000403263)

  Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS
    (0363010000543308 == 0363010000543308)

  Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

  Adres.bronhouder_identificatie
    == "0363"                                   PASS

  Adres.bronhouder_naam
    == "Amsterdam"                              PASS

  VBO pand.href UUID
    == Pand feature.id                          PASS
    (6299cde8-068f-5c75-ac0e-866ae1a47bfb)
```

```
chain-3: Eerste Anjeliersdwarsstraat 18

  Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS
    (0363200000006127 == 0363200000006127)

  Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS
    (0363010000543309 == 0363010000543309)

  Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

  Adres.bronhouder_identificatie
    == "0363"                                   PASS

  Adres.bronhouder_naam
    == "Amsterdam"                              PASS

  VBO pand.href UUID
    == Pand feature.id                          PASS
    (56ac4bba-bc5d-5d22-8616-285a6bc2f430)
```

```
chain-4: Eerste Anjeliersdwarsstraat 36

  Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS
    (0363200000006140 == 0363200000006140)

  Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS
    (0363010000543325 == 0363010000543325)

  Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

  Adres.bronhouder_identificatie
    == "0363"                                   PASS

  Adres.bronhouder_naam
    == "Amsterdam"                              PASS

  VBO pand.href UUID
    == Pand feature.id                          PASS
    (4cd357b2-46c9-53cb-9b1c-bfa64659d82d)
```

```
chain-5: Oostenburgervoorstraat 88

  Adres.identificatie
    == VBO.hoofdadres_identificatie             PASS
    (0363200000431014 == 0363200000431014)

  Adres.adresseerbaar_object_identificatie
    == VBO.identificatie                        PASS
    (0363010000544122 == 0363010000544122)

  Adres.adresseerbaar_object_type
    == "Verblijfsobject"                        PASS

  Adres.bronhouder_identificatie
    == "0363"                                   PASS

  Adres.bronhouder_naam
    == "Amsterdam"                              PASS

  VBO pand.href UUID
    == Pand feature.id                          PASS
    (c6870d66-edf3-5d84-bb27-41752f1fba28)
```

---

## Artifact inventory

### Raw Adres collection artifacts (R2)

| Source ID | BAG identificatie | OGC feature.id | File | Bytes |
|---|---|---|---|---|
| amsterdam-chain-1 | 0363200000006110 | 8d6a652e-c9f4-5c8b-bbe1-b9fb248a28fc | adres-0363200000006110.raw.json | 1201 |
| amsterdam-chain-2 | 0363200000403263 | 00c42ffb-ec16-59d0-8dab-2e87dab9945b | adres-0363200000403263.raw.json | 1204 |
| amsterdam-chain-3 | 0363200000006127 | c598bd48-f2de-5f5a-945d-450d6b7bfa17 | adres-0363200000006127.raw.json | 1202 |
| amsterdam-chain-4 | 0363200000006140 | 8bf9709c-963f-5768-baec-c2fe3c182c01 | adres-0363200000006140.raw.json | 1203 |
| amsterdam-chain-5 | 0363200000431014 | 08b1ee23-4932-550e-8406-e0d10520074d | adres-0363200000431014.raw.json | 1176 |

Each artifact is a single-feature FeatureCollection wrapping the exact PDOK
response. The `source_url` includes the `?identificatie=...` filter parameter.

### VBO raw page artifacts (pre-existing, R1)

10 VBO page snapshots (`vbo-page-0.raw.json` through `vbo-page-9.raw.json`)
plus 5 Pand individual snapshots and the derived VBO selected snapshot — all
unchanged from R1.

### Pre-existing broad snapshots

`bag-{adres,vbo,pand}.raw.json` — the original ISSUE_3/4A 20-feature set
with `bbox=3.9,52.3,5.1,52.4`. Unchanged and untouched.

---

## Summary gates

```
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
```

## Manifest changes in R2

1. **address_verification block:** `source_collection` updated from
   `"verblijfsobject"` to `"adres"` for all 5 chains. `source_note` updated
   to `"Independent BAG Adres collection record (R2 verified)"`. New `source_id`
   field added linking to the manifest source entry.

2. **Chain entries:** `address_source` updated from
   `"vbo_authoritative_bag_record"` to `"independent_adres_collection_record"`.
   New `adres_collection_source_id` field added.

3. **Sources section:** 5 new Adres collection source entries added
   (`amsterdam-chain-1` through `amsterdam-chain-5`) with full provenance:
   `collection=adres`, `source_url` with `?identificatie=...`, `retrieved_at`,
   `http_status=200`, `byte_length`, `artifact_sha256`,
   `normalized_content_sha256`, `snapshot_path`.

4. **issue_4b_r2 section:** Added with completion timestamp, filter method,
   and all verification flags.

## Test coverage

New test class `TestIndependentAdresVerification` in
`tests/nl_pilot/test_nl_pilot.py` with 13 tests:

- All 5 Adres snapshot files exist and are FeatureCollections
- `Adres.identificatie == VBO.hoofdadres_identificatie` (5 chains)
- `Adres.adresseerbaar_object_identificatie == VBO.identificatie` (5 chains)
- `Adres.adresseerbaar_object_type == "Verblijfsobject"` (5 chains)
- `Adres.bronhouder_identificatie == "0363"` (5 chains)
- `Adres.bronhouder_naam == "Amsterdam"` (5 chains)
- Artifact SHA-256 hash reproduction for all 5 Adres snapshots
- Complete Adres→VBO→Pand chain verification
- Manifest metadata verification (source entries, issue_4b_r2 section, chain references)

## Next step

ISSUE_4C: Generate `RealAmsterdamAsset` records from the 5 sealed
Adres→VBO→Pand chains instead of hard-coded fixtures.
