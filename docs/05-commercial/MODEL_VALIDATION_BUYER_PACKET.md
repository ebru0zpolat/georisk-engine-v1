# Model validation / internal audit — buyer packet

**Version:** v0.1 draft · **Date:** 19 September 2026 · **WO:** WO-17
**Status:** preparation only. **Every external action in this document is FOUNDER-DECISION:** sending a
message, naming an institution outside this repo, receiving their artefact, agreeing a boundary, agreeing a
price. Nothing here has been sent to anyone.
**Supersedes, in buyer scope only:** the offer (§3) of
[`TSKB_ANADOLU_SIGORTA_OUTREACH_PACKET.md`](TSKB_ANADOLU_SIGORTA_OUTREACH_PACKET.md). That packet's send gate
discipline, honesty box and prohibited-claims list are carried over and remain binding.

---

## 0. Send gate — no passing corpus, no outreach

Nothing in §8 is sent unless, **at the SHA the report would be delivered from**, all four hold:

| Requirement | How it is satisfied |
|---|---|
| The self-test corpus passes | `tests/verification/test_corpus.py` green — all three fixtures (golden qualified, synthetic labelled, Amsterdam ambiguous) produce their expected verdicts |
| Verdicts are replayable | Report reproduced byte-identically from its trail record (WO-13) |
| The checker is independent | `tests/verification/independent_gap_report.py` imports nothing from `app.` and agrees on every corpus verdict (WO-14, INV-07) |
| The artefact carries its limits | `limits` and `scope_of_evidence_supplied` blocks non-optional and present |

**This is a different gate from the previous packet's.** That one required proving we could recompute *our own*
golden portfolio. This one requires proving we can read *somebody else's* artefact and produce a defensible gap
list. Recomputing our own numbers is no longer what is being sold, so it is no longer what gates the send.

If the corpus cannot pass, there is nothing to offer this buyer and the call is not made.

---

## 1. Why this seat, not the sustainability seat

The sustainability or TSRS/CSRD preparer produces the number. Offering them a free analysis of their assets
gives them **another number**, from another vendor, with the same defence problem they already have.

Model validation, model risk management and internal audit are paid to **challenge** numbers. Their population
includes every vendor output the institution bought. An instrument that says "here is what this output can and
cannot support, and exactly what is missing" is an instrument for their actual job — and a vendor score is not.

The regulatory frame is theirs, not the preparer's: SR 26-2 extends model-risk governance to AI; EU AI Act
high-risk provisions apply from August 2026; PRA SS5/25 requires property-level granularity with dated
gap-closure plans; EBA ESG guidelines are in force. Each of these asks a validation function to demonstrate
that a third-party model's outputs are governed — which is the question this product answers.

**The risk of this seat, stated plainly.** Validation functions buy slowly, through procurement, and often
build rather than buy. The discovery in §2 is designed to find that out early rather than late: question 8
exists for exactly that.

---

## 2. The ask: thirty minutes, discovery, not a pitch

No deck. A structured interview. The eight questions from the previous packet §2.1 transfer **unchanged** —
they were already validation questions asked of the wrong seat. Q2 ("who reviewed or challenged those
figures"), Q3 ("when a reviewer asks where this number comes from, what do you hand them") and Q4 ("what did
you do with assets you didn't trust") are this buyer's daily work.

Two replacements:

| # | Question | What the answer tells us |
|---|---|---|
| 5v | Which third-party or vendor physical-risk outputs are in your model inventory, and at what tier? | Whether the population exists and is governed, and whether this is a tiered-model problem |
| 7v | If a reproducible evidence-sufficiency report on one of those vendor outputs landed on your desk, what would you compare it against, and who would have to agree with it? | Whether the artefact fits an existing validation workflow or would need a new one |

Question 7v is where the offer in §3 is placed, and only if questions 1–4 show that somebody is accountable for
defending the figures. If nobody is, thank them, record the finding, and make no offer.

**Recording rule (carried over).** The interview counts toward the structured-buyer-interview gate only if it
is run against the fixed script and the notes record segment and role.

---

## 3. The offer

> A defensibility gap report on **one third-party physical-risk output you already hold** — not on your assets,
> and not a second opinion on the risk. Per figure: which claims the supplied evidence supports, which it does
> not, exactly what is missing for each, and which single missing item would unlock the most. Reproducible from
> a hash-chained record. In exchange, ninety minutes of structured feedback from the person who would have to
> defend, or challenge, that output.

**What the offer is not.** Not an audit opinion, not assurance, not a certification, not a statement that the
vendor's number is wrong, and not a pilot. It carries no support, no SLA, no re-runs.

**What we need from them.** Not the vendor document itself in the first instance — the transcription contract
in [`vendor-evidence-adapter-v1.md`](../specs/vendor-evidence-adapter-v1.md) §2, which they may fill themselves.
That is deliberate: the lowest-friction version of this offer never requires them to hand over a licensed
third-party artefact at all.

---

## 4. Honesty box — say this in the meeting, unprompted

1. We do not model hazard. We do not produce a competing number, and we will not tell you the vendor's number
   is wrong — only whether the evidence supplied supports the claim made.
2. Absence of evidence in a packet is not evidence about the underlying model. A vendor may have excellent
   science and a poor packet. The report says which one we assessed.
3. The first version reads a structured form, not a PDF. Transcription is manual, attributed and hashed,
   because a parser that silently misreads a vendor document would make our own output unverifiable.
4. Every readiness flag in our own engine is false. We are not selling you a production system; we are selling
   you a reproducible way to ask a question.
5. We have not yet run this against an output we did not create. You would be the first, and the report will
   say so.

## 5. Prohibited claims (carried over, plus this product's own)

Nothing in a conversation, draft, deck or report may assert:

- that any output of ours is validated, calibrated, production-eligible, bank-grade or independently verified;
- that a gap report is an audit opinion, assurance engagement, certification or compliance statement;
- that a named producer's number is incorrect (there is no such verdict — INV-11);
- that we perform model validation *for* them, or that using the report satisfies any regulatory obligation;
- that any Turkish output is anything other than `NOT_QUALIFIED`.

## 6. Data boundary — FOUNDER-DECISION before receiving anything

1. Preferred: they fill the structured form themselves; we never receive the licensed artefact.
2. If an artefact is received: hash on receipt, retention terms written **before** receipt, deletion on the
   stated date, and no reuse in any corpus, test, demo or marketing material.
3. No producer and no institution is named publicly without written consent.
4. No asset identifier that could identify a property or a person enters the form (`asset_ref` is opaque, and
   the schema validator rejects the obvious cases).

## 7. The feedback session (the price of the free report)

Ninety minutes, structured, recorded in notes:

1. Which verdicts do you disagree with, and on what grounds?
2. Which requirement in the catalogue is missing, wrong, or not how your reviewers think?
3. What would the report have to say for it to change what you do next?
4. Would you have paid for this? What is the budget line, who approves, what is the timeline?

Every rejected verdict is recorded verbatim, **including the ones we believe are right**. A rejected verdict we
still believe is a grammar gap or a communication gap, and both are findings.

---

## 8. Draft messages — withheld until the founder sends them

### 8.1 Email (EN)

> Subject: a reproducibility question about vendor physical-risk outputs
>
> I am working on a narrow problem: when a vendor's physical-risk output has to be defended to a reviewer,
> what evidence actually travels with it. I am not selling a risk model and I do not produce a competing
> number.
>
> I am looking for thirty minutes with someone in model validation or internal audit to understand how that
> question is handled today — how a third-party physical-risk output enters the model inventory, who challenges
> it, and what gets handed over when someone asks where a figure came from.
>
> No deck, no pitch. If it is useful, I will show you what we produce and you can tell me what it gets wrong.

### 8.2 Email (TR)

> Konu: satıcı kaynaklı fiziksel risk çıktılarının izlenebilirliği
>
> Dar bir soru üzerinde çalışıyorum: bir satıcının fiziksel risk çıktısı bir denetçiye savunulmak zorunda
> kaldığında, o sayının yanında hangi kanıt geliyor? Bir risk modeli satmıyorum ve rakip bir sayı üretmiyorum.
>
> Model validasyon veya iç denetim tarafında birinden otuz dakika rica ediyorum: üçüncü taraf bir fiziksel risk
> çıktısı model envanterine nasıl giriyor, kim itiraz ediyor ve "bu sayı nereden geliyor" sorulduğunda ne teslim
> ediliyor?
>
> Sunum yok. Faydalı olursa ürettiğimiz çıktıyı gösteririm ve nerede yanıldığını siz söylersiniz.

### 8.3 Follow-up (either language, day 7)

> Following up once. If this sits with someone else in your organisation, I would rather ask them than ask you
> twice. If the answer is that nobody owns this question today, that is itself the answer I am looking for, and
> I would value hearing it.

---

## 9. Missing evidence — verify before anything is sent

- [ ] Corpus passing at the delivery SHA (§0)
- [ ] `limits` block present in both renderings of a sample report
- [ ] Data boundary text agreed by the founder (§6)
- [ ] Sample report produced on a fixture, reviewed line by line for any sentence that reads as an audit opinion
- [ ] Confirmation that no institution is named anywhere in this repository beyond the two already named in the
      previous packet
