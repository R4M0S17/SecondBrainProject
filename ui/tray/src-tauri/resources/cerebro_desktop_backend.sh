#!/usr/bin/env bash
# Start only the Cerebro FastAPI backend on :7842 (idempotent).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cerebro_desktop_common.sh
source "${SCRIPT_DIR}/cerebro_desktop_common.sh"

main() {
  cerebro_desktop_load_config
  cerebro_desktop_log "Starting backend only (cerebro_root=${CEREBRO_ROOT})"
  cerebro_desktop_ensure_backend
  cerebro_desktop_log "Backend ready (API ${BACKEND_URL})"
}

main "$@"
