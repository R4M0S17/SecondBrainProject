#!/bin/bash
set -e

MODELS_DIR=${MODELS_DIR:-bin/models}
CHAT_MODEL=${CEREBRO_LLAMACPP_MODEL:-Qwen3.5-2B-UD-Q4_K_XL.gguf}
EMBED_MODEL=${CEREBRO_EMBED_MODEL:-v5-nano-retrieval-Q4_K_M.gguf}
HF_BASE=${HF_BASE:-https://huggingface.co}

declare -A MODEL_URLS
MODEL_URLS["Qwen3.5-2B-UD-Q4_K_XL.gguf"]="${HF_BASE}/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-UD-Q4_K_XL.gguf"
MODEL_URLS["v5-nano-retrieval-Q4_K_M.gguf"]="${HF_BASE}/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF/resolve/main/v5-nano-retrieval-Q4_K_M.gguf"

mkdir -p "$MODELS_DIR"

download_if_missing() {
  local filename="$1"
  local url="${MODEL_URLS[$filename]}"
  [ -z "$url" ] && { echo "WARN: No URL for $filename"; return; }
  if [ -f "${MODELS_DIR}/${filename}" ]; then
    echo "✓ $filename already exists at ${MODELS_DIR}/${filename}"
    return
  fi
  echo "Downloading $filename ..."
  curl -L --retry 3 --retry-delay 5 -o "${MODELS_DIR}/${filename}" "$url"
  echo "✓ $filename downloaded"
}

download_if_missing "$CHAT_MODEL"

if [ "${CEREBRO_EMBEDDINGS_BACKEND:-local}" = "llamacpp" ]; then
  download_if_missing "$EMBED_MODEL"
fi
