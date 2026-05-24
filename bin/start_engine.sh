#!/bin/bash
set -e

PROFILE=${1:-chat}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CEREBRO_DIR="$(dirname "$SCRIPT_DIR")"
ARGS_FILE="${CEREBRO_DIR}/config/${PROFILE}.args"

if [ ! -f "$ARGS_FILE" ]; then
  echo "Error: profile '${PROFILE}' not found at ${ARGS_FILE}"
  echo "Available profiles: chat, coding, deep, embed"
  exit 1
fi

if [ "$PROFILE" = "embed" ]; then
  PORT=8082
else
  PORT=8080
fi

if lsof -i ":${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    PID=$(lsof -t -i ":${PORT}" -sTCP:LISTEN 2>/dev/null | head -1)
    echo "llama-server is already running on http://127.0.0.1:${PORT} (PID ${PID:-unknown})."
    if [ "$PROFILE" = "embed" ]; then
      echo "Embedding server is ready — no need to start again."
    else
      echo "Skip 'make engine' and start the backend: cd cerebro && make run"
      echo "Remember a third terminal for embeddings: make engine-embed"
    fi
    if [ "$PROFILE" = "embed" ]; then
      echo "To restart: kill \$(lsof -t -i :${PORT}) && make engine-embed"
    else
      echo "To restart: kill \$(lsof -t -i :${PORT}) && make engine"
    fi
    exit 0
  fi
  echo "Error: port ${PORT} is in use by another program (not a healthy llama-server)."
  lsof -i ":${PORT}" -sTCP:LISTEN || true
  echo "Free the port: kill \$(lsof -t -i :${PORT})"
  exit 1
fi

if [ "$PROFILE" = "embed" ]; then
  MODEL_LINE=$(grep '^--model' "$ARGS_FILE" | head -1)
  MODEL_REL=${MODEL_LINE#--model }
  MODEL_PATH="${CEREBRO_DIR}/${MODEL_REL}"
  if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: embedding model not found at ${MODEL_PATH}"
    echo "Download it (see docs/guides/FIX_CHAT_RUNTIME_WARNINGS.md) then retry: make engine-embed"
    exit 1
  fi
fi

mkdir -p "${CEREBRO_DIR}/bin/cache"

resolve_llama_server() {
  if [ -n "${CEREBRO_LLAMA_SERVER:-}" ] && [ -x "${CEREBRO_LLAMA_SERVER}" ]; then
    echo "${CEREBRO_LLAMA_SERVER}"
    return 0
  fi
  if command -v llama-server >/dev/null 2>&1; then
    command -v llama-server
    return 0
  fi
  for candidate in \
    /opt/homebrew/bin/llama-server \
    /usr/local/bin/llama-server \
    "${HOME}/.local/bin/llama-server"; do
    if [ -x "${candidate}" ]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

LLAMA_SERVER="$(resolve_llama_server || true)"
if [ -z "${LLAMA_SERVER}" ]; then
  echo "Error: llama-server not found (GUI apps often lack Homebrew in PATH)."
  echo "Install: brew install llama.cpp"
  echo "Or set CEREBRO_LLAMA_SERVER in ~/.cerebro/desktop.json (run: make desktop-config)"
  exit 1
fi

echo "Starting llama-server with profile: ${PROFILE} on port ${PORT} (${LLAMA_SERVER})"
exec "${LLAMA_SERVER}" \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --prio 3 \
  $(cat "$ARGS_FILE")
