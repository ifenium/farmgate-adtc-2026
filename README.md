# FarmGate

ADTC 2026 submission `ADTC2026_903` — Africa Deep Tech Challenge, Laptop LLM track,
Agriculture domain. An offline assistant for African agricultural market prices, QLoRA
fine-tuned from Qwen3 1.7B on WFP VAM price data, quantized to GGUF Q4_K_M, running
entirely on-device through `llama.cpp` with zero cloud dependency.

Built from the official [`adtc-2026-submission-template`](https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template).

## Repository layout

| Path | What it is |
|---|---|
| [`metadata.json`](metadata.json) | Submission manifest — team, model, test prompts |
| [`download_model.sh`](download_model.sh) | Downloads the GGUF from this repo's GitHub Release, verifies SHA256 |
| [`REPORT.md`](REPORT.md) | Full technical writeup — problem, design, constraints, findings, benchmarks, provenance |
| [`milestones/`](milestones/) | Dated decision record, one file per significant call made during the build — options considered, what was verified, what was deviated from |
| [`provenance/`](provenance/) | Gate 2 §3.1 model-provenance package — adapter weights, training config and logs, dataset sample, merge/quantization script, checksums |
| [`scripts/`](scripts/) | Dataset generation, SFT formatting, relabeling, evaluation — all first-party |
| [`dataset/`](dataset/) | The 1,200-example generator output (Run 1 split) |
| [`dataset_runB/`](dataset_runB/) | The relabeled Run B split (the shipped model's training target) |
| [`results/`](results/) | Bake-off and evaluation artifacts. `results/archive_stale_prerelease/` holds superseded profiler runs kept for the record, not for citation — see the note in that folder. |

## Quick start

```bash
bash download_model.sh
adtc-profiler run --submission . --mode participant --output submission.json --skip-accuracy
```

## License

Code and documentation in this repository are licensed under [Apache 2.0](LICENSE).
The base model (Qwen3 1.7B) is Apache 2.0. Training data is derived from WFP VAM Global
Food Prices, licensed CC BY 3.0 IGO (attribution required, see `REPORT.md` §2.2 and
[`provenance/DATASET_LICENSE.md`](provenance/DATASET_LICENSE.md)). Methodology for
deterministic, arithmetic-derived gold labels is adapted from
[`africatic/afritemp-bench`](https://huggingface.co/datasets/africatic/afritemp-bench)
(cited in `REPORT.md` §2.2).
