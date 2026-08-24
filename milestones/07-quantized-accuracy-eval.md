# 07 — Quantized GGUF Accuracy Evaluation

**Status:** Done (2026-08-19)

## Decision / goal

Fuse the real QLoRA adapter (milestone 05's 1000-iter run) into the base model, convert to GGUF, quantize to Q4_K_M — the actual artifact judges would run — and evaluate it against `dataset/test.jsonl` (150 held-out examples, never seen in training or validation) with programmatic per-family grading, not an aggregate number.

## What was verified (not assumed)

Pipeline: `mlx_lm.fuse --dequantize` → `convert_hf_to_gguf.py` → `llama-quantize` (Q4_K_M) → `models/Qwen3-1.7B-agri-Q4_K_M.gguf`. All three steps completed cleanly on the first real run (the dry run in milestone 05 had already de-risked the handoffs).

Evaluation script: [`scripts/evaluate_test_set.py`](../scripts/evaluate_test_set.py). Generation via `llama-cpp-python` bound to the quantized GGUF, same chat template and system prompt as training, greedy decoding (`temp=0`, `repeat_penalty=1.1`). Grading is deterministic/programmatic per `answer_type` — numeric tolerance (5% relative), keyword-matched direction for classification, position-matched market names for ranking, refusal-language detection for abstention. No LLM judge anywhere in the loop.

**Two grading bugs found and fixed before trusting the numbers** (smoke-tested on 5 examples first, then found these on the full run):
1. Naive "first number in response" extraction picked up the echoed query year (e.g. "...in March 2024 was 77.00 KES..." → extracted `2024`, not `77.00`) — the training format restates the date before the price. Fixed by excluding bare 4-digit numbers in a plausible calendar-year range unless no other number is present.
2. Naive substring search for market names in `cross_market_ranking` misgraded a genuinely-correct `full_rank` answer, because "Lama" is a literal substring of "LAMA-TESSI" and the naive search matched inside the longer name. Fixed with a longest-name-first, non-overlapping-span matcher. Also hardened the classification grader (`rise`/`fall`/`flat` keyword matching) to word-boundary regex instead of bare substring, since "flat" is a literal substring of "inflation" — no actual occurrence in this run, but a live latent bug, fixed defensively.

## Results — per family, not just aggregate

| Family | Subtype | Accuracy |
|---|---|---|
| state_at_time | local_currency | 0/25 (0%) |
| state_at_time | usd_converted | 0/25 (0%) |
| trend_change | rise | 16/16 (100%) |
| trend_change | fall | 0/10 (0%) |
| trend_change | flat | 0/4 (0%) |
| yoy_comparison | rise | 12/13 (92.3%) |
| yoy_comparison | fall | 0/9 (0%) |
| yoy_comparison | flat | 0/3 (0%) |
| cross_market_ranking | full_rank | 6/6 (100%) |
| cross_market_ranking | lowest | 6/7 (85.7%) |
| cross_market_ranking | highest | 3/6 (50%) |
| abstention_negative | beyond_cutoff | 13/13 (100%) |
| abstention_negative | gap_within_range | 0/13 (0%) |
| **Aggregate** | | **56/150 (37.3%)** |

**The aggregate number is actively misleading on its own** — exactly the risk flagged before running this. Three distinct, diagnosable failure modes, not "one accuracy number":

1. **state_at_time: total memorization failure (0%).** 1000 iterations over 900 examples was not enough to memorize hundreds of distinct specific prices. Responses match the training *format* almost perfectly (`"{number} {currency} per {unit}"`) but the values are fabricated — sometimes with nonsense currency/unit tokens (`"105.00 FIB"`, `"103.50 KCF"`, `"10.50 FLL per KG"`, one even producing a stray Khmer riel symbol `៛`). This is confident fabrication, not near-miss arithmetic, in almost every case; the 5 genuine near-misses that occurred were concentrated in the `usd_converted` subtype (errors 5-20%, e.g. `0.61` vs gold `0.68` USD).
2. **trend_change / yoy_comparison: mode collapse, not partial competence.** The 53%/48% aggregate numbers are an illusion. The model appears to have collapsed onto a single canned response — **"Rose 10.3%"**, verbatim, across totally unrelated commodities, countries, and date ranges — that happens to match the correct direction whenever the true answer is "rise" (hence 100%/92.3% on that subtype) and is wrong every single time the true answer is "fall" or "flat" (0% on both, 26 cases). This is a real, specific, fixable-with-more-training failure, not the model "sometimes reasoning correctly."
3. **abstention_negative: the split the whole submission depends on.** `beyond_cutoff` (future-dated queries): **100%**, including one response that correctly cited "December 2024" as its own training cutoff unprompted. `gap_within_range` (real, in-range data gaps): **0% — every single one is `confident_fabrication`**, never a hedge, never "I don't know." The model learned a coarse "is this date beyond my range?" heuristic perfectly but did not learn genuine epistemic humility about specific facts it never saw. This is exactly the family-level failure an aggregate would have hidden.

**Why this contradicts the clean val-loss curve from milestone 05, and why that's not a contradiction**: val loss (teacher-forced cross-entropy on the correct completion) dropped smoothly to ~0.33 and looked fully converged. That metric is dominated by the shared structural tokens common to all 900 examples ("The retail price of ... was ... per ..."), which the model learned very well — that's most of the tokens in any completion. The specific price digits are a small, individually-rare fraction of each sequence, so a model can achieve good average cross-entropy while being essentially unable to reproduce them correctly in free generation. This is precisely why the project's programmatic, per-family, generation-based grading (rather than trusting the training loss curve) was the right call — a loss curve alone would have reported "converged nicely" and missed all three findings above.

## Addendum (2026-08-19): trend/yoy class-balance diagnosis

Checked whether the "Rose 10.3%" mode collapse is explained by training-set class imbalance, per the hypothesis that a skewed distribution would make it a data fix rather than a training-budget problem.

**Actual rise/fall/flat distribution in `train.jsonl`**: trend_change — rise 53.9%, fall 32.8%, flat 13.3% (180 examples). yoy_comparison — rise 54.0%, fall 34.0%, flat 12.0% (150 examples).

**Verdict: real but mild skew, not sufficient on its own to explain total collapse.** A ~54% majority class is a real bias — enough to nudge an uncertain model toward "rise" as the safer default — but a properly-learning classifier shouldn't collapse to 100%/0%/0% off a 54/33/13 split; that pattern points to a severe imbalance (e.g. 90/5/5), which this isn't. Also checked whether "10.3%" specifically was an overrepresented literal value in training (i.e. the model echoing a memorized constant): only 5 of 330 trend/yoy examples have a magnitude near 10.3%, and the training set's percentage-magnitude distribution is broad (median 5.2%, spanning from under 1% to over 1000%) — "10.3%" isn't a dominant training value being parroted, it's a plausible-looking number sitting comfortably inside the dense central part of the distribution (most real values cluster in the ±5–20% range). This reads as **regression-to-the-distributional-mean under insufficient fact-conditioning**, the same root cause diagnosed for `state_at_time`'s 0% — the model learned "changes are typically small-to-moderate percentages and usually positive" as a corpus-level statistical prior, but not to condition the specific direction and magnitude on the two actual retrieved price facts in each instance.

**Implication**: this needs both a data fix (oversample `fall`/`flat` to remove the real if mild skew) *and* more training signal (to fix the underlying fact-conditioning gap) — neither alone is likely sufficient, since the skew doesn't fully explain the collapse and the collapse pattern (a distribution-typical fallback value, not the base model's pre-fine-tune behavior) suggests the format/register learning outpaced the fact-conditioning learning within 1000 iterations.

## Open risks / dependencies carried forward

- **1000 iterations is not enough for factual recall or trend classification at this dataset size.** Candidates for the next attempt: more iterations/epochs (the val loss plateau at iter ~900 may reflect settling into the format-only optimum, not a true ceiling), a higher learning rate (1e-5 is conservative), or explicit oversampling of the trend/yoy and gap_within_range families to break the mode-collapse and force genuine differentiation.
- `cross_market_ranking` (79% aggregate) is the one family with real, meaningful signal — worth understanding why it transferred better (plausibly: it only requires naming one of 3-5 candidates rather than recalling an exact number) before deciding how to fix the other families.
- Full per-example results (all 150, including responses and gold) are saved at [`results/test_eval_results.json`](../results/test_eval_results.json) for further analysis.
- This evaluation used greedy decoding with a mild repeat penalty — not yet cross-checked against the actual profiler's `lm-eval`-based accuracy stage (`adtc-profiler run` without `--skip-accuracy`), which uses a different scoring method (log-likelihood, not free generation) — HANDOVER's Day 5 accuracy stage should use that path for the number that actually counts toward `S_acc`.
