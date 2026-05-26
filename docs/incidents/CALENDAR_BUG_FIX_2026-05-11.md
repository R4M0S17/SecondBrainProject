# Calendar Agent Bug Fixes — 2026-05-11

Two bugs fixed in this session. Both were diagnosed by running the calendar tool
directly and inspecting the server routing logic.

---

## Bug 1 — JXA script always timed out (calendar returned zero events)

**Symptom:** The calendar agent responded that it could not retrieve events, even
when Apple Calendar had events. Tool call appeared to succeed but returned nothing.

**Root cause:** `integrations/calendar_reader.py` — `AppleCalendarBackend.get_upcoming_events()`
ran a JXA script that called `cal.events().forEach(...)` on every calendar. This fetched
ALL events (287 total across 9 calendars) into memory first, then filtered by date in
JavaScript. Wall-clock time: ~32 seconds. The Python `subprocess.run` timeout was 10 seconds,
so the process was always killed before returning results.

**Fixes:**

1. **`integrations/calendar_reader.py` — `_JXA_TEMPLATE`**: Replaced `cal.events().forEach(...)`
   with `cal.events.whose({_and: [{startDate: {_greaterThanEquals: now}}, {startDate: {_lessThanEquals: cutoff}}]})()`.
   The `whose()` call filters on the Calendar side and only returns matching events.
   Execution time dropped from ~32s to ~9s.

2. **`integrations/calendar_reader.py` — `AppleCalendarBackend.get_upcoming_events()`**:
   Raised `subprocess.run` timeout from `10` to `30` seconds as a safety margin.

---

## Bug 2 — Calendar agent gave terse date answers ("Today is Monday")

**Symptom:** Asking "what day is today?" to the calendar agent returned "Today is Monday"
while the same question to the general agent returned the full date with year, month and time.

**Root cause:** The server (`ui/tray/server.py`) chose between two execution paths:

- `runtime.stream()` — natural language streaming, no tools
- `runtime.run()` — LangGraph JSON tool loop, simulated streaming

The routing condition was:
```python
uses_confirmation_tools = bool(authorized_tools & {"write_file", "execute_python", "delete_file"})
```

The calendar agent had `write_file` in `CALENDAR_TOOLS` (left over from an earlier draft),
which triggered `uses_confirmation_tools = True` and forced it into `runtime.run()`. In `run()`
mode the model must respond in JSON format (`{"action": "answer", "answer": "..."}`), which
causes small models (Qwen 3 4B) to produce much shorter answers than they do in free-text mode.

The general agent has `authorized_tools = []` (no restriction), so `set([]) & {...} = {}`,
which evaluates to `False` and routes to `runtime.stream()` — natural language, full date.

The routing logic was also conceptually wrong: it was an accident that the calendar agent
ended up on the correct (tool-capable) path at all. Any tool-bearing agent that happened
not to have a confirmation-required tool would have silently lost tool calling.

**Fixes:**

1. **`ui/tray/server.py` — `query_stream_endpoint`**: Changed routing condition from
   `uses_confirmation_tools = bool(authorized_tools & CONFIRMATION_REQUIRED_TOOLS)` to
   `uses_tools = bool(authorized_tools)`. Any agent with a non-empty `authorized_tools`
   list uses `runtime.run()` (tool loop). Agents with an empty list (general agent) use
   `runtime.stream()` (natural language). This is the correct semantic.

2. **`core/agents/specialized.py` — `CALENDAR_TOOLS`**: Removed `write_file` and `read_file`.
   A calendar agent has no reason to read or write arbitrary files; its tools are
   `get_upcoming_events`, `query_events`, `search_upcoming`, `create_calendar_event`,
   `add_reminder`, and `search_documents`.

3. **`core/agents/specialized.py` — `make_calendar_profile` instructions**: Added explicit
   instruction: "When answering about dates or times, ALWAYS include the full day, month,
   year and time. Never respond with only the day name without year and month."

4. **`core/agents/runtime.py` — `_SYSTEM_TEMPLATE`**: Changed the answer format hint from
   `"<respuesta completa>"` to `"<respuesta completa y detallada en el idioma del usuario>"`
   to nudge small models toward fuller answers in JSON mode.

---

## Files changed

| File | Change |
|------|--------|
| `integrations/calendar_reader.py` | `whose()` filter in JXA; subprocess timeout 10s → 30s |
| `ui/tray/server.py` | Routing: `uses_confirmation_tools` → `uses_tools = bool(authorized_tools)` |
| `core/agents/specialized.py` | Removed `write_file`, `read_file` from `CALENDAR_TOOLS`; added full-date instruction |
| `core/agents/runtime.py` | More explicit answer format hint in `_SYSTEM_TEMPLATE` |

---

## Test result

```
tests/test_calendar.py       37 passed
tests/test_specialized.py    22 passed
tests/test_agent_runtime.py  12 passed
tests/test_agents.py          3 passed
Total: 80 passed, 0 failed
```
