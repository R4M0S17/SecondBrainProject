#!/bin/bash
set -e

PROFILE=${1:-chat}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CEREBRO_DIR="$(dirname "$SCRIPT_DIR")"
ARGS_FILE="${CEREBRO_DIR}/config/${PROFILE}.args"

if [ ! -f "$ARGS_FILE" ]; then
  echo "Error: profile '${PROFILE}' not found at ${ARGS_FILE}"
  echo "Available profiles: chat, coding, deep"
  exit 1
fi

echo "Starting llama-server with profile: ${PROFILE}"
exec llama-server \
  --host 127.0.0.1 \
  --port 8080 \
  --prio 3 \
  $(cat "$ARGS_FILE")
