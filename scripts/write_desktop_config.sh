#!/usr/bin/env bash
# Writes ~/.cerebro/desktop.json for one-click desktop launch (Phase 1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.cerebro"
CONFIG_FILE="${CONFIG_DIR}/desktop.json"
PROFILE_REL="config/profiles/lite-8gb.env"
PROFILE_PATH="${ROOT}/${PROFILE_REL}"

if [[ ! -f "${ROOT}/main.py" ]]; then
  echo "Error: ${ROOT} does not look like a Cerebro install (missing main.py)." >&2
  exit 1
fi

if [[ ! -x "${ROOT}/bin/start_engine.sh" ]]; then
  echo "Error: missing ${ROOT}/bin/start_engine.sh" >&2
  exit 1
fi

profile_env="${PROFILE_REL}"
if [[ ! -f "${PROFILE_PATH}" ]]; then
  echo "Warning: ${PROFILE_PATH} not found; profile_env will be empty (default env)." >&2
  profile_env=""
fi

if [[ ! -d "${ROOT}/.venv" ]]; then
  echo "Warning: ${ROOT}/.venv not found. Run 'make install' in ${ROOT} before desktop launch." >&2
fi

mkdir -p "${CONFIG_DIR}"
mkdir -p "${CONFIG_DIR}/logs"

# Detect brew-installed llama-server binary
LLAMA_SERVER_BIN=""
if command -v brew &>/dev/null; then
  _brew_llama="$(brew --prefix llama.cpp 2>/dev/null)/bin/llama-server" || true
  if [[ -x "${_brew_llama}" ]]; then
    LLAMA_SERVER_BIN="${_brew_llama}"
  fi
fi
# Fallback: check PATH
if [[ -z "${LLAMA_SERVER_BIN}" ]]; then
  _path_llama="$(command -v llama-server 2>/dev/null || true)"
  if [[ -n "${_path_llama}" && -x "${_path_llama}" ]]; then
    LLAMA_SERVER_BIN="${_path_llama}"
  fi
fi

# Preserve existing llama_server_bin if it was manually set
if [[ -f "${CONFIG_FILE}" ]]; then
  _existing="$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}')).get('llama_server_bin',''))" 2>/dev/null || true)"
  if [[ -n "${_existing}" && -x "${_existing}" ]]; then
    LLAMA_SERVER_BIN="${_existing}"
  fi
fi

cerebro_root_escaped="${ROOT//\\/\\\\}"
cerebro_root_escaped="${cerebro_root_escaped//\"/\\\"}"

LLAMA_LINE=""
if [[ -n "${LLAMA_SERVER_BIN}" ]]; then
  LLAMA_LINE="  \"llama_server_bin\": \"${LLAMA_SERVER_BIN}\""
fi

cat > "${CONFIG_FILE}" <<EOF
{
  "cerebro_root": "${cerebro_root_escaped}",
  "profile_env": "${profile_env}",
  "inference_backend": "llamacpp",
  "start_embed_server": false${LLAMA_LINE:+, }${LLAMA_LINE}
}
EOF

echo "Wrote ${CONFIG_FILE}"
echo "  cerebro_root: ${ROOT}"
echo "  profile_env:  ${profile_env:-<none>}"
echo "  llama_server: ${LLAMA_SERVER_BIN:-<PATH>}"
echo "  logs:         ${CONFIG_DIR}/logs/"
