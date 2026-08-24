# 01 — Model Selection

**Status:** Done (2026-08-18/19)

## Decision

Primary model: **Qwen3 1.7B**. Documented efficiency alternative: **Llama 3.2 1B**. Ruled out: **Gemma 4 E2B**.

## Options considered

- **Qwen3 1.7B** — Apache 2.0, standard dense architecture (QLoRA a solved path via Unsloth/PEFT), strong multilingual base, has a thinking-mode toggle that must be forced off.
- **Llama 3.2 1B** — safest tooling, older/weaker multilingual, fastest and lightest of the four candidates.
- **Gemma 4 E2B** — pitched as the "upside play" on an assumed exceptional memory ceiling (~3 GB estimated, speculative sub-1 GB PLE-stripped variant).
- **Llama 3.2 3B** — carried only as a control/reference point for the 3B size class, never a real candidate (HANDOVER §2's own size-class math rules out 3B before accuracy is even measured).
- DeepSeek distills — rejected outright, pre-bake-off: `<think>` streaming is bad for token economy/demo, and the small distills are Qwen-based anyway.

## What was verified (not assumed)

Ran a same-machine bake-off (Apple M3 Pro, arm64, CPU-only llama.cpp build — Metal/Accelerate/BLAS confirmed unlinked via `otool -L`) across all four models at n_ctx 2048 and 4096. Full data: [`results/bakeoff-day1.md`](../results/bakeoff-day1.md).

| Model | Peak RSS | TG tok/s |
|---|---|---|
| Llama 3.2 1B | 1.7–1.8 GB | 129–133 |
| Qwen3 1.7B | 2.4–2.7 GB | 87–92 |
| Llama 3.2 3B (control) | 4.1–4.4 GB | 44–54 |
| Gemma 4 E2B (UD-Q4_K_XL) | 4.0–4.5 GB | 49–50 |

Gemma's premise didn't survive measurement: peak RSS lands in the 3B control's class, not the 1–2B band it was picked for. Root cause found, not just observed — the UD-Q4_K_XL file itself is 2.97 GB on disk, bigger than Llama 3.2 3B's Q4_K_M (1.88 GB), because Per-Layer Embeddings and Gemma 4's non-standard architecture carry real bytes at this quant level regardless of the "E2B" (effective-2B) name. Checked unsloth's repo file listing before downloading anything: no separate PLE-stripped/text-only artifact exists, so the speculative sub-1 GB path was never reachable.

## Open risks / dependencies carried forward

- **Cross-architecture gap**: bake-off ran on arm64 Apple Silicon, not the x86-64 Standard Laptop. Relative ranking between models is trustworthy; absolute tok/s and RAM figures are not target-hardware numbers.
- **Qwen3 thinking-mode leak**: confirmed via source read that adtc-profiler's own throughput/accuracy paths never render a chat template, so this didn't affect bake-off numbers — but it's unresolved for the judge-facing chat UI and demo video. Needs a `/no_think` check baked into the fine-tune before Day 5.
- **Standalone-GGUF question (HANDOVER §3)** — still open with organizers. Doesn't change the model pick, but changes how much weight the fine-tune has to carry alone.
