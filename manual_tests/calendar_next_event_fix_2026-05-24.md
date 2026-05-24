# E2E — Próximo evento en calendario (2026-05-24)

Corrección del ítem **Calendario — próximo evento general** en `manual_tests/frontend_chat_qwen3_2026-05-24.md`.

| Campo | Valor |
|--------|--------|
| Problema original | `Apple Calendar tardó demasiado en responder` (~68 s) |
| Causa raíz | Dos osascript lentos en serie (Apple Calendar + BirthdayChain) en cada `get_upcoming_events` |
| Solución | Fast path acotado, timeout corto, ICS primero, cumpleaños solo en `search_upcoming` |

---

## Cambios implementados

| Cambio | Detalle |
|--------|---------|
| Sin BirthdayChain en eventos generales | `get_upcoming_events` usa `include_birthday_backends=False` |
| Cumpleaños siguen en `search_upcoming` | `include_birthday_backends=True` solo ahí |
| Timeout rápido | `CEREBRO_CALENDAR_OSASCRIPT_FAST_TIMEOUT` default **12 s** (antes 35 s × 2) |
| Fallback ICS | Si Apple hace timeout pero hay `.ics`, se muestran eventos + nota |
| Respuesta “próximo evento” | `max_events=1`, ventana mínima **14 días**, encabezado dedicado |
| Patrones fast path | `cual es el proximo evento en el calendario`, `evento más cercano`, etc. |

---

## Pruebas automatizadas

```bash
.venv/bin/python -m pytest tests/test_calendar_fast_path.py tests/test_calendar.py::test_merge_returns_ics_when_apple_times_out tests/test_calendar.py::test_get_upcoming_events_next_event_single -q --no-cov
```

**Resultado:** passed.

---

## Prueba live (llama.cpp + backend)

| Servicio | Config | Puerto |
|----------|--------|--------|
| llama.cpp | `make engine` | 8080 |
| Cerebro | `CEREBRO_ICS=manual_tests/fixtures/calendar_e2e.ics` `CEREBRO_CALENDAR_APPLE=false` | 7842 |

**Estado final:** ambos servidores **detenidos**; puerto 8080 libre.

### 1 — `cual es el proximo evento en el calendario?`

**Latencia:** ~0.0 s (fast path, sin LLM)

**Warnings:** `calendar_fast_path`, `ram_pressure_warn`

**Respuesta:**

```text
Fecha y hora actual: Sunday 24 de May de 2026, 15:34 EDT
Próximo evento en tu calendario:
- E2E Team Meeting a las 2026-05-24 20:21 UTC
```

**Resultado:** PASS (un solo evento, no timeout)

### 2 — `¿Cuál es mi próximo evento?`

Misma respuesta y latencia. **PASS**

### 3 — `Lista eventos próximas 48 horas`

Lista normal (puede mostrar hasta 5 eventos). **PASS**

---

## Uso en producción (Apple Calendar real)

1. Conceder **Automatización → Calendar** a Python/Cerebro.
2. Opcional: exportar calendario a `~/.cerebro/calendar.ics` (`CEREBRO_ICS`) para fallback si Apple tarda.
3. Ajustar timeout: `CEREBRO_CALENDAR_OSASCRIPT_FAST_TIMEOUT=12` (default).

Si Apple no responde pero existe ICS, verás eventos con:

`(Apple Calendar no respondió a tiempo; se muestran eventos de otras fuentes.)`

---

## Relacionado

- `manual_tests/frontend_chat_qwen3_2026-05-24.md`
- `manual_tests/calendar_fast_path_e2e_2026-05-24.md`
