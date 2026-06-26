#!/usr/bin/env bash
# Stop only the Cerebro FastAPI backend on :7842.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cerebro_desktop_common.sh
source "${SCRIPT_DIR}/cerebro_desktop_common.sh"

main() {
  cerebro_desktop_stop_port 7842 "Cerebro backend"
  cerebro_desktop_log "Backend stop complete."
}

main "$@"
