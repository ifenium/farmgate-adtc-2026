#!/bin/bash
# Downloads the submitted GGUF to model/ (idempotent, no credentials required).
# Weights hosted as a GitHub Release asset on this same repo.
set -euo pipefail

MODEL_URL="https://github.com/ifenium/farmgate-adtc-2026/releases/download/v1.1-model/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
EXPECTED_SHA256="6508b72361a7f57915e458aa92f8a6a90ba4cace778e3c88361fb3b3749baf4c"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$HERE/model"
MODEL_PATH="$MODEL_DIR/Qwen3-1.7B-agri-final-Q4_K_M.gguf"
PARTIAL_PATH="$MODEL_PATH.partial"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "ERROR: neither sha256sum nor shasum is available on this system." >&2
    exit 1
  fi
}

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_PATH" ] && [ "$(sha256_of "$MODEL_PATH")" = "$EXPECTED_SHA256" ]; then
  echo "Model already present and verified at $MODEL_PATH, skipping download."
else
  rm -f "$MODEL_PATH" "$PARTIAL_PATH"
  echo "Downloading model to $MODEL_PATH..."
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --progress-bar -o "$PARTIAL_PATH" "$MODEL_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$PARTIAL_PATH" "$MODEL_URL"
  else
    echo "ERROR: neither curl nor wget is available on this system." >&2
    exit 1
  fi
  mv "$PARTIAL_PATH" "$MODEL_PATH"
fi

ACTUAL_SHA256="$(sha256_of "$MODEL_PATH")"
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "ERROR: checksum mismatch for $MODEL_PATH"
  echo "  expected: $EXPECTED_SHA256"
  echo "  actual:   $ACTUAL_SHA256"
  rm -f "$MODEL_PATH"
  exit 1
fi

echo "Model verified at $MODEL_PATH."
