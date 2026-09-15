# 16 — Ranking Generator Leak Disclosure and `tp_001` Replacement

**Status:** Done (2026-09-15). Disclosed in `REPORT.md` §4.7. `tp_001` replaced in
`metadata.json` and `REPORT.md` §6.

## Decision / goal

While investigating milestone 15's system-prompt finding, re-examine `cross_market_ranking`'s
own generator — REPORT.md and milestone 10 both describe it as "the one family with real,
meaningful signal" and pick `full_rank` for `tp_001` specifically because it is "hardest to hit
by luck since it requires an exact 4-way order." Verify that claim directly rather than carry it
forward unchecked, since milestone 15 already found the family's headline number partly explained
by a mechanism (system-prompt brittleness) nobody had looked for.

## What was verified (not assumed) — the finding

`scripts/generate_sft_dataset.py:271` sorts the sampled markets by price **before** building the
prompt text:

```python
chosen = chosen.sort_values("price")
markets_list = ", ".join(chosen["market"].tolist())
```

The market names in every `cross_market_ranking` prompt are listed **in price order** — for
`full_rank`, that is the exact gold ranking; for `lowest`/`highest`, the correct answer is
literally the first or last name mentioned. Checked exhaustively across every example in
`dataset/all.jsonl` (not sampled):

| subtype | count | leak measured |
|---|---|---|
| `full_rank` | 53 | gold ascending order == prompt listing order, **53/53** |
| `lowest` | 54 | correct answer is the first-listed market, **54/54** |
| `highest` | 53 | correct answer is the last-listed market, **43/53** (81%) |

"Rank these from lowest to highest" is answerable by repeating the question back.
`tp_001` itself has this shape: Am Timan, Melfi, Zouar, Bardai are listed in the prompt in
their actual ascending price order (246.91 / 290.00 / 652.00 / 870.00 XAF).

**Direct test of the actual capability, not just the leak's existence**: re-ran the full
`cross_market_ranking` test set with the market names in each prompt **relisted**, gold
prices held fixed, on the v3 shipping GGUF (condition A, training system prompt, the model's
best-case condition):

| prompt market order | `full_rank` | `lowest` | `highest` | total |
|---|---|---|---|---|
| original (price-sorted, i.e. the leaked condition) | 6/6 | 7/7 | 3/6 | 16/19 |
| reversed | **0/6** | 1/7 | 5/6 | 6/19 |
| alphabetical | **0/6** | 1/7 | 4/6 | 5/19 |

`full_rank` collapses to **zero** the moment listing order stops matching price order — direct
evidence the model has no price-comparison capability here, only a listing-order echo.
`tp_001` with its four markets relisted in reverse (gold order unchanged) returns
`Bardai (103.00), Zouar (125.00), Melfi (147.00), Am Timan (168.00)` — the *listed* order
echoed verbatim, with the same canned price ladder the model emits regardless of prompt order
(see below). `highest` partially inverts under reversal (3/6 → 5/6) because the model names the
first-listed market and reversing puts the priciest market first — consistent with an
order-echo mechanism, not a comparison capability that happens to degrade under reordering.

**The volunteered prices are not real, independent of the leak.** Across all ranking responses
in the corrected (order-independent) evaluation: 49 decimal price figures emitted, of which
**4 (8.2%) match any real gold price anywhere in the `cross_market_ranking` test set**, and 27
(55%) cluster in a 100–170 numeric band regardless of the commodity, currency, or country asked
about (real gold prices in this family span 30 to 144,444). This corroborates `REPORT.md` §6's
prior finding — a live generation of the original `tp_001` returned the correct order with
fabricated prices — with a measured rate rather than a single anecdote.

**A second, smaller bug found while verifying this**: `scripts/evaluate_test_set.py`'s
`grade_ranking()` has no tie handling. For `lowest`/`highest`, it takes `sorted_markets[0]`/`[-1]`
with no allowance for a price tie, so when two markets are exactly tied for the target price, one
of two equally-correct answers is silently graded wrong depending on Python dict insertion order.
One test example hits this (`agmkt-rank-0157`, two markets tied at 2500.0); it happened to grade
in the model's favor in every run so far. Latent, same class as the two grading bugs already found
and fixed in `milestones/07`. **Fixed**: `grade_ranking` now accepts any market tied for the
target price as correct.

## Why this matters

Gate 2 §3.5 (anti-gaming) permits disqualification when two judges independently flag a model's
capability as simpler than presented. `full_rank` was the family REPORT.md and milestone 10 both
singled out as this submission's strongest, hardest-to-fake capability, and it was the basis for
choosing `tp_001` as a showcase prompt. Both claims do not survive testing. Disclosing this
plainly — rather than leaving the prior "hardest to hit by luck" framing in place — is the
project's own standing rule (`HANDOVER.md` §11: "distrust aggregates," "check your own graders").

## Decision: `tp_001` replaced

A showcase prompt answerable by echoing it cannot remain the submission's lead example. Replaced
with a `beyond_cutoff` prompt — a genuinely different, independently verified capability
(100% accuracy across every measurement this project has made, unaffected by this leak, unaffected
by the system-prompt brittleness in milestone 15 since abstention held at 26/26 across every
candidate system prompt tested there):

> "What was the retail price of Millet in Bama, Nigeria in February 2025?"

Verified genuinely fresh (absent from all 1,200 dataset examples, checked programmatically) and
grounded in real coverage: Bama, Nigeria reports Millet prices for 9 of 12 months in the 2024 WFP
CSV (Jan–Dec, with 3 gaps), giving the model real in-range history to demonstrate it knows the
difference between "past my cutoff" and "a gap in my data" — the same market/commodity pair
originally scoped for this family in milestone 10 before that milestone swapped to a
`state_at_time` prompt. Verified against the shipped v3 GGUF under the judge condition (no system
message): *"I don't have data for February 2025."* — correct, terse, matches the trained format.

Not chosen: another `state_at_time`/hedge-shaped prompt, which milestone 10 already reasoned
would waste a controllable slot showing the same behavior as `tp_002`. `beyond_cutoff` is a
distinct capability (cutoff-awareness vs. general price-recall honesty) and complements rather
than duplicates it.

## Open risks / dependencies carried forward

- The `cross_market_ranking` generator's price-sorted listing order is unchanged in
  `dataset/`/`dataset_runB/` — this milestone documents and discloses the leak, it does not fix
  the generator or retrain. A genuine fix (shuffle listing order independent of price order,
  regenerate the family, retrain) is dataset-redesign work, explicitly out of scope for this
  session per instruction.
- `full_rank`'s 6/6 and `lowest`'s 7/7 headline numbers throughout this project's history
  (milestones 07, 12; `REPORT.md` §4.1–4.3) should be read as "the model reliably echoes
  price-sorted listing order," not "the model compares prices across markets." `highest`'s
  weaker, more variable numbers (3/6 in most measurements) are now explained: it is the one
  subtype the leak only partially covers (81%, not 100%).
- The `grade_ranking` tie-handling fix changes grading on exactly one test example
  (`agmkt-rank-0157`) and does not change any previously reported aggregate, since that example
  already graded correct under the old (order-dependent) logic in every run so far.
