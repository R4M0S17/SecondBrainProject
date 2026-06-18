# Recordatorios — fix cerebro + pruebas live (2026-05-24)

| Campo | Valor |
|--------|--------|
| Prompt probado | `crea un recordatorio para mañana a las 3pm llamado "prueba1"` |
| Modelo UI | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Motor | llama.cpp `:8080` |
| Backend probado | **`cerebro/`** (mismo que la app Tauri / `make run` en subcarpeta) |
| Servidores al cerrar | **Apagados** — 8080 y 7842 libres |

---

## Causa del fallo que seguías viendo

Tu error (`No pude interpretar…` · **~22.5 s**) encaja con el **agente LangGraph completo** (JSON de herramientas roto), **no** con la ruta rápida de recordatorios.

La corrección anterior solo estaba en `SecondBrain/core/`, pero el chat/desktop arranca el backend desde **`cerebro/`**, que tenía una copia antigua de `runtime.py`:

- Seguía usando `calendar_reminder_fast_path` (regex rígido).
- Ese regex **no** reconoce `…para mañana… llamado "prueba1"`.
- Caía al LLM principal → JSON inválido → fallback de interpretación (~22 s).

---

## Qué se hizo ahora

| Cambio | Detalle |
|--------|---------|
| **Sincronizado `cerebro/core/`** | `runtime.py`, `reminder_intent_resolver.py`, `llm_parse_utils.py`, `specialized.py` |
| **Ruta `reminder_llm_intent`** | LLM corto extrae `title` + `datetime_str` → modal de confirmación |
| **Fallback heurístico** | Si el LLM devuelve JSON malo, parsea la frase (`para … llamado …`) sin plantillas fijas |
| **Reparación JSON** | En el bucle principal: `"tool": add_reminder` → con comillas |

Archivos clave:

- `cerebro/core/agents/reminder_intent_resolver.py`
- `cerebro/core/agents/runtime.py`
- `cerebro/core/agents/llm_parse_utils.py`

---

## Pruebas live (cerebro + Qwen3-4B)

Comando: `bash scripts/live_reminder_test_cerebro.sh`  
Backend: `cd cerebro && .venv/bin/python main.py`  
Motor: `cd cerebro && make engine`

### `POST /api/query` (~8.2 s)

| Campo | Valor |
|--------|--------|
| Respuesta | Confirmación `add_reminder` — **prueba1**, **mañana a las 3pm** |
| Error interpretación | **No** |
| `warnings` | `["reminder_llm_intent"]` |
| `pending_tool` | `{"title":"prueba1","datetime_str":"mañana a las 3pm"}` |

### `POST /api/query/stream` (~3.5 s) — **ruta del chat UI**

| Campo | Valor |
|--------|--------|
| Tokens | Mismo texto de confirmación |
| `warnings` | `reminder_llm_intent` (+ `ram_pressure_critical` por RAM baja) |
| `pending_tool` | Igual que arriba |
| Error interpretación | **No** |

**Antes:** ~22.5 s + `No pude interpretar la respuesta del modelo`  
**Después:** ~3–8 s + modal de confirmación con título y fecha correctos

---

## Qué debes hacer en tu máquina

1. **Reiniciar el backend desde `cerebro/`** (no solo el repo raíz si usas la app):

   ```bash
   cd cerebro
   make engine          # terminal 1
   .venv/bin/python main.py   # terminal 2 — o make run si existe
   ```

2. Vuelve a probar el mismo prompt en el chat.

3. Deberías ver el **panel de confirmación** (no el error de interpretación). Al aprobar, se crea el evento en **Calendario** (permiso Automatización → Calendar).

Si aún ves el error, comprueba que el proceso en el puerto 7842 sea el de `cerebro/` (no un `main.py` viejo del directorio padre).

---

## Pruebas automatizadas

```bash
cd /Users/mb/Desktop/Javier/SecondBrain
.venv/bin/python -m pytest tests/test_reminder_intent_resolver.py -q --no-cov
```

Incluye `test_heuristic_parse_para_llamado` para la frase exacta del usuario.

---

## Resultados crudos

- `manual_tests/logs/_live_reminder_cerebro_results.jsonl`
