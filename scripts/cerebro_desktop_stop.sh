#!/usr/bin/env bash
# Stop engine and backend (full shutdown).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/cerebro_desktop_stop_engine.sh"
bash "${SCRIPT_DIR}/cerebro_desktop_stop_backend.sh"
