# 13 — Default System Prompt Mitigation

**Status:** Adopted (2026-08-19). Shipping as `models/Qwen3-1.7B-agri-final-Q4_K_M.gguf` (sha256 `b7ae731d994b901c96022b037f6e2e46610aa71fe9dc2c9012f5583b10d5931e`), referenced from `submission/metadata.json`.

## Adoption verification (2026-08-19)

Before adopting, re-ran both checks that produce REPORT.md's numbers against the exact patched file, per the standing rule that every reported number must come from the file judges actually download:
- **Full 150-example evaluation**: 104/150 (69.3%), identical per-family breakdown to the pre-patch Run B result — confirms the metadata patch (`gguf_new_metadata.py`, weights untouched by construction) didn't corrupt anything in the copy/rewrite round-trip.
- **Official `adtc-profiler` run**: 82.61 tok/s / 2,255.66 MB peak RSS / 72.4% CPU, vs. pre-patch 77.96 tok/s / 2,251.88 MB / 72.9% — within normal `llama-bench` run-to-run noise (consistent with variance observed throughout this project), not a material change. Both numbers now updated in REPORT.md.

Both results were expected going in (the eval harness always supplies its own system message, so the template's fallback branch never fires during grading; the profiler doesn't render a chat template at all) — but verified rather than assumed, per instruction.

## Decision / goal

Check whether the submission format supports setting a system prompt that would ride along with the shipped GGUF, to counter the geographically-wrong self-description found in milestone 12's out-of-domain check — without retraining.

## What was verified (not assumed)

- `metadata.json`'s schema (re-checked against the live submission template README) has no system-prompt field anywhere.
- The GGUF's own embedded `tokenizer.chat_template` is the real mechanism: confirmed both `llama-cli` and `llama-server` (built fresh to check — the server binary wasn't previously compiled) default to `--jinja` enabled and `--chat-template` = "taken from model's [metadata]," meaning the template ships with, and governs, the model regardless of caller — a legitimate, standard mechanism, not a workaround.
- Extracted the actual template embedded in the shipping Run B GGUF (confirmed identical to the base model's official template, as expected since fine-tuning doesn't touch tokenizer files) and added a minimal, surgical modification: inject a default system message **only** when the caller supplies none (an `{%- else %}` branch on the existing `messages[0].role == 'system'` check). Verified via direct Jinja rendering that this leaves 100% of existing behavior — including the thinking-mode-off mechanism (milestone 04) — untouched when a caller *does* supply a system message.
- Patched a real test GGUF (`gguf_new_metadata.py --chat-template-file`, weights untouched) and ran real generations with no `-sys` flag at all:
  - "Who are you and what can you do?" — the wrong city/country pairings from milestone 12 did not recur; response referenced only real countries actually in the WFP corpus (Malawi, Ethiopia, Uganda, South Sudan), though still un-prompted additions beyond the system text's abstract framing.
  - A genuine domain question ("What was the retail price of Cassava in Lilongwe, Malawi in June 2024?") under the same default: the calibrated hedge still fired correctly, but the response also volunteered an **unrequested, unverified trend claim referencing January 2025** — past the model's own stated December 2024 cutoff, contradicting its own boundary in the same response.

## Conclusion

**Format-supported: yes, verified working.** Wording drafted (2 sentences, no invented specific place-names to avoid re-introducing the exact failure class): *"I'm an offline assistant for African agricultural market prices, built on WFP data through December 2024. I can compare prices across markets and describe price trends, but I don't reliably recall individual historical price figures — I'll say so directly rather than guess."*

**Partial fix, not a complete one.** It measurably helped the exact case it targeted, but the underlying tendency to volunteer unprompted, unverified specifics is broader than the one failure mode it was aimed at — a single system-prompt patch doesn't reach the domain-question case found during testing. This is now stated plainly in REPORT.md §4.5 rather than oversold.

## Open risks / dependencies carried forward

- Decision not yet made on whether to ship the patched template as the final submitted GGUF, given it's a partial mitigation — currently only a validated test artifact.
- If adopted, needs the same fuse/convert/quantize provenance chain the shipping model went through, or (cheaper) apply `gguf_new_metadata.py` directly to the exact file being submitted, immediately before packaging, to avoid drift between what's tested and what ships.
