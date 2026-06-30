# Cerebro Frontend — Changelog

All UI/UX changes implemented during the redesign session.

---

## Agent Memory Browser (2026-06)

- **Memory tab** in left sidebar (`psychology`) — primary UX for saved memories + read-only session context.
- **Edit flow** — pencil on each card → modal; `PATCH /api/memory/episodes` with content/tags (re-embed).
- **`MemoryViewContent`** shared by tab + optional slide-over panel.
- Clearer copy: *Saved memories* vs *This chat's context*; empty state with example CTA.
- Backend: `LongTermStore.update_episode`, extended PATCH model.
- Tests: `tests/test_memory_api.py` (includes content edit).
- Docs: [`MEMORY_BROWSER.md`](MEMORY_BROWSER.md)

---

## Phase 0: Design Token Migration

### `tailwind.config.js` — Full palette swap
- Surfaces: matte black (`#131317`, `#0e0e12`, `#1b1b1f`, etc.)
- Primary: blue-600 (`#2563eb`) as `primary-container`, cyan (`#00dce6`) as accent
- Secondary: indigo (`#c0c1ff`), Tertiary: gold (`#e8c423`)
- Font: Inter (body) + JetBrains Mono (mono/label)
- Added fontSize tokens: `display-lg`, `headline-md`, `body-base`, `label-mono`
- Added borderRadius: `DEFAULT`, `lg`, `xl`, `full`
- Added spacing tokens: `unit`, `gutter`, `margin-desktop`, `panel-width`
- Removed `darkMode: "class"` (always dark)
- Kept `success-green: '#4ade80'` for semantic use

### `src/index.css` — CSS utilities added
- `.glass-panel` — backdrop-blur(16px) + semi-transparent bg + border
- `.glow-ring`, `.glow-ring-cyan`, `.glow-ring-indigo`, `.glow-ring-gold`
- `.input-glow:focus-within` — blue border + box-shadow on focus
- `.scrollbar-auto` — auto-hiding scrollbar (thin, transparent by default, visible on hover)
- Updated `custom-scrollbar` to new palette (`#3a494b` / `#849495`)
- `pulse-primary` animation (blue) replaces old `pulse-green`

### `index.html` — Font loading
- JetBrains Mono (500) replaces Space Grotesk
- Material Symbols Outlined (100..700 weight range) added via CDN

---

## Phase 1: Layout Restructuring

### `MainLayout.tsx` — New flex structure
```
Titlebar spacer (h-7, transparent, macOS traffic light area)
Header (h-12, logo + controls)
flex flex-1 overflow-hidden
├── LeftSidebar (48px, chat/fleet/tools/logs icons)
├── chat area (flex-1)
│   ├── AgentBar (agent selector + model display)
│   ├── ChatWindow
│   │   ├── messages (scrollbar-auto)
│   │   ├── FastPathToggles (Math/Calendar/Reminders/Web Search)
│   │   └── InputArea
│   └── ...
└── SystemSidebar (280-320px, collapsible)
StatusBar (minimal footer)
```
- Fullscreen detection via Tauri `isFullscreen()` — spacer hides in fullscreen
- Responsive padding: `px-4 md:px-6 lg:px-8`

### `StatusBar.tsx` — Simplified footer
- Text reduced to `text-[11px]` with 70% opacity
- Shows: "Cerebro OS • EngineIndicator" + "RAM X/XGB • Uptime —"
- Horizontal padding: `px-4 md:px-6`
- Vertical padding: `py-1`

### `SystemSidebar.tsx` — Collapsible right sidebar
- Collapse/expand toggle button (chevron_right/chevron_left) in top-right corner
- Collapsed state: thin 40px strip with expand button only
- `scrollbar-auto` class for dynamic scrollbar visibility

---

## Phase 2: Header Redesign

### `Header.tsx` — Compact header
- Height reduced to `h-12` (48px)
- `data-tauri-drag-region` for window dragging (replaces separate titlebar)
- Logo (`whitelogo.svg` with `invert brightness-0`) + "Cerebro" text
- Nav tabs removed (moved to LeftSidebar)
- Icons: Documents, Settings, History, Monitoring — all `p-1.5` with hover state
- ServiceControls hidden on mobile via `hidden md:flex`

### `ServiceControls.tsx` — Styled buttons
- Turn on: green (`bg-success-green/15 text-success-green border-success-green/30`)
- Turn off: red (`bg-error/15 text-error border-error/30`)
- Smaller: `px-3 py-1 text-xs`

---

## Phase 3: Fast-Path Toggles

### `FastPathToggles.tsx` — New component
- Pill buttons: Math, Calendar, Reminders, Web Search
- Calendar toggles activeAgent (`"auto"` ↔ `"calendar"`)
- Web Search toggles `tool_permissions.search_web` (deep-merge safe)
- Math/Reminders: visual indicators (backend-managed)
- Moved inside ChatWindow (between messages and InputArea)

---

## Phase 4: Chat Interface Restyling

### `MessageBubble.tsx` — New bubble design
- User messages: `max-w-[70%] bg-primary-container/15 border border-primary-container/25 rounded-2xl rounded-tr-sm` (blue tint to differentiate)
- Assistant messages: `smart_toy` avatar → replaced with `whitelogo.svg` logo
- Streaming cursor: `bg-primary-container animate-pulse`
- Code block sections with glass styling

### `InputArea.tsx` — Input redesign
- `input-glow` container with `bg-surface-container-low` + `rounded-xl`
- Material Symbols: `add` (file upload), `mic`, `send`/`close`
- Engine status footer below input
- Textarea: fixed `outline-none focus:outline-none` to remove double glow
- Auto-grow: dynamic height based on line count, starts at single line

### `ChatWindow.tsx` — Scrollbar & layout
- `scrollbar-auto` replaces `custom-scrollbar` (auto-hiding)
- Empty state uses `whitelogo.svg`
- WarningTosasts, SwapBanner, InputArea preserved

### `TypingIndicator.tsx` — Restyled
- Dots: `bg-primary-container`
- Text: `text-on-surface-variant`
- Progress bar: `bg-primary-container`

---

## Phase 5: System Sidebar Widgets

### `RamGaugeRing.tsx` — Collapsible SVG ring
- SVG circular progress ring with blue glow
- Header acts as toggle button: collapses to show only percentage text
- Chevron rotates 180° when expanded

### `CpuMiniGraph.tsx` — Placeholder bar chart
- Shows "—" for CPU (no API data available)
- 6 flat placeholder bars

### `StorageAccessButton.tsx` — Folder access card
- Shows file count or "Open Files"
- Wired to DocumentsPanel via `onOpen` callback

### `ActiveFleetList.tsx` — Model list
- Shows current active model (with blue pulse dot + glow)
- Shows available models from Settings (`llamaCppModels`), up to 5 + "+N more"

---

## Phase 6: Restyle All Existing Components

### Batch 1: Core UI
| File | Changes |
|------|---------|
| `App.tsx` | Old color tokens → new palette |
| `SettingsPanel.tsx` | Full restyle, `fixed z-[60]` positioning |
| `DocumentsPanel.tsx` | Full restyle, `fixed z-[60]` positioning |
| `ConfirmModal.tsx` | Redesigned: Material Symbols, better spacing, clearer buttons |
| `AgentSelectorDropdown.tsx` | Restyled to new tokens |

### Batch 2: Settings
| File | Changes |
|------|---------|
| `ModelSelector.tsx` | Token migration, indigo active state |
| `FleetSettings.tsx` | Token migration |
| `ToolPermissions.tsx` | Token migration |
| `FolderManager.tsx` | Token migration |
| `IndexProgress.tsx` | Token migration |
| `DndToggle.tsx` | Token migration |

### Batch 3: Chat sub-components
| File | Changes |
|------|---------|
| `MessageFooter.tsx` | `font-label-mono`, new palette |
| `SourcesPanel.tsx` | Monospace, cyan bars |
| `ToolHistoryPanel.tsx` | SVG → MaterialSymbols (check_circle, error) |
| `MemoryPanel.tsx` | Glass-styled snippets |
| `WarningToast.tsx` | Tertiary-gold palette |
| `CommandAutocomplete.tsx` | Glass dropdown |
| `HistoryPanel.tsx` | Token migration |

### Batch 4: Status
| File | Changes |
|------|---------|
| `EngineIndicator.tsx` | Blue dot for active (`bg-primary-container`), gray for off (`bg-outline`), green for OK, red for down |

### Batch 5: Wizard
| File | Changes |
|------|---------|
| `WizardShell.tsx` | Token migration, buttons use `primary-container` |
| `StepBackend.tsx` | Token migration |
| `StepLlamaCpp.tsx` | Token migration, `secondary` for skipped state |
| `StepModel.tsx` | Token migration |
| `StepFolders.tsx` | Token migration |
| `WizardDots.tsx` | Token migration |

### Batch 6: Overlays
| File | Changes |
|------|---------|
| `TimeTravelView.tsx` | Token migration |
| `WorkflowPanel.tsx` | Token migration |

### Removed orphaned components
- `RamGauge.tsx` (replaced by RamGaugeRing)
- `VramGauge.tsx` (replaced by RamGaugeRing)
- `FilesCounter.tsx` (replaced by StorageAccessButton)
- `FleetPanel.tsx` (replaced by ActiveFleetList)
- `ModelBadge.tsx` (orphaned)
- `LatencyBadge.tsx` (orphaned)

---

## Phase 7: Polish & Verification

- **Tauri window**: Width increased from 560px → 960px (`tauri.conf.json`)
- **`npx tsc --noEmit`**: 0 errors
- **`npm run build`**: 106 modules, 0 errors
- **`grep` for old tokens**: 0 remaining (intentional `#a78bfa` Claude purple kept)
- **`make test-stable`**: 152/153 pass (1 pre-existing calendar test failure)

---

## Post-Phase Changes (User Requests)

### AgentBar (`src/components/chat/AgentBar.tsx`) — NEW
- Agent selector dropdown above FastPathToggles
- 5 agents: Auto (router), General, Thesis, Code, Calendar
- Current model display on the right
- Shows `—` when engine is off, actual model name when running
- Each agent has unique color + Material Symbol icon

### LeftSidebar (`src/layouts/LeftSidebar.tsx`) — NEW
- 48px vertical icon bar on the left
- Icons: `chat` (Chat), `dns` (Fleet), `build` (Tools), `terminal` (Logs)
- Active tab highlighted with `primary-container`
- Replaces nav tabs from Header

### Panel mutual exclusion
- Opening Settings → closes Documents
- Opening Documents → closes Settings
- Handled via `handleOpenSettings` / `handleOpenDocuments` callbacks in MainLayout

### Panel z-index fix
- Both SettingsPanel & DocumentsPanel: `fixed inset-0 z-[60]` (above header's `z-50`)
- Close buttons no longer hidden behind header

### Logo rendering
- `whitelogo.svg` rendered with `invert brightness-0` CSS filter for white appearance
- Applied in: Header, MessageBubble avatar, ChatWindow empty state

### macOS traffic lights
- Transparent `h-7` spacer at top of MainLayout reserves space for window buttons
- Detects fullscreen via Tauri `isFullscreen()` + `onResized()` listener
- Spacer hidden in fullscreen mode to avoid dead space

### Responsive layout
- Removed `max-w-5xl mx-auto` constraint from chat area
- Fluid padding: `px-4 md:px-6 lg:px-8`
- Sidebar: `w-[280px] xl:w-panel-width` for better scaling

### Scrollbar
- `.scrollbar-auto` CSS class: thin, transparent by default, visible on hover/scroll
- Applied to: ChatWindow messages area, SystemSidebar

---

## File Inventory

### New files (9)
| File | Purpose |
|------|---------|
| `src/components/chat/FastPathToggles.tsx` | Pill toggle bar |
| `src/components/chat/AgentBar.tsx` | Agent selector + model display |
| `src/components/status/SystemSidebar.tsx` | Collapsible right sidebar |
| `src/components/status/RamGaugeRing.tsx` | Collapsible SVG ring |
| `src/components/status/CpuMiniGraph.tsx` | CPU placeholder chart |
| `src/components/status/StorageAccessButton.tsx` | Folder access card |
| `src/components/status/ActiveFleetList.tsx` | Active + available models |
| `src/layouts/LeftSidebar.tsx` | Left icon navigation bar |

### Modified files (~45)
- `tailwind.config.js`, `index.html`, `src/index.css`
- `src/App.tsx`
- `src/layouts/MainLayout.tsx`, `Header.tsx`
- `src/components/status/StatusBar.tsx`, `ServiceControls.tsx`, `EngineIndicator.tsx`
- `src/components/chat/ChatWindow.tsx`, `MessageBubble.tsx`, `InputArea.tsx`, `TypingIndicator.tsx`
- `src/components/chat/MessageFooter.tsx`, `SourcesPanel.tsx`, `ToolHistoryPanel.tsx`, `MemoryPanel.tsx`
- `src/components/chat/WarningToast.tsx`, `CommandAutocomplete.tsx`, `HistoryPanel.tsx`
- `src/components/settings/SettingsPanel.tsx`, `ModelSelector.tsx`, `FleetSettings.tsx`
- `src/components/settings/ToolPermissions.tsx`, `FolderManager.tsx`, `IndexProgress.tsx`, `DndToggle.tsx`
- `src/components/shared/ConfirmModal.tsx`, `AgentSelectorDropdown.tsx`
- `src/components/documents/DocumentsPanel.tsx`
- `src/components/wizard/WizardShell.tsx`, `StepBackend.tsx`, `StepLlamaCpp.tsx`
- `src/components/wizard/StepModel.tsx`, `StepFolders.tsx`, `WizardDots.tsx`
- `src/components/debug/TimeTravelView.tsx`
- `src/components/automation/WorkflowPanel.tsx`
- `src/stores/debug.ts`
- `src-tauri/tauri.conf.json`

### Removed files (6)
- `RamGauge.tsx`, `VramGauge.tsx`, `FilesCounter.tsx`, `FleetPanel.tsx`
- `ModelBadge.tsx`, `LatencyBadge.tsx`

---

## Phase 7: Dashboard UX Polish (2026-06-25)

### `DashboardHome.tsx` — Stats & action grid cleanup
- **Memories stat**: changed fallback from `"—"` to `0` — no more placeholder text, reads `0` when no data.
- **Events stat**: changed from hardcoded `"—"` to `0`. Displays cleanly even without backend data source.
- **Action grid**: added 4th card **Quick Note** (`edit_note` icon → Chat tab) to fill `grid-cols-2` layout — no more empty cell.
- **Subtitle**: changed from *"Your Intelligent Operating System"* → *"Your second brain, always on"* (warmer, more personal).
- All action descriptions moved to i18n keys.

### `ActionCard.tsx` — Disabled tooltip
- Added `disabledReason?: string` prop. When `disabled` is true, renders the `title` attribute on `<button>` so users see *why* (e.g. *"Index some files in Settings to enable search"*) on hover.

### `QuickChatCard.tsx` — Better CTA copy
- Description changed from *"Jump straight into a ChatGPT-style conversation"* → *"Ask anything about your notes, files, or projects"* (shifts focus from ChatGPT-emulation to personal knowledge).

### `ActivityList.tsx` — Actionable empty state
- Added `rocket_launch` icon above empty message.
- Added secondary hint text: *"Start a conversation or upload your first file to get going"* (gives user a clear next step instead of dead-end "No recent activity yet").

### `locales/en.json` & `locales/es.json` — New i18n keys
- Added: `dashboard.subtitle`, `dashboard.search_files_desc`, `dashboard.search_files_disabled_reason`, `dashboard.analyze_folder_desc`, `dashboard.create_workflow_desc`, `dashboard.quick_note`, `dashboard.quick_note_desc`, `dashboard.no_activity_hint`.
- Updated existing: `dashboard.subtitle`, `dashboard.quick_chat_desc`.

---

## Phase 9: Focus Mode Moved to Settings + Notifications Toggle (2026-06-25)

### `FastPathToggles.tsx` — Removed focus mode button from chat
- Removed `"focusmode"` entry from fast-path pills (was `visibility_off` icon toggling `focus_mode`).
- This feature is now a persistent setting, not a per-session toggle.

### `FocusModeToggle.tsx` (new) — Settings toggle for focus mode
- Controls `focus_mode` (skips ContextEnricher — no calendar events or recent files injected into agent prompts).
- Shows label + description so users know exactly what it does.

### `NotificationsToggle.tsx` (new, replaces `DndToggle.tsx`)
- Controls `dnd_enabled` for future proactive agent notifications.
- Shows "(coming soon)" hint in description.
- Old `DndToggle.tsx` deleted.

### `SettingsPanel.tsx` — Two new sections
- **Focus Mode** section (above Notifications) — `FocusModeToggle` component.
- **Notifications** section — `NotificationsToggle` component (replaces old DND section).
- Both use the same toggle layout pattern (`bg-surface-container` row with `ToggleSwitch`).

### `locales/en.json` & `locales/es.json` — New i18n keys
- Added: `settings.focus_mode`, `settings.focus_mode_desc`, `settings.notifications`, `settings.notifications_desc`.
- `settings.dnd` key preserved (still used by existing translations).

### Files removed
- `src/components/settings/DndToggle.tsx` — replaced by `NotificationsToggle.tsx`.

---

## Phase 8: Files Stat Clickable + Offline Cache (2026-06-25)

### `StatCard.tsx` — Clickable stat cards
- Added optional `onClick` prop. When provided, the card renders as interactive (hover state, `cursor-pointer`, `active:scale-[0.98]`, keyboard accessible with `role="button"` and `tabIndex`).
- Enables any stat card to navigate or trigger actions.

### `DashboardHome.tsx` — Files stat opens DocumentsPanel
- Added `onDocumentsOpen` prop passed down from `MainLayout`.
- Files stat card (`description` icon) now calls `onDocumentsOpen` when clicked, opening the DocumentsPanel overlay.
- New 4th action card **Quick Note** navigates to Chat tab.

### `MainLayout.tsx` — Wire DashboardHome docs handler
- Passes `handleOpenDocuments` as `onDocumentsOpen` to `<DashboardHome>`.

### `stores/dashboard.ts` — localStorage cache for file count
- Added `CACHE_KEY = "cerebro_dashboard_cache"`. On every successful API fetch, `indexed_files` is persisted to localStorage.
- On API failure (backend off), `FALLBACK_STATUS` reads the cached value instead of defaulting to `0`.
- Users now see the last known file count even when the backend is stopped.

---

---

## Dashboard — Buscar Archivos (búsqueda RAG)

- **`POST /api/documents/search`** con dos modos: `chunks` (solo fragmentos, sin motor) y `answer` (RAG completo con síntesis)
- **`core/tools/document_search.py`** — módulo puro de búsqueda vectorial, sin dependencias FastAPI/LLM
- **`SearchDocumentsDialog`** — diálogo modal en Home con input query, toggle modo, filtro por carpeta vigilada, resultados con snippets + score
- **Degradación elegante**: si motor apagado, modo `answer` devuelve 200 con `answer=null` + warning `engine_off`
- **`_engine_is_ok()`** helper reutiliza `provider_registry.get_chat().is_available()`
- **Deep dive en chat** via `utils/documentSearchPrompt.ts` — prompt enriquecido con fragmentos y fuentes
- **Activity tracking** en dashboard tras cada búsqueda
- **Discoverability**: `DocumentsPanel` con filtro por filename + botón "Búsqueda semántica"; `ToolsPanel` Quick Action "Search Files" cableado; atajo `Cmd+Shift+F` global
- La action card **Buscar Archivos** ya no navega al tab Sources — abre el diálogo directamente
- 27 keys i18n en `es.json` + `en.json` (namespace `search_docs.*`)
- Tests: `tests/test_document_search.py` (16 tests, unit + API)
- `make test-stable` → 173 pass, 0 regresiones

## Build Status

- TypeScript: `npx tsc --noEmit` → **0 errors**
- Production: `npm run build` → **106 modules, 0 errors**
- Backend tests: `make test-stable` → 173 pass
