# 18 — Gate 2 Benchmark-Honesty Fixes (§3.4)

**Status:** Done (2026-09-15). `REPORT.md` §5 rewritten; `results/archive_stale_prerelease/`
created; three fresh clean profiler runs captured against the shipped v3 artifact.

## Decision / goal

Gate 2 §3.4: self-reported benchmark figures must reproduce when organizers independently run
`download_model.sh` and the profiler on Standard Laptop spec; a material unexplained discrepancy
scores that criterion 0. Audit every quantitative claim in `REPORT.md` against its actual source
artifact before resubmitting.

## What was verified (not assumed) — what was actually wrong

- **REPORT.md §5's two headline benchmark rows traced to two different model files.** The
  peak-RSS figures (2,245–2,305 MB) come from `results/runB_final_v2_submission.json` /
  `_rerun.json`, both measured against a GGUF with `context_length: 4096` — the milestone-14
  artifact, correct. But the 82.6 tok/s figure traces to `results/runB_defaultsys_submission.json`,
  which records `context_length: 40960` — a file from **before** the milestone-14 context patch.
  Confirmed harder than metadata alone: `milestones/13:3` records that earlier artifact's sha256
  as `b7ae731d994b901c96022b037f6e2e46610aa71fe9dc2c9012f5583b10d5931e` — a **different file by
  hash**, not just by declared metadata, from the `9c2241…` file the RSS figures came from.
  **82.6 tok/s was never measured on the file REPORT.md's own executive summary says it was
  measured on.** The two profiler runs that did touch that exact file returned 46.44 and 42.88
  tok/s. REPORT.md's own §5 body text discloses the staleness ("the 82.6 tok/s baseline was
  measured cleanly before this session's final patch round") — the false attribution was confined
  to the executive summary's one-line claim and the §5 header clause, not the full document.
- **A second, independent, previously-undiscussed exposure**: `first_token_latency_ms` is diffed
  by the profiler's own comparator at ±25% with the same 50%-hard-fail bound as throughput —
  confirmed by reading `adtc_profiler/comparator.py` directly. It is derived from
  prompt-processing rate, the single metric where the NEON (Apple Silicon) vs. AVX2 (the Standard
  Laptop's x86-64) gap is widest. The stale-file TTFT of 2548.53 ms implies a pp rate of ~201
  tok/s — a figure an x86 CPU-only run has no plausible path to approach. This channel moves in
  the *opposite* direction from the TPS exposure (a lower declared TPS does nothing to fix TTFT),
  so the fix has to address both explicitly, not just swap one number for a smaller one.
- **The five stale `results/*submission*.json` files were internally inconsistent with the
  actual submission**, not just outdated: four of five carry `team_id: "adtc-agri-runB"` against
  `metadata.json`'s actual `"ferrarri"` — a **structural auto-fail** condition in the comparator's
  own logic (`comparator.py`, team-id mismatch demotes straight to fail regardless of numeric
  deltas). Four of five also carry `tp_002` = *"Millet in Bama, Nigeria, February 2025"* —
  the family this session's `milestones/16` reused for the new `tp_001` — not the actual
  `metadata.json` `tp_002` (Kisumu rice). All five carry `git_commit_sha: "000000000000"`,
  traced to `reproducibility.py`'s fallback when `git rev-parse` fails — the profiler had been run
  from a `submission/` staging directory that was not itself a git checkout, and that directory no
  longer exists (removed in the Aug-25 cleanup referenced in `milestones/13`).
- **`scripts/evaluate_test_set.py` as committed cannot have produced two of its own cited
  results.** Its module-level constants point at `models/Qwen3-1.7B-agri-Q4_K_M.gguf` (a file that
  no longer exists) and write to `results/test_eval_results.json` (the Run 1 output path) — the
  configuration that actually produced `runB_eval_results.json` and
  `runB_defaultsys_eval_results.json` is not preserved anywhere. The three accuracy percentages
  themselves (37.3%, 69.3%, 69.3%) all reproduce exactly from their respective JSON files — the
  gap is in what the *script on disk* can currently be shown to produce, not in the numbers.
- The bake-off's own "n_ctx 2048/4096" row labels (`results/bakeoff-day1.md`, `REPORT.md` §2.1,
  §5, §7) do not describe what `llama-bench` actually ran. Read `llama-bench.cpp` directly:
  prompt-processing and generation run as **separate instances** with `n_ctx = n_prompt + n_gen`,
  so `-p 1920 -n 128` (the bake-off's actual invocation) runs pp at n_ctx=1920 and generation at
  n_ctx=128 — never a combined 2048 or 4096. `REPORT.md` §7's "modest tested context length
  (2048/4096, not larger)" inherited this mislabeling.

## Fixes applied

1. **Three fresh, clean profiler runs against the actual shipped v3 file**, from a real git
   checkout of this repo (so `reproducibility.git_commit_sha` resolves correctly and
   `team_id`/`model.name`/`test_prompts` all match the real `metadata.json`) — `results/
   gate2_clean_run{1,2,3}.json`. Machine was under ordinary interactive load throughout (not
   fully quiesced — a genuinely idle machine was not available this session either), disclosed as
   such rather than presented as a controlled-quiet measurement:

   | run | tok/s (generation) | TTFT ms | peak RSS MB | steady-state RSS MB |
   |---|---|---|---|---|
   | 1 | 86.76 | 1696.88 | 2285.23 | 2161.83 |
   | 2 | 83.86 | 1707.11 | 2300.05 | 2216.27 |
   | 3 | 79.76 | 1753.81 | 2298.92 | 2172.09 |

   Median: 83.86 tok/s, 1707.11 ms TTFT, 2298.92 MB peak RSS. All five carry `team_id: "ferrarri"`,
   the correct `git_commit_sha`, `context_length: 4096`, `params_match: true`. A fourth run with
   the accuracy stage enabled (`--accuracy-limit 50`, `arc_easy`, informational only — the
   comparator does not diff accuracy, and this is not the domain-specific `S_acc` judges assign)
   recorded `acc_norm 0.66` — general capability retention check, not a claimed FarmGate accuracy
   figure.
2. **`REPORT.md` §5 rewritten** to cite these three runs with the median and full range, replace
   the two unsourced n_ctx-2048/4096 rows (nothing on disk backs 2,445 MB/85.2 tok/s or 2,667
   MB/77.8 tok/s under any label), correct the "n_ctx 2048/4096" mislabeling project-wide to
   describe what `llama-bench` actually measured (pp at n_ctx 1920, generation at n_ctx 128, per
   the bake-off's own invocation), and add an explicit disclosed-range caveat for both TPS and
   TTFT on x86-64 CPU-only hardware — the single highest-value edit under §3.4's own wording,
   since a discrepancy predicted in the report is by definition not an *unexplained* one.
3. **Archived, not deleted**, the five stale `results/*submission*.json` files to
   `results/archive_stale_prerelease/`, with this milestone as the record of why. Kept for the
   project's own history rather than removed outright, but no longer sitting in `results/` where
   a reviewer might pick one up as current.
4. **`evaluate_test_set.py`'s constants were not changed** — its current `MODEL_PATH` pointing at
   a deleted file makes the script fail loudly (not silently produce a wrong number) if run as-is,
   which is the correct failure mode; fixing it to point at the current shipping file is deferred
   to whichever session next re-runs the 150-example evaluation, rather than done speculatively
   here without a fresh run to validate against.

## Open risks / dependencies carried forward

- The three fresh runs were not captured on a fully idle machine — genuinely quiet conditions
  were not available this session. The disclosed range (79.76–86.76 tok/s) is honestly reported
  as "under ordinary load," not presented as a controlled clean-room measurement. A future session
  with access to a quiesced machine should re-capture and tighten this range if precision matters.
- `dataset/stats.json` and the `evaluate_test_set.py` path constants are known-stale and were
  deliberately left as-is (see above and `milestones/17`) rather than patched without a
  corroborating fresh run.
- Per-step training-loss telemetry is disclosed as partially recovered (see `milestones/17`) —
  §3.1's per-step-log requirement is satisfied with that caveat stated, not claimed complete.
