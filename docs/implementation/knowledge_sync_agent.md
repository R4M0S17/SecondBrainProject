# Knowledge Sync Agent — Implementación

> **Blueprint** (archived): `docs/plans/maybe-later/knowledge_sync_agent.md`
> **Implementado**: 2026-06-14
> **Estado**: Completado — backend funcional + frontend integrado + 13 tests pass

---

## Arquitectura

```
POST /api/knowledge-sync/sync {"force": true}
  → RAM ≥ 0.3 GB? NO → abort (hard gate, never bypassed)
  → force=false? → check LLM idle + system idle
  → Source.fetch() → FetchedItem[]
  → ContentFilter.filter()
      Layer 1: embed(title+summary) · embed(interest_tags) ≥ 0.6
      Layer 2: search_by_vector(embedding) en LanceDB, skip si distance ≤ 0.92
      Layer 3: (opcional) Qwen2.5-0.5B evalúa novelty
  → ChunkingEngine.chunk() → Document[]
  → VectorStore.upsert() → LanceDB (local embeddings, no llama server needed)
```

### URIs sintéticas

| Source | `source_path` format |
|--------|----------------------|
| RSS | `knowledge://rss/{feed}/{article_id}` |
| GitHub | `knowledge://github/{owner}/{repo}/{path}` |
| Web | `knowledge://web/{domain}/{path}` |
| Manual | `knowledge://manual/{sha256(url)}` |

Se reusa la tabla `documents` de LanceDB.

---

## Módulos

```
core/knowledge_sync/
├── __init__.py
├── models.py              — FetchedItem, SyncSourceConfig, SyncState, SyncResult, enums
├── source_base.py         — SyncSource ABC (fetch/validate/estimate_next)
├── content_filter.py      — 3-layer filter + SLM helpers
│   ├── _filter_by_embedding()  — cosine sim vs interest_tags
│   ├── _filter_dedup()         — L2 distance vs LanceDB (≤ 0.92 = dup)
│   └── _filter_novelty_slm()  — Qwen2.5-0.5B (on-demand, no auto-start)
├── chunking.py            — word-level sliding window → Document[]
├── state_store.py         — JSON persistente por source (ETags, timestamps, errors)
├── orchestrator.py        — KnowledgeSyncOrchestrator
│   ├── trigger_sync()     — entry point público (API + scheduler)
│   ├── sync_one()         — ciclo completo para una fuente
│   ├── sync_all()         — fuentes habilitadas + debidas (check intervalo)
│   └── _sync_all_forced() — salta check intervalo (force=true)
├── router.py              — FastAPI router (/api/knowledge-sync/*)
└── sources/
    ├── __init__.py
    ├── rss_source.py      — feedparser + HTTP condicional (ETag/304)
    ├── github_source.py   — GitHub REST API (salta binarios, node_modules, etc.)
    └── web_source.py      — trafilatura para extracción de texto
```

### Filtro 3-capas

```
FetchedItem
    │
    ▼ Layer 1: Relevance (embedding cosine sim vs interest_tags)
    │  skip si score < 0.6
    │
    ▼ Layer 2: Semantic dedup (L2 distance contra LanceDB)
    │  skip si distance ≤ 0.92 (LanceDB _distance, 0 = identical)
    │
    ▼ Layer 3: Novelty SLM (condicional, solo manual o ≤2 items)
    │  usa Qwen2.5-0.5B en :8081, on-demand
    │  modelo: qwen2.5-0.5b-instruct-q5_k_m.gguf (498MB, ya descargado)
    │
    ▼ ChunkingEngine → VectorStore.upsert()
```

---

## Endpoints REST

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/knowledge-sync/sources` | Lista fuentes con estado |
| `POST` | `/api/knowledge-sync/sources` | Registrar fuente nueva |
| `DELETE` | `/api/knowledge-sync/sources/:id` | Eliminar fuente |
| `POST` | `/api/knowledge-sync/sync` | Sync manual (payload: `{"force":true}`) |
| `POST` | `/api/knowledge-sync/sync/:id` | Sync una fuente específica |
| `GET` | `/api/knowledge-sync/sources/:id/state` | Estado detallado |

---

## Archivos modificados

### Backend

| Archivo | Cambio |
|---------|--------|
| `core/memory/vector_store.py` | Nuevo método `search_by_vector(vector, top_k)` |
| `core/knowledge_sync/models.py` | +90 líneas: dataclasses + enums |
| `core/knowledge_sync/source_base.py` | +30 líneas: SyncSource ABC |
| `core/knowledge_sync/sources/rss_source.py` | +90 líneas: RssSyncSource |
| `core/knowledge_sync/sources/github_source.py` | +130 líneas: GithubSyncSource |
| `core/knowledge_sync/sources/web_source.py` | +55 líneas: WebSyncSource |
| `core/knowledge_sync/content_filter.py` | +210 líneas: ContentFilter 3-capas |
| `core/knowledge_sync/chunking.py` | +55 líneas: ChunkingEngine |
| `core/knowledge_sync/state_store.py` | +40 líneas: SyncStateStore |
| `core/knowledge_sync/orchestrator.py` | +200 líneas: KnowledgeSyncOrchestrator + pipeline |
| `core/knowledge_sync/router.py` | +70 líneas: FastAPI router |
| `main.py` | Wiring: instancia orchestrator, mount router, restore sources |
| `config/settings.toml` | Nueva sección `[knowledge_sync]` |
| `scheduler/proactive.py` | `attach_knowledge_sync_orchestrator()` + tick |
| `pyproject.toml` | Add `feedparser>=6.0` |

### Frontend

| Archivo | Cambio |
|---------|--------|
| `ui/tray/src/stores/tab.ts` | `LeftTab` incluye `"sources"` |
| `ui/tray/src/layouts/LeftSidebar.tsx` | Nuevo tab `sources` con icono `rss_feed` |
| `ui/tray/src/layouts/MainLayout.tsx` | Routing: `activeTab === "sources" → <SourcesView />` |
| `ui/tray/src/layouts/Header.tsx` | Botón Sync con toast de feedback |
| `ui/tray/src/api/types.ts` | Tipos: `SyncSource`, `SyncResult`, `SyncTriggerPayload`, `AppConfig.knowledge_sync` |
| `ui/tray/src/api/client.ts` | 6 funciones API: `listSyncSources`, `addSyncSource`, `removeSyncSource`, `triggerSync`, `syncOneSource`, `getSyncSourceState` |
| **`ui/tray/src/components/settings/SourcesView.tsx`** | **NUEVO** — Vista completa offline-first para left tab |
| `ui/tray/src/components/settings/KnowledgeSyncPanel.tsx` | **REESCRITO** — Solo toggle enable/disable en Settings |
| `ui/tray/src/components/settings/SettingsPanel.tsx` | Sección "Knowledge Sync" con toggle |

---

## Bugs encontrados y arreglados

| Bug | Síntoma | Archivo | Fix |
|-----|---------|---------|-----|
| **RAM gate demasiado alto** | Sync bloqueado con "Low RAM pressure" en M1 8GB | `orchestrator.py:82` | Umbral bajado de 1.0 → 0.3 GB |
| **Embed provider no era callable** | `'CachedEmbeddingProvider' object is not callable` | `content_filter.py:27` | `getattr(provider, "embed", provider)` |
| **Upsert usaba InferenceEngine** | Embeddings fallaban (modelo `nomic-embed-text` no disponible en llama server) | `orchestrator.py:139` | Usa `CachedEmbeddingProvider` (sentence-transformers local, 384d) |
| **Dedup: comparación invertida** | LanceDB devuelve L2 distance (0=idéntico) pero se comparaba como similarity (mayor=mejor) | `content_filter.py:93` | Cambiado `>= threshold` a `<= threshold` |
| **Sync All ignoraba force=true** | `sync_all()` respetaba intervalo de 60 min aunque `force=true` | `orchestrator.py` | Nueva ruta `_sync_all_forced()` sin intervalo |
| **Links se perdían al reconectar** | Sources agregados offline desaparecían al reiniciar backend | `SourcesView.tsx:tryBackend` | Push de local-only sources al backend al detectar conexión |
| **Chevron no expandía** | Clic en flechita no abría detalles del source | `SourcesView.tsx` | `setExpandedId` en el onClick del chevron |
| **Items indexed no se actualizaba** | Siempre 0 después del sync | `SourcesView.tsx` | Captura `result.indexed` del API |

---

## UI: Sources tab (left sidebar)

```
Left Sidebar:   Main panel:
┌─────┐         ┌─ Knowledge Sources ─────────────────── [● Connected] ─┐
│ 💬  │         │ [+ Add Link] [All|RSS|GitHub|Web]      [Sync]        │
│ 📡  │◄─active │                                                       │
│ 🔧  │         │ ┌─● Hacker News  RSS  ─────────────────── ↻ ✕ ⌄ ──┐ │
│ 💻  │         │ │  https://hnrss.org/frontpage                       │ │
└─────┘         │ │  Syncs: 1  ·  Last: 2h ago  ·  Indexed: 20      │ │
                │ └───────────────────────────────────────────────────┘ │
                │ ┌─● GitHub Blog  RSS  ────────────────── ↻ ✕ ⌄ ──┐ │
                │ │  https://github.blog/feed/                        │ │
                │ │  Syncs: 4  ·  Last: 1h ago  ·  Indexed: 32      │ │
                │ │  ── Expanded ───────────────────────────────     │ │
                │ │  URL: https://...  Interval: 60min               │ │
                │ │  Sync count: 4  Items indexed: 32  Added: 15m   │ │
                │ │  Last error: —                                   │ │
                │ └──────────────────────────────────────────────────┘ │
                └─────────────────────────────────────────────────────┘
```

### Funcionalidad offline

| Funcionalidad | Offline (backend down) | Online (backend up) |
|---------------|-----------------------|---------------------|
| Agregar links | ✅ localStorage | ✅ + push al backend |
| Eliminar links | ✅ localStorage + API | ✅ |
| Ver lista | ✅ desde caché localStorage | ✅ merge backend + local |
| Sync count | ✅ local | ✅ + items_indexed real |
| **Sync contenido** | ❌ Botón deshabilitado + tooltip | ✅ fetch → filter → chunk → index |
| Reconexión | — | Push automático de sources locales |

### Settings toggle

En Settings → Knowledge Sync → toggle Enable/Disable:

```
┌─ Knowledge Sync ──────────────────────┐
│  Enable Knowledge Sync      [══●══]   │
│  Enable to add RSS feeds, GitHub      │
│  repos, and web pages for automatic   │
│  knowledge sync.                      │
└───────────────────────────────────────┘
```

---

## Tests

```bash
make test tests/test_knowledge_sync.py   # 13 tests, ~1.2s
make test-stable                         # 154 tests (1 pre-existing fail en calendar)
```

| Test | Descripción |
|------|-------------|
| `test_rss_parse_sample` | Mock HTTP → 2 items RSS, verifica ETag |
| `test_rss_304_no_content` | HTTP 304 → 0 items |
| `test_github_fetch_file` | Mock GitHub API → README.md |
| `test_github_skip_binary` | .png/.exe → skip |
| `test_web_fetch_extract` | Mock trafilatura → texto limpio |
| `test_chunking_basic` | Chunking con overlap |
| `test_chunking_short_content` | < min_chunk → vacío |
| `test_filter_embedding_relevance` | Tags + embedding → solo relevantes pasan |
| `test_filter_dedup` | L2 distance ≤ 0.92 → skip |
| `test_state_store_save_load` | Persistencia JSON |
| `test_state_store_load_missing` | Source inexistente → idle |
| `test_orchestrator_ram_gate` | RAM < 0.3 GB → abort |
| `test_orchestrator_full_cycle` | Ciclo completo fetch→filter→chunk→upsert |

---

## Prueba rápida

```bash
# 1. Activar
curl -X PATCH http://localhost:7842/api/config \
  -H 'Content-Type: application/json' \
  -d '{"knowledge_sync": {"enabled": true}}'

# 2. Agregar feed
curl -X POST http://localhost:7842/api/knowledge-sync/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "rss:hn",
    "source_type": "rss",
    "uri": "https://hnrss.org/frontpage",
    "label": "Hacker News",
    "interval_minutes": 60
  }'

# 3. Sync forzado (salta RAM gate si > 0.3 GB libre)
curl -X POST http://localhost:7842/api/knowledge-sync/sync \
  -H 'Content-Type: application/json' \
  -d '{"force": true}'

# 4. Ver resultado
curl http://localhost:7842/api/knowledge-sync/sources
```
