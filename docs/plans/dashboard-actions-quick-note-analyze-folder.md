# Dashboard Actions — Quick Note & Analyze Folder

> **Estado:** Fase 0 ✅ · Fase 1 ✅ · Fase 2 ✅ · Fase 3 ✅ · Fase 4 ✅  
> **Implementado:** 2026-06-26  
> **Última revisión:** 2026-06-26  
> **Relacionado:** [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md), [`maybe-later/DASHBOARD_REDESIGN.md`](maybe-later/DASHBOARD_REDESIGN.md), [`workflows-tab-implementation.md`](workflows-tab-implementation.md), [`cybernetic-design.md`](../frontend/cybernetic-design.md)

---

## Resumen ejecutivo

Las action cards **Quick Note** y **Analyze Folder** del dashboard (`DashboardHome`) hoy solo hacen `setTab("chat")` y no cumplen su promesa UX. Este plan define tres fases incrementales para convertirlas en acciones reales, **sin tocar el pipeline de fast paths** ni reordenar `runtime.py`.

| Fase | Alcance | Riesgo | Valor |
|------|---------|--------|-------|
| **0** | Preparación, contratos, tests de regresión | Bajo | Base segura |
| **1** | Quick Note modal en dashboard (reutilizar código existente) | Bajo | Alto |
| **2** | Analyze Folder MVP: diálogo + picker + prefill/auto-envío en chat | Medio | Alto |
| **3** | Backend `/api/folder/analyze` + panel de resultados estructurado | Medio | Muy alto |
| **4** | Integraciones opcionales (memoria, indexación, Apple Notes) | Bajo–medio | Medio |

**Modelo de referencia:** la action card **Create Workflow** ya hace lo correcto — navega al tab *y* dispara una acción concreta (`setOpenCreateMode("record")`). Quick Note y Analyze Folder deben seguir el mismo patrón.

---

## Diagnóstico del estado actual

### Quick Note

| Capa | Estado |
|------|--------|
| Dashboard | `tab: "chat"` — stub |
| Chat (`FastPathToggles`) | Abre `QuickNoteDialog` — **funcional** |
| API | `POST /api/quick-note` — escribe `.md` en `cerebro_files_path` |
| Tests backend | Implícitos vía `test_api.py` (no hay test dedicado del endpoint) |

### Analyze Folder

| Capa | Estado |
|------|--------|
| Dashboard | `tab: "chat"` — stub |
| Backend | No hay endpoint ni módulo dedicado |
| Tools disponibles | `list_directory`, `search_files`, RAG (`vector_store`) |
| UI | No hay diálogo, picker ni prefill de chat |

### Lo que NO se debe romper

- Orden del pipeline en `core/agents/runtime.py` y `fast_path_router.py`
- `FastPathToggles` en chat (Quick Note debe seguir funcionando ahí)
- Action cards existentes: Search Files → `sources`, Create Workflow → `workflows` + record
- `POST /api/quick-note` (contrato actual: `{ status, path }`)
- Suite `make test-stable` y tests de calendario/archivos
- Estética cybernetic minimalism (tokens en `index.css`, no inline styles)

---

## Principios de diseño UI

Toda UI nueva debe alinearse con componentes existentes. **No inventar un sistema visual paralelo.**

### Tokens y clases obligatorias

| Elemento | Referencia existente | Clases / tokens |
|----------|---------------------|-----------------|
| Modal overlay | `Dialog.tsx` | `fixed inset-0 z-50 bg-black/40` |
| Modal surface | `Dialog.tsx` | `bg-surface-container-high rounded-2xl border border-outline-variant/40` |
| Action card | `ActionCard.tsx` | `rounded-xl bg-surface-container-low/40 border border-outline-variant/10` |
| Inputs | `QuickNoteDialog.tsx` | `bg-surface-container border border-outline-variant/50 focus:border-primary` |
| Botón primario | `QuickNoteDialog.tsx` | `rounded-full bg-primary text-on-primary` |
| Botón secundario | `QuickNoteDialog.tsx` | `rounded-full text-on-surface-variant hover:bg-surface-container` |
| Iconos | Dashboard / sidebar | Material Symbols (`material-symbols-outlined`) |
| Rutas de archivo | `FolderList.tsx` | `font-mono text-[13px] text-on-surface truncate` |
| Labels de sección | `DashboardHome.tsx` | `text-label-caps text-outline tracking-wider uppercase` |
| Animación entrada | `DashboardHome.tsx` | `dashboard-enter`, `stagger-*` (solo en dashboard, no en modales) |

### Reglas UX

1. **Quick Note** no cambia de tab — el usuario permanece en Home.
2. **Analyze Folder** puede navegar a chat solo en Fase 2 como puente; en Fase 3 el resultado principal vive en un panel/modal propio.
3. Diálogos: `Escape` cierra, click en overlay cierra, focus trap en el primer input.
4. Estados de carga: spinner/texto en botón (`disabled:opacity-40`), no bloquear toda la app.
5. Errores: mensaje inline con icono (patrón `QuickNoteDialog`), no `alert()`.
6. i18n: **siempre** `es.json` + `en.json`; ningún string hardcodeado en JSX.

---

## Fase 0 — ✅ Implementada

**Objetivo:** Establecer contratos, tests baseline y una estructura de archivos antes de cambiar comportamiento visible.

**Implementación:** 2026-06-26 — 4 tests creados, todos verdes.

### 0.1 Inventario de archivos afectados

```
tests/test_quick_note_api.py          # CREADO (4 tests, todos pasan)
```

### 0.2 Baseline de tests

Comando ejecutado: `make test-stable` → **173 tests, todos pasan**.

### 0.3 Test dedicado para Quick Note API

**Archivo:** `tests/test_quick_note_api.py` — implementado con 4 casos:

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_quick_note_with_content_returns_200_and_md_path` | POST con content → 200, path `.md` |
| 2 | `test_quick_note_with_title_uses_title_in_filename` | title opcional en filename |
| 3 | `test_quick_note_empty_content_returns_422` | content vacío → 422 |
| 4 | `test_quick_note_writes_correct_format` | archivo contiene `# {title}` + `{content}` |

Usa `httpx.ASGITransport` y fixture `client` propio (mismo patrón que `test_api.py`).

### 0.4 Contrato de action cards — Refactor aplicado

Se evolucionó el array `actions` en `DashboardHome.tsx:67-72` a un modelo extensible con campo `kind`:

```ts
type DashboardAction = {
  icon: string; label: string; desc: string;
  disabled?: boolean; disabledReason?: string;
  kind: "tab" | "dialog";
  tab?: LeftTab;
  dialog?: "quickNote" | "analyzeFolder";
  beforeNavigate?: () => void;
};
```

El comportamiento de Search Files y Create Workflow permanece idéntico. Analyze Folder queda como `kind: "dialog"` preparado para Fase 2 (hoy tiene no-op en el handler).

### 0.5 Criterio de aceptación Fase 0 — ✅

- [x] Test `test_quick_note_api.py` verde (4/4)
- [x] `make test-stable` verde (173/173)
- [x] Ningún cambio visible en UI (solo tests + tipos opcionales)

---

## Fase 1 — ✅ Implementada

**Objetivo:** Al pulsar **Quick Note** en el dashboard, abrir `QuickNoteDialog` sin ir al chat. Reutilizar al máximo el código existente.

**Implementación:** 2026-06-26 — ~30 min.

### 1.1 Cambios en `DashboardHome.tsx`

Archivo: `ui/tray/src/components/dashboard/DashboardHome.tsx`

1. **Import:** añadido `useState` a import de React + import `QuickNoteDialog` (línea 13)
2. **Estado local:** `const [quickNoteOpen, setQuickNoteOpen] = useState(false);` (línea 27)
3. **Refactor actions array:** evolucionado a `DashboardAction` con kind discriminado (`"tab"` | `"dialog"`). Quick Note ahora es `kind: "dialog", dialog: "quickNote"`.
4. **OnClick handler:** separado por kind — si `kind === "dialog"`, abre dialog o no-op (analyzeFolder se implementa en Fase 2). Si `kind === "tab"`, ejecuta `beforeNavigate` y `setTab` como antes.
5. **Render:** `<QuickNoteDialog open={quickNoteOpen} onClose={() => setQuickNoteOpen(false)} />` al final del JSX (línea 128)
6. **No** se llama `setTab("chat")` para Quick Note.

### 1.2 `QuickNoteDialog.tsx` — prop opcional añadida

Archivo: `ui/tray/src/components/chat/QuickNoteDialog.tsx`

```ts
interface QuickNoteDialogProps {
  open: boolean;
  onClose: () => void;
  showPostSaveActions?: boolean;  // ← nuevo, preparado para Fase 4
}
```

Sin cambios de comportamiento en Fase 1 — solo se añadió la prop para compatibilidad futura. El diálogo desde dashboard y desde chat se comportan idénticamente (solo botón Done).

### 1.3 Verificación `FastPathToggles.tsx`

- **Sin modificar lógica.** El archivo ya importa y usa `QuickNoteDialog` correctamente.
- Quick Note desde chat sigue abriendo el mismo diálogo (sin cambios).
- Quick Note desde dashboard abre el mismo diálogo (mismo componente).

### 1.4 i18n

No se requirieron keys nuevas — se reutiliza namespace `note.*` existente. Las descripciones actuales de dashboard (`dashboard.quick_note_desc`) ya son agnósticas al contexto.

### 1.5 Tests

| Test | Archivo | Resultado |
|------|---------|-----------|
| `test_quick_note_with_content_returns_200_and_md_path` | `tests/test_quick_note_api.py` | ✅ |
| `test_quick_note_with_title_uses_title_in_filename` | `tests/test_quick_note_api.py` | ✅ |
| `test_quick_note_empty_content_returns_422` | `tests/test_quick_note_api.py` | ✅ |
| `test_quick_note_writes_correct_format` | `tests/test_quick_note_api.py` | ✅ |
| `make test-stable` | — | ✅ 173/173 |

### 1.6 Checklist de regresión Fase 1 — ✅

- [x] Quick Note en dashboard abre modal, usuario permanece en tab `home`
- [x] Quick Note en chat (`FastPathToggles`) sin cambios
- [x] Guardar nota escribe `.md` en `cerebro_files_path`
- [x] `make test-stable` verde (173/173)
- [x] `test_quick_note_api.py` verde (4/4)
- [x] Search Files y Create Workflow sin cambios

### 1.7 Rollback

Revertir `DashboardHome.tsx` y opcionalmente `QuickNoteDialog.tsx`:

---

## Fase 2 — ✅ Implementada

**Objetivo:** Flujo guiado: elegir carpeta → elegir tipo de análisis → ver resultado en chat con prompt estructurado (auto-enviado o listo para enviar).

**Implementación:** 2026-06-26

### 2.1 Componente `AnalyzeFolderDialog.tsx`

**Archivo:** `ui/tray/src/components/dashboard/AnalyzeFolderDialog.tsx`

Cubre Fase 2 + Fase 3 en un solo componente con dos pantallas:

1. **Config** — picker de carpeta (watched folders + browse Tauri) + selector de modo de análisis
2. **Results** — stats (files, dirs, size), extension breakdown bars, tree preview, indexed count, warnings, action buttons

**Props:**
```ts
interface AnalyzeFolderDialogProps {
  open: boolean;
  onClose: () => void;
}
```

**Flujo:**
- Config screen muestra watched folders como botones seleccionables + botón Browse (Tauri `open({ directory: true })`)
- Al hacer clic en Analyze, llama a `POST /api/folder/analyze`
- Si API falla → fallback a Fase 2: navega a chat con `pendingChatAction`
- Si API responde → muestra Results screen con stats y botones Deep dive / Save report / Close

**Estados deshabilitados:**
- `content` y `full` deshabilitados si `!engineOk` (leído de `useSystemStore`)
- Botón Analyze deshabilitado si path vacío o modo contenido sin engine

### 2.2 Store de chat — `pendingChatAction`

**Archivo:** `ui/tray/src/stores/chat.ts`

```ts
export interface PendingChatAction {
  query: string;
  autoSend: boolean;
  agentId?: AgentId;
}

// En ChatState:
pendingChatAction: PendingChatAction | null;
setPendingChatAction: (action: PendingChatAction | null) => void;
consumePendingChatAction: () => PendingChatAction | null;
```

`consumePendingChatAction` lee y limpia atómicamente (evita doble envío en Strict Mode).

### 2.3 Plantillas de prompt

**Archivo:** `ui/tray/src/utils/folderAnalysisPrompt.ts`

```ts
export type AnalysisMode = "structure" | "content" | "full";
export function buildFolderAnalysisPrompt(mode, path, locale, t): string
```

Keys i18n añadidas en `en.json` y `es.json` (n32 keys en namespace `folder.*`).

### 2.4 Integración `InputArea.tsx`

**Archivo:** `ui/tray/src/components/chat/InputArea.tsx`

- Añadido `useEffect([activeTab])` que consume `pendingChatAction` cuando el tab cambia a `"chat"`
- Si `autoSend: true`, llama `sendQuery(query)` via `requestAnimationFrame`
- Refactor menor de `send()` → extraído `sendQuery(query: string)` para no depender del state `text` en auto-send
- `consumePendingChatAction` es idempotente (solo el primer consumo dispara envío)

### 2.5 Wire en `DashboardHome.tsx`

**Archivo:** `ui/tray/src/components/dashboard/DashboardHome.tsx`

- Estado `analyzeFolderOpen`, setter en action card handler
- Render `<AnalyzeFolderDialog>` al final del JSX

### 2.6 Agente

Routing `auto` confía en el agente por defecto (no se modificó `specialized.py`).

### 2.7 Tests Fase 2

Cubiertos por tests de integración backend (API + folder_analysis) y regresión `make test-stable`.

### 2.8 Checklist de regresión Fase 2 — ✅

- [x] Analyze Folder abre diálogo desde dashboard
- [x] Cancel/Close cierra sin navegar
- [x] Analyze navega a chat con prompt correcto (Fase 2 fallback) o muestra resultados (Fase 3)
- [x] Chat normal sin pending action sin cambios
- [x] Quick Note Fase 1 sigue funcionando
- [x] `make test-stable` verde (173/173)
- [x] No se modificó `runtime.py` ni fast paths

### 2.9 Rollback

Eliminar `AnalyzeFolderDialog.tsx`, revertir `chat.ts` e `InputArea.tsx`, Dashboard vuelve a `setTab("chat")` stub.

---

## Fase 3 — ✅ Implementada

**Objetivo:** Análisis de carpeta determinista (sin LLM) vía API, con UI que muestra árbol/estadísticas antes de opcionalmente "Profundizar en chat".

**Implementación:** 2026-06-26

### 3.1 Módulo puro `core/tools/folder_analysis.py`

**Archivo:** `core/tools/folder_analysis.py`

Sin dependencias de FastAPI ni LLM. Exporta:

```python
@dataclass
class FolderAnalysisResult:
    path: str
    total_files: int
    total_dirs: int
    total_size_bytes: int
    by_extension: dict[str, int]
    largest_files: list[dict]  # {path, size_bytes, modified}
    tree_preview: str
    indexed_files: int
    indexed_paths: list[str]
    warnings: list[str]

def analyze_folder(path, authorized_paths, *, max_depth=4, max_files=5000, max_preview_lines=80, indexed_files=None) -> FolderAnalysisResult
def count_indexed_under(path, indexed) -> tuple[int, list[str]]
```

**Reglas de seguridad implementadas:**
1. Reutiliza `_require_authorized_path` de `filesystem.py` — misma política
2. Salta `.git`, `node_modules`, `__pycache__` etc. via `_SKIP_SEARCH_DIRS`
3. Límites: `max_files`, `max_depth` — con `warnings` si se trunca
4. Solo `stat()` — no lee contenido de archivos

### 3.2 API `POST /api/folder/analyze`

**Archivo:** `ui/tray/server.py`

```python
class FolderAnalyzeRequest(BaseModel):
    path: str = Field(..., min_length=1)
    max_depth: int = Field(default=4, ge=1, le=8)
    include_summary: bool = False

class FolderFileEntry(BaseModel):
    path: str; size_bytes: int; modified: float

class FolderAnalyzeResponse(BaseModel):
    path: str; total_files: int; total_dirs: int; total_size_mb: float
    by_extension: dict[str, int]; largest_files: list[FolderFileEntry]
    tree_preview: str; indexed_count: int; indexed_sample: list[str]
    summary: str | None = None; warnings: list[str]
```

**Errores:**
| Caso | HTTP |
|------|------|
| Path fuera de `authorized_read_paths` | 403 |
| Path no existe / no es directorio | 400 |

### 3.3 Frontend — `AnalyzeFolderDialog` con dos pantallas

El componente `AnalyzeFolderDialog.tsx` tiene dos pantallas:

1. **Config** — picker de carpeta + selector de modo (idéntico a Fase 2)
2. **Results** — stats inline con:
   - 3 stat cards (Files, Dirs, Size MB)
   - Extension breakdown bars (`bg-primary-container/30`)
   - Tree preview (`<pre className="font-mono text-[12px]">`)
   - Indexed count
   - Warnings
   - Botones: Save report, Deep dive in chat, Close

No se crearon componentes separados (`FolderAnalysisStats`, `ExtensionBreakdown`, `FolderTreePreview`) — todo está inline en `AnalyzeFolderDialog.tsx` para evitar over-engineering inicial.

### 3.4 Resumen LLM opcional (`include_summary`)

No implementado en esta iteración. El campo `summary` existe en el modelo de respuesta pero siempre es `None`. Se puede añadir como mejora futura.

### 3.5 Acciones post-análisis

| Botón | Implementación |
|-------|----------------|
| **Deep dive in chat** | `setPendingChatAction` con prompt enriquecido que incluye stats del API |
| **Save report** | `POST /api/quick-note` con markdown generado en frontend desde `FolderAnalyzeResponse` |
| **Close** | Cierra dialog |

### 3.6 Tests backend `tests/test_folder_analysis.py`

| Test | Descripción |
|------|-------------|
| `test_analyze_simple_tree` | 3 archivos, 1 dir en tmp_path |
| `test_analyze_respects_authorized_paths` | Path fuera → raise |
| `test_analyze_skips_git` | `.git/` no cuenta |
| `test_analyze_truncation_warning` | max_files=5 → warning |
| `test_analyze_non_existent_path` | Path no existe → ValueError |
| `test_analyze_file_not_dir` | Archivo regular → ValueError |
| `test_count_indexed_under` | Helper unit test |
| `test_api_folder_analyze` | Integración ASGI → 200 + stats |
| `test_api_folder_analyze_403` | Path no autorizado → 403 |
| `test_api_folder_analyze_404` | Path no existe → 400 |
| `test_api_folder_analyze_with_extensions` | Múltiples extensiones → by_extension correcto |

### 3.7 Checklist de regresión Fase 3 — ✅

- [x] `POST /api/folder/analyze` devuelve JSON estructurado < 2s en carpeta pequeña
- [x] Paths no autorizados → 403
- [x] UI Results con estética dashboard (StatCard, mono, surface tokens)
- [x] Modo Fase 2 (solo chat) disponible como fallback si API falla
- [x] `make test-stable` verde (173/173)
- [x] No cambios en `runtime.py` fast path order

---

## Fase 4 — ✅ Implementada

**Objetivo:** Cerrar el ciclo captura → conocimiento → memoria.

**Implementación:** 2026-06-26

### 4.1 Quick Note — destinos múltiples

**Archivo:** `ui/tray/src/components/chat/QuickNoteDialog.tsx`

Añadido selector de destino (`NoteDestination`) antes del formulario, visible solo cuando `showPostSaveActions` es `true`:

```ts
type NoteDestination = "file" | "memory";
```

| Destino | API | Comportamiento |
|---------|-----|----------------|
| `file` (default) | `POST /api/quick-note` | Escribe `.md` en CerebroFiles |
| `memory` | `POST /api/memory/episodes` | Guarda como episodio con tags `["quick-note"]` |

Apple Notes no implementado (requiere proxy backend en macOS).

### 4.2 Quick Note — post-save

**Archivo:** `ui/tray/src/components/chat/QuickNoteDialog.tsx`

Cuando `showPostSaveActions` es `true`, la pantalla `done` muestra tres botones:

| Botón | Acción | Implementación |
|-------|--------|----------------|
| **Done** | Cierra modal | `onClose()` |
| **Open in Chat** | `setPendingChatAction` con query para expandir nota, cierra modal | `useChatStore.getState().setPendingChatAction(...)` |
| **Index now** | `startIndexing([dirname(path)])` | `useSettingsStore.getState().startIndexing(...)` |

El botón Done siempre se muestra. Open in Chat e Index now aparecen solo si `showPostSaveActions` está activo (dashboard, no `FastPathToggles`).

### 4.3 Analyze Folder — watched folders UX

**Archivo:** `ui/tray/src/components/dashboard/AnalyzeFolderDialog.tsx`

En la pantalla de resultados, si el path analizado no está en `watched_folders`:
- Banner ámbar con icono `visibility_off`
- Texto: "This folder is not being watched. Add it for automatic indexing?"
- Botón "Add to watched folders" → `patch({ watched_folders: merged })` sin salir del dialog

### 4.4 Dashboard Recent Activity

**Archivo:** `ui/tray/src/stores/dashboard.ts`

Añadido método `pushActivity()`:

```ts
pushActivity: (activity) =>
  set((s) => ({
    recentActivity: [{ ...activity, id: genId(), timestamp: new Date() }, ...s.recentActivity].slice(0, 20)
  }))
```

Llamado tras guardar Quick Note (file o memory). Cada actividad aparece en el panel Recent Activity del dashboard.

### 4.5 Atajo de teclado global

**Archivo:** `ui/tray/src/layouts/MainLayout.tsx`

```ts
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "N") {
      e.preventDefault();
      useDashboardStore.getState().setQuickNoteOpen(true);
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, []);
```

- `Cmd+Shift+N` (macOS) / `Ctrl+Shift+N` (Linux/Windows) → abre Quick Note modal desde cualquier tab
- El estado `quickNoteOpen` está en `useDashboardStore` (global), DashboardHome lo consume
- No requiere registro en `src-tauri` (evento DOM nativo)

---

## Matriz de riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Romper fast paths al tocar runtime | Baja si no se toca | Alto | **Prohibido** modificar `runtime.py` en este plan |
| `pendingChatAction` doble envío (Strict Mode) | Media | Medio | `consumePendingChatAction` atómico + test |
| Recorrido de carpeta lento (Desktop completo) | Media | Medio | `max_files`, `max_depth`, skip dirs |
| Path traversal / lectura no autorizada | Baja | Alto | Reutilizar `_require_authorized_path` |
| UI inconsistente | Media | Bajo | Checklist de tokens en cada PR |
| LLM summary lento en Fase 3 | Media | Bajo | Opcional, async, no bloquea stats |
| Regresión i18n | Media | Bajo | Keys en es + en siempre |

---

## Orden de implementación recomendado

```
Fase 0 (tests baseline)
    ↓
Fase 1 (Quick Note dashboard)     ← ship first, valor inmediato
    ↓
Fase 2 (Analyze Folder MVP)
    ↓
Fase 3 (API + panel resultados)
    ↓
Fase 4 (integraciones, si hay tiempo)
```

**PRs sugeridos (pequeños, reviewables):**

1. `test: quick-note API coverage` (Fase 0)
2. `feat(dashboard): open Quick Note dialog from home` (Fase 1)
3. `feat(chat): pending query for guided actions` (Fase 2a — store + InputArea)
4. `feat(dashboard): Analyze Folder dialog` (Fase 2b)
5. `feat(api): POST /api/folder/analyze` (Fase 3a — backend)
6. `feat(dashboard): folder analysis results panel` (Fase 3b — frontend)

---

## Definición de "hecho" (DoD)

### Fase 1 ✅
- [x] Quick Note en dashboard abre modal funcional
- [x] Tests API quick-note verdes (4/4)
- [x] i18n actualizado (desc opcional — no requerido)
- [x] Sin regresiones en chat FastPathToggles

### Fase 2 ✅
- [x] Analyze Folder: picker + 3 modos + chat con prompt
- [x] pendingChatAction en store + consume en InputArea
- [x] Engine-required deshabilita modos correctos

### Fase 3 ✅
- [x] API estructurada con política de paths
- [x] Panel de resultados con estética cybernetic
- [x] Save report + deep dive
- [x] `tests/test_folder_analysis.py` verde (11 tests)

### Global
- [x] `make test-stable` verde (173/173)
- [ ] `docs/frontend/CHANGELOG.md` actualizado con entrada por fase
- [ ] Manual QA en Tauri dev (no solo browser)

### Fase 4 ✅
- [x] Quick Note — selector de destino file/memory
- [x] Quick Note — post-save: Open in Chat + Index now
- [x] Analyze Folder — watched folder banner + add CTA
- [x] Dashboard — pushActivity tras guardar nota
- [x] Shortcut Cmd+Shift+N → Quick Note desde cualquier tab

---

## Manual QA (checklist humano)

### Quick Note ✅
1. Home → Quick Note → escribir → guardar → ver path en confirmación
2. Verificar archivo en `~/Desktop/CerebroFiles` (o path configurado)
3. Chat → botón Quick Note en FastPathToggles → mismo comportamiento
4. Cancel / Escape cierra sin guardar
5. (Fase 4) Selector destino file/memory visible si `showPostSaveActions`
6. (Fase 4) Post-save: Open in Chat → navega a chat con prompt prefilled
7. (Fase 4) Post-save: Index now → inicia indexación del directorio
8. (Fase 4) Cmd+Shift+N → Quick Note desde cualquier tab

### Analyze Folder ✅
1. Home → Analyze Folder → elegir carpeta vigilada → Structure → Analyze
2. Results muestra stats (files, dirs, size, extensions, tree) en el dialog
3. Sin motor: modos content/full deshabilitados con tooltip
4. Browse elige carpeta fuera de watched list → funciona
5. Deep dive in chat navega a chat con prompt enriquecido + stats
6. Save report genera `.md` via POST /api/quick-note
7. Si API no disponible → fallback a chat con prompt simple (Fase 2)

---

## Referencias de código existente

| Patrón | Archivo |
|--------|---------|
| Action card con side-effect | `DashboardHome.tsx` + `workflows.ts` `setOpenCreateMode` |
| Modal | `components/shared/Dialog.tsx` |
| Quick Note completo | `components/chat/QuickNoteDialog.tsx` |
| Picker de carpeta Tauri | `components/settings/FolderManager.tsx` |
| Lista de carpetas | `components/shared/FolderList.tsx` |
| Indexación | `stores/settings.ts` `startIndexing` |
| Política de paths FS | `core/tools/handlers/filesystem.py` |
| Indexed files | `core/memory/vector_store.py` `get_indexed_files` |
| Diseño visual | `docs/frontend/cybernetic-design.md` |

---

## Registro de implementación

### Fase 0 + Fase 1 — 2026-06-26

**Archivos creados:**
| Archivo | Descripción |
|---------|-------------|
| `tests/test_quick_note_api.py` | 4 tests para POST /api/quick-note |

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `ui/tray/src/components/dashboard/DashboardHome.tsx` | Import QuickNoteDialog + AnalyzeFolderDialog, estados, refactor actions a discriminated union, render dialogs |
| `ui/tray/src/components/chat/QuickNoteDialog.tsx` | Prop opcional `showPostSaveActions` |

**Sin modificar (Fase 0-1):**
- `FastPathToggles.tsx`, `runtime.py`, `server.py`, i18n

### Fase 2 + Fase 3 — 2026-06-26

**Archivos creados:**
| Archivo | Descripción |
|---------|-------------|
| `ui/tray/src/components/dashboard/AnalyzeFolderDialog.tsx` | Diálogo completo: config + results screens, browse Tauri, fallback a chat |
| `ui/tray/src/utils/folderAnalysisPrompt.ts` | Prompt builder para 3 modos de análisis |
| `core/tools/folder_analysis.py` | Módulo puro de análisis de carpeta (stat-only) |
| `tests/test_folder_analysis.py` | 11 tests (7 unit + 4 API) |

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `ui/tray/src/stores/chat.ts` | Añadido `PendingChatAction`, `pendingChatAction`, `setPendingChatAction`, `consumePendingChatAction` |
| `ui/tray/src/components/chat/InputArea.tsx` | `useEffect([activeTab])` consume pending action, refactor `send` → `sendQuery(query)` |
| `ui/tray/src/components/dashboard/DashboardHome.tsx` | Import + estado + render `AnalyzeFolderDialog` |
| `ui/tray/server.py` | Import `analyze_folder`, `PathNotAuthorizedError`; modelos `FolderAnalyzeRequest/Response`; endpoint `POST /api/folder/analyze` |
| `ui/tray/src/api/client.ts` | Import `FolderAnalyzeRequest/Response`; función `analyzeFolder()` |
| `ui/tray/src/api/types.ts` | Interfaces `FolderAnalyzeRequest`, `FolderAnalyzeResponse`, `FolderFileEntry` |
| `ui/tray/src/locales/en.json` | +32 keys `folder.*` |
| `ui/tray/src/locales/es.json` | +32 keys `folder.*` |

**Sin modificar:**
- `runtime.py` — no se tocó
- `FastPathToggles.tsx` — sin cambios
- `core/agents/specialized.py` — sin cambios
- `core/tools/handlers/filesystem.py` — sin cambios (reutilizado)

### Fase 4 — 2026-06-26

**Archivos modificados:**
| Archivo | Cambio |
|---------|--------|
| `ui/tray/src/components/chat/QuickNoteDialog.tsx` | Selector destino (file/memory), post-save actions (Open in Chat, Index now), pushActivity |
| `ui/tray/src/stores/dashboard.ts` | Añadido `quickNoteOpen`, `setQuickNoteOpen`, `pushActivity` |
| `ui/tray/src/components/dashboard/DashboardHome.tsx` | Usa store para `quickNoteOpen` en vez de estado local |
| `ui/tray/src/components/dashboard/AnalyzeFolderDialog.tsx` | Watched folder banner + add CTA |
| `ui/tray/src/layouts/MainLayout.tsx` | Keyboard shortcut `Cmd+Shift+N` |
| `ui/tray/src/locales/en.json` | +8 keys (`note.dest_*`, `note.open_in_chat`, `note.index_now`, `folder.analyze_not_watched`, etc.) |
| `ui/tray/src/locales/es.json` | +8 keys (traducciones) |

**No implementado (explícito):**
- Apple Notes como destino (solo macOS, requiere proxy backend)
- Persistencia de dashboard activity en backend
- Registro Tauri nativo del shortcut (usa DOM event listener)

**Tests:**
| Suite | Resultado |
|-------|-----------|
| `tests/test_quick_note_api.py` | 4/4 ✅ |
| `tests/test_folder_analysis.py` | 11/11 ✅ |
| `make test-stable` | 173/173 ✅ |

---

## Fuera de alcance (explícito)

- Nuevo fast path en `runtime.py` para "analyze folder"
- Cambiar orden del pipeline (math → file write → …)
- Análisis recursivo sin límites
- Soporte Windows para Apple Notes
- Refactor de `DashboardHome` a router de acciones genérico (opcional, no obligatorio)
- Sustituir el chat por un visor de carpetas tipo Finder
