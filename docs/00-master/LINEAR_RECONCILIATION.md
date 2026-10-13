# Linear ↔ repository reconciliation

> **Applied to Linear on 21 Aug 2026.** The Linear connector was authorized and the
> reconciliation below was carried out. See **Applied changes** for exactly what was written.
> The tables remain as the derivation record — regenerate them from repo state before the
> next sync rather than trusting them as current.

## Applied changes

**State corrections** — both were about PR #126, which merged on 21 Aug as `836a55a`:

| Issue | Was | Now |
|---|---|---|
| GEO-73 [P0] Canonical data-centre vulnerability contract + GitHub #126 reconciliation | In Progress | **Done** |
| GEO-60 [P0] GitHub #126 review blockers — profile/pathway, cutoff, cooling bridge | Todo | **Done** |

Both carry a closure note recording the merge SHA, the empty `git diff c9b4792 main`, the
verified gates (`production_release="none"`; EAL / downtime / BI all `None`-typed), and that
the P2 remainder lives in GitHub issue #129, still open.

**GEO-61 collision resolved.** GEO-61 is the *Aqueduct water-stress NL pack* — PR #132. PR
#136 had borrowed the id for different work and now has its own issue. A note on GEO-61
records the split and flags that #132's body still claims "PR #126 remains unmerged".

**Issues created** — one per active PR that had none:

| Issue | PR | Project |
|---|---|---|
| GEO-197 Versioned EU Taxonomy / ESRS E1 regulatory evidence registry | #133 | Methodology, Validation & Auditability |
| GEO-198 NACE evidence input + AHN/NCG metadata-only roadmap sources | #134 | Methodology, Validation & Auditability |
| GEO-199 WP-NL02/NL02B — Netherlands AHN pilot foundation | #136 | Netherlands/RVO Market Entry |
| GEO-200 [Frontend] Spatial risk taxonomy hub + evidence-aware routes | #135 | Product & Deployment |
| GEO-201 Keep blocked evidence out of data-centre pathway conclusions | #128 | Methodology, Validation & Auditability |
| GEO-202 Close-out decision on 19 stale open PRs (Backlog) | Group C below | Product & Deployment |
| GEO-203 Close-out decision on 11 stacked open PRs (Backlog) | Group B below | Product & Deployment |

Each links its PR as an attachment.

**Confirmed correct, unchanged:** GEO-173 and GEO-177 In Progress, GEO-191 Backlog — exactly
as PR #108 asserts.

**No archiving was done.** The workspace was upgraded, so the free-tier issue limit that
originally blocked issue creation no longer applies. Table 1 is kept as a record of what is
finished, not as a pending action.

## Snapshot

| | |
|---|---|
| Generated | 2026-08-21 |
| Applied to Linear | 2026-08-21 |
| Linear team | Georiskengine (196 issues at read time) |
| `origin/main` | `836a55a` |
| Open PRs | **36** |
| Merged onto `main` since 2026-08-14 | **10** |
| Open PRs carrying a discoverable Linear id | **3** (#108, #132, #136) |
| Linear ids found anywhere in open PR bodies | `GEO-61`, `GEO-173`, `GEO-177`, `GEO-191` |
| Workspace | `linear.app/georiskengine` (from PR #108) |

`GEO-` identifiers do **not** appear in any `main` commit message, so the PR↔issue mapping
cannot be recovered from git history. The three PRs above are the only machine-readable link
between this repository and the board.

---

## Table 1 — Completed work (originally derived as archive candidates)

Derived when archiving was needed to free slots under the free tier. The workspace has
since been upgraded, so no archiving was performed — this stands as the record of what is
finished. All ten merged on 2026-08-15 except #126.

| PR | Title | Merge commit on `main` |
|---|---|---|
| #119 | fix(oras5): fail closed on unscorable series | `1c40e0c` |
| #120 | chore(validation): ORAS5 evidence gates + validation tooling | `0401fa8` |
| #121 | fix(runtime): prohibit connector stubs in production | `a5d8c63` |
| #122 | fix(data-centres): close PR #115 review defects | `3b83d98` |
| #123 | feat(vulnerability): add data-centre engineering contract | `4371930` |
| #115 | feat(data-centres): harden decision-support contract on Gate-1 | `7e7e68a` |
| #124 | fix(runtime): stop labelling the live CDS read as a connector stub | `bce5142` |
| #127 | Fix liquid cooling forever-indeterminate and unknown-water clear | `e556afe` |
| #125 | fix(data-centres): fail closed on unknown water dependency in cooling | `91476b2` |
| #126 | Reconcile #115 assessment onto the #123 vulnerability contract | `836a55a` (2026-08-21) |

Closed without merging, superseded by #132:

| PR | Why closed |
|---|---|
| #130 | raster-flavored v0.1, superseded |
| #131 | same vector contract, wrong branch name, superseded |

Verified: neither `#130` nor `#131` appears in any commit reachable from `main`.

---

## Table 2 — Open PRs → required Linear state

`action` column: **link** = issue exists, attach the PR and correct its state · **create** =
no issue found, create one · **close** = confirm the PR is abandoned, then close it and its
issue.

### Group A — active, `main`-based (6)

| PR | Head | Draft | Linear id | Action |
|---|---|---|---|---|
| #136 WP-NL02/NL02B AHN pilot foundation | `487149c8` | no | GEO-61 | link — body asserts **In Review** |
| #135 spatial risk taxonomy hub | `04715a5a` | no | — | create |
| #134 NACE evidence input, AHN/NCG metadata sources | `afcec53b` | yes | — | create |
| #133 versioned EU Taxonomy/ESRS E1 evidence registry | `01be31c` | yes | — | create |
| #132 vector Aqueduct 4.0 NL water-stress pack | `0f02b8a` | yes | GEO-61 | link — **id collides with #136** |
| #128 keep blocked evidence out of pathway conclusions | `fc79116` | no | — | create |

All six state `production_eligible=false`; #132 and #136 say **do not merge**.

### Group B — stacked chains on non-`main` bases (11)

Each PR targets the previous PR's branch, so none can merge until its parent does. If the
stack is dead, close it from the tip down.

**RVO documentation stack** — #87 is the only one based on `main`:

| PR | Head | Base | Action |
|---|---|---|---|
| #87 Dutch pilot template & design-partner package (ws 01) | `08e0f504` | `main` | create or close |
| #88 source licensing & production-status matrix (ws 02) | `289b7526` | #87's branch | create or close |
| #89 flood/heat backtesting evidence design (ws 03) | `6c8515d5` | #88's branch | create or close |
| #90 NL calibration & independent challenge plan (ws 04) | `e8bbcd7e` | #89's branch | create or close |
| #91 claim-to-evidence register (ws 05) | `bd807868` | #90's branch | create or close |
| #92 36-month financial model scaffold (ws 06) | `8d23ab7d` | #91's branch | create or close |
| #93 pilot/LOI commercial evidence register (ws 07) | `d833e33f` | #92's branch | create or close |

**WP-08 / WP-10 stack:**

| PR | Head | Base | Linear id | Action |
|---|---|---|---|---|
| #108 WP-08 CDS preprocess + 2030/2050 heat intensity maps | `ce58a84e` | `main` | GEO-177, GEO-173, GEO-191 | link — see Table 3 |
| #109 observed-loss benchmark gates | `a97cf455` | #108's branch | — | create or close |
| #110 Annex C typed controls and loss pathway | `e3608f1e` | #109's branch | — | create or close |
| #116 preregister Harvey observed-loss reconstruction | `2575bf3b` | #110's branch | — | create or close |

### Group C — stale `main`-based singletons (19)

None updated since 2026-08-14; the oldest is from 2026-05-01. Tracked as a batch in
**GEO-202**.

Five of these (#96, #56, #55, #51, #64) proposed honesty fixes to public-facing claims. Those
fixes **were made, by other routes** — verified on `main` at `836a55a`: no testimonial content
in the frontend, and the only remaining `href="#"` is a JS-driven download button in
`app/static/index.html`. They are superseded, not pending, and safe to close.

Four others are worth reading before closing rather than batch-closing: **#112** (CI coverage
gate, no equivalent on `main`), **#105** (DataProvenance/damage-proxy, overlaps GEO-197/198),
**#106** (Climate Decision Record, may have no other home), **#58** (NL data plane, adjacent
to GEO-199).

| PR | Head | Draft | Last updated |
|---|---|---|---|
| #114 Enforce canonical positioning, evidence gates, P0 pilot contract | `3b544510` | yes | 2026-08-13 |
| #112 raise coverage on edge modules + CI coverage gate | `e0954cc6` | no | 2026-08-13 |
| #111 docs(business): accelerator & facilitator reality check | `28ee7a7e` | no | 2026-08-14 |
| #106 Phase 1 Climate Decision Record draft (extreme heat) | `9f30e0f0` | yes | 2026-08-07 |
| #105 DataProvenance + scenario damage-proxy metrics (WP-03/04) | `9a43ede7` | yes | 2026-08-07 |
| #96 fix(web): zero-placeholder links and honest CTAs | `f0943b42` | yes | 2026-08-07 |
| #77 deploy: FastAPI backend (Railway) + CORS | `c5797188` | no | 2026-08-06 |
| #64 chore: replace ESG/climate-map framing | `92501735` | no | 2026-08-05 |
| #61 fix: ship React landing demo + CORS/Render path | `d071dc97` | no | 2026-07-31 |
| #58 Netherlands data plane — KNMI / PDOK / Open-Meteo | `a7e27f10` | yes | 2026-07-20 |
| #57 MVP: working demo + real preview scorecard | `c848fe05` | yes | 2026-07-20 |
| #56 Align website claims with shipped repo API surface | `cf5170be` | yes | 2026-07-20 |
| #55 remove fake testimonials and dead homepage links | `88b6ced3` | yes | 2026-07-20 |
| #51 align homepage with real data-source inventory | `53d54382` | no | 2026-07-09 |
| #50 docs: monetization one-pager HTML | `f2e6988d` | yes | 2026-07-09 |
| #19 Add UI/UX Pro Max skill for Cursor | `89a63e9c` | yes | 2026-05-19 |
| #18 Add Impeccable frontend design skill | `1fe6999f` | yes | 2026-05-19 |
| #6 docs: Turkey corridor, BEST demo, GEE setup, investor pitch | `32113fd1` | no | 2026-05-01 |
| #2 Streamlit: Türkiye çimento pilot + corporate PDF | `f6679210` | no | 2026-05-01 |

---

## Table 3 — Contradictions found, and their disposition

| # | Contradiction | Evidence |
|---|---|---|
| 1 | **GEO-61 had two open PRs describing different work** — #132 Aqueduct water-stress, #136 AHN elevation pilot. | **Resolved.** GEO-61 keeps #132; #136 became GEO-199. Note added to GEO-61. |
| 2 | **33 of 36 open PRs had no discoverable Linear id.** | **Resolved for the 5 active ones** (GEO-197/198/199/200/201). The remaining 30 are batched: 11 stacked chains in GEO-203, 19 singletons in GEO-202. |
| 3 | **PR #108 pins three issue states.** Its body says GEO-177 and GEO-173 stay *In Progress* and GEO-191 stays *Backlog*. | **Verified correct** against the board on 21 Aug. No change made. #108 itself is `mergeable_state: dirty` and untouched since 14 Aug — flagged in GEO-203. |
| 4 | **PR #132's body claims "PR #126 remains unmerged."** #126 merged 21 Aug as `836a55a`. | **Open.** Not fixed here — #132 is someone else's draft and was not touched. Flagged on GEO-61 for whoever next edits the PR. |
| 5 | **Every open PR is behind `main`.** All 36 opened against `91476b2` or earlier. | **Open.** Inherent to the merge; each PR owner rebases or merges base when they resume. |

---

## Method note, for the next sync

Nothing here assumed an issue existed — every row said *find it, or create it*, and a failed
lookup was recorded as data rather than resolved by inventing an id. Keep that rule: the
board and the repo drift in both directions, and three separate relayed reports during this
work referenced superseded SHAs.

To redo this sync: re-read the board, re-list open PRs (paginate — there were 36 across two
pages), and regenerate Tables 1–3 from that. Do not trust the tables above as current.
