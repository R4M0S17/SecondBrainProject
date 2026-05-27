# Fast paths — orden, módulos y contratos

Referencia congelada del pipeline determinista en `AgentRuntime.run()` y `AgentRuntime.run_streaming()`.

**Regla de oro:** el **primer fast path que hace match gana**. No hay re-evaluación ni fallback al siguiente paso.

Plan de evolución: [`fast-path-evolution-plan.md`](fast-path-evolution-plan.md)  
Prompts que no deben romperse: [`stable-prompts.md`](stable-prompts.md)  
Cómo añadir uno nuevo: [`adding-a-fast-path.md`](adding-a-fast-path.md)

---

## Orden de evaluación (estable)

| # | Nombre | Módulo(s) | Entrada en runtime | LLM |
|---|--------|-----------|-------------------|-----|
| 1 | Math | `core/agents/math_fast_path.py` | `_try_math_fast_path` | No |
| 2 | File write | `file_write_fast_path.py`, `file_write_calendar_fusion.py`, `file_content_generator.py` | `_resolve_file_write_intent` | Solo si `content_source == spec` |
| 3 | Reminder intent | `reminder_intent_resolver.py` | `_try_reminder_llm_resolve` | Sí (llamada focalizada) |
| 4 | Calendar read | `calendar_fast_path.py`, `calendar_query_parse.py` | `_try_calendar_fast_path` | No |
| 5 | File search | `file_search_fast_path.py` | `_try_file_search_fast_path` | No |
| 6 | Agent loop | `runtime.py` (LangGraph) | `_graph.ainvoke` / reason node | Sí |

El mismo orden se repite en `run_streaming()` antes de entrar al nodo `reason_node`.

---

## Detalle por fast path

### 1. Math (`math_fast_path`)

| Campo | Valor |
|-------|--------|
| **Función** | `try_pure_math_fast_path(query, authorized_tools)` |
| **Herramientas** | `evaluate_math` (evaluación local; no invoca el tool registry en fast path) |
| **Match** | Expresión aritmética pura (`17 × 23`, `(2+3)*4`) |
| **Salida** | Respuesta directa (`answer` string) |
| **Warning** | `math_fast_path` |
| **Confirmación** | No |

---

### 2. File write (`file_write_*`)

Sub-pipeline interno en `_resolve_file_write_intent` (orden fijo):

1. **`try_file_write_calendar_fusion`** — cuerpo del archivo desde calendario.
2. **`try_file_write_fast_path`** — parse regex + clasificación de contenido.
3. Si `content_source == spec` → **`generate_file_content`** (LLM, una llamada).

| Campo | Valor |
|-------|--------|
| **Herramientas** | `write_file` (siempre vía `pending_tool`; requiere confirmación en UI) |
| **Rutas de escritura** | `CEREBRO_FILES_PATH` (default `~/Desktop/CerebroFiles`), `CEREBRO_AUTHORIZED_WRITE_PATHS` |
| **Salida** | `pending_tool_name=write_file`, preview en chat |
| **Warnings** | `file_write_fast_path`, `file_write_calendar_fusion`, `file_write_content_generated` |
| **Confirmación** | Sí — `POST /api/tool-confirm` |

**Clasificación de contenido** (`classify_file_content`):

| `content_source` | Significado | Acción |
|------------------|-------------|--------|
| `literal` | Texto final que el usuario dio | Escribir tal cual |
| `fenced` | Código en bloques ``` | Extraer y escribir |
| `spec` | Descripción (“receta de panqueques”, “tabla de verdad”) | LLM genera cuerpo → luego `write_file` |

**Fusión calendario → archivo:** cuando el prompt es “crea un archivo X con los próximos cumpleaños…”, gana **file write + fusion** (paso 2), no calendar read (paso 4).

---

### 3. Reminder intent (`reminder_intent_resolver`)

| Campo | Valor |
|-------|--------|
| **Función** | `resolve_reminder_intent` + opcional LLM extract |
| **Herramientas** | `add_reminder`, `delete_reminder` |
| **Match** | Crear/borrar recordatorio en calendario (evento corto) |
| **Salida** | `pending_tool` con título y `datetime_str` |
| **Warning** | `reminder_llm_intent` |
| **Confirmación** | Sí |

No confundir con **calendar read** (solo consulta) ni con **calendar fusion** (exportar cumpleaños a archivo).

---

### 4. Calendar read (`calendar_fast_path`)

| Campo | Valor |
|-------|--------|
| **Función** | `try_calendar_fast_path` → `fetch_calendar_read_answer` |
| **Herramientas** | `get_upcoming_events`, `search_upcoming`, `query_events` |
| **Match** | Preguntas de agenda sin intención de crear archivo |
| **Salida** | Respuesta directa en chat |
| **Warning** | `calendar_fast_path` |
| **Confirmación** | No |

Handlers reales: `core/tools/handlers/calendar.py` + `integrations/calendar_reader.py` (Apple Calendar / `.ics`).

---

### 5. File search (`file_search_fast_path`)

| Campo | Valor |
|-------|--------|
| **Función** | `try_file_search_fast_path` |
| **Herramientas** | `search_files` (ejecución directa en fast path, sin confirmación) |
| **Match** | “busca el archivo…”, “find files named…”, etc. |
| **Guard** | Rechaza queries con verbos de **escritura** (`crea`, `write`, `guarda`) |
| **Salida** | Respuesta directa con rutas encontradas |
| **Warning** | `file_search_fast_path` |
| **Confirmación** | No |

Raíces de búsqueda: `CEREBRO_AUTHORIZED_READ_PATHS` + `watched_folders` (merged en runtime).

---

### 6. Agent loop (fallback)

Si ningún fast path aplica:

- Construye system prompt con herramientas del agente.
- LLM responde JSON `{action: tool|answer, ...}` o texto en stream mode.
- Tools con `requires_confirmation=True` pausan igual que file write.

---

## Prioridad y conflictos conocidos

```text
"crea un archivo calendarioprueba.txt con los 2 proximos cumpleaños"
  → File write + calendar fusion (paso 2)
  ≠ Calendar read (paso 4)

"¿qué tengo en el calendario mañana?"
  → Calendar read (paso 4)

"busca el archivo demo.txt"
  → File search (paso 5)
  ≠ File write (paso 2) — file_search ignora verbos de creación

"crea un archivo demo.txt con hola"
  → File write (paso 2)
  ≠ File search — aunque contenga "archivo"
```

**Insertar un fast path nuevo antes del paso 2** puede robar prompts de creación de archivos. **Insertar después del paso 5** solo afecta lo que hoy cae al LLM.

---

## Espejo `core/` ↔ `cerebro/core/`

Existen dos copias del backend. Cambios en fast paths deben aplicarse en **ambas** rutas o solo en la que usa tu `main.py` activo — pero tests y PRs deben mantener paridad para no romper un arranque u otro.

---

## Metadata en respuestas

Los fast paths suelen añadir tags en `metadata.warnings` (vía `append_inference_warnings`):

| Warning | Fast path |
|---------|-----------|
| `math_fast_path` | Math |
| `file_write_fast_path` | File write (parse OK) |
| `file_write_calendar_fusion` | Calendario → archivo |
| `file_write_content_generated` | Spec → LLM generó cuerpo |
| `reminder_llm_intent` | Reminder |
| `calendar_fast_path` | Calendar read |
| `file_search_fast_path` | File search |

Útil para depurar desde el frontend (latencia ~0s suele indicar fast path, no loop LLM).

---

## Tests de regresión (por módulo)

| Módulo | Test file |
|--------|-----------|
| File write | `tests/test_file_write_fast_path.py` |
| Calendar fusion | `tests/test_file_write_calendar_fusion.py` |
| Calendar read | `tests/test_calendar_fast_path.py` |
| File search | `tests/test_file_search_fast_path.py` |
| Math | `tests/test_math_fast_path.py` |
| Reminder | `tests/test_reminder_intent_resolver.py` |

Suite estable (Fase 2 del plan): `make test-stable` — ver [`fast-path-evolution-plan.md`](fast-path-evolution-plan.md).

Live (con llama.cpp, manual): `scripts/test_file_write_llamacpp.py`, `scripts/test_file_search_llamacpp.py`.
