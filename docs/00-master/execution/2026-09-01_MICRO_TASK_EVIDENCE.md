# Roadmap execution record — first ten micro-tasks (2026-09-01)

**Reference plan:** GeoRisk Engine roadmap, 1 September 2026 (6-week horizon)
**Recorded `main` SHA:** `ab9062083af716f5d711f19949a4188a96768507`
**Reviewer:** ozpolat.ebru@gmail.com (self-attested, per project decision §1)
**Evidence class:** repository/GitHub state verification only. No test suite was executed
for this record, no live runtime call was made, and no eligibility flag was changed.

Verdict vocabulary per plan §11: `AUTO-PASS` (verified, no founder input needed),
`AUTO-BLOCK` (verified as blocked/failing), `FOUNDER-DECISION` (verified, decision
reserved to the founder).

Method for every ahead/behind and mergeability figure below:

```
git fetch origin pull/<N>/head:pr<N>
git rev-list --left-right --count origin/main...pr<N>   # behind<TAB>ahead
git merge-tree --write-tree --name-only origin/main pr<N>  # exit 0 = clean
```

---

## Summary table

| # | Task | Subject | Verdict |
|---|---|---|---|
| 1 | A1.1 | PR #154 exact head / main | AUTO-PASS |
| 2 | A2.1 | PR #163 exact head re-verification | AUTO-PASS |
| 3 | A3.1 | PR #155 head + mergeability | AUTO-PASS |
| 4 | B1.1 | PR #132 close reason | AUTO-PASS — two findings raised, both resolved by the B1.3 decision below |
| 5 | D1.1 | PR #174 exact-head verification | AUTO-PASS |
| 6 | C2.1 | PR #139 relation to current `main` | AUTO-PASS |
| 7 | C2.3 | PR #145 base/dependency verification | AUTO-PASS |
| 8 | E1.1 | Pilot overview first draft | AUTO-PASS (draft landed) |
| 9 | E4.1 | ICP scoring rubric | AUTO-PASS (rubric landed) |
| 10 | F1.1 | Data-provider category decision | FOUNDER-DECISION (options + recommendation recorded) |

Additional finding produced while verifying the above: **PR #136 (AHN, GEO-199)
does not merge cleanly into current `main`** — see the appendix.

---

## 1. A1.1 / A1.2 — PR #154 (GEO-206) synthetic simulation evidence

| Field | Value |
|---|---|
| PR | [#154](https://github.com/ebru0zpolat/georisk-engine/pull/154) — `feat: deterministic synthetic risk simulation evidence (claim-safe)` |
| Head branch | `feat/synthetic-risk-simulation-evidence` |
| **Exact head SHA** | `ad6211fe20de351f4cc2d3b71209e7fee0a5eab9` |
| **Current `main` SHA** | `ab9062083af716f5d711f19949a4188a96768507` |
| Merge base | `6c9db2cd1b565d1876bdffba714f27fd7f74f224` |
| Behind `main` | **55 commits** |
| Ahead of `main` | 1 commit |
| GitHub `mergeable_state` | `clean` |
| Local `git merge-tree` | clean — no conflicted paths |
| State | open, not draft, 4 files, +3613 |

**CI at this exact head:** run
[32952647511](https://github.com/ebru0zpolat/georisk-engine/actions/runs/32952647511)
(2026-08-26) — `pytest`, `frontend`, `verify-eal`, `dependency-security`,
`founder-operations-phase-1` all `success`; `Vercel Agent Review` `neutral`.

**Verdict — AUTO-PASS on the recording tasks (A1.1, A1.2).** Both SHAs and the
mergeability figures are captured.

**Carry-forward constraint.** The green CI above ran on `ad6211fe`, which is 55
commits behind `main`. Per plan §1.5 it does **not** validate the post-reconciliation
head. A1.4/A1.5 must re-run on the new head produced by A1.3.

---

## 2. A2.1 — PR #163 (GEO-207) NL CRE Evidence Resolver

| Field | Value |
|---|---|
| PR | [#163](https://github.com/ebru0zpolat/georisk-engine/pull/163) — `feat(nl-cre): NL CRE Evidence Resolver — scalable Article 4.113 evaluation` |
| Head branch | `feat/nl-cre-evidence-resolver` |
| **Exact head SHA** | `6d60475b6cd5b9c3159c56a7b9f422eb97141b23` |
| Head asserted in plan §A2.1 | `6d60475b6cd5b9c3159c56a7b9f422eb97141b23` |
| **Match** | ✅ confirmed unchanged |
| Merge base | `36f84f4d5a86342a48901c6e6fe534d9ecd50526` |
| Behind `main` | **14 commits** |
| Ahead of `main` | 3 commits |
| GitHub `mergeable_state` | `clean` |
| Local `git merge-tree` | clean — no conflicted paths |
| State | open, not draft, 7 files, +1589 |

**CI at this exact head:** run
[33268197294](https://github.com/ebru0zpolat/georisk-engine/actions/runs/33268197294)
(2026-08-29) — all five required jobs `success`.

**Verdict — AUTO-PASS.** The plan's asserted head is still the live head.
Same §1.5 constraint applies: A2.3–A2.7 must run on the reconciled head, not on
`6d60475b`.

---

## 3. A3.1 — PR #155 (GEO-208) AI sandbox dossier

| Field | Value |
|---|---|
| PR | [#155](https://github.com/ebru0zpolat/georisk-engine/pull/155) — `docs: WP-NL-AI01 AI regulatory sandbox candidate dossier v0.1` |
| Head branch | `docs/wp-nl-ai01-sandbox-dossier` |
| **Exact head SHA** | `afb449531aff5659a09eca4058a2fd31be5636d1` |
| Merge base | `6c9db2cd1b565d1876bdffba714f27fd7f74f224` |
| Behind `main` | **55 commits** |
| Ahead of `main` | 1 commit |
| GitHub `mergeable_state` | `clean` |
| Local `git merge-tree` | clean — no conflicted paths |
| State | open, not draft, 3 files, +384 (all under `docs/compliance/`) |

**CI at this exact head:** run
[32964733987](https://github.com/ebru0zpolat/georisk-engine/actions/runs/32964733987)
(2026-08-26) — all five required jobs `success`.

**Verdict — AUTO-PASS.** Head and mergeability recorded. The docs-only boundary
(A3.2) is consistent with the file list but is a separate task and is **not**
attested here.

---

## 4. B1.1 / B1.2 — PR #132 (GEO-61) Aqueduct NL pack: why it was closed unmerged

**Close event:** 2026-08-30T10:54:03Z, `state=closed`, `merged=false`, head
`ca017e2b665fa6d3eff85f3fa518b54de3fbc6d1`.

**Primary evidence:** closing comment
[#issuecomment-5468246064](https://github.com/ebru0zpolat/georisk-engine/pull/132#issuecomment-5468246064)
by `ebruozpolat` (author association `MEMBER`), 2026-08-30. Verbatim reason:

> Closing as superseded by **ADR-0007 — Replace Aqueduct 4.0 water stress with
> Klimaateffectatlas indicators for NL assets** (Accepted, 2026-08-30).

The comment gives three grounds — wrong quantity (withdrawals-to-supply ratio, not a
building hazard), wrong resolution (hydrological-basin scale, no discrimination inside
a Randstad portfolio), wrong signal — and states that because there was no Aqueduct
adapter on `main`, *closing this PR is itself the deletion ADR-0007 calls for*. The
branch is retained as a reference implementation for a possible non-NL portfolio.

**Determination for B1.3: the disposition is `superseded`, not `restore` or
`recreate`.** The 15 pack files of PR #132 are confirmed absent from `main`:

```
app/packs/nl/…                    (4 files)   absent from main
data/packs/aqueduct_nl/…          (8 files)   absent from main
scripts/build_aqueduct_nl_pack.py             absent from main
tests/packs/nl/water_stress/…     (2 files)   absent from main
```

### Finding B1-F1 — ADR-0007 is not committed to the repository

`git grep -i "ADR-0007" origin/main` returns **no match**, and there is no
`docs/decisions/` or equivalent ADR directory on `main`. The decision that closed a
P1 workstream exists only as a GitHub comment. Under plan §12.3 an issue needs an
exact artefact reference; a comment citing an uncommitted ADR is a weaker record than
the rule intends. **Recommended remediation before GEO-61 is marked Done: commit
ADR-0007 to the repository and cite its commit SHA.**

### Finding B1-F2 — an NL-scoped Aqueduct adapter landed on `main` *after* ADR-0007

The closing comment asserts "There is no Aqueduct adapter on `main`". That was true
of the pack in PR #132, but `main` currently contains:

| Path on `main` | Note |
|---|---|
| `app/nl_pilot/water_stress.py` | NL-scoped. Header: *"Water-stress context indicator — WRI Aqueduct Baseline Water Stress (BWS)"*; declares `AQUEDUCT_AUTHORITY`, `AQUEDUCT_LICENSE`, `WATER_STRESS_METHOD_VERSION = "aqueduct-bws-v0.1"`, loads a sealed snapshot `aqueduct-amsterdam-v1` |
| `scripts/vendor_aqueduct_water_stress.py` | Snapshot vendor script |
| `scripts/run_water_stress_demo.py` | Demo |
| `tests/nl_pilot/test_water_stress.py` | Tests |
| `docs/nl_pilot/water-stress-context.md` | Docs |
| `frontend/src/App.tsx` | Surfaces "WRI Aqueduct 4.0" as a manifested source |

This landed in `d559cb30ce93ea0d63abc919768fc6c4cac5fe07` —
`feat(nl-pilot): real hazard → EAL five-layer over real Amsterdam BAG assets (#168)`,
authored **2026-08-31**, i.e. one day *after* ADR-0007 was accepted. Separately,
`git grep -i klimaateffectatlas origin/main` returns **no match**: the replacement
indicator ADR-0007 mandates is not implemented anywhere.

So the current state of `main` is the opposite of ADR-0007's implementation note in
both directions — the rejected NL Aqueduct indicator is present and shipped to the
frontend, and the mandated Klimaateffectatlas replacement is absent. The
`app/services/validation_service.py` Aqueduct reference (Turkish Erdemir comparison)
is correctly out of ADR-0007's NL scope and is not part of this finding.

**Verdict — AUTO-PASS on B1.1/B1.2 (close reason and `main` presence are
established). B1.3 was FOUNDER-DECISION**, and the decision is now materially
different from the one the plan anticipated: not "restore or recreate the Aqueduct
pack", but "reconcile `main` with ADR-0007" — remove or re-scope
`app/nl_pilot/water_stress.py` and its frontend claim, and open the Klimaateffectatlas
workstream. GEO-61 should not be closed as Done on the strength of the PR-close alone
while `main` still ships the indicator the ADR rejected.

### B1.3 resolution — decided and executed, 2026-09-01

The founder took the reconciliation option. Executed on this branch:

| Action | Result |
|---|---|
| Commit ADR-0007 | `docs/decisions/ADR-0007-klimaateffectatlas-replaces-aqueduct-nl.md` — transcribed from the PR #132 closing comment, which remains the dated source of record. Closes finding B1-F1 |
| Remove the NL Aqueduct adapter | Deleted `app/nl_pilot/water_stress.py`, `scripts/vendor_aqueduct_water_stress.py`, `scripts/run_water_stress_demo.py`, `tests/nl_pilot/test_water_stress.py`, `docs/nl_pilot/water-stress-context.md`; dropped STUBS.md row 27 |
| Remove the frontend claim | Dropped the `WRI Aqueduct 4.0` evidence-manifest entry, its STALE limitation line and the derived stale counter in `frontend/src/App.tsx` |
| Open the Klimaateffectatlas workstream | `docs/nl_pilot/klimaateffectatlas-indicators.md` — five indicators, seven open gates (G-1…G-7), all `NOT_IMPLEMENTED`. Closes the second half of finding B1-F2 |

The adapter had no importer anywhere in `app/`, and no sealed snapshot existed on
disk (`data/nl_pilot/snapshots/water_stress/` was absent), so it was a dead
fail-closed seam rather than a live part of the five-layer EAL path. Removing it
touched no NL pilot behaviour.

Deliberately untouched, per ADR-0007's own scope: the Turkish Erdemir comparison
reference in `app/services/validation_service.py`, the unconfigured provider seam
in `app/data_centres/water_stress.py`, and the generic `water_stress` compound
driver in `app/scoring/risk_score.py` (derived from land/ocean/agriculture
components, never an Aqueduct quantity).

**Verification at this head** (Python 3.12, live CDS connectivity test deselected
per AGENTS.md):

| Check | Result |
|---|---|
| `pytest -q` | **1572 passed, 1 deselected** |
| `npx tsc -b`, `npx vite build`, `verify-public-assets.mjs`, `npm run test:risk-tiles` | all pass (4/4 tile tests) |
| `founder_ops.py validate-policy`, `pytest tests/automation`, `validate_workflows.sh` | valid policy (9 workflows), 59 passed, clean |
| `verify_eal.py --sample 5 --seed-from-git` + isolation guard | OK, 5 assets verified; 2 passed |

No eligibility flag changed.

---

## 5. D1.1 / D1.2 — PR #174 (GEO-74) CMIP6 horizon fidelity

| Field | Value |
|---|---|
| PR | [#174](https://github.com/ebru0zpolat/georisk-engine/pull/174) — `Add CMIP6 provenance and fidelity grading to horizon scenarios` |
| Head branch | `claude/georisk-p4-cmip6` |
| **Exact head SHA** | `5db3b186c39a0e58032be68d066c802d56fd94ca` |
| Head asserted in plan §D1.1 | `5db3b186c39a0e58032be68d066c802d56fd94ca` |
| **Match** | ✅ confirmed unchanged |
| Merge base | `ab9062083af716f5d711f19949a4188a96768507` (= current `main`) |
| Behind `main` | **0 commits** |
| Ahead of `main` | 3 commits |
| GitHub `mergeable_state` | `clean` |
| Local `git merge-tree` | clean |
| State | open, not draft, 10 files, +644 / −31 |

**CI at this exact head:** run
[33488294461](https://github.com/ebru0zpolat/georisk-engine/actions/runs/33488294461)
(2026-09-01) — `pytest`, `frontend`, `verify-eal`, `dependency-security`,
`founder-operations-phase-1` all `success`; `Vercel Agent Review` `neutral`.

**Verdict — AUTO-PASS on D1.1 and D1.2.** PR #174 is the only PR in the queue whose
green CI is simultaneously (a) at the exact current head and (b) on top of current
`main`. It therefore needs no reconciliation, and its CI result is not subject to the
§1.5 staleness caveat. D1.3–D1.9 (factor invariants, fidelity boundaries, citation
metadata) remain outstanding and are not attested here.

---

## 6. C2.1 / C2.2 — PR #139 (GEO-62) controlled-pilot operations foundation

| Field | Value |
|---|---|
| PR | [#139](https://github.com/ebru0zpolat/georisk-engine/pull/139) |
| Head branch | `feat/geo-62-controlled-pilot-ops` |
| **Exact head SHA** | `cb5b92189e5bfb2b453dae0d1ac23ff934e30782` |
| Merge base | `54564dbec0ff2249b32561193879e769b3a6e68d` |
| Behind `main` | **72 commits** |
| Ahead of `main` | 8 commits |
| GitHub `mergeable_state` | `clean` |
| Local `git merge-tree` | clean — no conflicted paths |
| State | open, not draft, 10 files, +3117 |

**C2.2 — which modules are still required.** Every path in the PR is absent from
current `main`, so none of the diff has been superseded by a later merge:

| Path | On `main`? |
|---|---|
| `app/ops/__init__.py` | absent |
| `app/ops/config.py` | absent |
| `app/ops/evidence.py` | absent |
| `app/ops/readiness.py` | absent |
| `app/ops/retention.py` | absent |
| `app/ops/smoke.py` | absent |
| `docs/ops/controlled-pilot-operations-runbook.md` | absent |
| `tests/ops/__init__.py` | absent |
| `tests/ops/test_geo62_controlled_pilot.py` | absent |
| `tests/ops/test_geo62_security_hardening.py` | absent |

**Verdict — AUTO-PASS.** PR #139 is 72 commits behind but conflict-free, and 10 of 10
files are still needed. Its own CI evidence is from 2026-08-23 at a merge base that is
72 commits stale, so under §1.5 it validates nothing about a reconciled head.

---

## 7. C2.3 / C2.4 — PR #145 base and dependency verification

| Field | Value |
|---|---|
| PR | [#145](https://github.com/ebru0zpolat/georisk-engine/pull/145) — `ci: add controlled-pilot release workflow, authenticated smoke script, and retention evidence capture` |
| Head branch | `codex/deploy-secrets-for-controlled-pilot-gate` |
| **Exact head SHA** | `793a9cfb491d49a195f2c0c5c055830f5e4f82ab` |
| Declared base ref | `main` |
| Merge base with `main` | `1903f074f97db0f779905add6474fe6f824441f3` |
| Behind `main` | **66 commits** |
| Ahead of `main` | 1 commit |
| State | **draft**, 5 files, +307, label `codex` |

**C2.3 finding — #145 is NOT stacked on #139.** Its base ref is `main`, its single
commit descends from `1903f074`, and `git merge-base` against `pr139` is not on the
#139 branch. The two PRs also share **zero changed files**:

| PR #139 | PR #145 |
|---|---|
| `app/ops/*` (6 modules), `tests/ops/*`, `docs/ops/…runbook.md` | `.github/workflows/controlled-pilot.yml`, `scripts/controlled_pilot_smoke.py`, `tests/test_controlled_pilot_smoke.py`, `docs/08-ops/API_DEPLOY.md`, `.env.example` |

There is no file-level dependency in either direction. They are independent branches
that were opened against the same objective one day apart.

**C2.4 preliminary (recorded, not yet decided).** The two PRs are functionally
duplicated on the smoke path and complementary on retention:

- *Duplicated — authenticated smoke.* Both implement the same three assertions:
  unauthenticated access must be rejected, `/v1/health` must report the approved
  `git_sha`, and the emitted JSON evidence must contain no credential.
  #139 does it as a library (`app/ops/smoke.py`, with URL/IP validation, a
  no-redirect transport and header redaction); #145 does it as a script
  (`scripts/controlled_pilot_smoke.py`, HTTPS-only, plus a golden Antalya demo-run
  verification). Shipping both would give the pilot two smoke implementations.
- *Not duplicated — durable retention.* #139's retention backends are
  `InMemoryRetention`, `TempDirRetention` and `DisabledRetention` — write-once but
  **not durable**, which is why the PR itself declares
  `DURABLE_RETENTION_VERIFIED=false`. #145 supplies the durable half: an S3
  `COMPLIANCE`-mode Object Lock put with a ≥365-day retain-until date, verified by
  reading `ObjectLockMode` and `ObjectLockRetainUntilDate` back. Nothing in #139
  covers this, and plan §C2.11/§C2.12 require it.

This suggests the C2.5 single operations PR should take #139's module layer plus
#145's release workflow and object-lock retention, and drop one of the two smoke
implementations. **That composition is a FOUNDER-DECISION (plan §11.6) and is
recorded here as a proposal only.**

**Verdict — AUTO-PASS on C2.3.** Base and dependency relationship established:
independent, not stacked, no file overlap.

---

## 8–10. Commercial micro-tasks

| Task | Artefact | Verdict |
|---|---|---|
| E1.1 — pilot overview first draft | [`docs/05-commercial/PILOT_PACKAGE_OVERVIEW.md`](../../05-commercial/PILOT_PACKAGE_OVERVIEW.md) | AUTO-PASS — v0.1 draft landed |
| E4.1 — ICP scoring rubric | [`docs/05-commercial/ICP_SCORING_RUBRIC.md`](../../05-commercial/ICP_SCORING_RUBRIC.md) | AUTO-PASS — rubric landed and frozen for the first 10 accounts |
| F1.1 — data-provider category | [`docs/05-commercial/DATA_PROVIDER_LOI_CATEGORY_DECISION.md`](../../05-commercial/DATA_PROVIDER_LOI_CATEGORY_DECISION.md) | FOUNDER-DECISION — options and a recommendation recorded; §11.8 reserves the choice |

None of these three is customer evidence. No prospect conversation, LOI, agreement or
revenue is claimed by any of them (plan §1.3, §12).

---

## Appendix — additional finding: PR #136 (GEO-199, AHN) conflicts with `main`

Produced while running the same reconciliation sweep. Relevant to B2.1/B2.2.

| Field | Value |
|---|---|
| PR | [#136](https://github.com/ebru0zpolat/georisk-engine/pull/136) |
| **Exact head SHA** | `8f7dd592f246a5c6a3eab44ea1f196f76c0eef77` |
| Head asserted in plan §B2.1 | `8f7dd592f246a5c6a3eab44ea1f196f76c0eef77` — ✅ match |
| Merge base | `54564dbec0ff2249b32561193879e769b3a6e68d` |
| Behind `main` | **72 commits** |
| Ahead of `main` | 10 commits |
| Local `git merge-tree` | **CONFLICT** |

Conflicted path: `app/nl_pilot/__init__.py` — `CONFLICT (add/add)`. `requirements.txt`
and `tests/nl_pilot/__init__.py` auto-merge. This is the only PR in the queue that
does not merge cleanly, so B2.2 is real reconciliation work rather than a
fast-forward.

---

## Eligibility flags — unchanged by this record

| Flag | Before | After | Reason |
|---|---|---|---|
| `production_eligible` | false | false | No production evidence produced |
| `controlled_pilot_eligible` | false | false | No deployment, smoke or retention evidence produced |
| `runtime_live_verified` | false | false | No live runtime call was made |
| `authenticated_smoke_passed` | false | false | No smoke was executed |
| `durable_retention_verified` | false | false | No durable storage was written |
