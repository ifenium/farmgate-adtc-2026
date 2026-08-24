# Day 1 model bake-off — raw results

**Measured on:** Apple M3 Pro (11-core, 5P+6E), 18 GB RAM, macOS 15.7.3, arm64.
**NOT the ADTC Standard Laptop** (x86-64 Intel/AMD, 4-core class, 8 GB DDR4, Ubuntu 22.04). See caveats below — do not present these absolute figures as target-hardware results in REPORT.md; only the relative ranking is defensible cross-architecture.

**Build:** llama.cpp @ `60adddd` (2026-08-18), CMake build with `-DGGML_METAL=OFF -DGGML_ACCELERATE=OFF -DGGML_BLAS=OFF -DLLAMA_CURL=OFF` — confirmed via `otool -L` that no Metal/Accelerate/BLAS is linked. `llama-bench -ngl 0`, default threads (5, = P-core count).

**Method:** `llama-bench` has no standalone `--ctx-size` flag in the current build — it derives `n_ctx = n_prompt + n_gen + n_depth`. Each row below sets `-p (n_ctx-128) -n 128 -d 0` to land on the target n_ctx. RAM (peak/steady RSS) and CPU% were captured by wrapping the same `llama-bench` invocation with adtc-profiler's own `MemorySampler`/`ThermalSampler` classes (identical code path to `adtc-profiler run`), sampled at 0.1s/0.5s intervals. `core_temp_c_peak` is `null` on this Mac — adtc-profiler's Darwin thermal path requires the `ismc` CLI, which isn't installed and isn't in Homebrew; not fixed, since patching the reference profiler for a nice-to-have number wasn't worth it, and thermal figures aren't meaningful cross-architecture anyway (P_thermal's 85°C threshold was set for x86 TDP profiles, and an M3 Pro under this light a load won't approach it regardless).

## Results

| Model | Quant | File size | n_ctx | PP tok/s | TG tok/s | Peak RSS | Steady RSS | CPU% p99 |
|---|---|---|---|---|---|---|---|---|
| Llama 3.2 1B Instruct | Q4_K_M | 0.75 GB | 2048 | 418.02 | 133.06 | 1717 MB | 1670 MB | 57.5% |
| Llama 3.2 1B Instruct | Q4_K_M | 0.75 GB | 4096 | 347.15 | 128.59 | 1784 MB | 1762 MB | 59.5% |
| Qwen3 1.7B | Q4_K_M | 1.03 GB | 2048 | 268.02 | 92.36 | 2431 MB | 2356 MB | 56.5% |
| Qwen3 1.7B | Q4_K_M | 1.03 GB | 4096 | 216.99 | 86.74 | 2659 MB | 2606 MB | 58.8% |
| Gemma 4 E2B it | UD-Q4_K_XL | 2.97 GB | 2048 | 125.18 | 48.80 | 4514 MB | 4292 MB | 85.7% |
| Gemma 4 E2B it | UD-Q4_K_XL | 2.97 GB | 4096 | 119.22 | 50.22 | 3999 MB | 3275 MB | 91.1% |
| Llama 3.2 3B Instruct (control) | Q4_K_M | 1.88 GB | 2048 | 149.71 | 53.72 | 4140 MB | 4074 MB | 60.0% |
| Llama 3.2 3B Instruct (control) | Q4_K_M | 1.88 GB | 4096 | 118.35 | 43.94 | 4415 MB | 3987 MB | 76.6% |

*(Gemma's ctx4096 peak RSS reading below its ctx2048 reading is measurement noise — mmap/page-cache warm-up between consecutive runs on the same file, 0.1s sampling interval possibly missing a transient spike — not a real effect. Don't read a trend into it.)*

## Headline finding: Gemma 4 E2B's RAM story does not hold up

HANDOVER.md §4 bet on Gemma as the "upside play" specifically because of an exceptional memory ceiling — UD-Q4_K_XL estimated ~3 GB, with a speculative sub-1 GB path via a PLE-stripped text-only variant.

Measured reality: **peak RSS 4.0–4.5 GB — matching or exceeding the Llama 3.2 3B control**, not the ~1–2B efficiency class Qwen3/Llama-1B occupy. The room-temperature explanation: the UD-Q4_K_XL **file itself is 2.97 GB on disk** — bigger than Llama 3.2 3B's Q4_K_M (1.88 GB) despite Gemma's "E2B" (effective-2B) branding. Per-Layer Embeddings and Gemma 4's non-standard architecture carry real bytes at this quant level even before KV cache is added; the "E" in E2B is an inference-compute framing, not a memory-footprint one.

I checked unsloth's repo file listing before downloading (per your instruction) — there is **no separate PLE-stripped/text-only artifact**, only the UD-Q4_K_XL used here. The sub-1 GB path HANDOVER flagged doesn't exist as a downloadable file in this repo, so it was never reachable today regardless of tooling.

**Practical effect on HANDOVER §4's decision rule:** the whole rationale for spending a 2-hour QLoRA timebox on Gemma was "if the memory ceiling is exceptional, the tooling risk is worth it." That premise is now measured false on this data — Gemma sits in the same RAM class as the 3B control, which HANDOVER's own §2 size-class table says loses ~15 weighted points before accuracy is scored versus the 1–2B class. Qwen3 1.7B (primary recommendation) and Llama 3.2 1B (fallback) both land cleanly in the efficient band; Gemma does not. I'd deprioritize the Gemma timebox unless you have a reason to doubt this measurement.

## Cross-architecture caveats (do not skip when writing REPORT.md)

- This is **arm64 Apple Silicon**, target is **x86-64**. Different SIMD paths (NEON vs AVX2/AVX512) mean absolute tok/s numbers will not transfer — all four models cleared `TPS_REFERENCE=15` by 3–28×, but that's not evidence the x86 Standard Laptop will.
- This machine has 18 GB RAM and macOS's RSS/mmap accounting; the 8 GB Ubuntu target may report peak RSS differently for the same workload. Relative RAM ranking between models (Gemma > Llama-3B > Qwen3 > Llama-1B) is the trustworthy part; absolute MB figures are not target-hardware numbers.
- No GPU offload confirmed (`-ngl 0`, no Metal linked) — this is a genuine CPU-only comparison, not Metal-accelerated ARM pretending to be CPU.
