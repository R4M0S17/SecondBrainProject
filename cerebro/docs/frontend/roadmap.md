# Cerebro — Frontend Development Roadmap
## Step-by-Step Modular Build Plan

> **Companion to:** `FRONTEND_DESIGN.md`
> **Backend base URL:** `http://localhost:7842`
> **Stack:** Tauri 2.0 · React 18 · TypeScript · Tailwind CSS · Zustand · Vite

Each module is self-contained and produces a working deliverable. Complete them in order — later modules depend on earlier ones.

---

## Dependency Graph

```
M0 (Scaffolding)
  └─ M1 (API Layer)
       ├─ M2 (Onboarding Wizard)
       ├─ M3 (Status Bar)          ← can be built in parallel with M2
       └─ M4 (Chat Core)
            ├─ M5 (Metadata Panels)
            ├─ M6 (Agent Selector)
            └─ M7 (Settings Panel)
                 └─ M8 (Confirmation Modal)
                      └─ M9 (Polish & Accessibility)
                           └─ M10 (Window Chrome & Draggability)
```

---

## Module 0 — Project Scaffolding ✅
**Goal:** Working Tauri + React + TypeScript skeleton that opens a window and shows "Cerebro" in white text on a dark background.

### Commands

```bash
# From cerebro/ui/tray/
npm install
npm run tauri dev
```

### Files created

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: react 18, zustand, lucide-react, @tauri-apps/api v2, @tauri-apps/plugin-dialog, @tauri-apps/plugin-shell |
| `vite.config.ts` | Vite + @vitejs/plugin-react, devServer port 1420 |
| `tsconfig.json` | ES2021, bundler resolution, strict mode |
| `postcss.config.js` | tailwindcss + autoprefixer |
| `tailwind.config.js` | Full Material Design 3 dark token palette (see below) |
| `index.html` | Google Fonts: Inter + Space Grotesk |
| `src/main.tsx` | ReactDOM.createRoot mounting `<App />` |
| `src/index.css` | Tailwind directives + custom-scrollbar + typing-dot + status-dot-pulse animations |
| `src-tauri/tauri.conf.json` | Window 560×680, decorations: true, titleBarStyle: Overlay, alwaysOnTop: true |
| `src-tauri/Cargo.toml` | tauri 2, tauri-plugin-shell, tauri-plugin-dialog, tauri-plugin-global-shortcut |
| `src-tauri/src/main.rs` | Cmd+Shift+Space toggle, blur-to-hide |

### Design token palette (`tailwind.config.js`)

```js
colors: {
  // Base levels (darkest → lightest)
  "bg-base":                  "#0f1117",   // deepest background
  "surface-container-lowest": "#0e0d15",
  "surface-container-low":    "#1c1b23",
  "surface-container":        "#201f27",
  "surface-container-high":   "#2a2932",
  "surface-container-highest":"#35343d",
  "surface":                  "#13121b",
  "bg-surface":               "#1a1d27",
  "bg-elevated":              "#242736",   // borders everywhere
  "background":               "#13121b",

  // Text
  "on-surface":               "#e5e0ed",
  "on-surface-variant":       "#c9c4d7",
  "text-primary":             "#e8eaf0",
  "text-secondary":           "#8b8fa8",
  "accent-gray":              "#8b8fa8",

  // Brand / interactive
  "primary":                  "#7c6af7",   // accent purple
  "inverse-primary":          "#5a46d3",
  "primary-container":        "#8e7fff",
  "on-primary":               "#2b009e",
  "secondary-container":      "#444652",
  "on-secondary-container":   "#b2b4c2",
  "outline":                  "#928ea0",
  "outline-variant":          "#242736",

  // Semantic
  "success-green":            "#4ade80",
  "tertiary":                 "#ffb86d",
  "error":                    "#ffb4ab",
  "error-container":          "#93000a",
  "amber":                    "#fbbf24",
}
```

Typography:
- UI text: **Inter** (`font-body`)
- Code/mono: **Space Grotesk** (`font-mono`)

### `src-tauri/src/main.rs` responsibilities

1. Register global shortcut `Cmd+Shift+Space` → toggle window `visible`.
2. On `WindowEvent::Focused(false)` → `window.hide()`.
3. Plugins: `tauri_plugin_shell`, `tauri_plugin_dialog`, `tauri_plugin_global_shortcut`.

### Acceptance criteria

- `npm run tauri dev` opens the window.
- `Cmd+Shift+Space` toggles the window.
- Window is frameless, 560×680, always on top.
- Clicking outside the window hides it.

---

## Module 1 — API Layer & Types ✅
**Goal:** Typed TypeScript client for every backend endpoint. No UI. Every future component imports from here — nothing calls `fetch` directly.

### Files created

```
src/api/
  types.ts      ← TypeScript interfaces for all data models
  client.ts     ← async functions, one per endpoint
  errors.ts     ← ApiError class
```

### `src/api/types.ts` — complete type definitions

```typescript
export interface SourceRef {
  path: string;
  score: number;
  snippet?: string;
}

export interface ToolCallRecord {
  name: string;
  duration_ms: number;
  success: boolean;
  args?: Record<string, unknown>;
  result?: string;
}

export interface MemoryRef {
  content: string;
  score: number;
  created_at?: string;
}

export interface ResponseMetadata {
  model: string;
  duration_s: number;
  sources: SourceRef[];
  tools: ToolCallRecord[];
  memory: MemoryRef[];
  warning?: string;           // single warning string, not an array
}

export interface QueryRequest {
  query: string;
  agent?: string;
  conversation_id?: string;
}

export interface QueryResponse {
  answer: string;
  metadata: ResponseMetadata;
  conversation_id: string;
}

export interface IndexResponse {
  status: "started" | "running" | "done" | "error";
  files_indexed?: number;
  message?: string;
}

export interface StatusResponse {
  ollama_ok: boolean;
  model: string;
  files_indexed: number;
  ram_used_gb: number;
  ram_total_gb: number;       // total RAM (not available)
  p95_latency_s: number;      // in seconds (not ms)
  total_queries: number;
  embedding_model?: string;
}

export interface WizardStatus {
  is_first_launch: boolean;
  ollama_running: boolean;
  model_pulled: boolean;
  folders_configured: boolean;
}

export interface AppConfig {
  model: string;
  watched_folders: string[];
  tool_permissions: {
    execute_python: boolean;
    write_file: boolean;
    read_file: boolean;
    search_web: boolean;
  };
  dnd_enabled: boolean;
  embedding_model: string;
}

export type AgentId = "general" | "thesis" | "code" | "calendar";

export interface Agent {
  id: AgentId;
  label: string;
  description: string;
}

export const AGENTS: Agent[] = [
  { id: "general",  label: "General",  description: "All-purpose assistant" },
  { id: "thesis",   label: "Thesis",   description: "Academic writing & research" },
  { id: "code",     label: "Code",     description: "Programming & debugging" },
  { id: "calendar", label: "Calendar", description: "Schedule & tasks" },
];
```

### `src/api/errors.ts`

```typescript
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
  }
}
```

### `src/api/client.ts` — full function list

All endpoints are prefixed with `/api/`. A shared `request<T>()` helper handles fetch, JSON parsing, and `ApiError` throwing.

```typescript
const BASE = "http://localhost:7842";

// POST /api/query
export async function queryAgent(req: QueryRequest, signal?: AbortSignal): Promise<QueryResponse>

// GET /api/status
export async function getStatus(): Promise<StatusResponse>

// POST /api/index
export async function startIndex(): Promise<IndexResponse>

// GET /api/index/status
export async function getIndexStatus(): Promise<IndexResponse>

// GET /api/config
export async function getConfig(): Promise<AppConfig>

// PATCH /api/config  (not PUT)
export async function updateConfig(patch: Partial<AppConfig>): Promise<AppConfig>

// GET /api/wizard/status
export async function getWizardStatus(): Promise<WizardStatus>

// GET /api/wizard/check-ollama → { running: boolean }
export async function wizardCheckOllama(): Promise<{ running: boolean }>

// POST /api/wizard/pull-models → returns ReadableStream for streaming log
export async function wizardPullModels(signal?: AbortSignal): Promise<ReadableStream<Uint8Array> | null>

// POST /api/wizard/set-folders
export async function wizardSetFolders(folders: string[]): Promise<{ ok: boolean }>

// POST /api/wizard/complete
export async function wizardComplete(): Promise<{ ok: boolean }>
```

### Acceptance criteria

- Each function can be called from the browser console during `tauri dev`.
- `getStatus()` returns a correctly-typed object when the Python backend is running.
- Calling any function when the backend is down throws `ApiError`.
- No component file imports `fetch` directly.

---

## Module 2 — Onboarding Wizard ✅
**Goal:** Three-step first-launch setup flow. After completion the user lands in the main chat window.

### Files created

```
src/components/wizard/
  WizardShell.tsx    ← outer layout: centered card, step indicator, title
  StepOllama.tsx     ← step 1: polls /api/wizard/check-ollama every 2s
  StepModel.tsx      ← step 2: streams /api/wizard/pull-models
  StepFolders.tsx    ← step 3: native folder picker + path list
  WizardDots.tsx     ← 3-dot progress indicator
src/stores/wizard.ts ← Zustand: currentStep, isComplete, advance, complete, reset
```

### Wizard store (`src/stores/wizard.ts`)

```typescript
interface WizardState {
  currentStep: 0 | 1 | 2;
  isComplete: boolean;
  advance: () => void;   // increments step, or sets isComplete on step 2
  complete: () => void;  // directly marks complete (used by App.tsx)
  reset: () => void;
}
```

### `WizardShell.tsx` layout

```
┌────────────────────────────────────────────────┐  bg-[#0f1117] full screen
│                                                │
│  ┌──────────────────────────────────────────┐  │  w-[440px] bg-[#1a1d27]
│  │  🧠  Cerebro                              │  │  border border-[#242736]
│  │      Your private AI second brain        │  │  rounded-xl p-[40px_36px]
│  │                                           │  │
│  │  ● ─── ○ ─── ○   Step 1 of 3 · Start…   │  │
│  │                                           │  │
│  │  [ Step component renders here ]          │  │
│  │                                           │  │
│  │  [ Continue →  ]  (disabled until ready) │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### `StepOllama.tsx` behavior

1. On mount, start polling `wizardCheckOllama()` every 2 seconds.
2. Three states: `null` (checking, spinner), `true` (running, green pulse dot + "Detected" badge), `false` (not found, red dot + instructions).
3. When `running=false`: shows `ollama serve` command hint in a code span.
4. On `running=true`: stops polling, enables Continue. `onReady(true)` callback.
5. Continue advances to step 2.

### `StepModel.tsx` behavior

1. On mount: call `wizardPullModels()`, which returns a `ReadableStream`.
2. Pump the stream into a scrolling terminal log area (`font-mono`, `bg-[#0e0d15]`, auto-scrolls to bottom).
3. Show elapsed time via a `useEffect` timer.
4. Show a "Cancel" link that calls `AbortController.abort()`.
5. On success (stream closes): `onReady(true)`.
6. On error: show error detail + "Retry" button.

### `StepFolders.tsx` behavior

1. "Add Folder" button invokes `@tauri-apps/plugin-dialog` `open({ directory: true, multiple: true })`.
2. Each path shown as a row with `×` remove button.
3. At least 1 path required to enable Continue.
4. On Continue: `WizardShell` calls `wizardSetFolders(paths)` then `wizardComplete()`, then `advance()`.

### `App.tsx` routing logic

```tsx
// On mount: call getWizardStatus()
// if (!is_first_launch) → complete()   ← skip wizard
// else show <WizardShell />
// In both cases: startPolling() + loadSettings()
```

### Acceptance criteria

- First launch: wizard appears, not chat window.
- Step 1 auto-detects Ollama; Continue is disabled until it's running.
- Step 2 streams the model pull log.
- Step 3 opens a real OS folder picker.
- After step 3: chat window appears; wizard never shows again.

---

## Module 3 — Status Bar ✅
**Goal:** Persistent health dashboard at the bottom of every screen. Polls `/api/status` every 10 seconds. Shows five live indicators.

### Files created

```
src/components/status/
  StatusBar.tsx         ← outer bar, flex row of all indicators
  OllamaIndicator.tsx   ← colored dot + "Ollama OK" label
  RamGauge.tsx          ← RAM reading with color thresholds
  LatencyBadge.tsx      ← p95 in seconds with color thresholds
  FilesCounter.tsx      ← indexed_files count, click-to-reindex
src/stores/system.ts    ← Zustand: StatusResponse + polling
```

### System store (`src/stores/system.ts`)

```typescript
interface SystemState {
  status: StatusResponse | null;
  lastRefreshed: number | null;    // Date.now() timestamp
  error: string | null;
  pollingInterval: ReturnType<typeof setInterval> | null;

  refresh: () => Promise<void>;
  startPolling: (intervalMs?: number) => void;  // default 10000ms, idempotent
  stopPolling: () => void;
}
```

`startPolling` is idempotent — safe to call from both `App.tsx` and `StatusBar.tsx`.

### `StatusBar.tsx` layout

```
● OLLAMA OK  ·  phi3:mini  ·  142 files  |  RAM 3.8/8 GB  ·  p95 8.4s  ·  47 queries
```

Full-width `h-[28px]`, `bg-[#1c1b23]`, `border-t border-[#242736]`, `font-mono text-[10px] uppercase tracking-wider text-[#c9c4d7]`.

### Color rules per indicator

| Indicator | Normal | Warning | Critical |
|-----------|--------|---------|----------|
| Ollama | `text-[#4ade80]` (green) | — | `text-[#ffb4ab]` (red) when `ollama_ok=false` |
| RAM | `text-[#c9c4d7]` | `text-amber-400` (> 4 GB) | `text-[#ffb4ab]` (> 5.5 GB) |
| p95 latency | `text-[#c9c4d7]` | `text-amber-400` (> 12s) | `text-[#ffb4ab]` (> 18s) |

> **Note:** `p95_latency_s` is in **seconds** (not ms). Thresholds are 12s / 18s.

### Acceptance criteria

- Status bar visible at all times (wizard and chat).
- All five indicators update every 10 seconds without page flicker.
- Ollama dot changes color within one poll interval of the daemon going down.

---

## Module 4 — Chat Window Core ✅
**Goal:** Working chat interface. User types a message, presses Enter, sees a response.

### Files created

```
src/components/chat/
  ChatWindow.tsx       ← scrollable history + input area + warning toasts + confirm modal
  MessageBubble.tsx    ← renders one message (user or assistant)
  InputArea.tsx        ← textarea + send/cancel button + command autocomplete
  TypingIndicator.tsx  ← three pulsing dots while loading
src/stores/chat.ts     ← Zustand: messages, isLoading, activeAgent, pendingConfirmation
src/layouts/
  MainLayout.tsx       ← Header + ChatWindow (flex-1 min-h-0) + StatusBar + lazy SettingsPanel
  Header.tsx           ← AgentSelectorDropdown + settings icon + close icon
```

### Chat store (`src/stores/chat.ts`)

```typescript
export interface Message {
  id: string;                    // `${Date.now()}-${random}`
  role: "user" | "assistant";
  content: string;
  metadata?: ResponseMetadata;
  timestamp: number;             // Date.now()
  expandedPanel?: "sources" | "tools" | "memory" | null;
}

export interface PendingConfirmation {
  toolName: string;
  toolPath?: string;
  toolAction?: string;
  toolSize?: string;
  warningText?: string;
  onApprove: () => void;         // callbacks stored directly in confirmation
  onDeny: () => void;
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  abortController: AbortController | null;
  activeAgent: AgentId;
  pendingConfirmation: PendingConfirmation | null;

  addMessage: (msg: Omit<Message, "id" | "timestamp">) => string;  // returns new id
  updateMessage: (id: string, patch: Partial<Message>) => void;
  setLoading: (loading: boolean) => void;
  setActiveAgent: (agent: AgentId) => void;
  cancelRequest: () => void;
  setAbortController: (ctrl: AbortController | null) => void;
  toggleMessagePanel: (id: string, panel: "sources" | "tools" | "memory") => void;
  setPendingConfirmation: (conf: PendingConfirmation | null) => void;
  clearMessages: () => void;
}
```

### `ChatWindow.tsx` layout

```tsx
<div className="flex flex-col flex-1 min-h-0">
  <main className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6 bg-[#0e0d15]">
    {/* empty state SVG when messages.length === 0 */}
    {messages.map(m => <MessageBubble key={m.id} message={m} />)}
    {isLoading && <TypingIndicator model={activeModel} />}
    <div ref={bottomRef} />
  </main>
  {/* WarningToast strip above input when warnings present */}
  <InputArea />
  {pendingConfirmation && <ConfirmModal ... />}
</div>
```

Auto-scroll: `useEffect` on `[messages, isLoading]` → `bottomRef.current?.scrollIntoView({ behavior: "smooth" })`.

### `MessageBubble.tsx`

```tsx
// User messages — right-aligned pill
<div className="flex justify-end" role="article" aria-label="Your message">
  <div className="bg-[#444652] text-[#e8eaf0] px-4 py-2 rounded-full max-w-[85%] text-[14px]">
    {content}
  </div>
</div>

// Assistant messages — left-aligned plain text
<div className="space-y-3" role="article" aria-label="Assistant message">
  <p className="text-[14px] text-[#e5e0ed] whitespace-pre-wrap">{content}</p>
  {metadata && <MessageFooter messageId={id} metadata={metadata} expandedPanel={expandedPanel} />}
  {/* expandedPanel === "sources" → <SourcesPanel> etc. */}
</div>
```

### `InputArea.tsx` behavior

- `<textarea>` auto-grows up to 88px (≈ 4 lines), then scrolls.
- `Enter` → send; `Shift+Enter` → newline; `Escape` → cancel if loading, else blur.
- While loading: textarea `disabled`, Send button becomes Stop (square icon), calls `cancelRequest()`.
- On send: `addMessage({ role: "user", ... })`, `setLoading(true)`, `setAbortController(ctrl)`, call `queryAgent({ query, agent: activeAgent }, ctrl.signal)`.
- Query is sent as-is — agent is passed via the `agent` field of `QueryRequest`, not via `/academic` prefix.
- Shows `<CommandAutocomplete>` when input starts with `/`.

### `MainLayout.tsx`

```tsx
// SettingsPanel is lazy-loaded
const SettingsPanel = lazy(() => import("../components/settings/SettingsPanel"));

<div className="flex flex-col w-[560px] h-[680px] bg-[#0f1117] overflow-hidden">
  <Header />
  <ChatWindow className="flex-1 min-h-0" />
  <StatusBar />
  {isOpen && <Suspense fallback={null}><SettingsPanel /></Suspense>}
</div>
```

### Acceptance criteria

- Type a question, press Enter → assistant response appears.
- Cancel button aborts the in-flight request.
- Auto-scroll keeps latest message visible.
- Typing indicator shows exactly while `isLoading=true`.
- Multiple back-and-forth exchanges work correctly.

---

## Module 5 — Metadata Panels ✅
**Goal:** Every assistant message shows a footer with badge buttons for sources, tools, and memory. Clicking a badge toggles an inline detail panel.

### Files created / modified

```
src/components/chat/
  MessageFooter.tsx     ← badges row: model · duration · SOURCES · TOOL · MEMORY
  SourcesPanel.tsx      ← collapsible: list of SourceRef with score bars
  ToolHistoryPanel.tsx  ← collapsible: list of ToolCallRecord
  MemoryPanel.tsx       ← collapsible: list of MemoryRef with score bars
  WarningToast.tsx      ← amber banner shown when metadata.warning is non-empty
```

### `MessageFooter.tsx`

```tsx
// Only rendered for assistant messages with metadata
<div className="flex items-center gap-2 mt-3">
  <span className="font-mono text-[12px] text-[#c9c4d7] opacity-60">
    {metadata.model} · {metadata.duration_s.toFixed(1)}s
  </span>
  <div className="flex gap-1">
    {/* Badge buttons: active state has border-[#7c6af7] text-[#7c6af7] */}
    {sources.length > 0 && <button onClick={() => togglePanel(id, "sources")}>{sources.length} SOURCES</button>}
    {tools.length > 0   && <button onClick={() => togglePanel(id, "tools")}>{tools.length} TOOL</button>}
    {memory.length > 0  && <button onClick={() => togglePanel(id, "memory")}>{memory.length} MEMORY</button>}
  </div>
</div>
```

Badge styling: `text-[10px] font-bold tracking-[0.05em] uppercase px-2 py-[2px] bg-[#201f27] border border-[#242736] rounded-sm`.

### `SourcesPanel.tsx`

Left-border-2 `border-[#7c6af7]` panel (`bg-[#1c1b23]`). Each source row: file path (truncated) + horizontal score bar (width = `score * 100%`, `bg-[#7c6af7]`) + score number.

### `ToolHistoryPanel.tsx`

Bordered panel (`bg-[#1c1b23] border border-[#242736]`). Each tool row: green ✓ if `success=true`, red ✗ if false. `name` + `duration_ms` right-aligned.

### `MemoryPanel.tsx`

Same score bar pattern as SourcesPanel. Shows `content` snippet + relevance score.

### `WarningToast.tsx`

Amber banner `bg-amber/10 border border-amber text-amber`, shown when `metadata.warning` is non-empty. Auto-dismisses after 6 seconds, or on `×` click. Dismissed state stored in `ChatWindow` local state (not the store), keyed by message id.

### Acceptance criteria

- Messages with 0 sources/tools/memory show no footer badges for those sections.
- Clicking a badge opens the panel; clicking it again closes it.
- Panels across different messages are independent.
- Scores render as proportional width progress bars.
- Warning toast auto-dismisses at 6s.
- Model + duration always shown when metadata present.

---

## Module 6 — Agent Selector & Command Autocomplete ✅
**Goal:** User can switch between General, Thesis, Code, and Calendar agents from the header. Typing `/` in the input shows an autocomplete menu.

### Files created / modified

```
src/components/chat/
  CommandAutocomplete.tsx     ← dropdown shown when input starts with "/"
src/components/shared/
  AgentSelectorDropdown.tsx   ← header dropdown for agent selection
```

### Agents

```typescript
// AgentId = "general" | "thesis" | "code" | "calendar"
// (not "academic" as in the original spec)
const AGENTS = [
  { id: "general",  label: "General",  description: "All-purpose assistant" },
  { id: "thesis",   label: "Thesis",   description: "Academic writing & research" },
  { id: "code",     label: "Code",     description: "Programming & debugging" },
  { id: "calendar", label: "Calendar", description: "Schedule & tasks" },
];
```

### `AgentSelectorDropdown.tsx`

```
┌──────────────────────────────────────┐   h-[48px] header
│  🤖 General ▾  │  phi3:mini · ollama │
└──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │ ● General    All-purpose assistant   │  ← active: bg-[#201f27] + border-l-2 border-[#7c6af7]
  │   Thesis     Academic writing        │
  │   Code       Programming             │
  │   Calendar   Schedule & tasks        │
  └──────────────────────────────────────┘
```

- Clicking an option sets `activeAgent` in chat store.
- Model badge shows `{model} · ollama` from system store.
- Dropdown closes on outside click.

### `CommandAutocomplete.tsx`

Shown when `input.startsWith("/")` and no space after it yet.

```
┌───────────────────────────────────────┐
│  /thesis    Thesis agent              │
│  /code      Code agent                │
│  /calendar  Calendar agent            │
└───────────────────────────────────────┘
```

- Keyboard: `↑` / `↓` navigate, `Enter` or `Tab` selects.
- Selecting sets `activeAgent` and clears the `/command` from the input.

### Sending with agent context

Agent is sent via the `agent` field of `QueryRequest` — no prefix prepended to the query string:

```typescript
const res = await queryAgent({ query, agent: activeAgent }, signal);
```

### Acceptance criteria

- Switching agent in dropdown updates the badge in the header.
- Typing `/` shows autocomplete; arrow keys navigate; Enter selects.
- Selecting updates `activeAgent` and clears the slash command from input.
- Query sent to `/api/query` contains `agent` field (not a `/prefix`).

---

## Module 7 — Settings Panel ✅
**Goal:** Slide-over panel from the right for folder management, model selection, tool permissions, and DND. All changes persist to the backend via `PATCH /api/config`.

### Files created

```
src/components/settings/
  SettingsPanel.tsx       ← absolute-positioned overlay + 320px slide-over shell
  FolderManager.tsx       ← add/remove watched_folders + dashed Add Folder button
  IndexProgress.tsx       ← progress bar during active indexing
  ModelSelector.tsx       ← radio list of models (phi3:mini, qwen2:1.5b, llama3:8b)
  ToolPermissions.tsx     ← toggle switches for execute_python / write_file
  DndToggle.tsx           ← DND switch bound to config.dnd_enabled
src/stores/settings.ts    ← Zustand: AppConfig, isDirty, isOpen, load, patch, open, close
```

### Settings store (`src/stores/settings.ts`)

```typescript
interface SettingsState {
  config: AppConfig | null;
  isDirty: boolean;
  isOpen: boolean;
  error: string | null;
  isSaving: boolean;

  load: () => Promise<void>;              // GET /api/config (falls back to DEFAULT_CONFIG)
  patch: (partial: Partial<AppConfig>) => Promise<void>; // optimistic PATCH /api/config
  open: () => void;
  close: () => void;
}
```

`patch()` is optimistic: merges locally first, then `PATCH /api/config`. On error: reverts and sets `error`.

### `SettingsPanel.tsx` layout

```
absolute inset-0 z-40
  ├── backdrop  (flex-1 bg-black/40, click-to-close)
  └── aside  w-[320px] h-full bg-[#1a1d27] border-l border-[#242736]
        ├── header  h-[48px] "Settings" + × button
        ├── content (scrollable): Watched Folders / Model / Tool Permissions / Notifications
        └── footer  h-[28px] mini status strip
```

The panel sits inside the 560×680 window as an `absolute` overlay (not `position: fixed`). Slide-in via `translate-x-0` / `translate-x-full` transition.

### `FolderManager.tsx`

- Reads `config.watched_folders`.
- Each path: `bg-[#242736]` row, folder SVG icon, monospace path, `×` on hover.
- "Add Folder" → `@tauri-apps/plugin-dialog` `open({ directory: true, multiple: true })`.
- Deduplicates paths before saving.

### `ModelSelector.tsx`

Three models hardcoded: `phi3:mini` (available), `qwen2:1.5b` (not pulled), `llama3:8b` (not pulled).
- Active row: `bg-[#242736] border-l-2 border-[#7c6af7]` + filled purple radio dot.
- Selecting calls `patch({ model: id })`.
- Embedding model shown in a locked notice: `nomic-embed-text (fixed)`.

### `ToolPermissions.tsx`

Custom pill toggles — `w-8 h-4 rounded-full`, `bg-[#7c6af7]` when on, `bg-[#13121b]` when off. Thumb slides via `translate-x`. Binds to `config.tool_permissions.execute_python` / `.write_file`.

### Acceptance criteria

- Settings icon in header opens the panel with a slide animation.
- Adding/removing a folder saves immediately via `PATCH /api/config`.
- Model selection updates `config.model`.
- Tool toggles update `config.tool_permissions.*`.
- DND toggle updates `config.dnd_enabled`.
- Closing (× or backdrop) plays reverse slide.
- `Escape` key closes the panel.

---

## Module 8 — Confirmation Modal ✅
**Goal:** Blocking modal when a tool requires user approval. User can approve or deny.

### Files created / modified

```
src/components/shared/
  ConfirmModal.tsx       ← blocking modal overlay
```

### `ConfirmModal.tsx` layout

```
absolute inset-0 bg-black/60 backdrop-blur-[4px] z-50
  └── card  w-[380px] bg-[#1a1d27] rounded-[12px] border border-[#242736] p-[28px_24px]
        ├── ⚠ "Tool requires your approval"
        ├── tool info block  bg-[#0f1117] rounded border border-[#242736]
        │     Tool    write_file
        │     Path    ~/Documents/summary.md
        │     Action  Create new file (2.3 KB)
        ├── warning paragraph  text-[#8b8fa8]
        └── [ Deny ]  [ ✓ Approve ]
```

Props:
```typescript
interface ConfirmModalProps {
  toolName: string;
  toolPath?: string;
  toolAction?: string;
  toolSize?: string;
  warningText?: string;
  onApprove: () => void;
  onDeny: () => void;
}
```

Callbacks (`onApprove`/`onDeny`) are stored directly on `PendingConfirmation` in the chat store — not looked up by ID.

### Detection logic

After receiving a response, scan `metadata.tools` for any record where `success === false`. If found: `setPendingConfirmation({ toolName, ..., onApprove: ..., onDeny: ... })`.

### Acceptance criteria

- Modal renders over entire window; nothing behind is clickable.
- `Escape` = Deny.
- Approve/Deny callbacks clear `pendingConfirmation`.
- Modal never appears when all tool calls succeeded.

---

## Module 9 — Polish & Accessibility ✅ (partial)
**Goal:** Smooth transitions, keyboard navigation, screen reader labels.

### Animations implemented

| Element | Transition |
|---------|-----------|
| Settings panel open/close | `translate-x-0 ↔ translate-x-full`, 200ms ease-out |
| Agent dropdown | Appears/disappears on open toggle |
| Typing indicator dots | `bounce` keyframe, staggered `-0.32s / -0.16s` delays |
| Ollama status dot | `pulse-green` keyframe (scale + box-shadow) |
| Custom scrollbar | `width: 4px`, `bg-[#242736]`, hover `bg-[#474554]` |

### Keyboard navigation

| Key | Action |
|-----|--------|
| `Cmd+Shift+Space` | Toggle window (Tauri global shortcut) |
| `Enter` | Send message |
| `Shift+Enter` | New line in textarea |
| `Escape` (loading) | Cancel request |
| `Escape` (settings open) | Close settings |
| `Escape` (modal open) | Deny confirmation |
| `↑` / `↓` | Navigate command autocomplete |

### ARIA labels

```tsx
<footer aria-label="System status">
<textarea aria-label="Chat input">
<button aria-label={isLoading ? "Cancel request" : "Send message"}>
<div role="article" aria-label="Your message">
<div role="article" aria-label="Assistant message">
<dialog role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
<aside role="complementary" aria-label="Settings">
<button role="switch" aria-checked={enabled}>  {/* DndToggle */}
```

### Error boundary

`App.tsx` wraps `MainLayout` / `WizardShell` in an `ErrorBoundary` class component that shows:
```
Something went wrong in the UI.
[error message]
[ Reload ]
```

### Performance

- SettingsPanel is `React.lazy()` loaded — only imported when settings are opened.
- Status polling is idempotent — `startPolling` no-ops if already running.
- `system.ts` store exposes `stopPolling()` — called on `App` unmount via `useEffect` cleanup.

### Final acceptance criteria

- All animated transitions play smoothly.
- Full keyboard-only operation possible from window open to sending a query.
- No console errors or warnings in production build.
- `npm run tauri build` produces a working `.dmg` with all features working.

---

## Module 10 — Window Chrome & Draggability ✅
**Goal:** Show native macOS traffic light buttons (close / minimize / fullscreen) and allow the user to drag the window to any position on screen.

### Problem

The window was configured with `decorations: false`, which strips all native window chrome. Two consequences:
1. No close / minimize / fullscreen buttons.
2. No title bar to grab — the window was stuck at the centered position.

### Solution

Tauri v2 supports `titleBarStyle: "Overlay"` on macOS. This floats the native traffic light buttons over the top-left of the window content without rendering a visible title bar background. Combined with `data-tauri-drag-region` on the header element, the window becomes freely draggable.

### Files changed

| File | Change |
|------|--------|
| `src-tauri/tauri.conf.json` | `decorations: false → true`; `titleBarStyle: "Overlay"`; height `680 → 708` |
| `src/layouts/MainLayout.tsx` | Added 28px drag strip (`data-tauri-drag-region`) as first child; height `680 → 708` |
| `src/layouts/Header.tsx` | Removed `data-tauri-drag-region` from header; reverted to `px-3`; removed custom close button |
| `src-tauri/src/lib.rs` | Switched to `.build() + .run(handler)` pattern; handles `RunEvent::Reopen` to show window on Dock click |

### Traffic light zone strip

A dedicated 28px `<div data-tauri-drag-region className="h-7 bg-[#1c1b23] shrink-0" />` sits at the very top of the layout. The traffic lights float in this empty strip — no content to overlap. The header and everything below it is untouched.

This also solves the dragging problem: the strip is completely empty so mouse events reach the `data-tauri-drag-region` handler unblocked. The header itself has interactive children (buttons, dropdown) that would capture mouse events and prevent dragging if `data-tauri-drag-region` were placed there.

### Dock icon behavior

`RunEvent::Reopen` fires on macOS when the user clicks the Dock icon while the app is running but has no visible windows (i.e. after `window.hide()`). The handler calls `win.show()` + `win.set_focus()`. This required switching from `Builder::run(context)` to `Builder::build(context).run(handler)`.

### Behavior notes

- **Red button (close):** Tauri's default for a tray app is to close the window. If hide-on-close is preferred, add an `on_window_event` handler in `lib.rs` that intercepts `CloseRequested` and calls `window.hide()` instead.
- **Yellow button (minimize):** Minimizes to the Dock — clicking the Dock icon then shows it again via `Reopen`.
- **Green button (fullscreen):** Enters native fullscreen.
- **Dragging:** Grab the 28px strip at the top. Position is not persisted across restarts — window recenters on next launch.

### Acceptance criteria

- Traffic light buttons visible in the top strip, not overlapping the header row.
- Dragging the top strip moves the window freely.
- Logo and agent dropdown sit fully below the traffic lights with no overlap.
- Clicking the Dock icon while the window is hidden shows and focuses the window.

---

## Development Commands Reference

```bash
# Install dependencies (first time)
cd cerebro/ui/tray
npm install

# Start dev server (hot reload)
npm run tauri dev

# Type-check only (no build)
npx tsc --noEmit

# Lint
npx eslint src --ext .ts,.tsx

# Full macOS production build
npm run tauri build
```

---

## File Tree

```
cerebro/ui/tray/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── postcss.config.js
├── tailwind.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx                          ← wizard/main routing + ErrorBoundary
│   ├── index.css                        ← Tailwind + custom animations
│   ├── api/
│   │   ├── types.ts
│   │   ├── client.ts
│   │   └── errors.ts
│   ├── stores/
│   │   ├── chat.ts
│   │   ├── system.ts
│   │   ├── settings.ts
│   │   └── wizard.ts
│   ├── layouts/
│   │   ├── Header.tsx
│   │   └── MainLayout.tsx
│   └── components/
│       ├── chat/
│       │   ├── ChatWindow.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── MessageFooter.tsx
│       │   ├── InputArea.tsx
│       │   ├── TypingIndicator.tsx
│       │   ├── WarningToast.tsx
│       │   ├── SourcesPanel.tsx
│       │   ├── ToolHistoryPanel.tsx
│       │   ├── MemoryPanel.tsx
│       │   └── CommandAutocomplete.tsx
│       ├── wizard/
│       │   ├── WizardShell.tsx
│       │   ├── WizardDots.tsx
│       │   ├── StepOllama.tsx
│       │   ├── StepModel.tsx
│       │   └── StepFolders.tsx
│       ├── status/
│       │   ├── StatusBar.tsx
│       │   ├── OllamaIndicator.tsx
│       │   ├── RamGauge.tsx
│       │   ├── LatencyBadge.tsx
│       │   └── FilesCounter.tsx
│       ├── settings/
│       │   ├── SettingsPanel.tsx
│       │   ├── FolderManager.tsx
│       │   ├── ModelSelector.tsx
│       │   ├── ToolPermissions.tsx
│       │   ├── DndToggle.tsx
│       │   └── IndexProgress.tsx
│       └── shared/
│           ├── AgentSelectorDropdown.tsx
│           └── ConfirmModal.tsx
└── src-tauri/
    ├── tauri.conf.json
    ├── Cargo.toml
    └── src/
        └── main.rs
```

---

## Testing Checklist Per Module

| Module | Manual test |
|--------|-------------|
| M0 | `npm run tauri dev` opens 560×680 window; `Cmd+Shift+Space` toggles; click outside hides |
| M1 | `getStatus()` in browser console returns typed data when backend running |
| M2 | Full wizard flow: Ollama detection → model pull stream → folder picker → chat appears |
| M3 | Kill Ollama → status bar dot goes red within 10s |
| M4 | 10 back-and-forth messages; cancel mid-flight; auto-scroll works |
| M5 | Response with 2 sources + 1 tool: badges appear, panels expand/collapse independently |
| M6 | Switch agent dropdown → badge updates; type `/` → autocomplete; select → `agent` field in request |
| M7 | Add folder → `GET /api/config` shows new path; toggle tool off → config updated |
| M8 | Tool call with `success=false` → modal appears; Deny → `pendingConfirmation` cleared |
| M9 | Navigate app keyboard-only; check no console errors in production build |
| M10 | Traffic lights visible top-left; drag header to move window; logo not obscured |
