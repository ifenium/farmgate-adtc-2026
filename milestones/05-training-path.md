# 05 — Training Path

**Status:** Done (2026-08-19)

## Decision

Train locally on the M3 Pro with **MLX-LM** (QLoRA), not `bitsandbytes`+PyTorch/MPS. No cloud GPU fallback — Udutech/AGH Cloud's ADTC-specific credit program is confirmed closed.

## Options considered

- **Udutech GPU credits (cloud fallback)** — the plan HANDOVER §7 named for Day 3–4.
- **bitsandbytes QLoRA on PyTorch/MPS** — the "standard" QLoRA tooling path (Unsloth/PEFT-adjacent), contingent on whether its historically CUDA-only backend has caught up on Apple Silicon.
- **MLX-LM QLoRA** — Apple's own array framework, purpose-built for Apple Silicon.

## What was verified (not assumed)

**Udutech GPU credits:** WebFetch on the Devpost/AGH Cloud application links returned unhelpful boilerplate (JS-rendered SPA) twice, so switched to the actual browser tool to render it. Confirmed on the live page: the "Africa Deep Tech Challenge 2026" program listing shows **status "Closed"**, **deadline 31 Jul 2026 at 8:00 PM GMT**, button **"Applications Closed"** — the application window closed before this project's Day 1 (18 Aug 2026) even started. HANDOVER §7's Day 1 action item was already stale when written. AGH Cloud's generic, non-ADTC "Compute Support Options" (Cloud Credits, immediate setup) exist as an unverified fallback if a cloud need arises later, but carry no ADTC-specific guarantee and weren't pursued further given the local path worked.

**bitsandbytes on MPS — premise checked, found partially outdated:** the working assumption ("bitsandbytes doesn't support Metal") is no longer fully true. Found via GitHub: a native MPS backend was merged into mainline `bitsandbytes-foundation/bitsandbytes` on 19 Feb 2026 (PR #1875, v0.50.0), using Metal kernels hosted on the HF Hub. Installed `bitsandbytes==0.50.1` and tested empirically rather than trusting the merge:
- A real `bnb.nn.Linear4bit` layer forward pass on `mps` device: works.
- A minimal QLoRA-shaped setup (frozen 4-bit base + trainable LoRA A/B, AdamW, 10 steps): **loss goes to NaN after exactly one optimizer step, at every learning rate tried (1e-2, 1e-4) — ruling out a hyperparameter mistake.** Isolated to compute dtype: fp16 reliably NaNs, **bf16 and fp32 both train cleanly** (loss decreases smoothly over 10 steps in both).
- Read of the underlying PR history: a companion PR (#1853, an alternative MPS approach) was rejected by the maintainer specifically over "supply chain concern" — the MPS backend ecosystem here is young and still being actively contested/refined, not a settled, battle-tested path.

**MLX-LM — QLoRA and GGUF path both checked against source, not docs alone:**
- QLoRA is automatic in `mlx_lm.lora`: if `--model` points to an MLX-quantized checkpoint (`convert.py -q`), training is QLoRA; no separate flag.
- `mlx_lm.fuse --export-gguf` is explicitly documented as limited to Mistral/Mixtral/Llama-style architectures, and explicitly **excludes Qwen2** — Qwen3 isn't listed at all, so this specific convenience path cannot be used for our model.
- Read `fuse.py`/`utils.py` source directly: `mlx_lm.fuse`'s **default** output (no `--export-gguf`) writes a standard Hugging Face–format directory — `.safetensors` weights, `config.json`, tokenizer files — completely architecture-agnostic.
- Checked our own cloned llama.cpp checkout (not memory): `conversion/qwen.py` line 159 registers `Qwen3ForCausalLM` explicitly (`@ModelBase.register("Qwen3ForCausalLM", "Qwen3Model")`), with a `Qwen/Qwen3-8B` usage example. This is the exact `architectures` value in a Qwen3 `config.json`.
- Verified path end-to-end: `mlx_lm.lora` (QLoRA) → `mlx_lm.fuse` (HF-format, no `--export-gguf`) → llama.cpp's own `convert_hf_to_gguf.py`/`conversion/qwen.py` (same converter lineage that produced every GGUF already used in this project) → `llama-quantize`.

## Why MLX-LM over bitsandbytes/MPS

Both are technically usable (bitsandbytes works if bf16/fp32 compute dtype is forced). The deciding factor is maturity and integration risk under a 6-day deadline with no cloud fallback: MLX-LM is Apple's purpose-built, widely-used framework for this exact hardware/task; bitsandbytes' MPS backend is six months old, already showed a real reproducible numerical bug on the very first test run, and had a sibling PR rejected over dependency-trust concerns. HANDOVER §4 already established the project's own rule for this kind of tradeoff ("tooling risk is the biggest threat") — same logic applies here.

## --mlock: not set by the profiler, configurable in our own app code

Full grep of `adtc_profiler`'s source: **`--mlock`/`--load-mode` is never passed to `llama-bench`, and `use_mlock` is never passed to `llama-cpp-python`'s `Llama()` in the accuracy path.** Both default off (`llama-bench`'s own default is `--load-mode auto`, which does not lock pages). This means judges' own audit runs — which use the same unmodified profiler — will also run without mlock, since that's not something a participant's repo can override inside the reference tool.

Tested `-lm mlock` directly against our build: works without error on this Mac (no elevated privilege needed here), no meaningful throughput regression (82.3 vs 87.1 tok/s — within normal run-to-run noise). Confirms the mechanism itself isn't broken in our build, not that the judges' sandbox grants the same privilege.

**Recommendation:** set `use_mlock=True` in our own application's `llama-cpp-python` invocation (the actual product code, not the profiler) — *if* HANDOVER §3's standalone-GGUF question resolves in a direction where our app code is what actually runs at judging time. This is a cheap, low-downside mitigation given our measured peak RSS (~2.4–2.7 GB, milestone 01) sits comfortably under the 7 GB ceiling — there's no memory-pressure reason not to lock those pages. Two caveats worth carrying forward: (1) mlock requires `RLIMIT_MEMLOCK` headroom, which some sandboxed/containerized environments restrict — if the judges' sandbox doesn't grant it, `use_mlock=True` can either silently no-op or hard-fail depending on build flags, so this needs testing in whatever environment actually ships, not assumed from this Mac; (2) if judges load the raw GGUF directly in LM Studio/Ollama instead of our app (§3 unresolved), this setting has no effect at all — it only helps if our own runtime code is what launches inference.

## P_thermal is untested and untestable on this hardware

Scoring applies a flat −10 if core/package temp exceeds 85°C or throttling is flagged (HANDOVER §2). This cannot be measured meaningfully on the M3 Pro dev machine: its thermal profile (Apple Silicon SoC, different die, different TDP, different cooling solution) says nothing about how a 10th–12th gen Intel i5 or Ryzen 5 behaves under sustained CPU-only inference — the two chips throttle at different temperatures under entirely different thermal designs. `adtc-profiler`'s own `thermal.py` already can't read `core_temp_c_peak` here anyway (no `ismc` CLI, see milestone 03/04) — it would report `null` even if the number meant something, which it wouldn't.

Nothing to verify here; only mitigations to note in REPORT.md as deliberate design choices rather than measured outcomes, since they were already true by design before this question came up:
- **Short, terse gold answers** (state_at_time/trend/yoy/ranking all render to one line — see milestone 02's schema) keep generation runs brief, minimizing sustained-load duration per query rather than long-form output that would keep the CPU pegged.
- **Modest context length** (2048/4096 tested in the Day 1 bake-off, not larger) keeps per-query compute bounded — no long-context workloads that would extend sustained high-utilization periods.
- Model size itself (1.7B, Q4_K_M) keeps per-token compute low relative to the 3B/Gemma alternatives ruled out in milestone 01, which independently reduces sustained thermal load vs. the class of model this project could have shipped.

None of this is a substitute for a real thermal measurement on target-class hardware — it's what's honestly available to say without one.

## End-to-end dry run (2026-08-19): 20 examples, 5 steps, real breakage found and fixed

Ran the full chain for real: `mlx_lm.convert` (download + 4-bit quantize `Qwen/Qwen3-1.7B`) → `mlx_lm.lora` (QLoRA, 20 train examples, 5 iters) → `mlx_lm.fuse --dequantize` → llama.cpp's `convert_hf_to_gguf.py` → `llama-quantize` → load in both raw `llama-cli` and the actual `adtc-profiler run` pipeline. This is exactly the kind of check the HANDOVER-established practice calls for — find handoff breakage now, not on Day 4 with no cloud fallback.

**Found a real bug, not a toy-scale one:** `mlx_lm.convert --hf-path Qwen/Qwen3-1.7B -q` downloaded 3.4 GB and quantized successfully ("Quantized model with 4.501 bits per weight"), then **crashed on save with zero output written** — `mlx_lm.utils.save()`'s very first line calls `hf_repo_to_path()` → `snapshot_download(hf_repo, local_files_only=True)`, which demands the *entire* upstream repo be present locally, including `.gitattributes`, `LICENSE`, `README.md` — three files irrelevant to loading the model, that its own preceding fetch step never requested, and refuses network access to complete despite having just used the network successfully for 3.4 GB. Root cause confirmed via the actual cache directory listing: all 9 weight/config/tokenizer files were present and correct; only the 3 non-essential metadata files were missing. Fixed by fetching those 3 files directly via `huggingface_hub.hf_hub_download`, then re-running — succeeded cleanly on retry.

**Practical fix adopted for the real Day 3–4 run:** never pass a bare `--hf-path <repo-id>` string to `mlx_lm.convert`/`mlx_lm.fuse`. Always point `--model`/`--hf-path` at a local directory that's already confirmed to exist — `save()`'s `src_path.exists()` check short-circuits the whole crash path when given a real local directory (confirmed: the later `mlx_lm.fuse` call, pointed at the local `models/Qwen3-1.7B-mlx-4bit/` directory, completed with no issue). For the real run: pre-download with `huggingface_hub.snapshot_download` (full repo, not just weights) before ever invoking `mlx_lm.convert`.

**Chat-template cross-check (the open risk from milestone 04, now closed):** the HF/MLX tokenizer's `chat_template.jinja` (from `Qwen/Qwen3-1.7B`) is textually *different* from the GGUF-embedded one (from unsloth's fork) — different Jinja refactoring, extra content-type guards, different iteration style. But rendering the same test conversation through both, via `transformers.AutoTokenizer.apply_chat_template`, produced **byte-for-byte identical output**, including the empty `<think>\n\n</think>\n\n` block. Confirmed empirically, not assumed from the diff.

**Training signal:** train loss 5.212 → 3.135 monotonically over 5 iterations (peak mem 2.36 GB). Real, healthy learning on the very first attempt.

**Quantized dry-run GGUF loaded and generated successfully** — through both raw `llama-cli` and a real `adtc-profiler run --skip-accuracy` call (schema-valid `submission.json`, fraud-check `params_match: true` against the claimed 1.7B). Output quality is exactly what "coherent-if-undertrained" should look like: fluent, correctly-shaped single-sentence answers following the training format ("The retail price of X in Y, Country in Month Year was Z"), right currency instinct on the training-set prompt (Kenya → "Ksh"), no crashes, no gibberish, no repetition loops — a completely different quality profile from the raw base model's Swahili failures (see below). Not yet fact-accurate, which is correct and expected: 5 steps is nowhere near enough to memorize anything, only to pick up format/register.

**Verdict: the pipeline works end to end.** One real bug found and fixed (the `hf_repo_to_path` crash) — exactly the kind of thing that would have cost real time on Day 3–4 with no cloud fallback to lean on.

## Open risks / dependencies carried forward

- The real Day 3–4 run is still full scale (900 train examples, many more iterations) — the dry run de-risks the *pipeline*, not training duration, hyperparameter choices, or final quality.
- Pre-download the full `Qwen/Qwen3-1.7B` snapshot (`snapshot_download`, not `--hf-path`) before starting the real run, per the fix above.
- Inherits the standalone-GGUF dependency and thinking-mode verification items already carried forward in milestones 01–04.
