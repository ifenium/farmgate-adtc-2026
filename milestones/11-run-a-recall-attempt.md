# 11 — Run A: Recall Attempt (Gated)

**Status:** Done (2026-08-19). Gate failed at iter 1500 — stopped as designed, did not proceed to leg 2 (iter 1500→3000).

## Decision / goal

Test whether `state_at_time` factual recall is reachable with more training signal (3000 iters, 10× LR, oversampled trend/yoy) before committing further days to that direction — with a hard, pre-committed checkpoint gate at iter 1500 (`state_at_time` accuracy < ~10% → stop) specifically so the decision would be made on real data, not sunk-cost momentum.

## What was verified (not assumed)

- Fixed a real mistake before it cost anything: copied validation data to `val.jsonl` instead of `valid.jsonl` (the exact naming lesson from Run 1, missed on the second dataset). Caught at iter 20 via the "Validation set not found" warning, killed, fixed, restarted — 20 iterations of throwaway compute, not the whole run.
- Oversampling verified before training: trend/yoy rise/fall/flat went from 54/33/13 to a real, checked 36/38/26 split (dataset/sft_runA/, 1066 train examples, up from 900).
- Full leg 1 (iter 1-1500) ran clean at ~0.67-0.70 it/sec, ~420 tok/s, peak mem 4.75 GB.
- **Val loss signal, independent of the gate**: bottomed at 0.314 (iter 500), crept back up to 0.374 by iter 1500 while train loss kept falling to ~0.12 — classic overfitting, a direct consequence of the 10× LR. This alone was already a warning sign before the gate check ran.
- **Gate check, on the real quantized artifact** (fuse → convert → quantize → generate + grade, same pipeline as milestone 07, restricted to the 50 `state_at_time` test examples): **3/50 (6.0%)** — below the pre-agreed 10% threshold. Gate failed.

## Result

Moved from 0% (Run 1) to 6% — some movement, not nothing, but nowhere near the threshold that would justify 1500 more iterations chasing this direction. Qualitatively informative too: sample responses showed the model now sometimes abstaining on genuinely-answerable `state_at_time` prompts (echoing `gap_within_range`'s refusal language on facts it actually could have stated) rather than only fabricating as in Run 1 — inconsistent, unstable resolution of the same prompt-shape contradiction Run B's design targets, not convergence toward real recall. This is further evidence *for* Run B's diagnosis (the contradiction between state_at_time and gap_within_range training signals), not against it.

**Per the pre-committed gate criterion: stopped here.** Leg 2 was not run.

## Open risks / dependencies carried forward

- Pivoting to Run B (milestone 09) — pending the user's choice of hedge wording (3 candidates presented, not yet selected).
- The trend/yoy oversampling fix (54/33/13 → 36/38/26) is independent of the Run A/B question and worth carrying into whichever training set Run B uses — it wasn't itself invalidated by the gate failure, only the raw-recall push was.
- `adapters_runA_leg1/`, the intermediate fused/converted/quantized gate artifacts, and `dataset/sft_runA/` are left on disk — not yet cleaned up, harmless to leave but not part of the eventual submission.
