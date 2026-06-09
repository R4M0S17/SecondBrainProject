# Local RAG Injection + Document Management

Two-phase implementation that adds RAG context to every agent query and a full document management UI.

---

## Phase 1: Local RAG Injection via ContextBuilder

**Goal**: Wire existing `VectorStore` + `InferenceEngine` into `ContextBuilder.build()` so relevant document chunks are included as context on every agent query. Zero new dependencies, feature-flagged by presence of `vector_store`.

### Changes

#### `core/memory/context_builder.py`

**`__init__`** — new optional params:
- `vector_store: VectorStore | None = None`
- `inference_engine: InferenceEngine | None = None`

**`build()`** — new Priority 4 between memory episodes and session messages:
1. Instructions + working memory (unchanged)
2. Session summary (unchanged)
3. Long-term memory episodes (unchanged)
4. **Vector store documents** — calls `vector_store.search(query, inference_engine, top_k=5)`, inserts matching chunks into `retrieved_documents`, respects remaining token budget
5. Recent session messages (unchanged)

If `vector_store` or `inference_engine` is `None`, Priority 4 is skipped entirely (safe default for tests).

#### `main.py`

Pass `vector_store` and `llm_engine` to `ContextBuilder`, store `inference_engine` on `app_state`:

```python
context_builder = ContextBuilder(
    short_term=short_term,
    long_term=long_term,
    vector_store=vector_store,
    inference_engine=llm_engine,
)
app_state.inference_engine = llm_engine
```

---

## Phase 2: Document Management (Upload + Index + UI)

**Goal**: Fix the index pipeline to actually ingest files, add document list/delete API, add a frontend panel to browse and upload documents.

### Backend Changes (`ui/tray/server.py`)

#### Fixed `_run_index_job`
Before: stub that only counted files.
After: runs `IngestionPipeline.ingest()` + `VectorStore.upsert()` for each file, including recursive directory scanning for supported extensions (`.pdf`, `.txt`, `.md`, `.py`, `.docx`).

New helper `_ingest_file(path, pipeline) → int` handles per-file ingestion with error isolation (one bad file doesn't fail the whole job).

#### New API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/documents` | GET | List all indexed files: `[{source_path, file_modified, filename}]` |
| `/api/documents?source_path=` | DELETE | Remove a file from the vector store by source path |

#### Fixed `/api/files/upload`
Before: saved to tempfile, extracted text, deleted tempfile — no persistence or indexing.
After: saves to `~/.cerebro/files/` (or `CEREBRO_FILES_PATH`), runs ingestion pipeline, auto-indexes into LanceDB. Uses `_safe_dest()` to avoid overwrites (appends `_1`, `_2` etc).

### Frontend Changes

#### New: `DocumentsPanel` (`ui/tray/src/components/documents/DocumentsPanel.tsx`)
Slide-over panel (same pattern as Settings) with:
- **Indexed file list** — each row shows filename, has a delete button on hover
- **Upload** — uses Tauri's native file dialog (`@tauri-apps/plugin-dialog`) to select files, then calls `/api/index` with the paths
- **Re-index** — re-runs indexing on all watched folders
- **Empty state** — helpful message when no documents are indexed
- **Error banner** — inline error display

#### Updated: `Header.tsx`
Added a Documents button (file icon) next to the settings gear, wired to `onDocumentsOpen` prop.

#### Updated: `MainLayout.tsx`
Added local state `docsOpen` with lazy-loaded `DocumentsPanel`. Passes `onDocumentsOpen` callback to `Header`.

#### Updated: `api/client.ts`
Added `listDocuments()` and `deleteDocument()` functions.

#### Updated: `api/types.ts`
Added `DocumentInfo` interface.

### Design Decisions

| Decision | Rationale |
|---|---|
| **`VectorStore.get_indexed_files()` for listing** | Already exists on VectorStore, returns `{source_path → file_modified}`. No new DB queries needed. |
| **`delete_by_source()` for removal** | Already implemented. Cascading delete removes all chunks for a source path. |
| **Tauri dialog for file picking** | Native file picker gives file paths directly → sent to `/api/index`. Consistent with `FolderManager` pattern. |
| **`_safe_dest()` for uploads** | Prevents accidental overwrite of existing files with same name. |
| **Slide-over panel** | Same UX pattern as Settings panel. Consistent with single-page app design (no routing). |

### Files Modified/Created

| File | Change |
|---|---|
| `core/memory/context_builder.py` | +2 params, ~15 new lines in `build()` |
| `main.py` | +1 line storing `app_state.inference_engine`, pass `vector_store`+`llm_engine` to ContextBuilder |
| `ui/tray/server.py` | Fixed `_run_index_job`, added `_ingest_file`, `_safe_dest`, `GET /api/documents`, `DELETE /api/documents`, reworked upload to persist + index |
| `ui/tray/src/api/types.ts` | Added `DocumentInfo` interface |
| `ui/tray/src/api/client.ts` | Added `listDocuments()`, `deleteDocument()` |
| `ui/tray/src/components/documents/DocumentsPanel.tsx` | **New:** document management slide-over panel |
| `ui/tray/src/layouts/Header.tsx` | Added Documents button |
| `ui/tray/src/layouts/MainLayout.tsx` | Added DocumentsPanel rendering |

### Test Compatibility

- `ContextBuilder` tests: new params default to `None`, Priority 4 is a no-op. Zero changes needed.
- API tests: new endpoints are additive. Existing tests unaffected.
