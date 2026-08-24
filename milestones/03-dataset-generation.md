# 03 — Dataset Generation

**Status:** Done (2026-08-19)

## Decision / goal

Build the generator implementing the schema from [`02-domain-and-dataset-design.md`](02-domain-and-dataset-design.md) and run it against real WFP VAM data to produce the actual 1,200-example SFT set (900/150/150 train/val/test).

## Options considered

Straight implementation of the approved design — no alternative approaches considered at this stage; the design decisions were already made and approved in milestone 02.

## What was verified (not assumed)

Generator: [`scripts/generate_sft_dataset.py`](../scripts/generate_sft_dataset.py). Output: [`dataset/`](../dataset/) (`train.jsonl` 900, `val.jsonl` 150, `test.jsonl` 150, `all.jsonl` 1,200, `stats.json`).

- **Every family hit its exact target on the first run** — no shortfall, no redistribution needed: state_at_time 400, trend_change 240, yoy_comparison 200, cross_market_ranking 160, abstention_negative 200 (100 gap + 100 cutoff). Total 1,200. Aggregate split landed exactly on 900/150/150.
- **Arithmetic independently re-verified, not just trusted from the generator**: pulled the raw CSV rows for a sampled `yoy_comparison` example (Rice imported, Beyla, Guinea: 6667→8000 GNF) and a `trend_change` example (Salt, Yunusari, Nigeria: 75.00→127.27 NGN) and recomputed the % change by hand from source — matched the generator's output exactly (19.99%≈20.0%, 69.69%≈69.7%). Also confirmed a sampled `gap_within_range` abstention case (Maize, Tshilenge, DRC, June 2023) has zero matching rows in the raw CSV while the same market/commodity reports in Jan/Jul/Aug/Sep 2023 — a genuine gap amid regular reporting, not an obscure never-reported combo.
- Split was implemented stratified by `(generator_family, generator_subtype)`, not just by family — so rise/fall/flat and lowest/highest/full_rank are each proportionally represented in train/val/test, not just the parent family. A refinement beyond what milestone 02 specified, not a deviation from it.

## Deviations from plan (surfaced during implementation)

- `two_point_examples` (backing both `trend_change` and `yoy_comparison`) uses the **full available date range** per (market, commodity) — earliest vs. latest date on file for `trend_change`, earliest vs. latest year for the same calendar month for `yoy_comparison` — rather than an arbitrary pair of dates. Maximizes observed price movement per example; means `trend_change` spans are not uniformly distributed in length.
- `gap_within_range` required the (market, commodity) pair to report in **≥8 of the 24 available months** before a missing month counts as a "gap" — added during implementation so the family tests genuine reporting gaps amid regular coverage, not combos that are almost never reported at all (which milestone 02's wording didn't explicitly rule out).
- **Abstention prompts are phrased identically to `state_at_time` prompts** (same template, no "is this available?" framing) — deliberate, so the model has to recognize absence from the lack of a training signal rather than learning to keyword-spot a differently-worded question.

## Open risks / dependencies carried forward

- Inherits the standalone-GGUF dependency flagged in milestone 02 (families 1–4 split strategy) — unchanged, still open.
- `yoy_comparison` needed a second data file (2023, `cc-by-igo`, same source) — downloaded with sign-off, no design change otherwise.
- Chat-formatting `train.jsonl`/`val.jsonl` for QLoRA is its own milestone: [`04-sft-formatting.md`](04-sft-formatting.md).
