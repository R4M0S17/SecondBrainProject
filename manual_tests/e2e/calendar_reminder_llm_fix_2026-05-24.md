# Fix recordatorios vía LLM — resultados (2026-05-24)

| Campo | Valor |
|--------|--------|
| Fecha | Domingo 24 de mayo de 2026 |
| Motor | llama.cpp `http://127.0.0.1:8080` — `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Backend | Cerebro `http://127.0.0.1:7842` |
| Agente | `general-v1` |
| Servidores al cerrar | **Detenidos** — puertos 8080 y 7842 libres |

---

## Problema original

| Síntoma | Causa |
|---------|--------|
| `No pude interpretar la respuesta del modelo` | El modelo (Qwen3 4B) devolvía JSON inválido (`"tool": add_reminder` sin comillas) → `json.loads` fallaba |
| Frases “predeterminadas” obligatorias | El fast path por regex solo aceptaba 3 órdenes de palabras |
| `No pude interpretar 'las 3pm'` | Bug en regex `(?:para\|el\|en\|a)` que cortaba `mañana a las` |

---

## Cambios implementados

| Archivo | Cambio |
|---------|--------|
| `core/agents/llm_parse_utils.py` | **Nuevo** — reparación de JSON (identificadores sin comillas) |
| `core/agents/reminder_intent_resolver.py` | **Nuevo** — el LLM extrae `title` + `datetime_str` de lenguaje libre |
| `core/agents/runtime.py` | Reparación en `_parse_llm_response`; normalización de args; prompt extra para recordatorios; sustituye fast path regex por `reminder_llm_intent` |
| `core/agents/specialized.py` | Ejemplo `add_reminder` en agente calendario + guía en general |
| `tests/test_agent_runtime.py` | Tests de reparación JSON y aliases de args |
| `tests/test_reminder_intent_resolver.py` | **Nuevo** |
| `tests/test_calendar_fast_path.py` | Runtime test actualizado a flujo LLM |

**Eliminado del flujo activo:** `calendar_reminder_fast_path` (regex de frases fijas). El archivo sigue en el repo pero ya no se invoca desde `runtime.py`.

---

## Pruebas live (las 3 frases del usuario)

Comando: `bash scripts/live_reminder_test.sh`

| # | Prompt | Antes | Después (~7–8 s) | `warnings` |
|---|--------|-------|------------------|------------|
| 1 | `crea un recordatorio para mañana a las 3pm llamado "prueba1"` | Error interpretación modelo (23.8s) | Confirmación `add_reminder` — título **prueba1**, cuándo **mañana a las 3pm** | `reminder_llm_intent` |
| 2 | `crea un recordatorio mañana a las 3pm con nombre "Reunión con Juan"` | Permisos Calendario (fast path 0.2s) | Confirmación — **Reunión con Juan**, **mañana a las 3pm** | `reminder_llm_intent` |
| 3 | `crea un recordatorio llamado Reunión con Juan para mañana a las 3pm` | Error `las 3pm` (regex) | Confirmación — **Reunión con Juan**, **mañana a las 3pm** | `reminder_llm_intent` |

**Ninguna prueba devolvió** `No pude interpretar la respuesta del modelo`.

Ejemplo de `pending_tool` (prueba 1):

```json
{
  "name": "add_reminder",
  "args": {
    "title": "prueba1",
    "datetime_str": "mañana a las 3pm"
  }
}
```

Tras **aprobar** en el panel de confirmación, se ejecuta `add_reminder` en Calendario (requiere Automatización → **Calendar** en macOS).

---

## Cómo funciona ahora

1. **Detección amplia** (`is_reminder_write_query`): cualquier frase con *recordatorio*, *recuérdame*, *crear/agregar/borrar*, etc.
2. **Extracción LLM** (`extract_reminder_intent`): una llamada corta al modelo pide JSON `intent/title/datetime_str` sin plantillas de usuario.
3. **Confirmación** (`requires_confirmation`): la UI muestra el modal antes de escribir en Calendario.
4. **Agente principal** (si no entra el paso 2): prompt extra + reparación JSON + aliases (`nombre`→`title`, `fecha`→`datetime_str`) para cuando el grafo LangGraph elige la herramienta.

---

## Pruebas automatizadas

```bash
.venv/bin/python -m pytest \
  tests/test_agent_runtime.py \
  tests/test_reminder_intent_resolver.py \
  tests/test_calendar_fast_path.py::test_runtime_reminder_llm_intent_queues_confirmation \
  -q --no-cov
```

**Resultado:** 38 passed.

---

## Uso en el chat

Puedes redactar el recordatorio **como quieras**, por ejemplo:

- `crea un recordatorio para mañana a las 3pm llamado "prueba1"`
- `recuérdame comprar leche el martes a las 10`
- `pon un reminder called Team sync tomorrow at 3pm`

El sistema interpreta con el LLM y pide confirmación; ya no hace falta una frase exacta tipo plantilla.

---

## Relacionado

- `manual_tests/e2e/calendar_reminder_prompts_2026-05-24.md` — registro de fallos antes del fix
- `scripts/live_reminder_test.sh` — script E2E reproducible
