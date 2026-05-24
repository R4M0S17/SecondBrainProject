#!/usr/bin/env bash
# HTTP smoke tests for Cerebro (manual_tests/test_1.md regression matrix).
# Requires: make engine && make run (in other terminals).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

export CEREBRO_BASE_URL="${CEREBRO_BASE_URL:-http://127.0.0.1:7842}"
export CEREBRO_LLAMACPP_URL="${CEREBRO_LLAMACPP_URL:-http://127.0.0.1:8080}"

exec "$PYTHON" "$ROOT/scripts/smoke_runner.py"
