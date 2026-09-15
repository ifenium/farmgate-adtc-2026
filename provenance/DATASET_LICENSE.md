# Dataset provenance and license

## Source

**WFP VAM Global Food Prices**, via HDX/CKAN, no authentication required:
https://data.humdata.org/dataset/global-wfp-food-prices

Two annual bulk CSVs used, both under the same license:
- `data/wfp_2024.csv` (59,114,868 bytes) — confirmed by direct parse: 223,549 African
  price observations, 39 countries, 1,922 distinct markets.
- `data/wfp_2023.csv` (65,233,602 bytes) — pulled in for `yoy_comparison`'s
  second calendar year (see `milestones/02`).

Columns used: `countryiso3, date, admin1, admin2, market, commodity, unit, pricetype,
currency, price, usdprice`.

## License

**CC BY 3.0 IGO** (`cc-by-igo` per the CKAN API metadata) — attribution required, no
non-commercial restriction. Confirmed before any development time was spent on this
domain, specifically to avoid the non-commercial trap found in an adjacent dataset
(`africatic/afritemp-bench`'s WGI/World Bank components are CC-BY-NC-3.0-IGO; see
`milestones/02`).

**Attribution statement**, per CC BY 3.0 IGO's attribution requirement:

> Price data sourced from the World Food Programme (WFP) Vulnerability Analysis and
> Mapping (VAM) unit's Global Food Prices dataset, licensed CC BY 3.0 IGO. No
> endorsement by WFP is implied.

## Derived data

Every gold answer in `dataset/` and `dataset_runB/` is **computed by arithmetic over
these CSVs** — never hand-written, never LLM-generated (see `milestones/02`, `03`).
Each record in `dataset/all.jsonl` carries a `source_rows` field with full
row-level traceability back to the raw CSV (`market, commodity, date, price,
usdprice, currency, unit, pricetype, priceflag`). This lineage is **not** carried
into the chat-formatted `dataset/sft/` / `dataset/sft_runB/` files actually consumed
by training — those retain only `id, generator_family, generator_subtype, messages,
text`. Trace a specific training example's source data via its `id` in
`dataset/all.jsonl` or `dataset_runB/{train,val,test}.jsonl`, which do carry
`source_rows`.

## Methodology citation

The core methodological approach — gold labels computed by verifiable arithmetic
over structured data rather than LLM-judged distillation — is adapted from
[`africatic/afritemp-bench`](https://huggingface.co/datasets/africatic/afritemp-bench)
(12,568 examples of temporal reasoning over African economic indicators, same
verifiable-arithmetic-labels approach, plus DPO preference pairs targeting
cutoff-awareness and spurious comparison). Used as a methodology template only —
no data or code from that dataset is reused; FarmGate's dataset is generated
independently from WFP VAM by `scripts/generate_sft_dataset.py`. See `REPORT.md`
§2.2 and `milestones/02`.

## Tooling licenses

- `gguf_new_metadata.py` and `gguf_set_metadata.py` (used for the metadata-only
  patches described in `milestones/13`, `14`, `15`) are upstream `gguf-py` scripts
  distributed with `llama.cpp`, MIT licensed. Vendored at
  `tools/llama.cpp/gguf-py/gguf/scripts/` in this project's build tree (not
  committed to this repo — see `download_model.sh` / `tools/llama.cpp` for how to
  obtain them).
