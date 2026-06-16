# Knowledge Sync v2 — Plan de mejoras

> Basado en issues detectados post-implementación de Knowledge Sync Agent v1
> Fecha: 2026-06-14
> Última actualización: 2026-06-15
> Estado: ✅ Implementado (10/10 mejoras completadas)

---

## Tabla de Contenidos

- [1. Source-type específicos: arXiv, PubMed, YouTube](#1-source-type-específicos-arxiv-pubmed-youtube)
- [2. Bypass del llama server para embed de queries RAG](#2-bypass-del-llama-server-para-embed-de-queries-rag)
- [3. Activar SLM 0.5B para novelty scoring](#3-activar-slm-05b-para-novelty-scoring)
- [4. WebSockets/SSE para progreso de sync en frontend](#4-websocketssse-para-progreso-de-sync-en-frontend)
- [5. top_k configurable en ContextBuilder](#5-top_k-configurable-en-contextbuilder)
- [6. Dedup semántico menos agresivo](#6-dedup-semántico-menos-agresivo)
- [7. Programación horaria (cron-style)](#7-programación-horaria-cron-style)
- [8. Exportar/importar fuentes](#8-exportarimportar-fuentes)
- [9. Resumen de archivos a modificar/crear](#9-resumen-de-archivos-a-modificarcrear)

---

## 1. Source-type específicos: arXiv, PubMed, YouTube

### Problema

Los sources RSS genéricos traen descriptions cortas (HN, arXiv). El chunker con `min_chunk=15` ahora crea un documento incluso con contenido corto, pero la calidad del chunk es baja (solo el título + metadata, sin cuerpo del artículo).

### Solución propuesta

```
core/knowledge_sync/sources/
├── __init__.py
├── rss_source.py          ← existente, genérico
├── github_source.py       ← existente
├── web_source.py          ← existente
├── arxiv_source.py        ← NUEVO: parser específico arXiv API
├── youtube_source.py      ← NUEVO: transcript via yt-dlp o API
└── pubmed_source.py       ← NUEVO: parser PubMed API
```

Cada source especializado:
- **arXiv**: usa API `export.arxiv.org/api/query` en vez de RSS. Obtiene `summary` completo (varios párrafos), no solo el título.
  - ⚠️ **Límite de 30 páginas**: papers extremadamente largos (tesis, libros) deben truncarse para evitar que el sliding window genere miles de vectores saturando LanceDB.
- **YouTube**: obtiene transcript del video usando SOLO `youtube-transcript-api` (librería liviana que extrae subtítulos de texto plano ya generados por YouTube).
  - ❌ **NO usar `yt-dlp`, Whisper, o descarga de audio/video.** En M1 8GB, transcodificar audio con Whisper agota la RAM al instante y mata el proceso.
- **PubMed**: parsea abstracts completos vía EUtils API. Aplicar mismo límite de páginas que arXiv.

### Registro en `_SOURCE_BUILDERS`

En `orchestrator.py`, extender `_SOURCE_BUILDERS` con los nuevos `SourceType`:

```python
class SourceType(StrEnum):
    RSS = "rss"
    GITHUB = "github"
    WEB = "web"
    MANUAL = "manual"
    ARXIV = "arxiv"       # NUEVO
    YOUTUBE = "youtube"   # NUEVO
    PUBMED = "pubmed"     # NUEVO
```

### Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `core/knowledge_sync/sources/arxiv_source.py` | +120 líneas: fetch via arXiv API, parse summary |
| `core/knowledge_sync/sources/youtube_source.py` | +100 líneas: transcript via yt-dlp |
| `core/knowledge_sync/sources/pubmed_source.py` | +100 líneas: fetch via EUtils |

---

## 2. Bypass del llama server para embed de queries RAG

### Problema

`ContextBuilder.build()` usa `VectorStore.search(query, embed_engine)` donde `embed_engine` es `CachedEmbeddingProvider`. Pero `VectorStore.search()` llama a `engine.embed(query)` que funciona con el provider local. Esto ya está resuelto en v1, PERO:

Si el `CachedEmbeddingProvider` no está disponible (no se pasó a `ContextBuilder`), cae en `self._inference_engine` que intenta `POST /api/embeddings` al llama server. Sin embed server en `:8082`, falla silenciosamente.

### Solución propuesta

```
core/memory/
├── vector_store.py            ← MODIFICAR
│   └── search()               → aceptar embed callable opcional
│   └── search_by_vector()     → ya existe, no tocar
├── context_builder.py         ← MODIFICAR (ya hecho en v1 parcialmente)
```

**Cambios concretos:**

1. En `VectorStore.search()`, permitir pasar un `embed_fn` callable en vez de `engine`:
   ```python
   async def search(self, query, engine=None, top_k=5, embed_fn=None):
       if embed_fn:
           vector = await embed_fn(query)
       elif engine:
           vector = await engine.embed(query)
       else:
           raise ValueError("Need engine or embed_fn")
       return await self.search_by_vector(vector, top_k)
   ```

2. En `ContextBuilder.build()`, pasar `self._embed_provider.embed` como `embed_fn`.

3. En `RAGQueryEngine`, mismo cambio: usar `embed_fn` en vez de `engine.embed()`.

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `core/memory/vector_store.py` | `search()` acepta `embed_fn` opcional |
| `core/memory/context_builder.py` | Pasar `embed_fn` en vez de engine |
| `core/rag/query_engine.py` | Usar `embed_fn` para no depender de llama server |

---

## 3. Activar SLM 0.5B para novelty scoring

### Problema

El modelo `qwen2.5-0.5b-instruct-q5_k_m.gguf` (498MB) está descargado y el symlink existe, pero nunca se usa porque:
1. `_ensure_slm_engine` requiere ≥1.5 GB libres — en M1 8GB con LLM cargado, hay ~0.7GB
2. `ContentFilter.filter()` nunca recibe `is_manual_trigger=True` desde `sync_one`

### Solución propuesta

```
core/knowledge_sync/
├── content_filter.py      ← MODIFICAR
│   ├── _ensure_slm_engine()  → bajar RAM gate de 1.5 → 0.5 GB
│   └── filter()               → aceptar is_manual_trigger desde orchestrator
├── orchestrator.py        ← MODIFICAR
│   └── sync_one()             → pasar is_manual_trigger=True si force
```

**Detalles:**
- RAM gate del SLM: 1.5 GB → 0.5 GB (suficiente para un modelo 0.5B con ctx 2048)
- `sync_one()` recibe parámetro `force: bool = False`
- Si `force=True`, pasa `is_manual_trigger=True` al content filter
- _filter_novelty_slm() clasifica items como ALTA/MEDIA/BAJA novedad
- Items BAJA se descartan (no se indexan)

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `core/knowledge_sync/content_filter.py` | RAM gate 1.5→0.5, propagar `is_manual_trigger` |
| `core/knowledge_sync/orchestrator.py` | `sync_one()` acepta `force`, lo pasa al filter |

---

## 4. WebSockets/SSE para progreso de sync en frontend

### Problema

Cuando el usuario da Sync, el frontend no muestra progreso. Solo ve el resultado ~30s después (o nunca, si la conexión falla). La experiencia es "apreta botón, no pasa nada, espera, aparece resultado".

### Solución propuesta

```
BACKEND:
core/knowledge_sync/
├── orchestrator.py        ← MODIFICAR
│   └── sync_one()             → emitir eventos de progreso vía callback
├── router.py              ← MODIFICAR
│   └── POST /api/knowledge-sync/sync/stream  → SSE endpoint
```

**Flujo SSE:**
```
Cliente → POST /api/knowledge-sync/sync/stream {"force":true}
Servidor → event: progress\ndata: {"stage":"fetch","source":"Hacker News","count":20}\n\n
Servidor → event: progress\ndata: {"stage":"filter","passed":18,"filtered":2}\n\n
Servidor → event: progress\ndata: {"stage":"index","chunks":15}\n\n
Servidor → event: complete\ndata: {"source_id":"hnrss","indexed":15}\n\n
```

**Frontend:**
```
ui/tray/src/
├── components/settings/SourcesView.tsx  ← MODIFICAR
│   └── syncAll() / syncOne()              → usar EventSource para SSE
├── api/client.ts                        ← MODIFICAR
│   └── triggerSyncStream()               → nuevo endpoint SSE
```

**Arquitectura:**
- El `Orchestrator` expone un `ProgressCallback` type alias: `Callable[[str, dict], Awaitable[None]]`
- `sync_one()` acepta `progress_cb: ProgressCallback | None = None`
- En cada etapa (fetch → filter → chunk → upsert), llama a `progress_cb("stage_name", data)`
- El SSE endpoint envuelve `trigger_sync` con un callback que escribe al SSE stream

### Archivos a modificar/crear

| Archivo | Cambio |
|---------|--------|
| `core/knowledge_sync/orchestrator.py` | `ProgressCallback` type, emitir eventos |
| `core/knowledge_sync/router.py` | New SSE endpoint |
| `ui/tray/src/api/client.ts` | `triggerSyncStream()` |
| `ui/tray/src/components/settings/SourcesView.tsx` | Consumir SSE |

---

## 5. top_k configurable en ContextBuilder

### Problema

`top_k=5` fijo en `ContextBuilder.build()`. No hay manera de que el usuario o el agente pidan más o menos contexto documental.

### Solución propuesta

```
core/memory/
├── context_builder.py        ← MODIFICAR
│   └── __init__()               → aceptar top_k: int = 5
│   └── build()                  → usar self._top_k
├── agents/runtime.py         ← MODIFICAR
│   └── _context_assembly_node()→ pasar top_k según perfil del agente
```

**Configurable por agente** en `agent profiles`:
```yaml
# agent_profiles/general.yaml
rag_top_k: 5

# agent_profiles/thesis.yaml  
rag_top_k: 10   # más contexto para investigación
```

**Variable de entorno:**
```bash
CEREBRO_RAG_TOP_K=10
```

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `core/memory/context_builder.py` | `top_k` parameter en `__init__` y `build()` |
| `core/agents/runtime.py` | Leer `rag_top_k` del perfil del agente |
| `config/settings.toml` | Opcional: `[rag].top_k` |

---

## 6. Dedup semántico menos agresivo

### Problema

El threshold L2 ≤ 0.4 filtra artículos del mismo tema como "duplicados". Dos artículos de HN sobre "AI" tienen distancia L2 ~0.3-0.5 y el segundo se descarta incorrectamente.

### Solución propuesta

Dos opciones complementarias:

**Opción A — Subir threshold L2:** De 0.4 → 0.25 (solo filtrar contenido casi idéntico).

**Opción B — Dedup por URL exacta:** Antes del embedding, checkear si la URL ya está indexada en LanceDB via `get_indexed_files()`. Si la URL exacta ya existe con el mismo `file_modified`, skip. Si es URL diferente, indexar aunque el embedding sea similar.

```
core/knowledge_sync/
├── content_filter.py      ← MODIFICAR
│   └── _filter_dedup()       → check URL exacta primero
│                              → si URL no existe, pasar (no dedup por embedding)
│                              → si URL existe, check distancia L2 ≤ 0.25
```

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `core/knowledge_sync/content_filter.py` | Dedup lógico: URL exacta → embedding solo si misma URL |

---

## 7. Programación horaria (cron-style)

### Problema

Actualmente los sources tienen `interval_minutes` (cada N minutos). No hay manera de decir "sync cada día a las 3 AM" o "cada lunes".

### Solución propuesta

```
core/knowledge_sync/
├── models.py              ← MODIFICAR
│   └── SyncSourceConfig      → nuevo campo: schedule_cron: str = ""
├── orchestrator.py        ← MODIFICAR
│   └── sync_all()            → check cron además de intervalo
├── scheduler/
│   └── proactive.py       ← MODIFICAR
│       └── _knowledge_sync_tick() → evaluar cron expressions contra ahora
```

**Formato:** Cron estándar de 5 campos: `minuto hora día-del-mes mes día-de-la-semana`
```
# Todos los días a las 3 AM
schedule_cron = "0 3 * * *"

# Cada lunes a las 8 AM  
schedule_cron = "0 8 * * 1"
```

**Dependencia opcional:** `croniter` (parsear cron expressions, 0 dependencias extra pesadas).

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `core/knowledge_sync/models.py` | Campo `schedule_cron` en `SyncSourceConfig` |
| `core/knowledge_sync/orchestrator.py` | Lógica cron en `sync_all()` |
| `scheduler/proactive.py` | Evaluar cron en tick |
| `ui/tray/src/api/types.ts` | Campo `schedule_cron` en `SyncSource` |
| `ui/tray/src/components/settings/SourcesView.tsx` | Input cron en form |

---

## 8. Exportar/importar fuentes

### Problema

No hay manera de respaldar la configuración de fuentes o compartirla entre máquinas.

### Solución propuesta

```
core/knowledge_sync/
├── router.py              ← MODIFICAR
│   ├── GET /api/knowledge-sync/export  → JSON con todas las fuentes
│   └── POST /api/knowledge-sync/import → cargar fuentes desde JSON
```

**⚠️ Exportar SOLO configuración, NO estado de sync.** El JSON debe contener únicamente el blueprint de las fuentes (URLs, labels, tags). NO incluir ETags, `last_sync_at`, `items_indexed_count`, cachés de contenido, ni ningún estado transitorio. Esto permite:
- Restaurar fuentes después de limpiar la base de datos
- Compartir config entre máquinas sin arrastrar metadata de sync

**Formato JSON:**
```json
{
  "version": 1,
  "exported_at": "2026-06-14T23:00:00Z",
  "sources": [
    {
      "id": "rss:hn",
      "source_type": "rss",
      "uri": "https://hnrss.org/frontpage",
      "label": "Hacker News",
      "interval_minutes": 60,
      "tags": ["tech", "news"],
      "schedule_cron": ""
    }
  ]
}
```

**Frontend:**
```
ui/tray/src/
├── api/client.ts                   ← MODIFICAR
│   ├── exportSyncSources()          → GET /api/knowledge-sync/export
│   └── importSyncSources(file)      → POST /api/knowledge-sync/import
├── components/settings/SourcesView.tsx  ← MODIFICAR
│   └── Botón "Export" / "Import" en toolbar
```

### Archivos a modificar/crear

| Archivo | Cambio |
|---------|--------|
| `core/knowledge_sync/router.py` | Endpoints export/import |
| `ui/tray/src/api/client.ts` | Funciones export/import |
| `ui/tray/src/components/settings/SourcesView.tsx` | Botones en toolbar |

---

## 9. Resumen de archivos a modificar/crear

### Backend (Python)

| Archivo | Acción | Líneas estimadas |
|---------|--------|------------------|
| `core/knowledge_sync/models.py` | Modificar | +5 |
| `core/knowledge_sync/orchestrator.py` | Modificar | +60 |
| `core/knowledge_sync/content_filter.py` | Modificar | +20 |
| `core/knowledge_sync/router.py` | Modificar | +80 |
| `core/knowledge_sync/sources/arxiv_source.py` | **Crear** | +120 |
| `core/knowledge_sync/sources/youtube_source.py` | **Crear** | +100 |
| `core/knowledge_sync/sources/pubmed_source.py` | **Crear** | +100 |
| `core/memory/vector_store.py` | Modificar | +10 |
| `core/memory/context_builder.py` | Modificar | +15 |
| `core/rag/query_engine.py` | Modificar | +10 |
| `scheduler/proactive.py` | Modificar | +15 |

### Frontend (TypeScript/React)

| Archivo | Acción | Líneas estimadas |
|---------|--------|------------------|
| `ui/tray/src/api/client.ts` | Modificar | +40 |
| `ui/tray/src/api/types.ts` | Modificar | +10 |
| `ui/tray/src/components/settings/SourcesView.tsx` | Modificar | +80 |

### Total estimado: **~690 líneas**

---

## 10. Orden de implementación sugerido (3 bloques)

Para mantener los tests en verde y poder hacer merge parcial, implementar en este orden:

### Bloque 1 — Core & RAG (sin nuevos sources)

| Prioridad | Mejora | Depende de |
|-----------|--------|------------|
| 1 | **Bypass del llama server para embed** (sección 2) | Nada |
| 2 | **top_k configurable** (sección 5) | Bloque 1.1 |
| 3 | **Dedup por URL exacta** (sección 6) | Nada |
| 4 | **Activar SLM 0.5B** (sección 3) | Nada |

Tests que deben seguir pasando: `tests/test_knowledge_sync.py` (13 tests)

### Bloque 2 — Nuevos Sources

| Prioridad | Mejora | Depende de |
|-----------|--------|------------|
| 5 | **arXiv source** (sección 1) | Nada |
| 6 | **YouTube source** (sección 1) | Nada |
| 7 | **PubMed source** (sección 1) | Nada |

Tests que deben seguir pasando: tests del Bloque 1 + nuevos tests por source.

### Bloque 3 — UI & API

| Prioridad | Mejora | Depende de |
|-----------|--------|------------|
| 8 | **SSE para progreso** (sección 4) | Bloque 2 (para probar con sources reales) |
| 9 | **Programación cron** (sección 7) | Nada |
| 10 | **Export/Import fuentes** (sección 8) | Nada |

---

## 11. Resumen de implementación (2026-06-15)

Todas las 10 mejoras fueron implementadas. 25 tests pasan (13 knowledge_sync + 12 memory/rag).

### Cambios realizados

**Backend:**

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `core/memory/vector_store.py` | `search()` acepta `embed_fn` opcional | +15 |
| `core/memory/context_builder.py` | `top_k` en `__init__` y `build()`, `embed_fn` en vez de engine | +20 |
| `core/rag/query_engine.py` | `embed_fn` en `__init__`, pasado a `store.search()` | +8 |
| `core/knowledge_sync/models.py` | `SourceType.ARXIV/YOUTUBE/PUBMED`, `schedule_cron` | +8 |
| `core/knowledge_sync/orchestrator.py` | `ProgressCallback`, `sync_one(force)`, cron en `sync_all()`, nuevos sources en `_SOURCE_BUILDERS` | +70 |
| `core/knowledge_sync/content_filter.py` | RAM gate 1.5→0.5GB, dedup por URL exacta | +20 |
| `core/knowledge_sync/router.py` | SSE endpoint (`POST /sync/stream`), export (`GET /export`), import (`POST /import`) | +120 |
| `core/knowledge_sync/sources/arxiv_source.py` | Nuevo: arXiv API parser | +100 |
| `core/knowledge_sync/sources/youtube_source.py` | Nuevo: YouTube transcript (youtubetranscript.com API) | +85 |
| `core/knowledge_sync/sources/pubmed_source.py` | Nuevo: PubMed EUtils API parser | +130 |
| `core/agents/runtime.py` | Pasar `rag_top_k` desde perfil del agente | +2 |
| `config/settings.toml` | Sección `[rag]` con `top_k = 5` | +2 |

**Frontend (TypeScript/React):**

| Archivo | Cambio |
|---------|--------|
| `ui/tray/src/api/types.ts` | `schedule_cron`, `SyncProgressEvent`, `SyncExportPayload`, `SyncImportResponse`, nuevos source types |
| `ui/tray/src/api/client.ts` | `triggerSyncStream()`, `exportSyncSources()`, `importSyncSources()` |
| `ui/tray/src/components/settings/SourcesView.tsx` | Nuevos source types, campo cron, botones Export/Import, SSE streaming |

### Tests: `tests/test_knowledge_sync.py` — 13/13 passed
