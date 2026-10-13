# TSKB and Anadolu Sigorta — first-call preparation packet

**Version:** v0.1 draft
**Date:** 2026-09-04
**Lane:** Türkiye (isolated lane; cannot touch NL readiness, CI reservation or priority — see
[`FOUNDER_AUTOMATION_OPERATING_ROADMAP.md`](../00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md) §3)
**Operating class:** AUTO-PASS *preparation* (brief, agenda, evidence table, drafts,
missing-evidence list). **Every external action in this document is FOUNDER-DECISION**: sending a
message, naming either institution outside this repo, ingesting their asset list, agreeing a price,
signing anything. Nothing here has been sent to anyone.

---

## 0. Send gate — no verified demo asset, no outreach

Nothing in §8 is sent unless a **rehearsal record** exists at the SHA the analysis would be
delivered from, showing that every analysed demo asset was independently recomputed from its own
audit-trail record and agreed to the cent. If the engine cannot prove that on the synthetic golden
portfolio, it has nothing to offer either institution, and the call is not made.

| Requirement | How it is satisfied |
|---|---|
| Rehearsal run at the current SHA | `PYTHONPATH=. python scripts/rehearse_free_analysis_pack.py --trail /path/outside/repo/audit_trail.jsonl` |
| Audit trail outside the repository | The script refuses any trail path that resolves inside the checkout |
| Every analysed asset independently verified | `independent_verification.failures == 0` in the record; one FAIL fails the run |
| At least 20 assets analysed (the offer's lower bound) | `coverage.analyzed_count >= 20` |
| Release manifest travels with the pack | `decision == demo_only`, `production_eligible == false` |
| Record committed | [`evidence/free_analysis_rehearsal.json`](./evidence/free_analysis_rehearsal.json) — `send_gate_satisfied: true` |

The record is bound to the `commit_sha` it names. A later code change to the pipeline, curves,
verifier or manifest invalidates it: re-run before sending, and re-run again at the delivery SHA.
The test `tests/portfolios/test_free_analysis_rehearsal.py` keeps the gate honest in CI.

---

## 1. Why these two, in this order

**TSKB (Türkiye Sınai Kalkınma Bankası) — first call.** Development bank with a climate mandate,
sophisticated on ESG, and small enough that a thirty-minute conversation can reach the person who
actually produces the physical-risk section of their sustainability report. They are a TSRS
(Türkiye Sürdürülebilirlik Raporlama Standartları) preparer, so the evidence problem is theirs
today, not hypothetically.

**Anadolu Sigorta — second call, the insurer angle.** Same regulatory frame from the underwriting
and reserving side: they hold the physical exposure directly, and they have to explain their
physical-risk view to a different set of reviewers. The conversation is different (loss and
accumulation, not collateral), so it is a second call, not a copy of the first.

**What the two calls test.** One question, from two seats at the same table: *how do you produce
physical-risk evidence for TSRS today, and who has to defend it?* The product's claim is that
reproducible, fail-closed evidence is worth more than a score. Either these two confirm that
someone is accountable for defending those numbers (rubric dimension D3), or they tell us nobody is
— which is the clearest possible "does not fit" signal and is worth a weekend on its own.

**Rubric note.** The frozen [`ICP_SCORING_RUBRIC.md`](./ICP_SCORING_RUBRIC.md) v1.0 scores the
**NL CRE pilot** only; a Türkiye account scores D1 = 0 there by construction and must not be
entered into that queue. Both accounts are tracked under the long-run segment view in
[`ICP.md`](./ICP.md) (Türkiye / TSRS) and the Türkiye lane. A TR-specific rubric is not defined;
do not improvise one before the first two conversations produce something to calibrate it on.

---

## 2. The ask: thirty minutes, discovery, not a pitch

Ask for thirty minutes to understand how they produce physical-risk evidence for TSRS. No deck.
The meeting is a structured interview and counts toward Gate 2.1 (fifteen structured buyer
interviews, [`SIX_MONTH_VALIDATION_GATES.md`](../business/SIX_MONTH_VALIDATION_GATES.md)) only if
it is run against the fixed script below and the notes record segment and role.

### 2.1 Discovery script (fixed — do not reorder in the meeting)

| # | Question | What the answer tells us |
|---|---|---|
| 1 | Walk me through how the physical-risk figures in your last TSRS report were produced. Who touched them, in what order? | Workflow, tooling, whether a vendor score is being copied through |
| 2 | Who reviewed or challenged those figures before publication? Internal audit, external assurer, a committee? | D3 evidence burden — the dimension the product addresses |
| 3 | When a reviewer asks "where does this number come from", what do you hand them today? | Whether provenance is a felt pain or a theoretical one |
| 4 | What did you do with assets where the data was missing or you didn't trust it? | Whether fail-closed is a feature to them or an inconvenience |
| 5 | Which assets are in scope — count, type, where the location and value data lives, and in what format? | Data readiness (D5), and whether 20–50 assets is a natural first cut |
| 6 | What is the next dated deadline where these figures have to be produced again? | Regulatory pressure (D2), with a date |
| 7 | If a small, reproducible analysis of twenty to fifty of your assets landed on your desk next month, who else would want to see it? | Buyer accessibility (D4), and who the executive sponsor might be |
| 8 | What would have to be true for a physical-risk evidence tool to be bought rather than trialled? Budget line, approver, timeline. | Procurement route (2.6) and willingness to pay (2.7) — asked, not assumed |

Question 7 is where the offer in §3 is placed, and only if questions 1–4 show that someone is
accountable for the numbers. If nobody is, thank them, record the finding, and do not make the
offer — a free analysis to a team with no reviewer teaches us nothing.

### 2.2 Insurer variant (Anadolu Sigorta)

Replace questions 5 and 7 with:

| # | Question |
|---|---|
| 5i | Which insured or owned locations are in scope — property book, own premises, or both? Where does the location data live and who owns it? |
| 7i | If a reproducible per-location physical-risk analysis for twenty to fifty locations landed with underwriting or reserving next month, who would want to see it, and what would they compare it against? |

Do not discuss pricing models, loss ratios, or reinsurance. The product does not model annual
exceedance probability (see §4.3) and must not be positioned as an actuarial input.

---

## 3. The offer that gets a yes

A free analysis of **twenty to fifty** of their assets, delivered as the standard output with the
provenance manifest and fail-closed tags, in exchange for a **structured feedback session**
(§6). It costs a weekend of founder time (§5), gives them something concrete, and gives us either a
design partner or a clear reason the product does not fit. Both are valuable; the second is not a
failure.

**What the offer is not.** It is not a pilot, not a proof of concept for procurement, and not a
free version of the NL pilot package. It does not close Gate 2.2 (one *paid* design partner); a
free analysis is interest, and is recorded as interest. It carries no support, no SLA, no
re-runs, and no commitment beyond the delivery and one session.

**Scope wording to use with them (EN):**

> A one-off, reproducible physical-risk evidence pack for 20–50 of your assets, on our current
> methodology version, with every number traceable to a sealed input and a recorded method
> version, and every asset we could not analyse listed with the reason. In return, ninety minutes
> of structured feedback from the person who has to defend these figures. No charge, no
> obligation, no reuse of your data beyond the analysis.

**Scope wording (TR):**

> 20–50 varlığınız için, mevcut metodoloji sürümümüz üzerinde, tek seferlik ve yeniden
> üretilebilir bir fiziksel risk kanıt paketi. Her sayı mühürlenmiş bir girdiye ve kayıtlı bir
> yöntem sürümüne izlenebilir; analiz edemediğimiz her varlık gerekçesiyle listelenir. Karşılığında,
> bu rakamları savunmak zorunda olan kişiden doksan dakikalık yapılandırılmış geri bildirim. Ücret
> yok, taahhüt yok, verinizin analiz dışında kullanımı yok.

---

## 4. What "standard output with the provenance manifest and fail-closed tags" actually is

This section is the evidence table. Every row names the artefact that exists on `main` today, so
that nothing is promised in a meeting that the repository cannot produce.

### 4.1 Deliverable contents

| # | Deliverable | Produced by | What the recipient sees |
|---|---|---|---|
| 1 | Per-asset five-layer result (hazard → exposure → vulnerability → expected loss → adaptation) | `POST /v1/portfolio/demo-run` (`app/api/portfolio.py`), ≤500 assets, `max_assets` cap | One row per analysed asset: hazard composite, EAL now / 2030 / 2050, recommended measure, avoided loss, residual EAL, audit record id, methodology and curve versions, calibration badge |
| 2 | Coverage summary and exclusion list | `CoverageSummary` in `app/schemas/portfolio_demo.py` | "Analysed N of M assets"; every excluded asset listed with its reason. Nothing is silently dropped |
| 3 | Methodology stamp | `MethodologyStamp` — `georisk-methodology-v0.3.1`, `expected-loss-v0.3`, damage-curve and adaptation-evidence versions | The exact method version each number was produced under, citable to [`GEORISK_ENGINE_METHODOLOGY.md`](../methodology/GEORISK_ENGINE_METHODOLOGY.md) |
| 4 | Hash-chained audit records | `AppendOnlyAuditTrail` (`app/services/audit_trail.py`); one record per EAL computation | An `eal_audit_record_id` per asset that a third party can replay |
| 5 | Independent recomputation | `scripts/verify_eal.py` → `verification_report.md`; verifier is code-isolated from the pipeline (`tests/verification/independent_eal.py`) | A report showing pipeline EAL and independently recomputed EAL agree to the cent — this proves **reproducibility**, not accuracy |
| 6 | Release manifest | `GET /v1/release-manifest` (`app/schemas/release_manifest.py`) | `decision: demo_only`, `production_eligible: false`, listed limitations and prohibited uses. This travels with the pack; it is not optional |
| 7 | Reproducibility record | Commit SHA, input file SHA-256, catalogue ids and versions | Enough for them to have someone re-run it at the recorded SHA and get byte-identical output |
| 8 | Walkthrough | One ninety-minute session (§6) | The feedback session doubles as the walkthrough |

### 4.2 Fail-closed tags — what the phrase means to them, concretely

| Situation | What the pack does | What it never does |
|---|---|---|
| Asset has no coordinates and no resolvable address | Listed under `excluded` with reason | Guess a location |
| Hazard source for a location is not qualified (`app/loss/flood_source_qualification.py`) | Labelled synthetic, calibration badge stays synthetic | Substitute a real-looking number |
| A required input field is missing | Row is excluded and named | Fill a plausible default |
| Method or catalogue version cannot be resolved on replay | Replay fails with an error | Fall back to "current" |
| Anything the engine cannot establish from a named source | Stays visibly unresolved | Gets filled with a default and moves on |

The pitch of the fail-closed tag is a single sentence: *everything we could not establish is
listed, not hidden.* That is the sentence a reviewer wants to hear, and it is the one competitors'
score sheets cannot say.

### 4.3 Honesty box — what the analysis is, and is not (say this in the meeting)

- Every damage curve on `main` is a **labelled synthetic v0.x curve** (`STUBS.md`). The pack's
  calibration badge says so on every row. Numbers are a **versioned physical-risk proxy under
  stated data and assumptions**, reproducible to the cent, not observationally validated loss.
- "EAL" on this methodology version is a **scenario damage proxy**, not actuarial expected annual
  loss: no exceedance probability, no return-period integration, no direct-damage versus
  business-interruption split ([`app/loss/METHODOLOGY.md`](../../app/loss/METHODOLOGY.md)).
- Hazard intensities for Türkiye come from the **global stub pipeline**, the same one the Antalya
  golden portfolio runs on. There is no calibrated `pack-tr` hazard layer. If they need real
  Turkish flood or heat hazard data before the analysis is useful, that is a fit finding, not a
  reason to overstate what exists.
- **Hazard coverage is flood, extreme heat, wildfire and earthquake** (methodology
  `georisk-methodology-v0.4.0`), and all four are labelled synthetic: stub intensities
  (`hazard-stub-v0.2`, `STUBS.md` #16a) priced through synthetic curves (`stub_global_mdr-v0.2.0`).
  Expect both institutions to ask about earthquake first (post-2023) and wildfire second
  (Manavgat 2021). The answer is that **both are modelled end to end and independently
  reproducible, and neither is calibrated**: the earthquake module needs a real seismic-hazard
  source (AFAD TDTH PGA) and refuses to run without one outside the labelled demo field; the
  wildfire module runs on a temperature proxy until a fire-danger (FWI) raster is wired. Earthquake
  is a geophysical, non-climate peril, is held stationary across the 2030 / 2050 horizons, and is
  reported with `hazard_class: geophysical`. Do not cite Manavgat 2021 or Kahramanmaraş 2023 as
  backtests. If they need calibrated seismic or fire hazard before the analysis is useful, that is
  the next data-vendoring step, and their answer to which source they trust is itself a finding.
- Nothing in the pack is a TSRS compliance determination, an assurance opinion, a second-party
  opinion, or a basis for a lending, underwriting or capital decision without their own review.
- `production_eligible` is `false` and the release decision is `demo_only`. Neither this document
  nor the analysis changes that.

### 4.4 Prohibited claims (mirror of the NL pilot list plus the `pack-tr` scanner)

Neither party may describe the analysis with any wording in the left column. The `pack-tr`
prohibited-phrase list in `app/packs/tr/sustainable_finance/claims.py` is authoritative; run it
over any written deliverable before it leaves the repo (§11 step 5). This packet passes that scan.

| Prohibited wording | Permitted wording instead |
|---|---|
| certified, approved, compliant, TSRS compliant, SPK/CMB approved | Supports selected evidence needs under the named standard or guideline |
| an audit, an assurance opinion, a verification report, a second-party opinion | Reviewer-oriented evidence bundle |
| independently validated empirical accuracy | Independently reproducible calculation record |
| prediction of actual loss | Versioned physical-risk proxy under stated data and assumptions |
| complete climate-risk assessment | Supports prioritisation and further investigation |
| production-grade, production-eligible, pilot-ready | Demonstration output; `production_eligible=false` |

---

## 5. Cost — "a weekend" measured honestly

Gate 2.8 requires *measured*, not estimated, delivery cost. Compute is not the cost: the §11
runbook, rehearsed on the Antalya golden portfolio on 2026-09-04, analysed 50 assets and
independently recomputed all 50 from their trail records in about one second on a laptop-class
container. The weekend is founder time. Log actual hours against this table when the first
analysis is delivered, and replace the estimates.

| Step | Estimate | Actual (fill in) |
|---|---|---|
| Intake: receive asset list, check licence and boundary checklist (§7), map columns to `asset_id, latitude/longitude or address, asset_value, building_type, use_class` | 2 h | |
| Geocoding and location QA for address-only rows; record every exclusion | 3 h | |
| Run `POST /v1/portfolio/demo-run`, `scripts/verify_eal.py`, capture release manifest and SHAs | 1 h | |
| Assemble the pack: narrative export, exclusion list, methodology stamp, reproducibility record, honesty box | 4 h | |
| Claim scan over every written page; internal read-through against §4.4 | 1 h | |
| Feedback session (§6) and write-up | 2 h | |
| **Total** | **~13 h** | |

Out-of-pocket cost: none if run locally. If a hosted environment is used, the C2 controlled-pilot
operations evidence (authenticated smoke, retention) is still open — deliver from a local run at a
recorded SHA rather than from an unverified hosted deployment.

---

## 6. The structured feedback session (the price of the free analysis)

Ninety minutes, with the person who defends the numbers in the room. Fixed agenda so the two
sessions (bank, insurer) are comparable.

| Min | Block | Output |
|---|---|---|
| 0–10 | Reproducibility record: they pick an asset, we replay it live at the recorded SHA | Does "reproducible" register as valuable? |
| 10–30 | Walk five assets: numbers, method stamp, audit record, calibration badge | Which field do they look at first? Which do they ignore? |
| 30–45 | Exclusion list: every asset we refused to analyse, with reason | Is fail-closed a feature or an irritant to them? Which exclusion reasons are unacceptable? |
| 45–60 | Their reviewer's view: what would the auditor / assurer / committee ask about this pack? | The list of what is missing for their review, in their words |
| 60–75 | Fit questions (fixed): Would you put this in front of your reviewer? What would you need changed first? Who would pay for it, from what budget, and when is the next deadline? | Sponsor, dataset, success criteria, procurement route, price — Gate 2.3–2.7 raw material |
| 75–90 | Decision: design partner conversation, or a written "does not fit because" | One of the two outcomes below |

**Outcome A — design-partner conversation.** They name a sponsor, a dataset and a next deadline.
Move to the NL-style pilot scope conversation with a **paid** framing; a free analysis is not
extended into a free pilot. Only money or a signed procurement commitment closes Gate 2.2.

**Outcome B — does not fit.** Record the reason verbatim in the interview notes. Common expected
reasons, so they are recognised and not argued with in the room: they need calibrated Turkish
hazard data before any proxy is useful; nobody reviews these figures; the TSRS section is
outsourced to a consultancy and the bank does not see the workings; the insurer needs annual
exceedance probability, which this methodology version does not model. Each is a product finding.

Both outcomes are logged the same way (§9).

---

## 7. Real-data boundary checklist — FOUNDER-DECISION before ingesting anything

Synthetic fixtures are the default. Ingesting a real asset list from either institution is a
founder decision on privacy and contract risk. Do not accept a file until every row is answered.

| # | Check | Answer before intake |
|---|---|---|
| 1 | Written permission from the institution to use the list for this analysis only | |
| 2 | NDA or equivalent confidentiality wording in place, covering both directions | |
| 3 | No personal data: no borrower names, no individual policyholders, no national ids. Asset ids are theirs and opaque | |
| 4 | Fields limited to what the pipeline consumes (`asset_id`, location, `asset_value`, `building_type`, `use_class`, optional `construction_year`, `floors`, `insurance_coverage`, `ltv`) | |
| 5 | Their licence permits them to share location and value data with a third party for analysis | |
| 6 | Retention: the file lives outside the repo, is never committed, and is deleted at an agreed date after the session. Deletion is a founder-authorised action | |
| 7 | The pack returned to them contains no field they did not send, apart from computed outputs | |
| 8 | Reuse: none. No aggregation into any public figure, no naming of the institution anywhere, including this repo, without a separate founder decision | |

If any row cannot be answered, the analysis runs on the Antalya golden portfolio as a
demonstration instead, and that is said plainly.

---

## 8. Draft messages — withheld until the founder sends them

Drafts in the founder's voice. **Not sent.** Names and roles are left as placeholders on purpose:
this repo holds no verified contact at either institution, and inventing one is a prohibited
partner claim. Fill from a verified source (§10) before sending. Keep the message short; the
meeting is the pitch, and there is no deck to attach.

### 8.1 TSKB — email (TR)

> **Konu:** TSRS fiziksel risk kanıtı — 30 dakikalık görüşme ricası
>
> Sayın [Ad Soyad],
>
> GeoRisk Engine'i geliştiriyorum: varlık düzeyinde fiziksel iklim riskini, her sayının
> mühürlenmiş bir girdiye ve kayıtlı bir yöntem sürümüne izlenebildiği, kanıt odaklı bir çıktıya
> dönüştüren bir motor.
>
> Bir ürün sunmak için değil, öğrenmek için yazıyorum. TSKB'nin TSRS raporlamasında fiziksel risk
> kanıtını bugün nasıl ürettiğini — kimin hazırladığını, kimin sorguladığını ve eksik veride ne
> yapıldığını — anlamak için otuz dakikanızı rica ediyorum.
>
> Görüşme faydalı olursa, 20–50 varlığınız için ücretsiz ve yeniden üretilebilir bir analizi,
> tek bir yapılandırılmış geri bildirim oturumu karşılığında sunmak isterim.
>
> Saygılarımla,
> Ebru Özpolat

### 8.2 TSKB — email (EN)

> **Subject:** Physical-risk evidence for TSRS — a thirty-minute conversation
>
> Dear [Name],
>
> I am building GeoRisk Engine, an engine that turns asset-level physical climate risk into
> evidence: every number traceable to a sealed input and a recorded method version, and every
> asset it cannot establish listed rather than filled in.
>
> I am writing to learn, not to pitch. I would value thirty minutes to understand how TSKB produces
> physical-risk evidence for TSRS today: who prepares it, who challenges it, and what happens when
> the data is missing.
>
> If the conversation is useful, I would like to offer a free, reproducible analysis of 20–50 of
> your assets in exchange for one structured feedback session.
>
> Kind regards,
> Ebru Özpolat

### 8.3 Anadolu Sigorta — email (TR)

> **Konu:** Fiziksel iklim riski kanıtı — sigortacı perspektifinden 30 dakika
>
> Sayın [Ad Soyad],
>
> GeoRisk Engine'i geliştiriyorum: lokasyon düzeyinde fiziksel iklim riskini, her sayının
> izlenebilir ve yeniden üretilebilir olduğu bir kanıt paketine dönüştüren bir motor.
>
> Sunum yapmak için değil, anlamak için yazıyorum. Anadolu Sigorta'nın TSRS kapsamındaki fiziksel
> risk açıklamalarını bugün nasıl ürettiğini ve bu rakamları kimin savunduğunu öğrenmek için otuz
> dakikanızı rica ediyorum.
>
> Faydalı olursa, 20–50 lokasyon için ücretsiz ve yeniden üretilebilir bir analizi tek bir
> yapılandırılmış geri bildirim oturumu karşılığında sunabilirim.
>
> Saygılarımla,
> Ebru Özpolat

### 8.4 Anadolu Sigorta — email (EN)

> **Subject:** Physical-climate evidence from the insurer's seat — thirty minutes
>
> Dear [Name],
>
> I am building GeoRisk Engine, which turns location-level physical climate risk into an evidence
> pack where every number is traceable and reproducible.
>
> I am writing to understand, not to present. I would value thirty minutes on how Anadolu Sigorta
> produces its physical-risk disclosures under TSRS today, and who has to defend those figures.
>
> If useful, I can offer a free, reproducible analysis of 20–50 locations in exchange for one
> structured feedback session.
>
> Kind regards,
> Ebru Özpolat

### 8.5 LinkedIn connect note (either, TR)

> Merhaba [Ad] — GeoRisk Engine'i geliştiriyorum (varlık düzeyinde, yeniden üretilebilir fiziksel
> iklim riski kanıtı). TSRS fiziksel risk raporlaması üzerine çalışmanız nedeniyle bağlantı kurmak
> isterim.

### 8.6 Follow-up (day 7, either, EN)

> A short follow-up on my note last week. Thirty minutes on how you produce physical-risk evidence
> for TSRS is the whole ask; if timing is wrong I will leave it there.

Sequence: email, LinkedIn connect on the same day, one follow-up on day seven, then stop. There is
no day-14 pilot-price touch in this sequence; pricing is asked in the room (§2.1 Q8), not sent.

---

## 9. Where the evidence goes

| Event | Record |
|---|---|
| Message sent (founder) | Date, channel, recipient role (not name in repo), in the Türkiye lane evidence log |
| Meeting held | Interview notes against §2.1 script; counts toward Gate 2.1 only if the script was followed and segment and role are recorded |
| Asset list received | §7 checklist completed and founder-signed; file location outside the repo; deletion date |
| Analysis delivered | Commit SHA, input SHA-256, `verification_report.md`, release manifest snapshot, hours logged in §5 |
| Feedback session | Notes against §6 agenda; outcome A or B with the reason verbatim |
| Outcome A | Opens a paid design-partner conversation; Gate 2.3–2.7 rows started. Gate 2.2 stays open until money or a signed procurement commitment |
| Outcome B | Product finding filed; account parked; re-contact only on a new trigger |

None of these records changes `production_eligible`, `controlled_pilot_eligible` or any readiness
flag. Naming either institution in any public material, including this repo's public docs, is a
separate FOUNDER-DECISION (public institutional or partner claim).

---

## 10. Missing evidence — verify before anything is sent

| # | Gap | Why it blocks | How to close |
|---|---|---|---|
| 0 | Rehearsal record (§0) is stale or missing at the SHA that would be delivered | No verified demo asset means no outreach | Re-run `scripts/rehearse_free_analysis_pack.py` with an out-of-repo trail; commit the record |
| 1 | No verified contact name or role at TSKB or Anadolu Sigorta | Placeholders in §8; a guessed name is a fabricated partner claim | Founder identifies from the latest published sustainability / TSRS report signatories, a warm introduction, or LinkedIn. Record the source |
| 2 | TSKB's most recent TSRS report: has it been read, and does it contain asset-level or portfolio-level physical-risk figures? | Q1–Q3 assume figures exist to defend; if they don't, the offer changes | Read the report's climate section; note whether physical-risk figures are quantitative and who assured them |
| 3 | Anadolu Sigorta's TSRS status and whether physical-risk disclosure is quantitative | Same as above from the insurer seat | Read the latest report; note the assurer |
| 4 | Whether a warm introduction exists to either institution | Cold outreach scores D4 = 2; a warm path is materially more likely to get thirty minutes | Founder checks network; record the path taken |
| 5 | Hours actually spent delivering the first analysis | Gate 2.8 needs measured cost | Fill §5 "Actual" column on delivery |
| 6 | Controlled-pilot operations evidence (C2) is open | Delivery must come from a local run at a recorded SHA, not a hosted deployment | Documented in §5; no action needed before the first call |
| 7 | No calibrated `pack-tr` hazard layer; earthquake and wildfire run on synthetic PGA / temperature-proxy inputs | Must be said in the meeting (§4.3); may be the fit finding | No action before the call; ask which seismic (AFAD TDTH) and fire-danger source they would accept, and log it |

---

## 11. Producing the analysis — runbook (local, recorded SHA)

Run from a clean checkout of the exact commit that will be recorded. Nothing here requires
external credentials; the stub pipeline is deterministic.

The audit trail is file-backed and defaults to `data/audit_trail/` inside the repo (git-ignored,
but still inside the checkout). For a real asset list, point it outside the repo with
`GEORISK_AUDIT_TRAIL_PATH` so that asset values never sit next to the source tree.

```bash
# 0. Record the SHA and the input hash; keep the trail outside the repo
git rev-parse HEAD
sha256sum /path/outside/repo/assets.csv
export GEORISK_AUDIT_TRAIL_PATH=/path/outside/repo/audit_trail.jsonl

# 1. Rehearse on the golden portfolio first (no real data) — this is the §0 send gate
PYTHONPATH=. python scripts/rehearse_free_analysis_pack.py \
    --trail "$GEORISK_AUDIT_TRAIL_PATH" \
    --record docs/05-commercial/evidence/free_analysis_rehearsal.json

# 2. Run the real list through the same path (after §7 is signed off)
#    CSV columns: asset_id, latitude, longitude (or address), asset_value, building_type, use_class
PYTHONPATH=. python -c "
import json
from datetime import date
from app.services.portfolio_ingest import parse_portfolio_csv
from app.services.portfolio_demo import run_portfolio_demo
vdate = date(2026, 6, 30)   # their as-of date; no-lookahead contract applies
text = open('/path/outside/repo/assets.csv', encoding='utf-8').read()
portfolio = parse_portfolio_csv(text, valuation_date=vdate, portfolio_id='free-analysis-v0')
n = run_portfolio_demo(list(portfolio.assets), vdate, portfolio_id='free-analysis-v0',
                       source='upload', max_assets=50)
json.dump(n.model_dump(mode='json'), open('/path/outside/repo/pack.json', 'w'), indent=2, default=str)
print(n.coverage.message)
"

# 3. Independent recomputation of EVERY analysed asset from its trail record.
#    (scripts/verify_eal.py exercises the same verifier on the reference fixture, not on their list.)
PYTHONPATH=. python -c "
import json, sys
sys.path.insert(0, 'tests')
from app.services.audit_trail import get_audit_trail
from verification.independent_eal import eal_from_trail
pack = json.load(open('/path/outside/repo/pack.json'))
trail = get_audit_trail()
fails = 0
for row in pack['assets']:
    rec = trail.get(row['eal_audit_record_id']).model_dump(mode='json')
    indep = eal_from_trail(rec, 'app/loss/curves/stub_global_mdr_v0.2.json')
    ok = round(indep['eal_absolute'], 2) == round(row['eal_absolute'], 2)
    fails += 0 if ok else 1
    print(row['asset_id'], row['eal_absolute'], 'PASS' if ok else 'FAIL', rec['record_hash'][:12])
print('independent verification:', 'ALL PASS' if fails == 0 else f'{fails} FAILURES')
" | tee /path/outside/repo/independent_verification.txt

# 4. Release manifest that travels with the pack (decision: demo_only, production_eligible: false)
PYTHONPATH=. python -c "
from app.core.config import settings
from app.services.release_manifest import build_release_manifest
print(build_release_manifest(settings).model_dump_json(indent=2))
" > /path/outside/repo/release_manifest.json

# 5. Claim scan over every written page before it leaves
PYTHONPATH=. python -c "
from app.packs.tr.sustainable_finance.claims import scan_text
r = scan_text(open('/path/outside/repo/cover_note.md', encoding='utf-8').read(), file='cover_note.md')
print('OK' if r.ok else r.findings)
"
```

Valuation date is theirs to state; the no-lookahead contract applies. The `portfolio_id` above is
a placeholder and must not carry the institution's name if the pack is ever stored anywhere
shared. The narrative also embeds one worked `verification` walkthrough (the highest-EAL asset)
for the session's live replay in §6.

---

*Related:* [`PILOT_PACKAGE_OVERVIEW.md`](./PILOT_PACKAGE_OVERVIEW.md) (NL pilot, paid scope this
offer must not be confused with) · [`ICP.md`](./ICP.md) · [`../turkiye/sustainable-finance/tr-sustainable-finance-evidence-pack.md`](../turkiye/sustainable-finance/tr-sustainable-finance-evidence-pack.md)
(`pack-tr` regulatory boundary) · [`../business/SIX_MONTH_VALIDATION_GATES.md`](../business/SIX_MONTH_VALIDATION_GATES.md) (Gate 2).
