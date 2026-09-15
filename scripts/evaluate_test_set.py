#!/usr/bin/env python3
"""Evaluate the quantized fine-tuned GGUF against the held-out dataset/test.jsonl
(150 examples, never seen in training or validation).

Programmatic grading per answer_type -- no LLM judge, matching the project's
"verifiably deterministic evaluation" methodology (milestones 02/03):
  - numeric (state_at_time): extract first number from the response, compare
    to gold_value with a 5% relative tolerance.
  - classification (trend_change, yoy_comparison): keyword-match the
    rise/fall/flat direction words against the gold generator_subtype.
  - ranking (cross_market_ranking): match the named market(s) and, for
    full_rank, their mentioned order, against gold_value.
  - abstain (abstention_negative): correct iff the response contains
    refusal language; a confident number instead is a hard fail, tagged
    separately from "near-miss arithmetic" so the two failure modes don't
    get conflated in the report.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import jinja2
from llama_cpp import Llama

MODEL_PATH = "/Users/Apple/Documents/hack/models/Qwen3-1.7B-agri-Q4_K_M.gguf"
TEST_PATH = "/Users/Apple/Documents/hack/dataset/test.jsonl"
TEMPLATE_PATH = "/Users/Apple/Documents/hack/data/qwen3_chat_template.jinja"
OUT_PATH = "/Users/Apple/Documents/hack/results/test_eval_results.json"

SYSTEM_PROMPT = (
    "You are an offline assistant for African agricultural market prices, "
    "built on WFP VAM price data through December 2024. Answer questions "
    "about crop prices, price trends, and market comparisons briefly and "
    "factually, in the exact numeric format used in training. If you do "
    "not have data for the requested market, commodity, or period, say so "
    "directly instead of guessing."
)

RISE_WORDS = ["rose", "rise", "risen", "increased", "increase", "higher", "went up"]
FALL_WORDS = ["fell", "fall", "fallen", "decreased", "decrease", "lower", "went down", "dropped"]
FLAT_WORDS = ["stayed about the same", "stayed the same", "unchanged", "no change", "remained the same", "steady"]

ABSTAIN_WORDS = [
    "don't have", "do not have", "no data", "not available", "unavailable",
    "no reported", "cannot provide", "can't provide", "unable to provide",
    "not have a", "no record", "don't have data", "no price data",
]

NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def build_template() -> jinja2.Template:
    template_str = Path(TEMPLATE_PATH).read_text(encoding="utf-8")
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    return env.from_string(template_str)


def render_prompt(tmpl: jinja2.Template, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return tmpl.render(messages=messages, add_generation_prompt=True, enable_thinking=False, tools=None)


def extract_first_number(text: str) -> float | None:
    """First plausible price number in the response.

    Our training format ("...in March 2024 was 77.00 KES...") echoes the
    query's date back before the price, so a bare 4-digit year (1990-2099,
    no decimal) is skipped as likely date-contamination rather than the
    answer -- unless it's the only number present, in which case it's used
    as a fallback (rare commodities like "Exchange rate" could plausibly
    have a gold value in that range).
    """
    candidates = []
    for m in NUMBER_RE.finditer(text):
        raw = m.group(0)
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        is_bare_year = YEAR_RE.match(raw) is not None
        candidates.append((val, is_bare_year))
    if not candidates:
        return None
    non_year = [v for v, is_year in candidates if not is_year]
    if non_year:
        return non_year[0]
    return candidates[0][0]


def grade_numeric(response: str, gold_value: float) -> tuple[bool, str]:
    pred = extract_first_number(response)
    if pred is None:
        return False, "no_numeric_answer"
    tol = max(abs(gold_value) * 0.05, 0.01)
    if abs(pred - gold_value) <= tol:
        return True, "correct"
    rel_err = abs(pred - gold_value) / max(abs(gold_value), 1e-9)
    if rel_err <= 0.20:
        return False, "near_miss"
    return False, "wrong_value"


def _any_word_match(low: str, words: list[str]) -> bool:
    # Word-boundary match, not bare substring: "flat" must not match inside
    # "inflation", etc. Multi-word phrases (e.g. "no change") have no
    # trailing-boundary ambiguity issue, \b still applies correctly to them.
    return any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)


def grade_classification(response: str, gold_subtype: str) -> tuple[bool, str]:
    low = response.lower()
    found = set()
    if _any_word_match(low, FLAT_WORDS):
        found.add("flat")
    if _any_word_match(low, RISE_WORDS):
        found.add("rise")
    if _any_word_match(low, FALL_WORDS):
        found.add("fall")
    if len(found) != 1:
        return False, f"ambiguous({sorted(found)})" if found else "no_direction_found"
    predicted = next(iter(found))
    if predicted == gold_subtype:
        return True, "correct"
    return False, f"wrong_direction(said_{predicted})"


def find_market_positions(text: str, markets: list[str]) -> dict[str, int]:
    """First non-overlapping occurrence of each market name.

    Processes longest names first so a short name that's a literal substring
    of a longer one (e.g. "Lama" inside "LAMA-TESSI") can't falsely match
    inside the longer name's span -- it has to find its own, separate
    occurrence in the text.
    """
    low = text.lower()
    order = sorted(markets, key=len, reverse=True)
    claimed: list[tuple[int, int]] = []
    positions: dict[str, int] = {}
    for market in order:
        needle = market.lower()
        search_from = 0
        while True:
            idx = low.find(needle, search_from)
            if idx == -1:
                break
            end = idx + len(needle)
            overlaps = any(not (end <= s or idx >= e) for s, e in claimed)
            if not overlaps:
                positions[market] = idx
                claimed.append((idx, end))
                break
            search_from = idx + 1
    return positions


def grade_ranking(response: str, subtype: str, gold_value: dict) -> tuple[bool, str]:
    positions = find_market_positions(response, list(gold_value))
    if not positions:
        return False, "no_market_named"

    sorted_markets = sorted(gold_value.items(), key=lambda kv: kv[1])
    if subtype == "lowest":
        target = sorted_markets[0][1]
        expected_set = {m for m, v in gold_value.items() if v == target}  # ties all correct
        predicted = min(positions, key=positions.get)
        return (predicted in expected_set), ("correct" if predicted in expected_set else f"named_{predicted}_not_{sorted(expected_set)}")
    if subtype == "highest":
        target = sorted_markets[-1][1]
        expected_set = {m for m, v in gold_value.items() if v == target}  # ties all correct
        predicted = min(positions, key=positions.get)
        return (predicted in expected_set), ("correct" if predicted in expected_set else f"named_{predicted}_not_{sorted(expected_set)}")
    # full_rank
    if len(positions) < len(gold_value):
        missing = set(gold_value) - set(positions)
        return False, f"missing_markets({sorted(missing)})"
    predicted_order = sorted(positions, key=positions.get)
    expected_order = [m for m, _ in sorted_markets]
    if predicted_order == expected_order:
        return True, "correct"
    return False, f"wrong_order(got_{predicted_order})"


def grade_abstain(response: str) -> tuple[bool, str]:
    low = response.lower()
    abstained = any(w in low for w in ABSTAIN_WORDS)
    if abstained:
        return True, "correct_abstention"
    if extract_first_number(response) is not None:
        return False, "confident_fabrication"
    return False, "non_abstain_non_numeric"


def grade(ex: dict, response: str) -> tuple[bool, str]:
    at = ex["answer_type"]
    if at == "numeric":
        return grade_numeric(response, ex["gold_value"])
    if at == "classification":
        return grade_classification(response, ex["generator_subtype"])
    if at == "ranking":
        return grade_ranking(response, ex["generator_subtype"], ex["gold_value"])
    if at == "abstain":
        return grade_abstain(response)
    raise ValueError(f"unknown answer_type {at}")


def main():
    tmpl = build_template()
    examples = [json.loads(l) for l in Path(TEST_PATH).open()]
    print(f"loaded {len(examples)} test examples")

    llm = Llama(model_path=MODEL_PATH, n_ctx=2048, verbose=False)

    results = []
    for i, ex in enumerate(examples):
        prompt = render_prompt(tmpl, ex["prompt"])
        out = llm.create_completion(
            prompt=prompt,
            max_tokens=150,
            temperature=0.0,
            repeat_penalty=1.1,
            stop=["<|im_end|>"],
        )
        response = out["choices"][0]["text"].strip()
        correct, reason = grade(ex, response)
        results.append({
            "id": ex["id"],
            "generator_family": ex["generator_family"],
            "generator_subtype": ex["generator_subtype"],
            "prompt": ex["prompt"],
            "gold_answer": ex["gold_answer"],
            "response": response,
            "correct": correct,
            "reason": reason,
        })
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(examples)} done")

    Path(OUT_PATH).write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # --- report ---
    by_family = defaultdict(list)
    for r in results:
        by_family[r["generator_family"]].append(r)
        by_family[(r["generator_family"], r["generator_subtype"])].append(r)

    print("\n=== Per-family accuracy ===")
    for fam in ["state_at_time", "trend_change", "yoy_comparison", "cross_market_ranking", "abstention_negative"]:
        rs = by_family[fam]
        n_correct = sum(r["correct"] for r in rs)
        print(f"{fam:24s} {n_correct:3d}/{len(rs):3d}  ({100*n_correct/len(rs):.1f}%)")
        for sub in sorted(set(r["generator_subtype"] for r in rs)):
            sub_rs = by_family[(fam, sub)]
            n_c = sum(r["correct"] for r in sub_rs)
            print(f"    {sub:22s} {n_c:3d}/{len(sub_rs):3d}  ({100*n_c/len(sub_rs):.1f}%)")

    n_correct_total = sum(r["correct"] for r in results)
    print(f"\nAGGREGATE: {n_correct_total}/{len(results)} ({100*n_correct_total/len(results):.1f}%)")
    print(f"\nFull results written to {OUT_PATH}")


if __name__ == "__main__":
    main()
