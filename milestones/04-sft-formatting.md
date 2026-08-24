# 04 — SFT Chat Formatting

**Status:** Done (2026-08-19)

## Decision / goal

Convert `dataset/train.jsonl` and `dataset/val.jsonl` into Qwen3 chat-template text ready for QLoRA, with thinking mode structurally disabled per [`01-model-selection.md`](01-model-selection.md)'s known gotcha. `test.jsonl` stays raw/untouched — it's the held-out set for post-quantization accuracy evaluation against the actual GGUF, not a training input.

## Options considered

- **Hand-roll a ChatML-lookalike template** vs. **extract and render the actual chat_template embedded in the downloaded GGUF**. Went with extraction — HANDOVER's own gotcha says to verify on the quantized artifact, since that's "whatever the template defaults to" for judges running LM Studio. A recalled/guessed template risks silently diverging from what the real tokenizer does.
- **Rely on `enable_thinking=False` being passed correctly at someone's later inference call** vs. **bake the empty think-block into every training example structurally**, so the behavior can't leak back regardless of how inference is invoked later. Went with the structural approach — matches the explicit instruction in milestone 01 ("baked into the fine-tune so it can't leak back").

## What was verified (not assumed)

- Pulled `tokenizer.chat_template` directly out of `models/Qwen3-1.7B-Q4_K_M.gguf` via `gguf-py` (from the llama.cpp checkout) — not from memory or the model card. Saved to `data/qwen3_chat_template.jinja`.
- Traced the template's Jinja logic: for the assistant message, `enable_thinking` is only read inside the `add_generation_prompt` branch (i.e., only affects the trailing generation prompt, not full rendered conversations). For a single-turn conversation, the assistant turn is always `loop.last`, which independently takes the branch that emits `<think>\n{reasoning_content}\n</think>\n\n{content}` — and since our examples never set `reasoning_content` or contain literal `<think>` tags, that renders as an **empty** think block ahead of the real answer, with no dependency on the `enable_thinking` flag at all for training-time rendering.
- Actually rendered a real conversation through the real template with `jinja2.Environment(...).from_string(...)` and inspected the output byte-for-byte — confirmed `<think>\n\n</think>\n\n` lands exactly before the assistant's content, before writing the formatting script.
- Ran the formatter: [`scripts/format_sft_chat.py`](../scripts/format_sft_chat.py) → [`dataset/sft/`](../dataset/sft/) (`train.jsonl` 900, `val.jsonl` 150). **Programmatically checked all 1,050 rendered examples, not sampled** — 900/900 train and 150/150 val contain the empty think-block marker. `test.jsonl` (150 lines) confirmed untouched.
- Before formatting, per a request to re-check deviation #1 from milestone 03: **full programmatic scan of all 440 `trend_change`/`yoy_comparison` examples** confirmed both comparison dates are explicit substrings in every prompt (0 failures), not just implied by a duration — the variable date-span deviation noted in milestone 03 is safe.

## Open risks / dependencies carried forward

- Inherits the standalone-GGUF dependency flagged in milestone 02/03 (families 1–4 split strategy) — unchanged, still open.
- A fixed system prompt is burned into every training example (offline agricultural price assistant, told explicitly to abstain rather than guess). Not yet validated against actual model behavior post-training — that's a Day 3–4 check once QLoRA runs.
- `dataset/sft/*.jsonl` carries both a `messages` array (framework-agnostic, lets the real training environment's own tokenizer re-render if preferred) and a pre-rendered `text` field (exact string used to confirm the think-block behavior here). If the actual training script applies its own `apply_chat_template` call on `messages` instead of consuming `text` directly, that's a second render through presumably the same GGUF-embedded template — should match, but worth a spot-check once the Day 3–4 training environment is live, since it may be using the base HF tokenizer's template rather than the GGUF's (they're expected to be identical, but this hasn't been cross-checked against `Qwen/Qwen3-1.7B`'s own `tokenizer_config.json` yet).
