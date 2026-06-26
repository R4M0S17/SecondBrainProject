# Time-Travel Debugger — `/api/debug/*`

SQLite-backed recorder que captura cada transición del agente LangGraph durante `AgentRuntime.run_streaming()`. Las escrituras van a un `asyncio.Queue` con background worker que hace flush cada 500ms / 50 items — el hot path nunca se bloquea.

## Arquitectura

```
Frontend (TimeTravelView.tsx)
    ↓ GET /api/debug/runs, /api/debug/runs/{id}/steps, /api/debug/steps/{id}
server.py (endpoints)
    ↓ llama a
TimeTravelRecorder (core/observability/time_travel.py)
    ↓ lee/escribe
SQLite (~/.cerebro/db/time_travel.sqlite)
```

## Schema SQLite

3 tablas con foreign keys y cascade delete:

- **`execution_runs`** — una ejecución del agente (id, agent_id, query, conversation_id, created_at, duration_ms, success)
- **`execution_steps`** — un nodo del grafo (id, run_id FK, step_number, node_name, input/output_preview, tool_name, tool_args_json, tool_result_preview, needs_confirmation, timestamp)
- **`execution_tokens`** — tokens emitidos en un step (id, step_id FK, token_order, token_text, is_final)

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/debug/runs` | Lista ejecuciones (limit/offset) |
| GET | `/api/debug/runs/{run_id}/steps` | Steps de una ejecución |
| GET | `/api/debug/steps/{step_id}` | Step detail con tokens |

## Integración en AgentRuntime

En `core/agents/runtime.py:1305`:

```python
_tt = self._time_travel
_run_id = _uuid.uuid4().hex if _tt else None
_step_num = 0
```

En cada `yield` del streaming:

1. `_tt.start_run(run_id, agent_id, query, conversation_id)` — al comenzar
2. `_tt.record_step(...)` — por cada nodo del grafo (fast_path, context_assembly, reason_node, tool_node, observe_node, update_state)
3. `_tt.record_tokens(step_id, tokens)` — lote de tokens emitidos
4. `_tt.end_run(run_id, success)` — al terminar

## Ciclo de vida

- **start**: `app_state.time_travel_recorder.start()` en `lifespan` (`server.py:487`)
- **stop**: `recorder.shutdown()` + `enforce_retention()` en shutdown (`server.py:504-506`)
- **Retention**: TTL 7 días, max 500 runs por defecto

## Tests

`tests/test_time_travel_debugger.py` — 9 tests, mockea el recorder, cubre:
- Lista vacía / con datos
- Paginación
- Steps por run_id
- Step detail con tokens
- 404 cuando no hay recorder / step no existe
