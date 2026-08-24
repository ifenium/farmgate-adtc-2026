# 09 — RAG Pivot Assessment

**Status:** Assessment complete (2026-08-19) — decision pending, not yet acted on.

## Decision / goal

Assess whether wiring retrieval over the WFP CSVs — so the model computes over retrieved rows instead of recalling memorized facts — is a realistic use of the ~5 remaining days, given milestone 07's finding that the fine-tune-as-database premise doesn't hold at 1.7B for factual recall.

## The finding that changes the answer

Milestone 08, resolved today: **judges only ever send the bare test prompt to the bare submitted GGUF — nothing else runs, nothing else can inject content into that prompt.** This isn't just "a wrapper app won't be executed" (the live-RAG-app framing) — it's stronger: there is no mechanism, at evaluation time, for retrieved context to enter the prompt *at all*, by any means. That rules out both flavors of RAG someone might reach for here:

- **Live retrieval app**: no infrastructure to run it — confirmed via the submission template's actual file structure (no code directory, no entrypoint, `llama.cpp` GGUF only).
- **Train the model to expect context in the prompt, injected by something else at eval time**: also dead, for the same reason — there is no "something else." The judge's raw question is the entire prompt the model ever sees.

**Consequence: no form of RAG can move `S_acc` for this submission, full stop.** This isn't a probability judgment ("RAG will probably help the demo but maybe not scoring") — it's now confirmed structural.

## What would actually be involved (assessed for completeness, not because it's recommended)

1. **Query understanding**: parse a natural-language question ("What was the price of X in Y in Z?") into structured filters (commodity, market, country, date/date-range). Either a rule-based parser (fragile against phrasing variance beyond the training template) or an LLM-based extraction pass (adds a second inference call, latency, and complexity).
2. **Retrieval**: structured filter/lookup over the cleaned WFP rows — this is exact-match lookup, not semantic search, so a real index (embeddings, vector DB) is unnecessary machinery; a direct filter over the cleaned dataframe is the right tool, but still needs building and testing against messy real market-name variants.
3. **Context injection**: format matched row(s) into the prompt before generation.
4. **Retraining redesign** (your hypothesis, and it's the right shape if this were being built): examples where the prompt *includes* retrieved context and the gold completion computes the answer from that context rather than from memorized weights, plus an explicit "no rows returned → abstain" pattern — structurally similar to the existing `gap_within_range` family, but conditioned on empty retrieval results instead of a memorized fact-gap.
5. **Failure handling**: ambiguous/multiple matches, fuzzy market-name matching, retrieval misses.
6. **Packaging as a real application** — separate from the GGUF+metadata.json submission entirely.

Realistic estimate for a genuinely robust version: 2-3+ days of the ~5 remaining, dominated by query-parsing robustness and the retraining redesign, not the retrieval mechanics themselves (those are simple — it's a CSV filter).

## Recommendation

**Don't pivot.** Every hour spent on this is an hour that cannot move `S_total`, because the confirmed evaluation architecture has no path for it to matter. That was a completely reasonable hypothesis on Day 1, before §3 was resolved — it's no longer reasonable now that it's a confirmed structural dead end for scoring purposes.

Your own framing is right: the fine-tune already nails format, `beyond_cutoff` abstention, and `cross_market_ranking` — those are real, working capabilities. The two diagnosed failures (`state_at_time` factual recall, `trend`/`yoy` mode collapse) are training problems, confirmed as training problems in milestone 07's diagnosis, not architecture problems RAG would fix even if it could run. The right use of the remaining days is a second, better-targeted training pass:
- More iterations past the format-only plateau milestone 05 found around iter ~900 (loss plateauing there may reflect settling into a format-only optimum, not a true ceiling on this task).
- A less conservative learning rate.
- Data-side fix for the mode collapse — see the class-balance diagnosis appended to [`milestones/07-quantized-accuracy-eval.md`](07-quantized-accuracy-eval.md): the skew is real (54/33/13 rise/fall/flat) but mild, not severe enough to fully explain 100%/0%/0% collapse on its own — this points to *undertraining plus* mild skew, not skew alone, so a fix likely needs both oversampling fall/flat and more training signal, not a data rebalance alone.

**Where RAG still has legitimate, non-zero value, if there's slack time after the retrain**: the 2-minute demo video (participants control that content entirely — it doesn't have to reflect what's scored) and the separate "Best Integration Award" ($3,000, judged on cross-disciplinary integration specifically) are outside the `S_total` formula's evaluation path. A minimal local RAG demo could be a stretch goal for that side-prize, clearly labeled in REPORT.md as outside the scored inference path — but strictly after the retrain, never instead of it.

## Open risks / dependencies carried forward

- No action taken yet — this is an assessment, pending your decision on whether/how to spend the retrain time.
- If a retrain is pursued, the specific hyperparameter changes (iterations, LR, family oversampling ratios) still need to be decided and are not yet specified beyond the direction above.
