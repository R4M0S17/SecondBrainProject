# Calendar day-query fast path upgrade

This update improves the deterministic calendar fast path so day-specific asks are handled reliably and quickly, without relying on LLM tool-call JSON.

## What changed

### 1. Stronger date-anchor parsing (`core/agents/calendar_query_parse.py`)

- Added support for richer day expressions in Spanish/English:
  - Qualified weekdays: `próximo lunes`, `este viernes`, `next monday`, `this thursday`
  - Relative days: `mañana`, `pasado mañana`, `today`, `tomorrow`
  - Text dates: `14 de junio`, `14/06/2026`, `June 14, 2026`
  - ISO dates: `2026-06-14`
- Expanded `ON/AFTER/BEFORE` anchor extraction to cover these forms consistently.
- Added a fallback loose parser for natural phrases with calendar context, e.g.:
  - `en mi calendario para 2027-01-14`
- Added Spanish weekday normalization fallback to keep parsing robust when dateparser fails on qualified phrasing.

### 2. Dynamic query window for day-scoped requests (`core/agents/calendar_query_parse.py`, `core/tools/handlers/calendar.py`)

- Added `hours_window_for_filter(...)` to compute an effective `hours_ahead` based on parsed date scope.
- `get_upcoming_events_for_query(...)` now uses this computed window automatically.
- Result: queries for specific dates farther in the future are included correctly (instead of being cut by a fixed short window).

### 3. Better fast-path day-query detection (`core/agents/calendar_fast_path.py`)

- Calendar read routing now also checks parsed date anchors + calendar context.
- This allows day-specific phrasing to trigger fast path more consistently.

### 4. Apple Calendar speed improvement retained (`integrations/calendar_reader.py`)

- AppleScript upcoming fetch now constrains events between `now` and `cutoffDate` in-script.
- This avoids scanning unlimited future events and reduces timeout risk.

## Tests added/updated

### `tests/test_calendar_query_parse.py`

- Added coverage for:
  - `que tengo para mañana`
  - `que tengo el próximo lunes`
  - `eventos del 14 de junio`
  - loose contextual date phrase parsing
  - dynamic window growth for far dates

### `tests/test_calendar_fast_path.py`

- Added coverage for:
  - `que tengo el próximo lunes`
  - specific-date query beyond 30 days (ensures dynamic window works)
  - `que tengo para mañana` (existing fast-path day behavior)

### `tests/test_calendar_reader.py`

- Added template assertion ensuring AppleScript includes upper-bound cutoff logic.

## Validation run

- Calendar parser and fast-path tests:
  - `tests/test_calendar_query_parse.py`
  - `tests/test_calendar_fast_path.py`
- Result: all passing for the updated scope.
