# Live E2E — Calendar fast path (2026-05-24)

Backend tests and live verification for birthday / upcoming calendar queries (Problem B from Qwen3 diagnosis).

---

## Code added

| File | Purpose |
|------|---------|
| `core/agents/calendar_fast_path.py` | Parse calendar/birthday prompts → run `get_upcoming_events` / `search_upcoming` without LLM JSON |
| `core/agents/runtime.py` | Hook after math fast path, before file-write fast path |
| `core/tools/handlers/calendar.py` | `CEREBRO_CALENDAR_APPLE=false` disables Apple Calendar osascript (ICS-only) |
| `tests/test_calendar_fast_path.py` | Unit + API tests with fixture `.ics` |
| `manual_tests/fixtures/calendar_e2e.ics` | Generated fixture for live runs |
| `manual_tests/fixtures/build_calendar_e2e_ics.py` | Regenerate fixture with relative dates |

**Automated tests:** `make test` → `tests/test_calendar_fast_path.py` (7 tests, ICS-only via test fixture).

---

## Services (live run)

| Service | Command | Port |
|---------|---------|------|
| llama.cpp | `make engine` | 8080 |
| Cerebro | `CEREBRO_ICS="$(pwd)/manual_tests/fixtures/calendar_e2e.ics" make run` | 7842 |

Both stopped after testing.

**Fixture events** (generated at run time):
- `E2E Team Meeting` — ~4 hours ahead
- `Ana cumpleaños` — ~30 days ahead

---

## Live test prompts

### 1 — Upcoming events (48h, general agent)

**Prompt:** `Lista eventos próximas 48 horas`  
**Agent:** `general-v1`

**Warnings:** `calendar_fast_path`, `ram_pressure_warn`

**Answer (excerpt):**
```text
Fecha y hora actual: Sunday 24 de May de 2026, 12:22 EDT
Eventos próximos (próximas 48h):
- E2E Team Meeting a las 2026-05-24 20:21 UTC
```

**Result:** PASS — no parse fallback; meeting listed.

---

### 2 — Birthday (general agent)

**Prompt:** `¿Hay algún cumpleaños próximo?`  
**Agent:** `general-v1`

**Answer (excerpt):**
```text
Eventos que coinciden con 'cumple' (próximos 365 días):
- Ana cumpleaños a las 2026-06-23 16:21 UTC
```

**Result:** PASS — `search_upcoming` via fast path.

---

### 3 — Calendar today (English, calendar agent)

**Prompt:** `What do I have on my calendar today?`  
**Agent:** `calendar-v1`

**Answer (excerpt):**
```text
Eventos próximos (próximas 24h):
- E2E Team Meeting a las 2026-05-24 20:21 UTC
```

**Result:** PASS

---

### 4 — Next event (Spanish, calendar agent)

**Prompt:** `¿Cuál es mi próximo evento?`  
**Agent:** `calendar-v1`

**Answer:** Same meeting in 24h window.  
**Result:** PASS

---

## Summary

| Test | Fast path | Parse fallback | Data from fixture |
|------|-----------|----------------|-------------------|
| 48h events | Yes | No | E2E Team Meeting |
| Birthday | Yes | No | Ana cumpleaños |
| EN today | Yes | No | E2E Team Meeting |
| Próximo evento | Yes | No | E2E Team Meeting |

**Latency note:** ~10 s per query on this Mac with Apple Calendar enabled — osascript timeout before ICS merge. For faster ICS-only reads set:

```bash
export CEREBRO_CALENDAR_APPLE=false
```

For real Apple Calendar + Contacts birthdays, grant **Automation** for Calendar/Contacts to Terminal or Cerebro in System Settings.

**ICS fallback:** export or sync to `~/.cerebro/calendar.ics` (`CEREBRO_ICS`) if Apple permissions are unavailable.

---

## Example prompts for tray chat

```text
Lista eventos próximas 48 horas
¿Hay algún cumpleaños próximo?
¿Qué tengo en el calendario?
¿Cuál es mi próximo evento?
```

Use agent **Calendar** or **General** (both have calendar read tools).

---

## Regenerate fixture

```bash
.venv/bin/python manual_tests/fixtures/build_calendar_e2e_ics.py
```

---

## Related

- [`diagnosis_frontend_chat_qwen3_2026-05-21.md`](../diagnoses/diagnosis_frontend_chat_qwen3_2026-05-21.md) — Problem B (parse fallback on calendar)
- [`file_write_fast_path_e2e_2026-05-24.md`](file_write_fast_path_e2e_2026-05-24.md) — File write E2E (same session)
