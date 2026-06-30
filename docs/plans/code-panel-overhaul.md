# Code Panel — Plan de overhaul por fases

> **Estado:** ✅ Completado (Fases 1–6)  
> **Relacionado:** [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md), [`workflows-tab-implementation.md`](workflows-tab-implementation.md)  
> **Archivos principales:** `ui/tray/src/components/code/`, `ui/tray/src/stores/tab.ts`

---

## Diagnóstico

La pestaña Code contiene tres sub-tabs (`Terminal`, `Output`, `Scratch`) que comparten nombre pero no cohesión conceptual. Los problemas fundamentales son:

1. **El terminal es un REPL falso** — cada comando abre un proceso `zsh -c` nuevo. No hay shell persistente: sin historial, sin tab-completion, sin procesos interactivos (vim, htop), sin pipes entre comandos consecutivos con estado.
2. **Scratch es un textarea sin sintaxis** — prometido como "prepare scripts to ask the agent" pero sin botón para ejecutar esa promesa.
3. **Output no persiste** — los tool calls desaparecen al resetear chat. Sin timestamps, sin filtro, con outputs truncados en `max-h-40`.
4. **Las tres tabs no hablan con el agente** — son islas aisladas dentro de una app de IA.
5. **Texto mezclado ES/EN** en mensajes de error del terminal.
6. **El dropdown "Cmds"** lista comandos Unix básicos que el usuario objetivo ya sabe.

Las fases están ordenadas por impacto vs. complejidad: primero los problemas que rompen la confianza del usuario (terminal falso, texto mezclado), luego las mejoras de valor real (integración con agente, persistencia), finalmente el pulido visual.

---

## Registro de implementación

### 2026-06-29 — Fase 1 y 2 completadas

**Fase 1 — Correcciones críticas:**
- **1.1** Eliminado dropdown "Cmds" en `TerminalTab.tsx` — quitado estado `showCommands`, ref `commandsRef`, useEffect click-outside y todo el markup del menú.
- **1.2** Añadido historial de comandos con teclas arriba/abajo (history array, historyIndex, savedLine) — limitado a 200 entradas.
- **1.3** Corregido texto mezclado ES/EN: añadidas claves `code.terminal_error_title`, `code.terminal_error_hint`, `code.terminal_fallback_title`, `code.terminal_fallback_hint`, `code.terminal_fallback_placeholder`, `code.run`, `code.terminal_loading`, `code.copied` en ambos locales. Reemplazados todos los strings hardcoded en `TerminalTab.tsx` con `t()`.
- **1.4** Persistencia de scratchpad en localStorage mediante middleware `persist` de Zustand con `partialize` en `stores/tab.ts`.

**Fase 2 — ScratchTab a mini-editor:**
- **2.1** Añadido `ScratchLang` type (`python | shell | javascript | plain`) y campos `scratchLang`/`setScratchLang` al store con persistencia. Selector de lenguaje en el header del textarea con 4 botones.
- **2.2** Botón "Enviar al agente" (primario) que usa `setPendingChatAction` + `autoSend: true` + navegación a chat. Reordenados botones: Send to Agent → Copy → Clear.
- **2.3** Shortcut ⌘+Enter para enviar. Hint dinámico mostrado debajo del textarea cuando hay contenido.

**Archivos modificados:**
- `ui/tray/src/components/code/TerminalTab.tsx`
- `ui/tray/src/components/code/ScratchTab.tsx`
- `ui/tray/src/stores/tab.ts`
- `ui/tray/src/locales/es.json`
- `ui/tray/src/locales/en.json`
- `docs/plans/code-panel-overhaul.md`

---

### 2026-06-29 — Fase 3 y 4 completadas

**Fase 3 — OutputTab: de lista estática a log de observabilidad:**
- **3.1** Añadido `executed_at: datetime` al dataclass `ToolCallRecord` en `core/observability/response_meta.py` con `default_factory`. Añadido `timestamp: str | None` al Pydantic model `ToolCallRecordModel` en `server.py`. Campo `timestamp` en conversión `_meta_to_model`. Extendido `ToolCallRecord` frontend en `api/types.ts` con `timestamp?: string`. Formateador `formatTs` en `OutputTab.tsx`.
- **3.2** Filtros por estado (`all`/`approved`/`denied`) y búsqueda por nombre de herramienta. Barra de filtros con input search + segmented buttons.
- **3.3** Expand/collapse con `Set<string>` state, toggle por card cuando `result_summary` > 300 caracteres. Reemplazado `max-h-40` fijo.
- **3.4** Creado `stores/toolOutput.ts` con store Zustand + persist (localStorage, max 500 registros). Hookeado en `chat.ts` → `updateMessage` intercepta `metadata.tools_called` y persiste vía `useToolOutputStore.getState().addCalls()`. OutputTab lee de `useToolOutputStore` en vez de derivar de `messages[]`. Botón "Clear history" en el header.

**Fase 4 — Integración terminal ↔ agente:**
- **4.1** Captura del último output del terminal: `outputBuf` en `executeCmd`, `lastCmdOutput` state React con `{ cmd, output }`.
- **4.2** Botón flotante "Preguntar al agente" (esquina inferior derecha) que envía el output al chat vía `setPendingChatAction` + `autoSend: true` + navegación a chat. Clave i18n `code.ask_agent`.

**Archivos modificados nuevos:**
- `core/observability/response_meta.py` — `executed_at` field
- `ui/tray/server.py` — `timestamp` field en modelo Pydantic + conversión
- `ui/tray/src/api/types.ts` — `timestamp?: string` en ToolCallRecord
- `ui/tray/src/stores/toolOutput.ts` — **nuevo archivo**
- `ui/tray/src/stores/chat.ts` — hook en `updateMessage`
- `ui/tray/src/components/code/OutputTab.tsx` — rewrite completo

---

### 2026-06-29 — Fase 5 y 6 completadas (plan finalizado)

**Fase 5 — Pulido visual y UX:**
- **5.1** Sub-tabs convertidos a segmented control en `CodePanel.tsx`. Reemplazados botones independientes por un grupo `bg-surface-container-low/60 rounded-xl p-1`. Texto oculto en pantallas estrechas (`hidden sm:inline`). Icono de header cambiado a `terminal`.
- **5.2** Barra de estado del terminal: estado `termStatus` con `cwd`, `exitCode`, `cmdCount`. Se actualiza tras cada comando. Barra `bg-[#0a0a0f] border-t` con cwd en verde, exit code (verde/rojo) y contador de comandos. Clave i18n `code.terminal_cmds`.
- **5.3** OutputTab como timeline: contenedor `relative pl-6` con línea vertical `w-px bg-outline-variant/15` y dots `w-2 h-2 rounded-full border-2` (verde para aprobado, rojo para denegado).
- **5.4** Sidebar: icono cambiado de `code` a `terminal`. Label cambiado de "Código"/"Code" a "Shell" en ambos locales.

**Fase 6 — Calidad: i18n completa y tests:**
- **6.1** Verificadas todas las cadenas: `code.copied`, `code.terminal_loading`, `code.terminal_error_*`, `code.terminal_fallback_*`, `code.run`, `code.ask_agent`, `code.terminal_cmds` — sin strings hardcoded en los componentes.
- **6.2** Tests de integración creados (14 tests total):
  - `TerminalTab.test.tsx` — render sin crash, error UI sin Tauri, ausencia de dropdown Cmds
  - `ScratchTab.test.tsx` — botón deshabilitado vacío/habilitado con contenido, click setea pendingChatAction, selector de lenguaje cambia scratchLang, ⌘+Enter funciona
  - `OutputTab.test.tsx` — empty state, tool calls desde store, filtro denied, búsqueda por nombre, expand/collapse

**Archivos modificados en Fase 5-6:**
- `ui/tray/src/components/code/CodePanel.tsx`
- `ui/tray/src/components/code/TerminalTab.tsx`
- `ui/tray/src/components/code/OutputTab.tsx`
- `ui/tray/src/layouts/LeftSidebar.tsx`
- `ui/tray/src/components/code/TerminalTab.test.tsx` — **nuevo**
- `ui/tray/src/components/code/ScratchTab.test.tsx` — **nuevo**
- `ui/tray/src/components/code/OutputTab.test.tsx` — **nuevo**
- `ui/tray/src/locales/es.json`
- `ui/tray/src/locales/en.json`
- `docs/plans/code-panel-overhaul.md`

---

## Fase 0 — Preparación y auditoría

**Objetivo:** Tener el contexto exacto de todas las dependencias antes de tocar código. Cero cambios funcionales en esta fase.

### 0.1 — Mapa de dependencias

Leer y documentar en comentario interno:

| Archivo | Rol |
|---------|-----|
| `components/code/CodePanel.tsx` | Orquestador, contiene los 3 sub-tabs con `display:none` |
| `components/code/TerminalTab.tsx` | xterm.js + Tauri `Command.create("zsh")` |
| `components/code/OutputTab.tsx` | Lee `useChatStore(s => s.messages)` y extrae `metadata.tools_called` |
| `components/code/ScratchTab.tsx` | `useTabStore(s => s.scratch)` — en memoria, sin persistencia |
| `stores/tab.ts` | `LeftTab` type, `scratch: string`, `setScratch` |
| `stores/chat.ts` | `messages[]` con `metadata.tools_called` |
| `api/types.ts` | `ToolCallRecord` — `name`, `args_summary`, `result_summary`, `approved`, `latency_ms` |
| `locales/es.json` / `en.json` | Claves `code.*`, `output.*` |

Verificar que `@xterm/xterm` y `@xterm/addon-fit` están en `package.json`. Confirmar versión (xterm v5 usa namespace `@xterm`, v4 usa `xterm`).

### 0.2 — Inventario de claves i18n faltantes

Las claves que se van a necesitar en fases posteriores. Agregarlas **vacías** ahora en `locales/es.json` y `locales/en.json` para que el sistema no lance warnings:

```json
// Claves nuevas a agregar en esta fase (valores en Fase 1+)
"code.history_placeholder": "",
"code.send_to_agent": "",
"code.language": "",
"code.lang_python": "",
"code.lang_shell": "",
"code.lang_js": "",
"code.lang_plain": "",
"code.terminal_status_cwd": "",
"code.terminal_status_exit": "",
"code.terminal_cmd_count": "",
"output.filter_all": "",
"output.filter_approved": "",
"output.filter_denied": "",
"output.search_placeholder": "",
"output.expand": "",
"output.collapse": "",
"output.timestamp": "",
"output.rerun": "",
"output.no_result_truncated": ""
```

### 0.3 — Añadir `@xterm/addon-search` a `package.json`

No se instala todavía, solo se verifica disponibilidad. Si el proyecto ya tiene lockfile limpio, no introducir paquetes hasta Fase 2.

### 0.4 — Crear rama de trabajo

```bash
git checkout -b feat/code-panel-overhaul
```

---

## Fase 1 — Correcciones críticas (roto → funcional)

**Objetivo:** Eliminar los problemas que dañan la credibilidad del panel. Sin añadir features nuevas todavía.

### 1.1 — Eliminar el dropdown "Cmds"

**Por qué:** No agrega valor. Ocupa espacio visual, distrae de la terminal, y asume que el usuario no sabe qué es `ls`.

**Archivos:** `TerminalTab.tsx`

**Qué eliminar:**
- Estado `showCommands` y `setShowCommands`
- `commandsRef` y el `useEffect` del click-outside
- El botón `Cmds` y el `div` flotante con el grid de comandos

**Qué hacer en su lugar:** El espacio top-right de la terminal queda libre para la barra de estado (Fase 5). Por ahora, dejarlo vacío.

### 1.2 — Historial de comandos con flechas arriba/abajo

**Por qué:** Es el problema más frustrante del terminal. Un usuario escribe un comando largo, lo ejecuta, quiere modificarlo, y no puede recuperarlo. Rompe el flujo completamente.

**Archivos:** `TerminalTab.tsx`

**Implementación:**

```typescript
// Añadir al scope de initTerminal(), junto a lineBuf:
const history: string[] = [];
let historyIndex = -1;
let savedLine = "";    // guarda el input actual cuando el user navega hacia arriba
```

En el handler `term.onData((data) => {...})`, antes del bloque `if (data === "\r")`:

```typescript
// Arrow Up — ESC [ A
if (data === "\x1b[A") {
  if (history.length === 0) return;
  if (historyIndex === -1) {
    savedLine = lineBuf;          // guardar línea actual antes de navegar
    historyIndex = history.length - 1;
  } else if (historyIndex > 0) {
    historyIndex--;
  }
  // Borrar lo que hay en el buffer visual
  term.write("\b \b".repeat(lineBuf.length));
  lineBuf = history[historyIndex];
  term.write(lineBuf);
  return;
}

// Arrow Down — ESC [ B
if (data === "\x1b[B") {
  if (historyIndex === -1) return;
  if (historyIndex < history.length - 1) {
    historyIndex++;
    term.write("\b \b".repeat(lineBuf.length));
    lineBuf = history[historyIndex];
    term.write(lineBuf);
  } else {
    // Restaurar la línea que estaba escribiendo
    historyIndex = -1;
    term.write("\b \b".repeat(lineBuf.length));
    lineBuf = savedLine;
    term.write(lineBuf);
  }
  return;
}
```

En `executeCmd`, después de `const cmd = lineBuf.trim()`, añadir al historial:

```typescript
if (cmd && (history.length === 0 || history[history.length - 1] !== cmd)) {
  history.push(cmd);
  if (history.length > 200) history.shift(); // cap de 200 entradas
}
historyIndex = -1;
savedLine = "";
```

**Nota:** No se puede usar `history` como variable global por conflicto con `window.history`. Mantenerla dentro del scope de `initTerminal`.

### 1.3 — Corregir texto mezclado ES/EN en error states

**Archivos:** `TerminalTab.tsx`, `locales/es.json`, `locales/en.json`

El terminal tiene `useTranslation` pero no lo usa en los mensajes de error. Actualmente mezcla:
- `"Asegúrate de ejecutar en Tauri..."` (hardcoded ES)
- `"In the meantime, you can run individual commands here:"` (hardcoded EN)
- `"type a command and press Enter…"` (hardcoded EN)

**Pasos:**

1. Añadir a `locales/es.json` bajo `"code"`:
```json
"terminal_error_title": "El terminal no pudo cargar",
"terminal_error_hint": "Asegúrate de ejecutar en modo Tauri (npm run tauri:dev) y que los permisos de shell estén configurados.",
"terminal_fallback_title": "Terminal interactivo disponible solo en Tauri",
"terminal_fallback_hint": "Mientras tanto, puedes ejecutar comandos individuales aquí:",
"terminal_fallback_placeholder": "$ escribe un comando y presiona Enter…",
"run": "Ejecutar"
```

2. Equivalente en `locales/en.json`:
```json
"terminal_error_title": "Terminal failed to load",
"terminal_error_hint": "Make sure you are running in Tauri mode (npm run tauri:dev) and that shell permissions are configured.",
"terminal_fallback_title": "Interactive terminal requires Tauri",
"terminal_fallback_hint": "In the meantime, you can run individual commands here:",
"terminal_fallback_placeholder": "$ type a command and press Enter…",
"run": "Run"
```

3. En `TerminalTab.tsx`, añadir `const { t } = useTranslation()` y reemplazar los strings hardcoded con `t("code.terminal_error_title")` etc.

### 1.4 — Persistencia del scratchpad en localStorage

**Por qué:** Ahora el scratch usa `useTabStore` (Zustand sin persistencia). Al refrescar la app, el contenido desaparece. Esto es inaceptable para un editor de código.

**Archivos:** `stores/tab.ts`

Zustand tiene middleware `persist`. Es un cambio de dos líneas:

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

// ...

export const useTabStore = create<TabState>()(
  persist(
    (set) => ({
      activeTab: "home",
      setTab: (tab) => set({ activeTab: tab }),
      scratch: "",
      setScratch: (v) => set({ scratch: v }),
    }),
    {
      name: "cerebro-tab-store",
      partializer: (state) => ({ scratch: state.scratch }), // solo persiste scratch, no activeTab
    }
  )
);
```

**Nota:** Si `partializer` no está disponible en la versión de Zustand instalada, usar `partialize` (es el nombre correcto en Zustand v4+):

```typescript
partialize: (state) => ({ scratch: state.scratch }),
```

Verificar versión en `package.json` antes de usar la API.

---

## Fase 2 — ScratchTab: de textarea a mini-editor

**Objetivo:** Que el scratch sea un editor de verdad, con intención declarada de lenguaje y acción directa hacia el agente.

### 2.1 — Selector de lenguaje

**Archivos:** `ScratchTab.tsx`, `stores/tab.ts`

El selector cambia el color del placeholder y establece el hint de sintaxis. No requiere un parser de sintaxis completo — la diferenciación visual es suficiente por ahora.

**Paso 1 — Extender el store:**

```typescript
// tab.ts
export type ScratchLang = "python" | "shell" | "javascript" | "plain";

interface TabState {
  activeTab: LeftTab;
  setTab: (tab: LeftTab) => void;
  scratch: string;
  setScratch: (v: string) => void;
  scratchLang: ScratchLang;
  setScratchLang: (lang: ScratchLang) => void;
}

// en el create:
scratchLang: "plain",
setScratchLang: (lang) => set({ scratchLang: lang }),

// en partialize:
partialize: (state) => ({ scratch: state.scratch, scratchLang: state.scratchLang }),
```

**Paso 2 — Componente selector en el header del textarea:**

```tsx
// En ScratchTab.tsx, dentro del header bar (donde están los stats)
const LANGS: { id: ScratchLang; label: string }[] = [
  { id: "python",     label: "Python" },
  { id: "shell",      label: "Shell" },
  { id: "javascript", label: "JS" },
  { id: "plain",      label: "Plain" },
];

// Reemplazar el header bar actual por:
<div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant/10 bg-surface-container-lowest/30 shrink-0">
  <span className="text-[10px] text-outline/50 font-label-mono">
    {scratch.length > 0
      ? t("code.stats", { lines: scratch.split("\n").length, chars: scratch.length })
      : t("code.empty")}
  </span>
  <div className="flex gap-1">
    {LANGS.map((lang) => (
      <button
        key={lang.id}
        onClick={() => setScratchLang(lang.id)}
        className={`px-2 py-0.5 text-[10px] rounded font-mono transition-colors ${
          scratchLang === lang.id
            ? "bg-primary-container/15 text-primary-container"
            : "text-outline/40 hover:text-outline/70"
        }`}
      >
        {lang.label}
      </button>
    ))}
  </div>
</div>
```

**Paso 3 — Placeholder dinámico según lenguaje:**

```typescript
const PLACEHOLDERS: Record<ScratchLang, string> = {
  python:     '# Python\ndef process(data):\n    return data\n\nresult = process([])',
  shell:      '#!/bin/zsh\n# Shell Script\nfor f in *.txt; do\n  echo "$f"\ndone',
  javascript: '// JavaScript\nconst run = async () => {\n  const data = await fetch("/api/status")\n  return data.json()\n}',
  plain:      '// Pega o escribe código aquí\n// Útil para preparar scripts antes de pedirle al agente que los ejecute',
};
```

### 2.2 — Botón "Enviar al agente"

**Por qué:** El placeholder actual promete que el scratch es útil "para preparar scripts before asking the agent to run them". El botón cumple esa promesa.

**Archivos:** `ScratchTab.tsx`, `stores/chat.ts`, `stores/tab.ts`

**Paso 1 — Entender el flujo de chat:**

`stores/chat.ts` expone `sendMessage(content: string)` o similar. Verificar el nombre exacto antes de importar. Si el store expone `submitQuery`, usar ese.

**Paso 2 — Implementación en ScratchTab:**

```tsx
import { useChatStore } from "../../stores/chat";
import { useTabStore } from "../../stores/tab";

// Dentro del componente:
const submit = useChatStore((s) => s.sendMessage); // ajustar al nombre real
const setTab = useTabStore((s) => s.setTab);

const handleSendToAgent = () => {
  if (!scratch.trim()) return;
  const langHint: Record<ScratchLang, string> = {
    python:     "python",
    shell:      "shell",
    javascript: "javascript",
    plain:      "",
  };
  const fence = langHint[scratchLang];
  const message = `Por favor ejecuta o analiza este código:\n\`\`\`${fence}\n${scratch}\n\`\`\``;
  submit(message);
  setTab("chat"); // navegar al chat para ver la respuesta
};
```

**Paso 3 — Botón en la UI:**

Añadir un tercer botón en la barra de acciones, con color primario para que destaque:

```tsx
<button
  onClick={handleSendToAgent}
  disabled={!scratch.trim()}
  className="flex items-center gap-1.5 px-3.5 py-2 bg-primary-container text-white text-[11px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
>
  <span className="material-symbols-outlined text-[15px]">send</span>
  {t("code.send_to_agent")}
</button>
```

Reordenar los botones: **Send to Agent** (primario) → **Copy** (secundario) → **Clear** (destructivo/fantasma).

### 2.3 — Shortcut de teclado para Send to Agent

El textarea ya tiene `spellCheck={false}`. Añadir un handler de teclado:

```tsx
<textarea
  // ... props existentes ...
  onKeyDown={(e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSendToAgent();
    }
  }}
/>
```

Mostrar el hint debajo del textarea:

```tsx
<p className="text-[10px] text-outline/30 mt-2 text-right font-label-mono">
  ⌘ + Enter para enviar al agente
</p>
```

---

## Fase 3 — OutputTab: de lista estática a log de observabilidad

**Objetivo:** Que el Output tab sea útil para debugging real — con timestamps, filtros y outputs completos.

### 3.1 — Timestamps por tool call

**Problema:** `ToolCallRecord` en `api/types.ts` probablemente no tiene `timestamp`. Hay dos enfoques:

**Opción A (sin cambio de backend):** El timestamp se infiere del orden dentro de `messages[]`. Cada `msg` tiene un `created_at` o similar. Verificar qué campos tiene el tipo `Message` en `api/types.ts`.

**Opción B (correcta):** Añadir `timestamp: string` a `ToolCallRecord` en el backend (`server.py`) al serializar `tools_called`.

Recomendación: **Opción B**. El backend tiene el timestamp exacto de ejecución de la herramienta.

**Backend — `server.py` / donde se construye `tools_called`:**

Localizar dónde se serializa `ToolCallRecord`. Añadir:

```python
"timestamp": tool_call.executed_at.isoformat() if hasattr(tool_call, "executed_at") else None,
```

Si `executed_at` no existe en el dataclass, añadirlo con `field(default_factory=lambda: datetime.now(timezone.utc))`.

**Frontend — `api/types.ts`:**

```typescript
export interface ToolCallRecord {
  name: string;
  args_summary: string;
  result_summary: string;
  approved: boolean;
  latency_ms: number;
  timestamp?: string;   // ISO 8601, nullable por compatibilidad con registros anteriores
}
```

**Frontend — `OutputTab.tsx`:**

```tsx
// Formateador — simple, sin dependencias externas
function formatTs(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// En la card, junto al latency_ms:
<div className="flex items-center gap-3">
  {tc.timestamp && (
    <span className="text-[10px] text-outline/40 font-label-mono">
      {formatTs(tc.timestamp)}
    </span>
  )}
  <span className="text-[10px] text-outline/50 font-label-mono">
    {tc.latency_ms}ms
  </span>
</div>
```

### 3.2 — Filtro por nombre y estado

**Archivos:** `OutputTab.tsx`

El estado de filtro es local al componente (no necesita store):

```typescript
const [filter, setFilter] = useState<"all" | "approved" | "denied">("all");
const [search, setSearch] = useState("");
```

**Barra de filtros (encima de la lista):**

```tsx
<div className="flex items-center gap-2 mb-4">
  {/* Búsqueda por nombre de tool */}
  <div className="flex-1 relative">
    <span className="material-symbols-outlined text-[14px] text-outline/40 absolute left-2.5 top-1/2 -translate-y-1/2">
      search
    </span>
    <input
      value={search}
      onChange={(e) => setSearch(e.target.value)}
      placeholder={t("output.search_placeholder")}
      className="w-full bg-surface-container-low border border-outline-variant/15 rounded-lg pl-8 pr-3 py-1.5 text-[12px] text-on-surface placeholder-outline/30 outline-none focus:border-primary-container/40 transition-colors"
    />
  </div>
  {/* Segmented filter */}
  {(["all", "approved", "denied"] as const).map((f) => (
    <button
      key={f}
      onClick={() => setFilter(f)}
      className={`px-3 py-1.5 text-[11px] font-medium rounded-lg transition-colors ${
        filter === f
          ? "bg-primary-container/10 text-primary-container"
          : "text-outline/50 hover:text-on-surface"
      }`}
    >
      {t(`output.filter_${f}`)}
    </button>
  ))}
</div>
```

**Aplicar filtro a la lista:**

```typescript
const filtered = toolCalls
  .filter((tc) => filter === "all" || (filter === "approved" ? tc.approved : !tc.approved))
  .filter((tc) => !search || tc.name.toLowerCase().includes(search.toLowerCase()))
  .slice()
  .reverse();
```

### 3.3 — Expand/collapse de outputs largos

**Problema:** `max-h-40` en el bloque de resultado corta información crítica.

**Archivos:** `OutputTab.tsx`

Añadir estado de expansión por card:

```typescript
const [expanded, setExpanded] = useState<Set<string>>(new Set());

const toggleExpand = (key: string) =>
  setExpanded((prev) => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });
```

En cada card, la key es `${tc.msgIdx}-${tc.tcIdx}`. Reemplazar el `max-h-40` por:

```tsx
const cardKey = `${tc.msgIdx}-${tc.tcIdx}`;
const isExpanded = expanded.has(cardKey);

<div className="relative">
  <pre
    className={`text-[12px] text-on-surface font-mono whitespace-pre-wrap bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5 leading-relaxed transition-all ${
      isExpanded ? "" : "max-h-40 overflow-hidden"
    }`}
  >
    {tc.result_summary || (
      <span className="text-on-surface-variant/40 italic">{t("output.no_result")}</span>
    )}
  </pre>
  {/* Mostrar el botón solo si el contenido desborda */}
  {(tc.result_summary?.length ?? 0) > 300 && (
    <button
      onClick={() => toggleExpand(cardKey)}
      className="mt-1 text-[10px] text-primary-container/70 hover:text-primary-container flex items-center gap-1 transition-colors"
    >
      <span className="material-symbols-outlined text-[13px]">
        {isExpanded ? "expand_less" : "expand_more"}
      </span>
      {isExpanded ? t("output.collapse") : t("output.expand")}
    </button>
  )}
</div>
```

### 3.4 — Persistencia del historial de tool calls

**Problema raíz:** `OutputTab` lee de `useChatStore(s => s.messages)`, que se pierde al resetear. La solución correcta es almacenar `tools_called` en un store separado y persistirlo.

**Archivos:** Crear `stores/toolOutput.ts`

```typescript
// stores/toolOutput.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ToolCallRecord } from "../api/types";

export interface StoredToolCall extends ToolCallRecord {
  id: string;           // `${conversationId}-${msgIndex}-${tcIndex}`
  conversationId: string;
  storedAt: string;     // ISO timestamp del momento en que se registró
}

interface ToolOutputState {
  calls: StoredToolCall[];
  addCalls: (calls: StoredToolCall[]) => void;
  clear: () => void;
}

export const useToolOutputStore = create<ToolOutputState>()(
  persist(
    (set) => ({
      calls: [],
      addCalls: (newCalls) =>
        set((s) => {
          const existingIds = new Set(s.calls.map((c) => c.id));
          const fresh = newCalls.filter((c) => !existingIds.has(c.id));
          const merged = [...s.calls, ...fresh];
          // Mantener máximo 500 registros para no inflar localStorage
          return { calls: merged.slice(-500) };
        }),
      clear: () => set({ calls: [] }),
    }),
    {
      name: "cerebro-tool-output",
      partialize: (state) => ({ calls: state.calls }),
    }
  )
);
```

**Dónde popular el store:** En `stores/chat.ts`, cuando llega el mensaje con `metadata.tools_called`, llamar `useToolOutputStore.getState().addCalls(...)`. Localizar el punto exacto donde se procesa la respuesta del stream.

**Actualizar `OutputTab.tsx`:**

```typescript
// Reemplazar la lógica de extracción de messages:
import { useToolOutputStore } from "../../stores/toolOutput";

// Dentro del componente:
const calls = useToolOutputStore((s) => s.calls);
const clearAll = useToolOutputStore((s) => s.clear);

// `calls` ya viene tipado como StoredToolCall[], con timestamp y conversationId
```

Añadir botón "Clear history" en el header del OutputTab para no acumular indefinidamente.

---

## Fase 4 — Integración terminal ↔ agente

**Objetivo:** Que el terminal no sea una isla. El output del último comando debe poder fluir al chat con un clic.

### 4.1 — Capturar el último output del terminal

**Archivos:** `TerminalTab.tsx`

Añadir un buffer en el scope de `initTerminal`:

```typescript
let lastOutput = "";   // output del último comando ejecutado
```

En `executeCmd`, capturar el output antes de escribirlo en el terminal:

```typescript
const executeCmd = async (cmd: string) => {
  let outputBuf = "";
  try {
    const { Command } = await import("@tauri-apps/plugin-shell");
    const fullCmd = cwd ? `cd "${cwd}" && ${cmd}` : cmd;
    const result = await Command.create("zsh", ["-c", fullCmd]).execute();
    if (result.stdout) {
      outputBuf += result.stdout;
      term.write(result.stdout.replace(/\n/g, "\r\n"));
    }
    if (result.stderr) {
      outputBuf += result.stderr;
      term.write(`\x1b[31m${result.stderr.replace(/\n/g, "\r\n")}\x1b[0m`);
    }
    // ...
  } catch { /* ... */ }
  lastOutput = outputBuf;  // guardar para "Ask about this output"
  // ...
};
```

### 4.2 — Botón "Preguntar al agente"

Añadir estado de React para exponer `lastOutput` fuera del closure de `initTerminal`:

```typescript
const [lastCmdOutput, setLastCmdOutput] = useState<{ cmd: string; output: string } | null>(null);
```

Dentro de `executeCmd`, al final:

```typescript
setLastCmdOutput({ cmd, output: lastOutput });
```

**UI — botón flotante en la esquina inferior derecha de la terminal:**

```tsx
{lastCmdOutput && (
  <button
    onClick={() => {
      const msg = `Tengo este output de terminal:\n\`\`\`\n$ ${lastCmdOutput.cmd}\n${lastCmdOutput.output}\`\`\`\n\n¿Puedes analizarlo?`;
      chatSubmit(msg);
      setTab("chat");
    }}
    className="absolute bottom-3 right-3 flex items-center gap-1.5 px-3 py-2 bg-surface-container/90 backdrop-blur-sm border border-outline-variant/20 rounded-lg text-[11px] font-medium text-on-surface-variant hover:text-on-surface hover:border-primary-container/40 transition-all shadow-lg z-10"
  >
    <span className="material-symbols-outlined text-[14px] text-primary-container/70">
      forum
    </span>
    Preguntar al agente
  </button>
)}
```

**Imports necesarios en `TerminalTab.tsx`:**

```typescript
import { useChatStore } from "../../stores/chat";
import { useTabStore } from "../../stores/tab";

// Dentro del componente:
const chatSubmit = useChatStore((s) => s.sendMessage);
const setTab = useTabStore((s) => s.setTab);
```

### 4.3 — Indicador de salida en tiempo real (opcional, post-MVP)

Si el proyecto mueve la ejecución de comandos al backend (recomendado para comandos de larga duración), se puede mostrar el output en streaming. Por ahora se deja como nota para futuras iteraciones.

---

## Fase 5 — Pulido visual y UX

**Objetivo:** Que el panel se vea y se sienta como parte de una app profesional, no como un prototipo funcional.

### 5.1 — Sub-tabs como segmented control

**Problema:** Los tres tabs actuales son botones independientes con estado diferenciado por clases. No hay un indicador claro del tab activo más allá del color.

**Archivos:** `CodePanel.tsx`

Reemplazar el `div` de tabs por un segmented control:

```tsx
<div className="flex bg-surface-container-low/60 rounded-xl p-1 gap-0.5">
  {TAB_IDS.map((tab) => (
    <button
      key={tab.id}
      onClick={() => setActiveTab(tab.id)}
      className={`flex items-center gap-1.5 px-3.5 py-2 text-[12px] font-medium rounded-lg transition-all flex-1 justify-center ${
        activeTab === tab.id
          ? "bg-surface-container-high text-on-surface shadow-sm"
          : "text-on-surface-variant/50 hover:text-on-surface/70"
      }`}
    >
      <span className="material-symbols-outlined text-[15px]">{tab.icon}</span>
      <span className="hidden sm:inline">{t("code." + tab.id)}</span>
    </button>
  ))}
</div>
```

El `hidden sm:inline` oculta el texto en ventanas muy estrechas y deja solo los iconos, evitando overflow.

### 5.2 — Barra de estado del terminal

**Objetivo:** El cwd y el exit code del último comando deben ser visibles sin leer el output del terminal.

**Archivos:** `TerminalTab.tsx`

Añadir estado de React:

```typescript
const [termStatus, setTermStatus] = useState({ cwd: "~", exitCode: null as number | null, cmdCount: 0 });
```

Actualizar en `executeCmd`:

```typescript
setTermStatus((s) => ({
  cwd: cwd || "~",
  exitCode: result.code,
  cmdCount: s.cmdCount + 1,
}));
```

**Barra en la parte inferior de la terminal (fuera del `div ref={terminalRef}`):**

```tsx
{terminalReady && !terminalError && shellAvailable !== false && (
  <div className="flex items-center justify-between px-3 py-1.5 bg-[#0a0a0f] border-t border-white/5 text-[10px] font-label-mono shrink-0">
    <span className="text-green-400/70 truncate max-w-[60%]">
      ⊡ {termStatus.cwd}
    </span>
    <div className="flex items-center gap-3 text-outline/40">
      {termStatus.exitCode !== null && (
        <span className={termStatus.exitCode === 0 ? "text-green-400/60" : "text-red-400/70"}>
          exit {termStatus.exitCode}
        </span>
      )}
      <span>{termStatus.cmdCount} cmds</span>
    </div>
  </div>
)}
```

**Ajuste de `terminalRef`:** La terminal debe respetar el espacio de la barra. El `FitAddon` hace fit del contenedor, así que mientras la barra esté fuera del `div ref={terminalRef}`, no hay conflicto.

### 5.3 — OutputTab como timeline

**Objetivo:** Que el Output tab tenga jerarquía visual clara — más fácil de leer de un vistazo.

**Archivos:** `OutputTab.tsx`

Reemplazar el `space-y-2` con un layout de timeline:

```tsx
<div className="relative pl-6">
  {/* Línea vertical */}
  <div className="absolute left-2 top-0 bottom-0 w-px bg-outline-variant/15" />

  {filtered.map((tc) => {
    const cardKey = `${tc.msgIdx}-${tc.tcIdx}`;
    return (
      <div key={cardKey} className="relative mb-3">
        {/* Dot en la línea */}
        <div className={`absolute -left-4 top-3.5 w-2 h-2 rounded-full border-2 ${
          tc.approved
            ? "bg-[#4ade80] border-[#1a2e1a]"
            : "bg-[#f87171] border-[#2a1e1e]"
        }`} />
        {/* Card existente */}
        <div className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-4 hover:border-outline-variant/25 transition-colors">
          {/* ... resto del contenido existente ... */}
        </div>
      </div>
    );
  })}
</div>
```

### 5.4 — Renombrar la pestaña del sidebar

**Archivos:** `layouts/LeftSidebar.tsx`, `locales/es.json`, `locales/en.json`

El icono actual es `code`, que es correcto. Lo que debe cambiar es el label:

```json
// es.json
"sidebar.code": "Shell"

// en.json
"sidebar.code": "Shell"
```

Alternativa: `"Workspace"` si se prefiere neutralidad. `"Shell"` es más honesto porque el tab primario es la terminal.

El icono en `LeftSidebar.tsx` se puede cambiar de `code` a `terminal` para mayor claridad:

```typescript
{ id: "code", icon: "terminal", labelKey: "sidebar.code" },
```

---

## Fase 6 — Calidad: i18n completa y tests

**Objetivo:** Que ninguna string hardcoded quede en los componentes de Code y que los cambios tengan cobertura mínima.

### 6.1 — Completar claves i18n

Recorrer los cuatro archivos del panel y extraer cualquier string que no pase por `t()`:

- `"Copied"` en `TerminalTab.tsx` → `t("code.copied")`
- `"Run"` en el botón del fallback → ya cubierto en Fase 1
- Labels de la barra de estado del terminal → añadir claves `code.terminal_status_*`
- `"Preguntar al agente"` del botón de integración → `t("code.ask_agent")`

### 6.2 — Tests de integración de componentes

No se busca cobertura exhaustiva — solo los flujos críticos que demorarían en detectarse manualmente:

**`TerminalTab.test.tsx`**
- Renderiza sin crash cuando Tauri no está disponible (muestra fallback UI)
- El fallback input dispara `Command.create` al presionar Enter
- El botón Copy ya no existe (Cmds dropdown eliminado)

**`ScratchTab.test.tsx`**
- El botón "Send to Agent" está desactivado cuando el scratch está vacío
- Al hacer clic, llama al store de chat con el contenido correcto
- ⌘+Enter dispara el mismo handler que el botón

**`OutputTab.test.tsx`**
- Con filtro `"denied"`, solo se muestran calls donde `approved === false`
- El botón expand/collapse alterna correctamente
- Con `search = "python"`, solo se muestran calls cuyo `name` incluye "python"

---

## Resumen de archivos modificados

| Archivo | Fases | Tipo de cambio | Estado |
|---------|-------|----------------|--------|
| `components/code/TerminalTab.tsx` | 1.1–1.3, 4.1–4.2, 5.2 | Refactor + feature | ✅ |
| `components/code/ScratchTab.tsx` | 2.1–2.3 | Feature | ✅ |
| `components/code/OutputTab.tsx` | 3.1–3.4, 5.3 | Refactor + feature | ✅ |
| `components/code/CodePanel.tsx` | 5.1 | Segmented control | ✅ |
| `stores/tab.ts` | 1.4, 2.1 | Persist + extend | ✅ |
| `stores/toolOutput.ts` | 3.4 | Nuevo archivo | ✅ |
| `stores/chat.ts` | 3.4 | Hook toolOutput | ✅ |
| `layouts/LeftSidebar.tsx` | 5.4 | Label/icon | ✅ |
| `locales/es.json` | 1.3, 3.x, 5.x | i18n | ✅ |
| `locales/en.json` | 1.3, 3.x, 5.x | i18n | ✅ |
| `api/types.ts` | 3.1 | `timestamp` opcional | ✅ |
| Backend `response_meta.py` | 3.1 | `executed_at` field | ✅ |
| Backend `server.py` | 3.1 | `timestamp` en Pydantic | ✅ |
| `TerminalTab.test.tsx` | 6.2 | Tests | ✅ |
| `ScratchTab.test.tsx` | 6.2 | Tests | ✅ |
| `OutputTab.test.tsx` | 6.2 | Tests | ✅ |

---

## Orden de ejecución recomendado

```
Fase 0  →  [Fase 1 ✅]  →  [Fase 2 ✅]  →  [Fase 3 ✅]  →  [Fase 4 ✅]  →  [Fase 5 ✅]  →  [Fase 6 ✅]
```

Plan completado. Pendiente para futuras iteraciones:
- **5.3** pre-flight check de `result_summary` real para mostrar botón expand (actual: threshold 300 chars, funciona correctamente)
- Syntax highlighting real (prism-react-renderer) si se desea en el futuro

---

## Decisiones de diseño adoptadas

1. **Label del sidebar:** `"Shell"` (más honesto). ✅
2. **Persistencia de Output:** localStorage vía Zustand `persist` (más simple, sin backend). Store `stores/toolOutput.ts` con cap de 500 registros. ✅
3. **Botón "Preguntar al agente":** Navega automáticamente al tab de chat (conveniente, decisión adoptada). ✅
4. **Syntax highlighting:** Solo placeholder diferenciado por lenguaje. Sin dependencias adicionales. ✅
