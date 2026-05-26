#!/bin/bash
# Live reminder E2E — cerebro backend (matches desktop app)
set -euo pipefail
API="http://127.0.0.1:7842/api/query"
STREAM="http://127.0.0.1:7842/api/query/stream"
OUT="/Users/mb/Desktop/Javier/SecondBrain/manual_tests/logs/_live_reminder_cerebro_results.jsonl"
PROMPT='crea un recordatorio para mañana a las 3pm llamado "prueba1"'
: > "$OUT"

echo "=== POST /api/query ===" >&2
start=$(date +%s)
body=$(curl -sf -X POST "$API" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "agent": "general-v1"}))' "$PROMPT")")
end=$(date +%s)
printf '%s\n' "{\"endpoint\":\"query\",\"elapsed_s\":$((end-start)),\"response\":$body}" >> "$OUT"
echo "$body" | python3 -m json.tool

echo "=== POST /api/query/stream ===" >&2
start=$(date +%s)
stream_raw=$(curl -sf -N -X POST "$STREAM" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "agent": "general-v1"}))' "$PROMPT")")
end=$(date +%s)
printf '%s\n' "{\"endpoint\":\"stream\",\"elapsed_s\":$((end-start)),\"raw\":$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"$stream_raw")}" >> "$OUT"
echo "$stream_raw" | tail -20

echo "Wrote $OUT"
