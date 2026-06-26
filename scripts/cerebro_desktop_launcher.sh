#!/usr/bin/env bash
# Legacy full launch: engine + embed + backend (idempotent). Same behavior as pre-split.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/cerebro_desktop_engine.sh"
bash "${SCRIPT_DIR}/cerebro_desktop_backend.sh"
