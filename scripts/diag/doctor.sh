#!/usr/bin/env bash
# Cerebro doctor — runs all diag scripts and prints actionable, colorized hints.
# Exit 0 when all checks pass; 1 when any check fails (see printed FAIL lines).

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 2

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

RED=$'\033[0;31m'
GRN=$'\033[0;32m'
YLW=$'\033[1;33m'
BLD=$'\033[1m'
NC=$'\033[0m'

fail=0
TMP=$(mktemp -d "${TMPDIR:-/tmp}/cerebro-doctor.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

echo "${BLD}=== Cerebro doctor ===${NC}"
echo "repo: $ROOT"
echo

# --- snapshot (RAM pressure) ---
"$PY" scripts/diag/snapshot.py >"$TMP/snapshot.txt" 2>&1 || true
cat "$TMP/snapshot.txt"
echo
if grep -q 'pressure=critical' "$TMP/snapshot.txt" 2>/dev/null; then
  echo "${RED}FAIL:${NC} RAM pressure is ${RED}critical${NC} — quit heavy apps or use ${GRN}make lite${NC} with ${GRN}make engine-lite${NC}."
  fail=1
elif grep -q 'pressure=warn' "$TMP/snapshot.txt" 2>/dev/null; then
  echo "${YLW}FAIL:${NC} RAM pressure is ${YLW}warn${NC} — not fully green; use lite profile or free RAM before relying on local inference."
  fail=1
fi

# --- models ---
set +e
"$PY" scripts/diag/check_models.py >"$TMP/models.txt" 2>&1
mod_ex=$?
set -u
cat "$TMP/models.txt"
echo
if [[ "$mod_ex" -eq 2 ]]; then
  fail=1
  while IFS= read -r line; do
    [[ "$line" == *"[MISS]"* ]] || continue
    hint="place the GGUF in bin/models/ or run ${GRN}python scripts/download_model.py llama${NC} for the default Llama 3.2 3B chat file"
    if [[ "$line" == *"embed"* ]]; then
      hint="add the embed GGUF named in CEREBRO_EMBED_MODEL to bin/models/"
    fi
    echo "${RED}FAIL:${NC} missing model — $line — $hint"
  done < <(grep '\[MISS\]' "$TMP/models.txt" || true)
elif [[ "$mod_ex" -ne 0 ]]; then
  fail=1
  echo "${RED}FAIL:${NC} check_models.py exited $mod_ex — inspect output above."
fi

# --- calendar permission ---
set +e
"$PY" scripts/diag/check_calendar.py >"$TMP/cal.txt" 2>&1
cal_ex=$?
set -u
cat "$TMP/cal.txt"
echo
if grep -q '^not-macos$' "$TMP/cal.txt" 2>/dev/null; then
  echo "${GRN}OK:${NC} not macOS — calendar probe skipped."
elif [[ "$cal_ex" -ne 0 ]]; then
  fail=1
  echo "${RED}FAIL:${NC} Calendar Automation — open ${YLW}System Settings → Privacy & Security → Automation${NC} and grant Calendar to the app running Python (Terminal / iTerm / your IDE)."
fi

# --- routing (needs live backend + engine) ---
set +e
"$PY" scripts/diag/check_routing.py >"$TMP/route.txt" 2>&1
route_ex=$?
set -u
cat "$TMP/route.txt"
echo
if [[ "$route_ex" -ne 0 ]]; then
  fail=1
  echo "${RED}FAIL:${NC} routing check — ensure backend (${GRN}make run${NC} or ${GRN}make lite${NC}) and llama engine (${GRN}make engine${NC} or ${GRN}make engine-lite${NC}) are up; optional: set ${GRN}CEREBRO_URL${NC} for a non-default host."
fi

if [[ "$fail" -eq 0 ]]; then
  echo "${GRN}${BLD}All doctor checks passed.${NC}"
else
  echo "${RED}${BLD}Doctor finished with failures.${NC} Fix items above and re-run: ${GRN}bash scripts/diag/doctor.sh${NC}"
fi
exit "$fail"
