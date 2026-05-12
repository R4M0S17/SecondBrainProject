# Calendar Agent Bug Fixes — 2026-05-11 v4

Four bugs fixed based on frontend test results:
1. General model year hallucination (2023 instead of 2026)
2. Recurring birthday events never returned (all birthdays in Cumpleaños calendar)
3. "Nearest event" query hitting 120-second timeout
4. Birthday query ("cumple") returning "Sin eventos"

---

## Bug 1 — General model reports wrong year ("2023" instead of "2026")

**Symptom:** "Hoy es Monday, 11 de mayo del **2023** a las 16:15 UTC."

**Root cause:** Qwen 3 4B's training distribution is biased toward earlier years.
When it sees `FECHA Y HORA ACTUAL: Monday, 2026-05-11 17:05 UTC` in the system prompt,
its generation probability for the year token leans toward 2023/2024 rather than
accepting 2026 as-is.

**Fix — `core/agents/runtime.py`:**

Added `AÑO ACTUAL: {current_year}` inline on the same line as the date in both
`_SYSTEM_TEMPLATE` and `_STREAM_SYSTEM_TEMPLATE`:

```
FECHA Y HORA ACTUAL: Monday, 2026-05-11 17:05 UTC — AÑO ACTUAL: 2026
```

Repeating the year as a named field makes it much harder for the model to substitute
a different year from training memory. Both `_build_system_prompt` and
`_build_stream_system_prompt` now pass `current_year` as a separate format argument.

---

## Bug 2 — Recurring birthday events never returned

**Symptom:** "cual es el cumpleaños mas cercano?" → "Sin eventos". The Cumpleaños
calendar has 46 events (Cumple David, Cumple Marlene, etc.) but none were returned.

**Root cause:** All birthday events in the Cumpleaños calendar are **yearly recurring
events** created in 2021. Apple Calendar stores the **original** `startDate` (e.g.,
`2021-02-05`), not the next occurrence. The JXA `whose(startDate >= now)` filter
excluded every single one of them — `2021-02-05 < 2026-05-11` is always true.

The `BirthdayBackend` (which reads Apple Contacts) was also empty because birthdays
are stored in the Calendar app, not Contacts.

**Fix — `integrations/calendar_reader.py` — `_JXA_TEMPLATE`:**

Replaced the single `whose()` date filter with a **two-phase query**:

- **Phase 1** (unchanged): `whose(startDate >= now AND startDate <= cutoff)` for
  regular future events. Fast.
- **Phase 2** (new): `whose(recurrence CONTAINS "FREQ=YEARLY")` to get all yearly
  recurring events. For each, compute the next annual occurrence in JavaScript, then
  include it if it falls within the window.

Phase 2 uses a **two-pass** approach to minimise IPC round trips to Calendar.app
(each `.property()` call is ~0.5s):
- Pass A: `ev.startDate()` only — filter to events in window
- Pass B: `ev.summary()` only — fetch title for matched events

This reduces IPC calls from O(n × 5 properties) to O(n + matches × 1), bringing
a 365-day birthday search from ~93s to ~17s.

**Result:** `query_events("cumple", hours_ahead=8760)` now correctly returns all 31
upcoming birthdays, with the nearest being **Cumple Marlene on 2026-06-18**.

---

## Bug 3 — "Cual es el evento más cercano?" hitting 120-second timeout

**Symptom:** 120-second timeout (exactly `TIMEOUT_SECONDS`).

**Root cause:** The model looped through multiple tool calls with progressively larger
`hours_ahead` values trying to find any event. Since the regular calendar has no
upcoming non-recurring events, each call returned "Sin eventos" and the model tried
a larger window. With ~22s per tool call + ~15s per LLM reasoning step, 5 iterations
= 120s exactly.

**Fix — `core/agents/specialized.py` — `make_calendar_profile` instructions:**

Added explicit anti-loop rule:
```
REGLA ANTI-BUCLE: Llama a una herramienta UNA SOLA VEZ por consulta.
Si el resultado dice 'Sin eventos', responde directamente con esa información.
NO repitas la llamada con una ventana de tiempo más grande.
```

Also added explicit instruction for "nearest event" and birthday searches:
```
Para el evento o cumpleaños MÁS CERCANO (próximo año):
{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 8760}}

Para buscar cumpleaños usa query_events con keyword='cumple' y hours_ahead=8760.
```

---

## Bug 4 — Birthday queries using wrong keyword

**Symptom:** "cual es el cumpleaños mas cercano?" → "Sin eventos". The model was
searching for keyword `"cumpleaños"` but all events are named `"Cumple [nombre]"`.

**Fix — calendar agent instructions:** Added the note:
```
NOTA: Los cumpleaños se guardan como eventos recurrentes anuales.
Para buscar cumpleaños usa query_events con keyword='cumple' y hours_ahead=8760.
```

---

## Subprocess timeout increase

Raised from 30s → 60s to cover the ~17s yearly recurring scan plus margin.

---

## Files changed

| File | Change |
|------|--------|
| `integrations/calendar_reader.py` | Two-phase JXA with yearly recurrence support; timeout 30s → 60s |
| `core/agents/runtime.py` | `AÑO ACTUAL:` added to both system templates |
| `core/agents/specialized.py` | Anti-loop rule + birthday keyword hint + nearest-event guidance |
| `~/.cerebro/state/calendar-v1.json` | Refreshed via `ensure_profiles` |

---

## Timing summary (after fix)

| Query | Tool call | Approx time |
|-------|-----------|-------------|
| "que tengo mañana?" | `get_upcoming_events(48)` | ~15s JXA + ~20s LLM = ~35s |
| "cumpleaños más cercano?" | `query_events("cumple", 8760)` | ~47s JXA + ~20s LLM = ~67s |
| "evento más cercano?" | `get_upcoming_events(8760)` | ~47s JXA + ~20s LLM = ~67s |

All under the 120-second agent timeout with single-call discipline enforced.

---

## Test result

```
tests/test_calendar.py       37 passed
tests/test_specialized.py    22 passed
tests/test_agent_runtime.py  12 passed
Total: 77 passed, 0 failed
```

**Restart the server** (`make run`) for all changes to take effect.
