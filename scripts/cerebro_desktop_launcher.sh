#!/usr/bin/env bash
# Starts Cerebro engine + backend if needed (Phase 2). Idempotent — safe to re-run.
set -euo pipefail

CONFIG_FILE="${HOME}/.cerebro/desktop.json"
LOG_DIR="${HOME}/.cerebro/logs"
ENGINE_URL="http://127.0.0.1:8080/health"
EMBED_URL="http://127.0.0.1:8082/health"
BACKEND_URL="http://127.0.0.1:7842/api/health"
ENGINE_WAIT_SEC=180
BACKEND_WAIT_SEC=120
POLL_SEC=2

log() { echo "[cerebro-launch] $*"; }

die() {
  echo "[cerebro-launch] ERROR: $*" >&2
  exit 1
}

url_healthy() {
  local url="$1"
  curl -sf --max-time 3 "${url}" >/dev/null 2>&1
}

tail_log_hint() {
  local name="$1"
  local path="${LOG_DIR}/${name}.log"
  if [[ -f "${path}" ]]; then
    echo "--- last 20 lines of ${path} ---" >&2
    tail -n 20 "${path}" >&2 || true
  fi
}

load_desktop_config() {
  if [[ ! -f "${CONFIG_FILE}" ]]; then
    die "Missing ${CONFIG_FILE}. Run: cd cerebro && make desktop-config"
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required to read ${CONFIG_FILE}"
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

print(root)
print(cfg.get("profile_env") or "")
print(cfg.get("inference_backend") or "llamacpp")
print("true" if cfg.get("start_embed_server") else "false")
print(llama)
PY
)" || die "Invalid ${CONFIG_FILE}"

  CEREBRO_ROOT="$(echo "${parsed}" | sed -n '1p')"
  PROFILE_ENV="$(echo "${parsed}" | sed -n '2p')"
  INFERENCE_BACKEND="$(echo "${parsed}" | sed -n '3p')"
  START_EMBED="$(echo "${parsed}" | sed -n '4p')"
  LLAMA_SERVER_BIN="$(echo "${parsed}" | sed -n '5p')"

  # GUI apps (Dock) get a minimal PATH — include Homebrew and user bins.
  export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
  if [[ -n "${LLAMA_SERVER_BIN}" && -x "${LLAMA_SERVER_BIN}" ]]; then
    export CEREBRO_LLAMA_SERVER="${LLAMA_SERVER_BIN}"
  fi

  if [[ ! -f "${CEREBRO_ROOT}/main.py" ]]; then
    die "cerebro_root is not valid (no main.py): ${CEREBRO_ROOT}"
  fi
  if [[ ! -x "${CEREBRO_ROOT}/bin/start_engine.sh" ]]; then
    die "Missing ${CEREBRO_ROOT}/bin/start_engine.sh"
  fi
  if [[ ! -x "${CEREBRO_ROOT}/.venv/bin/python" ]]; then
    die "Missing venv at ${CEREBRO_ROOT}/.venv — run: make install"
  fi
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local max_sec="$3"
  local elapsed=0

  while (( elapsed < max_sec )); do
    if url_healthy "${url}"; then
      log "${label} is up (${url})"
      return 0
    fi
    sleep "${POLL_SEC}"
    elapsed=$((elapsed + POLL_SEC))
  done
  return 1
}

ensure_engine() {
  if url_healthy "${ENGINE_URL}"; then
    log "Engine already running on :8080"
    return 0
  fi

  mkdir -p "${LOG_DIR}"
  log "Starting llama-server (chat profile)…"
  (
    cd "${CEREBRO_ROOT}"
    nohup ./bin/start_engine.sh chat >>"${LOG_DIR}/engine.log" 2>&1 &
  )

  if ! wait_for_url "Engine" "${ENGINE_URL}" "${ENGINE_WAIT_SEC}"; then
    tail_log_hint engine
    local recent
    recent="$(tail -n 12 "${LOG_DIR}/engine.log" 2>/dev/null || true)"
    if echo "${recent}" | grep -q "llama-server: not found\|llama-server not found"; then
      die "llama-server not found. Install: brew install llama.cpp — then make desktop-config && Turn on again"
    fi
    if echo "${recent}" | grep -q "failed to load model\|failed to open GGUF"; then
      die "GGUF model missing or wrong path in config/chat.args — see docs/guides/FIX_CHAT_RUNTIME_WARNINGS.md"
    fi
    die "Engine did not become healthy within ${ENGINE_WAIT_SEC}s (see engine.log)"
  fi
}

ensure_embed_server() {
  if [[ "${START_EMBED}" != "true" ]]; then
    log "Skipping embed server (start_embed_server=false)"
    return 0
  fi

  if url_healthy "${EMBED_URL}"; then
    log "Embed server already running on :8082"
    return 0
  fi

  mkdir -p "${LOG_DIR}"
  log "Starting embed server…"
  (
    cd "${CEREBRO_ROOT}"
    nohup ./bin/start_engine.sh embed >>"${LOG_DIR}/embed.log" 2>&1 &
  )

  if ! wait_for_url "Embed server" "${EMBED_URL}" 60; then
    tail_log_hint embed
    die "Embed server did not become healthy within 60s"
  fi
}

ensure_backend() {
  if url_healthy "${BACKEND_URL}"; then
    log "Backend already running on :7842"
    return 0
  fi

  mkdir -p "${LOG_DIR}"
  log "Starting Cerebro backend…"

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
        log "Warning: profile file not found: ${profile_path}"
      fi
    fi
    export CEREBRO_INFERENCE_BACKEND="${INFERENCE_BACKEND}"
    nohup "${CEREBRO_ROOT}/.venv/bin/python" main.py >>"${LOG_DIR}/backend.log" 2>&1 &
  )

  if ! wait_for_url "Backend" "${BACKEND_URL}" "${BACKEND_WAIT_SEC}"; then
    tail_log_hint backend
    die "Backend did not become healthy within ${BACKEND_WAIT_SEC}s"
  fi
}

main() {
  load_desktop_config
  log "Using cerebro_root=${CEREBRO_ROOT}"
  ensure_engine
  ensure_embed_server
  ensure_backend
  log "Cerebro is ready (API ${BACKEND_URL})"
}

main "$@"
