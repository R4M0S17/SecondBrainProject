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

cerebro_root_escaped="${ROOT//\\/\\\\}"
cerebro_root_escaped="${cerebro_root_escaped//\"/\\\"}"

cat > "${CONFIG_FILE}" <<EOF
{
  "cerebro_root": "${cerebro_root_escaped}",
  "profile_env": "${profile_env}",
  "inference_backend": "llamacpp",
  "start_embed_server": false
}
EOF

echo "Wrote ${CONFIG_FILE}"
echo "  cerebro_root: ${ROOT}"
echo "  profile_env:  ${profile_env:-<none>}"
echo "  logs:         ${CONFIG_DIR}/logs/"
