#!/bin/bash
# Downloads the submitted GGUF to model/ (idempotent, no credentials required).
#
# TODO before submission: the weight file is not yet hosted publicly. Upload
# models/Qwen3-1.7B-agri-final-Q4_K_M.gguf
# (sha256: 9c2241433b92a2ba45bab9e1eee398d774b8884030885c37ec0c141fd1bca5ce)
# to a public Hugging Face repo, GitHub Release asset, or other stable public
# URL, then set MODEL_URL below.
# This is a hosting decision, not made here -- pick where it goes.
set -euo pipefail

MODEL_URL="TODO-set-public-download-url"
MODEL_PATH="model/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
EXPECTED_SHA256="9c2241433b92a2ba45bab9e1eee398d774b8884030885c37ec0c141fd1bca5ce"

mkdir -p model

if [ -f "$MODEL_PATH" ]; then
  echo "Model already present at $MODEL_PATH, skipping download."
else
  echo "Downloading model to $MODEL_PATH..."
  curl -L -o "$MODEL_PATH" "$MODEL_URL"
fi

ACTUAL_SHA256=$(shasum -a 256 "$MODEL_PATH" | awk '{print $1}')
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "ERROR: checksum mismatch for $MODEL_PATH"
  echo "  expected: $EXPECTED_SHA256"
  echo "  actual:   $ACTUAL_SHA256"
  exit 1
fi

echo "Model verified at $MODEL_PATH."
