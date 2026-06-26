#!/usr/bin/env bash
# Shared helpers for Cerebro desktop launch/stop scripts (engine-backend split).
set -euo pipefail

CONFIG_FILE="${HOME}/.cerebro/desktop.json"
LOG_DIR="${HOME}/.cerebro/logs"
CEREBRO_LOW_POWER_ENABLED="${CEREBRO_LOW_POWER_ENABLED:-false}"
ENGINE_URL="http://127.0.0.1:8080/health"
EMBED_URL="http://127.0.0.1:8082/health"
BACKEND_URL="http://127.0.0.1:7842/api/health"
ENGINE_WAIT_SEC=180
BACKEND_WAIT_SEC=120
POLL_SEC=2

cerebro_desktop_log() { echo "[cerebro-desktop] $*"; }

cerebro_desktop_die() {
  echo "[cerebro-desktop] ERROR: $*" >&2
  exit 1
}

cerebro_desktop_url_healthy() {
  local url="$1"
  curl -sf --max-time 3 "${url}" >/dev/null 2>&1
}

cerebro_desktop_tail_log_hint() {
  local name="$1"
  local path="${LOG_DIR}/${name}.log"
  if [[ -f "${path}" ]]; then
    echo "--- last 20 lines of ${path} ---" >&2
    tail -n 20 "${path}" >&2 || true
  fi
}

cerebro_desktop_load_config() {
  if [[ ! -f "${CONFIG_FILE}" ]]; then
    cerebro_desktop_die "Missing ${CONFIG_FILE}. Run: make desktop-config"
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    cerebro_desktop_die "python3 is required to read ${CONFIG_FILE}"
  fi

  local parsed
  parsed="$(python3 - "${CONFIG_FILE}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)

for key in ("cerebro_root", "profile_env", "inference_backend", "start_embed_server"):
    if key not in cfg:
        raise SystemExit(f"desktop.json missing required field: {key}")

root = cfg["cerebro_root"]
if not isinstance(root, str) or not root:
    raise SystemExit("cerebro_root must be a non-empty string")

llama = cfg.get("llama_server_bin") or ""
if llama and not isinstance(llama, str):
    raise SystemExit("llama_server_bin must be a string")

profile = cfg.get("profile") or "normal"
args_file = "chat-lowpower.args" if profile == "low-power" else "chat.args"

print(root)
print(cfg.get("profile_env") or "")
print(cfg.get("inference_backend") or "llamacpp")
print("true" if cfg.get("start_embed_server") else "false")
print(llama)
print(profile)
print(args_file)
PY
)" || cerebro_desktop_die "Invalid ${CONFIG_FILE}"

  CEREBRO_ROOT="$(echo "${parsed}" | sed -n '1p')"
  PROFILE_ENV="$(echo "${parsed}" | sed -n '2p')"
  INFERENCE_BACKEND="$(echo "${parsed}" | sed -n '3p')"
  START_EMBED="$(echo "${parsed}" | sed -n '4p')"
  LLAMA_SERVER_BIN="$(echo "${parsed}" | sed -n '5p')"
  PROFILE="$(echo "${parsed}" | sed -n '6p')"
  ARGS_FILE="$(echo "${parsed}" | sed -n '7p')"

  export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
  if [[ -n "${LLAMA_SERVER_BIN}" && -x "${LLAMA_SERVER_BIN}" ]]; then
    export CEREBRO_LLAMA_SERVER="${LLAMA_SERVER_BIN}"
  fi

  if [[ ! -f "${CEREBRO_ROOT}/main.py" ]]; then
    cerebro_desktop_die "cerebro_root is not valid (no main.py): ${CEREBRO_ROOT}"
  fi
  if [[ ! -x "${CEREBRO_ROOT}/bin/start_engine.sh" ]]; then
    cerebro_desktop_die "Missing ${CEREBRO_ROOT}/bin/start_engine.sh"
  fi
  if [[ ! -x "${CEREBRO_ROOT}/.venv/bin/python" ]]; then
    cerebro_desktop_die "Missing venv at ${CEREBRO_ROOT}/.venv — run: make install"
  fi
}

cerebro_desktop_wait_for_url() {
  local label="$1"
  local url="$2"
  local max_sec="$3"
  local elapsed=0

  while (( elapsed < max_sec )); do
    if cerebro_desktop_url_healthy "${url}"; then
      cerebro_desktop_log "${label} is up (${url})"
      return 0
    fi
    sleep "${POLL_SEC}"
    elapsed=$((elapsed + POLL_SEC))
  done
  return 1
}

cerebro_desktop_ensure_engine() {
  if cerebro_desktop_url_healthy "${ENGINE_URL}"; then
    cerebro_desktop_log "Engine already running on :8080"
    return 0
  fi

  local engine_profile="chat"
  if [[ "${PROFILE}" == "low-power" ]]; then
    engine_profile="chat-lowpower"
  fi

  mkdir -p "${LOG_DIR}"
  cerebro_desktop_log "Starting llama-server (${engine_profile} profile)…"
  (
    cd "${CEREBRO_ROOT}"
    nohup ./bin/start_engine.sh "${engine_profile}" >>"${LOG_DIR}/engine.log" 2>&1 &
  )

  if ! cerebro_desktop_wait_for_url "Engine" "${ENGINE_URL}" "${ENGINE_WAIT_SEC}"; then
    cerebro_desktop_tail_log_hint engine
    local recent
    recent="$(tail -n 12 "${LOG_DIR}/engine.log" 2>/dev/null || true)"
    if echo "${recent}" | grep -q "llama-server: not found\|llama-server not found"; then
      cerebro_desktop_die "llama-server not found. Install: brew install llama.cpp — then make desktop-config && Turn on again"
    fi
    if echo "${recent}" | grep -q "failed to load model\|failed to open GGUF"; then
      cerebro_desktop_die "GGUF model missing or wrong path in config/${ARGS_FILE} — see docs/guides/FIX_CHAT_RUNTIME_WARNINGS.md"
    fi
    cerebro_desktop_die "Engine did not become healthy within ${ENGINE_WAIT_SEC}s (see engine.log)"
  fi
}

cerebro_desktop_ensure_embed_server() {
  if [[ "${START_EMBED}" != "true" ]]; then
    cerebro_desktop_log "Skipping embed server (start_embed_server=false)"
    return 0
  fi

  if cerebro_desktop_url_healthy "${EMBED_URL}"; then
    cerebro_desktop_log "Embed server already running on :8082"
    return 0
  fi

  mkdir -p "${LOG_DIR}"
  cerebro_desktop_log "Starting embed server…"
  (
    cd "${CEREBRO_ROOT}"
    nohup ./bin/start_engine.sh embed >>"${LOG_DIR}/embed.log" 2>&1 &
  )

  if ! cerebro_desktop_wait_for_url "Embed server" "${EMBED_URL}" 60; then
    cerebro_desktop_tail_log_hint embed
    cerebro_desktop_die "Embed server did not become healthy within 60s"
  fi
}

cerebro_desktop_ensure_backend() {
  if cerebro_desktop_url_healthy "${BACKEND_URL}"; then
    cerebro_desktop_log "Backend already running on :7842"
    return 0
  fi

  mkdir -p "${LOG_DIR}"
  cerebro_desktop_log "Starting Cerebro backend…"

  (
    cd "${CEREBRO_ROOT}"
    if [[ -n "${PROFILE_ENV}" ]]; then
      local profile_path="${CEREBRO_ROOT}/${PROFILE_ENV}"
      if [[ -f "${profile_path}" ]]; then
        set -a
        # shellcheck source=/dev/null
        . "${profile_path}"
        set +a
      else
        cerebro_desktop_log "Warning: profile file not found: ${profile_path}"
      fi
    fi
    export CEREBRO_INFERENCE_BACKEND="${INFERENCE_BACKEND}"
    if [[ "${PROFILE}" == "low-power" ]]; then
      export CEREBRO_LOW_POWER_ENABLED="true"
      export CEREBRO_LLAMACPP_MODEL="qwen2.5-0.5b-instruct-q5_k_m.gguf"
      cerebro_desktop_log "Using low-power profile (0.5B model — 8GB RAM friendly)"
    fi
    nohup "${CEREBRO_ROOT}/.venv/bin/python" main.py >>"${LOG_DIR}/backend.log" 2>&1 &
  )

  if ! cerebro_desktop_wait_for_url "Backend" "${BACKEND_URL}" "${BACKEND_WAIT_SEC}"; then
    cerebro_desktop_tail_log_hint backend
    cerebro_desktop_die "Backend did not become healthy within ${BACKEND_WAIT_SEC}s"
  fi
}

cerebro_desktop_stop_port() {
  local port="$1"
  local name="$2"
  local pids
  pids=$(lsof -t -i ":${port}" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "${pids}" ]]; then
    cerebro_desktop_log "${name} (port ${port}): not running"
    return 0
  fi
  cerebro_desktop_log "Stopping ${name} on port ${port} (PIDs: ${pids})"
  # shellcheck disable=SC2086
  kill ${pids} 2>/dev/null || true
  sleep 1
  if lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    cerebro_desktop_log "Force kill ${name} on ${port}"
    kill -9 "$(lsof -t -i ":${port}" -sTCP:LISTEN)" 2>/dev/null || true
  fi
}

cerebro_desktop_stop_stale_llama_engine() {
  if cerebro_desktop_url_healthy "${ENGINE_URL}"; then
    cerebro_desktop_log "Stopping stale llama.cpp engine on :8080…"
    cerebro_desktop_stop_port 8080 "llama-server (chat)"
  fi
}
