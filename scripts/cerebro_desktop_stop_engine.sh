#!/usr/bin/env bash
# Stop llama-server (:8080) and embed server (:8082).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cerebro_desktop_common.sh
source "${SCRIPT_DIR}/cerebro_desktop_common.sh"

main() {
  cerebro_desktop_stop_port 8080 "llama-server (chat)"
  cerebro_desktop_stop_port 8082 "embed server"
  cerebro_desktop_log "Engine stop complete."
}

main "$@"
