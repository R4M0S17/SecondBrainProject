# Búsqueda de archivos multi-root — estado y próxima implementación

**Fecha:** 2026-05-25  
**Contexto:** Pregunta de uso — buscar en Escritorio/Documents vs un solo folder; buscador inteligente sin límite artificial a una carpeta.

---

## Estado actual

La búsqueda de archivos **no recorre todo el Mac**. Solo opera dentro de rutas **autorizadas** (lista blanca por seguridad).

### Rutas por defecto

| Tipo | Rutas típicas |
|------|----------------|
| Lectura | Repo del proyecto + `~/Desktop` + `~/Desktop/CerebroFiles` |
| Escritura | `~/Desktop/CerebroFiles` (`CEREBRO_FILES_PATH`) |

**Sí** incluye automáticamente `~/Desktop` por defecto. No incluye `~/Documents` salvo que lo añadas explícitamente vía `CEREBRO_AUTHORIZED_READ_PATHS` o `Watched Folders`.

### Motor (`search_files`)

- **Multi-root:** si hay varias raíces autorizadas, recorre **todas** (no está limitado a un solo folder).
- **Filtros:** glob, extensión, substring en nombre, texto dentro del archivo (con límites de escaneo).
- **`base_path` opcional:** restringe la búsqueda a una raíz concreta (si está autorizada).

Referencias:

- `core/tools/handlers/filesystem.py` — `search_files`, `_search_roots`
- `core/agents/file_search_fast_path.py` — fast path determinista (ES/EN)
- `tests/test_file_search_fast_path.py` — `test_search_files_all_authorized_roots`

### Fast path (chat rápido)

Dispara sin LLM en frases del estilo:

- *“Busca archivos .py”*
- *“Encuentra archivos llamados informe”*
- *“Busca archivos que contengan presupuesto”*

Usa `authorized_read_paths()` desde **`CEREBRO_AUTHORIZED_READ_PATHS`** (env); como default incluye `~/Desktop`, pero si el usuario amplía rutas en la UI sin tocar el env puede haber brecha.

### Agente con herramientas + UI

- `watched_folders` en **Ajustes → Watched Folders** se fusiona con rutas de lectura al guardar config (`PATCH /api/config`).
- El tool registry del runtime recibe `partial(search_files, authorized_paths=merged_reads)`.

Ver: `ui/tray/server.py` (bloque `watched_folders` en patch de config).

---

## ¿Autorizar Escritorio y Documents?

**Recomendado** para un buscador personal útil, con matices:

| Pros | Contras |
|------|---------|
| Encuentra PDFs, notas y exports reales | Más archivos → búsquedas más lentas |
| Alineado con “segundo cerebro” local | Mayor superficie de privacidad |
| Multi-root ya soportado en código | En Mac 8 GB: evitar raíces enormes sin necesidad |

**No recomendable:** autorizar `~` completo, `Library`, iCloud sin control, carpetas de dependencias masivas (`node_modules`, `.git` ya se saltan en árboles conocidos).

**Enfoque recomendado:** lista corta y explícita de raíces, no “todo el disco”.

---

## Configuración hoy (sin cambiar código)

### Variable de entorno

Rutas separadas por `:`:

```bash
export CEREBRO_AUTHORIZED_READ_PATHS="$HOME/Desktop:$HOME/Documents:$HOME/Downloads:$HOME/Desktop/CerebroFiles:/ruta/al/proyecto"
```

Documentación: [`docs/README.md`](../../README.md) — tabla `CEREBRO_AUTHORIZED_READ_PATHS`.

### UI — Watched Folders

Añadir en ajustes: Escritorio, Documents, Downloads, carpetas de proyecto.

**Importante:** mantener **coherencia** entre env y watched folders para que fast path y agente vean las mismas raíces (ver brecha abajo).

### Perfil sugerido

```text
Lectura:   ~/Desktop, ~/Documents, ~/Downloads, ~/Desktop/CerebroFiles, [proyectos]
Escritura: ~/Desktop/CerebroFiles (u otras 1–2 carpetas explícitas)
RAG:       indexar las mismas carpetas “útiles” vía watched_folders
Evitar:    ~ entero, Library, volúmenes de backup
```

---

## Brecha conocida (prioridad para fix)

| Camino | Fuente de rutas autorizadas |
|--------|------------------------------|
| Fast path (`try_file_search_fast_path`) | `CEREBRO_AUTHORIZED_READ_PATHS` vía `file_search_fast_path.authorized_read_paths()` |
| Agente + tools | `app_state.authorized_read_paths` + `watched_folders` merge en runtime |

Si el usuario **solo** añade carpetas en la UI y no actualiza el env, el fast path puede **no** buscar en esas carpetas aunque el agente con `search_files` sí.

**Workaround actual:** duplicar rutas en env y en Watched Folders; reiniciar backend tras cambiar config.

---

## Próxima implementación y mejoras

### P0 — Alineación de rutas

- [ ] Pasar `app_state.authorized_read_paths` (merged con `watched_folders`) a `try_file_search_fast_path` desde `AgentRuntime._try_file_search_fast_path`.
- [ ] Tests: fast path encuentra archivo solo en carpeta de `watched_folders` sin env extra.
- [ ] Documentar en guía 8 GB que Watched Folders afecta búsqueda tras el fix.

### P1 — Resolución de ubicación en lenguaje natural

- [ ] Parser en `file_search_fast_path` (o módulo compartido) para sinónimos:
  - ES: escritorio, documentos, descargas, cerebro files
  - EN: desktop, documents, downloads
- [ ] Mapear a paths del usuario (`~/Desktop`, `~/Documents`, …) solo si la ruta está **autorizada**.
- [ ] Pasar `base_path` a `search_files` cuando el usuario acote explícitamente; si no, buscar en todas las raíces.

### P2 — Buscador “inteligente” (capas)

| Capa | Qué aporta | Estado |
|------|------------|--------|
| A — Glob / nombre / contenido | Rápido, local, sin GPU extra | **Hecho** (`search_files` + fast path) |
| B — Multi-root explícito | Varias carpetas sin un solo root | **Hecho** (config + env) |
| C — RAG semántico | *“¿dónde está el contrato del piso?”* | **Parcial** — `watched_folders` + indexación |
| D — Ranking / recencia | Ordenar por mtime, tamaño, relevancia | **Pendiente** |
| E — Spotlight / mdfind (macOS) | Búsqueda sistema-wide con permisos | **Fuera de scope** salvo decisión explícita |

### P3 — UX y límites 8 GB

- [ ] Mostrar en respuesta las **raíces** donde se buscó y cuántos resultados por root.
- [ ] Configurable `CEREBRO_SEARCH_MAX_RESULTS` / profundidad máxima por perfil lite.
- [ ] Mensaje claro si la ubicación pedida no está autorizada: *“Añade ~/Documents en Ajustes → Carpetas vigiladas”*.

### Criterios de aceptación (E2E manual)

1. Con Desktop + Documents en `watched_folders`, *“busca archivos pdf”* devuelve resultados de ambas (fast path y agente).
2. *“busca en el escritorio archivos llamados factura”* solo busca en `~/Desktop` si está autorizado.
3. Sin rutas autorizadas, mensaje de error accionable (no lista vacía silenciosa).

### Comandos de verificación

```bash
make test tests/test_file_search_fast_path.py tests/test_filesystem_tools.py -q
.venv/bin/python scripts/test_file_search_llamacpp.py   # live, tmp dir
```

---

## Relacionado

- Sesión frontend (búsqueda multi-root marcada DONE en checklist): [`manual_tests/sessions/frontend_chat_qwen3_2026-05-24.md`](../../../manual_tests/sessions/frontend_chat_qwen3_2026-05-24.md)
- Hidratación `watched_folders` en registry: [`stabilization/fix-plan-v2.md`](../stabilization/fix-plan-v2.md) — Step E1
- Variables ImplemeFIX: [`docs/README.md`](../../README.md)
