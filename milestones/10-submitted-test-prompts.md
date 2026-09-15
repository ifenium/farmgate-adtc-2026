# 10 — Submitted Test Prompts Locked

**Status:** Done (2026-08-19), **revised 2026-08-19 after Run B** (milestone 12) made `state_at_time` a proven, distinctive capability rather than a 0%-accuracy family to avoid. **Superseded 2026-09-15 — see `milestones/16`.**

## Correction (2026-09-15)

This milestone's central claim about `tp_001` — that `full_rank` is "hardest to hit by luck since it requires an exact 4-way order" (§"Options considered" below) — **does not hold up**. `milestones/16` found that `scripts/generate_sft_dataset.py` lists candidate markets in price order before building the prompt text, so `full_rank`'s gold order equals the prompt's own listing order in 53 of 53 dataset examples, including `tp_001` itself (Am Timan/Melfi/Zouar/Bardai are listed in their actual ascending price order). Direct testing confirmed the mechanism: `full_rank` collapses from 6/6 to 0/6 when market listing order is decoupled from price order. Round 1 judging separately found `tp_001` **refused outright** under the actual evaluation condition (no caller-supplied system message) — a second, independent finding, diagnosed in `milestones/15`.

`tp_001` has been replaced with the `beyond_cutoff` prompt this milestone's own §"What was verified" (below) had already scoped and set aside — see the "Correction" note at that section and `milestones/16` for the full replacement decision. The rest of this milestone (the reasoning for `tp_002`, the rejected pairings) is left as the historical record and is not otherwise affected.

## Decision (current)

```json
"test_prompts": [
  {
    "prompt_id": "tp_001",
    "prompt": "Rank Am Timan, Melfi, Zouar, Bardai in Chad by retail price of Maize (white) in January 2024, from lowest to highest."
  },
  {
    "prompt_id": "tp_002",
    "prompt": "What was the retail price of Rice (imported) in Kisumu, Kenya in September 2024?"
  }
]
```

`tp_001` (`full_rank`) is unchanged from the original decision. `tp_002` was swapped from a `beyond_cutoff` question to a `state_at_time`-shaped one.

## Why it changed

Original pairing (`full_rank` + `beyond_cutoff`) was locked before Run B existed, when `state_at_time` was a 0%-accuracy failure mode to route around. After milestone 12, `state_at_time` is 100% accurate and is specifically *the* engineered result the whole Run A/B methodology produced (relabeling it also fixed `gap_within_range` at zero additional cost — the headline finding). Two other pairings were considered and rejected:
- **`state_at_time` + `gap_within_range`-shaped**: rejected — the two families are now behaviorally identical (any price-lookup question triggers the same hedge), so this wastes a controllable slot showing the same behavior twice.
- **Keep the original `full_rank` + `beyond_cutoff`**: safest option (cutoff-honesty is a widely-expected LLM behavior, uncontroversial to any judge) but generic — doesn't showcase anything specific to this project's engineering work.

**Known risk, accepted deliberately, not overlooked**: a judge reading the `state_at_time` hedge cold, without REPORT.md's context, could read it as "this price app won't tell me a price" rather than "a deliberate, well-reasoned capability boundary." Mitigated, not eliminated, by the response text being self-explanatory (states the limit, states what it can do instead) without requiring outside context.

## Options considered (original, still the basis for `tp_001`)

Drawn from the two families milestone 07 actually proved out (`full_rank`: 6/6, hardest to hit by luck since it requires an exact 4-way order; `beyond_cutoff`: 13/13, including spontaneous correct citation of the December 2024 cutoff) — not from `state_at_time`, `trend_change`/`yoy_comparison`, or `lowest`/`highest`, all still unresolved *at the time* per the correction in milestone 07/09. `state_at_time`'s status changed with milestone 12.

## What was verified (not assumed)

- Both prompts are **genuinely fresh** — checked against `dataset/all.jsonl` (every train/val/test example, 1,200 total): zero exact-prompt matches. `tp_001` uses the Am Timan market, absent from the dataset entirely. `tp_002` (revised) uses the Kisumu market, also absent entirely.
- **tp_001** (unchanged): Chad, Maize (white), January 2024 — Am Timan 246.91, Melfi 290.00, Zouar 652.00, Bardai 870.00 XAF per KG. Clean spread (3.5×), no ties, matches the exact `full_rank` prompt template used in training.
- **tp_002** (revised): Rice (imported), Kisumu, Kenya, September 2024 — genuinely fresh, not grounded in a specific verified row since the target behavior (calibrated hedge) no longer depends on whether the fact exists in the corpus; any `state_at_time`-shaped question triggers the same trained response.
- ~~The original `beyond_cutoff` grounding note (Bama/Nigeria/Millet)~~ — no longer the submitted prompt, kept here for history: 15 months of real Millet price history (June 2023 – December 2024, NGN per 2.6 KG), asking about February 2025 tested genuine cutoff-generalization. Still a valid, available prompt if the pairing is reverted. **Correction (2026-09-15): it was.** This is now the submitted `tp_001` — see `milestones/16`.

## Open risks / dependencies carried forward

- Locked against Run B's trained behavior (milestone 12) — if any further retraining happens, re-verify this pairing still reflects the shipped model's actual strengths.
- `metadata.json` in the actual submission repo still needs these written in verbatim before Gate 1 submission — not yet done, this milestone only locks the decision.
- The `state_at_time` framing risk noted above (cold read without REPORT.md context) is accepted, not resolved — worth revisiting if there's a strong signal it's the wrong call before final submission.
