# Calendar Agent Bug Fixes — 2026-05-11 v2

Follow-up to `CALENDAR_BUG_FIX_2026-05-11.md`. Three additional bugs fixed after
confirming the calendar agent was still not working in the frontend.

---

## Bug 3 — Stale on-disk agent profile (most critical)

**Symptom:** Calendar agent responded with "get_upcoming_events is not available" or
gave inconsistent answers despite the tool being registered. The model lacked the
explicit JSON format examples needed by Qwen 3 4B to reliably call tools.

**Root cause:** `SpecializedAgentRouter.ensure_profiles()` only created agents that did
not yet exist on disk. It never updated existing profiles. The on-disk `calendar-v1.json`
was from 2026-05-07 and contained:
- `authorized_tools: ["read_file", "write_file", "search_documents", "get_upcoming_events", "query_events"]`
  — missing `search_upcoming`, `create_calendar_event`, and `add_reminder`
- Old instructions with no explicit `{"action": "tool", ...}` format examples

Every code change to `make_calendar_profile()` was therefore silently ignored at runtime.
Any agent profile change after the initial seed had no effect.

**Fix — `core/agents/specialized.py` — `ensure_profiles`:**

Method now compares the on-disk profile against the factory defaults on every startup.
If `authorized_tools` or `instructions` differ, it updates only those fields and saves,
preserving all session state (`session_summary`, `tool_trace`, `execution_count`, etc.).

```python
# Before — only seeds missing agents
if agent_id not in existing_ids:
    store.save(new_state)

# After — seeds missing agents AND refreshes stale profiles
if agent_id not in existing:
    store.save(new_state)
else:
    stale = (tools differ) or (instructions differ)
    if stale:
        state.profile.authorized_tools = canonical.authorized_tools
        state.profile.preferences["instructions"] = canonical.preferences["instructions"]
        store.save(state)
```

The disk profile was also updated immediately by running `ensure_profiles` outside the
server so the fix took effect without needing a cold start.

---

## Bug 4 — Tool return messages in English caused model hallucinations

**Symptom:** When the calendar was empty, the model sometimes said "the tool is not
available" or "I could not retrieve the results" instead of "no events found." This
happened because Qwen 3 4B received English strings like
`"No upcoming events in the next 24 hours."` and misinterpreted them as error states
rather than valid empty results.

**Root cause:** All return strings in `core/tools/handlers/calendar.py` were in English,
while the rest of the system (system prompt, instructions, model behavior) is in Spanish.

**Fix — `core/tools/handlers/calendar.py`:**

All return messages changed to Spanish:

| Before | After |
|--------|-------|
| `"No upcoming events in the next {n} hours."` | `"Sin eventos en las próximas {n} horas."` |
| `"Upcoming events (next {n}h):"` | `"Eventos próximos (próximas {n}h):"` |
| `"- {title} at {time}"` | `"- {title} a las {time}"` |
| `"No events found matching '{kw}' in the next {n} hours."` | `"Sin eventos que coincidan con '{kw}' en las próximas {n} horas."` |
| `"Events matching '{kw}':"` | `"Eventos que coinciden con '{kw}':"` |
| `"No events found matching '{kw}' in the next {n} days."` | `"Sin eventos que coincidan con '{kw}' en los próximos {n} días."` |
| `"Events matching '{kw}' (next {n} days):"` | `"Eventos que coinciden con '{kw}' (próximos {n} días):"` |

---

## Test fix — `tests/test_calendar.py`

`test_search_upcoming_returns_no_match_message` asserted `"No events found" in result`.
Updated to `"Sin eventos" in result` to match the new Spanish messages.

---

## Files changed

| File | Change |
|------|--------|
| `core/agents/specialized.py` | `ensure_profiles` now diffs and refreshes stale profiles on startup |
| `core/tools/handlers/calendar.py` | All return messages English → Spanish |
| `tests/test_calendar.py` | Updated English string assertion to Spanish |
| `~/.cerebro/state/calendar-v1.json` | Updated immediately (no restart needed) |

---

## Test result

```
tests/test_calendar.py       37 passed
tests/test_specialized.py    22 passed
tests/test_agent_runtime.py  12 passed
tests/test_agents.py          3 passed
Total: 80 passed, 0 failed
```

---

## Note on "no events found" responses

After these fixes the calendar agent correctly calls `get_upcoming_events` and returns
the tool result. If the agent reports no events for tomorrow, that is accurate — the
Apple Calendar on this machine has no events in the next 7 days. Events added on iPhone
or another device will only appear after iCloud syncs to the Mac's Calendar app.
