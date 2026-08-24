# 14 — Default Context Window (KV Cache Sizing) Fix

**Status:** Adopted (2026-08-24). Shipping as the current `models/Qwen3-1.7B-agri-final-Q4_K_M.gguf` (sha256 `9c2241433b92a2ba45bab9e1eee398d774b8884030885c37ec0c141fd1bca5ce`), superseding the system-prompt-only artifact from milestone 13.

## Decision / goal

A user cross-platform test (Windows, LM Studio) failed to load the previously-shipping model at all, citing `"failed to allocate buffer for kv cache"`. Diagnose the real cause before dismissing it as a Windows quirk, and fix it if it represents a genuine risk to the actual submission.

## What was verified (not assumed)

- The failed-load transcript itself was mis-attributed at first glance — its content (wrong stated knowledge cutoff, no trained hedge language, emoji usage, a different joke, cross-turn context bleed) made clear LM Studio had silently fallen back to loading a different, generic model after the real one failed — not a behavioral finding about our model at all. Caught by comparing against this project's own extensive prior transcripts, not assumed from platform difference alone.
- Root cause of the actual load failure, checked directly: `llama-server --help` confirms `--ctx-size` defaults to `0` = "loaded from model." The shipped GGUF's own `qwen3.context_length` metadata field (checked via `gguf-py`) is `40960` — Qwen3's native max. Any runtime that doesn't explicitly override context size (plausibly including the generic chat interface described in the ADTC FAQ, and confirmed to include LM Studio's apparent default behavior) allocates KV cache sized for the full 40,960 tokens.
- **Measured the real cost directly**, not estimated: started `llama-server` with no `-c` flag on the pre-fix file and sent an actual completion request — real-use peak RSS reached 3.4–4.2 GB, well above the ~2.25 GB this project's `llama-bench`-based numbers (which always used an explicit small context) had reported everywhere else. Still under the 7 GB ceiling on this development machine (18 GB RAM), but a materially different and less safe number, and a plausible explanation for the Windows failure on a machine with less headroom.
- This is squarely in-scope for the worst possible outcome under this challenge's rules: HANDOVER's own hard constraint states an OOM/sandbox crash means `S_total = 0`, immediate disqualification. Milestone 08 already established there is no invocation-time flag available to us — judges load the bare GGUF with no application layer we control. The GGUF's own declared metadata is the only lever that exists.
- **Fix**: patched `qwen3.context_length` from 40960 to 4096 (`gguf_set_metadata.py`, metadata-only — tensor data untouched by construction, same mechanism as milestone 13's chat-template patch). Verified the fix actually changes the resolved default, not just the declared number: `llama-server` with no `-c` flag now reports `n_ctx_slot = 4096`, and a real completion request under this configuration settled at ~2.6 GB peak RSS — back in line with the rest of the project's reported numbers.
- **Re-ran the full 150-example evaluation against the patched file**: 104/150, identical per-family breakdown to every prior Run B measurement — confirms the metadata-only patch changed nothing about model behavior or weights.
- **A TPS anomaly during re-verification was investigated, not reported at face value.** Two profiler runs on the patched file showed TPS collapse to 42–46 tok/s (down from a clean 82.61 baseline). Rather than accept this as a cost of the fix, ran a controlled comparison: benchmarked the pre-fix and post-fix files back-to-back under the same conditions. Both showed the same degraded range together — the signature of external system contention, not a fix-induced regression. `ps aux` confirmed a background process consuming ~70% of a CPU core at that moment, unrelated to this session's own tooling. Peak RSS (unaffected by CPU contention) stayed consistent across all runs. The clean 82.61 tok/s baseline is carried forward in REPORT.md with this caveat stated plainly rather than smoothed over.

## Conclusion

4096 tokens is far more than this project's domain ever needs (short factual Q&A, terse responses per generator family design) and eliminates the default-context OOM exposure entirely, at zero measured cost to accuracy and no established cost to throughput.

## Open risks / dependencies carried forward

- The Windows LM Studio failure was diagnosed by reasoning from this project's own controlled tests, not reproduced live on that exact machine after the fix — worth a follow-up confirmation there if time allows, though the mechanism (default context → KV cache size) is verified independently of that specific machine.
- A clean (uncontended) TPS re-measurement of the final shipping file hasn't been captured — the 82.61 tok/s figure predates this fix by one patch layer, carried forward on the strength of the controlled comparison rather than a fresh clean number. Worth doing if a precise final figure is needed.
- This supersedes milestone 13's artifact as the shipping file — milestone 13's own verification (accuracy, chat-template mechanism) still holds since this patch only adds a second, independent metadata change on top.
