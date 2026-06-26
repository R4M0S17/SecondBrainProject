# Pestaña Flujos — Plan de implementación por fases

> **Estado:** Fases 0–3.4 y Fase 4 parcial implementadas (2026-06-25) · Programación (APScheduler) pendiente post-v0.2  
> **Relacionado:** [`desktop_automation_workflows.md`](../implementation/desktop_automation_workflows.md), [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md), [`cybernetic-design.md`](../frontend/cybernetic-design.md)

---

## Registro de implementación (changelog)

### Fase 0 — Preparación ✅

| Área | Cambio |
|------|--------|
| **Frontend** | `WorkflowPanel` → `WorkflowHub` (orquestador); esqueleto de subcomponentes en `ui/tray/src/components/automation/` |
| **Tipos** | `WorkflowStep`, `WorkflowRun`, `RecordingStatus`, `WorkflowRecipe`, `workflow_type`, `steps` en `api/types.ts` |
| **i18n** | Namespace `workflows.*` en `locales/es.json` y `en.json` |
| **Layout** | `MainLayout.tsx` importa `WorkflowHub` |

### Fase 1 — Pestaña usable sin chat ✅

| Área | Cambio |
|------|--------|
| **Backend** | `core/automation/service.py` — start/stop/cancel/status + generalización compartida con tools |
| **API** | `POST /record/start`, `GET /record/status`, `POST /record/stop`, `POST /record/cancel`, `PATCH /{id}` |
| **SQLite** | Columnas `steps`, `workflow_type`; migración en `WorkflowStore.__init__` |
| **Generalizer** | Prompt LLM incluye `steps`; fallback `events_to_steps()` |
| **Frontend** | Grabación UI (`RecordingBanner`, `RecordingPreview`), empty state con `ActionCard`, lista + detalle con pasos |
| **Store** | `startRecording`, `pollRecordingStatus`, `stopRecording`, `cancelRecording`, `updateWorkflow` |
| **Dashboard** | "Crear Flujo" → `setOpenCreateMode("record")` + pestaña workflows |
| **Tests** | `tests/test_workflow_api.py` (record + PATCH), `WorkflowHub.test.tsx` |

### Fase 2 — Ejecución interactiva ✅

| Área | Cambio |
|------|--------|
| **SQLite** | Tabla `workflow_runs` (id, workflow_id, started/finished, success, output, error, params) |
| **Service** | `execute_desktop_workflow()` — `osascript -e` + argv por parámetros; `run_workflow()` persiste historial |
| **API** | `POST /{id}/run` body `{ params }` → `{ result, success, run_id, error }`; `GET /{id}/runs?limit=N` |
| **Tools** | `make_run_workflow` delega en `service.run_workflow` |
| **Frontend** | `WorkflowParamForm`, `WorkflowRunConfirm`, `WorkflowRunResult`, `WorkflowRunHistory` |
| **UX** | Confirmación antes de ejecutar; spinner solo en botón Run; borde éxito/error; delete confirm; ▶ hover en `WorkflowCard` |
| **Store** | `isRunning`, `runs`, `loadRuns`, `execute(id, params)` |
| **Tests** | Run con params, run fallido guarda error, list runs; `WorkflowParamForm.test.tsx` |

### Fase 3 — Recetas del asistente ✅

| Área | Cambio |
|------|--------|
| **Backend** | `core/automation/recipes.py` — 3 plantillas: `calendar_to_file`, `search_pdfs_desktop`, `add_reminder` |
| **Handlers** | Reutilizan `fetch_calendar_read_answer` + `write_file`, `search_files`, `add_reminder` |
| **API** | `GET /recipes/templates`, `POST /recipes` `{ template_id, name? }` |
| **Run** | `POST /{id}/run` detecta `workflow_type=recipe` → handler por `recipe_key` (sin osascript) |
| **SQLite** | Columna `recipe_key` en workflows |
| **Frontend** | `WorkflowTypeTabs` activos (rutinas / recetas / plantillas), `RecipeTemplateGrid`, empty state enlaza plantillas |
| **Store** | `viewTab`, `templates`, `loadTemplates`, `installTemplate` |
| **Tests** | `tests/test_workflow_recipes.py`; regresión `make test-stable` verde |

### Fase 3.4 — Guardar desde chat ✅

| Área | Cambio |
|------|--------|
| **Backend** | `core/automation/from_conversation.py` — infiere `recipe_key` desde `tools_called` del turno |
| **API** | `POST /api/workflows/from-conversation` `{ conversation_id, turn_index, name? }` |
| **Frontend** | `MessageFooter` — botón "Guardar como receta" si hubo tools exitosas (archivo/búsqueda/recordatorio) |
| **UX** | Tras guardar → pestaña Flujos, tab Recetas, workflow seleccionado |
| **Tests** | `test_from_conversation_*` en `test_workflow_api.py`, `tests/test_workflow_from_conversation.py` |

### Fase 4 — Refinamiento (parcial) ✅

| Área | Cambio |
|------|--------|
| **Export/import** | `GET /{id}/export`, `POST /import`; botones Exportar/Importar en `WorkflowHeader` + `WorkflowDetail` |
| **Dry-run** | `POST /{id}/run` con `dry_run: true`; checkbox en `WorkflowRunConfirm`; no ejecuta `osascript` |
| **Editar pasos** | `PATCH /{id}` acepta `steps` y `applescript`; edición inline en `WorkflowDetail` |
| **Privacidad grabación** | Aviso en `RecordingBanner` (`workflows.recording_privacy`) |
| **Accesibilidad** | CTA "Abrir Ajustes de Accesibilidad" en errores de grabador (`utils/macosSettings.ts`) |
| **Header** | Icono `account_tree` → `setTab("workflows")` en `Header.tsx` / `MainLayout.tsx` |
| **Pendiente** | Programación recurrente (APScheduler + tabla `schedules`) — post-v0.2 |

### Comandos de verificación

```bash
make test tests/test_workflow_api.py tests/test_workflow_recipes.py tests/test_workflow_from_conversation.py -q
make test-stable
cd ui/tray && npm run test -- --run src/components/automation/
```

### Archivos principales tocados

```
core/automation/
  service.py          # grabación + ejecución desktop/recipe + historial + dry-run
  recipes.py          # plantillas y handlers de receta (Fase 3)
  from_conversation.py # receta desde chat + export/import (Fase 3.4 / 4)
  workflow_store.py   # steps, workflow_type, recipe_key, workflow_runs
  generalizer.py      # steps en output LLM
  tools.py            # delega a service

ui/tray/server.py     # /api/workflows/* completo
ui/tray/src/components/automation/   # WorkflowHub + subcomponentes
ui/tray/src/stores/workflows.ts
tests/test_workflow_api.py
tests/test_workflow_recipes.py
tests/test_workflow_from_conversation.py
```

---

## 1. Resumen ejecutivo

El botón del dashboard **"Crear Flujo / Construye flujos automatizados"** (`account_tree`) lleva a la pestaña `workflows`, pero hoy esa pestaña es un visor técnico de AppleScript que depende del chat para crear flujos. El usuario espera un **centro de rutinas de Mac**: grabar, parametrizar, ejecutar y reutilizar acciones.

**Objetivo del plan:** transformar la pestaña en una experiencia completa, visualmente coherente con el resto de Cerebro (Cybernetic Minimalism + dashboard), sin depender del chat para las acciones básicas.

**Posicionamiento (mensaje al usuario):**

> *Rutinas de Mac: acciones que grabas una vez y repites con un clic.*

**Dos tipos de flujo en la misma pestaña:**

| Tipo | Origen | Ejemplo |
|------|--------|---------|
| **Rutina de escritorio** | Grabación CGEventTap → LLM → AppleScript | Abrir apps, clics repetitivos, atajos de teclado |
| **Receta del asistente** | Plantilla o guardado desde chat | Exportar calendario a Markdown, buscar PDFs, recordatorio |

---

## 2. Estado actual (post Fase 3.4 + Fase 4 parcial)

### Backend ✅

| Pieza | Ubicación | Estado |
|-------|-----------|--------|
| Grabador macOS | `core/automation/recorder.py` | ✅ |
| Generalizador LLM | `core/automation/generalizer.py` | ✅ + `steps` |
| Persistencia | `core/automation/workflow_store.py` | ✅ + runs + recipe_key |
| Servicio compartido | `core/automation/service.py` | ✅ grabación + run + dry-run |
| Recetas | `core/automation/recipes.py` | ✅ 3 plantillas |
| Desde chat | `core/automation/from_conversation.py` | ✅ inferencia + export/import |
| Tools agente | `core/automation/tools.py` | ✅ delega a service |
| API REST | `ui/tray/server.py` | ✅ record, run+params, runs, recipes, from-conversation, export/import |
| Tests | `tests/test_workflow_*.py` | ✅ |

### Frontend ✅

| Pieza | Ubicación | Estado |
|-------|-----------|--------|
| Hub principal | `WorkflowHub.tsx` | ✅ tabs + grabación + plantillas + import |
| Ejecución | `WorkflowParamForm`, `WorkflowRunConfirm`, `WorkflowRunResult`, `WorkflowRunHistory` | ✅ + dry-run |
| Plantillas | `RecipeTemplateGrid`, `WorkflowTypeTabs` | ✅ |
| Chat → receta | `MessageFooter.tsx` | ✅ |
| Header shortcut | `Header.tsx` | ✅ `account_tree` |
| Store | `stores/workflows.ts` | ✅ completo |
| i18n | `workflows.*` ES/EN | ✅ |
| Tests | `WorkflowHub.test.tsx`, `WorkflowParamForm.test.tsx` | ✅ |

### Brecha cerrada

```
Dashboard "Crear Flujo"  →  WorkflowHub (grabar / plantillas / ejecutar)  ✅
Chat "Guardar como receta"  →  WorkflowHub (tab Recetas)  ✅
Header account_tree  →  pestaña Flujos  ✅
```

### Pendiente (Fase 4 scheduling)

- APScheduler + tabla `schedules` + UI "Ejecutar cada…" — explícitamente post-v0.2

---

## 3. Principios de diseño (estética Cerebro)

Seguir el sistema **Cybernetic Minimalism** ya aplicado en dashboard, Memory Browser y Documents:

### Tokens (fuente: `tailwind.config.js`, `index.css`)

| Uso | Clase / valor |
|-----|----------------|
| Fondo página | `bg-background` (`#131317`) |
| Tarjetas / paneles | `bg-surface-container-low/40`, `border-outline-variant/10` |
| Hover interactivo | `hover:bg-surface-container/60`, `active:scale-[0.98]` |
| Acento primario (CTA) | `bg-primary-container` (`#2563eb`), `text-on-primary-container` |
| Éxito / Run | `text-success-green` (`#4ade80`), fondo `bg-[#22c55e]/20` |
| Advertencia / grabación | `text-tertiary-fixed-dim`, pulso `status-dot-pulse` |
| Labels sección | `text-label-caps text-outline tracking-wider uppercase` |
| Código / script | `font-mono text-code`, bloque `bg-surface-container-low rounded-xl` |
| Entrada animación | `dashboard-enter`, `stagger-1` … `stagger-5` |

### Componentes a reutilizar (no reinventar)

| Componente | Ruta | Uso en Flujos |
|------------|------|---------------|
| `ActionCard` | `dashboard/ActionCard.tsx` | Plantillas sugeridas en empty state |
| `ConfirmModal` | `shared/ConfirmModal.tsx` | Confirmar ejecución de rutina |
| `Toast` | `shared/Toast.tsx` | Éxito/error post-run |
| `Tooltip` | `ui/Tooltip.tsx` | Iconos de toolbar |
| Patrón slide-over | `DocumentsPanel`, `MemoryBrowserPanel` | **No** usar overlay; Flujos es pestaña principal (`MainLayout`) |

### Reglas visuales

1. **Sin gradientes decorativos** — profundidad por capas de `surface-container-*` y bordes 1px.
2. **Material Symbols** para iconos (`account_tree`, `fiber_manual_record`, `play_arrow`, etc.).
3. **Densidad media** — más rico que el panel actual, menos denso que un IDE.
4. **Jerarquía clara:** header fijo → sub-nav (tabs) → lista + detalle en split view.
5. **i18n obligatorio** — todas las cadenas vía `react-i18next`; ES por defecto (`CEREBRO_LOCALE`).

---

## 4. Arquitectura objetivo

```
┌─────────────────────────────────────────────────────────────────┐
│  WorkflowHub (pestaña workflows en MainLayout)                  │
├─────────────────────────────────────────────────────────────────┤
│  WorkflowHeader     título + CTA "Grabar" + búsqueda            │
│  WorkflowTypeTabs   [ Mis rutinas ] [ Recetas ] [ Plantillas ]  │
├──────────────┬──────────────────────────────────────────────────┤
│ WorkflowList │  WorkflowDetail / WorkflowEmpty / RecordingView  │
│ (sidebar)    │  • pasos humanos                               │
│              │  • formulario parámetros                        │
│              │  • historial runs                               │
│              │  • AppleScript colapsable (avanzado)            │
└──────────────┴──────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   stores/workflows.ts            api/client.ts
         │                              │
         └──────────►  /api/workflows/*  (+ record/*, recipes/*)
                              │
                    WorkflowStore + Recorder + Generalizer
                              │
                    ~/.cerebro/db/automation.sqlite
```

---

## 5. Layout objetivo (wireframe)

### Vista principal — con flujos

```
┌─ Flujos de Mac ──────────────────────── [ 🔴 Grabar ] [ Buscar… ] ─┐
│  [ Mis rutinas ]  Recetas   Plantillas                              │
├─────────────────┬───────────────────────────────────────────────────┤
│ MIS RUTINAS     │  Exportar capturas a carpeta                      │
│                 │  Mueve screenshots del escritorio a ~/Archivos    │
│ ▶ Exportar…  5× │  ┌─ Pasos ─────────────────────────────────────┐ │
│   Organizar… 2× │  │ 1. Activar Finder                           │ │
│   Abrir stack 0×│  │ 2. Abrir carpeta Escritorio                 │ │
│                 │  │ 3. Seleccionar archivos PNG                 │ │
│ + Nueva rutina  │  └─────────────────────────────────────────────┘ │
│                 │  Parámetros                                       │
│                 │  [ Carpeta destino: ~/Desktop/Capturas    ]       │
│                 │  [ Ejecutar ]  [ Renombrar ]  [ Eliminar ]        │
│                 │  ▼ AppleScript (avanzado)                         │
│                 │  Últimas ejecuciones · hace 2h · ✓ éxito          │
└─────────────────┴───────────────────────────────────────────────────┘
```

### Empty state — primera visita

```
┌─ Flujos de Mac ──────────────────────────────────── [ Grabar ] ─┐
│                                                                   │
│     account_tree (grande, primary-container/80)                   │
│     Crea tu primera rutina                                        │
│     Graba acciones en tu Mac o empieza con una plantilla          │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│  │ 🔴 Grabar   │ │ 📅 Calendario│ │ 📁 Archivos │  ← ActionCards │
│  │ rutina      │ │ → Markdown  │ │ en Desktop  │                 │
│  └─────────────┘ └─────────────┘ └─────────────┘                 │
└───────────────────────────────────────────────────────────────────┘
```

### Modo grabación (overlay compacto, no fullscreen)

```
┌─ Grabando rutina ─────────────────────────────────────────────────┐
│  ● REC  0:42   12 acciones   Safari · Finder · Notes               │
│  ┌─ Vista previa en vivo ─────────────────────────────────────┐  │
│  │ 10:41  [Safari] click en barra de direcciones               │  │
│  │ 10:41  [Safari] key 'return'                                │  │
│  │ 10:42  [Notes] click nueva nota                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│              [ Cancelar ]     [ Detener y crear flujo ]           │
└───────────────────────────────────────────────────────────────────┘
```

---

## 6. Plan por fases

### Fase 0 — Preparación (0.5 día)

**Objetivo:** Estructura de archivos y contratos sin cambiar comportamiento visible.

| Tarea | Detalle |
|-------|---------|
| Renombrar/refactor panel | `WorkflowPanel.tsx` → orquestador `WorkflowHub.tsx` que compone subcomponentes |
| Esqueleto de componentes | Crear archivos vacíos listados en §8 |
| Claves i18n | Añadir namespace `workflows.*` en `es.json` y `en.json` |
| Tipos TS | Extender `Workflow`, añadir `WorkflowRun`, `RecordingStatus`, `WorkflowRecipe` |
| Documentar en README plans | Entrada en `docs/plans/README.md` |

**Criterio de done:** `npm run build` (frontend) sin errores; panel actual sigue funcionando.

---

### Fase 1 — Pestaña usable sin chat (1 semana)

**Objetivo:** Cerrar la brecha "Crear Flujo" → acción inmediata.

#### 1.1 Backend — API de grabación

Nuevos endpoints en `ui/tray/server.py`:

| Método | Ruta | Body | Respuesta |
|--------|------|------|-----------|
| `POST` | `/api/workflows/record/start` | — | `{ status: "recording", started_at }` |
| `GET` | `/api/workflows/record/status` | — | `{ recording, event_count, apps[], duration_sec }` |
| `POST` | `/api/workflows/record/stop` | `{ name?: string }` | `Workflow` creado |
| `POST` | `/api/workflows/record/cancel` | — | `{ status: "cancelled" }` |
| `PATCH` | `/api/workflows/{id}` | `{ name?, description?, tags? }` | `Workflow` |

Implementación: reutilizar `app_state.recorder` y lógica de `make_stop_recording` en `core/automation/tools.py` (extraer a `core/automation/service.py` para no duplicar).

**Permisos macOS:** si `recorder` es `None` (sin pyobjc) o falta Accesibilidad, devolver `503` con mensaje i18n-key `workflows.error.accessibility_required`.

#### 1.2 Backend — Pasos legibles

Al generalizar, persistir `steps` en SQLite:

```sql
ALTER TABLE workflows ADD COLUMN steps TEXT NOT NULL DEFAULT '[]';
ALTER TABLE workflows ADD COLUMN workflow_type TEXT NOT NULL DEFAULT 'desktop';
-- workflow_type: 'desktop' | 'recipe'
```

Actualizar `generalizer.py` para incluir `steps: [{order, app, action, detail}]` en el JSON del LLM.

Migración: en `WorkflowStore.__init__`, `PRAGMA table_info` + `ALTER` si falta columna.

#### 1.3 Frontend — UI Fase 1

| Componente | Comportamiento |
|------------|----------------|
| `WorkflowHub` | Layout split + animación `dashboard-enter` |
| `WorkflowHeader` | Título i18n, botón primario "Grabar rutina", búsqueda local |
| `WorkflowList` | Tarjetas con nombre, `run_count`, última ejecución, icono tipo |
| `WorkflowDetail` | Nombre, descripción, lista de pasos, metadata |
| `WorkflowEmpty` | Hero + 3 `ActionCard` (grabar + 2 plantillas deshabilitadas hasta Fase 3) |
| `RecordingBanner` | Barra fija inferior o top durante grabación; polling `record/status` cada 1s |
| `RecordingPreview` | Scroll de eventos en lenguaje humano |

**Store (`workflows.ts`):**

```typescript
// Nuevos métodos
startRecording(), pollRecordingStatus(), stopRecording(name?), cancelRecording()
updateWorkflow(id, patch)
```

**Flujo UX grabación:**

1. Usuario pulsa "Grabar rutina" → `POST record/start` → banner con pulso rojo.
2. Realiza acciones en el Mac.
3. "Detener y crear flujo" → `POST record/stop` → spinner "Generando rutina…" (LLM).
4. Navega automáticamente al detalle del workflow creado.

#### 1.4 i18n Fase 1

Claves mínimas (`workflows.*`):

- `title`, `subtitle`, `record_start`, `record_stop`, `record_cancel`, `recording_banner`
- `empty_title`, `empty_subtitle`, `empty_record_cta`
- `list_runs`, `last_run`, `delete`, `run`, `rename`, `steps`, `advanced_script`
- `error.accessibility_required`, `error.recorder_unavailable`, `error.too_few_events`

#### 1.5 Tests Fase 1

| Archivo | Casos |
|---------|-------|
| `tests/test_workflow_api.py` | + record start/stop/cancel, PATCH, 503 sin recorder |
| `tests/test_workflow_generalizer.py` | (opcional) mock LLM devuelve `steps` |
| `ui/tray/src/components/automation/WorkflowHub.test.tsx` | empty state, lista, selección |

**Gate Fase 1:**

```bash
make test tests/test_workflow_api.py -q
# Manual: dashboard → Crear Flujo → Grabar → 3+ acciones → Detener → aparece en lista
```

---

### Fase 2 — Ejecución interactiva y pulido visual (1 semana)

**Objetivo:** Ejecutar flujos con parámetros, confirmación y feedback; UI premium.

#### 2.1 Backend — Run con parámetros e historial

| Método | Ruta | Cambio |
|--------|------|--------|
| `POST` | `/api/workflows/{id}/run` | Body opcional: `{ "params": { "folder": "~/Desktop" } }` |
| `GET` | `/api/workflows/{id}/runs` | Lista últimas N ejecuciones |

Nueva tabla:

```sql
CREATE TABLE workflow_runs (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    started_at  REAL NOT NULL,
    finished_at REAL,
    success     INTEGER NOT NULL,
    output      TEXT,
    error       TEXT,
    params      TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);
```

Inyectar parámetros en AppleScript: el generalizador ya genera `on run {param_list}`; el runner sustituye o pasa argumentos vía `osascript -e` con handler.

#### 2.2 Frontend — Formulario y confirmación

| Componente | Detalle |
|------------|---------|
| `WorkflowParamForm` | Inputs por tipo (`string`, `path`, `number`); estilo `input-glow` |
| `WorkflowRunConfirm` | Variante de `ConfirmModal`: lista apps/pasos + advertencia |
| `WorkflowRunResult` | Panel éxito/error con salida; auto-scroll |
| `WorkflowRunHistory` | Lista colapsable; icono ✓/✗, duración, timestamp relativo |
| `WorkflowScriptPanel` | AppleScript en `<details>` colapsado por defecto |
| `WorkflowCard` | Tarjeta en lista: botón ▶ flotante en hover, badge tipo |

**Micro-interacciones:**

- Run: botón con `disabled` + spinner inline; no bloquear toda la pestaña.
- Éxito: borde sutil `border-success-green/30` en resultado.
- Eliminar: confirmación secundaria (reutilizar patrón `ConfirmModal`).
- Renombrar: inline edit en header del detalle (doble clic o icono `edit`).

#### 2.3 Pulido estético

- Aplicar `stagger-*` al cargar lista.
- Sidebar lista: ancho `w-80` (320px = `panel-width`), `scrollbar-auto`.
- Detalle: padding `px-6 md:px-10` como `DashboardHome`.
- Empty state: icono `account_tree` 48px, `text-primary-container/80`.
- Grabación: punto rojo con `status-dot-pulse` + tiempo monospace `font-mono`.

#### 2.4 Tests Fase 2

- API: run con params, historial, run fallido guarda error.
- Frontend: test de formulario de parámetros y confirmación.

**Gate Fase 2:**

```bash
make test tests/test_workflow_api.py -q
# Manual: workflow con parámetro → formulario → confirmar → ejecutar → historial visible
```

---

### Fase 3 — Recetas del asistente (1–1.5 semanas)

**Objetivo:** Flujos alineados con el wedge de Cerebro (calendario, archivos, recordatorios).

#### 3.1 Concepto

Las **recetas** no usan AppleScript. Son definiciones declarativas que el backend ejecuta vía agente o fast paths existentes.

```json
{
  "id": "recipe-calendar-week-md",
  "workflow_type": "recipe",
  "name": "Exportar semana a Markdown",
  "description": "Crea un archivo con tus eventos de esta semana",
  "recipe_key": "calendar_to_file",
  "parameters": [
    { "name": "filename", "type": "string", "default": "semana.md" }
  ],
  "steps": [
    { "order": 1, "action": "Leer calendario de esta semana" },
    { "order": 2, "action": "Generar Markdown" },
    { "order": 3, "action": "Guardar en CEREBRO_FILES_PATH" }
  ]
}
```

#### 3.2 Backend

| Tarea | Detalle |
|-------|---------|
| Plantillas built-in | `core/automation/recipes.py` — 3 recetas: calendario→md, buscar PDFs, recordatorio |
| `GET /api/workflows/recipes/templates` | Lista plantillas (no persistidas) |
| `POST /api/workflows/recipes` | Instancia plantilla → fila en `workflows` con `workflow_type=recipe` |
| Run receta | `POST /api/workflows/{id}/run` detecta tipo → llama handler dedicado (no `osascript`) |

Handlers de receta reutilizan:

- `file_write_calendar_fusion` para calendario→archivo
- `search_files` fast path
- reminder fast path

#### 3.3 Frontend

| Componente | Detalle |
|------------|---------|
| `WorkflowTypeTabs` | Mis rutinas \| Recetas \| Plantillas |
| `RecipeTemplateGrid` | Grid de `ActionCard` con plantillas built-in |
| `RecipeInstallButton` | "Añadir a mis recetas" → POST recipes |
| Badge en lista | `desktop` = icono `desktop_mac`, `recipe` = icono `smart_toy` |

**Empty state actualizado:** las 3 tarjetas del hero enlazan a plantillas reales (Fase 3).

#### 3.4 Integración chat ✅

- En `MessageFooter`: si el mensaje usó tools de calendario/archivo exitosamente → botón "Guardar como receta".
- `POST /api/workflows/from-conversation` con `conversation_id` + `turn_index`.

#### 3.5 Tests Fase 3

- `tests/test_workflow_recipes.py` — plantillas, instalar, ejecutar receta calendario (mock calendar).
- Regresión: `make test-stable` (no romper fast paths).

**Gate Fase 3:**

```bash
make test-stable
make test tests/test_workflow_recipes.py tests/test_workflow_api.py -q
# Manual E2: "Exportar semana" desde pestaña Flujos → archivo en ~/Desktop/CerebroFiles
```

---

### Fase 4 — Programación y refinamiento (post-v0.2, opcional)

**Objetivo:** Repetición automática y editor ligero. Solo iniciar si Fases 1–3 estables.

| Feature | Backend | Frontend |
|---------|---------|----------|
| Programar ejecución | APScheduler job; `schedules` en SQLite | UI "Ejecutar cada…" con select día/hora |
| Editar pasos post-grabación | `PATCH` con `steps` + `applescript` | Lista editable en detalle ✅ |
| Exportar/importar | `GET /api/workflows/{id}/export` → JSON | Export en detalle + Import en header ✅ |
| Dry-run | Run con `dry_run: true` | Checkbox en confirmación ✅ |

**No incluir en v1:** editor nodos drag-and-drop tipo n8n (coste alto, poco valor en 8 GB).

---

## 7. Contratos API consolidados

### Workflow (respuesta extendida)

```typescript
interface Workflow {
  id: string;
  name: string;
  description: string;
  workflow_type: "desktop" | "recipe";
  applescript: string;          // vacío para recipe
  recipe_key?: string;          // solo recipe
  parameters: WorkflowParameter[];
  steps: WorkflowStep[];
  tags: string[];
  created_at: number;
  updated_at: number;
  run_count: number;
  last_run: number | null;
}

interface WorkflowStep {
  order: number;
  app?: string;
  action: string;
  detail?: string;
}

interface WorkflowRun {
  id: string;
  workflow_id: string;
  started_at: number;
  finished_at: number | null;
  success: boolean;
  output: string | null;
  error: string | null;
  params: Record<string, string>;
}
```

### Códigos de error HTTP

| Código | Situación |
|--------|-----------|
| `404` | Workflow no encontrado |
| `409` | Grabación ya en curso / no hay grabación activa |
| `422` | Menos de 3 eventos al detener |
| `503` | Recorder no disponible (pyobjc / permisos) |

---

## 8. Estructura de archivos (objetivo)

```
ui/tray/src/
├── components/automation/
│   ├── WorkflowHub.tsx              # Orquestador (reemplaza WorkflowPanel)
│   ├── WorkflowHeader.tsx
│   ├── WorkflowTypeTabs.tsx
│   ├── WorkflowList.tsx
│   ├── WorkflowCard.tsx
│   ├── WorkflowDetail.tsx
│   ├── WorkflowEmpty.tsx
│   ├── WorkflowParamForm.tsx
│   ├── WorkflowRunConfirm.tsx
│   ├── WorkflowRunResult.tsx
│   ├── WorkflowRunHistory.tsx
│   ├── WorkflowScriptPanel.tsx
│   ├── RecordingBanner.tsx
│   ├── RecordingPreview.tsx
│   ├── RecipeTemplateGrid.tsx
│   └── WorkflowHub.test.tsx
├── stores/workflows.ts              # Extendido
└── locales/
    ├── es.json                      # workflows.*
    └── en.json

core/automation/
├── recorder.py                      # Sin cambios mayores
├── generalizer.py                   # + steps en output
├── workflow_store.py                # + steps, workflow_type, runs table
├── service.py                       # NUEVO: start/stop/cancel/run lógica compartida
├── recipes.py                       # NUEVO Fase 3
└── tools.py                         # Delega a service.py

tests/
├── test_workflow_api.py             # Extendido
└── test_workflow_recipes.py         # NUEVO Fase 3
```

---

## 9. Integración con el resto del programa

| Punto | Cambio |
|-------|--------|
| `MainLayout.tsx` | Importar `WorkflowHub` en lugar de `WorkflowPanel` |
| `DashboardHome.tsx` | Opcional: `setTab("workflows")` + flag `openRecord=true` al pulsar Crear Flujo |
| `LeftSidebar.tsx` | Actualizar `sidebar.workflows` → "Flujos" (ES) |
| `Header.tsx` | Acceso directo `account_tree` → pestaña Flujos ✅ |
| `stores/tab.ts` | Sin cambio (`workflows` ya existe) |
| Permisos macOS | Reutilizar patrón de `StorageAccessButton` / wizard para Accesibilidad |

### Dashboard — deep link sugerido

```typescript
// stores/workflows.ts
openCreateMode: "list" | "record" | "templates" | null;

// DashboardHome ActionCard onClick:
setWorkflowCreateMode("record"); // o "templates"
setTab("workflows");
```

---

## 10. Criterios de aceptación globales (release)

| # | Escenario | Resultado esperado |
|---|-----------|-------------------|
| W1 | Dashboard → Crear Flujo | Pestaña con empty state útil o lista; nunca mensaje "pregunta al agente" |
| W2 | Grabar rutina (5+ acciones) | Workflow creado con pasos legibles en < 30s (LLM) |
| W3 | Ejecutar rutina desktop | Confirmación → ejecución → resultado visible |
| W4 | Plantilla "Calendario → Markdown" | Archivo creado sin usar chat |
| W5 | Sin permisos Accesibilidad | Mensaje claro + enlace a Ajustes (no crash) |
| W6 | i18n ES | Toda la pestaña traducida |
| W7 | Estética | Mismos tokens que dashboard; animaciones stagger; sin estilos inline |
| W8 | Regresión | `make test-stable` verde |

---

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| AppleScript frágil (resolución, timing) | Recetas del asistente para calendario/archivos; script colapsable + edición manual Fase 2 |
| LLM 2B falla al generalizar | Timeout 15s; mostrar error; opción "Reintentar" o guardar eventos crudos |
| Grabación captura datos sensibles | Aviso en banner; no persistir eventos crudos tras generalizar |
| Polling grabación consume CPU | Intervalo 1s solo mientras `recording=true`; detener al stop/cancel |
| Scope creep (editor visual) | Fase 4 explícitamente opcional; no canvas en Fases 1–3 |

---

## 12. Orden de implementación recomendado

```
Fase 0 (esqueleto)
    ↓
Fase 1.1 API record + PATCH
Fase 1.2 steps en SQLite/generalizer
Fase 1.3 UI hub + grabación + empty state
    ↓  gate: test_workflow_api + manual grabación
Fase 2.1 run params + historial
Fase 2.2 formulario + confirmación + pulido visual
    ↓  gate: ejecución con parámetros
Fase 3.1 recipes backend
Fase 3.2 tabs + plantillas + integración dashboard
    ↓  gate: make test-stable + E2 calendario
Fase 4 (opcional, post-v0.2)
```

**Estimación total:** 3–4 semanas (1 desarrollador), alineado con ventana post-Fase 1 de `CURRENT_FOCUS.md`.

---

## 13. Referencias

- Implementación actual: [`docs/implementation/desktop_automation_workflows.md`](../implementation/desktop_automation_workflows.md)
- Design system: [`docs/frontend/cybernetic-design.md`](../frontend/cybernetic-design.md)
- Patrón panel similar: [`docs/frontend/MEMORY_BROWSER.md`](../frontend/MEMORY_BROWSER.md)
- Fast paths (no romper): [`docs/architecture/fast-paths.md`](../architecture/fast-paths.md)
- Plan maestro: [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md)
