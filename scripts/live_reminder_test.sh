#!/bin/bash
# Live reminder E2E against :7842 + llama.cpp :8080
set -euo pipefail
API="http://127.0.0.1:7842/api/query"
OUT="/Users/mb/Desktop/Javier/SecondBrain/manual_tests/logs/_live_reminder_results.jsonl"
: > "$OUT"

prompts=(
  'crea un recordatorio para mañana a las 3pm llamado "prueba1"'
  'crea un recordatorio mañana a las 3pm con nombre "Reunión con Juan"'
  'crea un recordatorio llamado Reunión con Juan para mañana a las 3pm'
)

i=1
for p in "${prompts[@]}"; do
  echo "=== Test $i ===" >&2
  start=$(date +%s)
  body=$(curl -sf -X POST "$API" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "agent": "general-v1"}))' "$p")")
  end=$(date +%s)
  elapsed=$((end - start))
  printf '%s\n' "{\"test\": $i, \"prompt\": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$p"), \"elapsed_s\": $elapsed, \"response\": $body}" >> "$OUT"
  echo "$body" | python3 -m json.tool | head -30
  echo "elapsed: ${elapsed}s" >&2
  i=$((i + 1))
done
echo "Wrote $OUT"
