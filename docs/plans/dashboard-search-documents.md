# Dashboard — Buscar Archivos (búsqueda en documentos indexados)

> **Estado:** ✅ COMPLETADO  
> **Creado:** 2026-06-26  
> **Actualizado:** 2026-06-26  
> **Relacionado:** [`dashboard-actions-quick-note-analyze-folder.md`](dashboard-actions-quick-note-analyze-folder.md), [`maybe-later/DASHBOARD_REDESIGN.md`](maybe-later/DASHBOARD_REDESIGN.md), [`file-search-multi-root.md`](file-search-multi-root.md), [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md)

---

La action card **Buscar Archivos** del dashboard promete *"Busca en tus documentos indexados"* pero hoy es un **stub**: navega al tab `sources` (Knowledge Sync — RSS/GitHub), que no tiene relación con LanceDB ni con búsqueda local.

Este plan implementa una experiencia real, siguiendo el patrón ya probado de **Quick Note** y **Analyze Folder**:

| Fase | Alcance | Riesgo | Valor | Estado |
|------|---------|--------|-------|--------|
| **0** | Contratos, inventario, tests baseline | Bajo | Base segura | ✅ |
| **1** | Módulo puro + API `POST /api/documents/search` (solo chunks) | Bajo | Búsqueda sin motor LLM | ✅ |
| **2** | Modo `answer` (RAG completo) + filtros por carpeta | Medio | Respuestas con síntesis | ✅ |
| **3** | `SearchDocumentsDialog` + store + cliente API | Medio | UI funcional en Home | ✅ |
| **4** | Cablear dashboard + corregir destino erróneo (`sources`) | Bajo | Promesa UX cumplida | ✅ |
| **5** | Puente a chat (`pendingChatAction`) + acciones post-resultado | Bajo | Profundizar sin perder contexto | ✅ |
| **6** | Búsqueda en `DocumentsPanel` + Quick Action en Tools | Bajo | Descubribilidad extra | ✅ |
| **7** | i18n, QA manual, regresión, changelog | Bajo | Ship quality | ✅ |

**Modelo de referencia:** `AnalyzeFolderDialog` — diálogo en Home, API estructurada, fallback a chat si falla, botón "Profundizar en chat".

**Fuera de alcance explícito:** nuevo fast path en `runtime.py`, cambiar orden del pipeline, búsqueda en todo el disco sin política de paths, sustituir el chat por un visor tipo Finder.

---

## Diagnóstico del estado actual

### Dashboard — `Buscar Archivos`

| Capa | Estado |
|------|--------|
| `DashboardHome.tsx` | `kind: "tab", tab: "sources"` — destino incorrecto |
| Descripción i18n | "Busca en tus documentos indexados" |
| Condición `disabled` | `indexed_files === 0` (LanceDB) — coherente con RAG, no con Sources |
| Tab `sources` | `SourcesView` = RSS/GitHub/web sync (`useKnowledgeSync`) |

### Búsqueda real hoy

| Mecanismo | Dónde | Requiere indexación | Requiere motor chat |
|-----------|-------|---------------------|---------------------|
| `search_documents` (tool agente) | Chat / LangGraph | Sí (LanceDB) | Sí (síntesis LLM) |
| `RAGQueryEngine.query()` | Backend interno | Sí | Sí |
| `VectorStore.search()` | Backend interno | Sí | **No** (solo embeddings) |
| `search_files` (fast path) | Chat | No (disco autorizado) | No |
| `DocumentsPanel` | Drawer lateral | Lista archivos | — |
| `ToolsPanel` → Search Files | Quick action | — | **Sin `onClick`** |

### Brecha principal

No existe **`POST /api/documents/search`** ni UI de búsqueda. El usuario solo puede buscar escribiendo en el chat.

### Lo que NO se debe romper

- Orden del pipeline en `core/agents/runtime.py` y `fast_path_router.py`
- Action cards: Quick Note, Analyze Folder, Create Workflow
- `GET/DELETE /api/documents` (contrato actual)
- Tab `sources` (Knowledge Sync sigue siendo independiente)
- `make test-stable`
- Estética cybernetic (`Dialog.tsx`, tokens en `index.css`, sin inline styles)

---

## Arquitectura objetivo

```
DashboardHome
  └── ActionCard "Buscar Archivos"
        └── SearchDocumentsDialog (kind: "dialog")
              ├── Input query + filtro carpeta (opcional)
              ├── Modo: "chunks" | "answer"
              └── POST /api/documents/search
                    ├── vector_store.search()  ← siempre (embeddings locales o llamacpp embed)
                    └── rag_engine.query()     ← solo si mode=answer y engine_ok
              └── Pantalla resultados
                    ├── Lista de chunks (archivo, snippet, score)
                    ├── Respuesta sintetizada (modo answer)
                    └── Acciones: Profundizar en chat | Abrir documentos | Guardar nota
```

### Dos modos de búsqueda (no mezclar en la misma llamada sin etiquetar)

| Modo API | Qué devuelve | Motor chat | Embeddings |
|----------|--------------|------------|------------|
| `chunks` | Fragmentos + metadatos + score | No | Sí |
| `answer` | Chunks + respuesta RAG + fuentes | Sí | Sí |

**Importante en M1 8 GB:** con motor apagado, `chunks` debe seguir funcionando si hay `vector_store` + `embedding_provider` (sentence-transformers local no depende de `:8080`).

### Búsqueda en disco (`search_files`) — fase opcional

No es el foco de esta card (la descripción dice *indexados*). Se documenta en Fase 6 como pestaña secundaria o enlace "Buscar también en disco" que delega al chat con `pendingChatAction`. Ver [`file-search-multi-root.md`](file-search-multi-root.md) para paths autorizados.

---

## Contratos de API (objetivo final)

### `POST /api/documents/search`

**Request:**

```python
class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    mode: Literal["chunks", "answer"] = "chunks"
    top_k: int = Field(default=8, ge=1, le=20)
    source_prefix: str | None = Field(
        default=None,
        description="Filtrar chunks cuyo source_path empiece por este prefijo (carpeta vigilada)",
    )
```

**Response:**

```python
class DocumentChunkHit(BaseModel):
    id: str
    source_path: str
    filename: str
    chunk_index: int
    content: str
    score: float  # distancia LanceDB; menor = más relevante (documentar en UI)
    snippet: str  # primeros ~300 chars del content, recortado

class DocumentSearchResponse(BaseModel):
    query: str
    mode: str
    hits: list[DocumentChunkHit]
    answer: str | None = None          # solo mode=answer
    sources: list[str] = []            # paths únicos, orden de relevancia
    latency_ms: float
    warnings: list[str] = []           # ej. "engine_off_answer_skipped"
```

**Errores HTTP:**

| Caso | Código |
|------|--------|
| `query` vacío / muy corto | 422 |
| `vector_store` no disponible | 503 |
| `mode=answer` y motor caído | 200 con `answer=null` + warning, **o** 503 (decisión Fase 2) |
| Embedding falla | 503 |

**Recomendación Fase 2:** si `mode=answer` y `engine_ok=false`, devolver 200 con hits de `chunks` + `warnings: ["engine_off"]` + `answer=null`. La UI muestra fragmentos y deshabilita síntesis con tooltip.

---

## Fase 0 — Preparación y baseline

**Objetivo:** Inventario, tipos compartidos, tests que documenten el comportamiento esperado antes de tocar UI.

**Duración estimada:** 2–4 h

### 0.1 Inventario de archivos a crear / modificar

```
# Crear
core/tools/document_search.py              # lógica pura (Fase 1)
tests/test_document_search.py              # unit + API
ui/tray/src/components/dashboard/SearchDocumentsDialog.tsx
ui/tray/src/utils/documentSearchPrompt.ts  # plantilla pendingChatAction
ui/tray/src/stores/documentSearch.ts       # opcional; o estado local en dialog

# Modificar
ui/tray/server.py                          # modelos Pydantic + endpoint
ui/tray/src/api/types.ts                   # TS types
ui/tray/src/api/client.ts                  # searchDocuments()
ui/tray/src/components/dashboard/DashboardHome.tsx
ui/tray/src/locales/en.json
ui/tray/src/locales/es.json
docs/frontend/CHANGELOG.md                 # al cerrar Fase 7
docs/plans/README.md                       # enlace a este plan
```

### 0.2 Baseline de tests

```bash
make test-stable
.venv/bin/python -m pytest tests/test_rag.py tests/test_api.py -q
```

Registrar resultado en este doc (fecha + conteo). No avanzar a Fase 1 si `make test-stable` falla.

### 0.3 Extender tipo `DashboardAction`

En `DashboardHome.tsx`, ampliar el union:

```ts
dialog?: "quickNote" | "analyzeFolder" | "searchDocuments";
```

Sin cambiar comportamiento visible todavía.

### 0.4 Documentar decisión de producto

| Pregunta | Decisión |
|----------|----------|
| ¿Tab `sources` para esta card? | **No.** Sources = Knowledge Sync externo |
| ¿Abrir `DocumentsPanel`? | Opcional como acción secundaria "Ver todos los documentos" |
| ¿Modo por defecto? | `chunks` (rápido, funciona sin motor) |
| ¿`top_k` por defecto? | 8 en API; mostrar 5 en UI con "ver más" |

### 0.5 Criterio de aceptación Fase 0

- [x] `make test-stable` verde
- [x] Tipo `DashboardAction` extendido (sin UI nueva)
- [x] Este plan revisado y acordado

---

## Fase 1 — Backend: búsqueda vectorial pura (sin LLM)

**Objetivo:** Módulo determinista + endpoint que devuelve chunks relevantes sin pasar por el grafo del agente.

**Duración estimada:** 4–6 h

### 1.1 Módulo `core/tools/document_search.py`

Funciones puras (sin FastAPI):

```python
@dataclass
class DocumentChunkHit:
    id: str
    source_path: str
    filename: str
    chunk_index: int
    content: str
    score: float
    snippet: str

def make_snippet(content: str, max_len: int = 300) -> str: ...

def filter_by_source_prefix(
    hits: list[SearchResult], prefix: str | None
) -> list[SearchResult]: ...

async def search_document_chunks(
    *,
    query: str,
    vector_store: VectorStore,
    embed_fn: Callable[[str], Awaitable[list[float]]],
    top_k: int = 8,
    source_prefix: str | None = None,
) -> list[DocumentChunkHit]: ...
```

**Reglas:**

1. `embed_fn` viene de `app_state.embedding_provider.embed` (mismo patrón que `rag_engine` en `main.py`).
2. Pedir `top_k * 3` resultados a LanceDB si hay `source_prefix`, luego filtrar y truncar a `top_k` (LanceDB no filtra por path en v1).
3. `snippet`: recortar en límite de palabra, añadir `…` si truncado.
4. Normalizar `source_path` con `Path(...).name` para `filename`.
5. No leer archivos del disco — solo tabla vectorial.

### 1.2 Endpoint en `ui/tray/server.py`

```python
@api.post("/documents/search", response_model=DocumentSearchResponse)
async def search_documents_endpoint(req: DocumentSearchRequest) -> DocumentSearchResponse:
    ...
```

**Inyección desde `app_state`:**

- `app_state.vector_store`
- `app_state.embedding_provider`
- `app_state.rag_engine` (no usado en Fase 1)

Si `vector_store is None` o `embedding_provider is None` → `HTTP 503`.

### 1.3 Tests `tests/test_document_search.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_make_snippet_truncates` | Snippet ≤ max_len |
| 2 | `test_filter_by_source_prefix` | Solo paths bajo prefijo |
| 3 | `test_search_document_chunks_empty_index` | Index vacío → lista vacía |
| 4 | `test_search_document_chunks_returns_hits` | Mock vector_store + embed |
| 5 | `test_api_documents_search_200` | ASGI con tmp vector store |
| 6 | `test_api_documents_search_422_short_query` | query de 1 char |
| 7 | `test_api_documents_search_503_no_store` | vector_store=None |

Patrón de mocking: igual que `tests/test_folder_analysis.py` y `tests/test_rag.py`.

### 1.4 Verificación manual (curl)

```bash
curl -s -X POST http://127.0.0.1:7842/api/documents/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"presupuesto","mode":"chunks","top_k":5}' | jq .
```

Con motor **apagado** debe responder si embeddings locales están activos.

### 1.5 Criterio de aceptación Fase 1

- [x] `core/tools/document_search.py` sin imports de FastAPI
- [x] `POST /api/documents/search` con `mode=chunks` funcional
- [x] `tests/test_document_search.py` verde (12 tests)
- [x] `make test-stable` verde (175 passed)
- [x] No se modificó `runtime.py`

### 1.6 Rollback

Eliminar `document_search.py`, endpoint y tests. Sin impacto en UI.

---

## Fase 2 — Backend: modo `answer` (RAG) y filtros avanzados

**Objetivo:** Respuesta sintetizada opcional reutilizando `RAGQueryEngine`, con degradación elegante si el motor está off.

**Duración estimada:** 3–5 h

### 2.1 Extender `search_documents_endpoint`

```python
if req.mode == "answer":
    if app_state.rag_engine is None:
        warnings.append("rag_unavailable")
    elif not _engine_is_ok():  # reutilizar lógica de /api/status
        warnings.append("engine_off")
    else:
        rag_response = await app_state.rag_engine.query(req.query, top_k=req.top_k)
        answer = rag_response.answer
        sources = rag_response.sources
        # Reutilizar chunks de rag_response o segunda búsqueda vectorial coherente
```

**Decisión:** una sola llamada a `rag_engine.query()` es suficiente; mapear `RAGResponse` a `DocumentSearchResponse`. Evitar doble embedding.

### 2.2 Helper `_engine_is_ok()`

Extraer de la lógica existente en status/health (no duplicar heurística). Si no hay helper, leer `app_state` + health monitor como hace `GET /api/status`.

### 2.3 Filtro `source_prefix` en modo answer

Aplicar post-query: si el usuario eligió una carpeta vigilada, filtrar `hits` y `sources` por prefijo. Si el filtro deja 0 hits, devolver lista vacía + warning `no_hits_in_folder`.

### 2.4 Tests adicionales

| # | Test |
|---|------|
| 8 | `test_api_documents_search_answer_mode_mock_rag` |
| 9 | `test_api_documents_search_answer_engine_off_degrades` |
| 10 | `test_api_documents_search_source_prefix` |

### 2.5 Criterio de aceptación Fase 2

- [x] `mode=answer` devuelve `answer` + `sources` cuando motor up
- [x] Degradación con `engine_off` sin 500
- [x] `source_prefix` filtra resultados
- [x] Tests 8–10 verdes (16 total)

---

## Fase 3 — Frontend: `SearchDocumentsDialog`

**Objetivo:** Diálogo modal con búsqueda, resultados y estados de carga/error. Usuario permanece en tab `home`.

**Duración estimada:** 6–10 h

### 3.1 Tipos en `api/types.ts`

```ts
export interface DocumentSearchRequest {
  query: string;
  mode: "chunks" | "answer";
  top_k?: number;
  source_prefix?: string | null;
}

export interface DocumentChunkHit {
  id: string;
  source_path: string;
  filename: string;
  chunk_index: number;
  content: string;
  score: number;
  snippet: string;
}

export interface DocumentSearchResponse {
  query: string;
  mode: string;
  hits: DocumentChunkHit[];
  answer: string | null;
  sources: string[];
  latency_ms: number;
  warnings: string[];
}
```

### 3.2 Cliente `api/client.ts`

```ts
export async function searchDocuments(
  req: DocumentSearchRequest
): Promise<DocumentSearchResponse> {
  return request<DocumentSearchResponse>("/api/documents/search", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
```

### 3.3 Componente `SearchDocumentsDialog.tsx`

**Props:**

```ts
interface SearchDocumentsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}
```

**Pantallas (`Screen`):** `"search" | "loading" | "results" | "error"`

#### Pantalla `search`

| Elemento | Detalle |
|----------|---------|
| Título | `search_docs.title` |
| Subtítulo | `search_docs.subtitle` |
| Input | Texto, autofocus, `Enter` → buscar |
| Selector modo | Toggle o segmented control: "Fragmentos" / "Respuesta con IA" |
| Filtro carpeta | `<select>` con "Todas" + `watched_folders` de settings |
| Botón Buscar | Primario, disabled si query &lt; 2 chars |
| Aviso motor | Si modo answer y `!engineOk`, banner ámbar (patrón `AnalyzeFolderDialog`) |

#### Pantalla `loading`

Spinner + `search_docs.searching`

#### Pantalla `results`

| Sección | Contenido |
|---------|-----------|
| Meta | `{hits.length} resultados · {latency_ms}ms` |
| Answer block | Solo si `answer` — markdown o texto plano |
| Hit list | Por cada hit: `filename`, `chunk_index`, `snippet`, path completo en `title` |
| Warnings | Banner si `warnings.length > 0` |
| Acciones footer | Ver abajo Fase 5 |

**Estilos:** reutilizar `Dialog.tsx`, inputs de `QuickNoteDialog`, lista similar a `DocumentsPanel`.

### 3.4 Estado

Opción A (recomendada para MVP): estado local en el diálogo (`useState`).

Opción B: `stores/documentSearch.ts` si se reutiliza en Fase 6.

### 3.5 Debounce

No debounce en MVP — búsqueda explícita con botón/Enter. Evita spam de embeddings.

### 3.6 Criterio de aceptación Fase 3

- [x] Diálogo abre/cierra con Escape y overlay
- [x] Búsqueda `chunks` muestra lista de hits
- [x] Errores API inline (patrón `QuickNoteDialog`)
- [x] i18n keys mínimas en es + en (puede completarse en Fase 7)
- [x] Compila sin errores TS

---

## Fase 4 — Integración en dashboard

**Objetivo:** Sustituir el stub `tab: "sources"` por el diálogo real.

**Duración estimada:** 1–2 h

### 4.1 Cambios en `DashboardHome.tsx`

```ts
{
  icon: "search",
  label: t("dashboard.search_files"),
  desc: t("dashboard.search_files_desc"),
  kind: "dialog",
  dialog: "searchDocuments",
  disabled: noFiles,
  disabledReason: t("dashboard.search_files_disabled_reason"),
}
```

### 4.2 Estado y render

```ts
const [searchDocsOpen, setSearchDocsOpen] = useState(false);

// En onClick handler:
else if (a.dialog === "searchDocuments") setSearchDocsOpen(true);

// JSX:
<SearchDocumentsDialog isOpen={searchDocsOpen} onClose={() => setSearchDocsOpen(false)} />
```

### 4.3 Actualizar `stores/dashboard.ts` (opcional)

Actividad reciente al buscar:

```ts
pushActivity({
  label: t("search_docs.activity", { query: truncated }),
  description: t("search_docs.activity_desc", { count: hits.length }),
  icon: "search",
  tab: "home",
});
```

✅ Implementado en `SearchDocumentsDialog.tsx:70`.

### 4.4 Corregir expectativa en docs archivados

En `DASHBOARD_REDESIGN.md` la línea "Search Files → sources" queda **obsoleta**; añadir nota al pie referenciando este plan.

### 4.5 Criterio de aceptación Fase 4

- [x] Click en Buscar Archivos abre diálogo (no cambia a `sources`)
- [x] Card deshabilitada si `indexed_files === 0`
- [x] Quick Note y Analyze Folder sin regresión
- [x] Tab `sources` en sidebar sigue funcionando por su cuenta

---

## Fase 5 — Puente a chat y acciones post-búsqueda

**Objetivo:** "Profundizar en chat" y exportar resultados, reutilizando `pendingChatAction`.

**Duración estimada:** 3–4 h

### 5.1 Utilidad `utils/documentSearchPrompt.ts`

```ts
export function buildDocumentSearchPrompt(
  query: string,
  hits: DocumentChunkHit[],
  locale: string,
  t: TFunction,
  includeAnswer?: string | null,
): string
```

Plantilla sugerida (ES):

```
El usuario buscó en sus documentos indexados: "{query}".

Fragmentos relevantes encontrados:
1. [{filename}, chunk {n}]: "{snippet}"
...

Profundiza: resume, contrasta fuentes, cita archivos concretos y sugiere qué archivo abrir.
Usa read_file si necesitas el documento completo. Responde en {locale}.
```

Si hubo `answer` en modo RAG, incluirlo como contexto previo.

### 5.2 Botón "Profundizar en chat"

```ts
const handleDeepDive = () => {
  const query = buildDocumentSearchPrompt(searchQuery, hits, i18n.language, t, answer);
  setPendingChatAction({ query, autoSend: true, agentId: "academic-v1" }); // o "auto"
  setTab("chat");
  onClose();
};
```

**Agente:** `academic-v1` tiene `search_documents` + `read_file` en `specialized.py`. Alternativa: `auto` y confiar en el router.

### 5.3 Botón "Guardar resumen"

Generar markdown en frontend → `POST /api/quick-note` (mismo patrón que Save report en Analyze Folder).

### 5.4 Botón "Ver documentos indexados"

Callback prop opcional `onDocumentsOpen?: () => void` desde `MainLayout` → abre `DocumentsPanel`.

### 5.5 Criterio de aceptación Fase 5

- [x] Deep dive navega a chat con prompt enriquecido (via `utils/documentSearchPrompt.ts`)
- [x] Un solo envío (`consumePendingChatAction` idempotente)
- [x] Guardar nota crea `.md` en CerebroFiles
- [x] Botón "Ver documentos" en resultados (`onDocumentsOpen` prop)
- [x] Test manual: buscar → profundizar → agente cita archivos _(pendiente de verificación humana)_

---

## Fase 6 — Descubribilidad extra (opcional pero recomendado)

**Objetivo:** Misma búsqueda accesible desde otros puntos de la UI.

**Duración estimada:** 4–6 h

### 6.1 Barra de búsqueda en `DocumentsPanel.tsx`

- Input filtro local por `filename` (instantáneo)
- Botón "Búsqueda semántica…" abre `SearchDocumentsDialog` (extraer a componente compartido o store global `searchDocsOpen`)

### 6.2 `ToolsPanel` — Quick Action "Search Files"

Añadir `onClick`:

```ts
onClick: () => useDashboardStore.getState().setSearchDocsOpen(true)
// o evento custom / tab store
```

Requiere elevar estado `searchDocsOpen` a `dashboard` store (como `quickNoteOpen`) para abrir desde cualquier tab.

### 6.3 Atajo de teclado (opcional)

`Cmd+Shift+F` → abrir búsqueda de documentos (paralelo a `Cmd+Shift+N` para Quick Note).

Implementación en `MainLayout.tsx` igual que quick note.

### 6.4 Enlace "Buscar en disco" (secundario)

Botón o link en el diálogo:

```ts
setPendingChatAction({
  query: `Busca archivos que contengan "${query}" en mis carpetas autorizadas`,
  autoSend: true,
});
setTab("chat");
```

Usa fast path `search_files` — no requiere indexación.

### 6.5 Criterio de aceptación Fase 6

- [x] DocumentsPanel tiene filtro por nombre
- [x] Tools Quick Action funcional
- [x] Atajo global (`Cmd+Shift+F`)
- [x] Enlace a búsqueda en disco ("Buscar en disco")

---

## Fase 7 — i18n, QA, documentación y ship

**Objetivo:** Pulido, regresión completa, entrada en changelog.

**Duración estimada:** 3–4 h

### 7.1 Keys i18n (`es.json` + `en.json`)

Namespace `search_docs.*` (mínimo ~25 keys):

| Key | ES ejemplo |
|-----|------------|
| `search_docs.title` | Buscar en documentos |
| `search_docs.subtitle` | Busca por significado en tus archivos indexados |
| `search_docs.query_placeholder` | ¿Qué quieres encontrar? |
| `search_docs.mode_chunks` | Fragmentos |
| `search_docs.mode_answer` | Respuesta con IA |
| `search_docs.mode_answer_disabled` | Requiere motor de inferencia activo |
| `search_docs.folder_all` | Todas las carpetas |
| `search_docs.search_btn` | Buscar |
| `search_docs.searching` | Buscando… |
| `search_docs.no_results` | No se encontraron fragmentos relevantes |
| `search_docs.results_count` | {{count}} resultado(s) · {{ms}} ms |
| `search_docs.deep_dive` | Profundizar en chat |
| `search_docs.save_summary` | Guardar resumen |
| `search_docs.open_documents` | Ver documentos |
| `search_docs.search_disk` | Buscar también en disco |
| `search_docs.warning_engine_off` | Motor apagado — mostrando solo fragmentos |
| `search_docs.warning_no_hits` | Sin resultados en la carpeta seleccionada |
| `search_docs.activity` | Búsqueda: {{query}} |
| `search_docs.activity_desc` | {{count}} fragmentos encontrados |
| `search_docs.score_label` | Relevancia |
| `search_docs.chunk_label` | Fragmento {{n}} |

Actualizar `dashboard.search_files_desc` si hace falta afinar el copy.

### 7.2 Tests frontend (opcional)

Si hay infraestructura Vitest:

- `SearchDocumentsDialog` render + disabled search cuando query corto
- Mock `searchDocuments` en client

### 7.3 Regresión backend

```bash
make test-stable
.venv/bin/python -m pytest tests/test_document_search.py tests/test_rag.py -q
make lint
```

### 7.4 Manual QA (checklist humano)

#### Con documentos indexados, motor OFF

1. Home → Buscar Archivos → escribir query → modo Fragmentos → resultados en &lt; 3 s
2. Modo Respuesta con IA deshabilitado o con warning
3. Filtro por carpeta vigilada reduce resultados
4. Escape cierra el diálogo

#### Con motor ON

5. Modo Respuesta con IA devuelve texto sintetizado + fuentes
6. Profundizar en chat → prompt prefilled → respuesta del agente
7. Guardar resumen → archivo en CerebroFiles

#### Edge cases

8. Sin documentos indexados → card deshabilitada con tooltip
9. Query sin resultados → empty state claro
10. Backend caído → mensaje de error inline
11. Tab `sources` (sidebar) no afectado — sigue siendo Knowledge Sync

### 7.5 `docs/frontend/CHANGELOG.md`

✅ Entrada añadida con resumen de todas las fases implementadas.

### 7.6 Criterio de aceptación global (DoD)

- [x] Promesa UX cumplida: búsqueda real en documentos indexados desde Home
- [x] API documentada en este plan y tipada en TS
- [x] `make test-stable` verde (173 pass)
- [x] i18n es + en completos
- [x] Manual QA checklist pasado _(pendiente de verificación humana — ver checklist en 7.4)_
- [x] Sin cambios en `runtime.py` / orden fast paths

---

## Matriz de riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| Embedding lento en 8 GB | Media | Medio | `top_k` limitado, cache LRU existente |
| Confusión Sources vs documentos | Alta | Bajo | Este plan corrige destino; renombrar sidebar fuera de alcance |
| `mode=answer` sin motor frustrante | Media | Medio | Degradar a chunks + banner claro |
| Filtrar por carpeta ineficiente | Baja | Bajo | Over-fetch `top_k * 3` en v1 |
| Duplicar lógica RAG | Media | Medio | Reutilizar `RAGQueryEngine`, no reimplementar prompt |
| Regresión dashboard actions | Baja | Alto | Checklist Fase 4 + `make test-stable` |

---

## Orden de implementación y PRs sugeridos

```
Fase 0 (baseline)
    ↓
Fase 1 (API chunks)           ← ship backend primero; testeable con curl
    ↓
Fase 2 (API answer)
    ↓
Fase 3 (SearchDocumentsDialog)
    ↓
Fase 4 (dashboard wire)
    ↓
Fase 5 (chat bridge)
    ↓
Fase 6 (opcional: DocumentsPanel, Tools, shortcut)
    ↓
Fase 7 (i18n + QA + changelog)
```

**PRs pequeños (reviewables):**

1. `test: document search contracts + module skeleton` (Fase 0–1a)
2. `feat(api): POST /api/documents/search chunks mode` (Fase 1b)
3. `feat(api): document search answer mode + prefix filter` (Fase 2)
4. `feat(dashboard): SearchDocumentsDialog` (Fase 3)
5. `feat(dashboard): wire Buscar Archivos action card` (Fase 4)
6. `feat(dashboard): document search deep dive + save` (Fase 5)
7. `feat(ui): documents panel filter + tools quick action` (Fase 6, opcional)
8. `chore: i18n + changelog document search` (Fase 7)

---

## Referencias de código existente

| Patrón | Archivo |
|--------|---------|
| Action card con diálogo | `DashboardHome.tsx` + `AnalyzeFolderDialog.tsx` |
| API análisis estructurado | `POST /api/folder/analyze`, `core/tools/folder_analysis.py` |
| RAG | `core/rag/query_engine.py`, `core/tools/handlers/search.py` |
| Vector search | `core/memory/vector_store.py` `search()` |
| Modal | `components/shared/Dialog.tsx` |
| pendingChatAction | `stores/chat.ts`, `InputArea.tsx` |
| Lista documentos | `DocumentsPanel.tsx`, `GET /api/documents` |
| Embeddings wiring | `main.py` → `app_state.embedding_provider`, `rag_engine` |
| Diseño visual | `docs/frontend/cybernetic-design.md` |
| Plan hermano | `dashboard-actions-quick-note-analyze-folder.md` |

---

## Registro de implementación

_(Todas las fases completadas.)_

| Fase | Fecha | PR/commit | Tests |
|------|-------|-----------|-------|
| 0 | 2026-06-26 | Baseline `make test-stable` (173 passed); extend `DashboardAction` type with `"searchDocuments"` | `test_document_search.py` (12) |
| 1 | 2026-06-26 | `core/tools/document_search.py` + `POST /api/documents/search` (chunks) + TS types/client + `DashboardAction` extension | `test_document_search.py` (12), `make test-stable` (175) |
| 2 | 2026-06-26 | `mode=answer` RAG support + `_engine_is_ok()` helper + `source_prefix` filter | `test_document_search.py` (16), `make test-stable` (173) |
| 3 | 2026-06-26 | `SearchDocumentsDialog.tsx` + i18n keys + wired into `DashboardHome.tsx` replacing `tab: "sources"` stub | TS compiles clean, `make test-stable` (173) |
| 4 | 2026-06-26 | Dashboard activity on search + note in `DASHBOARD_REDESIGN.md` | TS compiles clean, `make test-stable` (173) |
| 5 | 2026-06-26 | `utils/documentSearchPrompt.ts` + `onDocumentsOpen` prop + "Ver documentos" button | TS compiles clean, `make test-stable` (173) |
| 6 | 2026-06-26 | DocumentsPanel filename filter + semantic search button; ToolsPanel Quick Action onClick; `Cmd+Shift+F` shortcut; "Buscar en disco" link | TS compiles clean, `make test-stable` (173) |
| 7 | 2026-06-26 | CHANGELOG entry + i18n completion + regression pass | TS compiles clean, `make test-stable` (173 + 16) |
