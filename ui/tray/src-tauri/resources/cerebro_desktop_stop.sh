#!/usr/bin/env bash
set -euo pipefail
log() { echo "[cerebro-stop] $*"; }

stop_port() {
  local port="$1"
  local name="$2"
  local pids
  pids=$(lsof -t -i ":${port}" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "${pids}" ]]; then
    log "${name} (port ${port}): not running"
    return 0
  fi
  log "Stopping ${name} on port ${port} (PIDs: ${pids})"
  kill ${pids} 2>/dev/null || true
  sleep 1
  if lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    log "Force kill ${name} on ${port}"
    kill -9 $(lsof -t -i ":${port}" -sTCP:LISTEN) 2>/dev/null || true
  fi
}

stop_port 7842 "Cerebro backend"
stop_port 8080 "llama-server (chat)"
log "Done."
