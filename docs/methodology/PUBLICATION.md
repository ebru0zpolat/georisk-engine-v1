# Methodology publication hierarchy

| Layer | Artefact | Role |
|-------|----------|------|
| 1. Normative | [`GEORISK_ENGINE_METHODOLOGY.md`](./GEORISK_ENGINE_METHODOLOGY.md) | Version-controlled technical specification (formula, assumptions, limitations, change history). |
| 2. Public summary | [`/methodology`](https://georiskengine.com/methodology) (`frontend/public/methodology/index.html`) | Canonical public bilingual summary aligned to the same methodology version. |
| 3. Demo UI | Portfolio demo (`/demo`) | Product illustration; must show calibration status and use **Recomputed EAL** only as a replay label. |
| 4. PDF (optional) | Derived snapshot only | Generated from the approved HTML/Markdown source; must show version and generation date; must **not** become an independently edited source of truth. |

**Current public version:** `georisk-methodology-v0.4.0` (September 2026).

**Formula note:** v0.4.0 brought wildfire and earthquake into scope with their curves and did not change `expected-loss-v0.3` arithmetic; v0.3.1 clarified meaning, assumptions and limitations.

Layer-4 formula detail: [`app/loss/METHODOLOGY.md`](../../app/loss/METHODOLOGY.md).  
Reproducibility verifier note: [`tests/verification/METHODOLOGY.md`](../../tests/verification/METHODOLOGY.md).
