# 06 — Swahili Language Bonus: Base-Competence Check

**Status:** Declined (2026-08-19). Decision: **English-only submission, no language bonus attempt.**

## Decision / goal

Before committing to ~300 translated Swahili examples for the language bonus, check whether the *base* (un-finetuned) Qwen3-1.7B-Q4_K_M GGUF has real latent Swahili competence in this domain's shape, on the premise that "fine-tuning on ~300 examples surfaces existing capability; it doesn't teach a language." If the base model's Swahili is weak, ~300 examples won't fix it.

## Options considered

Not a design-alternatives decision — a go/no-go gate on an already-decided plan (Swahili chosen in principle over Hausa/Amharic/Arabic on base-model support, Latin script, and WFP coverage depth across Kenya/Tanzania/Uganda/DRC). This milestone is the verification step before spending time on that plan.

## What was verified (not assumed)

Ran 8 Swahili prompts (price lookup ×2, rise/fall trend ×2, cross-market ranking ×1, "honest I-don't-know" abstention shape ×2, open-domain fluency ×1) directly against the base GGUF via `llama-cli`, using the real chat template with `enable_thinking: false`. Ran **twice** — once at temp=0 with `llama-bench`'s default `--repeat-penalty 1.0` (disabled), once rerun with `--repeat-penalty 1.1` — specifically to rule out "degenerate greedy-decoding loop" as a confound before trusting any repetition-based failures. Full raw transcripts: [`results/swahili_base_check.txt`](../results/swahili_base_check.txt) (run 1) and [`results/swahili_base_check_v2.txt`](../results/swahili_base_check_v2.txt) (run 2, repetition penalty enabled).

**Pattern held across both runs, not just one decoding setting:**
- **Code-switches to English on 4 of 8 prompts** (rice/Dar es Salaam, beans-trend, sugar-trend, potato-future) — asked in Swahili, answered entirely in English, both runs. Not decoding-setting-dependent.
- **Confident fabrication when it does attempt Swahili**: the Kampala-vs-Kigali rice ranking produced a fluent, grammatical, confidently wrong answer both times — run 2: *"Ili ya chini zaidi ya mchele kati ya Kampala na Kigali ni 1,200 USD/kg"* — a per-kg rice price of $1,200 is absurd on its face, stated with no hedge.
- **Genuine coherence collapse, not just a greedy artifact**: 2–3 of 8 prompts degenerated into repetition loops in *both* runs (e.g., run 2's Goma/sorghum prompt loops the same clause block twice within 200 tokens even with repeat-penalty 1.1 enabled) — the penalty reduced but did not eliminate looping, meaning this is a real coherence weakness, not purely a temp=0 artifact.
- **Persistent factual/attention error, reproduced identically in both runs**: the "price of potatoes in March 2027" prompt both times answered about "the price of maize" instead — a specific, repeatable commodity-confusion bug, not one-off noise.
- **Fabricated institution names when declining in English**: cited different, inconsistent-sounding Kenyan agency acronyms across the two runs for the same prompt (run 1: "KALR"/"KBS"/"KALS"; run 2: "KATA"/"CBS"/"FAO") — the instability between runs on the same question is itself evidence these are being invented, not retrieved.
- **One genuinely correct behavior, consistently**: appropriately declines to fabricate a real number in 5 of 8 cases rather than always confabulating — the epistemic instinct to hedge exists, even though the language and coherence often don't hold up around it.

## Verdict (my read — raw transcripts are there for you to judge directly)

This is not "confident nonsense" in the narrow sense of fluent-but-wrong. It's a mix of three distinct failure modes: language collapse to English, genuine coherence breakdown (repetition loops that survive a repetition penalty), and confident fabrication when Swahili is attempted at all — plus a reproduced factual/attention error. The one consistently *good* sign is appropriate declining behavior in over half the prompts, but that's an epistemic reflex, not evidence of Swahili fluency.

Given the premise ("fine-tuning surfaces existing capability, it doesn't teach a language"): the existing capability being surfaced here is weak enough that ~300 examples would plausibly teach *format* (the model may learn to answer price questions in Swahili-shaped sentences) without necessarily fixing the underlying coherence and code-switching problems — those look like base-model limitations, not domain-shape gaps.

## Final decision

**Declined — English-only submission.** User reviewed the raw transcripts directly and confirmed the check is decisive: the base model's Swahili competence in this domain shape is not reliable enough to bet a fine-tune on. The ~300-example translated-Swahili plan from HANDOVER §6/this milestone's scoping is dropped. No further work planned against the +15% African-language multiplier (HANDOVER §2) — accepted as forgone rather than chased with mitigations (e.g., explicit language-consistency supervision) that would add scope this close to deadline for an uncertain payoff on a base competence gap, not a domain-shape gap.

## Open risks / dependencies carried forward

- None — this track is closed. HANDOVER's bonus-terms ambiguity (§2/§9 item 4, microsite vs Devpost language-bonus wording) is now moot for this submission regardless of how it resolves.
