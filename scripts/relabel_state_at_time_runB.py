#!/usr/bin/env python3
"""Run B: relabel all state_at_time examples (train+val+test) from confident
price to calibrated hedge, removing the contradiction with gap_within_range
that milestone 07 diagnosed as the actual root cause (same prompt shape,
two opposing training signals). Everything else copied through unchanged.

Approved hedge wording (user, 2026-08-19), used verbatim with only
{commodity}/{market}/{month_year} substituted -- no invented variation,
per the same "identical prompt shape, no keyword-spotting" principle that
already worked for beyond_cutoff (which generalized perfectly despite a
single fixed template on the user-prompt side).
"""
from __future__ import annotations

import json
from pathlib import Path

SRC_DIR = Path("/Users/Apple/Documents/hack/dataset")
OUT_DIR = Path("/Users/Apple/Documents/hack/dataset_runB")
OUT_DIR.mkdir(exist_ok=True)

HEDGE_TEMPLATE = (
    "I don't have the exact retail price for {commodity} in {market} in {month_year} "
    "— I'm not built to recall individual price points from the series. What I can do "
    "reliably: tell you whether a price rose, fell, or held steady over a period, or "
    "compare it across markets, using WFP data through December 2024."
)


def relabel(ex: dict) -> dict:
    if ex["generator_family"] != "state_at_time":
        return ex
    ex = dict(ex)
    hedge = HEDGE_TEMPLATE.format(
        commodity=ex["commodity"],
        market=ex["market"][0],
        month_year=ex["query_period"]["month_year"],
    )
    ex["gold_answer"] = hedge
    ex["gold_value"] = None
    ex["answer_type"] = "abstain"
    ex["source_rows"] = []  # no longer claiming a specific fact as the answer
    return ex


def main():
    n_relabeled = 0
    n_total = 0
    for split in ("train", "val", "test"):
        examples = [json.loads(l) for l in (SRC_DIR / f"{split}.jsonl").open()]
        out = []
        for ex in examples:
            n_total += 1
            new_ex = relabel(ex)
            if new_ex is not ex:
                n_relabeled += 1
            out.append(new_ex)
        with (OUT_DIR / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for ex in out:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"{split}: {len(out)} examples written")

    print(f"\nrelabeled {n_relabeled}/{n_total} examples (state_at_time only)")


if __name__ == "__main__":
    main()
