# Frontend Refactor Plan

Problemas detectados en el frontend (`ui/tray/src/`), organizados por prioridad.

---

## P1 — Código Muerto (eliminar) ✅ DONE

### `AgentSelectorDropdown.tsx` — duplicado muerto

- **Archivo:** `ui/tray/src/components/shared/AgentSelectorDropdown.tsx`
- **Problema:** Componente completo nunca se importa. `AgentBar.tsx` es el que se usa realmente.
- **Acción:** Archivo eliminado.

### `HistoryPanel.tsx` + `stores/history.ts` — componente nunca renderizado

- **Archivo:** `ui/tray/src/components/chat/HistoryPanel.tsx`, `ui/tray/src/stores/history.ts`
- **Problema:** Componente nunca renderizado. Store sin consumidores (solo el test y el panel).
- **Acción:** Eliminados `HistoryPanel.tsx`, `stores/history.ts`, `stores/history.test.ts`.

### `StartupGate.tsx` — wrapper sin lógica

- **Archivo:** `ui/tray/src/components/shared/StartupGate.tsx`
- **Problema:** Hacía `return children`. No agregaba valor.
- **Acción:** Eliminado `StartupGate.tsx`, `StartupGate.test.tsx`. Limpiado import y wrapper en `App.tsx`.

### `selectRamPressure()` / `selectSwapInProgress()` — selectores sin consumidores

- **Archivo:** `ui/tray/src/stores/system.ts`
- **Problema:** Funciones exportadas, cero componentes las importaban.
- **Acción:** Eliminadas líneas 75-83 del archivo original.

### Tab type `"fleet"` — definido sin ruta de renderizado

- **Archivo:** `ui/tray/src/stores/tab.ts`
- **Problema:** `LeftTab` incluía `"fleet"` pero nadie lo asignaba ni renderizaba.
- **Acción:** Eliminado `"fleet"` del union type.

### CSS muerto en `index.css`

- **Archivo:** `ui/tray/src/index.css`
- **Problema:** `.glow-ring-indigo`, `.glow-ring-gold`, `.glow-ring-cyan`, `.glass-panel-hover` no referenciados en ningún componente.
- **Acción:** Eliminadas las 4 clases. Preservado `.glow-ring` (usado en `ActiveFleetList.tsx`) y `.glass-panel` (usado en `SystemSidebar.tsx`).

---

## P2 — Duplicación (unificar) ✅ DONE (parcial — P2.4 pendiente)

### Selector de agente duplicado ✅

- **Archivos:** `AgentBar.tsx` vs `AgentSelectorDropdown.tsx`
- **Acción:** `AgentSelectorDropdown.tsx` eliminado en P1. Solo queda `AgentBar.tsx`.

### Toggle switch — 4 reimplementaciones ✅

- **Archivos:**
  - `DndToggle.tsx` — usa `ToggleSwitch` con `className="bg-background"` + `knobClassName="shadow"`
  - `ToolPermissions.tsx` — usa `ToggleSwitch` con `className="bg-background"`
  - `KnowledgeSyncPanel.tsx` — usa `ToggleSwitch` con `className="bg-outline/30"` + `knobClassName="shadow-sm"`
  - `ToolsPanel.tsx` — usa `ToggleSwitch` con `size="sm"` + `className="bg-surface-container-highest"`
- **Acción:** Extraído `components/shared/ToggleSwitch.tsx` con props: `enabled`, `onChange`, `size` ("sm" | "md"), `ariaLabel`, `className` (off track color), `knobClassName` (shadow, etc.). Reemplazadas las 4 implementaciones.

### Folder picker duplicado ✅

- **Archivos:** `FolderManager.tsx` vs `StepFolders.tsx`
- **Acción:** Extraído `components/shared/FolderList.tsx` con props: `folders`, `onAdd`, `onRemove`, `minFoldersMessage`. Ambos consumidores actualizados para usarlo. Cada uno mantiene su lógica de estado/backend.

### `CLAUDE_MODELS` definido dos veces ⏳ PENDIENTE

- **Archivos:** `SettingsPanel.tsx` líneas 228-233 y `api/types.ts` líneas 398-401
- **Problema:** Datos y estructuras diferentes. No se puede unificar sin romper un consumidor.
- **Acción:** Pendiente — requiere decisión de producto sobre qué modelos mostrar.

### Toast/dialog — 3 patrones distintos ✅

- **Archivos:**
  - `WarningToast.tsx` — refactorizado para usar `Toast` compartido, mantiene estado `visible` local
  - `Header.tsx` — refactorizado para usar `Toast` con `fixed bottom-4 right-4` positioning
  - `FastPathToggles.tsx` — `QuickNoteDialog` extraído a su propio archivo usando `Dialog` compartido
- **Acción:** Creados `components/shared/Toast.tsx` (auto-dismiss, role="alert", dismiss button customizable) y `components/shared/Dialog.tsx` (overlay + modal wrapper). `QuickNoteDialog` extraído a `components/chat/QuickNoteDialog.tsx`.

---

## P3 — Componentes Monstruo (refactorizar) ✅ DONE (parcial — useQueryDispatch pendiente)

### `InputArea.tsx` — 714 → 598 líneas ✅

- **Acción:**
  - ✅ Extraído `utils/fileProcessing.ts` — constants + pure functions (`hasExtension`, `isTextLikeFile`, `isImageLikeFile`, `readFileAsDataUrl`, `resizeImage`, `buildLocalAttachment`)
  - ⏳ `hooks/useQueryDispatch.ts` — PENDIENTE (riesgo alto de romper flujo query)
  - ❌ `FilePreview.tsx` — no creado (componente no tenía preview de archivos)
- **Impacto:** InputArea bajó de 714 a 598 líneas. Sin cambios de comportamiento.

### `SourcesView.tsx` — 723 → 189 líneas ✅

- **Acción:**
  - ✅ Extraído `hooks/useKnowledgeSync.ts` — toda la lógica de estado, CRUD, localStorage, sync, export/import
  - ✅ Extraído `components/settings/SourceList.tsx` — listado de sources con expand, sync, remove
  - ✅ Extraído `components/settings/SourceForm.tsx` — formulario de alta con type selector, URL, tags, schedule
- **Impacto:** SourcesView bajó de 723 a 189 líneas (orquestador delgado que usa hook + componentes).

### `SettingsPanel.tsx` — 430 → 227 líneas ✅

- **Acción:**
  - ✅ Extraído `components/settings/ClaudeApiKeySection.tsx` — manejo de API key con localStorage offline-first
  - ✅ Extraído `components/settings/ClaudeModelSection.tsx` — lista de modelos Claude
- **Impacto:** SettingsPanel bajó de 430 a 227 líneas.

### `CodePanel.tsx` — 487 → 56 líneas ✅

- **Acción:**
  - ✅ Extraído `components/code/TerminalTab.tsx` — terminal xterm.js + fallback shell
  - ✅ Extraído `components/code/OutputTab.tsx` — tool calls output
  - ✅ Extraído `components/code/ScratchTab.tsx` — scratchpad con store persistente
- **Impacto:** CodePanel bajó de 487 a 56 líneas (solo tab bar + activeTab state).

---

## P4 — Error States Faltantes ✅ DONE

| Componente | Acción |
|---|---|
| `CpuMiniGraph` | ✅ Añadido early return `if (!status)` con skeleton "Waiting for data…" |
| `RamGaugeRing` | ✅ Añadido early return `if (!status)` con "Connecting…" pulse |
| `ActiveFleetList` | ✅ Añadido check `llamaCppLoading` con spinner antes del empty state "No models available" |
| `FleetSettings` | ✅ Añadido estado `modelsLoading` con spinner mientras se resuelve `getFleetModels()` |
| `QuickNoteDialog` | ✅ Añadido `error` state en catch — muestra mensaje de error en el dialog |
| `StorageAccessButton` | ✅ Añadido check `!status` → muestra "Connecting…" en vez de "0 files" |
| `EngineIndicator` | ✅ Confirmado que ya maneja todos los estados relevantes (up/down/restarting/suspended/off/claude) |
| `ClaudeApiKeySection` | ✅ Añadido `initialLoading` state — spinner + "Checking backend…" mientras se resuelven las llamadas iniciales. `backendOk` cambiado a `boolean \| null` para distinguir "no checked" de "offline". |

---

## P5 — Inconsistencias ✅ DONE (parcial — P5.2 pendiente)

### Idioma mezclado ✅

- **Acción:** Estandarizado a inglés en:
  - `ToolsPanel.tsx`: traducción de QUICK_ACTIONS (Search Files, Create Note, Run Workflow, Search Web, Day Events, Spotlight)
  - `TerminalTab.tsx`: traducción de toda la UI (terminal init, error, commands list, placeholder, run button)
  - `OutputTab.tsx`: traducción de empty state, tool result labels (No tools executed yet, Executed, Denied, No result)
  - `ScratchTab.tsx`: traducción de descripción, placeholder, line count, copy/clear buttons

### Nombres de API inconsistentes ⏳ PENDIENTE

- **Problema:** Requiere grep+rename de ~40 funciones. Dejado para análisis aparte.
- **Acción:** Pendiente.

### `RamMargin` en FleetSettings — UI fantasma ✅

- **Acción:** Eliminado el bloque JSX de control de RAM margin y el estado `ramMargin`. Los botones `+`/`-` no tenían efecto en el backend.

### `_onOpenSettings` prop no usado ✅

- **Acción:** Eliminada la prop de `LeftSidebarProps`, del parámetro de `LeftSidebar()`, y de la llamada `<LeftSidebar />` en `MainLayout.tsx`. `handleOpenSettings` sigue existiendo y usándose por `Header.tsx`.

### `RamGaugeRing` props definidas pero no usadas desde afuera ✅

- **Acción:** Eliminadas props `used` y `total` de la interfaz y del destructuring. El componente ahora lee directamente del store.

---

## P6 — Strings Hardcodeados

### Backend URL

- **Archivo:** `ui/tray/src/api/client.ts` línea 40
- **Código:** `const BASE = "http://localhost:7842"`
- **Problema:** Puerto y host hardcodeados.
- **Acción:** Cambiar a `import.meta.env.VITE_CEREBRO_API_URL ?? "http://localhost:7842"`.

### Mensajes de terminal en UI desktop

| Archivo | Línea | Texto |
|---|---|---|
| `InputArea.tsx` | 433 | `"Cannot reach the backend. Make sure \`make run\` is running on port 7842."` |
| `services.ts` | 102 | `"Turn off from Terminal: make desktop-stop"` |
| `services.ts` | 81 | `"Turn on from Terminal: make desktop-launch"` |
| `services.ts` | 55 | `"Backend did not respond in time. See ~/.cerebro/logs/"` |

- **Problema:** Instrucciones de desarrollo (comandos `make`, rutas a logs) visibles en app desktop.
- **Acción:** Cambiar a mensajes user-friendly: "Backend not responding. Try restarting from the tray menu." o similar. Mover los comandos a tooltips/detalles expandibles.

### Polling intervals esparcidos

- **Problema:** `10_000`, `2_000`, `1_000`, `4_000`, `6_000`, `1_500` — 6 valores distintos en 8 ubicaciones, sin constantes compartidas.
- **Acción:** Centralizar en `constants.ts`: `POLL_INTERVAL`, `HEALTH_POLL_INTERVAL`, `TOAST_DURATION`, etc.

### Supported file types

- **Archivo:** `InputArea.tsx` líneas 599-608
- **Problema:** Array inline de tipos MIME permitidos.
- **Acción:** Mover a `constants.ts`.

---

## P7 — Complejidad Innecesaria

### Doble collapse en SystemSidebar

- **Archivo:** `SystemSidebar.tsx` + `RamGaugeRing.tsx`
- **Problema:** `SystemSidebar` tiene su propio collapse que reduce a un ícono de RAM. `RamGaugeRing` tiene otro collapse interno que esconde detalles. Dos niveles de anidamiento visual confuso.
- **Acción:** Unificar collapse en `SystemSidebar`, que `RamGaugeRing` sea siempre compacto o siempre detallado según el padre.

### Wizard salta steps en modo Claude

- **Archivo:** `ui/tray/src/components/wizard/WizardShell.tsx` línea 83
- **Problema:** Cuando `mode === "claude"`, step 0 → step 3. `StepFolders` en este modo llama `wizardSetFolders + wizardComplete` asumiendo que es el último paso. Lógica no obvia.
- **Acción:** Hacer el flujo explícito en el store `wizard.ts` con un `completionSteps` map en vez de jumps condicionales.

---

## P8 — Tipo `AgentId` inconsistente con backend

- **Archivo:** `ui/tray/src/api/types.ts` línea 252 + `api/client.ts` líneas 32-38
- **Problema:** Frontend usa `AgentId = "auto" | "general" | "thesis" | "code" | "calendar"`, y el map `AGENT_ID_MAP` traduce a `"general-v1"`, `"academic-v1"`, etc. Esta capa de traducción añade complejidad sin beneficio claro.
- **Acción:** Simplificar: que `AgentId` use directamente los mismos IDs que el backend (`"auto"`, `"general-v1"`, `"academic-v1"`, `"code-v1"`, `"calendar-v1"`) y eliminar `AGENT_ID_MAP`.

---

## Resumen de Acciones

| Prioridad | Count | Tipo |
|---|---|---|
| P1 — Eliminar dead code | 7 | 🧟 |
| P2 — Unificar duplicación | 5 | 🪞 |
| P3 — Refactorizar monstruos | 4 | 🧠 |
| P4 — Agregar error states | 8 | 🚫 |
| P5 — Corregir inconsistencias | 6 | 🔀 |
| P6 — Deshardcodear strings | ~10 | 💬 |
| P7 — Simplificar complejidad | 2 | 🔧 |
| P8 — Simplificar tipos | 1 | 🎯 |

**Total: ~43 Issues**
