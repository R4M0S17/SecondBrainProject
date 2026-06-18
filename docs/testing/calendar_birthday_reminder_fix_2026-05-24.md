# Resultados — cumpleaños acotados y recordatorios (2026-05-24)

Mejoras pedidas en `manual_tests/sessions/frontend_chat_qwen3_2026-05-24.md` (ítems 1 y 2).

| Campo | Valor |
|--------|--------|
| Fecha | Domingo 24 de mayo de 2026 |
| Modelo (sesión manual original) | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Verificación live | llama.cpp `:8080` + Cerebro `:7842` |
| Estado servidores al cerrar | **llama.cpp detenido** — puerto 8080 libre |

---

## Resumen

| Mejora | Estado | Notas |
|--------|--------|--------|
| Cumpleaños — máx. 3 o mismo día | **OK** | Fast path sin LLM; ya no lista ~27 eventos |
| “solo uno” en cumpleaños | **OK** | Una sola línea en la respuesta |
| Crear recordatorio (parse) | **OK** | `calendar_reminder_fast_path`; sin error de interpretación del modelo |
| Crear recordatorio (osascript) | **Actualizado** | Desde 2026-05-24 PM: va a **Calendario** (evento 30 min), no app Recordatorios |
| Borrar recordatorio | **Actualizado** | Borra evento por título en Calendario por defecto |

---

## Cambios en código

| Archivo | Cambio |
|---------|--------|
| `core/tools/handlers/calendar.py` | `limit_keyword_event_matches`, `max_results` en `search_upcoming`, `delete_reminder` |
| `core/agents/calendar_fast_path.py` | `_birthday_max_results()` (default 3, “solo uno” → 1) |
| `core/agents/calendar_reminder_fast_path.py` | **Nuevo** — crear/borrar recordatorio sin JSON del LLM |
| `core/agents/runtime.py` | Hook `calendar_reminder_fast_path` antes de lectura de calendario |
| `integrations/calendar_reader.py` | `delete_apple_calendar_event_by_title()` (ya no usa app Recordatorios) |
| `core/tools/registry.py` | Tool `delete_reminder` |
| `core/agents/specialized.py` | `delete_reminder` en `GENERAL_TOOLS` y `CALENDAR_TOOLS` |
| `tests/test_calendar_fast_path.py` | +6 tests (límite, solo uno, mismo día, recordatorio, runtime) |
| `tests/test_calendar.py` | +4 tests (límite, delete) |

---

## Pruebas automatizadas

Comando:

```bash
.venv/bin/python -m pytest tests/test_calendar_fast_path.py tests/test_calendar.py::test_limit_keyword_event_matches_caps_at_three tests/test_calendar.py::test_limit_keyword_event_matches_same_day_bundle tests/test_calendar.py::test_delete_reminder_success tests/test_calendar.py::test_delete_reminder_not_found -v --no-cov
```

**Resultado:** 17 passed, 0 failed.

Casos relevantes:

- `test_calendar_fast_path_birthday_caps_at_three` — muestra 3 de 8, texto “mostrando 3 de 8”.
- `test_calendar_fast_path_birthday_solo_uno` — exactamente 1 línea `- `.
- `test_calendar_fast_path_birthday_same_day_bundle` — dos cumpleaños el mismo día, sin listar el siguiente día.
- `test_calendar_reminder_fast_path_add` — parsea título y fecha del prompt en español.
- `test_runtime_reminder_fast_path_bypasses_llm` — no llama a `chat.complete`.

---

## Prueba live (API)

### Servicios

| Servicio | Comando | Puerto |
|----------|---------|--------|
| llama.cpp | `make engine` | 8080 |
| Cerebro | `CEREBRO_ICS="$(pwd)/manual_tests/fixtures/calendar_e2e.ics" CEREBRO_CALENDAR_APPLE=false .venv/bin/python main.py` | 7842 |

**Cierre:** proceso `llama-server` terminado; puerto **8080 libre**.

### 1 — Próximo cumpleaños (límite por defecto)

**Prompt:** `¿Cuál es mi próximo cumpleaños?`  
**Agent:** `general-v1`

**Warnings:** `ram_pressure_warn`, `calendar_fast_path`

**Respuesta:**

```text
Fecha y hora actual: Sunday 24 de May de 2026, 14:55 EDT
Próximo evento que coincide con 'cumple' (próximos 365 días):
- Ana cumpleaños a las 2026-06-23 16:21 UTC
```

**Resultado:** PASS — una sola entrada (fixture con un cumpleaños); no lista larga; sin LLM.

---

### 2 — “dime solo uno”

**Prompt:** `cual es el proximo cumpleaños en mi calendario? dime solo uno`  
**Agent:** `general-v1`

**Warnings:** `ram_pressure_warn`, `calendar_fast_path`

**Respuesta:**

```text
Fecha y hora actual: Sunday 24 de May de 2026, 14:55 EDT
Próximo evento que coincide con 'cumple' (próximos 365 días):
- Ana cumpleaños a las 2026-06-23 16:21 UTC
```

**Resultado:** PASS — encabezado “Próximo evento”; un solo ítem.

---

### 3 — Crear recordatorio

**Prompt:** `crea un recordatorio mañana a las 3pm con nombre pruebaCalendarioE2E`  
**Agent:** `general-v1`

**Warnings:** `ram_pressure_warn`, `calendar_reminder_fast_path`

**Respuesta:**

```text
Failed to add reminder 'pruebaCalendarioE2E'. Check that Reminders has Automation permission.
```

**Resultado (sesión anterior):** PASS (fast path / parse).  
**Nota:** Tras el cambio a Calendario, el mensaje de error pide permiso de **Calendar**, no Recordatorios.

---

## Comportamiento esperado en producción (calendario real)

Con Apple Calendar activo y muchos cumpleaños:

| Pregunta | Respuesta esperada |
|----------|-------------------|
| `¿Cuál es mi próximo cumpleaños?` | Hasta **3** próximos; si hay varios el **mismo día** que el primero, solo los de ese día |
| `… dime solo uno` | **1** cumpleaños |
| `lista todos los cumpleaños` (con “todos”) | Sin límite (comportamiento anterior) |
| `crea un recordatorio mañana a las 3pm con nombre "X"` | Confirmación vía mensaje de éxito o error de permisos |
| `borra el recordatorio X` | `Recordatorio 'X' eliminado` o `No encontré…` |

---

## Relacionado

- Sesión manual original: `manual_tests/sessions/frontend_chat_qwen3_2026-05-24.md`
- E2E calendario lectura (día anterior): `manual_tests/e2e/calendar_fast_path_e2e_2026-05-24.md`
