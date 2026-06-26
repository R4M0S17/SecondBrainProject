> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Fleet Orchestrator — Frontend Implementation Path
**Companion to `LOCAL_MODEL_FLEET_ORCHESTRATOR.md`**
React 18 + TypeScript + Zustand + Tauri · `ui/tray/src/`

---

## Prerequisites

Backend modules from `LOCAL_MODEL_FLEET_ORCHESTRATOR.md` must expose:
- `GET /api/fleet/status` — hardware snapshot + current model selection + swap state
- `GET /api/fleet/models` — full model registry with each model's metadata
- `GET /api/status` — extended with fleet fields: `current_model_id`, `quantization`, `gpu_layers_used`, `ram_pressure_pct`, `swap_in_progress`, `model_swaps_session`
- SSE stream (`POST /api/query/stream`) — new event type `model_swap` with `{ phase: "started" | "complete", from_model: string, to_model: string, reason: string }`
- `ResponseMetadata` — extended with `model_id`, `quantization`, `gpu_layers_used`, `model_swap_occurred`, `selection_rationale`

---

## Implementation Order (strict dependency chain)

```
FE-1 Types ✅
  └─ FE-2 API Client ✅
       └─ FE-3 System Store ✅
            ├─ FE-4 ModelBadge ✅
            │    └─ FE-7 StatusBar update ✅
            │         └─ FE-8 FleetPanel (popover on ModelBadge click) ✅
            ├─ FE-5 VramGauge ✅
            │    └─ FE-7 StatusBar update (also needs FE-5) ✅
            ├─ FE-6 SwapBanner ✅
            └─ FE-9 Settings Fleet Section ✅
FE-1 Types ✅
  └─ FE-10 MessageFooter extension (independent of store) ✅
```

---

## FE-1 — Type Extension ✅ DONE

**File:** `src/api/types.ts`

**What to add:**

New interface `HardwareSnapshot` with fields:
- `ram_total_gb`, `ram_available_gb`, `ram_pressure_pct` (number)
- `gpu_backend` (`"metal" | "cuda" | "none"`)
- `gpu_vram_total_gb`, `gpu_vram_available_gb` (number)
- `unified_memory` (boolean — true on Apple Silicon, meaning GPU and RAM share the same pool)

New interface `FleetModelEntry` with fields:
- `id`, `family`, `path` (string)
- `params_b`, `quant`, `ram_required_gb`, `vram_required_gb` (number)
- `gpu_layers` (number)
- `context_length` (number)
- `capabilities` (string array)
- `speed_tokens_per_sec` (number)
- `available_on_disk` (boolean)

New interface `FleetStatus` with fields:
- `current_model` (FleetModelEntry)
- `hardware` (HardwareSnapshot)
- `swap_in_progress` (boolean)
- `swap_target_model_id` (string or null)
- `model_swaps_session` (number)
- `selection_rationale` (string)
- `mode` (`"auto" | "pinned"`)

New interface `FleetModelsResponse` with fields:
- `models` (FleetModelEntry array)
- `active_model_id` (string)

New interface `ModelSwapEvent` with fields:
- `phase` (`"started" | "complete"`)
- `from_model` (string)
- `to_model` (string)
- `reason` (string)
- `estimated_seconds` (number, present when phase is `"started"`)

**Extend existing interfaces:**

`StatusResponse` — add optional fields: `current_model_id`, `quantization`, `gpu_layers_used`, `ram_pressure_pct`, `swap_in_progress`, `model_swaps_session`

`ResponseMetadata` — add optional fields: `model_id`, `quantization`, `gpu_layers_used`, `model_swap_occurred`, `selection_rationale`

---

## FE-2 — API Client Extension ✅ DONE

**File:** `src/api/client.ts`

**New functions to add:**

`getFleetStatus()` — GET `/api/fleet/status` → `FleetStatus`

`getFleetModels()` — GET `/api/fleet/models` → `FleetModelsResponse`

`setFleetMode(mode: "auto" | "pinned", pinned_model_id?: string)` — PATCH `/api/fleet/config` — switches the orchestrator between automatic selection and user-pinned model

**Extend `queryAgentStream`:**

In the SSE line parser (the section that handles `parsed.token`, `parsed.metadata`, `parsed.error`), add a new branch for `parsed.model_swap`. When this event arrives, call a new optional callback parameter `onModelSwap?: (event: ModelSwapEvent) => void`. The function signature gains this optional fourth parameter after `onConversationId`.

---

## FE-3 — System Store Extension ✅ DONE

**File:** `src/stores/system.ts`

**Add to `SystemState` interface:**
- `fleetStatus: FleetStatus | null`
- `swapEvent: ModelSwapEvent | null` — the most recent in-flight swap event; null when no swap active

**Add to store actions:**
- `refreshFleet()` — calls `getFleetStatus()` and sets `fleetStatus`; called in the same polling cycle as `refresh()` (both fire every 10s)
- `setSwapEvent(event: ModelSwapEvent | null)` — set by the chat store when an SSE `model_swap` event arrives; cleared when phase is `"complete"` or when a new conversation starts

**Modify `startPolling`:** call `refreshFleet()` immediately alongside the existing `refresh()` call, and include it in the `setInterval` callback.

**Add selector:**
`selectSwapInProgress(state: SystemState): boolean` — returns `state.fleetStatus?.swap_in_progress ?? false`

---

## FE-4 — ModelBadge Component ✅ DONE

**New file:** `src/components/status/ModelBadge.tsx`

**Purpose:** replaces the plain `<span>{model}</span>` in `StatusBar`. Clickable — opens `FleetPanel` (FE-8).

**Visual spec:**
- Displays: short model name (e.g., `qwen2.5-7b`) + quantization pill (e.g., `Q4_K_M`) side by side
- Quantization pill color: green for Q8, yellow for Q4/Q5, orange for Q2/Q3
- During a swap (`swapInProgress = true`): the entire badge pulses with a slow CSS opacity animation and shows a small spinner icon to the left of the model name
- On hover: cursor changes to pointer (signals it's clickable)
- Clicking the badge calls a prop `onClick` (the parent `StatusBar` manages open state for `FleetPanel`)

**Props:** `modelId: string`, `quantization: string`, `swapInProgress: boolean`, `onClick: () => void`

**Data source:** reads `model` and new `quantization` field from `useSystemStore`'s `status`; reads `swap_in_progress` from `fleetStatus`

---

## FE-5 — VramGauge Component ✅ DONE

**New file:** `src/components/status/VramGauge.tsx`

**Purpose:** sits next to `RamGauge` in `StatusBar` for non-cloud mode. On Apple Silicon (unified memory), the component renders nothing — the existing `RamGauge` already covers the shared pool. On NVIDIA, shows a separate VRAM bar.

**Visual spec:**
- Same style as existing `RamGauge` (monospace, `10px`, uppercase)
- Label: `VRAM`
- Bar fill color: same green→yellow→red thresholds as `RamGauge`
- When `unified_memory` is true: returns `null` (renders nothing)

**Props:** `used: number`, `total: number`, `unified: boolean`

**Data source:** `fleetStatus.hardware.gpu_vram_total_gb`, `gpu_vram_available_gb`, `unified_memory` from `useSystemStore`

---

## FE-6 — SwapBanner Component ✅ DONE

**New file:** `src/components/chat/SwapBanner.tsx`

**Purpose:** appears inside `ChatWindow` between the message list and `InputArea` when a model swap is in progress. Disappears when swap completes. Does not block input (the user can still type; the request will be queued until the swap finishes).

**Visual spec:**
- Full-width bar, same height as `WarningToast`
- Background: `#1e1b2e` with a left border accent in amber (`#f59e0b`)
- Spinner icon (animated) on the left
- Text: `Switching to {to_model} ({reason}) · ~{estimated_seconds}s`
- When phase is `"complete"`: briefly shows `{to_model} ready` in green for 1.5 seconds, then unmounts
- No close button — it self-manages based on `swapEvent` from the store

**Props:** none — reads directly from `useSystemStore`'s `swapEvent`

**Integration point:** render `<SwapBanner />` inside `ChatWindow.tsx` just above `<InputArea />`, always present in the DOM but renders `null` when `swapEvent` is null

---

## FE-7 — StatusBar Update ✅ DONE

**File:** `src/components/status/StatusBar.tsx`

**Changes (no new file):**

1. Import `ModelBadge` (FE-4), `VramGauge` (FE-5), and `fleetStatus` from `useSystemStore`

2. Add local state `fleetPanelOpen: boolean` (controls `FleetPanel` FE-8)

3. In the left group: replace the plain `<span>{model}</span>` with `<ModelBadge modelId={...} quantization={...} swapInProgress={...} onClick={() => setFleetPanelOpen(true)} />`

4. In the right group (non-cloud path): add `<VramGauge>` between `<RamGauge>` and the separator dot — only when `fleetStatus?.hardware.gpu_backend !== "none"`

5. Render `<FleetPanel open={fleetPanelOpen} onClose={() => setFleetPanelOpen(false)} />` at the bottom of the returned JSX (it manages its own position as an overlay)

---

## FE-8 — FleetPanel Component ✅ DONE

**New file:** `src/components/status/FleetPanel.tsx`

**Purpose:** read-only informational popover that opens when the user clicks `ModelBadge`. Shows the full fleet state. No config changes happen here (those go in Settings FE-9).

**Visual spec:**
- Positioned absolutely, anchored above the `StatusBar` (bottom of screen), left-aligned with the `ModelBadge`
- Width: 300px, max-height: 400px, scrollable
- Background: `#1a1d27` border `#242736`, same dark theme as `SettingsPanel`
- Close on Escape or click outside (same pattern as `ConfirmModal`)
- Sections (in order):
  - **Active model** — name, family, params, quant, context length, GPU layers in use, tokens/sec
  - **Hardware** — RAM bar (used/total), VRAM bar (or "Unified" label on Apple Silicon), CPU %, GPU backend badge
  - **Selection** — `selection_rationale` string from fleet status (why this model was chosen)
  - **Available models** — compact list of all `FleetModelEntry` items; the active one is highlighted; entries missing from disk show a warning icon

**Props:** `open: boolean`, `onClose: () => void`

**Data source:** `useSystemStore`'s `fleetStatus` — no additional API call needed if the store is already polling

---

## FE-9 — Settings Panel Fleet Section ✅ DONE

**File:** `src/components/settings/SettingsPanel.tsx` + new file `src/components/settings/FleetSettings.tsx`

**New component `FleetSettings`:**

A self-contained section that plugs into `SettingsPanel` as a new `<section>`. Contains:

1. **Mode toggle** — two-button row (same styling as the existing `Local / Claude API` toggle):
   - `Auto` (default) — orchestrator picks the model
   - `Pinned` — user forces a specific model

2. **Model picker** — shown only when mode is `Pinned`. A `<select>` dropdown listing all `FleetModelEntry` items from `getFleetModels()`, grouped by family. Each option shows: `{id} · {params_b}B · {quant} · {ram_required_gb}GB`. Models not found on disk are disabled with a `(not found)` suffix.

3. **RAM safety margin** — shown only in `Auto` mode. A numeric input (or simple `- / +` stepper) for the percentage margin the orchestrator keeps free before selecting a model (default: 15%). Label: `RAM safety margin · {value}%`. On change calls `setFleetMode("auto")` with the updated threshold.

4. **Swap stats** — read-only row: `{model_swaps_session} swaps this session`. Always visible.

**Integration in `SettingsPanel.tsx`:** add a new `<section>` with label `Fleet Orchestrator` after the existing `Model` section, containing `<FleetSettings />`. The section is hidden when `isCloud` is true (fleet orchestration only applies to local inference).

---

## FE-10 — MessageFooter Extension ✅ DONE

**File:** `src/components/chat/MessageFooter.tsx`

**Changes (no new file):**

`ResponseMetadata` now carries `model_id`, `quantization`, `model_swap_occurred`, `selection_rationale`.

1. After the existing latency display, add a model chip: `{model_id} · {quantization}` in `text-[#474554]` monospace — same muted style as pipeline timing.

2. When `model_swap_occurred` is true, prepend a small amber icon (⇄ or similar SVG) before the model chip to indicate the model was swapped mid-session to serve this specific response.

3. Tooltip (native `title` attribute) on the model chip: show `selection_rationale` — the reason the orchestrator chose this model for the request.

The model chip is only rendered when `model_id` is present in metadata (guard with `metadata?.model_id`).

---

## Chat Store Extension (minor)

**File:** `src/stores/chat.ts`

In `queryAgentStream`'s call site, pass the new `onModelSwap` callback. When called:
- phase `"started"` → call `useSystemStore.getState().setSwapEvent(event)`
- phase `"complete"` → call `useSystemStore.getState().setSwapEvent(null)` after a 1500ms delay (so `SwapBanner` can briefly show the "ready" state before disappearing)

---

## Acceptance Criteria

| Module | Criteria |
|---|---|
| FE-1 | TypeScript compiles with zero errors after type additions |
| FE-2 | `getFleetStatus()` and `getFleetModels()` appear in Network tab when called |
| FE-3 | `fleetStatus` in Zustand devtools shows hardware fields after polling |
| FE-4 | `ModelBadge` pulses visibly in Storybook/dev when `swapInProgress=true` |
| FE-5 | `VramGauge` renders on NVIDIA; returns null on Apple Silicon (check `unified_memory`) |
| FE-6 | `SwapBanner` appears during a manually triggered swap and auto-dismisses |
| FE-7 | StatusBar shows `ModelBadge` + `VramGauge`; clicking badge opens FleetPanel |
| FE-8 | FleetPanel lists all registry models; active model highlighted; closes on Escape |
| FE-9 | Pinned mode forces a specific model; auto mode shows RAM margin input |
| FE-10 | Each assistant message footer shows model chip; swap icon on swapped messages |

---

## Files changed / created summary

```
CHANGED:
  src/api/types.ts              ← FE-1: new interfaces, extend StatusResponse + ResponseMetadata
  src/api/client.ts             ← FE-2: new functions, extend queryAgentStream signature
  src/stores/system.ts          ← FE-3: fleet state + actions + refreshFleet
  src/stores/chat.ts            ← chat store: wire onModelSwap callback
  src/components/status/StatusBar.tsx        ← FE-7
  src/components/settings/SettingsPanel.tsx  ← FE-9: add FleetSettings section
  src/components/chat/ChatWindow.tsx         ← add SwapBanner
  src/components/chat/MessageFooter.tsx      ← FE-10

CREATED:
  src/components/status/ModelBadge.tsx       ← FE-4
  src/components/status/VramGauge.tsx        ← FE-5
  src/components/status/FleetPanel.tsx       ← FE-8
  src/components/chat/SwapBanner.tsx         ← FE-6
  src/components/settings/FleetSettings.tsx  ← FE-9
```

**Total:** 5 new files · 8 files modified · 0 new dependencies (no new npm packages needed)
