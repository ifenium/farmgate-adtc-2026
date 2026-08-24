# 02 — Domain Lock and Dataset Design

**Status:** Done (2026-08-19)

## Decision

Domain: **Agriculture — crop advisory + market literacy.** Load-bearing data source: **WFP VAM Global Food Prices**. SFT dataset: 1,200 examples across 5 generator families with arithmetically-computed gold answers, 900/150/150 train/val/test.

## Options considered

- **Agriculture** — commodity price data is structured/numeric/time-stamped, so gold answers can be computed arithmetically rather than LLM-judged. The pitch: the moat isn't the topic, it's verifiably deterministic African evaluation data (methodology borrowed from `africatic/afritemp-bench`).
- **Healthcare (malaria + maternal health)** — strong protocol sources (WHO/IMCI) but mostly free text, harder to make deterministic; highest-stakes domain, would need explicit CHW-education framing with abstention behavior.

## What was verified (not assumed)

Ran parallel data-availability scans for both domains before picking — agents were told to confirm access by actually hitting endpoints, not just reading docs.

**Agriculture:** WFP VAM bulk CSV downloaded and parsed directly (not doc-inferred) — 223,549 African price observations, 39 countries, 1,922 markets, in the 2024 file alone. License confirmed via CKAN API metadata: `cc-by-igo`, no NC clause. FAO GIEWS and extension text (PlantwisePlus, FAO guides) checked and marked optional/needs-license-check — GIEWS site resisted scraping and its license is unconfirmed but likely CC BY-NC-SA; not load-bearing.

**Healthcare:** WHO/IMCI PDFs confirmed directly downloadable, genuinely algorithmic decision-tree content — but license confirmed **CC BY-NC-SA 3.0 IGO on all three core documents checked**, a direct conflict with the 6-month commercialization residency prize. DHS's public aggregate API confirmed working with zero registration friction (a real finding — the registration wait was expected to be the blocker, it wasn't), but it's indicator statistics, not clinical guidance text, so it can't replace IMCI as the qualitative backbone.

**The deciding factor** was the license asymmetry, not data volume — both domains were technically buildable in the time left. Agriculture's load-bearing source was clean; healthcare's best content wasn't. Full comparison in the conversation record; verdict folded into [`HANDOVER.md` §6](../HANDOVER.md).

## Dataset schema (approved before generation started)

Five generator families, gold answers computed by arithmetic over WFP VAM rows, full traceability (`source_rows`) back to the raw CSV:

| Family | Count | Tests |
|---|---|---|
| `state_at_time` | 400 | Direct price lookup (local currency / USD subtypes) |
| `trend_change` | 240 | Two-point rise/fall/flat, auto-labeled by threshold |
| `yoy_comparison` | 200 | Calendar-aligned same-month year-over-year |
| `cross_market_ranking` | 160 | N-market ranking, unit/currency-matched to avoid spurious comparison |
| `abstention_negative` | 200 | Correct refusal — `gap_within_range` (real data gaps) and `beyond_cutoff` (dates past the training cutoff) |

Full field-level schema and per-family prompt templates are in the conversation record and in [`03-dataset-generation.md`](03-dataset-generation.md) once the generator exists.

## Open risks / dependencies carried forward

- **Depends on HANDOVER §3 (standalone-GGUF question) — flagging explicitly per instruction.** The split strategy for families 1–4 deliberately lets train and test reference overlapping underlying price facts (only the exact question phrasing is held out), on the reasoning that the model has no RAG fallback at inference and must carry price knowledge in its weights alone. **If §3 comes back answered "judges run the full app" (RAG included), this assumption should be revisited** — a fact-disjoint split would become viable and arguably more honest once retrieval can supply facts at inference time, and part of the qualitative/advisory layer could shift into the RAG corpus instead of the fine-tune.
- `yoy_comparison` required a second calendar year the original plan didn't account for (2024 WFP file alone only spans Jan–Dec 2024, discovered empirically, not assumed) — 2023 file pulled in (same source, same `cc-by-igo` license, user sign-off obtained). No design change otherwise.
- Extension/advisory text (qualitative layer) remains unverified on bulk-scrape friction and license — still a stretch addition, not a dependency, per the original scan.
