# Agent Memory — Frontend & API

**Tab:** sidebar → **Memoria** / **Memory** (`psychology` icon)  
**Shortcut:** Dashboard stat card or header icon (opens the same tab)

## What this screen is for

Cerebro has two different “memory” concepts. The UI separates them on purpose:

| Section | User-facing name | Editable? | Meaning |
|---------|------------------|-----------|---------|
| **Saved memories** | Recuerdos guardados | **Yes** (+, edit, pin, delete) | Long-term facts in LanceDB (`agent_memory`) — persist across chats |
| **This chat's context** | Contexto de este chat | **No** (read-only) | Current session scratchpad: summary, working notes, short-term buffer |
| **Recall test** | ¿Qué recordaría Cerebro? | N/A | Preview which saved memories would match a query (no chat message sent) |

**Documents / Sources** = your files. **Memory tab** = what the agent learned about *you*.

## User actions

| Action | How |
|--------|-----|
| Add | **+ Añadir recuerdo** — text + save |
| Edit | Pencil icon on card → modal (content + comma-separated tags) |
| Pin | Pin icon — tag `pinned` in backend |
| Delete | Trash icon |
| Filter | Chips: All, Pinned, Session, Academic, Code |
| Empty state | “Try an example memory” pre-fills a sample |

Auto-generated memories (consolidation, archived chats) can be edited; UI shows an amber note that changes affect future recall.

## Architecture

```
LeftSidebar (memory tab)
    → MemoryView.tsx
        → MemoryViewContent.tsx
            → MemoryEpisodeCard + MemoryEpisodeEditor (modal)
            → MemoryRecallSearch
            → session panel (read-only)

Dashboard / Header
    → setTab("memory")   // primary entry
    → MemoryBrowserPanel (optional narrow slide-over, same MemoryViewContent)
```

## Files

| Path | Role |
|------|------|
| `ui/tray/src/components/memory/MemoryView.tsx` | Tab page shell |
| `ui/tray/src/components/memory/MemoryViewContent.tsx` | Shared layout + logic |
| `ui/tray/src/components/memory/MemoryEpisodeEditor.tsx` | Edit modal |
| `ui/tray/src/stores/memory.ts` | Zustand + API calls |
| `core/memory/long_term.py` | `store_episode`, `update_episode`, `delete_episode`, `search` |
| `ui/tray/server.py` | `/api/memory/*` |

## REST API

| Method | Route | Body / notes |
|--------|-------|----------------|
| `GET` | `/api/memory/episodes` | `?agent_id=&limit=` → `{ episodes, stats }` |
| `GET` | `/api/memory/session` | Session summary + working_memory |
| `POST` | `/api/memory/episodes` | `{ content, tags? }` |
| `PATCH` | `/api/memory/episodes/{id}` | `{ content?, tags?, pinned? }` — re-embeds vector on content change |
| `DELETE` | `/api/memory/episodes/{id}` | |
| `POST` | `/api/memory/recall` | `{ query }` → semantic search results |

Tests: `tests/test_memory_api.py`

## Operations note

After pulling memory API changes, **restart the backend** (`make run` or restart the desktop app). A stale process returns **404** on `/api/memory/*` and the UI shows a restart hint.

## Related

- Chat message badge **Memoria** = which episodes were used for *that* reply only (`MemoryPanel.tsx`)
- [`design.md`](design.md) — metadata badges in chat
