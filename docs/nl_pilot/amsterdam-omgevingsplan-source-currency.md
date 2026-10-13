# Amsterdam Omgevingsplan: is the pinned version still current law?

**Recorded:** 9 October 2026 · **Code:** `app/nl_pilot/amsterdam_source.py` (`AMSTERDAM_SOURCE_SUPERSESSIONS`,
`assess_source_currency`, `require_current_law_claim`), `app/nl_pilot/evidence_truth.py`
(`check_pack_current_law_claim`) · **Tests:** `tests/nl_pilot/test_source_currency.py`

## The event

| Field | Value |
|---|---|
| Pinned version | `CVDR696291/15`, in force from 19 June 2026 |
| Successor publication | Gemeenteblad 2026, 430670 (`gmb-2026-430670`): *Wijzigingsbesluit Omgevingsplan gemeente Amsterdam: Toevoeging van regels over horeca, darkstores en evenementenlocaties* |
| Adopted | 2 September 2026 |
| Published | 15 September 2026 |
| Takes effect | **14 October 2026**. `/15` is current law up to and including 13 October 2026 |
| Evidence status | `unsealed_official_notice`. The publication is not yet in the provenance manifest because overheid.nl was unreachable from the acquisition environment |

We pinned the WTI snapshot on 27 August 2026. It reads "Geldend van 19-06-2026 t/m heden" because the amendment
had not been adopted yet, so the sealed evidence cannot show when `/15` stops being current. The supersession
registry adds that fact. The registry can only take a current-law claim away. It can never make one stronger.

## What the change notice says about substance, and what we have verified

The change notice says the amendment covers horeca, darkstores, events and the numbering that goes with them.
It says the amendment does **not** change Articles 4.113, 4.115 or 4.116. We record this as
`reported_unamended_articles` and keep `reported_unamended_verified = False`. That flag is `init=False`, so no
constructor can set it to true. It can only become true once someone has checked those articles against a sealed
copy of the successor text. Until then, nobody should assume the threshold mappings carry over.

## How the gate behaves

| Date the claim is made | `currency_state` | Current-law claim | Blocker |
|---|---|---|---|
| < 2026-06-19 (before `/15` took effect) | `not_yet_in_force` | refused | `NL_AMS_SOURCE_VERSION_NOT_YET_IN_FORCE` |
| 2026-06-19 … 2026-10-13 | `current_pending_supersession` | permitted | none |
| ≥ 2026-10-14 | `superseded` | refused | `NL_AMS_SOURCE_VERSION_SUPERSEDED` |
| missing or unparseable (the whole ISO-8601 value must parse) | `undetermined` | refused | `NL_AMS_SOURCE_CURRENCY_AS_OF_INVALID` |
| any date, version reference without sealed effectivity evidence | `undetermined` | refused | `NL_AMS_SOURCE_VERSION_UNRECOGNIZED` |

- **Pack build.** The build checks currency at the pack's own `evidence_as_of`, which is the latest legal
  `retrieved_at`. If the evidence was retrieved on or after the effective date, the build fails. The pack carries
  a `source_currency` block. `truth_state.claim_boundaries.not_verified` lists current-law status on or after
  14 October 2026.
- **Validation.** `validate_evidence_pack_v2` recomputes `source_currency` from the registry. It rejects a pack
  when the block is missing, has been edited, or shows a superseded version as current law.
- **Use of a pack.** Anyone using a pack as a statement of current law on a given date must call
  `check_pack_current_law_claim(pack, as_of)`. From 14 October 2026 this call raises for every pack still pinned
  to `/15`.

Applicability itself does not fail closed because of this amendment. Only the current-law (source-version)
claim does.

## Steps to remove the blocker

1. Acquire the consolidated CVDR696291 version that is in force from 14 October 2026.
2. Seal the following in the provenance manifest: that version, its WTI metadata, and the `gmb-2026-430670`
   publication.
3. Re-verify the Article 4.113, 4.115 and 4.116 rule mappings against the sealed successor text.
4. Re-pin `resolved_version_ref`, extend `scripts/acquire_amsterdam_legal_source.py`, and rebuild
   `data/nl_pilot/evidence-pack-amsterdam-v2.json`.
