# 15 — System-Prompt Brittleness Discovery and the v3 Default-Prompt Fix

**Status:** Done (2026-09-15). Shipping as the current `models/Qwen3-1.7B-agri-final-Q4_K_M.gguf`,
sha256 `6508b72361a7f57915e458aa92f8a6a90ba4cace778e3c88361fb3b3749baf4c`, superseding the
milestone-14 artifact (kept as the documented fallback per HANDOVER.md hard constraint #7,
at `models/Qwen3-1.7B-agri-final-Q4_K_M.milestone14-fallback.gguf`, sha256
`9c2241433b92a2ba45bab9e1eee398d774b8884030885c37ec0c141fd1bca5ce`).

## Decision / goal

Round 1's judge scorecard showed the submitted `tp_001` (a `full_rank` prompt, the family
milestone 10 chose specifically because it scored 6/6 offline) being **refused** by the
shipped model: *"I don't have the exact retail price data for Maize (white) in January 2024
for Am Timan, Melfi, Zouar, and Bardai in the format you're asking for... I can't reliably
recall individual historical price figures."* Investigate why, per HANDOVER's carried-forward
§6 finding.

## What was verified (not assumed)

- The eval harness (`scripts/evaluate_test_set.py`) supplies a training-shaped system
  prompt on every call. Milestone 13's default-system-prompt patch fires **only** when the
  caller supplies none — an `{%- else %}` branch, by design. **The eval harness can never
  exercise the branch milestone 13 shipped.** Confirmed by rendering both conditions through
  the actual GGUF-embedded template and diffing byte-for-byte.
- Measured the shipped GGUF under both conditions on the full `cross_market_ranking` test
  set, with `llm.reset()` before every generation (see next bullet for why that matters):

  | condition | `full_rank` | `lowest` | `highest` | total |
  |---|---|---|---|---|
  | A — eval harness's training system prompt | 6/6 | 7/7 | 3/6 | 16/19 |
  | B — no system message (the judge condition) | 4/6 | 6/7 | 1/6 | 11/19 |

  Under condition B, `tp_001` is refused — reproducing the Round 1 scorecard exactly.
- **A second, independent bug was found while measuring this**: `llama_cpp.Llama` at
  `temperature=0.0` is **not stateless across calls in the same process**. `evaluate_test_set.py`
  runs all 150 examples through one persistent instance. Verified directly: `tp_001`'s response
  flips from refusal to a correct ranking after ≥5 prior generations in the same instance, and
  `llm.reset()` restores the refusal. **Every accuracy number this project has reported was
  measured on a persistent instance and is order-dependent** — a genuine Gate 2 §3.4 exposure,
  independent of the system-prompt finding. All numbers in this milestone and going forward use
  `llm.reset()` before every generation, matching the fresh single-turn state a judge's request
  actually produces.
- **Root cause, tested directly, not guessed**: swept six candidate default system prompts
  (rewording the milestone-13 disclaimer six different ways, from "capability-first" phrasing to
  dropping the default entirely) against the shipped weights. **None recovered condition A's
  ranking accuracy** — all six scored 10–12/19, close to condition B's 11/19, regardless of
  wording. This ruled out "the disclaimer's wording is the problem."
  - Milestone 04 burned **one fixed system prompt** into all 1,200 training examples. Tested the
    implied hypothesis directly: set the default system message to the **verbatim training
    system prompt** (byte-identical to `evaluate_test_set.SYSTEM_PROMPT`, cross-checked against
    `dataset/sft_runB/train.jsonl`'s own `messages[0]`). This reproduced condition A's numbers
    **exactly** — `full_rank` 6/6, `lowest` 7/7, `highest` 3/6, total 16/19 — full recovery, not
    a partial improvement. **The model is system-prompt-brittle**: it only performs at its
    trained level when given the exact string it was trained under, not merely a message
    "in the spirit of" that string. Appending even one additional sentence to the verbatim
    prompt cost 2 of 19 ranking answers in a follow-up test — the brittleness is real and the
    string should not be edited at all.

## Fix adopted

Patched the default branch of the shipped GGUF's chat template (same mechanism as milestone 13
— an `{%- else %}` on `messages[0].role == 'system'`, fires only when the caller supplies none)
to inject the **verbatim training system prompt** in place of milestone 13's two-sentence
disclaimer. Template file: `data/runB_chat_template_v3_trainingsys.jinja`. Metadata-only patch
via `gguf_new_metadata.py`, applied to a copy of the exact shipping file — weights untouched by
construction, verified: all 310 tensors byte-identical to the pre-patch file (compared by
per-tensor sha256), `qwen3.context_length` still 4096 (milestone 14's fix undisturbed), the
thinking-mode-off mechanism (`<think>\n\n</think>\n\n`, milestone 04) still present in the
rendered output.

**Full 150-example evaluation, judge condition (no system message), `llm.reset()` per example:**

| family | shipped (pre-fix) | v3 (this fix) |
|---|---|---|
| `state_at_time` | 50/50 | 50/50 |
| `abstention_negative` | 26/26 | 26/26 |
| `cross_market_ranking` | 11/19 (58%) | **16/19 (84%)** |
| `trend_change` | 16/30 | 9/30 |
| `yoy_comparison` | 7/25 | 7/25 |
| **aggregate** | 110/150 | 108/150 |
| **`tp_001` (as submitted at Round 1)** | **refuses** | **correct order** |

`state_at_time` and `abstention_negative` hold at 100% — HANDOVER's hard constraint #7 (revert
if abstention or ranking degrades) is satisfied; ranking improved, nothing degraded.

**The aggregate moving 110→108 is not a regression.** Both `trend_change` numbers are scoring
luck, not capability: the pre-fix model answers "rose" on **30 of 30** `trend_change` prompts
under the judge condition — one canned direction, scoring 16/30 only because 16 of 30 truths
happen to be "rise." The v3 model spreads its guesses across fell/flat/rose but is equally
uninformed by the actual facts. Neither model has real trend capability; this is the same
mode-collapse failure documented in `milestones/07` (Run 1) and `milestones/12` (Run B),
unaddressed by this fix and out of scope for it. See `REPORT.md` §4.4.

**Profiler comparison** (five paired runs, alternating files, machine under normal interactive
load — not the "quiet machine" milestone 14 wanted but never captured): shipped 75.81–77.06
tok/s / 2,243.69–2,253.20 MB; v3 78.02–82.00 tok/s / 2,237.53–2,268.94 MB. v3 is not slower.
No throttling in any run. See `REPORT.md` §5 and `milestones/18` for the full clean
re-measurement this session also captured.

## Why this matters beyond fixing one prompt

Under Gate 2 §3.5 (anti-gaming — capability that appears reduced under evaluation conditions is
disqualification-eligible at organizers' discretion), a submitted showcase prompt that the shipped
model *refuses* under the exact condition judges use is a direct, provable exposure — not a
close call. This was caught by testing the actual judge condition rather than the condition the
project's own eval harness happened to use.

## Open risks / dependencies carried forward

- `trend_change`/`yoy_comparison` remain genuinely unresolved (unchanged from milestones 07/09/12)
  — see `REPORT.md` §4.4. This fix does not touch that family.
- System-prompt brittleness is now a documented, measured property of the shipped model, not
  merely inferred. Any future retraining pass should either preserve the exact training system
  prompt as the shipped default, or explicitly test robustness to prompt paraphrase as part of
  its own acceptance criteria.
- The `llm.reset()` non-determinism finding applies to **every** prior accuracy figure in this
  project's history (Run 1, Run A, Run B as originally reported) — not re-measured retroactively
  for all of them, since the per-family diagnoses those runs produced (mode collapse, memorization
  failure) do not depend on this effect. Only the exact aggregate percentages carry this caveat.
- See `milestones/16` for a second, independently discovered issue in `cross_market_ranking`
  (a data-generation leak, not a system-prompt effect) that further qualifies what this family's
  accuracy numbers mean.
