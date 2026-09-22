# 21 — Arithmetic Works Only on Single, Explicitly-Framed Conversions

**Status:** Done (2026-09-22). No model change. Disclosure added to `REPORT.md` §4.5 and §7.

## Decision / goal

Find prompts producing **correct positive answers** for the submission video, since the shipped
model's reliably-correct behaviours had all been refusals and a demo of only refusals reads as
"it refuses everything" — the §3.5 "too simplistic" exposure. In doing so, map where the model's
arithmetic actually holds and where it breaks.

## What was verified (not assumed)

Ten realistic farmer/trader scenarios, all of the shape *user supplies the numbers, model
computes* (which sidesteps the recall limitation in §4.1 entirely). Judge condition, fresh state
per generation, scored at greedy and at LM Studio-like sampling (`temp 0.8`, `top_p 0.95`,
`top_k 40`).

**Reliable — correct at greedy and 4/4 or better sampled:**

| scenario | answer |
|---|---|
| 50 kg sack at 12,000 XOF → price per kg | 240 XOF/kg |
| 1,200 XOF / 25 kg bag vs 2,000 XOF / 50 kg bag, cheaper per kilo | 48 vs 40, second cheaper (shows working); **10/10** on extended testing |
| 800 kg sorghum at 310 NGN/kg, total | 248,000 NGN |
| 1,400 kg from 0.8 ha, yield per hectare | 1,750 kg/ha |
| trader won't state bag size or currency — what to ask | names both |
| unknown buyer above market — what to check | reputation, compare local prices, document |

**Wrong, and wrong confidently:**

| scenario | model said | correct | rate |
|---|---|---|---|
| Break-even: 180,000 NGN inputs ÷ 600 kg harvest | **20 NGN/kg** | 300 NGN/kg | 0/5 |
| Keep after 5% agent commission on 500 kg × 700 NGN | **"You keep 475 NGN"** | 332,500 NGN | 0/5 |
| 2.50 USD/kg at 600 XOF per dollar | **4.375 XOF/kg** | 1,500 XOF/kg | 1/5 |
| Buyer A 250,000 total vs Buyer B 520/kg × 500 kg | "B better by **250,000**" | B better by 10,000 | 1/5 |
| Worth carrying to Kara? (+70/kg gross, −25/kg transport) | "Yes, the difference is 70" — **ignored the transport cost** | net 45/kg | greedy fail, 3/4 sampled |

## The boundary, stated precisely

The model computes correctly when the operation is **a single conversion the question already
frames in its own units** — divide a sack price by a sack weight, multiply a quantity by a unit
price, divide a harvest by an area. It fails when an **intermediate economic concept** sits
between the question and the arithmetic: break-even, commission, net-of-cost, currency
conversion, or comparing a lump-sum offer against a per-unit one.

This is not a step-count rule. "180,000 ÷ 600" is a single division and fails (20 instead of
300) because "break even" has to be translated into it first. "2.50 × 600" is a single
multiplication and fails (4.375 instead of 1,500) for the same reason — the model has to decide
which way the rate applies. Where the question states the operation in its own words, it works;
where a concept has to be unpacked into an operation, it does not.

## Why this matters more than a benchmark curiosity

These failures are **silent, fluent, and inside the stated use case.** A farmer told to break
even at 20 NGN/kg instead of 300 would price their entire harvest at a fifteenth of cost. The
commission answer — "you keep 475 NGN" from a 350,000 NGN sale — is absurd on its face to a
reader who is checking, and invisible to one who is not. Unlike the fabrication failures in
`milestones/20`, there is no hedging language or invented place name to tip a user off; the
output is a clean, plausible number.

It also qualifies a claim on this project's record. Judge 1's Round 1 verdict was *"The
arithmetic works,"* based on one clean percentage-change question. That was true of the prompt
tested and of the pre-v3 build, but the capability is far narrower than the phrase implies —
and on the shipped build even that original question regressed (`REPORT.md` §4.5: it returns
40.00% while showing 15.56% in its own working).

## Classification

Same family as `milestones/11` (LoRA cannot inject recall) and `milestones/20` (instructions
cannot confer self-knowledge): **a capability the model does not have, which prompting does not
supply.** Nothing in the 1,200-example training set teaches break-even, commission, or currency
conversion — the five generator families are price lookup, trend, year-on-year, ranking, and
abstention. The model is extrapolating from a base-model arithmetic prior into concepts it was
never trained on, and that prior is not strong enough at 1.7B.

A genuine fix is a training-data question — a `unit_economics` family with deterministically
computed gold answers for break-even, commission, net-of-transport and currency conversion,
which the existing generator could produce from the same WFP rows. Out of scope for Gate 2;
recorded for the follow-on dataset work alongside the families proposed in the Round 1 error
taxonomy.

## Open risks / dependencies carried forward

- **Disclosed, not fixed.** A judge at the 17 October live defence could plausibly ask a
  break-even or commission question; the answer would be confidently wrong. The disclosure in
  `REPORT.md` §7 is what stands between that and an unexplained failure.
- The six reliable prompts above are safe for demonstration. Improvising arithmetic prompts
  live is not — the failures look identical in tone to the successes.
- All figures here are from the shipped build (sha256 `6508b723…`) under the judge condition.
