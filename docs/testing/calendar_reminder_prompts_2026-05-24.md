# Pruebas manuales — prompts de recordatorio (2026-05-24)

Sesión de chat con **Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf**. Objetivo: crear un recordatorio mañana a las 3pm.

| Campo | Valor |
|--------|--------|
| Fecha | Domingo 24 de mayo de 2026 |
| Modelo | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Ruta esperada | `calendar_reminder_fast_path` → evento 30 min en **Calendario** (no app Recordatorios) |

**Estado:** documentado; **mejoras pendientes** (ver § Mejoras pendientes).

---

## Resultados

| # | Prompt | Respuesta | Latencia | Fast path | Resultado |
|---|--------|-----------|----------|-----------|-----------|
| 1 | `crea un recordatorio para mañana a las 3pm llamado "prueba1"` | No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta. | 23.8s | No | **Fallo** — fue al LLM; el orden de palabras no coincide con ningún patrón |
| 2 | `crea un recordatorio mañana a las 3pm con nombre "Reunión con Juan"` | No pude crear el recordatorio 'Reunión con Juan' en Calendario. Revisa permisos de Automatización para Calendar. | 0.2s | Sí | **Parcial** — parse OK; falló osascript / permisos macOS |
| 3 | `crea un recordatorio llamado Reunión con Juan para mañana a las 3pm` | No pude interpretar 'las 3pm' como fecha/hora. Prueba un formato como 'mañana a las 3pm' o '2026-05-20 15:00'. | 1.1s | Sí | **Fallo** — bug en regex: la fecha se corta en `las 3pm` (sin `mañana`) |

---

## Detalle por prueba

### 1 — Orden `para … llamado` (no soportado hoy)

**Prompt:** `crea un recordatorio para mañana a las 3pm llamado "prueba1"`

**Qué pasó:** No activó `calendar_reminder_fast_path`. El agente intentó interpretar JSON del modelo y falló (~24s).

**Por qué:** Los patrones en `core/agents/calendar_reminder_fast_path.py` exigen una de estas formas:

- `… recordatorio <cuándo> con nombre "<título>"`
- `… recordatorio llamado <título> para <cuándo>`
- `recuérdame <título> para <cuándo>`

No existe variante `recordatorio para <cuándo> llamado "<título>"`.

**Reformulación que sí debería usar fast path:**

```text
crea un recordatorio mañana a las 3pm con nombre "prueba1"
```

---

### 2 — Formato recomendado; permisos de Calendario

**Prompt:** `crea un recordatorio mañana a las 3pm con nombre "Reunión con Juan"`

**Qué pasó:** Fast path correcto (0.2s). `add_reminder` llamó a Calendario y AppleScript/JXA devolvió error.

**Por qué:** Falta (o está denegado) **Automatización → Calendario** para el proceso que ejecuta Cerebro (Terminal, Cursor, app Tauri, etc.).

**Qué hacer en macOS:**

1. Ajustes del Sistema → **Privacidad y seguridad** → **Automatización**
2. Buscar la app desde la que lanzas `make run` / el backend
3. Activar **Calendario** (no hace falta Recordatorios para esta ruta)

**Repetir la prueba #2** tras conceder permiso; debería responder algo como:

`Recordatorio 'Reunión con Juan' añadido al calendario para el …`

---

### 3 — `llamado … para mañana` — bug de parsing

**Prompt:** `crea un recordatorio llamado Reunión con Juan para mañana a las 3pm`

**Qué pasó:** Fast path activo, pero `dateparser` recibió solo `las 3pm` en lugar de `mañana a las 3pm`.

**Causa raíz (código):** En `_ADD_TITLE_WHEN_RE`, el separador entre título y fecha es:

```regex
(?:para|el|en|a)\s+
```

La alternativa suelta `a` hace match con el artículo **a** de `mañana **a** las 3pm`, partiendo el título en:

| Campo parseado | Valor erróneo |
|----------------|---------------|
| `title` | `Reunión con Juan para mañana` |
| `when` | `las 3pm` |

**Workaround hasta arreglar el regex:**

```text
crea un recordatorio mañana a las 3pm con nombre "Reunión con Juan"
```

o título sin la palabra `para` antes de la fecha:

```text
crea un recordatorio llamado Reunión con Juan el mañana a las 3pm
```

(mejor aún: usar la forma de la prueba #2).

---

## Prompts que funcionan hoy (referencia)

| Intención | Ejemplo |
|-----------|---------|
| Crear (recomendado) | `crea un recordatorio mañana a las 3pm con nombre "prueba1"` |
| Crear (recuérdame) | `recuérdame llamar al médico mañana a las 3pm` |
| Borrar | `borra el recordatorio prueba1` |

Verbos válidos al inicio: `crea`, `crear`, `agrega`, `añade`, etc.  
Palabra clave: `recordatorio`, `reminder` o `tarea`.

---

## Mejoras pendientes

- [ ] **P1 — Regex `_ADD_TITLE_WHEN_RE`:** sustituir `(?:para|el|en|a)` por delimitadores de palabra (`\bpara\b`, `\bel\b`, `\ben\b`, `\ba\b`) o exigir `para` como prefijo de frase de fecha, para no cortar en `mañana a las`.
- [ ] **P2 — Nuevo patrón:** `crea un recordatorio para <cuándo> llamado "<título>"` (orden de la prueba #1).
- [ ] **P3 — Permisos:** mensaje en UI o wizard si `add_reminder` falla por Automatización (enlace a Ajustes → Automatización → Calendario).
- [ ] **P4 — Tests:** añadir casos en `tests/test_calendar_fast_path.py` para prueba #1 (orden `para…llamado`) y #3 (título con `para` + `mañana a las`).
- [ ] **P5 — Documentación usuario:** una línea en ayuda del chat con el template recomendado.

---

## Archivos relacionados

| Archivo | Rol |
|---------|-----|
| `core/agents/calendar_reminder_fast_path.py` | Patrones regex y hook sin LLM |
| `core/tools/handlers/calendar.py` | `add_reminder` → evento en Calendario |
| `manual_tests/e2e/calendar_birthday_reminder_fix_2026-05-24.md` | Ronda anterior (fast path + cumpleaños) |
| `manual_tests/sessions/frontend_chat_qwen3_2026-05-24.md` | Contexto general de la sesión |

---

## Checklist de re-verificación

1. Conceder Automatización → Calendario al host de Python.
2. Repetir prueba #2; confirmar evento de 30 min mañana 15:00.
3. Tras fix P1, repetir prueba #3 sin error de `las 3pm`.
4. Tras fix P2, repetir prueba #1 sin error de interpretación del modelo.
