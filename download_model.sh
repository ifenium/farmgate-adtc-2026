#!/bin/bash
# Downloads the submitted GGUF to model/ (idempotent, no credentials required).
# Weights hosted as a GitHub Release asset on this same repo.
set -euo pipefail

MODEL_URL="https://github.com/ifenium/farmgate-adtc-2026/releases/download/v1.0-model/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
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
