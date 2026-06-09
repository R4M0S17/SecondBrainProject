# Plan de Implementación Modular

Tres features priorizadas para Cerebro2, ordenadas por complejidad. Sin código — solo la ruta arquitectónica.

---

## Fase 1: Time-Travel Debugger (SQLite) ✅ COMPLETADA

### Resumen de implementación

| Archivo | Tipo | Propósito |
|---------|------|-----------|
| `core/observability/time_travel.py` | Nuevo | SQLite schema + `TimeTravelRecorder` con worker queue |
| `core/observability/__init__.py` | Modificado | Exporta `TimeTravelRecorder` |
| `core/agents/runtime.py` | Modificado | Hook en `run_streaming()` + fast path |
| `ui/tray/server.py` | Modificado | Router `/api/debug/*` + shutdown hook |
| `main.py` | Modificado | Crea y inyecta `TimeTravelRecorder` en `AppState` |
| `ui/tray/src/api/types.ts` | Modificado | Interfaces `DebugRun`, `DebugStep`, `DebugStepDetail` |
| `ui/tray/src/api/client.ts` | Modificado | Funciones `listDebugRuns`, `getDebugRunSteps`, `getDebugStepDetail` |
| `ui/tray/src/stores/debug.ts` | Nuevo | Zustand store |
| `ui/tray/src/components/debug/TimeTravelView.tsx` | Nuevo | Panel full-screen con runs list, steps list, step detail |
| `ui/tray/src/layouts/Header.tsx` | Modificado | Botón gear icon en header que abre el debugger |

### Detalles de implementación

**Backend (`time_travel.py`):**
- SQLite con WAL mode y 3 tablas: `execution_runs`, `execution_steps`, `execution_tokens`
- Worker asíncrono con `asyncio.Queue` que flushea cada 500ms o 50 items (no bloquea el hot path)
- Write API: `start_run`, `record_step`, `record_tokens`, `end_run` — todos fire-and-forget
- Read API: `get_runs`, `get_run_steps`, `get_step_detail` — consulta directa a SQLite
- Cleanup: `enforce_retention()` borra runs > TTL o > max_runs

**Hook en `run_streaming()`:**
- Graba context_assembly, cada reason_node (con tokens), tool_node (con resultado), observe_node
- También graba fast path results (una línea directa)
- `end_run` marca éxito/duración

**REST API:**
- `GET /api/debug/runs?limit=50&offset=0` — lista de ejecuciones
- `GET /api/debug/runs/{run_id}/steps` — steps de una ejecución
- `GET /api/debug/steps/{step_id}` — step detail + tokens

**Frontend:**
- Full-screen overlay con 3 paneles: lista runs (izquierda), lista steps (centro), detalle step (derecha)
- Steps coloreados por tipo de nodo (indigo=context, amber=reason, red=tool, blue=observe, purple=update)
- Muestra: tool name + args, output, tool result, tokens reconstruidos, input preview
- Botón de engranaje (⚙) en el header para abrir/cerrar

---

## Fase 2: Reflection-Turn (135M sub-model) ✅ COMPLETADA

### Resumen de implementación

| Archivo | Tipo | Propósito |
|---------|------|-----------|
| `core/reflection/reflector.py` | Nuevo | `Reflector` class + `CritiqueResult` + heuristics + LLM critic prompt |
| `core/reflection/__init__.py` | Nuevo | Exporta `CritiqueResult`, `Reflector` |
| `core/agents/runtime.py` | Modificado | Hook en `run()` y `run_streaming()` después de `final_answer` |
| `main.py` | Modificado | Crea `Reflector` con provider opcional vía `CEREBRO_REFLECTION_MODEL_URL` |
| `tests/test_reflector.py` | Nuevo | 18 tests: heuristic, provider, runtime integration |

### Detalles de implementación

**Reflector (`reflector.py`):**
- `CritiqueResult`: score (0-10), issues list, needs_correction, corrected_answer, latency_ms
- **Heuristic checks** (siempre activos, sin modelo):
  - Detección de patrones problemáticos: "Lo siento", "como asistente de IA", training cutoff dates
  - 5 reglas de formato/factual/consistency/completeness
  - Penalización por severidad acumulada
- **LLM critique** (cuando `CEREBRO_REFLECTION_MODEL_URL` está configurado):
  - System prompt + query + context + answer → espera JSON con `{issues, score}`
  - Merge con issues heurísticos (deduplicados por tipo)
  - Timeout 5s, fallback graceful a heurística
- Stats internas: triggered/corrected/skipped

**Hook en AgentRuntime:**
- `run()`: después de `graph.ainvoke()`, llama `reflector.critique()`. Si necesita corrección, llama `_reflect_correction()` que añade un mensaje con los issues al historial y re-consulta al LLM. Máximo 1 reflexión.
- `run_streaming()`: misma lógica después del loop de streaming, antes de `StreamRunComplete`. La respuesta corregida va en el metadata.
- `_reflect_correction()`: reusa el chat provider principal con temperatura 0.1, parsea la respuesta como JSON o texto plano.

**Activación:**
- Por defecto: heuristics only (no necesita modelo externo)
- Opcional: `CEREBRO_REFLECTION_MODEL_URL=http://127.0.0.1:8082` para usar SmolLM2-135M/TinyLlama

---

## Fase 3: Desktop Recorder (AppleScript nativo) ✅ COMPLETADA

### Resumen de implementación

| Archivo | Tipo | Propósito |
|---------|------|-----------|
| `core/automation/recorder.py` | Nuevo | `ActionEvent` dataclass + `Recorder` con CGEventTap (vía pyobjc Quartz) + fallback graceful |
| `core/automation/workflow_store.py` | Nuevo | SQLite store para workflows: CRUD, search, run_count tracking |
| `core/automation/generalizer.py` | Nuevo | LLM-based event→AppleScript generalization + prompt |
| `core/automation/tools.py` | Nuevo | Tool handler factories: `start_recording`, `stop_recording`, `run_workflow` |
| `core/automation/__init__.py` | Nuevo | Exports |
| `core/tools/registry.py` | Modificado | `register_automation_tools()` registra 3 tools con RESTRICTED scope + confirmation |
| `main.py` | Modificado | Crea `Recorder` + `WorkflowStore` + registra automation tools |
| `ui/tray/server.py` | Modificado | `recorder`/`workflow_store` en AppState + `/api/workflows/*` CRUD + shutdown cleanup |
| `ui/tray/src/stores/workflows.ts` | Nuevo | Zustand store: loadAll, select, remove, execute |
| `ui/tray/src/components/automation/WorkflowPanel.tsx` | Nuevo | Full-screen panel: workflow list, detail view, run/delete |
| `ui/tray/src/layouts/Header.tsx` | Modificado | Botón activity icon para abrir WorkflowPanel |
| `ui/tray/src/api/types.ts` + `client.ts` | Modificado | `Workflow` type + API functions |
| `tests/test_automation.py` | Nuevo | 17 tests: ActionEvent, WorkflowStore CRUD, Recorder lifecycle, Generalizer |

### Detalles de implementación

**Recorder (`recorder.py`):**
- `ActionEvent`: timestamp, action_type (key_down, left_click, modifier, etc.), key_code, key_char, mouse_x/y, app_name, window_title
- `Recorder`:
  - Inicia thread con CFRunLoop + CGEventTap para capturar eventos en tiempo real
  - `start()` / `stop()` — thread-safe con lock
  - Captura: keyDown, leftMouseDown, rightMouseDown, flagsChanged
  - Obtiene app activa y título de ventana vía osascript (sin depender de pyobjc AppKit)
  - Fallback graceful cuando pyobjc no está instalado (eventos vacíos + log warning)
  - Requiere permisos Accessibility en System Settings

**WorkflowStore (`workflow_store.py`):**
- SQLite WAL mode, tabla `workflows` con índice por created_at
- Métodos: save, get, list_all, update, delete, search, increment_run_count
- Parámetros almacenados como JSON, tags como JSON array

**Generalizer (`generalizer.py`):**
- Convierte ActionEvent[] a log legible (ej: `[Terminal] key 'n'`)
- System prompt ~200 tokens que pide AppleScript + parámetros
- Timeout 15s, validación de JSON, captura de errores

**Tools:**
- `start_recording`: scope RESTRICTED, requires_confirmation=True
- `stop_recording`: scope RESTRICTED, llama al generalizer + guarda en store
- `run_workflow`: scope RESTRICTED, requires_confirmation=True, ejecuta via osascript
- Mínimo 3 eventos para generalizar

**API:**
- `GET /api/workflows` — lista
- `GET /api/workflows/{id}` — detalle
- `DELETE /api/workflows/{id}` — borrar
- `POST /api/workflows/{id}/run` — ejecutar

---

## Timeline estimado

| Fase | Archivos nuevos | Líneas (aprox) | Esfuerzo |
|------|----------------|----------------|----------|
| ~~Time-Travel Debugger~~ | ✅ **4 (PY+TS)** | **~450 backend + ~350 frontend** | **✅ COMPLETADA** |
| ~~Reflection-Turn~~ | ✅ **2 (PY)** | **~250 backend** | **✅ COMPLETADA** |
| ~~Desktop Recorder~~ | ✅ **7 (PY+TS)** | **~700 backend + ~250 frontend** | **✅ COMPLETADA** |

### Dependencias entre fases
- **Reflection-Turn** y **Desktop Recorder** son independientes — se pueden hacer en paralelo
- **Time-Travel Debugger** es prerequisito lógico para debuggear los otros dos
- Las tres son ortogonales a la arquitectura existente: no tocan código core del runtime más que añadiendo hooks pequeños

### Riesgos
- ~~**Recorder**: macOS sandboxing — la Accessibility API requiere permisos explícitos del usuario.~~ ✅ **Resuelto: CGEventTap retorna NULL sin permisos → log warning + fallback graceful. Mensaje claro al usuario.**
- ~~**Reflection**: SmolLM-135M puede ser demasiado básico para criticar bien.~~ ✅ **Resuelto: heuristics siempre activas + LLM opcional configurable vía CEREBRO_REFLECTION_MODEL_URL.**
- ~~**Debugger**: SQLite write en hot path del streaming puede añadir latencia.~~ ✅ **Resuelto con worker queue + batch writes cada 500ms.**
