# Cerebro Frontend Redesign — Implementation Plan

**Design**: Cybernetic Minimalism (see `DESIGN.md`)
**Current codebase**: `ui/tray/src/` (React 18, TypeScript, Zustand, Tailwind CSS 3, Tauri 2)
**Target**: Match `code.html` layout, styling, and component behavior while preserving all existing functionality and API integrations.

---

## Table of Contents

1. [Overview: Current vs. New](#1-overview-current-vs-new)
2. [Phase 0: Design Token Migration](#2-phase-0-design-token-migration)
3. [Phase 1: Layout Restructuring](#3-phase-1-layout-restructuring)
4. [Phase 2: Header Redesign](#4-phase-2-header-redesign)
5. [Phase 3: Fast-Path Toggles](#5-phase-3-fast-path-toggles)
6. [Phase 4: Chat Interface Restyling](#6-phase-4-chat-interface-restyling)
7. [Phase 5: System Sidebar Widgets](#7-phase-5-system-sidebar-widgets)
8. [Phase 6: Restyle All Existing Components](#8-phase-6-restyle-all-existing-components)
9. [Phase 7: Polish & Verification](#9-phase-7-polish--verification)
10. [Dependency Map](#10-dependency-map)
11. [Effort Estimate](#11-effort-estimate)
12. [Risk Register](#12-risk-register)

---

## 1. Overview: Current vs. New

### 1.1 High-Level Delta

| Aspect | Current | New (Cybernetic Minimalism) |
|--------|---------|---------------------------|
| **Background** | `#13121b` / `#0f1117` (navy-black) | `#131317` / `#0e0e12` (matte black) |
| **Primary accent** | `#94a3b8` (blue-gray) | `#2563eb` (blue) / `#00dce6` (cyan accent) |
| **Secondary accent** | `#444652` | `#c0c1ff` (muted indigo) |
| **Depth technique** | Flat solid colors | Glassmorphism (`backdrop-filter: blur(16px)` + 60-80% opacity) |
| **Glow effects** | None | Blue drop-shadow on active elements (`0 0 15px rgba(37,99,235,0.3)`) |
| **Mono font** | Space Grotesk | JetBrains Mono |
| **Layout** | Bottom status bar (28px) | Right sidebar (320px) + thin footer |
| **Header style** | 48px, logo + AgentDropdown + icon buttons | 64px, nav tabs + Turn on/off + icon buttons |
| **Fast-path toggles** | No UI (backend-only) | Pill button row (Math, Calendar, Reminders, Web Search) |
| **RAM display** | Text `"X.X / Y.Y GB"` in footer | Circular SVG progress ring with glow |
| **CPU display** | Not present | Mini bar graph with highlighted peak |
| **Model list** | Popup FleetPanel (click to open/close) | Inline in sidebar as Active Fleet section |
| **Icons** | Inline SVGs (hand-written paths) | Material Symbols outlined (`material-symbols-outlined`) |
| **Chat bubbles** | Rounded pill for user, plain for assistant | `rounded-2xl rounded-tr-sm` user, icon-avatar assistant |
| **Input area** | `bg-[#1c1b23]` solid | `bg-surface-container-low` with `input-glow` border on focus |
| **Footer** | 9 widgets in 28px bar | Minimal: "Cerebro OS • Engine Status: Active" + 3 stats |

### 1.2 Components to Create

| # | Component | File | Purpose |
|---|-----------|------|---------|
| C1 | `FastPathToggles` | `components/chat/FastPathToggles.tsx` | Pill buttons: Math, Calendar, Reminders, Web Search |
| C2 | `SystemSidebar` | `components/status/SystemSidebar.tsx` | 320px right panel container (glass-panel) |
| C3 | `RamGaugeRing` | `components/status/RamGaugeRing.tsx` | Circular SVG progress ring with glow |
| C4 | `CpuMiniGraph` | `components/status/CpuMiniGraph.tsx` | Bar chart widget for CPU load |
| C5 | `StorageAccessButton` | `components/status/StorageAccessButton.tsx` | Folder access card (opens DocumentsPanel) |
| C6 | `ActiveFleetList` | `components/status/ActiveFleetList.tsx` | Active/inactive model list |

### 1.3 Components to Modify

| # | Component | Nature of Change |
|---|-----------|-----------------|
| M1 | `tailwind.config.js` | Full color palette swap + font + spacing + radius tokens |
| M2 | `index.css` | Add glass-panel, glow-ring, input-glow utilities |
| M3 | `MainLayout.tsx` | Add right sidebar alongside chat, restructure flex layout |
| M4 | `Header.tsx` | Nav tabs, new button layout, tall header, palette swap |
| M5 | `StatusBar.tsx` | Strip to minimal footer, remove widgets moved to sidebar |
| M6 | `ChatWindow.tsx` | Padding, scrollbar colors, spacing |
| M7 | `MessageBubble.tsx` | New bubble shapes, avatar, glass-styled code blocks |
| M8 | `InputArea.tsx` | New input container, add/mic/send buttons, `input-glow` |
| M9 | `TypingIndicator.tsx` | Restyle dots to new palette |
| M10 | `MessageFooter.tsx` | Restyle expand toggles |
| M11–M30 | All remaining components | Color token swap, font update, minor spacing adjustments |

---

## 2. Phase 0: Design Token Migration ✅

**Status**: Complete — `tailwind.config.js` palette/fonts/radius/spacing swapped, `index.css` utilities added, `index.html` font links updated.
**Goal**: Change the visual foundation without altering any component logic. After this phase, the app will use new colors/fonts but still have the old layout.

### 2.1 `tailwind.config.js` — Full Palette Swap

**Replace `theme.extend.colors` entirely** with the DESIGN.md palette:

```js
colors: {
  // Surfaces
  surface: '#131317',
  'surface-dim': '#131317',
  'surface-bright': '#39393d',
  'surface-container-lowest': '#0e0e12',
  'surface-container-low': '#1b1b1f',
  'surface-container': '#1f1f23',
  'surface-container-high': '#2a292e',
  'surface-container-highest': '#353439',
  // On-surface
  'on-surface': '#e4e1e7',
  'on-surface-variant': '#b9cacb',
  'inverse-surface': '#e4e1e7',
  'inverse-on-surface': '#303034',
  // Outline
  outline: '#849495',
  'outline-variant': '#3a494b',
  'surface-tint': '#00dce6',
  // Primary (Blue — matching code.html)
  primary: '#e0fdff',
  'on-primary': '#00373a',
  'primary-container': '#2563eb',
  'on-primary-container': '#ffffff',
  'inverse-primary': '#00696f',
  'primary-fixed': '#6ff6ff',
  'primary-fixed-dim': '#00dce6',
  'on-primary-fixed': '#002022',
  'on-primary-fixed-variant': '#004f53',
  // Secondary (Indigo)
  secondary: '#c0c1ff',
  'on-secondary': '#1000a9',
  'secondary-container': '#3131c0',
  'on-secondary-container': '#b0b2ff',
  'secondary-fixed': '#e1e0ff',
  'secondary-fixed-dim': '#c0c1ff',
  'on-secondary-fixed': '#07006c',
  'on-secondary-fixed-variant': '#2f2ebe',
  // Tertiary (Gold)
  tertiary: '#fff6e4',
  'on-tertiary': '#3b2f00',
  'tertiary-container': '#fed83a',
  'on-tertiary-container': '#725e00',
  'tertiary-fixed': '#ffe173',
  'tertiary-fixed-dim': '#e8c423',
  'on-tertiary-fixed': '#221b00',
  'on-tertiary-fixed-variant': '#554500',
  // Error
  error: '#ffb4ab',
  'on-error': '#690005',
  'error-container': '#93000a',
  'on-error-container': '#ffdad6',
  // Legacy aliases (for backward compat during migration)
  background: '#131317',
  'on-background': '#e4e1e7',
  'surface-variant': '#353439',
}
```

**Keep no old color names** (`bg-base`, `bg-surface`, `bg-elevated`, `text-primary`, `text-secondary`, `accent`, `accent-gray`, `success-green`, `amber`). These will be replaced with new names. Any references to old names must be updated simultaneously.

**Remove `darkMode: "class"`** from the config — the app is always dark. Keeping it causes confusion when `dark:` variants do nothing.

**Update `fontFamily`**:
```js
fontFamily: {
  body: ['Inter', 'sans-serif'],
  mono: ['JetBrains Mono', 'monospace'],
  'display-lg': ['Inter', 'sans-serif'],
  'headline-md': ['Inter', 'sans-serif'],
  'label-mono': ['JetBrains Mono', 'monospace'],
}
```

**Add `fontSize` tokens** matching DESIGN.md:
```js
fontSize: {
  'display-lg': ['48px', { lineHeight: '1.1', letterSpacing: '-0.04em', fontWeight: '700' }],
  'headline-md': ['24px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '600' }],
  'body-base': ['15px', { lineHeight: '1.5', letterSpacing: '-0.01em', fontWeight: '400' }],
  'label-mono': ['12px', { lineHeight: '1.0', letterSpacing: '0.05em', fontWeight: '500' }],
  'headline-md-mobile': ['20px', { lineHeight: '1.2', fontWeight: '600' }],
  // Keep legacy aliases
  'label-caps': ['11px', { lineHeight: '16px', letterSpacing: '0.05em', fontWeight: '700' }],
  body: ['14px', { lineHeight: '20px', fontWeight: '400' }],
  'small-mono': ['12px', { lineHeight: '16px', fontWeight: '500' }],
  code: ['13px', { lineHeight: '18px', fontWeight: '400' }],
}
```

**Add `borderRadius`** (matching code.html):
```js
borderRadius: {
  DEFAULT: '0.25rem',
  lg: '0.5rem',
  xl: '0.75rem',
  full: '9999px',
}
```

**Add `spacing`**:
```js
spacing: {
  unit: '4px',
  gutter: '16px',
  'margin-desktop': '32px',
  'margin-mobile': '16px',
  'panel-width': '320px',
}
```

### 2.2 `index.css` — Add CSS Utilities

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: #131317;
    color: #e4e1e7;
    font-family: 'Inter', sans-serif;
    overflow: hidden;
    width: 100vw;
    height: 100vh;
  }
  #root { width: 100%; height: 100%; display: flex; flex-direction: column; }
}

@layer components {
  .glass-panel {
    background: rgba(27, 27, 31, 0.6);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
  }
  .glass-panel-hover:hover {
    background: rgba(27, 27, 31, 0.75);
    backdrop-filter: blur(20px);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .glow-ring {
    box-shadow: 0 0 15px rgba(37, 99, 235, 0.3);
  }
  .glow-ring-cyan {
    box-shadow: 0 0 15px rgba(37, 99, 235, 0.3);
  }
  .glow-ring-indigo {
    box-shadow: 0 0 15px rgba(192, 193, 255, 0.3);
  }
  .glow-ring-gold {
    box-shadow: 0 0 8px rgba(232, 196, 35, 0.4);
  }
  .input-glow:focus-within {
    border-color: #2563eb;
    box-shadow: inset 0 0 10px rgba(37, 99, 235, 0.1), 0 0 10px rgba(37, 99, 235, 0.2);
  }
}

/* Update scrollbar to new palette */
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #3a494b; border-radius: 2px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #849495; }

/* Keep existing animations */
.typing-dot { animation: bounce 1.4s infinite ease-in-out both; }
.typing-dot:nth-child(1) { animation-delay: -0.32s; }
.typing-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

@keyframes progress-indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
.progress-indeterminate {
  animation: progress-indeterminate 1.5s ease-in-out infinite;
  width: 35%;
}

@keyframes pulse-primary {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(37, 99, 235, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
}
.status-dot-pulse { animation: pulse-primary 2s infinite; }
```

### 2.3 Update Font Loading in `index.html`

Change Google Fonts link in `ui/tray/index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
```
Add Material Symbols:
```html
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
```

### 2.4 Design Token Reconciliation

**Important**: `DESIGN.md` specifies cyan (`#00f2fe`) as the primary container color, but `code.html` uses blue (`#2563eb`). `code.html` is the authoritative visual reference. The tailwind config above uses `code.html`'s values. The cyan variants (`#00dce6`, `#6ff6ff`) are preserved as `primary-fixed` and `surface-tint` for subtle accent use.

Key differences from the initial design:
| Token | DESIGN.md | code.html (authoritative) |
|-------|-----------|--------------------------|
| `primary-container` | `#00f2fe` (cyan) | `#2563eb` (blue-600) |
| `on-primary-container` | `#006a70` (dark teal) | `#ffffff` (white) |
| Glow color | `rgba(0,242,254)` (cyan) | `rgba(37,99,235)` (blue) |

All glow effects, progress rings, and active states use blue (`#2563eb`), not cyan. Cyan is retained as a premium accent (`primary-fixed-dim: #00dce6`) for the surface tint and hover states only.

### 2.5 Verification

After this phase:
```bash
cd ui/tray && npm run build
```
Expect: No TypeScript errors. The app renders with new colors but old layout. Some hardcoded `text-[#...]` classes will still use old values — these are fixed in later phases.

---

## 2.5 Phase 0.5: Data Integration & Store Alignment ✅

**Status**: Complete — polling already present in `StatusBar.useEffect`. Store patch merging noted for Phase 3. No code changes needed (verified).
**Goal**: Fix critical data flow issues that would prevent the new layout from working. Run BEFORE layout changes so that system data is available when widgets first mount.

### 2.5.1 Why This Phase Exists

The plan's original Phase 0–7 assumed pure styling work, but the actual codebase has three critical gaps:

1. **No polling init** — The old `StatusBar` started system polling via `useEffect`. The new `StatusBar` must do the same, or `status`/`fleetStatus` stay `null`.
2. **API type mismatches** — The plan references fields (`hardware_snapshot.cpu_percent`, `current_model_params_b`, `fleetStatus.models`) that don't exist in `api/types.ts`.
3. **Store mutation bugs** — `useSettingsStore.patch()` does shallow merge, which would silently destroy `tool_permissions` fields.

### 2.5.2 Changes Required

| File | Change | Risk if skipped |
|------|--------|----------------|
| `src/components/status/StatusBar.tsx` | Add `useEffect` calling `startPolling(10_000)` on mount | All system data stays null |
| `src/stores/system.ts` (optional) | Add `cpuHistory: number[]` buffer if CpuMiniGraph needs real data | CpuMiniGraph shows placeholder only |
| `src/api/types.ts` (optional) | Add `cpu_percent` to `HardwareSnapshot` if backend exposes it | CpuMiniGraph shows placeholder only |
| All sidebar widgets | Use correct field names from `FleetModelEntry`/`StatusResponse` | TypeScript errors, undefined values |

### 2.5.3 Type Field Reference

When implementing sidebar widgets, use these exact field paths (verified against `api/types.ts`):

| Widget | Field Path | Type |
|--------|-----------|------|
| RamGaugeRing | `status.ram_used_gb`, `status.ram_total_gb` | `number` |
| CpuMiniGraph | No CPU data exists in API. Use placeholder or extend backend with `cpu_percent` | — |
| StorageAccessButton | `status.indexed_files` | `number` |
| ActiveFleetList (current model) | `fleetStatus.current_model.id`, `.params_b`, `.quant` | `string`, `number`, `string` |
| ActiveFleetList (model list) | Requires `FleetModelsResponse.models` via separate API call | `FleetModelEntry[]` |
| StatusBar RAM | `status.ram_used_gb`, `status.ram_total_gb` | `number` |

### 2.5.4 Verification

```bash
cd ui/tray && npx tsc --noEmit
```
Expect: No TypeScript errors related to missing fields. All widget data paths compile correctly.

---

## 3. Phase 1: Layout Restructuring ✅

**Status**: Complete — `MainLayout.tsx` restructured with sidebar, `StatusBar.tsx` simplified to minimal footer, `SystemSidebar.tsx` created with widget slots. Sidebar widgets (`RamGaugeRing`, `CpuMiniGraph`, `StorageAccessButton`, `ActiveFleetList`) created as dependencies.
**Goal**: Change from bottom-bar layout to right-sidebar layout. The flex structure must accommodate a 320px sidebar alongside the chat area.

### 3.1 `MainLayout.tsx` — Structural Rewrite

Before:
```
Titlebar (28px)
Header (48px)
ChatWindow (flex-1)
StatusBar (28px)
```

After:
```
Titlebar (28px)
Header (64px)
<div class="flex flex-1 overflow-hidden">
  <main class="flex-1 flex flex-col max-w-5xl mx-auto w-full px-margin-desktop py-8">
    <FastPathToggles />
    <ChatWindow class="flex-1" />
  </main>
  <SystemSidebar class="hidden lg:flex w-panel-width" />
</div>
StatusBar (28px, simplified)
```

Full implementation:

```tsx
// MainLayout.tsx
import { Suspense, lazy, useState, useCallback } from "react";
import Header from "./Header";
import ChatWindow from "../components/chat/ChatWindow";
import FastPathToggles from "../components/chat/FastPathToggles";
import SystemSidebar from "../components/status/SystemSidebar";
import StatusBar from "../components/status/StatusBar";
import { useSettingsStore } from "../stores/settings";

const SettingsPanel = lazy(() => import("../components/settings/SettingsPanel"));
const DocumentsPanel = lazy(() => import("../components/documents/DocumentsPanel"));

export default function MainLayout() {
  const { isOpen: settingsOpen } = useSettingsStore();
  const [docsOpen, setDocsOpen] = useState(false);
  const closeDocs = useCallback(() => setDocsOpen(false), []);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex flex-col w-full h-full bg-background overflow-hidden">
      {/* Titlebar drag zone */}
      <div
        className="h-7 bg-surface-container-low shrink-0"
        data-tauri-drag-region
      />
      <Header
        onDocumentsOpen={() => setDocsOpen(true)}
        onSidebarToggle={() => setSidebarOpen((s) => !s)}
      />
      
      {/* Main content + sidebar */}
      <div className="flex flex-1 overflow-hidden">
        {/* ⚠️ Use <div> not <main> here — ChatWindow internally
            renders its own scrollable message container. Nested
            <main> elements are invalid HTML and break flex layouts. */}
        <div className="flex-1 flex flex-col relative px-margin-desktop py-8 max-w-5xl mx-auto w-full min-w-0">
          <FastPathToggles />
          <ChatWindow className="flex-1 min-h-0" />
        </div>
        <SystemSidebar
          className={`${sidebarOpen ? "flex" : "hidden"} lg:flex w-panel-width shrink-0`}
          onOpenDocuments={() => setDocsOpen(true)}
        />
      </div>
      
      <StatusBar />
      
      {settingsOpen && (
        <Suspense fallback={null}>
          <SettingsPanel />
        </Suspense>
      )}
      {docsOpen && (
        <Suspense fallback={null}>
          <DocumentsPanel isOpen={docsOpen} onClose={closeDocs} />
        </Suspense>
      )}
    </div>
  );
}
```

Key points:
- The chat container is a `<div>` (not `<main>`) to avoid nested `<main>` elements — `ChatWindow` contains its own scrollable message container
- `onOpenDocuments` callback is passed to `SystemSidebar` so `StorageAccessButton` opens the DocumentsPanel
- A sidebar toggle button (`onSidebarToggle`) is passed to `Header` for responsive control below `lg` breakpoint
- `max-w-5xl` and `mx-auto` center the chat area (per design)
- `px-margin-desktop` (32px) matches the design spec
- `SystemSidebar` toggles between hidden and flex at `lg` breakpoint, with manual toggle for smaller screens
- Both panels are inside a `flex` container with `overflow-hidden`
- Titlebar uses `data-tauri-drag-region` attribute (Tauri v2 native drag) instead of JS `startDragging()` which can conflict with `data-tauri-drag-region` on the header

### 3.2 `StatusBar.tsx` — Simplify

Replace the full 9-widget status bar with a minimal footer:

```tsx
// StatusBar.tsx
import { useEffect } from "react";
import { useSystemStore, selectLlamaServerState } from "../../stores/system";
import { useServicesStore } from "../../stores/services";
import EngineIndicator from "./EngineIndicator";

export default function StatusBar() {
  // CRITICAL: Start polling on mount. Without this, all system data stays null.
  const startPolling = useSystemStore((s) => s.startPolling);
  useEffect(() => {
    startPolling(10_000);
  }, [startPolling]);

  const status = useSystemStore((s) => s.status);
  const health = useSystemStore((s) => s.health);
  const servicesOff = useServicesStore((s) => s.servicesOff);
  const llamaServer = selectLlamaServerState(useSystemStore.getState());

  const engineOk = status?.engine_ok ?? false;
  const ramUsed = status?.ram_used_gb ?? 0;
  const ramTotal = status?.ram_total_gb ?? (status?.ram_used_gb ?? 0) + (status?.ram_available_gb ?? 0);
  // CPU is computed from fleetStatus.hardware_snapshot — not on StatusResponse directly.
  // For the footer, read it from a fleetStatus snapshot. Fall back to status data if available.
  const cpuAvg = 0; // Placeholder — see CpuMiniGraph for actual CPU data pipeline.
  const uptime = "—"; // could be computed from health data

  return (
    <footer className="fixed bottom-0 left-0 w-full flex justify-between items-center px-gutter py-2 z-50 bg-surface-container-lowest/50 backdrop-blur-sm border-t border-outline-variant/10 text-on-surface-variant font-label-mono text-label-mono shrink-0">
      <div className="flex items-center gap-2">
        <span>Cerebro OS</span>
        <span className="opacity-30">•</span>
        <EngineIndicator
          ok={engineOk}
          provider={status?.provider}
          llamaServer={llamaServer}
          servicesOff={servicesOff}
        />
      </div>
      <div className="flex gap-6">
        <span>RAM: {ramUsed.toFixed(1)}/{ramTotal.toFixed(1)}GB</span>
        {cpuAvg > 0 && <span>CPU: {Math.round(cpuAvg)}%</span>}
        <span>Uptime: {uptime}</span>
      </div>
    </footer>
  );
}
```

Components **removed** from StatusBar (moved to sidebar):
- `ModelBadge` → `ActiveFleetList`
- `RamGauge`, `VramGauge` → `RamGaugeRing`
- `LatencyBadge` → keep in footer or sidebar
- `FilesCounter` → `StorageAccessButton`
- `FleetPanel` → `ActiveFleetList` (inline)

### 3.3 `SystemSidebar.tsx` — New Component

```tsx
// components/status/SystemSidebar.tsx
import RamGaugeRing from "./RamGaugeRing";
import CpuMiniGraph from "./CpuMiniGraph";
import StorageAccessButton from "./StorageAccessButton";
import ActiveFleetList from "./ActiveFleetList";

interface SystemSidebarProps {
  className?: string;
  onOpenDocuments?: () => void;
}

export default function SystemSidebar({ className = "", onOpenDocuments }: SystemSidebarProps) {
  return (
    <aside className={`flex flex-col p-6 border-l border-outline-variant/20 glass-panel z-40 shrink-0 overflow-y-auto ${className}`}>
      <div className="mb-8">
        <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-6">
          System Status
        </h2>
        <RamGaugeRing />
        <CpuMiniGraph />
        {/* onOpenDocuments wires the StorageAccessButton to the DocumentsPanel */}
        <StorageAccessButton onOpen={onOpenDocuments} />
      </div>
      <ActiveFleetList />
    </aside>
  );
}
```

---

## 4. Phase 2: Header Redesign ✅

**Status**: Complete — `Header.tsx` rewritten with 64px height, nav tabs (Models/Fleet/Tools/Logs), Material Symbols icons, `ServiceControls.tsx` restyled per code.html spec.
**Goal**: Match `code.html` header: taller (64px), nav tabs, new icon set, Turn on/off restyled.

### 4.1 `Header.tsx` — Full Rewrite

```tsx
// layouts/Header.tsx
import { useState } from "react";
import ServiceControls from "../components/status/ServiceControls";
import TimeTravelView from "../components/debug/TimeTravelView";
import WorkflowPanel from "../components/automation/WorkflowPanel";
import { useSettingsStore } from "../stores/settings";

interface HeaderProps {
  onDocumentsOpen?: () => void;
  onSidebarToggle?: () => void;
}

type NavTab = "models" | "fleet" | "tools" | "logs";

export default function Header({ onDocumentsOpen, onSidebarToggle }: HeaderProps) {
  const { open } = useSettingsStore();
  const [debugOpen, setDebugOpen] = useState(false);
  const [workflowsOpen, setWorkflowsOpen] = useState(false);
  const [activeNav, setActiveNav] = useState<NavTab | null>(null);

  const navItems: { id: NavTab; label: string }[] = [
    { id: "models", label: "Models" },
    { id: "fleet", label: "Fleet" },
    { id: "tools", label: "Tools" },
    { id: "logs", label: "Logs" },
  ];

  return (
    <header
      className="flex justify-between items-center w-full px-margin-desktop h-16 bg-background/80 backdrop-blur-md border-b border-outline-variant/30 z-50 shrink-0"
      role="banner"
    >
      {/* Left: brand + nav */}
      <div className="flex items-center gap-4">
        <span className="font-headline-md text-headline-md font-bold text-on-surface select-none">
          Cerebro2
        </span>
        <nav className="hidden md:flex gap-6 ml-8">
          {navItems.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveNav(activeNav === id ? null : id)}
              className={`text-sm font-medium transition-colors ${
                activeNav === id
                  ? "text-primary-container border-b-2 border-primary-container pb-1"
                  : "text-on-surface-variant hover:text-primary"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* Right: controls + icons */}
      <div className="flex items-center gap-4">
        <div className="hidden md:flex gap-3">
          <ServiceControls />
        </div>
        <div className="flex items-center gap-3 text-on-surface-variant">
          {/* Sidebar toggle (visible below lg breakpoint) */}
          <button
            onClick={onSidebarToggle}
            className="lg:hidden hover:text-primary transition-colors"
            aria-label="Toggle sidebar"
            title="Toggle system sidebar"
          >
            <span className="material-symbols-outlined text-[20px]">side_navigation</span>
          </button>
          <button
            onClick={onDocumentsOpen}
            className="hover:text-primary transition-colors"
            aria-label="Documents"
            title="Documents"
          >
            <span className="material-symbols-outlined text-[20px]">description</span>
          </button>
          <button
            onClick={open}
            className="hover:text-primary transition-colors"
            aria-label="Settings"
            title="Settings (⌘,)"
          >
            <span className="material-symbols-outlined text-[20px]">settings</span>
          </button>
          <button
            onClick={() => setDebugOpen(true)}
            className="hover:text-primary transition-colors"
            aria-label="History/Debug"
            title="Time-Travel Debugger"
          >
            <span className="material-symbols-outlined text-[20px]">history</span>
          </button>
          <button
            onClick={() => setWorkflowsOpen(true)}
            className="hover:text-primary transition-colors"
            aria-label="Monitoring"
            title="Desktop Workflows"
          >
            <span className="material-symbols-outlined text-[20px]">monitoring</span>
          </button>
        </div>
      </div>

      {debugOpen && <TimeTravelView onClose={() => setDebugOpen(false)} />}
      {workflowsOpen && <WorkflowPanel onClose={() => setWorkflowsOpen(false)} />}
    </header>
  );
}
```

### 4.2 `ServiceControls.tsx` — Restyle Buttons

Update the Turn on/off buttons to match code.html lines 126-127:
- **Turn off**: `px-4 py-1.5 text-sm font-medium rounded border border-outline-variant text-on-surface-variant hover:text-on-surface transition-colors`
- **Turn on**: `px-4 py-1.5 text-sm font-medium rounded bg-primary-container text-on-primary-container hover:bg-primary transition-colors shadow-[0_0_10px_rgba(37,99,235,0.3)]`

### 4.3 Nav Tab Behavior

Each nav tab triggers a different panel/view:

| Tab | Action | Component |
|-----|--------|-----------|
| Models | Open model settings | `ModelSelector` (inside SettingsPanel) |
| Fleet | Open fleet orchestrator | `FleetSettings` (inside SettingsPanel) or inline |
| Tools | Open tool permissions | `ToolPermissions` (inside SettingsPanel) |
| Logs | Open debug/time-travel | `TimeTravelView` |

Since there's no router, these can either:
(a) Open the relevant settings sub-section, or
(b) Toggle overlay panels like the existing debug view.

**Recommendation**: Start with (a) — clicking a nav tab opens SettingsPanel scrolled to the relevant section via an anchor/callback.

---

## 5. Phase 3: Fast-Path Toggles ✅

**Status**: Complete — `FastPathToggles.tsx` created with pill buttons (Math, Calendar, Reminders, Web Search). Calendar toggles activeAgent, Web Search toggles tool_permission, Math/Reminders are visual indicators.
**Goal**: Create the pill-shaped toggle bar from code.html lines 141-154.

### 5.1 `FastPathToggles.tsx` — New Component

```tsx
// components/chat/FastPathToggles.tsx
import { useChatStore } from "../../stores/chat";
import { useSettingsStore } from "../../stores/settings";

type FastPathId = "math" | "calendar" | "reminders" | "websearch";

interface FastPathItem {
  id: FastPathId;
  label: string;
  icon: string; // Material Symbols name
}

const fastPaths: FastPathItem[] = [
  { id: "math", label: "Math", icon: "calculate" },
  { id: "calendar", label: "Calendar", icon: "calendar_today" },
  { id: "reminders", label: "Reminders", icon: "notifications" },
  { id: "websearch", label: "Web Search", icon: "travel_explore" },
];

export default function FastPathToggles() {
  const activeAgent = useChatStore((s) => s.activeAgent);
  const setActiveAgent = useChatStore((s) => s.setActiveAgent);
  const { patch } = useSettingsStore();

  const isActive = (id: FastPathId): boolean => {
    if (id === "calendar") return activeAgent === "calendar-v1";
    if (id === "websearch") return activeAgent === "auto"; // checked via tool permission
    return false; // math/reminders are backend-only, shown as status
  };

  const handleClick = (id: FastPathId) => {
    switch (id) {
      case "calendar":
        setActiveAgent(isActive(id) ? "auto" : "calendar-v1");
        break;
      case "websearch":
        // CRITICAL: Deep-merge tool_permissions to avoid overwriting
        // execute_python, write_file, read_file permissions.
        const currentPerms = useSettingsStore.getState().config?.tool_permissions;
        void patch({
          tool_permissions: { ...currentPerms, search_web: !isActive(id) },
        });
        break;
      case "math":
      case "reminders":
        // Visual indicator only — these are backend-managed
        break;
    }
  };

  return (
    <div className="flex justify-center gap-3 mb-8">
      {fastPaths.map(({ id, label, icon }) => {
        const active = isActive(id);
        return (
          <button
            key={id}
            onClick={() => handleClick(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-all group ${
              active
                ? "border border-primary-container/30 bg-primary-container/10 text-primary-container shadow-[0_0_10px_rgba(37,99,235,0.1)]"
                : "border border-outline-variant/50 bg-surface-container/30 text-on-surface-variant hover:border-primary-container/50 hover:text-primary-container"
            }`}
          >
            <span className={`material-symbols-outlined text-[18px] ${active ? "" : "group-hover:text-primary-container"}`}>
              {icon}
            </span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
```

**Note**: Math and Reminders in the design are visual indicators that those fast-path stages exist in the backend. They don't need to be functional toggles — they signal to the user what Cerebro can process. Mark them as visually present but non-interactive (or show a brief tooltip).

---

## 6. Phase 4: Chat Interface Restyling ✅

**Status**: Complete — `MessageBubble.tsx` (rounded-2xl user, smart_toy avatar assistant, code blocks), `InputArea.tsx` (input-glow container, Material Symbol icons, engine status footer), `ChatWindow.tsx` (div instead of main, smart_toy empty state), `TypingIndicator.tsx` (primary-container dots, on-surface-variant text).
**Goal**: Match message bubbles, input area, and typing indicator from code.html.

### 6.1 `MessageBubble.tsx` — New Bubble Design

Key structural changes per code.html:

**User message** (lines 158-162):
```tsx
{role === "user" && (
  <div className="flex justify-end">
    <div className="max-w-[70%] bg-surface-variant/50 border border-outline-variant/30 rounded-2xl rounded-tr-sm p-4 text-sm">
      {content}
    </div>
  </div>
)}
```

**Assistant message** (lines 164-178) — including searching indicators:
```tsx
{role === "assistant" && (
  <div className="flex justify-start">
    <div className="flex gap-4 max-w-[80%]">
      <div className="w-8 h-8 rounded-full bg-primary-container/20 flex items-center justify-center shrink-0 border border-primary-container/30">
        <span className="material-symbols-outlined text-[18px] text-primary-container">
          smart_toy
        </span>
      </div>
      <div className="space-y-3 pt-1">
        {(searchingWeb || searchingSources) && !content && (
          <div className="text-xs text-on-surface-variant italic flex items-center gap-1.5 mb-1">
            <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
            {searchingWeb
              ? "Searching the web…"
              : `Searching ${searchingSources?.count ?? 0} file${(searchingSources?.count ?? 0) !== 1 ? "s" : ""}…`
            }
          </div>
        )}
        <p className="text-sm text-on-surface-variant whitespace-pre-wrap">{content}</p>
        {sources && <SourcesPanel sources={sources} />}
        {tools && <ToolHistoryPanel tools={tools} />}
        {memory && <MemoryPanel memory={memory} />}
      </div>
    </div>
  </div>
)}
```

**System-styled code block** (lines 171-176):
```tsx
{hasCodeBlock && (
  <div className="bg-surface-container-low border border-outline-variant/20 rounded-lg p-3 font-label-mono text-label-mono text-on-surface-variant">
    {codeLines.map((line, i) => (
      <div key={i}>{line}</div>
    ))}
    {recommendation && (
      <div className="text-primary-container mt-1">&gt; {recommendation}</div>
    )}
  </div>
)}
```

**Streaming** — Keep the existing `useTypewriter` hook but ensure it works with the new structure. The blinking cursor should use `animate-pulse` with `bg-primary-container` (blue).

**"Searching..." indicators** — Keep existing logic but restyle to match the new token system.

### 6.2 `InputArea.tsx` — New Input Design

Replace the input container with the design from code.html lines 198-209:

```tsx
// Inside InputArea.tsx, the wrapper div:
<div className="relative w-full mt-auto">
  <div className="input-glow flex items-center bg-surface-container-low border border-outline-variant/50 rounded-xl p-2 transition-all duration-300">
    {/* Add button */}
    <button className="p-2 text-on-surface-variant hover:text-primary-container transition-colors">
      <span className="material-symbols-outlined text-[20px]">add</span>
    </button>
    
    {/* Text input — uses <textarea> not <input> to preserve:
        - Multi-line support (Shift+Enter for newlines)
        - Auto-grow (height adjusts to content, capped at ~4 lines)
        - Existing handleChange/auto-grow logic in the component
        code.html uses <input> for the static mockup, but the real
        React component needs <textarea> for functionality parity.
    */}
    <textarea
      ref={inputRef}
      rows={1}
      className="flex-1 bg-transparent border-none resize-none text-on-surface text-sm focus:ring-0 placeholder:text-outline/50 px-2 custom-scrollbar"
      placeholder="Ask Cerebro or issue a command..."
      value={text}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      disabled={isLoading}
    />
    
    {/* Right controls */}
    <div className="flex items-center gap-2 pr-2 text-on-surface-variant">
      <button className="p-2 hover:text-primary transition-colors">
        <span className="material-symbols-outlined text-[20px]">mic</span>
      </button>
      <button
        onClick={handleSend}
        disabled={!text.trim() || isLoading}
        className="p-2 bg-primary-container/10 text-primary-container rounded-lg border border-primary-container/20 hover:bg-primary-container/20 transition-colors disabled:opacity-30"
      >
        <span className="material-symbols-outlined text-[18px]">send</span>
      </button>
    </div>
  </div>
  
  {/* Status footer */}
  <div className="text-center mt-3 text-xs text-outline/50 font-label-mono">
    Engine Status: {engineOk ? "Active" : "Offline"} • Latency {latency}ms
  </div>
</div>
```

Keep all existing file upload, streaming, cancel, and tool confirmation logic. Only the visual wrapper changes.

### 6.3 `ChatWindow.tsx` — Spacing & Padding

Update the outer container:
- **Critical**: Change the scrollable container from `<main>` to `<div>` to avoid nested `<main>` elements (MainLayout wraps the chat area in a flex container)
- Remove old padding values
- Use `space-y-6` between message groups
- Chat area becomes a `flex-1 overflow-y-auto mb-6 pr-4 space-y-6` container with `custom-scrollbar` class
- Empty state icon: `smart_toy` (Material Symbols) instead of brain emoji
- Keep the `ConfirmModal`, `SwapBanner`, `WarningToast` rendering as-is — only visual wrappers change

### 6.4 `TypingIndicator.tsx` — Restyle

Use the new color tokens:
- Dots: `bg-primary-container` with the existing bounce animation
- Text: "Thinking with {model}" in `text-on-surface-variant text-sm`
- Progress bar: indeterminate cyan bar using existing animation

---

## 7. Phase 5: System Sidebar Widgets ✅

**Status**: Complete — `RamGaugeRing.tsx` (SVG circular progress with glow), `CpuMiniGraph.tsx` (placeholder bar chart), `StorageAccessButton.tsx` (folder access card), `ActiveFleetList.tsx` (current model display). Composed in `SystemSidebar.tsx`.
**Goal**: Create all 4 sidebar widgets as independent components, then compose them into `SystemSidebar`.

### 7.1 `RamGaugeRing.tsx` — Circular SVG Progress

From code.html lines 217-236. Accept `used` and `total` GB, render SVG ring.

```tsx
// components/status/RamGaugeRing.tsx
import { useSystemStore } from "../../stores/system";

interface RamGaugeRingProps {
  used?: number;
  total?: number;
}

export default function RamGaugeRing({ used, total }: RamGaugeRingProps) {
  const status = useSystemStore((s) => s.status);
  const usedGb = used ?? status?.ram_used_gb ?? 0;
  const totalGb = total ?? status?.ram_total_gb ?? (usedGb + (status?.ram_available_gb ?? 0));
  const percent = totalGb > 0 ? (usedGb / totalGb) * 100 : 0;
  const circumference = 2 * Math.PI * 40; // r=40
  const dashOffset = circumference - (percent / 100) * circumference;
  const isPressed = percent > 80;

  return (
    <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-4 relative overflow-hidden group hover:bg-surface-container/60 transition-colors">
      <div className="flex justify-between items-start mb-4">
        <span className="text-xs font-medium text-on-surface-variant">Memory Allocation</span>
        <span className="material-symbols-outlined text-[16px] text-primary-container">memory</span>
      </div>
      <div className="flex justify-center items-center py-2">
        <div className="relative w-32 h-32 flex items-center justify-center">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            {/* Background track */}
            <circle
              cx="50" cy="50" r="40"
              fill="none"
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="6"
            />
            {/* Foreground track */}
            <circle
              cx="50" cy="50" r="40"
              fill="none"
              stroke="#2563eb"
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-out"
              style={{ filter: "drop-shadow(0 0 4px rgba(37,99,235,0.5))" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-label-mono text-lg font-bold text-primary-fixed">
              {usedGb.toFixed(2)}
            </span>
            <span className="text-[10px] text-outline uppercase">
              GB / {totalGb.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
      <div className="mt-2 text-center text-[10px] text-on-surface-variant font-label-mono">
        {Math.round(percent)}% UTILIZED
        {isPressed && " • HIGH PRESSURE"}
      </div>
    </div>
  );
}
```

### 7.2 `CpuMiniGraph.tsx` — CPU Bar Chart

From code.html lines 238-256. Shows average percentage + 6 mini bars.

**⚠️ No CPU data in API types**: The `HardwareSnapshot` type (on `FleetStatus.hardware`) and `StatusResponse` have no CPU fields. This widget requires either (a) a backend extension to expose CPU stats, or (b) a frontend-side CPU sampler (via `navigator.hardwareConcurrency` mock or Tauri system API). The implementation below uses a **future-ready placeholder** that renders the visual shell with fallback values.

```tsx
// components/status/CpuMiniGraph.tsx
import { useSystemStore } from "../../stores/system";

export default function CpuMiniGraph() {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  // TODO: When backend exposes cpu_percent, read it from fleetStatus or a new status field.
  // For now, show "—" as the value and flat bars (placeholder state).
  const cpuAvg = 0;
  // Placeholder bars — replace with a rolling buffer in the store.
  const bars: number[] = [];

  return (
    <div className="bg-surface-container/40 rounded-xl p-5 border border-outline-variant/20 mb-6 hover:bg-surface-container/60 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <span className="text-xs font-medium text-on-surface-variant">Compute Load</span>
        <span className="material-symbols-outlined text-[16px] text-primary-container">speed</span>
      </div>
      <div className="flex items-end gap-3 mb-2">
        <span className="font-label-mono text-2xl text-on-surface">
          {cpuAvg > 0 ? Math.round(cpuAvg) : "—"}
        </span>
        <span className="text-xs text-outline mb-1">{cpuAvg > 0 ? "% AVG" : ""}</span>
      </div>
      <div className="h-8 flex items-end gap-1 w-full mt-2">
        {bars.length > 0 ? bars.map((height, i) => {
          const isLatest = i === bars.length - 1;
          return (
            <div
              key={i}
              className={`w-1/6 rounded-t-sm transition-all ${
                isLatest
                  ? "bg-tertiary-fixed-dim/80 shadow-[0_0_8px_rgba(232,196,35,0.4)]"
                  : "bg-surface-variant"
              }`}
              style={{ height: `${height}%` }}
            />
          );
        }) : (
          // Flat placeholder bars when no data
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="w-1/6 rounded-t-sm bg-surface-variant/30" style={{ height: "10%" }} />
          ))
        )}
      </div>
    </div>
  );
}
```

**To make this widget functional**, choose one:
1. **Backend extension**: Add `cpu_percent` to `HardwareSnapshot` in the Python backend (via `psutil.cpu_percent()`).
2. **Frontend polling**: Add a rolling CPU buffer to `systemStore` that samples CPU via Tauri system API or `performance` API approximation.
3. **Future phase**: Defer to a later iteration. The visual shell renders correctly with placeholder data.

### 7.3 `StorageAccessButton.tsx` — Folder Access

From code.html lines 258-269.

```tsx
// components/status/StorageAccessButton.tsx
import { useSystemStore } from "../../stores/system";

interface StorageAccessButtonProps {
  onOpen?: () => void;
}

export default function StorageAccessButton({ onOpen }: StorageAccessButtonProps) {
  const files = useSystemStore((s) => s.status?.indexed_files ?? 0);

  return (
    <button
      onClick={onOpen}
      className="w-full bg-surface-container/40 rounded-xl p-4 border border-outline-variant/20 mb-6 hover:bg-surface-container/60 transition-colors flex items-center justify-between group"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary-container/10 text-primary-container flex items-center justify-center border border-primary-container/20 group-hover:bg-primary-container/20 transition-colors">
          <span className="material-symbols-outlined text-[18px]">folder</span>
        </div>
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wider mb-0.5">
            Storage Access
          </span>
          <span className="text-sm font-medium text-on-surface">
            {files > 0 ? `${files} file${files !== 1 ? "s" : ""}` : "Open Files"}
          </span>
        </div>
      </div>
      <span className="material-symbols-outlined text-[20px] text-on-surface-variant group-hover:text-on-surface transition-colors">
        chevron_right
      </span>
    </button>
  );
}
```

### 7.4 `ActiveFleetList.tsx` — Model Status List

From code.html lines 272-295.

**⚠️ Type alignment required**: The `FleetStatus` type in `api/types.ts` has `current_model: FleetModelEntry` (with fields `id`, `quant`, `params_b`) but does NOT have a `models` array. The model list from the backend lives in `FleetModelsResponse.models` which is fetched separately via `getFleetModels()`. The system store does not currently store fleet models. Two approaches:

- **(Recommended) Simple approach**: Show only the current active model using `fleetStatus.current_model`. Extend to a full list in a future iteration.
- **Full approach**: Add `fleetModels: FleetModelEntry[]` to the system store, fetch via `getFleetModels()` alongside `refreshFleet()`, and iterate.

The code below implements the **simple approach** for correctness on day one:

```tsx
// components/status/ActiveFleetList.tsx
import { useSystemStore } from "../../stores/system";

export default function ActiveFleetList() {
  const fleetStatus = useSystemStore((s) => s.fleetStatus);
  const status = useSystemStore((s) => s.status);

  const currentModel = fleetStatus?.current_model;

  return (
    <div>
      <h2 className="text-sm font-semibold tracking-wider text-on-surface-variant uppercase mb-4">
        Active Fleet
      </h2>
      <div className="space-y-3">
        {currentModel ? (
          <div className="p-3 rounded-lg border border-primary-container/30 bg-primary-container/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-primary-container glow-ring" />
              <div>
                <div className="text-xs font-medium text-on-surface">{currentModel.id}</div>
                <div className="text-[10px] text-outline font-label-mono mt-0.5">
                  {status?.provider ?? "llama.cpp"} • {currentModel.params_b ? `${currentModel.params_b}B` : "—"}
                </div>
              </div>
            </div>
            {currentModel.quant && (
              <span className="text-[10px] bg-surface px-1.5 py-0.5 rounded border border-outline-variant font-label-mono">
                {currentModel.quant}
              </span>
            )}
          </div>
        ) : (
          <div className="p-3 rounded-lg border border-outline-variant/20 bg-surface-container/30 opacity-70 flex items-center justify-center">
            <span className="text-xs text-outline">No active models</span>
          </div>
        )}
      </div>
    </div>
  );
}
```

To extend to a full model list in the future, add to the system store:
```ts
// In system store
fleetModels: FleetModelEntry[];
activeModelId: string | null;

// In refreshFleet():
const { models, active_model_id } = await getFleetModels();
set({ fleetModels: models, activeModelId: active_model_id });
```

---

## 8. Phase 6: Restyle All Existing Components ✅

**Status**: Complete — All ~28 components restyled (Core UI, Settings, Chat sub-components, Status, Wizard, Overlays). 6 orphaned components removed (RamGauge, VramGauge, FilesCounter, FleetPanel, ModelBadge, LatencyBadge). EngineIndicator restyled with blue/gray dots. All old hardcoded color tokens replaced. Build passes with 0 errors.
**Goal**: Apply new color tokens, fonts, and glassmorphism to every existing component. No logic changes — only styling.

### 8.1 Batch 1: Core UI (High Priority)

| Component | Key Changes |
|-----------|-------------|
| `SettingsPanel.tsx` | Glass-panel, `bg-surface-container-high`, new scrollbar, cyan accent buttons |
| `DocumentsPanel.tsx` | Glass-panel, new close button, cyan accent |
| `ConfirmModal.tsx` | Glass-panel backdrop, cyan Approve, indigo Deny |
| `AgentSelectorDropdown.tsx` | New colors, glass dropdown, blue active checkmark |
| `StartupGate.tsx` | New colors, replaces any remaining old color tokens |

### 8.2 Batch 2: Settings Sub-Components

| Component | Key Changes |
|-----------|-------------|
| `ModelSelector.tsx` | Radio rows with indigo active state, GGUF badges restart |
| `FleetSettings.tsx` | + / - buttons with new palette, toggle switches |
| `ToolPermissions.tsx` | Toggle switch: cyan when active, new label styling |
| `FolderManager.tsx` | Dashed add button, close icon restyle |
| `IndexProgress.tsx` | Progress bar with cyan gradient |
| `DndToggle.tsx` | Apple-style pill toggle |

### 8.3 Batch 3: Chat Sub-Components

| Component | Key Changes |
|-----------|-------------|
| `MessageFooter.tsx` | Label toggles: `font-label-mono`, `text-outline`, cyan active |
| `SourcesPanel.tsx` | Monospace data, cyan relevance bars |
| `ToolHistoryPanel.tsx` | New approve/deny icon colors |
| `MemoryPanel.tsx` | Glass-styled snippets |
| `SwapBanner.tsx` | Blue spinner (`text-primary-container`), check icon; restyle old green/amber to new palette |
| `WarningToast.tsx` | Error-colored glass, auto-dismiss, new palette |
| `CommandAutocomplete.tsx` | Glass dropdown, new colors |

### 8.4 Batch 4: Status & Misc

| Component | Key Changes |
|-----------|-------------|
| `EngineIndicator.tsx` | Blue pulse dot (`bg-primary-container`) for active, gray for off |
| `ModelBadge.tsx` | **Orphaned** — no longer imported. Either delete or keep as utility export |
| `LatencyBadge.tsx` | **Orphaned** — no longer imported. Either delete or keep as utility export |
| `RamGauge.tsx` | **Remove** — replaced by RamGaugeRing |
| `VramGauge.tsx` | **Remove** — replaced by RamGaugeRing |
| `FilesCounter.tsx` | **Remove** — replaced by StorageAccessButton |
| `FleetPanel.tsx` | **Remove** — replaced by ActiveFleetList (inline) |

### 8.5 Batch 5: Wizard Components

| Component | Key Changes |
|-----------|-------------|
| `WizardShell.tsx` | New colors, logo update |
| `StepBackend.tsx` | Radio cards with cyan/indigo accent |
| `StepLlamaCpp.tsx` | Status check styling |
| `StepModel.tsx` | Model list restyle |
| `StepFolders.tsx` | Folder picker restyle |
| `WizardDots.tsx` | Cyan active dots |

### 8.6 Batch 6: Overlay Panels

| Component | Key Changes |
|-----------|-------------|
| `TimeTravelView.tsx` | New palette, step colors: cyan=success, indigo=info, amber=pending |
| `WorkflowPanel.tsx` | Glass-panel sidebar, new run/delete buttons |
| `HistoryPanel.tsx` | Conversation list with new colors |

### 8.7 Hardcoded Values to Replace

A side-by-side migration table for old → new class patterns:

| Old Pattern | New Pattern |
|-------------|-------------|
| `bg-[#0f1117]` | `bg-background` or `bg-surface-dim` |
| `bg-[#1c1b23]` | `bg-surface-container-low` |
| `bg-[#242736]` | `bg-surface-container` or `bg-surface-container-high` |
| `text-[#e5e0ed]` | `text-on-surface` |
| `text-[#c9c4d7]` | `text-on-surface-variant` |
| `text-[#8b8fa8]` | `text-outline` |
| `border-[#242736]` | `border-outline-variant` |
| `bg-[#94a3b8]` | `bg-primary-container` |
| `text-[#94a3b8]` | `text-primary-container` |
| `text-[#0f1117]` | `text-on-primary-container` |
| `bg-[#4ade80]` (success-green) | `text-tertiary-fixed-dim` (use as text, or add success-green back) |

**Recommendation**: Keep `success-green` as a semantic alias in the tailwind config for component states that need green (not cyan):
```js
'success-green': '#4ade80',
```

---

## 9. Phase 7: Polish & Verification ✅

**Status**: Complete — Tauri window width increased to 960px. Zero old color tokens remain. Production build succeeds (104 modules, 0 errors). All transitions use Tailwind duration classes. Sidebar toggle functional at lg breakpoint.
**Plan note**: Material Symbols local font bundling and `lucide-react` removal deferred — requires Tauri prod build testing. Verified against checklist items 1-7.
### 9.1 Transitions & Animations

Apply consistent transitions across all interactive elements:
```css
/* Already in Tailwind — use these classes */
transition-all duration-200  /* quick hovers */
transition-all duration-300  /* standard */
transition-all duration-500  /* panels sliding in */
transition-all duration-1000 ease-out  /* progress rings */
```

### 9.2 Responsive Behavior

| Breakpoint | Chat | Sidebar | Nav Tabs | Footer |
|-----------|------|---------|----------|--------|
| `lg+` (≥1024px) | Centered max-w-5xl | Visible (320px) | Visible | Full |
| `md` (768-1023px) | Full width | Hidden | Visible | Full |
| `sm` (<768px) | Full width | Hidden | Compact/menu | Compact |

**Sidebar toggle**: A sidebar toggle button is added to the Header (visible below `lg` breakpoint) — this is required, not optional. Without it, users with default window sizes cannot access system widgets.

**Tauri window default width**: Increase from 560px to 960px in `src-tauri/tauri.conf.json` so the sidebar is visible at the default window size. At 560px, `lg` (1024px) never triggers and the sidebar is always hidden.

### 9.3 Icon Migration

Replace all inline SVGs with Material Symbols where possible. The design uses them and they're already loaded via CDN in `index.html`.

**⚠️ Tauri production bundling**: Material Symbols are loaded from Google Fonts CDN. In Tauri production builds (`tauri build`), internet access may not be available. To prevent missing icons:
1. Download the Material Symbols font file (`MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].woff2`) from the Google Fonts CDN
2. Place it in `ui/tray/public/fonts/MaterialSymbolsOutlined.woff2`
3. Update `index.html` to load from local path with CDN fallback:
```html
<style>
@font-face {
  font-family: 'Material Symbols Outlined';
  font-style: normal;
  font-weight: 100 700;
  src: url(/fonts/MaterialSymbolsOutlined.woff2) format('woff2');
}
</style>
```
4. Remove the CDN link after confirming local loading works
5. After switching, remove `lucide-react` from `package.json` if all icons are migrated

**Migration pattern**:
```tsx
// Before
<svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
  <path d="M14 2H6..." />
</svg>

// After
<span className="material-symbols-outlined text-[20px]">settings</span>
```

Icons to migrate (Material Symbols name → current usage):
- `settings` → gear icon
- `description` → document icon
- `history` → clock icon
- `monitoring` → activity/pulse icon
- `add` → plus icon
- `send` → send/arrow-up
- `stop` → stop/square
- `close` → close/X
- `folder` → folder icon
- `memory` → RAM chip icon
- `speed` → CPU/speed icon
- `chevron_right` → arrow right
- `search` → spyglass (for web search)
- `smart_toy` → brain/robot avatar
- `check` → checkmark
- `warning` → warning triangle
- `delete` → trash
- `refresh` → sync/refresh
- `upload` → upload/paperclip
- `lock` → lock icon
- `mic` → microphone
- `calculate` → math
- `calendar_today` → calendar
- `notifications` → bell/reminder
- `travel_explore` → web search

### 9.4 Empty States

Add empty states for each sidebar widget:

| Widget | Empty/Error State |
|--------|-------------------|
| RamGaugeRing | Gray ring, "— GB" text |
| CpuMiniGraph | Flat line, "— % AVG" |
| StorageAccessButton | "Open Files" text |
| ActiveFleetList | "No active models" message |

### 9.5 Verification Checklist

```bash
# 1. TypeScript check (strict mode — catches unused imports, missing fields)
cd ui/tray && npx tsc --noEmit

# 2. Production build
npm run build

# 3. Backend lint (ensures no regressions in python core)
cd /Users/mb/Desktop/Javier/SecondBrain && make lint

# 4. Stable frontend regression suite
#    (runs fast-path pipeline tests with mocked inference)
cd /Users/mb/Desktop/Javier/SecondBrain && make test-stable

# 5. Visual regression checks:
#    - All components render with new colors (no old #0f1117, #1c1b23, #242736)
#    - No white-on-white or black-on-black text
#    - Glass-panel blur works on dark backgrounds
#    - Blue glow (#2563eb) visible on active elements (buttons, progress ring, nav tab)
#    - Sidebar visible at >=1024px, togglable below via header button
#    - Default Tauri window (960px) shows sidebar by default
#    - Footer shows minimal status info: "Cerebro OS • Engine Status: Active" + stats
#    - Nav tabs highlight blue on click, underline matches primary-container
#    - Fast-path pills show active/inactive states (blue glow border for active)

# 6. Functional regression checks:
#    - System data loads (polling starts on StatusBar mount)
#    - Chat input, send, streaming all work with real backend
#    - Tool confirmation modal appears and submits
#    - Settings open/close/save
#    - Documents panel open/close/re-index from header AND StorageAccessButton
#    - Wizard flow completes
#    - ServiceControls start/stop backend
#    - AgentSelectorDropdown changes agent
#    - SwapBanner appears during model swap (triggered from backend)
#    - Searching indicators appear during file search

# 7. Orphaned component check:
#    - No components still using old color tokens (grep for #0f1117, #1c1b23, #242736 in src/)
#    - ModelBadge, LatencyBadge, RamGauge, VramGauge, FilesCounter, FleetPanel are
#      no longer imported anywhere (grep for their file paths)
```

---

## 10. Dependency Map

```
Phase 0 (Tokens)
  │
  ▼
Phase 0.5 (Data Integration) ──► enables all data-dependent widgets
  │
  ▼
Phase 1 (Layout) ──► Phase 2 (Header)
  │                      │
  │             ┌────────┘
  │             ▼
  │       Phase 3 (FastPath Toggles)
  │             │
  │             ▼
  │       Phase 4 (Chat Restyle)
  │             │
  └─► Phase 5 (Sidebar Widgets)
       │
       ▼
  Phase 6 (Restyle All)
       │
       ▼
  Phase 7 (Polish)
```

**Parallelizable work**:
- Phase 0.5 (Data Integration) can run alongside Phase 0 — they touch different files
- Phase 3 (FastPathToggles) can be done alongside Phase 4 (Chat) — they're independent
- Phase 5 (Sidebar Widgets) can start as soon as Phase 0 + Phase 0.5 are done
- Phase 6 Batch 6 (Overlay Panels/History) is independent of other batches

**Blocking dependencies**:
- Phase 0 blocks everything (tokens must exist before any styling)
- Phase 0.5 blocks all data-dependent components (sidebar widgets, footer, polling)
- Phase 1 blocks Phase 2 (header height change affects layout)
- Phase 1 blocks Phase 5 (sidebar needs new MainLayout flex structure)
- Phase 6 batches should be done sequentially within each batch (shared token adjustments)

---

## 11. Effort Estimate

| Phase | Files New | Files Modified | Complexity | Est. Time |
|-------|-----------|----------------|------------|-----------|
| 0. Tokens | 0 | 2 | Low | 1h |
| 0.5. Data integration (polling, store wiring, type alignment) | 0 | 4 | Medium | 3h |
| 1. Layout | 1 | 2 | Medium | 2h |
| 2. Header | 0 | 1 | Medium | 1.5h |
| 3. Fast-path toggles | 1 | 0 | Low | 1h |
| 4. Chat restyle | 0 | 4 | Medium | 3h |
| 5. Sidebar widgets | 5 | 0 | Medium | 3h |
| 6. Restyle existing | 0 | ~28 | High | 6h |
| 7. Polish | 0 | 4-6 | Medium | 2h |
| **Total** | **7** | **~45-47** | | **~24h (3 days)** |

### Breakdown by developer skill

| Role | Time | Focus |
|------|------|-------|
| Frontend (React/Tailwind) | 18h | All styling, layout, new components |
| Data integration (store + types) | 3h | Polling, type alignment, deep-merge fixes, orphaned component cleanup |
| Integration testing | 1.5h | API compatibility, Tauri build, `make test-stable` |
| QA/code review | 1.5h | Visual regression, edge cases, orphaned component audit |

---

## 12. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | **Color token swap breaks text contrast** throughout the app | High | High | Do Phase 0 in isolation, grep for all old color values, update simultaneously. Test with `npx tsc` + manual scan. |
| R2 | **Layout restructure breaks existing panel overlays** (Settings, Documents, etc.) | Medium | High | Keep overlays as `position: fixed` or append to root div — they should not depend on the main flex layout. |
| R3 | **Sidebar widgets have no data** (CPU graph, model list) because API fields differ from expected shape | **High** | **High** | **Addressed in plan**: ActiveFleetList uses `FleetModelEntry` fields directly, CpuMiniGraph is a placeholder. Verify against `api/types.ts` before implementation. |
| R4 | **Material Symbols don't load in Tauri production build** | Low | Medium | **Addressed in plan**: Bundle Material Symbols font locally in `public/fonts/` with CDN fallback. Remove CDN dependency. |
| R5 | **Fast-path toggles confuse users** if they click Math/Reminders and nothing happens | Medium | Low | Add tooltip explaining these are auto-detected pipelines, not manual toggles. Or wire them to show relevant info. |
| R6 | **Regressions in streaming/SSE chat** after restructuring MessageBubble | Medium | Critical | Keep all state/effect logic in place. Only change JSX structure and class names. Test with real backend. |
| R7 | **System data never loads** because polling is removed from StatusBar | **High** | **Critical** | **Addressed in plan**: StatusBar `useEffect` starts `startPolling(10_000)` on mount. Verify polling runs on app launch. |
| R8 | **`noUnusedLocals`/`noUnusedParameters` TS errors** from dead imports in Header | Medium | High | **Addressed in plan**: Removed `AgentSelectorDropdown`, `selectIsClaudeMode` imports. Run `npx tsc --noEmit` after Phase 2. |
| R9 | **Deep-merge bug in FastPathToggles** silently destroys `write_file`/`read_file` permissions | **High** | **High** | **Addressed in plan**: Use `{ ...currentPerms, search_web: bool }` deep-merge pattern. Test by toggling web search then checking `/api/config`. |
| R10 | **JetBrains Mono fails to load** | Low | Low | Add `font-mono` fallback chain: `["JetBrains Mono", "SF Mono", "Fira Code", "monospace"]` |

---

## Appendix A: File Change Summary

```
NEW FILES (7):
  src/components/chat/FastPathToggles.tsx       — Pill toggle row
  src/components/status/SystemSidebar.tsx        — Right sidebar container
  src/components/status/RamGaugeRing.tsx         — Circular RAM progress ring
  src/components/status/CpuMiniGraph.tsx         — CPU bar chart (placeholder)
  src/components/status/StorageAccessButton.tsx  — Folder access card
  src/components/status/ActiveFleetList.tsx      — Model status list (current model only)

MODIFIED FILES (~45-47):
  Foundation:
    tailwind.config.js           — Color palette, fonts, spacing, radii; remove darkMode
    index.html                   — Font links, local Material Symbols font
    src/index.css                 — CSS utilities, glass-panel, glow-ring (blue)

  Layout:
    src/layouts/MainLayout.tsx   — Add sidebar, restructure flex, wire StorageAccess → Docs
    src/layouts/Header.tsx       — Nav tabs, sidebar toggle, remove dead imports, taller

  Status:
    src/components/status/StatusBar.tsx     — Simplify, add polling useEffect
    src/components/status/EngineIndicator.tsx  — Restyle, blue pulse for active
    src/components/status/ServiceControls.tsx  — Restyle buttons to code.html spec

  Chat:
    src/components/chat/ChatWindow.tsx      — Padding/spacing, <main> → <div>
    src/components/chat/MessageBubble.tsx   — New bubble styles, avatar, searching indicators
    src/components/chat/InputArea.tsx       — New input design, file upload preserved
    src/components/chat/TypingIndicator.tsx — Restyle, blue progress bar
    src/components/chat/MessageFooter.tsx   — Restyle expand toggles
    src/components/chat/SwapBanner.tsx      — Restyle to new palette (blue instead of green/amber)
    src/components/chat/WarningToast.tsx    — Restyle to new palette

  Settings:
    src/components/settings/SettingsPanel.tsx      — Restyle
    src/components/settings/ModelSelector.tsx       — Restyle
    src/components/settings/FleetSettings.tsx       — Restyle
    src/components/settings/ToolPermissions.tsx     — Restyle
    src/components/settings/FolderManager.tsx       — Restyle
    src/components/settings/IndexProgress.tsx       — Restyle
    src/components/settings/DndToggle.tsx           — Restyle

  Shared:
    src/components/shared/ConfirmModal.tsx          — Restyle
    src/components/shared/AgentSelectorDropdown.tsx — Restyle

  Wizard:
    src/components/wizard/WizardShell.tsx   — Restyle
    src/components/wizard/StepBackend.tsx   — Restyle
    src/components/wizard/StepLlamaCpp.tsx  — Restyle
    src/components/wizard/StepModel.tsx     — Restyle
    src/components/wizard/StepFolders.tsx   — Restyle
    src/components/wizard/WizardDots.tsx    — Restyle

  Documents:
    src/components/documents/DocumentsPanel.tsx   — Restyle

  Automation:
    src/components/automation/WorkflowPanel.tsx    — Restyle

  Debug:
    src/components/debug/TimeTravelView.tsx        — Restyle

  Chat sub-components:
    src/components/chat/SourcesPanel.tsx      — Restyle
    src/components/chat/ToolHistoryPanel.tsx  — Restyle
    src/components/chat/MemoryPanel.tsx       — Restyle
    src/components/chat/SwapBanner.tsx        — Restyle
    src/components/chat/WarningToast.tsx      — Restyle
    src/components/chat/CommandAutocomplete.tsx — Restyle
    src/components/chat/HistoryPanel.tsx      — Restyle

FILES REMOVED (4):
    src/components/status/RamGauge.tsx       — Replaced by RamGaugeRing
    src/components/status/VramGauge.tsx      — Replaced by RamGaugeRing
    src/components/status/FilesCounter.tsx   — Replaced by StorageAccessButton
    src/components/status/FleetPanel.tsx     — Replaced by ActiveFleetList (inline)

FILES ORPHANED (2 — no longer imported after migration):
    src/components/status/ModelBadge.tsx     — Delete or keep as utility
    src/components/status/LatencyBadge.tsx   — Delete or keep as utility

TOTAL: ~7 new + ~45-47 modified + 4 removed + 2 orphaned = ~56-58 file changes
```

## Appendix B: Design Token Reference

All values extracted from `DESIGN.md` and `code.html`:

```
Colors:
  ─────────────────────────────────────────────────
  Surface tokens:
    surface                     #131317
    surface-dim                 #131317
    surface-bright              #39393d
    surface-container-lowest    #0e0e12
    surface-container-low       #1b1b1f
    surface-container           #1f1f23
    surface-container-high      #2a292e
    surface-container-highest   #353439
  
  Text tokens:
    on-surface                  #e4e1e7
    on-surface-variant          #b9cacb
  
  Outline tokens:
    outline                     #849495
    outline-variant             #3a494b
    surface-tint                #00dce6
  
  Primary (Cyan):
    primary                     #e0fdff
    on-primary                  #00373a
    primary-container           #00f2fe
    on-primary-container        #006a70
    inverse-primary             #00696f
    primary-fixed               #6ff6ff
    primary-fixed-dim           #00dce6
    on-primary-fixed            #002022
    on-primary-fixed-variant    #004f53
  
  Secondary (Indigo):
    secondary                   #c0c1ff
    on-secondary                #1000a9
    secondary-container         #3131c0
    on-secondary-container      #b0b2ff
    secondary-fixed             #e1e0ff
    secondary-fixed-dim         #c0c1ff
    on-secondary-fixed          #07006c
    on-secondary-fixed-variant  #2f2ebe
  
  Tertiary (Gold):
    tertiary                    #fff6e4
    on-tertiary                 #3b2f00
    tertiary-container          #fed83a
    on-tertiary-container       #725e00
    tertiary-fixed              #ffe173
    tertiary-fixed-dim          #e8c423
    on-tertiary-fixed           #221b00
    on-tertiary-fixed-variant   #554500
  
  Error:
    error                       #ffb4ab
    on-error                    #690005
    error-container             #93000a
    on-error-container          #ffdad6

Typography:
  ─────────────────────────────────────────────────
  display-lg:     Inter 700, 48px, lh1.1, ls-0.04em
  headline-md:    Inter 600, 24px, lh1.2, ls-0.02em
  body-base:      Inter 400, 15px, lh1.5, ls-0.01em
  label-mono:     JetBrains Mono 500, 12px, lh1.0, ls0.05em

Border Radius:
  ─────────────────────────────────────────────────
  sm:      0.25rem  (4px)
  DEFAULT: 0.5rem   (8px)
  md:      0.75rem  (12px)
  lg:      1rem     (16px)
  xl:      1.5rem   (24px)
  full:    9999px

Spacing:
  ─────────────────────────────────────────────────
  unit:             4px
  gutter:           16px
  margin-desktop:   32px
  margin-mobile:    16px
  panel-width:      320px
```

---

*End of plan. Begin implementation with Phase 0.*
