# Provenance package (Gate 2 §3.1)

This folder was assembled 2026-09-15 (see `milestones/17`). None of it existed before that
session — the training run it documents (Run B, shipped) happened on 2026-08-19, and none of
this project's original tooling produced a `provenance/`-shaped record of it. Everything here
was **recovered and reconstructed**, then independently verified against the committed artifacts
it describes, not assumed correct from memory or prose. Where recovery was partial, that is
stated plainly below rather than padded.

## What's here

| Path | What it is | Recovery method |
|---|---|---|
| `CHECKSUMS.txt` | SHA256 of base model, adapter, final GGUF | Adapter/GGUF: recomputed directly. Base: HF Hub's own local LFS cache manifest (`trees/<rev>.json`) — canonical, not recomputed |
| `DATASET_LICENSE.md` | WFP VAM CC BY 3.0 IGO attribution, methodology citation, tooling licenses | Source docs read directly (CKAN API metadata, `tools/llama.cpp/LICENSE`) |
| `merge_and_quantize.sh` | Fuse → convert → quantize → patch → promote chain, runnable, `--base-only` mode | Reconstructed from session-transcript tool calls; the base-only path was run live this session to build `before_after/` |
| `adapter/` | Run B's LoRA adapter — 7 checkpoints + `adapter_config.json` | Copied directly from `adapters_runB/`, already on disk, never previously committed |
| `training_logs/` | Per-step val/train loss for the dry run, Run 1, Run A leg 1, and Run B | Recovered from the Claude Code session transcript that ran the training (see below) |
| `before_after/` | The mandatory ≥2-prompt comparison vs. the unmodified base model | Generated live this session from a freshly converted+quantized base GGUF |

## Training-log recovery: how, and what's missing

No `.log` file from any of the four training runs (dry run, Run 1, Run A, Run B) survives on
disk — `mlx_lm lora` was launched with its stdout redirected to `/tmp/runB.log` and equivalents
(see the verbatim launch command in `milestones/17`), and `/tmp` does not persist across the
machine's own cleanup cycles. What does survive: the **Claude Code session transcript** that
issued those training commands and periodically polled their output with `tail`, which is
retained by the harness independently of `/tmp`.

Extracted every `Iter N: Val loss X` and `Iter N: Train loss X, ...` line from that transcript,
attributed each to one of the four runs by transcript line-range and corroborating signal
(learning rate — 1e-5 for the dry run/Run 1/Run B, 1e-4 for Run A — and token-count
progression), deduplicated against repeated polling reads of the same still-growing log file, and
cross-checked the resulting curves against every headline number already published in
`milestones/07`, `11`, and `12`. All three matched exactly (see `milestones/17` for the
comparison table) — this was the check that confirmed the recovery method was sound, not merely
plausible-looking.

**Validation-loss curves are complete for all three real training runs** (11 points for Run 1,
9 for Run A leg 1, 13 — all of them — for Run B, since MLX-LM's own `--steps-per-eval` schedule
is sparse enough that `tail`-based polling never dropped a val-loss line). **Train-loss curves
are only partially recovered** — MLX-LM reports train loss every `--steps-per-report` (20) steps,
which is dense enough that polling-based `tail` reads did drop earlier lines as each run
progressed. Run B retained 12 of its 60 expected train-loss lines (iters 200, 220, 240, 260, 280,
1000, 1020, 1040, 1060, 1080, 1180, 1200); Run 1 and Run A retained more (partial coverage
throughout, denser toward each run's end, per the same tail-truncation mechanism). This is
disclosed as a real gap against Gate 2 §3.1's "per-step training logs" requirement, not claimed
as complete.

## The `dataset/sft_runB/` reconstruction

`scripts/generate_sft_runB.py` (added this session) is a **verified, not assumed**
reconstruction of the transformation that produced `dataset/sft_runB/` — the file MLX-LM actually
trained on — from `dataset_runB/{train,val}.jsonl`. Running it against the committed
`dataset_runB/train.jsonl` reproduces the exact set of 166 duplicate rows found in the committed
`dataset/sft_runB/train.jsonl`: same 124 distinct duplicated source examples (82 duplicated
once, 42 duplicated twice), confirmed by exact `id`-set match. A sample of the rendered chat
`text` field matches byte-for-byte. This closes a real gap: the duplication was previously
described in `milestones/11`/`12` only as "oversampling (54/33/13 → 36/38/26)" — that it is
literal verbatim row duplication (not new generations) was not previously stated anywhere.

## Base-model comparison: what was and wasn't reproduced from scratch

The base Qwen3 1.7B GGUF used for the `before_after/` exhibit was converted fresh, this session,
directly from the pinned HF Hub snapshot (`Qwen/Qwen3-1.7B`, revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, still present in the local cache) — not a re-download,
and not the same file as any earlier bake-off artifact (the original Day-1 bake-off's base GGUF
was deleted in the Aug-25 cleanup referenced in `milestones/13`; see `milestones/17` for the full
trace). It is **not** committed as a binary — at 1.28 GB it would both violate this repo's own
"no GGUF in git" rule and exceed GitHub's 100 MB per-file limit — reproduce it with
`merge_and_quantize.sh --base-only`.

One structural difference from the shipped fine-tuned GGUF was found and is disclosed rather than
silently reconciled: the base conversion carries an explicit `output.weight` tensor (311 tensors
total) where the fine-tuned GGUF has tied embeddings and omits it (310 tensors). Traced to the
upstream checkpoint's own state dict, which stores a redundant `lm_head.weight` despite
`config.json` declaring `tie_word_embeddings: true` — the fine-tune's conversion path went through
MLX's own 4-bit-quantize/dequantize round trip first, which does not preserve that redundant
tensor. Functionally immaterial (llama.cpp uses the tied embedding table for output projection
when `output.weight` is absent) and does not affect the before/after text comparison, which is
what §3.1 actually requires.

## Known gaps, stated plainly

- Per-step **train**-loss logs are partial, not complete (see above).
- The base model's HF revision was not pinned in the original 2026-08-19 training run — recovered
  retrospectively from `refs/main`'s state at the time, not an originally-enforced pin.
  `merge_and_quantize.sh` pins it explicitly going forward.
- `dataset/sft_runB/train.jsonl`'s exact row *order* (post-shuffle) is not recoverable — only the
  row *set* is exactly reproduced. This does not affect training correctness.
- Six pre-existing project scripts (everything except this session's additions) hardcode absolute
  `/Users/Apple/Documents/hack/...` paths rather than resolving relative to the repo root — a
  portability wart, not fixed in this pass; noted in `milestones/17`.
