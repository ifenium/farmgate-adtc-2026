# 17 — Gate 2 Provenance Assembly (§3.1)

**Status:** Done (2026-09-15). `provenance/` folder added; `REPORT.md` §8 added;
`metadata.json` carries `git_commit_sha` (added in a follow-up commit, see below).

## Decision / goal

Gate 2 §3.1 mandates a `provenance/` folder (adapter weights + config, training script/config,
per-step training logs, dataset sample with license, checksums of base/adapter/final GGUF,
merge+quantization script) and a REPORT.md section with a before/after comparison on ≥2 prompts
against the unmodified base model. None of this existed before this session — verified absent,
not assumed, by checking both the working directory and the submitted repo clone directly.

## What was verified (not assumed)

- **`provenance/` did not exist** in either location. **`REPORT.md` had no provenance section**
  (headings enumerated: §1–§7, no §8). **`metadata.json` had no `git_commit_sha` field** (10 keys,
  none matching `commit|sha|revision`).
- **No per-step training log file exists anywhere** — `/tmp/runB.log` and equivalents for Run 1
  and Run A are gone; the only `.log` files in the project (`results/*_ctx*.log`) are the Day-1
  bake-off's and are all zero bytes. **Recovered instead from this project's own Claude Code
  session transcript** (`dc24f4cd-ce1e-4f27-a2eb-00e5242e8bd6.jsonl`), which preserved the tool
  output of the `mlx_lm lora` training calls. Segmented cleanly into four distinct runs by
  transcript line-range and corroborating signal (learning rate, token-count progression): a
  5-iteration dry run (milestone 05), Run 1 (1000 iters, LR 1e-5), Run A leg 1 (gated at 1500
  iters, LR 1e-4), and Run B (1200 iters, LR 1e-5, the shipped run). Extracted validation-loss and
  train-loss points for each, deduped against transcript polling re-reads, and cross-checked
  against every headline number already published in the milestones:

  | run | recovered curve | milestone claim | match |
  |---|---|---|---|
  | Run 1 | 5.090 → 0.324 @iter900, 0.328 @iter1000 (11 val points) | "5.09 → 0.328" (`milestones/07`) | exact |
  | Run A leg 1 | 0.314 @iter500 → 0.374 @iter1500 (9 val points) | "bottomed 0.314... rose to 0.374" (`milestones/11`) | exact |
  | Run B | 4.886 → 0.263 @iter800, 0.269–0.270 stable through 1200 (13 val points, complete) | "bottomed 0.263 at iter 800... stable through 1200" (`milestones/12`) | exact |

  Written to `provenance/training_logs/` as one JSONL per run per metric (8 files). Train-loss
  telemetry survives only partially for each run (transcript polling used `tail`, which drops
  earlier lines as a run progresses) — disclosed as such in `provenance/README.md`, not padded
  or estimated.
- **The file MLX-LM actually trained on, `dataset/sft_runB/train.jsonl`, had no generating
  script.** `format_sft_chat.py` writes only `dataset/sft/`; `relabel_state_at_time_runB.py`
  writes only `dataset_runB/`. Nothing bridges the two. Recovered the exact transformation from
  the same session transcript (two inline `python3 -c` heredocs) and **reconstructed it as a
  committed script**, `scripts/generate_sft_runB.py`. Verified, not assumed: running the
  reconstruction against the committed `dataset_runB/train.jsonl` reproduces the exact 166-row
  duplicate set found in the committed `dataset/sft_runB/train.jsonl` — same 124 distinct
  duplicated source rows (82 duplicated once, 42 duplicated twice), confirmed by exact `id`-set
  match, not just a matching count. A 30-example sample of the chat-rendered `text` field also
  matches byte-for-byte. (The final in-file shuffle order is not recoverable — the original run's
  exact RNG call sequence for that step is lost — but this does not affect training correctness
  or the row-level provenance claim.) **The 166 duplicate rows were previously described in the
  milestones only as "oversampling (54/33/13 → 36/38/26)"** — that they are literal verbatim
  row duplication, not new generations, was not previously disclosed anywhere and is now stated
  plainly in the reconstructed script's docstring and in `provenance/README.md`.
- **No merge/quantize script existed**, only incomplete prose in `milestones/07` and `12` that
  stopped at `llama-quantize` and omitted the base 4-bit quantization step, both metadata
  patches, and the final promotion-to-shipping-filename step. Recovered the full chain from the
  transcript (six steps, each with its line number and timestamp) and wrote it as a real,
  runnable script, `provenance/merge_and_quantize.sh`, with a `--base-only` mode for
  reproducing the before/after exhibit's base-model GGUF without needing a trained adapter.
  Confirmed the shipped hash closes the chain: transcript-recorded `shasum` outputs at two
  points in the original run both read `9c2241433b92a2ba45bab9e1eee398d774b8884030885c37ec0c141fd1bca5ce`
  — the milestone-14 artifact's actual hash.
- **Base model weights survive at the exact revision cited in the milestones**
  (`Qwen/Qwen3-1.7B`, revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`) in the local HF cache —
  confirmed via `refs/main` and the snapshot directory name, both independently. The revision
  itself was **not pinned** in the original training run (`mlx_lm convert --hf-path Qwen/Qwen3-1.7B`,
  no `--revision` flag) and appears in **zero** committed project files before this session —
  `70d244cc…` is a retrospective read of what `refs/main` happened to be on 2026-08-19, not an
  enforced pin. `provenance/merge_and_quantize.sh` now pins it explicitly going forward.
- **Base SHA256 values are not absent, only never project-recorded.** HuggingFace's local LFS
  cache manifest (`trees/70d244cc….json`) carries the canonical `lfs_sha256` for every weight
  file, and the cache's own blob filenames on disk are literally those hashes — cited directly in
  `provenance/CHECKSUMS.txt` rather than recomputed (recomputing a combined 4+ GB was unnecessary:
  the values are the same by construction of how the HF Hub client stores LFS objects).
- **Built the mandatory before/after exhibit from the pinned revision, no re-download needed.**
  Converted the untouched base snapshot directly (`convert_hf_to_gguf.py` → `llama-quantize`,
  Q4_K_M, no LoRA, no dequantize round-trip) and generated all three exhibit prompts (`tp_001`,
  the original submitted `tp_002`, and a general self-description question) through each model's
  own embedded chat template with no system message — the same judge condition milestone 15
  investigated. Full transcripts and analysis: `provenance/before_after/base_vs_finetuned.md`.
  **A tensor-count discrepancy was found and understood, not ignored**: the freshly-converted
  base GGUF has 311 tensors (an explicit `output.weight`) vs. the shipped fine-tune's 310 (tied
  embeddings, `output.weight` omitted). Traced to the checkpoint's own upstream state dict, which
  stores a redundant `lm_head.weight` even though `config.json` declares `tie_word_embeddings: true`
  — the fine-tune's conversion path went through MLX's own 4-bit-quantize-then-dequantize round
  trip first, which does not preserve that redundant tensor. Functionally immaterial (llama.cpp
  falls back to the tied embedding table for output projection when `output.weight` is absent;
  verified the base GGUF loads and generates coherent text) but noted for completeness.

## What was added

```
provenance/
├── README.md                        # this package's own index and disclosure notes
├── CHECKSUMS.txt                    # base / adapter / final-GGUF SHA256, all sourced, none invented
├── DATASET_LICENSE.md               # WFP VAM CC BY 3.0 IGO attribution, afritemp-bench citation
├── merge_and_quantize.sh            # reconstructed, runnable, --base-only mode included
├── adapter/                          # adapters_runB/, all 7 checkpoints + config (133 MiB)
├── training_logs/                    # 8 files: {dry_run,run1,runA_leg1,runB}_{val,train}_loss.jsonl
└── before_after/
    ├── base_vs_finetuned.md          # the mandatory ≥2-prompt exhibit, plus a third general-capability prompt
    └── before_after_raw.json         # raw generation output backing the exhibit
```

`data/qwen3_chat_template.jinja` and the three `runB_chat_template*.jinja` files, plus
`data/wfp_2023.csv`/`wfp_2024.csv`, were added to the repo root (`data/`) — previously referenced
by committed scripts but never committed themselves, which meant an organizer could not re-derive
this project's own headline WFP corpus statistic (223,549 African observations / 39 countries /
1,922 markets in the 2024 file alone) without independently sourcing the same CSVs. `README.md`
and `LICENSE` (Apache 2.0, matching the base model's own license) were also added — both were
absent; the official submission template ships both and is itself GPL-3.0-licensed, but that
license governs the template repository's own boilerplate, not a mandate on participant code.

`metadata.json`'s `git_commit_sha` field is added in a **follow-up commit** referencing this
commit's own hash — a file cannot self-referentially contain the hash of the commit that
introduces it, so the standard two-commit pattern is used here (see the git log for the exact
pair).

## Open risks / dependencies carried forward

- The six pre-existing project scripts (`generate_sft_dataset.py`, `format_sft_chat.py`,
  `evaluate_test_set.py`, `relabel_state_at_time_runB.py`, `ood_check_runB.sh`,
  `swahili_base_check.sh`) all hardcode absolute `/Users/Apple/Documents/hack/...` paths rather
  than resolving relative to the repo root. `scripts/generate_sft_runB.py` (this session, §3.1
  reconstruction) does not have this problem. Not fixed for the other six — out of scope for this
  session, noted here for a future pass.
- `dataset/stats.json` still describes the 1,200-row `all.jsonl` split (900/150/150), not the
  1,066-row file training actually consumed after oversampling. Anyone reading `stats.json` as
  "the training set size" is off by 166 — documented in `provenance/README.md` rather than
  silently left for a reader to discover.
- The adapter-only checkpoints (`adapters_runB/0000200_adapters.safetensors` through
  `0001000_...`) are included for full training-progression transparency; only
  `adapters.safetensors` (== the `0001200` checkpoint, confirmed by matching sha256) is what
  actually produced the shipped GGUF.
