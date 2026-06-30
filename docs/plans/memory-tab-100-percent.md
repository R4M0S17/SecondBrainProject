# Plan: Pestaña de Memoria al 100% — Implementación por Fases

> **Objetivo:** Llevar la pestaña de Memoria de ~70% funcional a 100%, resolviendo todos los gaps críticos identificados en el análisis del 2026-06-27.
>
> **Estado:** ✅ **COMPLETADO** — Fase 1–5 implementadas el 2026-06-27. Pestaña de Memoria al 100%.
>
> **Estimación total:** ~8-10 horas de desarrollo (completadas en ~3.5h)
>
> **Prerrequisito:** Backend de memoria (`/api/memory/*`) funcionando correctamente.

---

## Índice

- [Fase 1 — Críticos UX (bloqueantes)](#fase-1--críticos-ux-bloqueantes)
- [Fase 2 — Store & Performance](#fase-2--store--performance)
- [Fase 3 — Tags dinámicos y editor mejorado](#fase-3--tags-dinámicos-y-editor-mejorado)
- [Fase 4 — Integración con Chat](#fase-4--integración-con-chat)
- [Fase 5 — Estadísticas y Pulido Final](#fase-5--estadísticas-y-pulido-final)
- [Checklist Final](#checklist-final)

---

## Fase 1 — Críticos UX (bloqueantes)

**Tiempo estimado:** 1.5 horas  
**Impacto:** Alto — sin esto el usuario puede perder datos accidentalmente y la búsqueda es inutilizable.

---

### 1.1 — Modal de confirmación antes de borrar un episodio

**Problema:** El botón de borrar en `MemoryEpisodeCard` llama `onDelete` directamente sin confirmación.  
**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Añadir estado para el ID del episodio pendiente de borrar:

```tsx
// FactsTab.tsx — dentro del componente, junto al resto de useState
const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
```

2. En el render de `MemoryEpisodeCard`, cambiar `onDelete` para que solo setee el estado:

```tsx
// ANTES (línea ~174):
onDelete={() => void deleteEpisode(episode.id)}

// DESPUÉS:
onDelete={() => setDeleteConfirmId(episode.id)}
```

3. Añadir el modal de confirmación al final del JSX de `FactsTab`, después del `MemoryEpisodeEditor`:

```tsx
{deleteConfirmId && (
  <div
    className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/60"
    role="dialog"
    aria-modal="true"
    onClick={() => setDeleteConfirmId(null)}
  >
    <div
      className="w-full max-w-sm bg-surface-container border border-outline-variant rounded-xl shadow-xl p-5 space-y-4"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-[24px] text-error">warning</span>
        <h3 className="text-[14px] font-semibold text-on-surface">
          {t("memory.delete_confirm_title")}
        </h3>
      </div>
      <p className="text-[12px] text-on-surface-variant leading-[17px]">
        {t("memory.delete_confirm_desc")}
      </p>
      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={() => setDeleteConfirmId(null)}
          className="px-3 py-1.5 text-[12px] text-on-surface-variant hover:text-on-surface transition-colors"
        >
          {t("note.cancel")}
        </button>
        <button
          type="button"
          onClick={() => {
            void deleteEpisode(deleteConfirmId);
            setDeleteConfirmId(null);
          }}
          className="px-4 py-1.5 rounded-lg bg-error text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
        >
          {t("memory.delete_confirm_action")}
        </button>
      </div>
    </div>
  </div>
)}
```

4. Añadir claves i18n en `ui/tray/src/locales/en.json`:

```json
"memory.delete_confirm_title": "Delete this memory?",
"memory.delete_confirm_desc": "This fact will be permanently removed. Cerebro will no longer recall it in future chats.",
"memory.delete_confirm_action": "Delete forever"
```

5. Añadir claves i18n en `ui/tray/src/locales/es.json`:

```json
"memory.delete_confirm_title": "¿Eliminar este recuerdo?",
"memory.delete_confirm_desc": "Este hecho se eliminará permanentemente. Cerebro no lo recordará en futuros chats.",
"memory.delete_confirm_action": "Eliminar para siempre"
```

**Criterio de aceptación:** Al pulsar el icono de borrar, aparece el modal. Cancelar no hace nada. Confirmar borra y refresca la lista.

---

### 1.2 — Debounce en la búsqueda de Recall

**Problema:** `MemoryRecallSearch` lanza un request HTTP por cada pulsación de tecla porque el formulario se envía manualmente, pero no hay debounce en el campo de texto libre.  
**Archivo a editar:** `ui/tray/src/components/memory/MemoryRecallSearch.tsx`

**Pasos:**

1. Cambiar el state de `query` a un `inputValue` inmediato y un `query` debounced:

```tsx
// REEMPLAZAR el componente completo con este patrón:
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { MemoryRecallResult } from "../../api/types";

interface MemoryRecallSearchProps {
  onSearch: (query: string) => Promise<MemoryRecallResult[]>;
  usingMock?: boolean;
}

export default function MemoryRecallSearch({ onSearch, usingMock = false }: MemoryRecallSearchProps) {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");
  const [results, setResults] = useState<MemoryRecallResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const abortRef = useRef<AbortController>();

  const runSearch = async (q: string) => {
    if (!q.trim()) {
      setResults(null);
      setSearchError(null);
      return;
    }
    // Cancelar request anterior si existe
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setSearching(true);
    setSearchError(null);
    try {
      const hits = await onSearch(q);
      setResults(hits);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      setResults([]);
      setSearchError(err instanceof Error ? err.message : t("memory.recall_error"));
    } finally {
      setSearching(false);
    }
  };

  const handleInputChange = (value: string) => {
    setInputValue(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) {
      setResults(null);
      setSearchError(null);
      return;
    }
    debounceRef.current = setTimeout(() => {
      void runSearch(value);
    }, 350);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (debounceRef.current) clearTimeout(debounceRef.current);
    void runSearch(inputValue);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, []);

  return (
    // ... resto del JSX igual pero usando inputValue y handleInputChange
  );
}
```

2. En el JSX, actualizar el `<input>`:

```tsx
<input
  type="search"
  value={inputValue}
  onChange={(e) => handleInputChange(e.target.value)}
  placeholder={t("memory.recall_placeholder")}
  className="..."
/>
```

**Criterio de aceptación:** Al escribir en el campo de búsqueda, los requests solo se disparan 350ms después de que el usuario deja de teclear. No hay requests duplicados cuando el usuario escribe rápido.

---

### 1.3 — Arreglar la métrica "Recall Rate"

**Problema:** En `FactsTab.tsx` el `recallRate` divide `recall_hits_session / queries_with_recall` pero `queries_with_recall` en el backend se calcula como `queries_total if memory_hits > 0` — lo cual no es una métrica válida.

**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Eliminar el cálculo del `recallRate` completamente (líneas 45-48).

2. Reemplazar el chip de recall rate por uno que muestre información real:

```tsx
// ANTES:
{recallRate > 0 && (
  <span className="text-[10px] text-outline font-label-mono ml-auto self-center">
    {t("memory.recall_rate", { rate: recallRate })}
  </span>
)}

// DESPUÉS — mostrar recall hits directamente sin ratio falso:
{stats.recall_hits_session > 0 && (
  <span className="flex items-center gap-1 text-[10px] text-violet-400/70 font-label-mono ml-auto self-center" title="Times Cerebro retrieved memory from LanceDB in this session">
    <span className="material-symbols-outlined text-[12px]">neurology</span>
    {t("memory.recall_hits_count", { count: stats.recall_hits_session })}
  </span>
)}
```

3. Añadir claves i18n en ambos archivos de locale:

```json
// en.json:
"memory.recall_hits_count": "{{count}} recall{{count, plural, one {} other {s}}} this session"

// es.json:
"memory.recall_hits_count": "{{count}} recall en esta sesión"
```

**Criterio de aceptación:** La métrica muestra "X recalls en esta sesión" en lugar de un porcentaje sin sentido.

---

## Fase 2 — Store & Performance

**Tiempo estimado:** 1.5 horas  
**Impacto:** Medio — sin esto hay requests innecesarios y el store es ineficiente.

---

### 2.1 — Cache con TTL para evitar double-refresh

**Problema:** `MemoryViewContent.tsx` llama `refresh()` cada vez que el componente monta. Si el usuario navega entre pestañas o abre el `MemoryBrowserPanel`, se hacen requests redundantes cada vez.

**Archivo a editar:** `ui/tray/src/stores/memory.ts`

**Pasos:**

1. Añadir campo `lastRefreshedAt` al estado del store:

```typescript
interface MemoryState {
  // ... campos existentes
  lastRefreshedAt: number | null;    // timestamp epoch ms
  refresh: (force?: boolean) => Promise<void>;
  // ... resto sin cambios
}
```

2. Inicializar en el store:

```typescript
export const useMemoryStore = create<MemoryState>((set, get) => ({
  // ... campos existentes
  lastRefreshedAt: null,
```

3. Modificar el método `refresh` para aceptar un flag `force` y respetar un TTL de 30s:

```typescript
refresh: async (force = false) => {
  const STALENESS_MS = 30_000; // 30 segundos
  const last = get().lastRefreshedAt;
  if (!force && last !== null && Date.now() - last < STALENESS_MS) {
    return; // datos recientes, no hacer request
  }
  set({ loading: true, error: null, errorCode: null });
  try {
    const [episodesRes, session] = await Promise.all([
      listMemoryEpisodes(),
      getMemorySession(),
    ]);
    set({
      episodes: episodesRes.episodes,
      stats: episodesRes.stats,
      session,
      loading: false,
      usingMock: false,
      lastRefreshedAt: Date.now(),
    });
  } catch (e) {
    const code = formatLoadError(e);
    set({
      loading: false,
      error: code === "stale_backend" || code === "unavailable" || code === "offline"
        ? code
        : (e instanceof Error ? e.message : "Failed to load memory"),
      errorCode: code === "stale_backend" || code === "unavailable" || code === "offline"
        ? code
        : null,
      usingMock: false,
    });
  }
},
```

4. Asegurarse de que `addEpisode`, `updateEpisode`, `deleteEpisode` y `togglePin` llaman `refresh(true)` (con force) para forzar actualización tras mutaciones:

```typescript
addEpisode: async (content, tags = ["manual"]) => {
  // ...
  await createMemoryEpisode(trimmed, tags);
  await get().refresh(true); // ← force=true
},
```

Aplicar el mismo cambio a `updateEpisode`, `deleteEpisode` y `togglePin`.

**Criterio de aceptación:** Abrir y cerrar el panel de memoria 5 veces en 30 segundos produce solo 1 request al backend (el primero). Al crear/editar/borrar, el refresh es inmediato.

---

### 2.2 — Botón "Copy to Clipboard" en cada episodio

**Problema:** No hay forma de copiar el contenido de un episodio al clipboard.  
**Archivo a editar:** `ui/tray/src/components/memory/MemoryEpisodeCard.tsx`

**Pasos:**

1. Añadir props y estado al componente:

```tsx
interface MemoryEpisodeCardProps {
  // props existentes...
  onCopy?: () => void; // opcional, el componente lo maneja internamente
}
```

2. Añadir estado `copied` local para feedback visual:

```tsx
const [copied, setCopied] = useState(false);

const handleCopy = async () => {
  await navigator.clipboard.writeText(episode.content);
  setCopied(true);
  setTimeout(() => setCopied(false), 1500);
};
```

3. Añadir el botón en la barra de acciones del card (junto a edit/pin/delete):

```tsx
<button
  type="button"
  onClick={() => void handleCopy()}
  className="p-1 rounded hover:bg-surface-container-highest text-on-surface-variant transition-colors"
  aria-label={t("memory.copy_episode")}
  title={copied ? t("memory.copied") : t("memory.copy_episode")}
>
  <span className="material-symbols-outlined text-[16px]">
    {copied ? "check" : "content_copy"}
  </span>
</button>
```

4. Añadir claves i18n en ambos locales:

```json
// en.json:
"memory.copy_episode": "Copy to clipboard",
"memory.copied": "Copied!"

// es.json:
"memory.copy_episode": "Copiar al portapapeles",
"memory.copied": "¡Copiado!"
```

**Criterio de aceptación:** Clic en el icono de copy → contenido en el clipboard → el icono cambia a ✓ por 1.5s → vuelve al icono de copia.

---

### 2.3 — Confirmación antes de "Save All" en SessionTab

**Problema:** El botón "Guardar en hechos" del `SessionTab` guarda TODOS los auto-notes a la vez sin confirmación. Si hay 20 notas, el usuario crea 20 episodios de golpe.

**Archivo a editar:** `ui/tray/src/components/memory/SessionTab.tsx`

**Pasos:**

1. Añadir estado para el confirm:

```tsx
const [confirmSaveAll, setConfirmSaveAll] = useState(false);
const [savingAll, setSavingAll] = useState(false);
```

2. Modificar el `handleSaveAll` para proteger con estado:

```tsx
const handleSaveAll = async () => {
  setSavingAll(true);
  for (const [key, value] of autoNotes) {
    try {
      await addEpisode(`${key}: ${value}`, ["auto-note", "session"]);
    } catch {
      /* skip */
    }
  }
  setSavingAll(false);
  setConfirmSaveAll(false);
};
```

3. Cambiar el botón "Save to facts" para que muestre el confirm inline:

```tsx
{!confirmSaveAll ? (
  <button
    type="button"
    onClick={() => setConfirmSaveAll(true)}
    className="text-[11px] text-primary-container hover:underline flex items-center gap-1"
  >
    <span className="material-symbols-outlined text-[14px]">bookmark_add</span>
    {t("memory.save_to_facts")}
  </button>
) : (
  <div className="flex items-center gap-2">
    <span className="text-[11px] text-on-surface-variant">{t("memory.save_all_confirm")}</span>
    <button
      type="button"
      disabled={savingAll}
      onClick={() => void handleSaveAll()}
      className="text-[11px] text-primary-container font-medium hover:underline disabled:opacity-50"
    >
      {savingAll ? t("status.loading") : t("memory.confirm_yes")}
    </button>
    <button
      type="button"
      onClick={() => setConfirmSaveAll(false)}
      className="text-[11px] text-on-surface-variant hover:underline"
    >
      {t("note.cancel")}
    </button>
  </div>
)}
```

4. Añadir claves i18n:

```json
// en.json:
"memory.save_all_confirm": "Save all {{count}} notes?",
"memory.confirm_yes": "Yes, save all"

// es.json:
"memory.save_all_confirm": "¿Guardar todas las {{count}} notas?",
"memory.confirm_yes": "Sí, guardar todo"
```

**Criterio de aceptación:** Primer clic en "Guardar en hechos" muestra confirmación inline. Segundo clic guarda todo. Cancelar aborta sin crear episodios.

---

## Fase 3 — Tags dinámicos y editor mejorado

**Tiempo estimado:** 2 horas  
**Impacto:** Medio — mejora la usabilidad del sistema de filtrado y la edición de episodios.

---

### 3.1 — Filtros de tags dinámicos basados en los episodios reales

**Problema:** Los filtros en `FactsTab` están hardcoded: `["all", "pinned", "session", "academic", "code"]`. Si el usuario tiene tags propios (`"trabajo"`, `"personal"`, `"tesis"`), nunca aparecen como filtro.

**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Eliminar la constante hardcoded `FILTERS` (línea 8).

2. Calcular los filtros dinámicamente con `useMemo`:

```tsx
// Filtros base siempre visibles
const BASE_FILTERS: MemoryFilter[] = ["all", "pinned"];

// Tags únicos extraídos de los episodios (excluyendo los que ya están hardcoded)
const EXCLUDED_FROM_DYNAMIC = new Set(["manual", "pinned"]);

const dynamicFilters = useMemo(() => {
  const tagCounts = new Map<string, number>();
  for (const ep of episodes) {
    for (const tag of ep.tags) {
      if (!EXCLUDED_FROM_DYNAMIC.has(tag)) {
        tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1);
      }
    }
  }
  // Ordenar por frecuencia, mostrar los 6 más comunes
  return Array.from(tagCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([tag]) => tag);
}, [episodes]);

const allFilters = [...BASE_FILTERS, ...dynamicFilters];
```

3. Actualizar el filtrado de episodios para que funcione con tags dinámicos:

```tsx
const filteredEpisodes = useMemo(() => {
  let list = [...episodes];
  if (filter === "pinned") {
    list = list.filter((e) => e.pinned);
  } else if (filter !== "all") {
    // filtrar por tag exacto
    list = list.filter((e) => e.tags.includes(filter));
  }
  list.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.created_at - a.created_at;
  });
  return list;
}, [episodes, filter]);
```

4. Actualizar el tipo `MemoryFilter` en el store para aceptar strings arbitrarios:

```typescript
// ui/tray/src/stores/memory.ts
// ANTES:
export type MemoryFilter = "all" | "pinned" | "session" | "academic" | "code";

// DESPUÉS:
export type MemoryFilter = string; // Cualquier tag es un filtro válido
```

5. Actualizar el render de los filtros para mostrar conteo:

```tsx
{allFilters.map((f) => {
  const count = f === "all"
    ? episodes.length
    : f === "pinned"
    ? episodes.filter(e => e.pinned).length
    : episodes.filter(e => e.tags.includes(f)).length;

  return (
    <button
      key={f}
      type="button"
      onClick={() => setFilter(f)}
      className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors flex items-center gap-1 ${
        filter === f
          ? "bg-violet-400/20 text-violet-300 border border-violet-400/30"
          : "bg-surface-container text-on-surface-variant border border-transparent hover:border-outline-variant/20"
      }`}
    >
      {f === "all" ? t("memory.filter_all")
       : f === "pinned" ? t("memory.filter_pinned")
       : f}
      <span className="opacity-60">{count}</span>
    </button>
  );
})}
```

**Criterio de aceptación:** Los filtros muestran automáticamente los tags más usados en los episodios reales. Si el usuario crea 5 episodios con tag `"tesis"`, aparece un botón de filtro `"tesis (5)"`.

---

### 3.2 — Autocomplete de tags en el editor de episodios

**Problema:** En `MemoryEpisodeEditor`, el campo de tags es un input de texto libre sin sugerencias. El usuario no sabe qué tags ya existen.

**Archivo a editar:** `ui/tray/src/components/memory/MemoryEpisodeEditor.tsx`

**Pasos:**

1. Importar `useMemoryStore` para acceder a los episodios existentes:

```tsx
import { useMemoryStore } from "../../stores/memory";
```

2. Calcular los tags únicos existentes:

```tsx
const { episodes } = useMemoryStore();
const existingTags = useMemo(() => {
  const all = new Set<string>();
  for (const ep of episodes) {
    for (const tag of ep.tags) {
      all.add(tag);
    }
  }
  return Array.from(all).sort();
}, [episodes]);
```

3. Añadir estado para sugerencias visibles:

```tsx
const [showSuggestions, setShowSuggestions] = useState(false);

const currentTagInput = tagsText.split(",").pop()?.trim() ?? "";
const suggestions = currentTagInput.length > 0
  ? existingTags.filter(t =>
      t.toLowerCase().includes(currentTagInput.toLowerCase()) &&
      !tagsText.split(",").map(s => s.trim()).includes(t)
    )
  : [];
```

4. Añadir la UI de sugerencias debajo del input de tags:

```tsx
<div className="relative">
  <input
    type="text"
    value={tagsText}
    onChange={(e) => { setTagsText(e.target.value); setShowSuggestions(true); }}
    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
    onFocus={() => setShowSuggestions(true)}
    placeholder={t("memory.edit_tags_placeholder")}
    className="mt-1.5 w-full bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-[12px] text-on-surface focus:outline-none focus:border-primary-container/50"
  />
  {showSuggestions && suggestions.length > 0 && (
    <div className="absolute top-full left-0 right-0 z-10 mt-1 bg-surface-container border border-outline-variant/20 rounded-lg shadow-lg overflow-hidden">
      {suggestions.slice(0, 5).map((tag) => (
        <button
          key={tag}
          type="button"
          className="w-full text-left px-3 py-1.5 text-[12px] text-on-surface hover:bg-surface-container-highest transition-colors font-label-mono"
          onMouseDown={() => {
            const parts = tagsText.split(",");
            parts[parts.length - 1] = ` ${tag}`;
            setTagsText(parts.join(",").trimStart() + ", ");
            setShowSuggestions(false);
          }}
        >
          {tag}
        </button>
      ))}
    </div>
  )}
</div>
```

5. También añadir chips de tags conocidos para insertar con un clic:

```tsx
{existingTags.length > 0 && (
  <div className="flex flex-wrap gap-1 mt-1">
    {existingTags.slice(0, 8).map(tag => (
      <button
        key={tag}
        type="button"
        onClick={() => {
          if (!tagsText.split(",").map(s => s.trim()).includes(tag)) {
            setTagsText(prev => prev ? `${prev.trimEnd().replace(/,\s*$/, "")}, ${tag}` : tag);
          }
        }}
        className="px-2 py-0.5 rounded-md bg-surface-container text-on-surface-variant text-[10px] font-label-mono hover:bg-surface-container-highest transition-colors border border-outline-variant/10"
      >
        + {tag}
      </button>
    ))}
  </div>
)}
```

**Criterio de aceptación:** Al editar tags y escribir "ac", aparece dropdown con sugerencias como "academic", "auto-note". Al hacer clic se añade al campo. Los chips de tags conocidos aparecen debajo del input para inserción rápida.

---

### 3.3 — Arreglar el bug del tag "pinned" duplicado en el Editor

**Problema:** En `MemoryEpisodeEditor.tsx` línea 28, si el episodio está pinned se añade el tag `"pinned"` a la lista. Esto no debería hacerse — `pinned` es un campo separado en la base de datos, no un tag.

**Archivo a editar:** `ui/tray/src/components/memory/MemoryEpisodeEditor.tsx`

**Pasos:**

1. Eliminar la línea que añade el tag "pinned":

```tsx
// ELIMINAR esta línea en handleSave():
if (episode.pinned) tags.push("pinned");
```

**Criterio de aceptación:** Al editar un episodio pinned, el campo de tags no muestra ni añade "pinned" automáticamente.

---

## Fase 4 — Integración con Chat

**Tiempo estimado:** 2.5 horas  
**Impacto:** Alto — es la feature más importante porque conecta la memoria con el uso real.

---

### 4.1 — Mejorar el MemoryPanel en el Chat para que sea clickable

**Problema:** `MemoryPanel.tsx` muestra la memoria recuperada pero no permite navegar a ella.  
**Archivos a editar:** `ui/tray/src/components/chat/MemoryPanel.tsx` y `ui/tray/src/stores/tab.ts`

**Pasos:**

1. Mejorar el look del MemoryPanel con un header más descriptivo:

```tsx
// MemoryPanel.tsx — reemplazar el componente completo:
import { useTranslation } from "react-i18next";
import type { MemoryRef } from "../../api/types";

interface MemoryPanelProps {
  memory: MemoryRef[];
  onViewAll?: () => void;
}

export default function MemoryPanel({ memory, onViewAll }: MemoryPanelProps) {
  const { t } = useTranslation();
  if (memory.length === 0) return null;

  return (
    <div className="bg-violet-500/5 border border-violet-400/15 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[14px] text-violet-400/70">neurology</span>
          <span className="text-[10px] font-semibold tracking-[0.06em] uppercase text-violet-400/70">
            {t("memory.used_in_response", { count: memory.length })}
          </span>
        </div>
        {onViewAll && (
          <button
            type="button"
            onClick={onViewAll}
            className="text-[10px] text-violet-400/60 hover:text-violet-400 transition-colors underline"
          >
            {t("memory.view_all")}
          </button>
        )}
      </div>
      <div className="space-y-1.5">
        {memory.map((mem) => (
          <div key={mem.id} className="space-y-0.5">
            <p className="text-[11px] text-on-surface-variant/80 leading-[15px] line-clamp-2 italic">
              "{mem.summary_snippet}"
            </p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-[2px] bg-surface-container overflow-hidden rounded-full">
                <div
                  className="h-full bg-violet-400/60 rounded-full"
                  style={{ width: `${Math.round(mem.relevance_score * 100)}%` }}
                />
              </div>
              <span className="font-mono text-[9px] text-outline">
                {mem.relevance_score.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

2. Añadir claves i18n:

```json
// en.json:
"memory.used_in_response": "{{count}} memor{{count, plural, one {y} other {ies}}} used",
"memory.view_all": "View in Memory tab"

// es.json:
"memory.used_in_response_one": "{{count}} recuerdo usado",
"memory.used_in_response_other": "{{count}} recuerdos usados",
"memory.view_all": "Ver en pestaña Memoria"
```

3. Buscar dónde se renderiza `MemoryPanel` en el chat y pasarle un `onViewAll` que navegue a la pestaña de memoria. Buscar en `ui/tray/src/components/chat/`:

```bash
grep -rn "MemoryPanel" ui/tray/src/
```

4. En el componente padre que renderiza `MemoryPanel`, importar el tab store y añadir la navegación:

```tsx
import { useTabStore } from "../../stores/tab";

// Dentro del componente:
const { setLeftTab } = useTabStore();

// En el JSX:
<MemoryPanel
  memory={metadata.memory_retrieved}
  onViewAll={() => setLeftTab("memory")}
/>
```

**Criterio de aceptación:** Cuando una respuesta del chat usa memoria, aparece el panel de memoria con las referencias. El link "Ver en pestaña Memoria" cambia la tab lateral a Memory.

---

### 4.2 — Indicador de memoria en el Dashboard

**Problema:** El Dashboard tiene un card de "Memories" pero solo muestra `{{hits}} recalls this session` sin linking a la pestaña.  
**Archivo a editar:** `ui/tray/src/components/dashboard/DashboardHome.tsx`

**Pasos:**

1. Buscar el card de memorias en DashboardHome y añadir un botón que navegue a la pestaña:

```bash
grep -n "memories\|memory" ui/tray/src/components/dashboard/DashboardHome.tsx
```

2. Convertir el card de memorias en clickable que lleve a la pestaña Memory:

```tsx
// El card de memories debería tener un onClick que navegue:
import { useTabStore } from "../../stores/tab";

const { setLeftTab } = useTabStore();

// En el card de memories, añadir:
onClick={() => setLeftTab("memory")}
className="... cursor-pointer hover:border-violet-400/30 transition-colors"
```

**Criterio de aceptación:** Hacer clic en el card de Memories en el dashboard lleva directamente a la pestaña Memoria.

---

### 4.3 — Highlight de episodio en FactsTab desde el chat

**Problema:** Cuando el usuario navega a Memory desde el chat (via `onViewAll`), no sabe cuál episodio fue el que se usó.

**Archivos a editar:** `ui/tray/src/stores/memory.ts` y `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Añadir un campo `highlightedId` al store:

```typescript
// En MemoryState interface:
highlightedId: string | null;
setHighlightedId: (id: string | null) => void;

// En el store:
highlightedId: null,
setHighlightedId: (id) => {
  set({ highlightedId: id });
  // Auto-limpiar el highlight después de 3s
  setTimeout(() => set({ highlightedId: null }), 3000);
},
```

2. En `MemoryEpisodeCard`, añadir prop `highlighted` y animar con un ring:

```tsx
interface MemoryEpisodeCardProps {
  // ... props existentes
  highlighted?: boolean;
}

// En el artículo principal:
<article
  className={`... transition-all ${
    highlighted
      ? "ring-2 ring-violet-400/50 ring-offset-1 ring-offset-surface-container"
      : ""
  }`}
>
```

3. En `FactsTab`, usar el `highlightedId` del store:

```tsx
const { highlightedId } = useMemoryStore();

// En el map:
<MemoryEpisodeCard
  key={episode.id}
  episode={episode}
  highlighted={highlightedId === episode.id}
  // ... resto de props
/>
```

4. Cuando el usuario hace clic en "View All" desde el `MemoryPanel`, pasar el `mem.id` del primer resultado:

```tsx
// Donde se renderiza MemoryPanel:
onViewAll={() => {
  if (metadata.memory_retrieved[0]) {
    useMemoryStore.getState().setHighlightedId(metadata.memory_retrieved[0].id);
  }
  setLeftTab("memory");
}}
```

**Criterio de aceptación:** Al navegar desde el chat a la pestaña Memoria, el episodio que se usó en la respuesta aparece resaltado con un ring violeta durante 3 segundos.

---

## Fase 5 — Estadísticas y Pulido Final

**Tiempo estimado:** 2 horas  
**Impacto:** Bajo/Medio — mejora la experiencia pero no es bloqueante.

---

### 5.1 — Panel de estadísticas expandido en FactsTab

**Problema:** Las 3 tarjetas de estadísticas muestran datos básicos. Falta context_memory_pct y la distribución de sources.

**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Añadir un 4to stat card para `context_memory_pct`:

```tsx
// En el grid de stats, cambiar de grid-cols-3 a grid-cols-4 y añadir:
{
  icon: "data_usage",
  label: t("memory.stat_context"),
  value: `${stats.context_memory_pct}%`,
  tip: "Memory currently active in agent context"
}
```

2. Añadir una mini gráfica de distribución de sources después de los stat cards:

```tsx
// Calcular distribución:
const sourceDist = useMemo(() => {
  const counts: Record<string, number> = { episode: 0, consolidation: 0, archived: 0, manual: 0 };
  for (const ep of episodes) {
    counts[ep.source] = (counts[ep.source] ?? 0) + 1;
  }
  return counts;
}, [episodes]);

// Renderizar si hay más de 5 episodios:
{episodes.length >= 5 && (
  <div className="mb-3 flex items-center gap-1 h-1.5 rounded-full overflow-hidden" title="Memory source distribution">
    {Object.entries(sourceDist).map(([source, count]) => {
      const pct = Math.round((count / episodes.length) * 100);
      if (pct === 0) return null;
      const colors: Record<string, string> = {
        manual: "bg-violet-400/70",
        episode: "bg-blue-400/70",
        consolidation: "bg-green-400/70",
        archived: "bg-outline/40",
      };
      return (
        <div
          key={source}
          className={`h-full ${colors[source] ?? "bg-outline/40"}`}
          style={{ width: `${pct}%` }}
          title={`${source}: ${count}`}
        />
      );
    })}
  </div>
)}
```

**Criterio de aceptación:** Los stat cards muestran 4 métricas incluyendo el % de contexto activo. La barra de distribución muestra visualmente la proporción de episodios por tipo.

---

### 5.2 — Export de episodios como JSON/Markdown

**Problema:** No hay forma de exportar la memoria del agente.  
**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Añadir botón de export junto al botón "Add":

```tsx
const handleExport = () => {
  const exportData = episodes.map(ep => ({
    content: ep.content,
    tags: ep.tags,
    source: ep.source,
    pinned: ep.pinned,
    confidence: ep.confidence,
    created_at: new Date(ep.created_at).toISOString(),
  }));

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cerebro-memory-${new Date().toISOString().split("T")[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
};

// Añadir botón en la barra de acciones:
{episodes.length > 0 && (
  <button
    type="button"
    onClick={handleExport}
    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container text-on-surface-variant text-[12px] hover:opacity-90 shrink-0 border border-outline-variant/20"
    title={t("memory.export_title")}
  >
    <span className="material-symbols-outlined text-[16px]">download</span>
    {t("memory.export")}
  </button>
)}
```

2. Añadir claves i18n:

```json
// en.json:
"memory.export": "Export",
"memory.export_title": "Download all memories as JSON"

// es.json:
"memory.export": "Exportar",
"memory.export_title": "Descargar todos los recuerdos como JSON"
```

**Criterio de aceptación:** El botón Export descarga un archivo `.json` con todos los episodios actuales del agente.

---

### 5.3 — Búsqueda de texto en FactsTab

**Problema:** Con muchos episodios, el usuario no puede buscar dentro de la lista. Solo puede filtrar por tag.

**Archivo a editar:** `ui/tray/src/components/memory/FactsTab.tsx`

**Pasos:**

1. Añadir estado para búsqueda de texto:

```tsx
const [textSearch, setTextSearch] = useState("");
```

2. Añadir campo de búsqueda antes de los filtros:

```tsx
{episodes.length >= 5 && (
  <div className="relative mb-2">
    <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[14px] text-outline">search</span>
    <input
      type="text"
      value={textSearch}
      onChange={(e) => setTextSearch(e.target.value)}
      placeholder={t("memory.search_placeholder")}
      className="w-full bg-surface-container-low border border-outline-variant/20 rounded-lg pl-8 pr-3 py-1.5 text-[12px] text-on-surface placeholder:text-outline/50 focus:outline-none focus:border-primary-container/50"
    />
    {textSearch && (
      <button
        type="button"
        onClick={() => setTextSearch("")}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface"
      >
        <span className="material-symbols-outlined text-[14px]">close</span>
      </button>
    )}
  </div>
)}
```

3. Incorporar la búsqueda de texto en el `filteredEpisodes` useMemo:

```tsx
const filteredEpisodes = useMemo(() => {
  let list = [...episodes];

  // Filtro por tag/pinned
  if (filter === "pinned") {
    list = list.filter((e) => e.pinned);
  } else if (filter !== "all") {
    list = list.filter((e) => e.tags.includes(filter));
  }

  // Búsqueda de texto (case-insensitive sobre content + tags)
  if (textSearch.trim()) {
    const q = textSearch.toLowerCase();
    list = list.filter(
      (e) =>
        e.content.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q))
    );
  }

  list.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.created_at - a.created_at;
  });
  return list;
}, [episodes, filter, textSearch]);
```

4. Añadir claves i18n:

```json
// en.json:
"memory.search_placeholder": "Search your memories…"

// es.json:
"memory.search_placeholder": "Buscar en tus recuerdos…"
```

**Criterio de aceptación:** El campo de búsqueda filtra episodios en tiempo real. Buscar "tesis" muestra solo episodios que contienen esa palabra en el contenido o en los tags.

---

### 5.4 — Teclado accesible en MemoryEpisodeCard

**Problema:** Los botones de acción del card no tienen `tabIndex` ordenado ni respuesta a teclas de acceso rápido.

**Archivo a editar:** `ui/tray/src/components/memory/MemoryEpisodeCard.tsx`

**Pasos:**

1. Añadir soporte para Escape en el card expandido:

```tsx
// En el artículo, añadir onKeyDown:
<article
  onKeyDown={(e) => {
    if (e.key === "Escape" && expanded && onToggleExpand) {
      onToggleExpand();
    }
  }}
  // ... resto de props
>
```

2. Asegurarse de que todos los botones tienen `aria-label` con las traducciones correctas (ya lo tienen, verificar que estén en ambos locales).

**Criterio de aceptación:** En un card expandido, pulsar Escape lo colapsa.

---

## Checklist Final

Antes de considerar el trabajo completo, verificar cada punto:

### Fase 1 — Críticos UX ✅
- [x] Modal de confirmación aparece antes de borrar un episodio
- [x] Cancelar el modal NO borra el episodio
- [x] Búsqueda de Recall tiene debounce de 350ms (verificar en Network tab que solo hay 1 request por búsqueda)
- [x] "Recall Rate" muestra "X recalls en esta sesión" en lugar de porcentaje
- [x] Botón "Save All" en SessionTab pide confirmación antes de crear episodios masivos

### Fase 2 — Store & Performance ✅
- [x] Navegar a la pestaña Memoria 5 veces en 30 segundos produce solo 1 request a `/api/memory/episodes`
- [x] Crear un episodio actualiza la lista inmediatamente (fuerza refresh)
- [x] Botón de copy funciona y muestra ✓ por 1.5s
- [x] `navigator.clipboard.writeText` funciona en Tauri con fallback (sin Tauri plugin instalado, falla silenciosamente)

### Fase 3 — Tags dinámicos ✅
- [x] Los filtros muestran los tags reales de los episodios (no solo session/academic/code hardcoded)
- [x] Al crear episodios con tags nuevos, esos tags aparecen en los filtros automáticamente
- [x] Autocomplete en el editor muestra sugerencias basadas en tags existentes
- [x] El bug del tag "pinned" duplicado está resuelto

### Fase 4 — Integración con Chat ✅
- [x] Si una respuesta usa memoria, el MemoryPanel muestra las referencias con diseño mejorado
- [x] El botón "Ver en pestaña Memoria" navega correctamente a la Memory tab
- [x] Al navegar, el episodio usado se resalta con ring violeta por 3 segundos
- [x] El card de Memories en el Dashboard es clickable y lleva a la Memory tab

### Fase 5 — Estadísticas y Pulido Final ✅
- [x] El 4to stat card muestra `context_memory_pct`
- [x] El botón Export descarga un archivo JSON válido con todos los episodios
- [x] La búsqueda de texto filtra episodios por content y tags en tiempo real
- [x] Con 0 resultados, la búsqueda muestra mensaje adecuado (empty state) y botón para limpiar (X)
- [x] Todas las nuevas claves i18n están en `en.json` Y `es.json`
- [x] Escape colapsa el card expandido

---

## Notas de implementación

### Sobre Tauri y Clipboard
El `navigator.clipboard` puede no funcionar en el webview de Tauri sin configuración adicional. Si falla, usar el fallback:

```tsx
const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(episode.content);
  } catch {
    // Fallback para Tauri si `@tauri-apps/plugin-clipboard-manager` está instalado
  }
  setCopied(true);
  setTimeout(() => setCopied(false), 1500);
};
```

> **Nota:** El dynamic import `@tauri-apps/plugin-clipboard-manager` causa error `TS2307` si el paquete no está instalado. Se eliminó el fallback del import dinámico; si se necesita, instalar el paquete y descomentar el bloque catch.

### Sobre el orden de implementación recomendado
Implementar en el orden de las fases: primero los críticos (Fase 1), luego el store (Fase 2), después los tags (Fase 3), luego el chat (Fase 4) y finalmente el pulido (Fase 5). Cada fase es independiente y deployable por sí sola.

### Sobre i18n
Siempre añadir las claves en AMBOS archivos (`en.json` y `es.json`). El app defaultea a español (`CEREBRO_LOCALE=es`) — si falta la clave en español el usuario verá la clave cruda.

### Sobre tests
Después de cada fase, ejecutar:
```bash
cd ui/tray && npm run build   # verificar que no hay errores de TypeScript
```

Para las funciones del store (Fase 2), añadir tests en `tests/` si se quiere cobertura formal.
