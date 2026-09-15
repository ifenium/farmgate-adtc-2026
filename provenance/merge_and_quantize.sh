#!/bin/bash
# FarmGate / ADTC2026_903 -- full merge + quantize + patch chain (Gate 2 §3.1).
#
# Reconstructed from session-transcript history (see provenance/README.md
# for exact source line numbers and timestamps) -- this script did not exist
# as a committed artifact before this Gate 2 pass; the chain was previously
# documented only in milestone-file prose, and that prose stopped at
# llama-quantize, omitting the base-quantize step, the metadata patches, and
# the promotion-to-shipping-filename step.
#
# Verified end to end this session: running the base-quantize + fuse +
# convert + quantize steps against the untouched Qwen/Qwen3-1.7B checkpoint
# (no adapter) reproduces a working GGUF used for the §3.1 before/after
# exhibit. The QLoRA training step itself (mlx_lm lora) is NOT re-run by
# this script -- it launches a real multi-hour training job; see
# provenance/training_logs/ for the recovered per-step logs of the run that
# produced adapters_runB/, and provenance/adapter/ for the adapter it saved.
#
# Requires: mlx-lm, llama.cpp built at tools/llama.cpp (convert_hf_to_gguf.py
# + llama-quantize), gguf-py's gguf_new_metadata.py / gguf_set_metadata.py
# scripts (both ship with llama.cpp's gguf-py package; also vendored at
# tools/llama.cpp/gguf-py/gguf/scripts/ in this repo's build tree).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
LLAMA_CPP="${LLAMA_CPP_DIR:-$REPO_ROOT/tools/llama.cpp}"
BASE_HF_REPO="Qwen/Qwen3-1.7B"
BASE_REVISION="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"

WORK_DIR="${WORK_DIR:-$REPO_ROOT/build}"
mkdir -p "$WORK_DIR"

usage() {
  cat <<EOF
Usage:
  $0                 Full chain: base quantize -> QLoRA (external) -> fuse ->
                      convert -> quantize -> patch chat-template -> patch
                      context length -> promote to shipping filename.
                      Requires an already-trained adapter at
                      provenance/adapter/ (or ADAPTER_PATH env var).
  $0 --base-only      Steps 0-3 only, no adapter: produces an UNMODIFIED
                      base-model GGUF at
                      \$WORK_DIR/Qwen3-1.7B-base-Q4_K_M.gguf -- this is what
                      built the §3.1 before/after exhibit
                      (provenance/before_after/).
EOF
}

MODE="full"
if [ "${1:-}" = "--base-only" ]; then MODE="base-only"; fi
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then usage; exit 0; fi

# --- step 0: base 4-bit MLX quantization -----------------------------------
# QLoRA loads the base model in 4-bit for training-memory efficiency only --
# this is separate from the final GGUF quantization in step 3. Pin the
# revision explicitly; the original Aug-19 run did not (see
# provenance/README.md "Revision pinning" note).
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

if [ ! -d "$WORK_DIR/Qwen3-1.7B-mlx-4bit" ]; then
  echo "[0] base 4-bit MLX quantization ($BASE_HF_REPO @ $BASE_REVISION)"
  # Known gotcha (see milestones/05): a bare --hf-path can crash on save if
  # the local HF cache lacks .gitattributes/LICENSE/README.md -- mlx_lm's
  # save() step demands the full repo be mirrored locally even though only
  # the weight/config/tokenizer files are actually used. Pre-warming the
  # cache with a full snapshot_download (as the base-only path below does)
  # avoids this; a cold cache may need that same pre-fetch here too.
  python3 -m mlx_lm convert --hf-path "$BASE_HF_REPO" --revision "$BASE_REVISION" \
    -q --mlx-path "$WORK_DIR/Qwen3-1.7B-mlx-4bit"
else
  echo "[0] base 4-bit MLX checkpoint already present, skipping"
fi

if [ "$MODE" = "base-only" ]; then
  # --- base-only path: straight to GGUF, no LoRA, no dequantize -----------
  # Convert the ORIGINAL fp16 HF snapshot directly (not the 4-bit MLX
  # checkpoint) so the "before" exhibit reflects the unmodified public
  # weights, not an artifact of MLX's own quantization.
  BASE_SNAPSHOT="$(python3 -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$BASE_HF_REPO', revision='$BASE_REVISION'))
")"
  echo "[1] convert (base, no adapter) -> f16 GGUF"
  python3 "$LLAMA_CPP/convert_hf_to_gguf.py" "$BASE_SNAPSHOT" \
    --outfile "$WORK_DIR/Qwen3-1.7B-base.f16.gguf" --outtype f16
  echo "[2] quantize -> Q4_K_M"
  "$LLAMA_CPP/build-cpu/bin/llama-quantize" \
    "$WORK_DIR/Qwen3-1.7B-base.f16.gguf" "$WORK_DIR/Qwen3-1.7B-base-Q4_K_M.gguf" Q4_K_M
  sha256sum "$WORK_DIR/Qwen3-1.7B-base-Q4_K_M.gguf"
  echo "Base-only GGUF: $WORK_DIR/Qwen3-1.7B-base-Q4_K_M.gguf"
  exit 0
fi

# --- steps 1-6: fine-tuned chain -------------------------------------------
ADAPTER_PATH="${ADAPTER_PATH:-$HERE/adapter}"
if [ ! -f "$ADAPTER_PATH/adapters.safetensors" ]; then
  echo "ERROR: no adapter found at $ADAPTER_PATH -- run QLoRA training first" >&2
  echo "  (this script does not train; see provenance/training_logs/ for the" >&2
  echo "  recovered logs of the run that produced provenance/adapter/)" >&2
  exit 1
fi

echo "[1] fuse (dequantize)"
python3 -m mlx_lm fuse --model "$WORK_DIR/Qwen3-1.7B-mlx-4bit" \
  --adapter-path "$ADAPTER_PATH" --save-path "$WORK_DIR/Qwen3-1.7B-fused" --dequantize

echo "[2] convert -> f16 GGUF"
python3 "$LLAMA_CPP/convert_hf_to_gguf.py" "$WORK_DIR/Qwen3-1.7B-fused" \
  --outfile "$WORK_DIR/Qwen3-1.7B.f16.gguf" --outtype f16

echo "[3] quantize -> Q4_K_M"
"$LLAMA_CPP/build-cpu/bin/llama-quantize" \
  "$WORK_DIR/Qwen3-1.7B.f16.gguf" "$WORK_DIR/Qwen3-1.7B-Q4_K_M.gguf" Q4_K_M

echo "[4] patch: default chat-template system message"
# Fires ONLY when the caller supplies no system message of its own (an
# {%- else %} branch on the existing messages[0].role == 'system' check) --
# see milestones/13 (original patch) and milestones/15 (this session's fix,
# which replaces the milestone-13 wording with the VERBATIM training system
# prompt -- the model is system-prompt-brittle; see milestones/15 for why).
python3 "$LLAMA_CPP/gguf-py/gguf/scripts/gguf_new_metadata.py" \
  "$WORK_DIR/Qwen3-1.7B-Q4_K_M.gguf" "$WORK_DIR/Qwen3-1.7B-defaultsys.gguf" \
  --chat-template-file "$REPO_ROOT/data/runB_chat_template_v3_trainingsys.jinja" --force

echo "[5] patch: context_length 40960 -> 4096"
# Prevents runtimes that don't set --ctx-size from allocating KV cache for
# the full native 40,960-token context (measured real-use peak RSS 3.4-4.2
# GB pre-patch vs ~2.6 GB post-patch -- see milestones/14).
cp "$WORK_DIR/Qwen3-1.7B-defaultsys.gguf" "$WORK_DIR/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
python3 "$LLAMA_CPP/gguf-py/gguf/scripts/gguf_set_metadata.py" \
  "$WORK_DIR/Qwen3-1.7B-agri-final-Q4_K_M.gguf" qwen3.context_length 4096 --force --verbose

echo "[6] verify"
sha256sum "$WORK_DIR/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
echo "Expected (this repo's shipping artifact): 6508b72361a7f57915e458aa92f8a6a90ba4cace778e3c88361fb3b3749baf4c"
echo "Fine-tuned GGUF: $WORK_DIR/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
