#!/usr/bin/env python3
"""Format dataset/{train,val}.jsonl into Qwen3 chat-template text for QLoRA.

Uses the chat_template extracted directly from the actual downloaded GGUF
(models/Qwen3-1.7B-Q4_K_M.gguf -> data/qwen3_chat_template.jinja), not a
guessed/recalled template -- this is "whatever the template defaults to" per
HANDOVER.md's Day-1 gotcha, since that's what judges get in LM Studio too.

Thinking-mode-off is baked into every training example structurally: each
example is a single-turn conversation, so the assistant message is always
the template's `loop.last` turn, which (traced through the Jinja logic and
confirmed by rendering it) always emits an empty `<think>\n\n</think>\n\n`
block ahead of the real content -- with no reliance on whoever runs
inference later correctly passing enable_thinking=False.

test.jsonl is untouched -- it's the held-out set for post-quantization
accuracy evaluation against the actual GGUF, not a training input.
"""
from __future__ import annotations

import json
from pathlib import Path

import jinja2

DATASET_DIR = Path("/Users/Apple/Documents/hack/dataset")
TEMPLATE_PATH = Path("/Users/Apple/Documents/hack/data/qwen3_chat_template.jinja")
OUT_DIR = DATASET_DIR / "sft"
OUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "You are an offline assistant for African agricultural market prices, "
    "built on WFP VAM price data through December 2024. Answer questions "
    "about crop prices, price trends, and market comparisons briefly and "
    "factually, in the exact numeric format used in training. If you do "
    "not have data for the requested market, commodity, or period, say so "
    "directly instead of guessing."
)

THINK_MARKER = "<think>\n\n</think>\n\n"


def build_template() -> jinja2.Template:
    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    return env.from_string(template_str)


def format_example(ex: dict, tmpl: jinja2.Template) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ex["prompt"]},
        {"role": "assistant", "content": ex["gold_answer"]},
    ]
    text = tmpl.render(messages=messages, add_generation_prompt=False, enable_thinking=False, tools=None)
    return {
        "id": ex["id"],
        "generator_family": ex["generator_family"],
        "generator_subtype": ex["generator_subtype"],
        "messages": messages,
        "text": text,
    }


def process(split_name: str, tmpl: jinja2.Template) -> tuple[int, int]:
    in_path = DATASET_DIR / f"{split_name}.jsonl"
    out_path = OUT_DIR / f"{split_name}.jsonl"
    n = 0
    n_think_ok = 0
    with in_path.open() as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            ex = json.loads(line)
            formatted = format_example(ex, tmpl)
            if THINK_MARKER in formatted["text"]:
                n_think_ok += 1
            fout.write(json.dumps(formatted, ensure_ascii=False) + "\n")
            n += 1
    return n, n_think_ok


def main():
    tmpl = build_template()
    for split_name in ("train", "val"):
        n, n_think_ok = process(split_name, tmpl)
        status = "OK" if n_think_ok == n else "MISMATCH"
        print(f"{split_name}: {n} examples formatted, {n_think_ok}/{n} contain the empty think block [{status}]")

    test_path = DATASET_DIR / "test.jsonl"
    print(f"test.jsonl left untouched at {test_path} ({sum(1 for _ in test_path.open())} lines) -- held out for post-quantization eval, not formatted.")


if __name__ == "__main__":
    main()
