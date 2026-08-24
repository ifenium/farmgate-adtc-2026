# 12 — Run B: Honesty Pivot

**Status:** Done (2026-08-19)

## Decision / goal

Test whether relabeling `state_at_time` from confident price to a calibrated hedge — removing the contradictory training signal against `gap_within_range` that shares its exact prompt shape — fixes both families at once, per the diagnosis in milestones 07/09/11.

## What was verified (not assumed)

- Relabeling script ([`scripts/relabel_state_at_time_runB.py`](../scripts/relabel_state_at_time_runB.py)) applied the user-approved hedge verbatim across all 400 `state_at_time` examples (train+val+test), with only `{commodity}`/`{market}`/`{month_year}` substituted — confirmed 400/1200 relabeled, everything else byte-identical to the original dataset (checked programmatically, not assumed).
- Same trend/yoy oversampling as Run A applied to the training set (54/33/13 → 36/38/26), `valid.jsonl` named correctly this time (checked before launch, not after a failed run).
- Training: 1200 iters, LR 1e-5 (unchanged from the original successful run), AdamW. **Clean convergence, no overfitting** — val loss bottomed at 0.263 (iter 800), held stable at 0.269-0.270 through iter 1200. Contrast with Run A's 0.314→0.374 divergence under the higher LR.
- Full pipeline run for real: fuse `--dequantize` → `convert_hf_to_gguf.py` → `llama-quantize` (Q4_K_M) → full 150-example evaluation against `dataset_runB/test.jsonl` (the relabeled ground truth, so hedges grade as correct for `state_at_time`).

## Results

| Family | Subtype | Run 1 | Run B |
|---|---|---|---|
| state_at_time | both | 0/50 (0%) | **50/50 (100%)** |
| abstention_negative | beyond_cutoff | 13/13 (100%) | 13/13 (100%) |
| abstention_negative | gap_within_range | 0/13 (0%) | **13/13 (100%)** |
| cross_market_ranking | full_rank | 6/6 (100%) | 6/6 (100%) |
| cross_market_ranking | lowest | 6/7 (86%) | 7/7 (100%) |
| cross_market_ranking | highest | 3/6 (50%) | 3/6 (50%) |
| trend_change | rise/fall/flat | 100%/0%/0% | 0%/40%/25% |
| yoy_comparison | rise/fall/flat | 92%/0%/0% | 8%/67%/0% |
| **Aggregate** | | **56/150 (37.3%)** | **104/150 (69.3%)** |

**The core hypothesis is fully confirmed: removing the contradiction fixed both families it targeted, completely, on the first attempt.** `state_at_time` went from total fabrication to 100% calibrated, honest, well-formed responses. `gap_within_range` — which nothing in this run's training data touched directly, it kept its original examples — went from 0% to 100% purely as a side effect of no longer fighting `state_at_time`'s contradictory signal for the same prompt shape. That's strong, direct evidence the milestone 09 diagnosis was correct, not a lucky coincidence.

Sample hedge output (Cairo eggs, December 2024): *"I don't have the exact retail price for Eggs (medium size) in Cairo (national average) in December 2024 — I'm not built to recall individual price points from the past."* Note: paraphrased ("from the past" vs. the approved template's "from the series") — the model learned the behavioral pattern rather than memorizing the string verbatim, which is a good sign (genuine generalization), though a minor, harmless deviation from the exact approved wording worth knowing about.

## The honest caveat: trend/yoy is not fixed, it changed shape

The aggregate for `trend_change`/`yoy_comparison` went *down* in raw terms (53%/48% → 17%/28%), and this needs to be read correctly, not as "Run B made things worse." **Run 1's 53%/48% was itself an illusion** — mode collapse to "Rose 10.3%" that happened to match the majority class ("rise" was 54% of training). Run B's oversampling shifted the class balance, and the model **collapsed to a different single answer instead of learning to differentiate** — now defaulting to "Fell ~10.9%" regardless of the actual facts (checked directly: five different rise-truth examples all got answered "Fell 10.9%" or "Fell 10.8%," verbatim-close, unrelated to the real commodities/countries/magnitudes). The oversampling fix didn't touch the real root cause (the model still isn't conditioning on the two actual retrieved price facts) — it just moved where the collapse lands. This matches exactly what the milestone 07 addendum predicted: the class-balance fix alone was not expected to be sufficient without also fixing the underlying fact-conditioning gap, and it wasn't.

`cross_market_ranking` held or slightly improved (78.9%→84.2% aggregate) — plausibly incidental rather than a direct effect of anything Run B changed there.

## Open risks / dependencies carried forward

- `trend_change`/`yoy_comparison` remain genuinely unresolved — worse in raw score than Run 1's illusory number, though for an understood and honestly-diagnosed reason, not a new mystery. Neither of the two submitted prompts (milestone 10) touches this family, so the only exposure is the 2 hidden prompts.
- The minor hedge paraphrasing ("from the past" vs. "from the series") is harmless for grading (keyword-based) but worth knowing about if exact wording ever matters for a qualitative judge impression.
- `results/runB_eval_results.json` has full per-example detail for further inspection.
- Decision point: accept this as the final trained artifact and move to submission packaging, or spend further time specifically on trend/yoy (a different fix than either Run A or B attempted would likely be needed — this hasn't been designed yet).
