> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Dashboard Redesign — Plan de Implementación Modular

**Propósito**: Transformar Cerebro de un chat-centric UI a un dashboard tipo "sistema operativo inteligente" (inspirado en Raycast + Obsidian). El chat pasa de ser la pantalla principal a una herramienta más, invocada desde acciones.

> **Nuevo**: El dashboard incluye un CTA prominente "Quick Chat" que permite a usuarios que solo quieren un chat tipo ChatGPT/Claude saltarse el dashboard y abrir la interfaz de chat actual (AgentBar + ChatWindow) con un solo clic.

---

## Estado de implementación — ✅ COMPLETADO (Jun 2026)

Todas las fases (0–5) están implementadas y compilan sin errores. 12 archivos nuevos, 7 modificaciones.

---

## Arquitectura implementada

```
App (ErrorBoundary)
├── WizardShell (first launch)
└── MainLayout
    ├── Header (sin cambios relevantes)
    ├── LeftSidebar (home icon como primer tab)
    ├── Center Content (based on activeTab):
    │   ├── home     → DashboardHome  ← NUEVO (default)
    │   ├── chat     → AgentBar + ChatWindow
    │   ├── tools    → ToolsPanel
    │   ├── code     → CodePanel
    │   └── sources  → SourcesView
    ├── SystemSidebar
    └── StatusBar
```

---

## Fase 0 — Foundation ✅

### 0.1 Añadir tab "home" al tipo `LeftTab`

**Archivo**: `src/stores/tab.ts`

- `LeftTab = "home" | "chat" | "tools" | "code" | "sources"`
- `activeTab` por defecto: `"home"`

### 0.2 Añadir sidebar item "home"

**Archivo**: `src/layouts/LeftSidebar.tsx`

- Primer elemento del array: `{ id: "home", icon: "home", labelKey: "sidebar.home" }`
- Orden: home → chat → sources → tools → code

### 0.3 Añadir i18n keys

**Archivo**: `src/locales/en.json` y `src/locales/es.json`

~20 keys añadidas: `sidebar.home`, `dashboard.title`, `dashboard.subtitle`, `dashboard.quick_chat`, `dashboard.quick_chat_desc`, `dashboard.files`, `dashboard.memories`, `dashboard.events`, `dashboard.web`, `dashboard.connected`, `dashboard.disconnected`, `dashboard.search_files`, `dashboard.analyze_folder`, `dashboard.create_workflow`, `dashboard.recent_activity`, `dashboard.no_activity`, `dashboard.loading`, `dashboard.total_queries`, `dashboard.avg_latency`, `dashboard.indexed_items`.

---

## Fase 1 — Dashboard Store ✅

### 1.1 Store `stores/dashboard.ts`

```ts
import { create } from "zustand";
import { getStatus, listConversations } from "../api/client";
import type { ConversationSummary, StatusResponse } from "../api/types";

export interface RecentActivity {
  id: string;
  label: string;
  description: string;
  timestamp: Date;
  icon: string;
  tab?: "chat" | "sources" | "tools" | "code";
}

interface DashboardState {
  status: StatusResponse | null;
  recentActivity: RecentActivity[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  status: null,
  recentActivity: [],
  loading: true,
  error: null,

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const [status, conversations] = await Promise.all([
        getStatus(),
        listConversations().catch(() => [] as ConversationSummary[]),
      ]);

      const activity: RecentActivity[] = [];

      if (status.indexed_files > 0) {
        activity.push({
          id: "indexed",
          label: `Knowledge base: ${status.indexed_files} files indexed`,
          description: "Available for search and context",
          timestamp: new Date(),
          icon: "database",
          tab: "sources",
        });
      }

      for (const conv of conversations.slice(0, 5)) {
        activity.push({
          id: `conv-${conv.conv_id}`,
          label: conv.first_user_message ?? "Chat conversation",
          description: `Agent: ${conv.agent_id} · ${conv.message_count} messages`,
          timestamp: new Date(conv.last_active),
          icon: "chat",
          tab: "chat",
        });
      }

      set({ status, recentActivity: activity, loading: false });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load", loading: false });
    }
  },
}));
```

### 1.2 Integración en `App.tsx`

```ts
import { useDashboardStore } from "./stores/dashboard";

// Dentro del useEffect de App:
useDashboardStore.getState().refresh();
```

Se ejecuta al mount, después de `startPolling()` y `loadSettings()`.

---

## Fase 2 — DashboardHome Component ✅

### 2.1 `components/dashboard/DashboardHome.tsx`

Componente principal con 4 secciones verticales dentro de un scroll container:

```
┌─────────────────────────────────────┐
│         CEREBRO                     │
│   Your Intelligent Operating System │
│                                     │
│   ┌─────────────────────────────┐   │
│   │  💬 Quick Chat              │   │  ← CTA hero
│   └─────────────────────────────┘   │
│                                     │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌───┐ │
│   │📁 12k │ │🧠 300 │ │📅 5  │ │🌐 │ │
│   │Files  │ │Mem's  │ │Events│ │Web│ │
│   └──────┘ └──────┘ └──────┘ └───┘ │
│                                     │
│   ┌──────────────────────────────┐  │
│   │  What do you need?           │  │
│   │  [Search Files] [Workflow]   │  │
│   │  [Analyze Folder]            │  │
│   └──────────────────────────────┘  │
│                                     │
│   Recent Activity                   │
│   ┌──────────────────────────────┐  │
│   │ • Knowledge base: 12k files  │  │
│   │ • Chat conversation          │  │
│   │ • ...                        │  │
│   └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

- Hero: título + subtítulo
- QuickChatCard: CTA a chat
- Stats row: 4 StatCards (Files, Memories, Events, Web)
- Action cards: "Search Files" (se deshabilita si `indexed_files === 0`), "Analyze Folder", "Create Workflow"
  - **Nota (Jun 2026):** "Search Files" ahora abre `SearchDocumentsDialog` en lugar de navegar a `sources`. Ver [`dashboard-search-documents.md`](../dashboard-search-documents.md).
- Recent Activity: ActivityList con datos reales del store

Incluye animación stagger fade-in (clases `stagger-1` a `stagger-5`).

### 2.2 Sub-componentes

#### `StatCard.tsx`
Props: `icon`, `label`, `value`, `color`. Renderiza tarjeta con icono Material Symbols + valor bold grande + etiqueta pequeña.

#### `ActionCard.tsx`
Props: `icon`, `label`, `description`, `onClick`, `disabled?`. Botón tipo card con hover states. Cuando `disabled=true`: opacidad 40%, cursor not-allowed, sin hover effects.

#### `QuickChatCard.tsx`
Props: `onClick`. CTA hero con gradient background, glow en hover, icono chat grande, flecha animada. Un clic → navega al tab "chat".

#### `ActivityList.tsx`
Props: `activities`, `onActivityClick?`. Lista con icono, label, descripción truncada, timestamp relativo. Empty state con mensaje i18n si no hay actividades.

#### `DashboardSkeleton.tsx`
Skeleton loading con `animate-pulse`. Misma estructura visual que DashboardHome.

#### `DashboardError.tsx`
Props: `message`, `onRetry`. Icono warning + mensaje + botón Retry.

### 2.3 Utilidad `utils/time.ts`

```ts
export function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diff = now - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

---

## Fase 3 — Layout Integration ✅

### 3.1 `MainLayout.tsx`

Importa `DashboardHome` y lo renderiza como primer caso del switch:

```tsx
{activeTab === "home" ? (
  <DashboardHome />
) : activeTab === "tools" ? (
  <ToolsPanel />
) : activeTab === "code" ? (
  <CodePanel />
) : activeTab === "sources" ? (
  <SourcesView />
) : (
  <div className="flex-1 flex flex-col px-4 md:px-6 lg:px-8 pt-2 pb-6 w-full min-w-0 min-h-0">
    <AgentBar />
    <ChatWindow className="flex-1 min-h-0" />
  </div>
)}
```

### 3.2 Animación de entrada

En `index.css`:

```css
@keyframes dashboard-enter {
  0% { opacity: 0; transform: translateY(8px); }
  100% { opacity: 1; transform: translateY(0); }
}
.dashboard-enter {
  animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.stagger-1 { animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; animation-delay: 0.05s; }
.stagger-2 { animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; animation-delay: 0.12s; }
.stagger-3 { animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; animation-delay: 0.20s; }
.stagger-4 { animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; animation-delay: 0.28s; }
.stagger-5 { animation: dashboard-enter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; animation-delay: 0.36s; }
```

Aplicado al contenedor principal de `DashboardHome` y a cada sección vía clases `stagger-N`.

---

## Fase 4 — Recent Activity Enriched ✅

### 4.1 Conversaciones reales

`refresh()` en `stores/dashboard.ts` usa `Promise.all` para llamar `getStatus()` y `listConversations()` en paralelo:

- `listConversations()` con `.catch(() => [])` — no rompe el dashboard si falla
- Activity items desde indexed_files (icono `database`, tab `sources`)
- Últimas 5 conversaciones (icono `chat`, tab `chat`)

### 4.2 Activity tracking local

No implementado (quedó como mejora futura en el plan original).

---

## Fase 5 — Polish & Edge Cases ✅

### 5.1 Estados vacíos

- **Sin archivos indexados**: ActionCard "Search Files" se renderiza con `disabled=true` → opacidad reducida, cursor not-allowed, sin hover effects.
- **Sin conversaciones**: ActivityList muestra empty state "No recent activity yet".
- **Error de conexión**: DashboardError con icono warning + mensaje + botón Retry.

### 5.2 Responsive

- Stats grid: `grid-cols-2 md:grid-cols-4`
- Action cards: `grid-cols-1 sm:grid-cols-2`
- Padding: `px-6 md:px-10 lg:px-12`
- Sin scroll horizontal (`overflow-y-auto`, contenedores `min-w-0`)

### 5.3 Performance

- `refresh()` solo cuando el tab está activo (vía useEffect en DashboardHome)
- Status cacheado en el store — no hay flicker al navegar
- Sub-componentes sin estado interno, puros

### 5.4 Animaciones

- Stagger fade-in de 5 secciones con `animation-delay` incremental (0.05s–0.36s)
- Action cards: hover con border glow + `active:scale-[0.98]`
- QuickChatCard: glow en hover + flecha animada
- Sidebar home: tooltip "Home"/"Inicio" via `aria-label` + hover div

---

## Resumen de archivos creados/modificados

| Archivo | Acción | Fase | Estado |
|---------|--------|------|--------|
| `src/stores/tab.ts` | Modificar: añadir "home" a LeftTab, default "home" | 0.1 | ✅ |
| `src/layouts/LeftSidebar.tsx` | Modificar: añadir item "home" | 0.2 | ✅ |
| `src/locales/en.json` | Modificar: ~20 dashboard keys | 0.3 | ✅ |
| `src/locales/es.json` | Modificar: ~20 dashboard keys (traducidas) | 0.3 | ✅ |
| `src/stores/dashboard.ts` | **Crear**: store con status + recentActivity | 1 | ✅ |
| `src/App.tsx` | Modificar: refresh() en mount | 1.2 | ✅ |
| `src/components/dashboard/DashboardHome.tsx` | **Crear**: componente principal | 2 | ✅ |
| `src/components/dashboard/StatCard.tsx` | **Crear**: tarjeta de métrica | 2.2 | ✅ |
| `src/components/dashboard/ActionCard.tsx` | **Crear**: tarjeta de acción (con disabled) | 2.2 | ✅ |
| `src/components/dashboard/QuickChatCard.tsx` | **Crear**: CTA hero | 2.2 | ✅ |
| `src/components/dashboard/ActivityList.tsx` | **Crear**: lista de actividad reciente | 2.2 | ✅ |
| `src/components/dashboard/DashboardSkeleton.tsx` | **Crear**: skeleton loading state | 2.2 | ✅ |
| `src/components/dashboard/DashboardError.tsx` | **Crear**: error state con retry | 2.2 | ✅ |
| `src/utils/time.ts` | **Crear**: formatRelativeTime() | 2.3 | ✅ |
| `src/layouts/MainLayout.tsx` | Modificar: case "home" → DashboardHome | 3 | ✅ |
| `src/index.css` | Modificar: dashboard-enter + stagger classes | 3.2 | ✅ |
| `src/stores/activity.ts` | **Crear** (opcional): local activity tracking | 4.2 | ❌ No implementado |

Total: **12 archivos nuevos**, **7 modificaciones**, **1 pendiente opcional**.

---

## Notas técnicas importantes (post-implementación)

1. **SystemSidebar no se tocó** — correcto, sigue accesible desde cualquier tab.

2. **StatusBar no se tocó** — engine status, RAM, uptime visibles desde el dashboard.

3. **El chat no desapareció** — dejó de ser el default. El icono de chat en la sidebar y QuickChatCard lo invocan.

4. **`listConversations()` con fallback** — `.catch(() => [])` evita que el dashboard se rompa si el backend no implementa el endpoint.

5. **La build compila** — `npm run build` pasa con 0 errores nuevos (los 5 errores existentes son pre-91 en archivos no relacionados: `FastPathToggles`, `InputArea`, `MessageBubble`, `StatusBar.test`).

6. **Animación de entrada** — `dashboard-enter` + `stagger-N` clases en el contenedor principal y cada sección. Transición suave al navegar al dashboard.
