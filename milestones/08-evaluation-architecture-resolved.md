# 08 — Evaluation Architecture Resolved: Bare GGUF Only

**Status:** Done (2026-08-19). Resolves HANDOVER §3, open since Day 1.

## Decision / goal

Determine whether ADTC judges evaluate the standalone `.gguf` file or the participant's full submitted application, before committing further engineering effort in either direction — this had been sitting as an unresolved "email the organizers" item since Day 1 while the project defaulted to the worse-case assumption.

## Options considered

Not a design choice — a fact-finding resolution. The two hypotheses on the table were: (a) bare GGUF loaded into a generic tool (LM Studio/Ollama), matching HANDOVER's original Day 1 note and its "assume the fine-tune must carry accuracy on its own" fallback; (b) full submitted application running live, which would make a RAG/tool-use layer load-bearing for the actual score.

## What was verified (not assumed)

Went to primary sources directly and cross-checked them against each other, specifically distrusting single AI-summarized reads after the first WebFetch pass on this exact question came back internally inconsistent between two pages.

1. **FAQ accordion, africadeeptech.org/challenge-2026** — read the raw accessibility tree text myself (not a WebFetch summary) after clicking each accordion item open, since a first-pass AI summary of this page had asserted judges run the full app ("we do not measure resource limits on any supporting application stack" + "the judge chats with it live") — technically accurate quotes, but the summary's framing overstated what they mean once cross-checked against the submission template.
   - *"Judging is done by actually running your submitted model... we spin up a fresh sandboxed instance of your exact submission... and the judge chats with it live through our in-browser interface."*
   - *"Just the model. Automated profiling and resource limits... apply only to the LLM inference process itself (llama.cpp running your GGUF model)... Judging is also scoped to the model's responses, not a broader application UI."*
   - *"Just your model repository with a working `download_model.sh`, plus your two required test prompts... Accuracy (S_acc) is scored entirely by the judging panel, who run your actual model — you never submit an accuracy number."*
2. **`adtc-2026-submission-template` repo file listing** (GitHub API, not summarized): `.gitignore`, `LICENSE`, `README.md`, `REPORT.md`, `download_model.sh`, `metadata.json`, `model/`. No code directory. No app entrypoint. No Docker Compose file, despite `metadata.json`'s `model.packaging` enum listing `docker_image`/`docker_build_from_repo` as options.
3. **The README's raw text**, fetched directly via `curl` (a second WebFetch AI-summary pass on this exact file had claimed "no application entrypoint... the submission is a passive artifact" — plausible-sounding but worth confirming against the literal text given point 1's summary had gone the other way): confirms the required structure is exactly the 4 files above, states *"llama.cpp only... No other runtime is supported by our evaluation framework"* and *"8 GB RAM limit... Out-of-memory errors during evaluation result in automatic disqualification"* scoped to the model process.

**Reconciling the two FAQ-vs-README readings**: given the template repo has no room for an application (no code directory, no entrypoint), "your exact submission" in the FAQ's live-chat answer can only refer to the GGUF file — ADTC's own in-browser chat interface loads the participant's model file directly; there is no participant-authored server or app on the other end of that chat.

## Conclusion

**Bare GGUF only, confirmed from three independent primary-source reads, not inferred from one summary.** No RAG layer, no wrapper application, no tool-use pipeline can run during any part of scoring — not the automated telemetry, not the live judge-panel chat, not the accuracy benchmark. The fine-tune has to carry 100% of `S_acc` on its own. HANDOVER's Day 1 "assume the worse case" fallback was, in the end, the correct assumption — now confirmed rather than merely defaulted to.

**Direct implication for the `cross_disciplinary_pairing` metadata claim**: since there's no infrastructure to run a live integration, the claim has to be realized through (a) what the fine-tuned model's weights themselves demonstrably do, and (b) the written methodology in `REPORT.md`. This project's dataset methodology — gold labels computed by verifiable arithmetic over WFP VAM's structured economic data (milestones 02/03) — already *is* a legitimate cross-disciplinary story (applied data science / economics), told through training methodology rather than a runtime integration. No new engineering needed to satisfy this field; it needs framing in REPORT.md.

## Open risks / dependencies carried forward

- This resolution directly gates the RAG-pivot assessment — see [`milestones/09-rag-pivot-assessment.md`](09-rag-pivot-assessment.md).
- `REPORT.md`'s writeup now needs to explicitly carry the cross-disciplinary story via methodology, since there's no runtime demo of it to fall back on beyond the 2-minute video (which judges are told is not strictly required to show live operation).
- Not independently confirmed with the organizers directly (no email was sent) — this is a strong, three-source-corroborated inference from public materials, not written organizer confirmation. Low residual risk given how consistent and specific all three sources are with each other.
