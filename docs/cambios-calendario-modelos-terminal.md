# Cambios realizados — Sesión 10 Jun 2026

## 1. Calendario: Timeout de Apple Calendar

### Problema
AppleScript con `whose start date ≥ now` se colgaba al iterar sobre múltiples calendarios en macOS, causando timeout de 30s y mensaje:
```
Apple Calendar tardó demasiado en responder.
```

### Solución
- **`integrations/calendar_reader.py`** — Reemplazé AppleScript por JXA (JavaScript for Automation) con filtro `whose()` de fechas. JXA maneja múltiples calendarios de forma fiable y es mucho más rápido (~3s vs timeout 30s).
- Cambié de `osascript -e` (AppleScript) a `osascript -l JavaScript -e` (JXA).
- El JXA usa `cal.events.whose({_and: [{startDate: {_greaterThanEquals: now}}, {startDate: {_lessThanEquals: cutoff}}]})` — esto deja que Calendar.app filtre internamente sin cargar todos los eventos.

### Archivos modificados
- `integrations/calendar_reader.py` — Nueva función `_JXA_FETCH_UPCOMING`, `_fetch_upcoming_via_applescript` usa JXA

---

## 2. Fast path: Queries no matcheaban

### Problema
Varias formas de preguntar por reuniones no activaban el fast path y caían al LLM, que respondía sin datos reales:
- `"dime si tengo reuniones hoy?"`
- `"tengo reuniones hoy?"` (sin "para")
- `"tell me if i have meetings today?"`
- `"dime si hay eventos mañana?"`

### Solución
- **`core/agents/calendar_query_parse.py`** — Agregué patrón `(?:tengo|hay)\s+(?:reuniones?|eventos?|citas?)\s+` a `_ON_RE`
- **`core/agents/calendar_fast_path.py`** — Agregué patrón `(dime|tell\s+me)\s+(si|if)\s+(tengo|i\s+have|hay)\s+(reuniones?|eventos?|citas?|meetings?|algo)\b` a `_UPCOMING_RE`
- En `_extract_loose_on_filter` — Fallback ahora solo intenta parsear la última palabra como día si coincide con `_WEEKDAY_FRAGMENT|_REL_DAY_FRAGMENT` (evita falsos positivos como "horas")

### Archivos modificados
- `core/agents/calendar_query_parse.py`
- `core/agents/calendar_fast_path.py`

---

## 3. Modelos: 0.8B no aparecía en frontend

### Problema
El endpoint `/api/llama-cpp/models` devolvía 500 porque `_find_all_gguf()` crasheaba al hacer `stat()` sobre symlinks rotos que apuntaban a la carpeta `cerebro/` (ya inexistente). El frontend entonces usaba `FALLBACK_LLAMA_CPP_MODELS` (hardcoded) que no incluía el 0.8B.

### Solución
- **`ui/tray/server.py`** — Agregué `try/except OSError` en `_find_all_gguf()`: si un `.gguf` no se puede leer, lo salta sin crashear todo el endpoint.
- **`ui/tray/src/stores/settings.ts`** — Agregué `Qwen_Qwen3.5-0.8B-Q4_K_M.gguf` (0.5GB) y `Qwen_Qwen3.5-0.8B-Q5_K_M.gguf` (0.6GB) a `FALLBACK_LLAMA_CPP_MODELS`.
- **`bin/models/`** — Eliminé 2 symlinks rotos que causaban el crash.

### Archivos modificados
- `ui/tray/server.py`
- `ui/tray/src/stores/settings.ts`

---

## 4. Terminal: Se borraba al cambiar de pestaña

### Problema
- Al cambiar de sub-pestaña (terminal → scratch → terminal) el panel de terminal aparecía en blanco porque xterm se quedaba huérfano (su `<div>` se desmontaba del DOM).
- Al cambiar de pestaña principal (Code → Chat → Code) el contenido de Scratch se perdía.

### Solución
- **`components/code/CodePanel.tsx`** — Cambié de render condicional (`{activeTab === "x" && <div>}`) a CSS `display: none` (`style={{ display: activeTab === "x" ? "flex" : "none" }}`). Ahora los 3 paneles están siempre en el DOM.
- **`stores/tab.ts`** — Moví `scratch` de `useState` local a Zustand store global, persistiendo su contenido entre montajes/desmontajes de `CodePanel`.

### Archivos modificados
- `ui/tray/src/stores/tab.ts`
- `ui/tray/src/components/code/CodePanel.tsx`

---

## Archivos tocados (resumen)

| Archivo | Cambio |
|---------|--------|
| `integrations/calendar_reader.py` | JXA en vez de AppleScript |
| `core/agents/calendar_query_parse.py` | Regex `tengo/hay eventos [day]` |
| `core/agents/calendar_fast_path.py` | Regex `dime si tengo...` |
| `ui/tray/server.py` | try/except en `_find_all_gguf` |
| `ui/tray/src/stores/settings.ts` | 0.8B en fallback list |
| `ui/tray/src/stores/tab.ts` | `scratch` en store global |
| `ui/tray/src/components/code/CodePanel.tsx` | CSS hide en vez de condicional, scratch desde store |
