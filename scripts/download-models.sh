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

# ── Qwen2.5-0.5B (low-power mode) ──────────────────────────
Qwen2.5_0.5B_FILE="qwen2.5-0.5b-instruct-q5_k_m.gguf"
Qwen2.5_0.5B_SHA256="041474553fcabfc2a2d67903f9d2c2e50bd92528e670da4f33b5d0ce6e59fd55"
Qwen2.5_0.5B_URL="${HF_BASE}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q5_k_m.gguf"

if [ ! -f "$MODELS_DIR/$Qwen2.5_0.5B_FILE" ]; then
    echo "Downloading $Qwen2.5_0.5B_FILE ..."
    curl -L --retry 3 --retry-delay 5 -o "$MODELS_DIR/$Qwen2.5_0.5B_FILE" "$Qwen2.5_0.5B_URL"
    echo "Verifying checksum..."
    echo "$Qwen2.5_0.5B_SHA256  $MODELS_DIR/$Qwen2.5_0.5B_FILE" | shasum -a 256 -c -
    echo "✓ $Qwen2.5_0.5B_FILE downloaded and verified"
fi
