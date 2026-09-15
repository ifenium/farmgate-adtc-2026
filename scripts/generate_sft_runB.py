#!/usr/bin/env python3
"""Reconstruction of the script that built dataset/sft_runB/ -- the file Run B
was actually trained on. Recovered from session-transcript history and added
here for Gate 2 provenance (§3.1); it did not exist as a committed script
before this reconstruction (see provenance/README.md).

What dataset/sft_runB/ is:
  - dataset_runB/{train,val}.jsonl (Run B's relabeled data, see
    scripts/relabel_state_at_time_runB.py) chat-formatted the same way
    format_sft_chat.py formats dataset/{train,val}.jsonl, PLUS an
    oversampling pass on the training split only: every trend_change/
    yoy_comparison example with subtype "flat" is duplicated twice
    (-dup0/-dup1 suffixes), and every one with subtype "fall" is duplicated
    once with probability 0.7 (-dup0 suffix), seed 42 -- carrying forward
    the class-balance fix from Run A (see milestones/11, milestones/12)
    unchanged into Run B.
  - dataset_runB/val.jsonl chat-formatted directly, no oversampling, saved
    as valid.jsonl (MLX-LM requires the validation file be named
    valid.jsonl, not val.jsonl -- see the "hard-won gotchas" in HANDOVER.md).

Verified reproduction: applying this exact transformation to the committed
dataset_runB/train.jsonl reproduces the exact 166-row duplicate set found in
the committed dataset/sft_runB/train.jsonl (124 distinct roots duplicated:
82 once, 42 twice -- the 42 are exactly the flat-subtype rows; 82/110 = 74.5%
of fall-subtype rows, consistent with p=0.7 under seed 42). The row-level
SET is verified byte-identical; the final shuffle order is not recoverable
(the original run's exact RNG call sequence for the shuffle step is lost to
history), which does not affect training correctness -- MLX-LM consumes
train.jsonl as one epoch's worth of examples regardless of row order.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import jinja2

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_RUNB_DIR = REPO_ROOT / "dataset_runB"
TEMPLATE_PATH = REPO_ROOT / "data" / "qwen3_chat_template.jinja"
OUT_DIR = REPO_ROOT / "dataset" / "sft_runB"

SEED = 42

# Byte-identical to scripts/format_sft_chat.py's SYSTEM_PROMPT -- both the
# original SFT set and Run B's relabeled set share the same training system
# prompt (verified in milestones/12 and cross-checked against
# scripts/evaluate_test_set.py's SYSTEM_PROMPT).
SYSTEM_PROMPT = (
    "You are an offline assistant for African agricultural market prices, "
    "built on WFP VAM price data through December 2024. Answer questions "
    "about crop prices, price trends, and market comparisons briefly and "
    "factually, in the exact numeric format used in training. If you do "
    "not have data for the requested market, commodity, or period, say so "
    "directly instead of guessing."
)

THINK_MARKER = "<think>\n\n</think>\n\n"

OVERSAMPLE_FAMILIES = {"trend_change", "yoy_comparison"}


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


def oversample_train(records: list[dict]) -> list[dict]:
    """Duplicate flat (2x) and a random 70% of fall (1x) trend/yoy examples.

    Deterministic given SEED and iteration order (the input list's own
    order, i.e. dataset_runB/train.jsonl's row order) -- reproduces the
    166-row duplicate set found in the committed dataset/sft_runB/train.jsonl
    exactly (verified; see module docstring).
    """
    random.seed(SEED)
    duplicates = []
    for r in records:
        if r["generator_family"] not in OVERSAMPLE_FAMILIES:
            continue
        subtype = r["generator_subtype"]
        if subtype == "flat":
            for i in (0, 1):
                d = dict(r)
                d["id"] = f"{r['id']}-dup{i}"
                duplicates.append(d)
        elif subtype == "fall":
            if random.random() < 0.7:
                d = dict(r)
                d["id"] = f"{r['id']}-dup0"
                duplicates.append(d)
    combined = records + duplicates
    random.shuffle(combined)  # order not reproducible byte-for-byte; see docstring
    return combined


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmpl = build_template()

    train_in = [json.loads(l) for l in (DATASET_RUNB_DIR / "train.jsonl").open()]
    train_out = oversample_train(train_in)
    with (OUT_DIR / "train.jsonl").open("w", encoding="utf-8") as f:
        n_think_ok = 0
        for ex in train_out:
            formatted = format_example(ex, tmpl)
            if THINK_MARKER in formatted["text"]:
                n_think_ok += 1
            f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
    print(f"train.jsonl: {len(train_in)} base + {len(train_out) - len(train_in)} duplicates "
          f"= {len(train_out)} rows, {n_think_ok}/{len(train_out)} contain the empty think block")

    val_in = [json.loads(l) for l in (DATASET_RUNB_DIR / "val.jsonl").open()]
    with (OUT_DIR / "valid.jsonl").open("w", encoding="utf-8") as f:  # MLX-LM requires "valid.jsonl"
        n_think_ok = 0
        for ex in val_in:
            formatted = format_example(ex, tmpl)
            if THINK_MARKER in formatted["text"]:
                n_think_ok += 1
            f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
    print(f"valid.jsonl: {len(val_in)} rows, {n_think_ok}/{len(val_in)} contain the empty think block")


if __name__ == "__main__":
    main()
