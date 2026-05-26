# E2E — Fusión calendario → archivo (2026-05-25)

Exportar datos del calendario a un archivo de texto (`write_file`) sin que el chat solo imprima la agenda ni guarde la descripción literal del prompt.

| Campo | Valor |
|--------|--------|
| Estado | **DONE** |
| Prompt de referencia | `crea un archivo pruebacalendario.txt con contenido de los proximos 3 cumpleaños en mi calendario` |
| Carpeta escritura | `~/Desktop/CerebroFiles` |
| Tests auto | `tests/test_file_write_calendar_fusion.py` (8 tests) |
| Smoke live | `scripts/test_file_write_llamacpp.py` (incluye fusión general + calendar-v1) |

---

## Síntomas reportados (antes del fix)

| # | Síntoma | Causa |
|---|---------|--------|
| 1 | Solo imprime cumpleaños en chat, no crea archivo | Fast path calendario antes que escritura; agente Calendar sin `write_file` |
| 2 | `add_reminder` con error de fecha | `is_reminder_write_query` detectaba `crea` pero no `proximos` |
| 3 | Archivo creado con 42 bytes de texto literal | Fusión llamaba `try_calendar_fast_path`, que se auto-bloqueaba en export → cuerpo vacío → fallback literal |

---

## Cambios implementados

| Archivo | Rol |
|---------|-----|
| `core/agents/file_write_calendar_fusion.py` | **Nuevo** — detecta export calendario→archivo, llama `fetch_calendar_read_answer` |
| `core/agents/calendar_fast_path.py` | `fetch_calendar_read_answer()` (lectura sin bloqueo); `try_calendar_fast_path()` sigue bloqueando export en chat |
| `core/agents/runtime.py` | Orden: archivo (fusión) → recordatorios → calendario-chat; rechaza cuerpo literal si falla fusión |
| `core/agents/reminder_intent_resolver.py` | Excluye prompts de export; lectura `proximos` / `crea un archivo` |
| `core/agents/specialized.py` | `write_file` en `CALENDAR_TOOLS` |

**Warnings en metadata:** `file_write_calendar_fusion`, `file_write_fast_path`

**UI:** modal `write_file` con vista previa del listado de cumpleaños + nota “(Contenido obtenido del calendario.)”

---

## Verificación

### Automática

```bash
pytest tests/test_file_write_calendar_fusion.py tests/test_file_write_fast_path.py -q
make engine   # opcional para smoke live
.venv/bin/python scripts/test_file_write_llamacpp.py
```

### Manual (tray)

1. `make engine` + `make run` (reiniciar backend tras pull)
2. Agente **General**, **Calendar** o **Auto**
3. Prompt de referencia → **Aprobar** `write_file`
4. `cat ~/Desktop/CerebroFiles/pruebacalendario.txt` debe contener líneas `- Cumple …`, no solo la frase del prompt

### Resultado esperado en disco (extracto)

```text
Fecha y hora actual: Monday 25 de May de 2026, 13:43 EDT
Próximos eventos que coinciden con 'cumple' (mostrando 3 de 27; próximos 365 días):
- Cumple Ximena Palacios  a las 2026-06-02 04:00 UTC
- Cumple Marlene a las 2026-06-18 04:00 UTC
- Cumple J y L a las 2026-07-06 04:00 UTC
```

**Veredicto:** PASS (2026-05-25, backend local + Apple Calendar)

---

## Relacionado

- [`file_write_smart_e2e_2026-05-24.md`](file_write_smart_e2e_2026-05-24.md) — literal / spec LLM / fences
- [`file_write_fast_path_e2e_2026-05-24.md`](file_write_fast_path_e2e_2026-05-24.md) — confirmación `write_file`
- [`sessions/frontend_chat_qwen3_2026-05-24.md`](../sessions/frontend_chat_qwen3_2026-05-24.md) — índice de sesión
