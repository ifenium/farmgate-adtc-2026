# 19 — Gate 2 Submission-Compliance Fixes (§3.2 / §3.3)

**Status:** Done (2026-09-15).

## §3.2 — `download_model.sh` static URL

**Already compliant.** `MODEL_URL` was, and remains, a single static double-quoted string literal
with no `${VAR:-default}` expansion, no runtime construction, no external lookup — confirmed by
reading the file verbatim. Updated only the URL and `EXPECTED_SHA256` values to point at the new
`v1.1-model` release asset (milestone 15's v3 artifact), still a static literal.

**Clean-Ubuntu-22.04 portability defects found and fixed** (not a §3.2 compliance failure per se,
but a real risk under §3.4's "organizers independently run `download_model.sh`"):

- `shasum` is not guaranteed present on a stock Ubuntu install (it ships with `sha256sum` via
  coreutils by default). Fixed: `sha256sum` tried first, `shasum -a 256` as a fallback, matching
  the official template's own `command -v`-based tool-detection pattern.
- No `--fail` on the `curl` call — a server error page downloads silently as if it were the model
  file. Combined with the pre-existing `if [ -f "$MODEL_PATH" ]` idempotency check, a single failed
  run permanently poisons every future run (the broken file is seen as "already present" and never
  re-downloaded). Fixed: `curl -L --fail`, download to a `.partial` path, `mv` into place only on
  success — matching the official template's own pattern, which does this correctly.
- No `curl`-vs-`wget` fallback, unlike the official template. Fixed.
- No script-relative pathing — `MODEL_PATH` was a plain relative path, correct only when invoked
  from the repo root. Fixed with `HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`, matching
  the official template's own idiom.
- The idempotency check now also verifies the checksum of an already-present file (not just its
  existence) before skipping the download, and removes a corrupted file on mismatch rather than
  leaving it in place to fail every subsequent run identically.

Tested directly: a fresh copy with the correct file present skips re-download and verifies clean;
a copy with a corrupted file re-downloads (confirmed correctly attempting a fresh fetch, which
404s in this test only because no matching release asset existed yet at test time — the control
flow itself is correct).

**One genuine improvement over the official template, kept rather than removed**: the official
template's own `download_model.sh` performs **no checksum verification at all** — this project's
`EXPECTED_SHA256` check is an addition beyond what the template requires, not a defect to be
"fixed away."

## §3.1 (submission-hygiene half) — `README.md`, `LICENSE`, `.gitignore`

Both files were **absent** from the submitted repo (confirmed: 63 tracked files, neither present).
The official template ships both and its own README records that requirement
(`milestones/08:21`). Added:

- `README.md` — repository navigation (what each top-level path is, quick-start commands), not a
  restatement of the generic template checklist.
- `LICENSE` — **Apache 2.0**, not the template's own GPL-3.0. Verified the template repo's LICENSE
  file governs only the *template repository's* boilerplate (its own README states "this template
  is licensed under... GPL v3" — a statement about the template, not a mandate on participant
  submissions). Apache 2.0 was chosen to match the base model's own license
  (`Qwen/Qwen3-1.7B`'s `LICENSE` file, confirmed present in the local HF cache snapshot, reads
  "Apache License / Version 2.0") and to avoid GPL copyleft friction against the challenge's
  commercialization-residency prize track.
- `.gitignore` — expanded from the project's original two lines (`*.gguf`, `model/`) to match the
  official template's own scope (`.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `submission.json`,
  `audit.json`), verified by fetching the live template file rather than assumed from memory.
  Confirmed the added `provenance/adapter/*.safetensors` path is unaffected — the template's
  pattern is scoped to `model/*.safetensors`, not global, so adapter weights outside `model/`
  remain committable, which is required for `provenance/` per §3.1.

## §3.3 — code and documentation originality

**Code: no change needed.** Re-confirmed a clean grep for adapted/borrowed-code markers across
`scripts/*` returns zero hits — all first-party.

**Documentation citation gaps found and fixed:**

- The project's own methodology admission — that its verifiable-arithmetic-gold-label approach is
  adapted from `africatic/afritemp-bench` — existed only in `milestones/02` and the untracked
  `HANDOVER.md`, never in the graded `REPORT.md` itself (which mentions afritemp-bench only as a
  licensing cautionary tale, not as a methodology citation). Added a proper citation to
  `REPORT.md` §2.2 and to the new `provenance/DATASET_LICENSE.md`.
- The WFP VAM data source had no URL and no formal attribution statement in `REPORT.md` despite
  `REPORT.md` itself asserting specific corpus statistics (223,549 observations / 39 countries /
  1,922 markets) derived from it. Added the HDX source URL and a CC BY 3.0 IGO attribution
  statement to `REPORT.md` §2.2 and `provenance/DATASET_LICENSE.md`.
- `gguf_new_metadata.py` and `gguf_set_metadata.py` (used for every metadata-only patch in
  `milestones/13`, `14`, and `15`) are upstream `llama.cpp`/`gguf-py` scripts, MIT licensed
  (confirmed by reading `tools/llama.cpp/LICENSE` directly) — previously used without citation.
  Cited in `provenance/DATASET_LICENSE.md`'s tooling-licenses section.

## Open risks / dependencies carried forward

- The submission template repository itself has not been updated for Gate 2 as of this session
  (single commit, `2026-06-15`, confirmed via its GitHub commit history) — this project's own
  README/LICENSE/`.gitignore` choices are based on the template as it currently exists, not on any
  Gate-2-specific template revision.
- `download_model.sh`'s portability fixes were tested locally (macOS, both `sha256sum` and
  `shasum` present) — not tested on an actual Ubuntu 22.04 machine, since none was available this
  session. The fixes themselves (tool-detection fallback chains, matching the official template's
  own pattern) are standard and low-risk, but this is a real gap between "verified the logic is
  correct" and "verified on the target OS," disclosed rather than silently assumed equivalent.
