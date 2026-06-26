# Desktop Automation — `/api/workflows/*`

Grabación, almacenamiento y ejecución de workflows de automatización (AppleScript). El frontend permite listar, ver detalle, borrar y ejecutar workflows. La grabación se hace vía agente (comandos "start recording" / "stop recording").

> **Plan de producto y UI:** ver [`docs/plans/workflows-tab-implementation.md`](../plans/workflows-tab-implementation.md) — pestaña Flujos por fases (grabación desde UI, recetas, diseño).

## Arquitectura

```
Frontend (WorkflowPanel.tsx)
    ↓ GET/POST/DELETE /api/workflows/*
server.py (endpoints)
    ↓ llama a
WorkflowStore (core/automation/workflow_store.py)
    ↓ lee/escribe
SQLite (~/.cerebro/db/automation.sqlite)
```

Además:
- **Recorder** (`core/automation/recorder.py`) — captura eventos del sistema vía pyobjc en macOS
- **Generalizer** (`core/automation/generalizer.py`) — usa el LLM para convertir eventos crudos en AppleScript
- **Tools** (`core/automation/tools.py`) — `make_run_workflow(workflow_store)` ejecuta AppleScript via `osascript`

## Schema SQLite

Tabla única `workflows`:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | TEXT PK | UUID |
| name | TEXT | Nombre del workflow |
| description | TEXT | Descripción |
| applescript | TEXT | Código AppleScript |
| parameters | TEXT (JSON) | Parámetros del workflow |
| tags | TEXT (JSON) | Etiquetas |
| created_at | REAL | Timestamp creación |
| updated_at | REAL | Timestamp última modificación |
| run_count | INTEGER | Contador de ejecuciones |
| last_run | REAL | Timestamp última ejecución |

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/workflows` | Listar todos |
| GET | `/api/workflows/{wf_id}` | Detalle |
| DELETE | `/api/workflows/{wf_id}` | Borrar |
| POST | `/api/workflows/{wf_id}/run` | Ejecutar (via osascript) |

## Flujo de grabación

1. Usuario dice "start recording" → `make_start_recording(recorder)` → `recorder.start()`
2. Usuario realiza acciones en el sistema
3. Usuario dice "stop recording" → `make_stop_recording(recorder, workflow_store, provider)`
   - `recorder.stop()` devuelve eventos capturados
   - `generalize_events(events, provider)` convierte a AppleScript vía LLM
   - `workflow_store.save(...)` persiste el workflow
4. Usuario ejecuta via "ejecuta workflow {id}" o desde el frontend

## Ejecución

`make_run_workflow(workflow_store)` en `core/automation/tools.py:87`:

```python
result = subprocess.run(
    ["osascript", "-e", applescript],
    capture_output=True, text=True, timeout=30.0
)
```

Incrementa `run_count` y actualiza `last_run` en cada ejecución exitosa.

## Frontend

`WorkflowPanel.tsx` — overlay full-screen con:
- Lista de workflows (izquierda)
- Detalle con AppleScript, parámetros, tags, run count (derecha)
- Botones: Run y Delete
- Placeholder: "No workflows yet. Ask the agent to 'start recording' to create one."

## Tests

`tests/test_workflow_api.py` — 11 tests, usa `WorkflowStore` real SQLite in-memory, mockea `subprocess.run`:
- Lista vacía / con datos / múltiple
- Get por ID + 404
- Delete + 404
- Run con subprocess mockeado + incremento de contador
- Run con workflow inexistente
