# Plan: Disable Auto-Launch of Calendar & Text Editor Apps to Save Resources

## Problem Statement

When you open the Cerebro frontend, the macOS Calendar and Notes (Text Editor) apps automatically launch and stay open in the background, consuming unnecessary system resources. These apps should remain closed and only be invoked when the user explicitly asks the agent to interact with them (e.g., "create a note" or "show my calendar events").

---

## Root Cause Analysis

The apps are being launched through multiple interaction points:

### 1. **Context Enricher (Primary Culprit)**
- **Location**: `core/agents/context_enricher.py`
- **What it does**: On EVERY query, if `CEREBRO_PROACTIVE_CONTEXT=true`, the ContextEnricher injects ambient context (upcoming calendar events, recent files) into the query before sending it to the agent
- **How it launches apps**: It calls `CalendarReader` which uses AppleScript (`osascript`) to query the Calendar app via `tell application "Calendar"` commands
- **Effect**: When osascript executes these Calendar commands, macOS automatically activates/opens the Calendar app (because the app must be running to respond to AppleScript queries)

### 2. **Tool Registration**
- **Location**: `core/tools/registry.py`, `core/tools/handlers/macos.py`
- **What happens**: The following tools are registered and available to the agent:
  - `create_note` (via `integrations/macos_apps.py`)
  - `search_notes` (via `integrations/macos_apps.py`)
  - `send_notification` (via `integrations/macos_apps.py`)
  - Calendar query functions (via `integrations/calendar_reader.py`)
- **Issue**: If these tools are being called during initialization or probing, they trigger app launches

### 3. **AppleScript Interaction Points**
- **Location**: `integrations/macos_apps.py`, `integrations/calendar_reader.py`
- **How they work**: These modules use `osascript` to communicate with macOS apps via JXA (JavaScript for Automation) or AppleScript
- **Side effect**: Running `osascript` commands that reference Calendar or Notes apps causes macOS to activate/open those apps if they're not already running

---

## Environment Configuration

Currently in `main.py` (line 84):
```
PROACTIVE_CONTEXT = os.getenv("CEREBRO_PROACTIVE_CONTEXT", "true").lower() == "true"
```

This is **set to `true` by default**, which means the context enricher is **always enabled** and **always querying the Calendar app on every query**.

---

## Fix Strategy (High-Level Steps)

### Phase 1: Disable Proactive Context Enrichment at Startup
**Goal**: Stop the context enricher from automatically calling Calendar and Notes on every query.

**What to do**:
1. Create a configuration flag that allows users to disable proactive context enrichment entirely OR set it to skip calendar/notes queries
2. Change the default value of `CEREBRO_PROACTIVE_CONTEXT` from `true` to `false`
3. Alternatively, add a new environment variable `CEREBRO_ENRICH_CALENDAR` and `CEREBRO_ENRICH_FILES` to control which context enrichment features are enabled
4. Update the `ContextEnricher` initialization in `main.py` to respect these flags

**Why this works**:
- The context enricher is responsible for proactively querying Calendar and Files every time a query is made
- By disabling it (especially for Calendar), the Calendar app will never be launched unless explicitly needed
- This has the side benefit of reducing latency on every query (no wait for calendar queries to timeout)

---

### Phase 2: Make Calendar & Notes Tools Lazy-Load
**Goal**: Only open Calendar/Notes when the user explicitly asks the agent to use them.

**What to do**:
1. In `core/tools/handlers/macos.py`, modify the handler functions to NOT execute AppleScript queries on initialization
2. In `core/tools/handlers/calendar.py`, wrap all calendar tool handlers to only execute when called, not during registration
3. Verify that calendar/notes tools are wrapped with the `ToolConfirmationPolicy` (in `core/tools/policy.py`) so users get confirmation before these apps are accessed
4. Add a "lazy initialization" pattern: first time a tool is called, it shows the user that the app is about to be opened and asks for confirmation (optional but recommended)

**Why this works**:
- Tools are currently available but only called when the agent decides to use them
- By ensuring they're lazy, we guarantee that Calendar/Notes apps are only opened when there's an actual user intent to interact with them
- This shifts from "always-on probing" to "on-demand invocation"

---

### Phase 3: Add Confirmation Gates for Sensitive App Access
**Goal**: Before opening Calendar or Notes, ask the user for permission.

**What to do**:
1. Check `core/tools/policy.py` to see which tools require confirmation
2. Add `create_note`, `search_notes`, and calendar query functions to the `CONFIRMATION_REQUIRED_TOOLS` list if they're not already there
3. This ensures that before the agent opens Notes or accesses Calendar, it pauses and shows a confirmation modal to the user
4. User can then approve or deny the action

**Why this works**:
- Gives users explicit control over when apps are accessed
- Prevents accidental or unnecessary app launches
- Builds trust and transparency into the system

---

### Phase 4: Test & Verify Resource Usage
**Goal**: Confirm that Calendar and Notes apps no longer auto-launch.

**What to do**:
1. Set the following environment variables:
   ```
   CEREBRO_PROACTIVE_CONTEXT=false
   CEREBRO_ENRICH_CALENDAR=false
   CEREBRO_ENRICH_FILES=true
   ```
2. Start the backend and frontend
3. Check running processes: `ps aux | grep -E "Calendar|Notes|TextEdit"`
4. Make several queries to the agent (ones that don't ask about calendar or notes)
5. Verify that Calendar and Notes apps do NOT appear in the process list
6. Open Activity Monitor and check memory usage before and after

**Then test that tools still work**:
1. Ask the agent: "Create a note with title 'Test' and content 'Hello'"
2. Ask the agent: "What events do I have today?"
3. Verify that the agent can still perform these tasks (but only when explicitly asked)

---

## Detailed Implementation Checklist

### Step 1: Update Environment Defaults
- [ ] Open `main.py`
- [ ] Find line 84: `PROACTIVE_CONTEXT = os.getenv("CEREBRO_PROACTIVE_CONTEXT", "true")`
- [ ] Change `"true"` to `"false"` 
- [ ] Add new env variables for granular control:
  - `CEREBRO_ENRICH_CALENDAR` (default: false)
  - `CEREBRO_ENRICH_FILES` (default: true)
  - `CEREBRO_ENRICH_NOTES` (default: false)
- [ ] Update `.env.example` to document these new variables

### Step 2: Update Context Enricher
- [ ] Open `core/agents/context_enricher.py`
- [ ] Modify the `__init__` method to accept individual feature flags for calendar, files, and notes
- [ ] Modify the `enrich()` method to check these flags before calling calendar/notes queries
- [ ] Ensure that when calendar enrichment is disabled, no calendar functions are called

### Step 3: Update Tool Registry & Handlers
- [ ] Open `core/tools/handlers/macos.py` and `core/tools/handlers/calendar.py`
- [ ] Verify that tool handlers don't execute any app-launching code on import or registration
- [ ] Add docstrings noting that these tools will trigger app launches (for transparency)
- [ ] Ensure handlers are wrapped with proper error handling

### Step 4: Verify Policy Configuration
- [ ] Open `core/tools/policy.py`
- [ ] Check if `create_note`, `search_notes`, and calendar functions are in `CONFIRMATION_REQUIRED_TOOLS`
- [ ] If not, add them
- [ ] This ensures users are asked before Calendar/Notes access

### Step 5: Update Configuration Files
- [ ] Open `.env.example`
- [ ] Add the new environment variables with explanations:
  ```
  # Proactive Context Enrichment (disabled by default to save resources)
  CEREBRO_PROACTIVE_CONTEXT=false
  
  # Granular enrichment control
  CEREBRO_ENRICH_CALENDAR=false    # Set true to include upcoming events in every query (opens Calendar app)
  CEREBRO_ENRICH_FILES=true        # Set true to include recent files in every query
  CEREBRO_ENRICH_NOTES=false       # Set true to include notes context (opens Notes app)
  ```

### Step 6: Document the Change
- [ ] Create/update a document explaining:
  - Why proactive context is disabled by default
  - How to re-enable it if the user wants proactive calendar/notes context
  - Trade-off: proactive context is convenient but costs resources and latency
  - Users can still use calendar/notes by explicitly asking the agent

### Step 7: Test
- [ ] Start backend with `CEREBRO_PROACTIVE_CONTEXT=false`
- [ ] Open frontend
- [ ] Verify Calendar and Notes do not appear in running processes
- [ ] Make 5+ queries that don't mention calendar/notes
- [ ] Then ask: "Show me today's events" and verify it works
- [ ] Ask: "Create a note called 'Test'" and verify it works
- [ ] Check that confirmation dialogs appear before app access

### Step 8: Cleanup & Optimization (Optional Future Work)
- [ ] Consider caching calendar queries (don't re-fetch events every query)
- [ ] Consider running calendar queries asynchronously in a separate thread pool
- [ ] Document this as a performance optimization opportunity

---

## Expected Results After Implementation

✅ **Calendar app does NOT auto-launch** when you open Cerebro frontend  
✅ **Notes app does NOT auto-launch** when you open Cerebro frontend  
✅ **Reduced resource usage** - no unnecessary app processes running in background  
✅ **Faster query response times** - no waiting for calendar queries to timeout  
✅ **Explicit permission model** - apps only open when user asks the agent to interact with them  
✅ **Tools still work** - agent can still create notes and query calendar on demand  

---

## Rollback / Re-enable Instructions

If the user wants to re-enable proactive calendar context enrichment (sacrifice resources for convenience):

```bash
# In .env file or as env var:
export CEREBRO_PROACTIVE_CONTEXT=true
export CEREBRO_ENRICH_CALENDAR=true

# Then restart Cerebro
```

Then Calendar app will be queried on every query and will auto-open.

---

## Alternative Approaches (Not Recommended)

### Option A: Keep apps open but minimize to tray
- **Downside**: Apps still consume resources, just not visible
- **Not ideal**

### Option B: Close apps after each query
- **Downside**: Expensive operation, slow, unreliable
- **Not ideal**

### Option C: Use a separate daemon/service to provide calendar data
- **Upside**: Decouples app launching from context enrichment
- **Downside**: Complex, requires refactoring calendar_reader.py
- **Future enhancement**

---

## Summary

The fix is straightforward:
1. **Disable proactive context enrichment by default** - change one line in `main.py`
2. **Verify tool policy** - ensure calendar/notes tools require confirmation
3. **Update documentation** - explain the trade-off and how to re-enable if desired
4. **Test thoroughly** - verify apps don't launch and tools still work on-demand

This will save resources without sacrificing functionality, because users can still interact with Calendar and Notes by asking the agent directly.
