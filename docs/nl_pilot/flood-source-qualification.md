# Flood-source qualification & sealed evidence pack

> The fail-closed gate that decides whether a real return-period flood-hazard map
> may be trusted as the reference-level source. It is a **prerequisite for**, and
> deliberately **separate from**, any change that promotes `expected-loss-v0.4`
> flood to the default.

## Why a gate

The reference-level machinery is built (`app/loss/flood_hazard_map.py`, wired into
`flood_depth`, STUBS #26). But "we vendored a JSON" is not "we may rely on it in a
regulated EAL". Before a real map is trusted, the **source** must be qualified: it
must be real, licensed, in the right datum, cover the required area at the required
return periods, and be bound to an auditable evidence record. That record is the
**sealed evidence pack** a buyer's diligence asks for.

## The evidence pack

`FloodSourceEvidencePack` (`app/loss/flood_source_qualification.py`) names:

- `source_id` and the exact `map_artifact` + `map_artifact_sha256` (binds the pack
  to the precise sealed map bytes);
- a `licence` (`FloodMapLicence`: licensor, use-rights, attribution, validity);
- the `datum` (must be `NAP` — the same datum as the elevation);
- a `methodology` citation;
- the `required_points` and `required_return_periods` the source must cover.

`pack.seal_sha256()` is the pack's own canonical seal. Build one for a vendored
real map with `scripts/build_flood_evidence_pack.py` (it refuses a synthetic map).

## The six controls (all must pass — fail-closed)

`evaluate_flood_source_qualification(pack=…, map_path=…, as_of=…)` returns a
`FloodSourceQualificationVerdict`. `qualified=True` only when **all** hold:

1. **real source** — the map is not a labelled synthetic fixture (its provenance
   sidecar is verified on load);
2. **artifact bound** — `sha256(map bytes) == pack.map_artifact_sha256` (a 64-hex
   digest);
3. **licence** — licensor + attribution present, use-rights stated, in effect at
   `as_of`;
4. **datum** — pack datum and map datum both equal `NAP`;
5. **coverage** — every required point resolves at every required return period;
6. **methodology** — a source/methodology is cited.

Any gap leaves `qualified=False` with the reason named.

The datum check above is the *source-qualification* control. Separately, at depth
time, `flood_depth.assert_differenceable` re-checks the **full** compatibility of the
elevation and the map before subtracting them — not just the datum name, but units,
horizontal CRS, value semantics (a ground surface vs a water surface, never an
already-computed depth) and an explicit datum transformation — failing closed with
`FLOOD_DATUM_MISMATCH`. So a NAP water level can never be differenced against an
EGM2008 (Copernicus DEM) elevation even if both packs claim `NAP`.

## Offline / honest state

```bash
PYTHONPATH=. python scripts/run_flood_source_qualification_demo.py
```

Offline the only map available is the labelled synthetic fixture, so the gate
returns **NOT QUALIFIED** — every other control can pass, but control (1) fails:
a synthetic source can never be qualified. Vendor a real map
(`scripts/vendor_flood_hazard_map.py`) and seal a real pack
(`scripts/build_flood_evidence_pack.py`) to reach **QUALIFIED**.

## Demo: two non-fungible modes

`scripts/run_flood_reference_demo.py` keeps the ingestion *mechanics* strictly
separate from a real *qualification*, and the qualified mode never falls back:

- `--mode fixture` (default) — labelled **synthetic** NAP elevation + synthetic
  flood map. Exercises the elevation → depth → JRC wiring and the mandatory
  provenance record. Claim: **integration mechanics only**; it proves nothing about
  real risk. The synthetic elevation is labelled
  `SYNTHETIC_NAP_ELEVATION — integration demonstration only; not AHN evidence` and is
  never described as "representing AHN" (data not from AHN is not AHN).
- `--mode qualified` — requires a real, sealed flood-hazard map **and** evidence pack
  **and** a real, sealed NAP elevation source (e.g. AHN). Runs this gate; if any real
  evidence is missing or the gate is not QUALIFIED, it prints `NOT_QUALIFIED` and
  exits non-zero. **No synthetic fallback.** Absent real AHN evidence for the pilot
  points, that is the expected result today.

## Sequence to a v0.4-default change

1. Vendor a real NL flood-hazard map (LIWO / flood extent) **and** a real, sealed
   AHN-NAP elevation for the pilot points.
2. Seal an evidence pack bound to the map; **this gate returns QUALIFIED** and the
   demo's `--mode qualified` proceeds instead of `NOT_QUALIFIED`.
3. Exact-head test/review of the qualification completes and merges.
4. **Only then**, in a **separate PR**, evaluate promoting v0.4 flood to default.

This gate never performs step 4; it only makes step 4 eligible. Until step 1, #180
provides mergeable ingestion infrastructure only — STUBS #26 stays OPEN.
