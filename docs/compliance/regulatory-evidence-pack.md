# Regulatory Evidence Pack — Amsterdam Hemelwater

**Status:** Technical demonstrator — not operational, not certified  
**Version:** 0.2  
**Pack ID:** `NL-AMSTERDAM-HEMELWATER-2026-V1`

---

## What is this?

A **machine-readable JSON data structure** that maps specific Dutch
regulatory rules to per-asset regulatory screening states.  The
first implemented instance covers Amsterdam hemelwater (rainwater
management) rules from the current Omgevingsplan (Paragraaf 4.4.2)
and the Waterschapsverordening AGV.

**Implementation status:** This is an implementation specification
and technical demonstrator.  The regulatory capacity gate logic is
implemented; the hydrological stress model (rainfall-runoff-storage
simulation) is not yet implemented.

Amsterdam Regulatory Evidence Pack is GeoRisk Engine's first
machine-readable prototype that links official local regulatory
provisions to per-asset fail-closed screening states with versioned
rule definitions.  Since independent SHA-256 verification of official
source artifacts and asset-level applicability verification are not
yet complete, the output is NOT a legal compliance certificate or
regulatory approval.

## Key features

| Feature | Detail |
|---------|--------|
| Rule types | Storage requirement (60 L/m²), discharge limit (1 L/m²/h), emptying requirement (60 h) |
| Screening | Per-asset gate chain: applicability filter → rule threshold evaluation; applicability remains unverified until independently established |
| Source registry | Placeholder content hashes until real artifacts retrieved; draft/superseded sources blocked |
| Official source artifacts | Per-artifact provenance: authority, publication ID, URL, retrieval timestamp, mime type, byte length, SHA-256 of raw artifact bytes |
| Threshold provenance | Per-rule exact citation: article/lid/paragraph/page linked to artifact SHA-256 |
| Threshold verification | `threshold_source_verified=false` until independently verified; unverified thresholds produce `source_unverified` (fail-closed) |
| Terminology | Neutral threshold language: `threshold_satisfied` / `threshold_not_satisfied` / `source_unverified` (NOT compliance language) |
| Deterministic | Same inputs → byte-identical output (except envelope timestamp) |
| Checksum | SHA-256 over deterministic content; tamper-evident (checksum-integrity, not external-source verification) |
| Two checksums | `artifact_sha256` fingerprints the retrieved official publication; `content_sha256` fingerprints this generated pack |
| Fail-closed | Invalid CRS, duplicate IDs, missing sources, unverified applicability → immediate abort |
| Classification | Explicitly `synthetic_reference`, `not_customer_data`, `production_eligible=false` |

## Architecture

```
Official source artifact retrieval
    ↓
artifact_sha256 (raw bytes of PDF/XML from Overheid.nl)
    ↓
Threshold provenance (Artikel 4.116, lid 1(a)/(b)/(c))
    ↓
RegulatoryRule definitions (thresholds + applicability filters)
    ↓
AssetVerification engine (per-asset rule evaluation)
    ↓
Evidence Pack (JSON + content_sha256 checksum)
```

### Provenance chain

```
official artifact bytes
    → source SHA256 (artifact_sha256)
    → article / paragraph / lid
    → threshold value
    → rule
    → asset applicability evidence
    → evidence pack
    → pack SHA256
```

**Important:** The pack SHA256 and the artifact SHA256 are two
separate checksums.  The artifact SHA256 fingerprints the retrieved
official publication; the pack SHA256 fingerprints this generated
evidence pack.

### Official source artifact verification

Each official source artifact record contains:

- `source_id` — matches source_registry entry
- `authority` — the issuing authority (e.g. "Gemeente Amsterdam")
- `official_publication_id` — the publication's own identifier (NOT a GeoRisk internal ID)
- `source_url` — URL of the official publication
- `retrieved_at` — ISO 8601 timestamp of retrieval (empty if not yet retrieved)
- `effective_from` / `effective_until` — dates the regulation is in force
- `mime_type` — MIME type of the retrieved artifact (e.g. `application/pdf`)
- `byte_length` — byte length of the retrieved artifact
- `artifact_sha256` — SHA-256 of the raw byte content (NOT rendered HTML or copy-pasted text)
- `source_checksums_verified` — True only after independent retrieval and hash
- `status` — must be `"current"` (draft/superseded/repealed fail verification)

Verification gate:
```
retrieve official publication from Overheid.nl
    ↓
publication/effective version matches expected?
    ├── NO → source_unverified
    └── YES
          ↓
   raw artifact SHA matches recorded SHA?
          ├── NO → source_changed
          │        rule verification invalidated
          └── YES
                ↓
         threshold mapping may proceed
```

### Amsterdam source attribution

All three Amsterdam hemelwater thresholds (60 L/m², 1 L/m²/h, 60h)
are from the **Amsterdam Omgevingsplan** (Paragraaf 4.4.2 / Artikel
4.116), NOT from the AGV Waterschapsverordening.

The AGV source (`agv-waterschapsverordening`) is retained for future
AGV-specific rules (e.g. hard surface compensation, surface water
requirements).  It is NOT used for the 60/1/60 thresholds.

**Historical note:** The Hemelwaterverordening Amsterdam expired
31 October 2024.  The current regulation is the consolidated
Omgevingsplan.

## Permitted uses

1. **Schema-conformance testing** — verify the pack structure
2. **Dry-run demonstration** — show the system's verification logic
3. **Regulatory sandbox preparation** — structured evidence for AI sandbox applications
4. **Academic methodology documentation** — cite the rule structure and verification approach
5. **Integration testing** — verify downstream consumers can parse the pack
6. **CI regression testing** — detect rule drift or schema changes

## Prohibited uses

| Prohibited | Reason |
|-----------|--------|
| Standalone compliance certification | This is decision-support evidence, not legal compliance |
| Credit/lending decisions | No individual property should be approved or rejected based solely on this pack |
| Regulatory submission without human review | All outputs require independent legal/expert verification |
| Marketing claims ("EU approved", "AI Act certified", etc.) | Prohibited per repository claim policy |
| Production eligibility assertion | `production_eligible` is hardcoded to `false` in this synthetic reference instance |
| Replacement for professional engineering assessment | Storage calculations are illustrative; real assessments require site-specific engineering |

## Source-to-engineering trace

Each rule in the pack traces to an official source with:
- `source_id` → `source_registry` entry
- `content_hash` → SHA-256 of the canonical source text
- `status` → must be `"current"` (draft/superseded blocked programmatically)

Each rule also carries threshold provenance:
- `article_reference` → e.g. "Artikel 4.116"
- `paragraph_reference` → e.g. "Paragraaf 4.4.2"
- `lid_reference` → e.g. "lid 1(a)"
- `official_artifact_sha256` → must match the referenced artifact's SHA-256
- `provenance_verified` → True only after full chain verified

## CRS handling

| CRS | Axis order | Status |
|-----|-----------|--------|
| EPSG:28992 | x (easting), y (northing) | Supported |
| EPSG:4326 | longitude, latitude | Supported |

Invalid CRS values are rejected at pack generation time (fail-closed).

## Regulatory domain

This pack covers **hemelwater** (rainwater management) only.  Future
packs for other Dutch regulatory domains (overstroming, bodemdaling,
hitte) will follow the same schema and architecture.

**Architectural separation:** This evidence pack implements the
REGULATORY CAPACITY GATE — independent numeric threshold evaluation.
It does NOT implement a hydrological stress model (rainfall hyetograph,
roof area, runoff coefficients, green-roof retention, infiltration,
controlled discharge routing).  The two engines serve different
purposes and must not be conflated.

## Evidence classification

```
{
  "evidence_class": "synthetic_reference",
  "customer_data_status": "not_customer_data",
  "production_eligible": false,
  "decision_use_approved": false
}
```

## Repository context

This work is part of the GeoRisk Engine NL pilot preparation.
It is separate from:
- PR #141 (pilot protocol)
- PR #150 (PDOK ROR connector)
- PR #153 (synthetic portfolio fixture)
- PR #154 (synthetic risk simulation evidence)
- PR #155 (AI regulatory sandbox dossier)

## ESRS E1 evidence mapping

GeoRisk Engine maps its regulatory screening outputs to ESRS E1
disclosure requirements using **versioned instrument + semantic
concept pairs**.  This is necessary because the same disclosure
requirement number maps to different concepts across ESRS versions:

| Concept                          | ESRS 2023 (in-force) | ESRS 2026 (adopted, not in force) |
|----------------------------------|----------------------|------------------------------------|
| Transition plan (mitigation)     | E1-1                 | E1-1                               |
| Climate risk identification      | ESRS2-IRO1/E1        | E1-2                               |
| Climate resilience               | —                    | E1-3                               |
| Adaptation policies              | E1-2                 | E1-4                               |
| Adaptation actions/resources     | E1-3                 | E1-5                               |
| GHG emissions                    | E1-6                 | E1-8                               |
| GHG removals and carbon credits  | E1-7                 | —                                  |
| Anticipated financial effects    | E1-9                 | E1-11                              |

**Key design decisions:**

- `semantic_concept` is the stable cross-version identifier
- `disclosure_requirement` alone is insufficient for mapping
- Status terminology: `evidence_supported` / `insufficient_evidence` /
  `not_assessed` (NOT eligible/aligned/compliant)
- `asset_applicability_verified` is INDEPENDENT of source verification gates
- Financial exposure requires `carrying_value` from financial statements,
  NOT arbitrary asset valuations

**Implementation status:** The mapping engine produces evidence-readiness
assessments, NOT compliance verdicts.  Actual ESRS disclosure mapping
requires portfolio-level financial data not yet available in the pilot
infrastructure.

## Operational status

| Gate | Status |
|------|--------|
| Regulatory capacity gate (threshold evaluation) | ✅ Implemented |
| Official source artifact registry | ✅ Implemented (placeholder hashes) |
| Threshold provenance records | ✅ Implemented (citation chain) |
| Source artifact verification gate | ✅ Implemented (fail-closed) |
| ESRS E1 evidence mapping (versioned) | ✅ Implemented |
| Hydrological stress model (rainfall-runoff-storage) | ❌ Not yet implemented |
| Source registry integrity | ✅ Verified |
| Fail-closed validation | ✅ Verified |
| Schema conformance | ✅ Verified |
| Official artifact SHA-256 verification | ❌ Pending — requires retrieval |
| Human legal review | ❌ Pending |
| External-use approval | ❌ Not yet — separate gate required |
| Production eligible | ❌ False by design |
