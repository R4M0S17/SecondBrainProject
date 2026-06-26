#!/usr/bin/env bash
# Start only llama-server (:8080) and optional embed server (:8082) (idempotent).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cerebro_desktop_common.sh
source "${SCRIPT_DIR}/cerebro_desktop_common.sh"

main() {
  cerebro_desktop_load_config
  cerebro_desktop_log "Starting engine only (cerebro_root=${CEREBRO_ROOT})"
  cerebro_desktop_log "Using profile=${PROFILE} (args file: ${ARGS_FILE})"

  if [[ "${INFERENCE_BACKEND}" == "mlx" ]]; then
    cerebro_desktop_log "MLX backend — skipping llama.cpp engine (MLX uses ~1 GB instead of ~2.5 GB)"
    cerebro_desktop_stop_stale_llama_engine
  else
    cerebro_desktop_ensure_engine
    cerebro_desktop_ensure_embed_server
  fi

  cerebro_desktop_log "Engine stack ready"
}

main "$@"
