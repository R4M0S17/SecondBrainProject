# Calendar Agent Fix Plan

## Root cause diagnosis

When the user types "what do I have tomorrow?" in Calendar mode and gets back
`{"action": "get_upcoming_events", "date": "tomorrow"}` as raw text, **four separate
bugs** are responsible. They must all be fixed for the calendar agent to work end-to-end.

---

## Bug 1 — Streaming path never executes tools ✅ DONE

**File:** `ui/tray/src/components/chat/InputArea.tsx`

When `activeAgent === "calendar"`, `send()` now calls `queryAgent()` (`POST /api/query`)
instead of `queryAgentStream()`. The full answer is replayed character-by-character at 10ms
intervals to preserve streaming UX. Tool-confirmation flow preserved on both paths.

---

## Bug 2 — LLM outputs wrong tool call format ✅ DONE

**Files changed:**
- `core/tools/registry.py` — added `parameters: dict[str, str]` field to `ToolDefinition`; added `handlers()` and `definitions()` methods to `ToolRegistry`; annotated both calendar tools with their arg signatures.
- `core/agents/runtime.py` — `_SYSTEM_TEMPLATE` now uses `{available_tools_detail}` block with name, signature, and description per tool; `_build_system_prompt` accepts `list[ToolDefinition]`; `AgentRuntime.__init__` takes optional `tool_definitions`; `_context_assembly_node` passes defs to prompt builder.
- `core/agents/specialized.py` — `make_calendar_profile()` instructions now include explicit `{"action": "tool", ...}` format examples for both tools.
- `main.py` — builds a `ToolRegistry` via `register_calendar_tools`, passes `.handlers()` and `.definitions()` to `AgentRuntime`.

---

## Bug 3 — Apple Calendar backend disabled by default

**File:** `core/tools/handlers/calendar.py`

`CalendarReader` constructor has `use_apple_calendar=False` by default.
The tool handlers only pass `ics_path`, so Apple Calendar is **never queried**.
On macOS, this is the actual source of truth for the user's events.

The `ICalBackend` reads `~/.cerebro/calendar.ics` which almost certainly does not exist
on the user's machine.

**Fix (Module CAL-3):**
In `core/tools/handlers/calendar.py`, change both `get_upcoming_events()` and
`query_events()` to instantiate `CalendarReader` with
`use_apple_calendar=platform.system() == "Darwin"`.
Keep the `ics_path` parameter for tests (so tests still pass with a fixture file).
When both backends are active, `CalendarReader` already deduplicates results.

---

## Bug 4 — No reminder creation capability

**File:** `core/tools/handlers/calendar.py`, `core/tools/registry.py`

The calendar agent can only **read** events. There is no tool to create a reminder or
schedule a notification. The user's original goal was natural language creation:
"notify me next Monday at 9am".

`AppleCalendarBackend` already uses `osascript` for reading — the same mechanism
can write events/reminders.

**Fix (Module CAL-4):**

Add a new JXA script template to `integrations/calendar_reader.py` for event creation:
```javascript
var app = Application("Calendar");
var cal = app.defaultCalendar();
var ev = app.CalendarEvent({
    summary: "{title}",
    startDate: new Date("{iso_start}"),
    endDate: new Date("{iso_end}"),
    description: "{description}"
});
cal.events.push(ev);
```

Add `create_calendar_event(title, datetime_str, duration_mins=60, description="")` to
`core/tools/handlers/calendar.py`. It should:
1. Parse `datetime_str` using `dateparser.parse()` — see CAL-7 for why `dateutil` is not enough.
2. Call the JXA script via `osascript`.
3. Return a confirmation string with the created event details.

Register it in `core/tools/registry.py` `register_calendar_tools()`:
```python
ToolDefinition(
    name="create_calendar_event",
    description="Create a timed event in Apple Calendar (use for meetings, appointments)",
    required_permission="tools.calendar.write",
    requires_confirmation=True,   # pauses for user approval before creating
    scope=ToolScope.LOCAL,
    audit_level=AuditLevel.FULL,
)
```

Add `"create_calendar_event"` to `CALENDAR_TOOLS` in `core/agents/specialized.py`.

---

## Gap 1 — "when is the next birthday" needs a long-range search

**Why the current plan is not enough:**

`query_events` defaults to `hours_ahead=168` (7 days). A birthday 2 months away is
~1440 hours ahead — it would never appear. The LLM could theoretically pass a large
`hours_ahead` if the tool signature is documented (CAL-2), but there are two extra problems:

1. Querying 8760 hours (1 year) of events via `cal.events()` in JXA iterates the entire
   calendar — on a large calendar this can timeout (the JXA call in `AppleCalendarBackend`
   already has a 10-second timeout).

2. Apple Calendar's **Birthdays** calendar (auto-generated from Contacts) is a special
   subscribed calendar. The current JXA template iterates `app.calendars()` then
   `cal.events()` — but on the Birthdays calendar `cal.events()` silently returns nothing
   in many macOS versions; birthdays are stored differently internally.

**Fix (Module CAL-5):**

A. Add a dedicated `search_upcoming(keyword, days_ahead=365)` tool to
   `core/tools/handlers/calendar.py` that:
   - Passes `hours_ahead = days_ahead * 24` to `CalendarReader.get_upcoming_events()`
   - Is clearly named for long-range semantic search, so the LLM picks it for
     "next birthday / next anniversary / next holiday" type queries.

B. Add a separate JXA path for **Birthdays** in `integrations/calendar_reader.py`.
   The Birthdays calendar requires querying via `Application("Contacts")` and converting
   birthdays to upcoming dates manually in JXA, not via `Application("Calendar")`.
   ```javascript
   var contacts = Application("Contacts");
   var people = contacts.people();
   var results = [];
   var now = new Date();
   people.forEach(function(p) {
       try {
           var bday = p.birthdate();
           if (!bday) return;
           var next = new Date(now.getFullYear(), bday.getMonth(), bday.getDate());
           if (next < now) next.setFullYear(next.getFullYear() + 1);
           results.push({ title: p.name() + "'s Birthday", start: next.toISOString() });
       } catch(e) {}
   });
   JSON.stringify(results);
   ```
   Add `BirthdayBackend` class to `integrations/calendar_reader.py` using this script.
   Enable it in `CalendarReader.__init__` alongside `AppleCalendarBackend` on macOS.

Register `search_upcoming` in `core/tools/registry.py` and add it to `CALENDAR_TOOLS`.

---

## Gap 2 — "add a reminder for next saturday" needs Apple Reminders support

**Why the current plan is not enough:**

CAL-4 adds `create_calendar_event` which writes to **Apple Calendar** (time-blocked events).
But when a user says "add a reminder", they mean the **Apple Reminders app** — a to-do
item with a due date, not a calendar event. These are two different Apple apps with
different JXA APIs.

**Fix (Module CAL-6):**

Add `add_reminder(title, datetime_str, notes="")` to `core/tools/handlers/calendar.py`.
Use a separate JXA template targeting `Application("Reminders")`:
```javascript
var app = Application("Reminders");
var list = app.defaultList();
list.reminders.push(app.Reminder({
    name: "{title}",
    dueDate: new Date("{iso_datetime}"),
    body: "{notes}"
}));
```

Register in `core/tools/registry.py`:
```python
ToolDefinition(
    name="add_reminder",
    description="Add a task/reminder to Apple Reminders app (use for to-dos, not meetings)",
    required_permission="tools.calendar.write",
    requires_confirmation=True,
    scope=ToolScope.LOCAL,
    audit_level=AuditLevel.FULL,
)
```

Add `"add_reminder"` to `CALENDAR_TOOLS` in `core/agents/specialized.py`.

Update the calendar profile instructions (`make_calendar_profile`) to distinguish:
- Use `add_reminder` for: "remind me to", "don't forget", "to-do", simple task with date
- Use `create_calendar_event` for: "schedule a meeting", "block time", "appointment"

---

## Gap 3 — Natural language dates: "next saturday" fails with dateutil

**Why the current plan is not enough:**

CAL-4 mentions using `dateutil.parser.parse()` for natural language dates. This is wrong.
`python-dateutil` (already installed) **cannot** parse relative phrases like:
- "next saturday"
- "next monday at 9am"
- "in 3 days"
- "this friday afternoon"

`dateutil.parser.parse("next saturday")` either raises `ParserError` or returns a wrong
date. The LLM will pass the user's exact phrase as the `datetime_str` argument, so this
will break.

**Fix (Module CAL-7):**

A. Add `dateparser>=1.1` to `pyproject.toml` dependencies. `dateparser` handles all the
   relative phrases above, locale-aware, and falls back gracefully.

B. In `core/tools/handlers/calendar.py`, use `dateparser.parse(datetime_str, settings={"PREFER_DATES_FROM": "future"})` for all date parsing in `create_calendar_event` and `add_reminder`.
   - `PREFER_DATES_FROM: future` ensures "saturday" picks the next upcoming Saturday, not last week's.
   - If `dateparser.parse()` returns `None` (completely unrecognizable input), return an error
     string asking the user to clarify the date.

---

## Module order (implement in sequence)

| # | Module | Effort | Status |
|---|--------|--------|--------|
| CAL-1 | Non-stream path for calendar agent in frontend | Small | ✅ Done |
| CAL-2 | Tool signature detail in system prompt | Small | ✅ Done |
| CAL-3 | Enable Apple Calendar + Contacts backends on macOS | Small | ✅ Done |
| CAL-4 | `create_calendar_event` tool (Calendar app) | Small | ✅ Done |
| CAL-5 | `search_upcoming` + `BirthdayBackend` | Medium | ✅ Done |
| CAL-6 | `add_reminder` tool (Reminders app) | Small | ✅ Done |
| CAL-7 | `dateparser` dependency + date parsing fix | Small | ✅ Done |

CAL-7 must be done before CAL-4 and CAL-6 (both depend on it).

---

## What will work after all modules are implemented

| User query | Tool used | Works? |
|---|---|---|
| "what do I have tomorrow?" | `get_upcoming_events(hours_ahead=24)` | ✅ |
| "do I have anything this week?" | `get_upcoming_events(hours_ahead=168)` | ✅ |
| "when is the next birthday?" | `search_upcoming(keyword="birthday", days_ahead=365)` + `BirthdayBackend` | ✅ |
| "add a reminder for next saturday" | `add_reminder(title=..., datetime_str="next saturday")` | ✅ |
| "schedule a meeting next monday at 3pm" | `create_calendar_event(...)` | ✅ |
| "do I have a dentist appointment?" | `search_upcoming(keyword="dentist")` | ✅ |

---

## Tests to add / update

- `tests/test_calendar.py`: add test for `get_upcoming_events` with
  `use_apple_calendar=False` (iCal file fixture). Add test for missing iCal file
  returns empty list gracefully. Add test for `BirthdayBackend` with mocked osascript.
- `tests/test_calendar_agent.py`: add test that `_parse_llm_response` correctly
  parses the updated format with tool signatures in the prompt.
- `tests/test_tools.py`: add tests for `create_calendar_event`, `add_reminder`,
  `search_upcoming` — all with mocked `osascript` subprocess calls.
- `tests/test_api.py`: add test that `POST /api/query` with `agent="calendar-v1"`
  and a mocked `get_upcoming_events` returns the tool result in the answer.

---

## Not in scope

- Google Calendar OAuth (deferred to v2.0 per spec).
- Recurring event creation.
- Removing the Calendar option from the agent dropdown (defer — test once fixes are in).
