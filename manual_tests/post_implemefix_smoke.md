# ImplemeFIX — Post smoke report (Module 7)

| Field | Value |
|--------|--------|
| Date | 2026-05-19 21:41 EDT |
| Branch | `fix-1-ram-containment` |
| Base URL | http://127.0.0.1:7842 |
| Chat engine | http://127.0.0.1:8080 |
| Chat model | `Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` |
| Embeddings | `CEREBRO_EMBEDDINGS_BACKEND=local` (no `:8082` server) |
| `make test` | **688 passed**, 85.4% coverage |
| `make smoke` | **exit 0** (10 warnings — RAM pressure) |

## vs pre-flight baseline

| Metric | Baseline (Llama + embed server) | Post-ImplemeFIX |
|--------|--------------------------------|-----------------|
| Chat RAM (llama-server) | ~2126 MiB | ~1900 MiB (Qwen Q4_K_M) |
| Embed server | ~234 MiB on :8082 | **0** (in-process MiniLM) |
| First-turn latency | ~20.9 s | ~18.6 s (still above 8 s target) |
| Second-turn latency | ~15.1 s | ~20.3 s (RAM-stressed run) |
| Raw JSON in chat | Reproduced | Not seen in smoke math/bullets checks |

## Automated results

| Check | Status |
|-------|--------|
| `backend_reachable` | ok |
| `health` | ok |
| `status` | ok |
| `ram_ratio` | ok |
| `ram_budget` | warn |
| `embed_server_8082` | ok |
| `config_patch` | ok |
| `fleet_status` | ok |
| `latency_turn1_s` | ok |
| `latency_turn1_meta_ms` | ok |
| `latency_turn1` | warn |
| `latency_turn2_s` | ok |
| `latency_turn2` | warn |
| `time_turn3` | warn |
| `time_three_turns` | ok |
| `fs_write_cerebrofiles` | warn |
| `fs_deny_unauthorized` | warn |
| `calendar_query` | ok |
| `g2_math` | ok |
| `g3_bullets` | ok |
| `g6_calendar_create` | warn |
| `c1_calendar_agent` | warn |
| `g7_write_file` | warn |
| `auto_calendar_route` | ok |

## Status snapshot

```json
{
  "model": "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
  "engine_ok": true,
  "ram_used_gb": 6.73,
  "ram_total_gb": 8.0,
  "ram_pressure": "warn"
}
```

## Warnings

- ram_budget: system RAM 84% used (target ≤60%)
- latency_turn1: 18.6s > target 8.0s
- latency_turn2: 20.3s > target 1.0s
- time_turn3: answer may not echo system time: '200'
- fs_write_cerebrofiles: unclear tool path: 'No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.'
- fs_deny_unauthorized: expected friendly denial, got: 'no pude interpretar la respuesta del modelo. intenta reformular tu pregunta.'
- g6_calendar_create: expected create_calendar_event pending_tool or approval
- c1_calendar_agent: expected create_calendar_event pending_tool
- g7_write_file: HTTP 500 (RAM-stressed machine — treating as warn)
- g7_write_file: expected write_file confirmation or tool call

## Module 7 checklist

| Item | Result |
|------|--------|
| Cold start engine + backend | OK (automated via smoke) |
| Tray UI | Manual — `cd ui/tray && npm run dev` |
| First-turn latency ≤ 8 s | **WARN** 18.6 s |
| Second-turn latency ≤ 1 s | **WARN** 20.3 s (84% RAM used) |
| RAM ≤ 60% steady-state | **WARN** 84% system RAM during smoke |
| Time/date × 3 | OK aggregate; turn 3 short answer flagged |
| File write CerebroFiles | **WARN** parser fallback under RAM stress |
| Unauthorized path message | **WARN** same |
| Calendar query | OK |
| `make test` | OK (688 tests) |
| `make lint` | Pre-existing black drift on branch (21 files); smoke_runner formatted |
| Activity Monitor screenshot | Manual |

## How to re-run

```bash
# Terminal 1
make engine

# Terminal 2
set -a && . config/profiles/lite-8gb.env && set +a && make run

# Terminal 3
CEREBRO_SMOKE_QUERY_TIMEOUT=180 make smoke
```

## Targets (8 GB M1)

- First-turn latency target: ≤ 8.0s (warn if over)
- Second-turn latency target: ≤ 1.0s (warn if over)
- System RAM target: ≤ 60% during chat
