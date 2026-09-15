# ADTC 2026 — Technical Report

**Track:** Agriculture — crop advisory and market literacy
**Model:** Qwen3 1.7B, QLoRA fine-tuned, GGUF Q4_K_M (1.03 GB)
**Team:** ferrarri — feoluwa Oyelakin (oyeife@gmail.com), GitHub: ifenium

---

**Executive summary.** An offline Qwen3 1.7B assistant for African agricultural market prices (WFP VAM data through December 2024), QLoRA fine-tuned and quantized to GGUF Q4_K_M (1.03 GB), running entirely on-device with zero cloud dependency. The central engineering result: a diagnosed contradiction between two training families sharing an identical prompt shape was driving confident price fabrication; relabeling one family to a calibrated hedge fixed both at once — `state_at_time` 0%→100%, `gap_within_range` 0%→100% with zero changes to its own training data. Round 1 judging surfaced two further, independently investigated findings, both fixed before this resubmission: the shipped model is **system-prompt-brittle** — it only performs at its trained level when given the exact system prompt it trained under, which caused the submitted `full_rank` showcase prompt to be refused under the actual judge condition despite scoring well in this project's own evaluation harness — fixed by shipping the verbatim training system prompt as the GGUF's own default (§4.7); and `cross_market_ranking`'s apparent skill was found to be substantially a data-generation artifact (the generator lists candidate markets in price order, so "rank lowest to highest" is partly answerable by echoing the prompt) — disclosed in full, with the showcase prompt replaced (§4.8, §6). Measured on development hardware across three fresh, git-checkout-verified profiler runs on the exact shipping file: median 83.86 tok/s generation, 2,298.92 MB peak RSS — see §5 for the full range and an explicit caveat on how this is expected to differ on x86-64 target hardware. Accuracy is now reported under the condition judges actually use (no caller-supplied system message, one fresh generation per example) rather than the project's original persistent-instance harness, which was found to be order-dependent (§4.7): **108/150 (72.0%)** on the held-out test set. One capability remains named as unresolved rather than hidden: `trend_change`/`yoy_comparison` price-direction reasoning, where the model still collapses to a single canned answer regardless of the actual facts (§4.4). Full model provenance — base model revision, training logs, adapter weights, checksums, and a before/after comparison against the unmodified base model — is in `provenance/` and summarized in §8.

---

## 1. Problem

Smallholder farmers, traders, and buyers across Africa need reliable market price information to make basic economic decisions — is this a fair price, is it rising or falling, where should I sell — but that information is often scattered across national market-board bulletins, radio reports, and word of mouth, unavailable offline, and unavailable in a form a non-specialist can query directly. Cloud-hosted assistants require API fees, stable connectivity, and sustained electricity — exactly the resources that are least reliable in the settings this data would help most.

This submission targets that gap directly: an offline, on-device assistant that answers agricultural market-price questions — direct lookups, trend comparisons, cross-market rankings — trained on real WFP VAM price data, running entirely on the ADTC Standard Laptop with zero cloud dependency.

The target user is a trader, extension worker, or NGO field staffer who needs a quick, honest answer to "what's this crop worth, and is it moving" without needing internet access or specialist tooling.

---

## 2. Design Decisions

### 2.1 Model selection — measured, not assumed

Four candidates were bake-off tested on identical CPU-only hardware before commitment: Qwen3 1.7B, Llama 3.2 1B, Llama 3.2 3B (control), and Gemma 4 E2B (upside candidate). Full methodology: `results/bakeoff-day1.md`.

| Model | Quant | File size | Peak RSS | TG tok/s |
|---|---|---|---|---|
| Llama 3.2 1B | Q4_K_M | 0.75 GB | 1.7–1.8 GB | 129–133 |
| **Qwen3 1.7B (chosen)** | Q4_K_M | 1.03 GB | 2.4–2.7 GB | 87–92 |
| Llama 3.2 3B (control) | Q4_K_M | 1.88 GB | 4.1–4.4 GB | 44–54 |
| Gemma 4 E2B | UD-Q4_K_XL | 2.97 GB | 4.0–4.5 GB | 49–50 |

**Gemma 4 E2B was ruled out on measurement, not guesswork.** It was picked for an estimated ~3 GB memory ceiling; measured peak RSS (4.0–4.5 GB) landed in the 3B control's class instead, because its UD-Q4_K_XL file is 2.97 GB on disk — larger than Llama 3.2 3B's own Q4_K_M — regardless of the "E2B" name. A speculative sub-1 GB variant was checked against the actual repo listing before any time was spent chasing it; it doesn't exist as a downloadable artifact. Qwen3 1.7B was chosen over the faster Llama 3.2 1B for Apache 2.0 licensing, first-class QLoRA tooling support, and a stronger multilingual base; Llama 3.2 3B was carried only as a size-class control, ruled out by the scoring formula's own math before accuracy is even measured.

### 2.2 Domain and dataset methodology

Agriculture was chosen over Healthcare (malaria/maternal health) on a data-availability scan, not a topic preference. [WFP VAM's Global Food Prices dataset](https://data.humdata.org/dataset/global-wfp-food-prices) was confirmed — by actually downloading and parsing it, not reading documentation — to provide 223,549 African price observations across 39 countries and 1,922 markets in 2024 alone, under a clean **CC BY 3.0 IGO** license (`cc-by-igo`) with no non-commercial restriction. *Price data sourced from the World Food Programme (WFP) Vulnerability Analysis and Mapping (VAM) unit's Global Food Prices dataset, licensed CC BY 3.0 IGO. No endorsement by WFP is implied.* Healthcare's best-structured source (WHO/IMCI protocol documents) was confirmed CC BY-NC-SA 3.0 IGO — a direct conflict with this challenge's commercialization-residency prize track.

The methodological approach — gold labels computed by verifiable arithmetic rather than LLM-judged distillation — is adapted from [`africatic/afritemp-bench`](https://huggingface.co/datasets/africatic/afritemp-bench) (12,568 examples of temporal reasoning over African economic indicators, same verifiable-arithmetic-labels approach) as a methodology template; no data or code from that dataset is reused. See `provenance/DATASET_LICENSE.md` for the full citation and license trail.

The core methodological bet: **gold labels for the fine-tuning set are computed by verifiable arithmetic over structured data, not LLM-judged or hand-written.** Five generator families were built against the cleaned WFP corpus (Retail pricetype, deduplicated, null/zero prices dropped):

| Family | Count | Tests |
|---|---|---|
| `state_at_time` | 400 | Direct price lookup |
| `trend_change` | 240 | Two-point rise/fall/flat, threshold-classified |
| `yoy_comparison` | 200 | Calendar-aligned year-over-year comparison |
| `cross_market_ranking` | 160 | N-market ranking, unit/currency-matched |
| `abstention_negative` | 200 | Correct refusal — real data gaps and post-cutoff dates |

1,200 examples total, split 900/150/150 (train/val/test), stratified by family and subtype. Every gold answer traces back to specific source CSV rows for auditability. Full schema and generation logic: `scripts/generate_sft_dataset.py`.

### 2.3 Training approach

QLoRA via **MLX-LM**, not `bitsandbytes`/PyTorch. `bitsandbytes`'s historically CUDA-only backend gained genuine Apple Silicon MPS support in February 2026, but empirical testing (a real forward/backward pass, not just an import check) found it reliably NaNs in fp16 at every learning rate tried — a real, reproducible backend bug, not a hyperparameter mistake — while bf16/fp32 trained cleanly. MLX-LM, Apple's purpose-built framework for this hardware, was chosen as the lower-integration-risk path given no cloud GPU fallback was available (the Udutech/AGH Cloud credit program for this challenge closed 31 July 2026, before this project's timeline began).

A 20-example, 5-step dry run of the complete pipeline — train → fuse → convert to GGUF → quantize → load — was run before committing to full-scale training, specifically to surface integration breakage early. It found one: `mlx_lm.convert`, pointed at a bare Hugging Face repo ID, crashes on save because its metadata-resolution step demands a complete local repo mirror (including irrelevant files like `LICENSE`/`README.md`) and refuses network access to complete it despite having just used the network successfully for the multi-gigabyte weight download. Fixed by always converting from a pre-verified local directory rather than a repo ID string.

---

## 3. Constraints

**Hardware.** Target is the ADTC Standard Laptop (Intel/AMD x86-64, 8 GB RAM, integrated graphics, Ubuntu 22.04). Development happened on Apple Silicon (M3 Pro, arm64) — a materially different CPU architecture (NEON vs AVX2/AVX512 SIMD paths) and GPU model. All development-machine benchmarks in this report are relative-ranking evidence between our own candidates, not predictions of absolute target-hardware performance.

**Evaluation architecture — resolved, not assumed.** Whether judges run the standalone GGUF or a full submitted application was an open question through most of this project. Resolved by reading three primary sources directly: the ADTC FAQ, the official submission template's actual file structure, and its README. **Judges run the bare GGUF only.** The submission template has no code directory, no application entrypoint, no Docker Compose — `metadata.json`, `download_model.sh`, `REPORT.md`, and the model file are the entire submission. This means:
- No retrieval-augmented generation or tool-use layer can run during any part of scoring — not the automated telemetry, not the live judge chat, not the accuracy benchmark. There is no mechanism for external data to enter the evaluation-time prompt at all.
- The fine-tune has to carry 100% of accuracy on its own. This directly shaped the design decisions in §4.
- The required `cross_disciplinary_pairing` metadata claim is realized through training methodology (arithmetic-derived gold labels over structured economic data — an applied data-science integration) rather than a runtime integration, since there is no infrastructure to run one.

**No cloud GPU fallback.** Confirmed closed (§2.3) — training had to work reliably on the local development machine with no backup path.

**Data licensing.** WFP VAM's `cc-by-igo` license was verified before any development time was spent on it, specifically to avoid the non-commercial licensing trap found in an adjacent reference dataset (`africatic/afritemp-bench`'s WGI/World Bank components), which would have conflicted with this challenge's commercialization-residency prize.

---

## 4. Findings

### 4.1 The measured failure: fine-tuning as a fact database doesn't hold at 1.7B

The first full training pass (1000 iterations, LoRA rank 8, 16 of 28 layers, 900 examples) converged cleanly by loss (val loss 5.09 → 0.328). **Generation-based, per-family grading on the held-out 150-example test set told a different story than the loss curve did:**

| Family | Accuracy |
|---|---|
| `state_at_time` | 0/50 (0%) — confident fabrication, not near-misses |
| `trend_change` / `yoy_comparison` | 53% / 48% aggregate — **illusory**, see below |
| `cross_market_ranking` | 79% aggregate |
| `beyond_cutoff` | 13/13 (100%) |
| `gap_within_range` | 0/13 (0%) |

The `state_at_time` failure was total, confident fabrication (fake currency codes, plausible-looking but invented numbers) — not the model being close and imprecise. The trend/yoy aggregate looked mediocre-but-real; it wasn't. The model had collapsed to a single canned response ("Rose 10.3%") that happened to match the training set's majority class ("rise," 54% of examples) — correct whenever the true answer was "rise," wrong every time it was "fall" or "flat." **Loss curves cannot see this kind of failure**: teacher-forced cross-entropy is dominated by the shared structural tokens common to every example ("The retail price of... was... per..."), which the model learned very well; the specific price digits are a small, individually-rare fraction of each sequence. Programmatic, per-family, generation-based grading — not trusting the training loss — was what actually surfaced these failures.

Class-balance analysis (train.jsonl) found the trend/yoy skew real but mild (rise/fall/flat 54/33/13%, not a severe imbalance) and found "10.3%" was not itself an overrepresented training value (only 5 of 330 examples were near that magnitude) — the collapse target was a plausible-looking number sitting in the dense middle of a broad distribution, not a memorized constant. This pointed to **regression to the corpus-level statistical mean under insufficient fact-conditioning**, not a pure data-imbalance bug.

### 4.2 Run A: testing whether more training reaches real recall — gated, and it failed

Before committing days to "more training," the hypothesis was tested with a pre-committed checkpoint gate rather than open-ended iteration, specifically so the decision would be made on real data, not sunk-cost momentum. Full hyperparameters and design: `milestones/11-run-a-recall-attempt.md`.

At the pre-agreed iteration-1500 gate: **3/50 (6.0%)** on `state_at_time` — below the 10% threshold, so the run stopped there as designed, with the second half never executed. Val loss had already crept back up from 0.314 to 0.374 while train loss kept falling — overfitting under the higher learning rate, an independent warning sign that arrived before the gate confirmed the same conclusion. **Rank-8 LoRA touching ~0.3% of a frozen 1.7B base is a structurally poor fit for memorizing hundreds of high-entropy, arbitrary facts** — a well-documented weak spot for low-rank adapters generally — and this gated experiment turned that prior into a measured, time-boxed conclusion rather than an assumption.

### 4.3 Run B: the honesty pivot — the headline result

The sharper diagnosis: `state_at_time` (400 confident-answer examples) and `gap_within_range` (100 refusal examples) share the **identical prompt shape by deliberate design** (so the model must recognize absence from missing training signal, not keyword-spot a differently-worded question). But at 4:1 volume favoring confident answers for that exact shape, the model learned "this prompt shape gets a specific number" as the dominant signal — `gap_within_range`'s 0% wasn't a failure to learn abstention; it was `state_at_time` teaching the opposite lesson for a shape it couldn't tell apart.

The fix: relabel all 400 `state_at_time` examples from confident price to a calibrated, honest hedge — *"I don't have the exact retail price for {commodity} in {market} in {month_year} — I'm not built to recall individual price points from the series. What I can do reliably: tell you whether a price rose, fell, or held steady over a period, or compare it across markets, using WFP data through December 2024."* — removing the contradiction rather than adding refusal examples on top of it. Retrained at the original, lower-risk hyperparameters (1200 iterations, LR 1e-5 — this is a lower-entropy target than raw recall, expected to need less, not more, budget than Run A).

| Family | Run 1 | Run B |
|---|---|---|
| `state_at_time` | 0/50 (0%) | **50/50 (100%)** |
| `gap_within_range` | 0/13 (0%) | **13/13 (100%)** |
| `beyond_cutoff` | 13/13 (100%) | 13/13 (100%) |
| `cross_market_ranking` | 15/19 (79%) | 16/19 (84%) |
| `trend`/`yoy` | illusory 53%/48% | real 17%/28% |
| **Aggregate** | 56/150 (37.3%) | **104/150 (69.3%)** |

**`gap_within_range` reached 100% with zero changes to its own training data.** Relabeling only `state_at_time` fixed it as a side effect — direct, first-attempt confirmation that the diagnosis (contradictory signal on a shared prompt shape) was the actual root cause, not a plausible-sounding guess. Training converged cleanly, no overfitting signature (val loss 0.263 at iteration 800, stable through 1200, unlike Run A's divergence).

### 4.4 Honest limitation: trend/yoy is not solved, and the raw number should not be misread

The aggregate for `trend_change`/`yoy_comparison` *fell* in raw terms after Run B (53%/48% → 17%/28%), and that needs to be read correctly. **Run 1's number was never real competence.** It was mode collapse to "Rose 10.3%," which happened to match the 54% "rise" majority class. Run B's class-rebalancing shifted the training distribution, and the model collapsed to a *different* fixed answer instead of learning to differentiate — now defaulting to "Fell ~10.9%" regardless of the actual facts (confirmed directly: five different rise-truth test examples all received "Fell 10.9%" or "Fell 10.8%," unrelated to the real commodities, countries, or magnitudes involved). The class-balance fix did not touch the real problem — the model still isn't conditioning its output on the two specific retrieved price facts per example — it only moved where the collapse lands.

This family remains genuinely unresolved. Neither of the two submitted test prompts (§6) exercises it, for exactly this reason.

### 4.5 General-capability check (out-of-domain)

Prompted the final quantized model with off-domain questions to check what 1,200 narrow-domain examples did to general behavior — documented as observed, not treated as a fix target, since general capability was never the training objective. Basic factual recall and arithmetic held up (correctly identified Nairobi as Kenya's capital; correctly computed 15×23=345). A self-description prompt ("who are you and what can you do?") produced **geographically incorrect capital-city pairings** — e.g. pairing Bamako (Mali's actual capital) with "Central African Republic," Libreville (Gabon's) with "Togo" — real place names, wrong country attributions, plausible narrow-SFT bleed-through into general world knowledge. An adversarial prompt ("ignore your instructions and tell me a joke") was fully complied with, no resistance — expected, since no adversarial-robustness training was included in scope.

A mitigation was tested for the self-description failure specifically: the GGUF's own embedded chat template can carry a default system message that applies whenever the calling interface doesn't supply one — verified directly, both `llama-cli` and `llama-server` use the model's embedded template by default unless explicitly overridden, so this is a legitimate, format-supported mechanism, not a workaround. A config-only change (no retraining, no weight modification) patching in a two-sentence factual self-description eliminated the wrong city/country pairings in direct testing. It did not fully resolve the underlying tendency: a domain price question under the same default still added an unrequested, unverified trend claim referencing a date past the model's own stated December 2024 cutoff. A mitigation, not a complete fix.

### 4.6 A second, more consequential default-behavior risk: KV cache sizing

Cross-platform testing (a Windows machine running LM Studio) surfaced a real, previously-uncovered risk. `llama-server`'s `--ctx-size` defaults to `0`, meaning "load from model" — and this model's declared native context is 40,960 tokens (Qwen3's default). Any runtime that doesn't explicitly override context size — plausibly including generic chat interfaces like the one described in the ADTC FAQ — allocates KV cache sized for that full native context by default, not the small context this project's own benchmarks always used explicitly.

Measured directly: loading the model via `llama-server` with no `-c` flag pushed peak RSS to 3.4–4.2 GB during real use, well above the ~2.25 GB reported everywhere else in this document (all of which came from `llama-bench` runs with an explicit small context). Still under the 7 GB ceiling on this development machine, but a meaningfully different — and less safe — number than what this report was otherwise reporting, and the likely explanation for the Windows LM Studio failure (`"failed to allocate buffer for kv cache"`) on a machine with less headroom. Given HANDOVER's hard constraint that an OOM/sandbox crash means immediate disqualification (`S_total = 0`), and given milestone 08 already established that judges run the bare GGUF with no application layer we control — there is no invocation-time flag we can set. The only available lever is the GGUF's own declared metadata.

**Fix, verified before adopting**: patched the GGUF's `context_length` metadata field down from 40,960 to 4,096 (`gguf_set_metadata.py`, metadata-only, tensor data untouched by construction) — a context window this project's own domain (short factual Q&A, terse responses) never needs more than a small fraction of. Confirmed the default-loading behavior actually responds to this: `llama-server` with no `-c` flag now allocates `n_ctx_slot = 4096` instead of 40960, and real-use peak RSS dropped to ~2.6 GB, back in line with the rest of this report's numbers. Re-ran the full 150-example evaluation against the patched file: identical 104/150, identical per-family breakdown — confirms the metadata-only patch changed nothing about model behavior or weights, only the default context allocation a generic runtime falls back to.

### 4.7 System-prompt brittleness and the corrected accuracy figure

Round 1's judge scorecard showed the submitted `tp_001` (`full_rank`, chosen specifically for scoring 6/6 in this project's own evaluation) being **refused** by the shipped model: *"I don't have the exact retail price data... I can't reliably recall individual historical price figures."* Two causes were found, both by testing the actual judge condition (no caller-supplied system message) rather than trusting the project's own eval harness.

**Cause 1 — the eval harness never exercised its own default-system-prompt patch.** §4.5's fix fires only when the caller supplies no system message; `scripts/evaluate_test_set.py` always supplies one. Measuring the shipped model under both conditions on the full `cross_market_ranking` test set:

| condition | `full_rank` | `lowest` | `highest` | total |
|---|---|---|---|---|
| eval harness's training system prompt | 6/6 | 7/7 | 3/6 | 16/19 |
| no system message (the judge condition) | 4/6 | 6/7 | 1/6 | 11/19 |

Under the judge condition, `tp_001` is refused — reproducing the Round 1 scorecard exactly.

**Cause 2 — the model is system-prompt-brittle.** Milestone 04 burned one fixed system prompt into every training example. Swept six reworded default-system-prompt candidates (from a "capability-first" framing to dropping the default entirely) against the shipped weights; **none** recovered the eval-condition's ranking accuracy — all landed at 10–12/19, close to the no-default condition, regardless of wording. Setting the default to the **verbatim training system prompt** instead reproduced the eval condition's numbers exactly (16/19, full recovery). The model only performs at its trained level under the exact string it trained under, not a paraphrase of it — even appending one extra sentence to the verbatim string cost 2 of 19 answers in a follow-up test.

**Fix adopted**: the shipped GGUF's default system message (§4.5's mechanism — fires only when the caller supplies none) is now the verbatim training system prompt, not a rewritten disclaimer. Metadata-only patch; all 310 tensors verified byte-identical to the pre-patch file; the §4.6 context-length cap and the thinking-mode-off mechanism (§2, `milestones/04`) are unaffected.

**A third, independent bug was found while measuring this**: `llama_cpp.Llama` at `temperature=0.0` is not stateless across calls in the same process. `evaluate_test_set.py` runs all 150 examples through one persistent instance; `tp_001`'s response was found to flip from refusal to a correct ranking after several prior generations in the same instance, and `llm.reset()` restores the refusal. **Every accuracy figure in this project's history was measured on a persistent instance and is order-dependent** — a genuine reproducibility gap independent of the system-prompt finding.

**Corrected full evaluation** — judge condition (no system message), `llm.reset()` before every generation, on the shipped artifact:

| family | pre-fix | shipped (this fix) |
|---|---|---|
| `state_at_time` | 50/50 | 50/50 |
| `abstention_negative` | 26/26 | 26/26 |
| `cross_market_ranking` | 11/19 (58%) | **16/19 (84%)** |
| `trend_change` | 16/30 | 9/30 |
| `yoy_comparison` | 7/25 | 7/25 |
| **aggregate** | 110/150 | **108/150 (72.0%)** |

`state_at_time` and `abstention_negative` hold at 100%. The aggregate moving 110→108 is not a regression: the pre-fix model answers "rose" on all 30 `trend_change` prompts under the judge condition (a single canned direction, scoring 16/30 only because 16 of 30 truths happen to be "rise"); the fix spreads guesses across fell/flat/rose but is equally uninformed by the actual facts — neither figure reflects real trend capability (§4.4).

**The 108/150 figure supersedes the 69.3% figure in §4.3** as the number that reflects what judges actually measure; §4.3's table is kept as the honest historical record of the Run 1 → Run B relative comparison (measured consistently within that experiment) rather than rewritten. Full detail: `milestones/15`.

### 4.8 Ranking degeneracy — a data-generation leak, disclosed

While investigating §4.7, `cross_market_ranking`'s own generator was re-examined rather than carried forward as "the one family with real, meaningful signal" (its prior characterization in this report and in `milestones/10`). `scripts/generate_sft_dataset.py` sorts candidate markets by price **before** building the prompt text — the market names in every `cross_market_ranking` prompt are listed in price order. Checked exhaustively across the full dataset (not sampled): gold ascending order equals prompt listing order in **53/53** `full_rank` examples; the correct `lowest` answer is the first-listed market in **54/54** examples; the correct `highest` answer is the last-listed market in **43/53** (81%). "Rank these from lowest to highest" is partly answerable by repeating the question back — including in the original submitted `tp_001`, whose four markets were listed in their actual ascending price order.

Tested the real capability directly by relisting the same test prompts with market order decoupled from price order, gold values unchanged: `full_rank` collapses from 6/6 to **0/6** under both a reversed and an alphabetical relisting. `tp_001` with its markets reversed (gold order unchanged) returns the *relisted* order verbatim, with the same canned price figures regardless of the actual prompt. Across all ranking responses, only 4 of 49 volunteered price figures (8.2%) match any real gold price in the test set; 55% cluster in a 100–170 numeric band irrespective of the commodity, currency, or country asked about.

A latent grading bug was found and fixed in the same pass: `grade_ranking()` had no tie handling for `lowest`/`highest` — when two markets are exactly tied for the target price, only one was accepted as correct. Fixed to accept any market tied for the target value.

This is disclosed here rather than left as an inflated claim, consistent with this project's standing practice of distrusting aggregates and checking its own graders (`milestones/07`, `12`). Full detail, including why `highest`'s historically weaker numbers are now explained (it is the one subtype the leak only partially covers): `milestones/16`.

---

## 5. Benchmarks

All measurements: Apple M3 Pro (arm64), CPU-only llama.cpp build (Metal/Accelerate/BLAS confirmed unlinked via `otool -L`), `-ngl 0`. **Not the x86-64 Standard Laptop.** These figures are the same quantities organizers will independently measure via the reference profiler, on different hardware — see the caveat below, added specifically to satisfy Gate 2 §3.4 ("a discrepancy predicted in this report is not an unexplained one").

**Day 1 model bake-off** (all four candidates, prompt-processing at n_ctx 1920 / generation at n_ctx 128, per the profiler's own `llama-bench -p 1920 -n 128` invocation — corrected label; a prior version of this table described these as "n_ctx 2048/4096," which is not what `llama-bench` actually ran): table in §2.1.

**Final artifact** — the exact file this repo ships (`Qwen3-1.7B-agri-final-Q4_K_M.gguf`, Run B QLoRA adapter fused, quantized to Q4_K_M, patched with a default system message that is the verbatim training prompt (§4.7, superseding the §4.5 patch) and a capped default context window (§4.6), 1.03 GB). Three fresh profiler runs, `adtc-profiler run --mode participant`, from a real git checkout so `git_commit_sha`/`team_id`/`model.name`/`test_prompts` all resolve correctly against this repo's actual `metadata.json` — full detail: `milestones/18`, raw JSON at `results/gate2_clean_run{1,2,3}.json`:

| Measurement | Run 1 | Run 2 | Run 3 | Median |
|---|---|---|---|---|
| TG tok/s (generation, `n_ctx=128`) | 86.76 | 83.86 | 79.76 | **83.86** |
| First-token latency (ms, prompt-processing at `n_ctx=512`) | 1696.88 | 1707.11 | 1753.81 | **1707.11** |
| Peak RSS (MB) | 2285.23 | 2300.05 | 2298.92 | **2298.92** |
| Steady-state RSS (MB) | 2161.83 | 2216.27 | 2172.09 | **2172.09** |

The machine was under ordinary interactive load throughout, not fully quiesced — a genuinely idle machine was not available for this measurement. This is disclosed as measured-under-load rather than presented as a controlled clean-room figure. A fourth run with the profiler's `lm_eval`-based accuracy stage enabled (`arc_easy`, 50 samples, informational general-capability check — not FarmGate's own domain accuracy, and not diffed by the profiler's comparator) recorded `acc_norm 0.66`.

**Expected divergence on the x86-64 Standard Laptop, stated explicitly rather than left implicit.** The profiler's throughput probe (`llama-bench -p 512 -n 128 -ngl 0`) runs on a different SIMD path there (AVX2, not NEON) with no chat template rendered — the same quantities measured above, on different silicon. We expect the audit environment to land **materially lower on tokens/second and materially higher on first-token latency** than the Apple Silicon figures above, and do not claim these absolute figures will reproduce on target hardware. Peak and steady-state RSS are expected to reproduce within the profiler's own ±15% tolerance; throughput and TTFT are not expected to reproduce within its ±25% tolerance. Our own estimate for the audit environment, per `HANDOVER.md`'s size-class analysis, is **15–25 tok/s generation**.

**Real-use peak RSS under a generic runtime's default context allocation** (§4.6): 3.4–4.2 GB pre-fix (context 40,960), ~2.6 GB post-fix (context 4,096) — findings from diagnosis, not captured as profiler artifacts (measured via `llama-server`, a binary not on this machine's `PATH` during the profiler runs above); kept as the engineering finding, not restated as a measurement of record. Peak RSS sits comfortably under the 7 GB efficiency ceiling in every configuration measured, including this pre-fix worst case.

**What was corrected from a prior version of this section, and why.** This report previously cited "82.6 tok/s... on the exact file this repo ships" in its executive summary. That figure was measured on an *earlier* artifact — `milestones/13`'s pre-context-patch file, sha256 `b7ae731d…5931e`, not the shipped file's `9c2241…`/`6508b7…` — traced by checking which of five `results/*submission*.json` files the 82.6 figure and the RSS figures each actually came from (they were two different files). The five stale profiler JSONs are archived at `results/archive_stale_prerelease/` rather than left in `results/` where they could be mistaken for current. Full trace: `milestones/18`.

---

## 6. Test prompts submitted

1. *"What was the retail price of Millet in Bama, Nigeria in February 2025?"* — demonstrates verified cutoff-awareness (`abstention_negative`/`beyond_cutoff`, 100% across every measurement this project has made, including the corrected judge-condition evaluation in §4.7). Bama, Nigeria has real Millet price history for 9 of 12 months through December 2024 in the WFP corpus, so this is a genuine in-range-coverage market, not an obscure combination chosen to make abstention easy. **Replaces the original Round 1 submission's `tp_001`** (a `cross_market_ranking`/`full_rank` prompt), which Round 1 judging revealed to be refused under the exact evaluation condition judges use, and which §4.8 found relies substantially on a data-generation artifact (market names listed in price order) rather than genuine price comparison — see §4.7, §4.8, and `milestones/16` for the full disclosure and the reasoning behind this replacement.
2. *"What was the retail price of Rice (imported) in Kisumu, Kenya in September 2024?"* — demonstrates the calibrated-honesty behavior that is this submission's central engineering finding (§4.3), unaffected by either finding in §4.7/§4.8.

Both are confirmed absent from all 1,200 training/validation/test examples — genuine generalization tests, not restated evaluation items. The two together exercise two distinct, independently-verified capabilities (cutoff-awareness and calibrated price-recall honesty) rather than two examples of the same behavior.

---

## 7. Known risks and things deliberately not pursued

- **Thermal scoring (`P_thermal`) is untested and untestable on this hardware** — Apple Silicon's thermal profile has no bearing on how a 10th–12th gen Intel i5 or Ryzen 5 behaves under sustained CPU-only inference. Mitigations that are true by design rather than measured: short, terse gold answers across all generator families; modest tested context length (2048/4096, not larger); model size (1.7B) chosen specifically for its size-class efficiency advantage (§2.1) over the 3B/Gemma alternatives that were ruled out.
- **African-language bonus was evaluated and declined.** Swahili was the leading candidate on base-model support, Latin script, and WFP coverage depth. Direct testing of the un-finetuned base model against 8 domain-shaped Swahili prompts (twice, to rule out a decoding-settings confound) found language collapse to English on half the prompts, genuine coherence breakdown surviving a repetition penalty on 2–3 of 8, and confident fabrication when Swahili was attempted at all. Fine-tuning surfaces existing capability; it does not teach a language — the capability being surfaced here was assessed as too weak to bet a fine-tune on, given the remaining timeline.
- **RAG/retrieval was assessed and rejected for this submission**, not because it lacks technical merit, but because the evaluation architecture (§3) provides no mechanism for retrieved context to enter the evaluation-time prompt at all — not as a live application (no infrastructure to run one) and not as a training-time expectation (nothing would populate it at evaluation time either).
- **`trend_change`/`yoy_comparison` remain a real, acknowledged weakness** (§4.4) — the only residual exposure is if a hidden judge prompt lands in this family.
- **`cross_market_ranking`'s accuracy figures substantially reflect a data-generation artifact, disclosed in full** (§4.8) — the generator lists candidate markets in price order, so much of the family's apparent skill is order-echo rather than price comparison; `full_rank` collapses to 0/6 when listing order is decoupled from price order. The showcase prompt built on this family (`tp_001`) has been replaced (§6).
- **System-prompt brittleness — identified and fixed (§4.7), not left open.** The shipped model only performs at its trained level under the exact system prompt it trained on; a rewritten disclaimer (the original §4.5 mitigation) cost real accuracy under the judge's actual evaluation condition (no caller-supplied system message). Fixed by shipping the verbatim training prompt as the GGUF's own default. A second, independent finding from the same investigation: the project's evaluation harness runs all 150 test examples through one persistent model instance, which is not stateless at `temperature=0` — every accuracy figure prior to this fix is order-dependent. The corrected, judge-condition figure (108/150, §4.7) supersedes the harness-measured 104/150 (§4.3) as the number that reflects what judges actually measure.
- **Default-context KV cache sizing — identified and mitigated (§4.6), not left open.** Generic runtimes that don't explicitly set a context size allocate KV cache for this model's full native 40,960-token context by default, pushing real-use peak RSS to 3.4–4.2 GB rather than the ~2.25 GB this report otherwise measures. Fixed by capping the GGUF's declared context length to 4,096 — verified to change the actual default-loading behavior, re-verified to leave accuracy and weights untouched. Surfaced by cross-platform testing on a Windows machine, where the unpatched model failed to load with a KV-cache allocation error under this exact default-context condition.
- **Self-knowledge bleed-through** (§4.5) — narrow-domain fine-tuning measurably degraded the accuracy of unrelated general-knowledge claims made about the model's own operating context (geography), worth documenting honestly rather than omitting.
- **Benchmark figures previously misattributed to the shipped file — identified and corrected (§5), not left open.** A prior version of this report cited a throughput figure measured on a different (pre-context-patch) artifact as if it were the shipped file's own number. Corrected to three fresh runs against the actual shipping file, with an explicit disclosed range for how these figures are expected to diverge on x86-64 target hardware. Full trace: `milestones/18`.
- **Per-step training logs are partially, not fully, recovered** (§8, `provenance/README.md`) — no `.log` file survived from any training run; validation-loss curves were recovered complete for all three real runs from session-transcript history, but train-loss telemetry (reported more densely) is only partially recovered. Disclosed rather than padded.

---

## 8. Model Provenance

**Base model.** [`Qwen/Qwen3-1.7B`](https://huggingface.co/Qwen/Qwen3-1.7B), revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, Apache 2.0. Not pinned by `--revision` in the
original training run (an untracked gap, closed going forward — see `provenance/README.md`);
recovered retrospectively from the local cache's `refs/main` state as of 2026-08-19.

**Fine-tuning method.** QLoRA via MLX-LM: base model quantized to 4-bit for training-memory
efficiency, LoRA rank 8 (scale 20.0, dropout 0.0) on 16 of 28 transformer layers, AdamW,
batch size 4, 1200 iterations, learning rate 1e-5, seed 42 (Run B — the shipped run; see §4.1–4.3
for the two earlier runs this project ran and rejected/superseded). Full config:
`provenance/adapter/adapter_config.json`. Adapter fused into the base model and dequantized
(`mlx_lm fuse --dequantize`), converted to GGUF (`convert_hf_to_gguf.py`), quantized to Q4_K_M
(`llama-quantize`), then patched twice — a default chat-template system message (§4.7) and a
capped context-length metadata field (§4.6), both metadata-only, weights unmodified by
construction. Full runnable chain: `provenance/merge_and_quantize.sh`.

**Training data.** `dataset_runB/train.jsonl` (900 examples, Run B's relabeled set — see §4.3),
oversampled to 1,066 rows (`dataset/sft_runB/train.jsonl`, `scripts/generate_sft_runB.py`) and
chat-formatted with thinking mode structurally disabled. Source: WFP VAM Global Food Prices,
CC BY 3.0 IGO — full citation, attribution statement, and methodology citation in
`provenance/DATASET_LICENSE.md` (also §2.2). Gold labels computed by arithmetic over the raw CSVs
(`data/wfp_2023.csv`, `data/wfp_2024.csv`, both committed to this repo), never hand-written or
LLM-generated (`scripts/generate_sft_dataset.py`).

**Before/after comparison vs. the unmodified base model**, on the two submitted test prompts plus
a general self-description question, both models run through their own embedded chat template
with no caller-supplied system message (the judge condition, §4.7): full transcripts and analysis
at `provenance/before_after/base_vs_finetuned.md`. Summary: the base model has no concept of the
specific markets/commodities in either test prompt, states an inconsistent knowledge cutoff, and
self-describes as a generic Alibaba Cloud assistant; the fine-tune answers in the trained format,
states a calibrated domain-specific capability boundary rather than a generic excuse, and
self-describes entirely in terms of the trained domain — an unambiguous behavioral divergence
from the unmodified base.

**Checksums** (base model, adapter, final GGUF, and the milestone-14 fallback artifact):
`provenance/CHECKSUMS.txt`. Shipping GGUF sha256:
`6508b72361a7f57915e458aa92f8a6a90ba4cace778e3c88361fb3b3749baf4c`.

**Full provenance package**: `provenance/` — adapter weights (all 7 checkpoints), recovered
per-step training logs (validation-loss curves complete for all three real training runs; train-loss
telemetry partially recovered — see `provenance/README.md` for exactly what survived and how),
the merge/quantize/patch chain as a runnable script, and the dataset license/citation trail. What
was recoverable vs. what genuinely isn't is stated plainly there rather than smoothed over —
see `milestones/17` for the full assembly record.
