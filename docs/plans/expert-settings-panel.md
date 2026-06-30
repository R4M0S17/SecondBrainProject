# Plan: Panel de Expert Settings — Implementación por Fases

> **Objetivo:** Crear un panel de configuración avanzada de tipo "ventana de preferencias profesional" accesible desde el panel lateral de Settings actual. Consolidar todas las opciones técnicas/de experto fuera del panel lateral rápido, manteniendo ese panel limpio para el usuario casual.
>
> **Estado:** ✅ Completado — todas las fases implementadas + Models section (2026-06-29)
>
> **Estimación total:** ~10–14 horas de desarrollo
>
> **Prerrequisito:** Panel lateral de Settings (`SettingsPanel.tsx`) funcionando correctamente. Tool Manager ya integrado en Settings (completado 2026-06-29).

---

## Índice

- [Arquitectura general](#arquitectura-general)
- [Fase 1 — Shell del modal y navegación](#fase-1--shell-del-modal-y-navegación)
- [Fase 2 — Tool Manager (migración)](#fase-2--tool-manager-migración)
- [Fase 3 — Sección Inference](#fase-3--sección-inference)
- [Fase 4 — Sección Memory & RAG](#fase-4--sección-memory--rag)
- [Fase 5 — Providers, API Keys & Paths](#fase-5--providers-api-keys--paths)
- [Fase 6 — Web Search & Fleet](#fase-6--web-search--fleet)
- [Fase 7 — Observability](#fase-7--observability)
- [Fase 8 — Pulido final y keyboard shortcuts](#fase-8--pulido-final-y-keyboard-shortcuts)
- [Checklist final](#checklist-final)

---

## Arquitectura general

### Modelo mental

El sistema de Settings quedará en dos capas:

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings Lateral (320px slide-over)                            │
│  → Ajustes rápidos: idioma, modelo, backend, API key, folders   │
│  → Botón "Expert Settings ↗" al fondo                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ click
┌─────────────────────────────────────────────────────────────────┐
│  Expert Settings Modal (~85vw × ~88vh, centrado)               │
│                                                                  │
│  ┌──────────────┐  ┌───────────────────────────────────────┐   │
│  │ Nav lateral  │  │  Contenido de la sección activa       │   │
│  │              │  │                                       │   │
│  │ ○ Tools      │  │  (cambia al hacer click en nav)       │   │
│  │ ○ Inference  │  │                                       │   │
│  │ ○ Memory/RAG │  │                                       │   │
│  │ ○ Providers  │  │                                       │   │
│  │ ○ Paths      │  │                                       │   │
│  │ ○ Web Search │  │                                       │   │
│  │ ○ Fleet/RAM  │  │                                       │   │
│  │ ○ Debug      │  │                                       │   │
│  └──────────────┘  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Archivos nuevos a crear

```
ui/tray/src/components/expert/
  ExpertSettingsModal.tsx        ← shell principal del modal
  ExpertNavItem.tsx              ← ítem de la navegación lateral
  sections/
    ToolManagerSection.tsx       ← migrado desde SettingsPanel
    InferenceSection.tsx
    MemoryRagSection.tsx
    ProvidersSection.tsx
    PathsSection.tsx
    WebSearchSection.tsx
    FleetSection.tsx
    ObservabilitySection.tsx
```

### Archivos a modificar

```
ui/tray/src/components/settings/SettingsPanel.tsx   ← añadir botón de entrada + quitar Tool Manager
ui/tray/src/stores/settings.ts                      ← añadir estado expertOpen + activeExpertSection
ui/tray/src/locales/en.json                         ← traducciones nuevas
ui/tray/src/locales/es.json                         ← traducciones nuevas
```

### Gestión de estado del modal

Se añade al store existente `useSettingsStore` (ya usa zustand):

```typescript
// campos nuevos en SettingsState
expertOpen: boolean;
activeExpertSection: ExpertSection;
openExpert: (section?: ExpertSection) => void;
closeExpert: () => void;
setExpertSection: (section: ExpertSection) => void;

// tipo de sección
type ExpertSection =
  | "tools"
  | "inference"
  | "memory-rag"
  | "providers"
  | "paths"
  | "web-search"
  | "fleet"
  | "observability";
```

### Persistencia de parámetros avanzados

La mayoría de los parámetros avanzados se guardan en `~/.cerebro/state/config.json` vía el endpoint `/api/config` (PATCH). Los que no tienen endpoint aún requieren reinicio del servidor (se marca explícitamente en cada sección).

---

## Fase 1 — Shell del modal y navegación

**Tiempo estimado:** 2 horas
**Impacto:** Fundacional — sin esto las fases siguientes no tienen dónde montarse.

---

### 1.1 — Extender el store de settings

**Archivo:** `ui/tray/src/stores/settings.ts`

1. Añadir el tipo `ExpertSection` antes del interface de estado:

```typescript
export type ExpertSection =
  | "tools"
  | "inference"
  | "memory-rag"
  | "providers"
  | "paths"
  | "web-search"
  | "fleet"
  | "observability";
```

2. Añadir los campos al interface `SettingsState`:

```typescript
expertOpen: boolean;
activeExpertSection: ExpertSection;
openExpert: (section?: ExpertSection) => void;
closeExpert: () => void;
setExpertSection: (s: ExpertSection) => void;
```

3. Añadir implementación en el `create`:

```typescript
expertOpen: false,
activeExpertSection: "tools",
openExpert: (section = "tools") =>
  set({ expertOpen: true, activeExpertSection: section }),
closeExpert: () => set({ expertOpen: false }),
setExpertSection: (s) => set({ activeExpertSection: s }),
```

---

### 1.2 — Botón de entrada en SettingsPanel

**Archivo:** `ui/tray/src/components/settings/SettingsPanel.tsx`

Añadir al fondo del contenido scrollable, antes de `<ModelModeToggle />`:

```tsx
{/* Expert Settings */}
<section>
  <button
    onClick={() => openExpert()}
    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 transition-colors text-left group"
  >
    <div className="flex items-center gap-3">
      <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary-container transition-colors">
        tune
      </span>
      <div>
        <div className="text-[12px] font-medium text-on-surface">
          {t("settings.expert_title")}
        </div>
        <div className="text-[10px] text-on-surface-variant">
          {t("settings.expert_desc")}
        </div>
      </div>
    </div>
    <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary-container transition-colors">
      open_in_new
    </span>
  </button>
</section>
```

Importar `openExpert` del store:

```typescript
const { close, isOpen, patch, config, openExpert } = useSettingsStore();
```

---

### 1.3 — Shell del modal `ExpertSettingsModal.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/ExpertSettingsModal.tsx`

Estructura del componente:

```tsx
export default function ExpertSettingsModal() {
  // cierra con Escape
  // backdrop click cierra
  // layout: fixed inset-0 z-[70] flex items-center justify-center p-8
  // inner: w-[85vw] max-w-[1100px] h-[88vh] bg-surface-container rounded-2xl
  //        border border-outline-variant shadow-2xl flex overflow-hidden
  //
  // columna izquierda: w-[200px] shrink-0 bg-surface-container-low
  //                    border-r border-outline-variant p-3 flex flex-col gap-1
  //
  // columna derecha: flex-1 overflow-y-auto custom-scrollbar p-8
  //                  renderiza la sección activa
}
```

La columna izquierda muestra los `ExpertNavItem` agrupados con separadores:

```
──── Herramientas ────
  ○ Tool Manager

──── Motor ────
  ○ Inference
  ○ Memory & RAG
  ○ Providers & Keys
  ○ Paths

──── Red ────
  ○ Web Search
  ○ Fleet & RAM

──── Sistema ────
  ○ Observabilidad
```

---

### 1.4 — Componente `ExpertNavItem.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/ExpertNavItem.tsx`

```tsx
interface ExpertNavItemProps {
  id: ExpertSection;
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
}
```

Estilo activo: barra de 3px a la izquierda + `bg-primary-container/15 text-primary-container`.
Estilo inactivo: `text-on-surface-variant hover:bg-surface-container hover:text-on-surface`.

---

### 1.5 — Montar el modal en `MainLayout.tsx`

**Archivo:** `ui/tray/src/layouts/MainLayout.tsx`

1. Importar `ExpertSettingsModal` con lazy:

```typescript
const ExpertSettingsModal = lazy(() => import("../components/expert/ExpertSettingsModal"));
```

2. Leer el estado del store:

```typescript
const expertOpen = useSettingsStore((s) => s.expertOpen);
```

3. Añadir al JSX justo debajo del `{settingsOpen && <SettingsPanel />}`:

```tsx
{expertOpen && (
  <Suspense fallback={null}>
    <ExpertSettingsModal />
  </Suspense>
)}
```

---

### 1.6 — Traducciones de la shell

**Archivos:** `en.json` y `es.json`

```json
// es.json
"settings.expert_title": "Configuración Avanzada",
"settings.expert_desc": "Inference, memoria, paths, herramientas y más",
"expert.title": "Configuración de Experto",
"expert.nav.tools": "Tool Manager",
"expert.nav.inference": "Inference",
"expert.nav.memory_rag": "Memory & RAG",
"expert.nav.providers": "Providers & Keys",
"expert.nav.paths": "Paths",
"expert.nav.web_search": "Web Search",
"expert.nav.fleet": "Fleet & RAM",
"expert.nav.observability": "Observabilidad",
"expert.group.tools": "Herramientas",
"expert.group.engine": "Motor",
"expert.group.network": "Red",
"expert.group.system": "Sistema"
```

---

## Fase 2 — Tool Manager (migración)

**Tiempo estimado:** 1 hora
**Impacto:** Alto — quita el bloque más denso del panel lateral, aliviando Settings significativamente.

---

### 2.1 — Crear `ToolManagerSection.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/sections/ToolManagerSection.tsx`

Extraer el bloque del Tool Manager que está actualmente en `SettingsPanel.tsx` (el `useToolsStore`, el `groupedTools`, y el JSX del browser) a este componente independiente. No necesita wrapper de 320px — tiene espacio completo del panel derecho del modal.

Mejoras respecto a la versión en el panel lateral:
- Mostrar la descripción de cada tool al hacer hover (tooltip o texto inline)
- Añadir la sección de **Recent Usage** (historial de uso por sesión) que en el panel lateral no cabía
- Añadir contador de herramientas habilitadas vs totales en el header de cada categoría: `filesystem (6/9 enabled)`

---

### 2.2 — Quitar Tool Manager del panel lateral

**Archivo:** `ui/tray/src/components/settings/SettingsPanel.tsx`

Eliminar:
- Los imports `useToolsStore`, `useMemo`, `useRef`, `ToggleSwitch`, `SCOPE_COLORS`
- El estado `tools`, `toolsLoading`, `toolRetryRef`, `groupedTools`
- Los dos `useEffect` del tool loader
- El bloque JSX de la sección "Tool Manager"

El panel lateral queda aliviado.

---

### 2.3 — Registrar la sección en `ExpertSettingsModal`

En el switch/render del panel derecho:

```tsx
{activeSection === "tools" && <ToolManagerSection />}
```

---

## Fase 3 — Sección Inference

**Tiempo estimado:** 2 horas
**Impacto:** Alto — expone parámetros críticos de calidad de inferencia que hoy no son editables desde la UI.

---

### 3.1 — Parámetros a exponer

Todos estos se guardan vía `/api/config` PATCH y se leen de `/api/config` GET:

| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `temperature` | float slider | 0.0 – 2.0 | 0.7 | Creatividad del modelo |
| `top_p` | float slider | 0.0 – 1.0 | 0.9 | Nucleus sampling |
| `top_k` | int input | 1 – 200 | 40 | Top-K sampling |
| `repeat_penalty` | float slider | 1.0 – 1.5 | 1.1 | Penalización de repetición |
| `context_length` | int select | 1024/2048/4096/8192 | 4096 | Contexto máximo en tokens |
| `llamacpp_url` | text input | URL | http://127.0.0.1:8080 | URL del servidor llamacpp |
| `embed_url` | text input | URL | http://127.0.0.1:8082 | URL del servidor de embeddings |
| `profile` | select | chat/coding/deep | chat | Perfil de inferencia |

**Nota sobre `llamacpp_url` y `embed_url`:** cambiarlos requiere reinicio del servidor Python. La UI debe mostrar un warning: `⚠ Requiere reiniciar el servidor para aplicar`.

---

### 3.2 — Componente `InferenceSection.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/sections/InferenceSection.tsx`

Estructura visual:

```
┌─ Parámetros de generación ──────────────────────────────────┐
│  Temperature       [──●────────────] 0.7                    │
│  Top-P             [─────────●─────] 0.9                    │
│  Top-K             [40           ↕] input numérico          │
│  Repeat Penalty    [──●────────────] 1.1                    │
│  Context Length    [ 4096 ▾ ]                               │
│  Profile           [ Chat ▾ ]                               │
└─────────────────────────────────────────────────────────────┘

┌─ URLs del servidor ──────────────────────────────────────────┐
│  ⚠ Cambios requieren reiniciar el servidor                  │
│  llamacpp URL  [ http://127.0.0.1:8080               ]      │
│  Embed URL     [ http://127.0.0.1:8082               ]      │
└─────────────────────────────────────────────────────────────┘
```

Usar sliders HTML nativos con `input[type=range]` + valor numérico editable al lado. Los cambios se debounce 500ms antes de hacer PATCH a `/api/config`.

---

## Fase 4 — Sección Memory & RAG

**Tiempo estimado:** 1.5 horas
**Impacto:** Medio — permite afinar la calidad de memoria y recuperación semántica.

---

### 4.1 — Parámetros a exponer

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `short_term_max_messages` | int input | 35 | Mensajes máximos en memoria corta |
| `context_budget_pct` | float slider | 85% | % del contexto antes de consolidar |
| `consolidation_target_pct` | float slider | 60% | % objetivo tras consolidar |
| `session_resume_max_turns` | int input | 8 | Turnos máximos al resumir sesión |
| `rag_top_k` | int input | 5 | Resultados RAG a recuperar |
| `semantic_compression` | bool toggle | true | Comprimir con modelo semántico |
| `embedding_cache_ttl_days` | int input | 30 | TTL del caché de embeddings (días) |
| `embedding_cache_max_size` | int input | 200 | Entradas máximas en caché LRU |
| `embeddings_backend` | select | auto | local / llamacpp / auto |

---

### 4.2 — Componente `MemoryRagSection.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/sections/MemoryRagSection.tsx`

Estructura visual:

```
┌─ Memoria a corto plazo ──────────────────────────────────────┐
│  Max mensajes en contexto     [ 35  ]                        │
│  Consolidar al                [──────────●──] 85%            │
│  Objetivo tras consolidar     [──────●──────] 60%            │
│  Turnos para reanudar sesión  [ 8   ]                        │
└─────────────────────────────────────────────────────────────┘

┌─ RAG & Embeddings ───────────────────────────────────────────┐
│  Resultados RAG (top_k)       [ 5   ]                        │
│  Compresión semántica         [toggle ON]                    │
│  Backend de embeddings        [ Auto ▾ ]                     │
│  TTL del caché (días)         [ 30  ]                        │
│  Tamaño máximo caché          [ 200 ]                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 5 — Providers, API Keys & Paths

**Tiempo estimado:** 1.5 horas
**Impacto:** Alto — centraliza la gestión de credenciales y permisos de sistema de archivos.

---

### 5.1 — Sub-sección API Keys

| Campo | Variable env | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | ANTHROPIC_API_KEY | Requerida para backend Claude |
| `TAVILY_API_KEY` | TAVILY_API_KEY | Requerida para Tavily web search |
| `CEREBRO_API_KEY` | CEREBRO_API_KEY | Key opcional para proteger el servidor local |

Mostrar el valor como `password` input con botón de ojo para revelar. No guardar en `/api/config` — estos se leen del entorno. La UI muestra el estado actual (`● Configurada` / `○ No configurada`) y permite copiar/actualizar via un endpoint dedicado o instrucciones de cómo setearlas en el entorno.

**Diseño del indicador de estado:**

```
ANTHROPIC_API_KEY    [● Configurada]  [Actualizar]
TAVILY_API_KEY       [○ No configurada]  [Añadir]
CEREBRO_API_KEY      [○ No configurada]  [Añadir]
```

---

### 5.2 — Sub-sección Paths & Permissions

| Campo | Descripción |
|---|---|
| `authorized_read_paths` | Lista editable de rutas con permiso de lectura |
| `authorized_write_paths` | Lista editable de rutas con permiso de escritura |
| `models_dir` | Directorio donde se buscan archivos GGUF |
| `cerebro_db` | Ruta de la base de datos LanceDB |
| `cerebro_state` | Ruta del estado persistente |

**UX de la lista de paths:**
- Mostrar cada path como un chip con botón `×` para eliminar
- Botón `+ Añadir path` que abre un file-picker nativo de Tauri (`open()` con `directory: true`)
- Las rutas de DB y state son solo lectura (informativas)

```
┌─ Rutas autorizadas de lectura ──────────────────────────────┐
│  [~/Desktop ×]  [~/Documents ×]  [~/Downloads ×]           │
│  [+ Añadir ruta]                                            │
└─────────────────────────────────────────────────────────────┘

┌─ Rutas autorizadas de escritura ────────────────────────────┐
│  [~/Desktop ×]                                              │
│  [+ Añadir ruta]                                            │
└─────────────────────────────────────────────────────────────┘

┌─ Directorios del sistema ───────────────────────────────────┐
│  Modelos GGUF   bin/models/                    [Editar]    │
│  Base de datos  ~/.cerebro/db                  (solo info) │
│  Estado         ~/.cerebro/state               (solo info) │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.3 — Componente `ProvidersSection.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/sections/ProvidersSection.tsx`

Agrupa API Keys + Paths en una sola sección dividida con sub-headers. Verificar disponibilidad de `@tauri-apps/api/dialog` para el file-picker nativo antes de implementar.

---

## Fase 6 — Web Search & Fleet

**Tiempo estimado:** 1 hora
**Impacto:** Medio — ajuste fino de comportamiento de búsqueda y orquestación de modelos.

---

### 6.1 — Sección Web Search

**Archivo nuevo:** `ui/tray/src/components/expert/sections/WebSearchSection.tsx`

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `web_backend` | select | duckduckgo | duckduckgo / tavily |
| `web_max_results` | int | 5 | Resultados máximos |
| `web_max_chars` | int | 4000 | Caracteres máximos de página |
| `web_timeout` | int | 15 | Timeout en segundos |

---

### 6.2 — Sección Fleet & RAM

**Archivo nuevo:** `ui/tray/src/components/expert/sections/FleetSection.tsx`

Parámetros:

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `ram_primary_gb` | float | 1.0 | RAM mínima para provider primario |
| `ram_fallback_gb` | float | 0.3 | RAM mínima para fallback |
| `ram_min_available_gb` | float | 0.5 | RAM mínima antes de warnings críticos |
| `swap_timeout` | int | 60 | Segundos de idle antes de descargar modelo |
| `llamacpp_simple` | bool | true | `false` = ModelManager multi-server |
| `mlx_enabled` | select | auto | auto / true / false |

Mostrar también estado en tiempo real del `FleetOrchestrator` (modelo activo, swaps realizados, hardware detectado) leyendo de `/api/fleet/status`.

---

## Fase 7 — Observabilidad

**Tiempo estimado:** 45 minutos
**Impacto:** Bajo-medio — consolida las herramientas de debug en un solo lugar.

---

### 7.1 — Componente `ObservabilitySection.tsx`

**Archivo nuevo:** `ui/tray/src/components/expert/sections/ObservabilitySection.tsx`

Contenido:

1. **Time-travel Debugger:** Botón grande que abre `TimeTravelView` (actualmente también accesible desde Settings → Advanced). Mostrar conteo de runs guardados.

2. **Métricas del sistema:** Leer de `/api/status` y mostrar en tiempo real:
   - RAM usada / disponible
   - Latencia media de última sesión
   - Hits/misses del embedding cache (de `/api/cache/embedding-stats`)
   - Total de tool calls en sesión

3. **Logs de inferencia:** Toggle para activar/desactivar logging verboso (`CEREBRO_LOG_LEVEL`). Requiere reinicio — mostrar warning.

4. **Botón "Abrir carpeta de datos":** Abre `~/.cerebro/` en Finder usando Tauri shell.

---

## Fase 8 — Pulido final y keyboard shortcuts

**Tiempo estimado:** 1 hora
**Impacto:** Alto en UX — hace que el panel se sienta profesional y ágil.

---

### 8.1 — Keyboard shortcut `Cmd+Shift+,`

En `MainLayout.tsx`, añadir al keydown handler existente:

```typescript
if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === ",") {
  e.preventDefault();
  useSettingsStore.getState().openExpert();
}
```

Documentar en un tooltip del botón de entrada: `Cmd+Shift+,`

---

### 8.2 — Animación de entrada del modal

El modal aparece con:
- `opacity: 0 → 1` en 180ms
- `scale: 0.97 → 1` en 180ms `ease-out`
- Backdrop: `opacity: 0 → 1` en 150ms

Usar Tailwind `transition-all duration-[180ms] ease-out` + clase condicional en el estado de apertura.

---

### 8.3 — Persistencia de la sección activa

Guardar `activeExpertSection` en `localStorage` bajo la clave `cerebro_expert_section`. Al volver a abrir el modal, restaurar la última sección visitada en lugar de siempre abrir en "tools".

```typescript
openExpert: (section) => {
  const last = localStorage.getItem("cerebro_expert_section") as ExpertSection | null;
  const target = section ?? last ?? "tools";
  localStorage.setItem("cerebro_expert_section", target);
  set({ expertOpen: true, activeExpertSection: target });
},
setExpertSection: (s) => {
  localStorage.setItem("cerebro_expert_section", s);
  set({ activeExpertSection: s });
},
```

---

### 8.4 — Indicador de cambios sin guardar

Si alguna sección tiene cambios pendientes (debounce en vuelo), mostrar un punto naranja en el nav item de esa sección y un banner sutil en el header del modal:

```
⟳ Guardando cambios...   →   ✓ Guardado
```

---

### 8.5 — Limpiar Settings lateral

Con la migración completa, el panel lateral de 320px queda con solo:

```
  Idioma
  Carpetas indexadas
  Backend de inferencia
  Modelo
  Claude API Key            ← solo el indicador de estado, no el input completo
  Focus Mode
  Notificaciones
  Low Power Mode
  ──────────────
  [⚙ Configuración Avanzada ↗]   Cmd+Shift+,
```

El objetivo final es que cualquier usuario pueda configurar el día a día sin tocar Expert Settings nunca.

---

## Checklist final ✅

Todas las fases completadas. El panel de Expert Settings es totalmente funcional con 8 secciones navegables.

### Fase 1 — Shell ✅
- [x] Tipo `ExpertSection` añadido al store
- [x] `expertOpen`, `openExpert`, `closeExpert`, `setExpertSection` en store
- [x] Botón "Configuración Avanzada" en `SettingsPanel.tsx`
- [x] `ExpertSettingsModal.tsx` creado con layout de dos columnas
- [x] `ExpertNavItem.tsx` creado con estilos activo/inactivo
- [x] Modal montado en `MainLayout.tsx` con lazy import
- [x] Cierre con Escape y click en backdrop + animación opacity/scale
- [x] Traducciones en `en.json` y `es.json`
- [x] Keyboard shortcut `Cmd+Shift+,`
- [x] Persistencia de sección activa en localStorage

### Fase 2 — Tool Manager ✅
- [x] `ToolManagerSection.tsx` creado con tool browser + recent usage + contadores
- [x] Tool Manager eliminado de `SettingsPanel.tsx`
- [x] Imports huérfanos limpiados de `SettingsPanel.tsx`
- [x] TypeScript compila sin errores (`npx tsc --noEmit`)

### Fase 3 — Inference ✅
- [x] `InferenceSection.tsx` con sliders y inputs (temperature, top_p, top_k, repeat_penalty, context_length, profile, llamacpp_url, embed_url)
- [x] Debounce de 500ms antes de PATCH `/api/config`
- [x] Warning visible para parámetros que requieren reinicio (URLs)
- [x] Valores se leen de `/api/config` al montar

### Fase 4 — Memory & RAG ✅
- [x] `MemoryRagSection.tsx` completo (short_term_max_messages, context_budget_pct, consolidation_target_pct, session_resume_max_turns, rag_top_k, semantic_compression, embedding_cache_ttl_days, embedding_cache_max_size, embeddings_backend)
- [x] Todos los parámetros mapeados a `/api/config`

### Fase 5 — Providers & Paths ✅
- [x] `ProvidersSection.tsx` con API keys (ANTHROPIC, TAVILY, CEREBRO) + paths (watched_folders)
- [x] Inputs de API key con toggle de visibilidad (eye button)
- [x] PathList component con chips removibles + inline add input
- [x] Status indicators (● configurada / ○ no configurada)

### Fase 6 — Web & Fleet ✅
- [x] `WebSearchSection.tsx` con web_backend, web_max_results, web_max_chars, web_timeout
- [x] `FleetSection.tsx` con parámetros RAM/fleet (ram_primary_gb, ram_fallback_gb, ram_min_available_gb, swap_timeout, llamacpp_simple, mlx_enabled)
- [x] Estado en tiempo real de `/api/fleet/status` (modelo activo, swaps, RAM)
- [x] Polling cada 5s del FleetStatus

### Fase 7 — Observabilidad ✅
- [x] `ObservabilitySection.tsx` con métricas en tiempo real (RAM, latencia, tool calls, queries, memory hits, embed cache stats)
- [x] Botón de debug time-travel integrado (abre TimeTravelView)
- [x] Verbose logging toggle con warning de reinicio
- [x] Botón "Abrir ~/.cerebro en Finder" via Tauri shell
- [x] Polling cada 10s de `/api/cache/embedding-stats`

### Fase 8 — Pulido ✅
- [x] `Cmd+Shift+,` abre el modal
- [x] Animación de entrada (opacity + scale 180ms ease-out)
- [x] Persistencia de sección activa en localStorage
- [x] Indicador de guardado (spinner en header mientras `expertSaving` está activo)
- [x] Settings lateral limpio y minimalista (Tool Manager migrado)
- [x] TypeScript pasa sin errores (`npx tsc --noEmit`)

---

> **Nota de implementación:** Cada fase es independiente y mergeable por separado. El orden recomendado es estrictamente el del índice — la Fase 1 desbloquea todas las demás, y la Fase 8 depende de que las secciones de contenido existan para que el indicador de cambios tenga algo que monitorear.
