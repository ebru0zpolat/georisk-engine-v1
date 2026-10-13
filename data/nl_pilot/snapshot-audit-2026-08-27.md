# ISSUE_4A — Snapshot Joinability Audit (Corrected)

**Date:** 2026-08-27 (corrected)
**Snapshots:** `data/nl_pilot/snapshots/bag-{pand,verblijfsobject,adres}.raw.json`
**Acquisition:** Live PDOK BAG OGC API v2, bbox=3.9,52.3,5.1,52.4 (CRS84), limit=20

## Join key architecture

Two distinct identifier spaces exist in BAG/OGC data:

| Identifier | Type | Example | Used by |
|------------|------|---------|---------|
| BAG identificatie | Numeric (16-digit) | `0305100000001259` | `properties.identificatie` on all collections |
| Feature ID (UUID) | UUID v4 | `33478d74-7a5d-81b3-95fc8017b5ab` | Top-level `id` field on OGC Feature |

**Critical rule:** href UUIDs match `feature.id`, NOT `properties.identificatie`.

## Join paths

```
Adres → VBO:
  adres.properties.adresseerbaar_object_identificatie
      == vbo.properties.identificatie

VBO → Pand:
  UUID from vbo.properties["pand.href"]
      == pand.feature.id  (top-level OGC Feature id)

Pand → VBO (validation):
  UUID from pand.properties["verblijfsobject.href"]
      == vbo.feature.id  (top-level OGC Feature id)
```

## Results

| Metric | Value |
|--------|-------|
| ADRES_FEATURES | 20 |
| VBO_FEATURES | 20 |
| PAND_FEATURES | 20 |
| ADRES_TO_VBO_RESOLVED | 15/20 |
| VBO_TO_PAND_RESOLVED | 3/20 |
| COMPLETE_CHAINS | 3 |
| AMSTERDAM_COMPLETE_CHAINS | 0 |
| NON_AMSTERDAM_COMPLETE_CHAINS | 3 (all Abcoude) |

### Complete chain records

| Address | Woonplaats | VBO ident | Pand ident | Gebruiksdoel | Oppervlakte | Bouwjaar |
|---------|-----------|-----------|-----------|-------------|------------|---------|
| (Abcoude) | Abcoude | 0305010000001451 | 0305100000001272 | woonfunctie | 184 m² | 1940 |
| (Abcoude) | Abcoude | 0305010000001503 | 0305100000001259 | industriefunctie,woonfunctie | 262 m² | 1910 |
| (Abcoude) | Abcoude | 0305010000001504 | 0305100000001258 | woonfunctie | 312 m² | 1976 |

### Unresolved relations

- **5 adres records** have no matching VBO identificatie in snapshot (outside bbox overlap)
- **17 VBO records** have pand.href UUIDs not present in pand snapshot (different bbox area)

## Gates

| Gate | Status | Reason |
|------|--------|--------|
| FEATURE_ID_JOIN | **PASS** | UUID→feature.id correctly resolves 3/3 attempted joins |
| BAG_IDENTIFICATIE_SEPARATION | **PASS** | feature.id ≠ identificatie; both preserved separately |
| CROSS_COLLECTION_JOINABLE | **PASS** (limited) | Chains resolve correctly; coverage limited by bbox |
| AMSTERDAM_COMPLETE_CHAINS | **FAIL** | 0 Amsterdam records in current snapshots |

## Root cause: bbox too wide

The CRS84 bbox `3.9,52.3,5.1,52.4` covers a ~120km×11km area including Abcoude, Aalsmeer, and Amsterdam. PDOK returns the first 20 records spatially ordered — all happen to be outside Amsterdam center.

## Required before ISSUE_4

1. **Tighter Amsterdam-only bbox** (e.g., `4.88,52.31,4.98,52.41`)
2. **Re-acquire + re-seal snapshots** with Amsterdam focus
3. **Increase limit** or add CQL filter for `gemeentenaam='Amsterdam'`
