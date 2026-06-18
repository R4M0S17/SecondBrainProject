# Knowledge Sync Agent — Sistema de Conocimiento Temporal para Cerebro2

## Presupuesto de RAM — La Restricción que lo Gobierna Todo

| Componente | RAM estimada |
|---|---|
| Qwen 3.5 2B (Q4_K_M) via llama.cpp | ~1.5 GB |
| Qwen 3.5 0.8B (Q4_K_M) via MLX | ~0.6 GB |
| macOS + sistema base | ~2.5 GB |
| LanceDB + VectorStore activo | ~150 MB |
| **Presupuesto libre para lo nuevo** | **~3.2 GB** |

---

## 1. Pipeline de Sincronización Online

La trampa clásica es construir un crawler genérico que llena tu disco con ruido. La solución es un **ingester orientado a señal, no a volumen**, que solo corre cuando hay red y el sistema está idle.

### Arquitectura: `KnowledgeSyncAgent`

Se enchufa como background worker independiente que `_build_app_state()` registra en el paso 7 junto al `LlamaServerHealthMonitor`.

```python
# core/knowledge/sync_agent.py

class KnowledgeSyncAgent:
    """Runs only when: network=True AND ram_free > 1.5GB AND idle > 5min"""

    def __init__(self, vector_store: VectorStore, ram_monitor: RamMonitor):
        self.store = vector_store
        self.ram = ram_monitor
        self.sources: list[KnowledgeSource] = []
        self._lock = asyncio.Lock()

    async def run_cycle(self):
        if not await self._should_run():
            return
        async with self._lock:  # solo un ciclo a la vez
            for source in self.sources:
                items = await source.fetch()
                filtered = self._filter_high_signal(items)
                await self._ingest_batch(filtered)

    async def _should_run(self) -> bool:
        return (
            self._has_network()
            and await self.ram.get_free_gb() > 1.5
            and self._idle_since_min() > 5
        )
```

### Filtro de 3 Capas (señal alta)

**Capa 1 — Filtro léxico** (~0ms): descarta items sin al menos 2 de tus `domain_tags` de los agentes (`academic-v1`, `code-v1`, etc.). Simple set intersection sobre tokens.

**Capa 2 — Deduplicación semántica** (~5ms con MiniLM): embeds el contenido con `LocalEmbeddingProvider` (MiniLM-L6, 384d, ya cargado en MPS). Busca en LanceDB con `top_k=1`. Si `cosine_similarity > 0.92` → ya existe, descarta.

**Capa 3 — Score de novedad temporal**: documentos donde el 60%+ de sus entidades (fechas, versiones, nombres) ya existen en LongTermStore con timestamps > 30 días reciben prioridad alta. Usa `spacy en_core_web_sm` (12MB) para extraer entidades.

### Fuentes Concretas (`KnowledgeSource`)

```python
class RSSSource(KnowledgeSource):
    """feedparser — 0 deps extra, async-friendly"""
    feeds = [
        "https://hnrss.org/frontpage",
        "https://arxiv.org/rss/cs.AI",
        "https://github.com/trending.atom",
    ]

class GitHubReleasesSource(KnowledgeSource):
    """Monitorea releases de repos en LongTermStore con tag='repo'"""
    # GitHub API (unauthenticated: 60 req/h)

class WebPageSource(KnowledgeSource):
    """Para URLs que el usuario marca como 'seguir'"""
    # httpx + readability-lxml para extraer texto principal
```

### Scheduleo

No uses `cron`. Conecta al `RamMonitor` en `core/observability/`. Cuando `ram_free > 2GB` durante 5 minutos seguidos → dispara un ciclo. Cuando el usuario interactúa activamente → pausa. Esto es un `asyncio.Event` que el `AgentRuntime` activa/desactiva.

---

## 2. Base de Conocimiento Local Ultra-Ligera

Tu VectorStore actual (LanceDB + MiniLM 384d) es casi exactamente lo correcto. El problema es que no está diferenciado del índice de archivos locales. Solución: **tabla separada** en el mismo LanceDB.

### `LiveKnowledgeStore`

```python
# core/knowledge/live_store.py
# Tabla LanceDB: "live_knowledge"
# Schema: (id, content, vector, source_url, published_at,
#           domain_tags, staleness_score, access_count, summary)

class LiveKnowledgeStore:
    TABLE = "live_knowledge"
    MAX_ENTRIES = 2000        # ~60MB en disco con 384d int8
    EVICTION_THRESHOLD = 1800
```

**Por qué 2000 entradas**: con chunks de ~300 tokens y vectores int8 de 384d, cada entrada ocupa ~1.5KB en disco y ~384 bytes en RAM (índice activo). 2000 entradas = ~750KB en RAM. Irrelevante.

**Cuantización int8**: LanceDB soporta nativo. Un cambio de línea: `pa.list_(pa.int8(), 384)`. Pierdes ~1% recall, ahorras 75% de memoria.

**Política de evicción** — score compuesto:
```
staleness_score = (days_old * 0.4) + (1/access_count * 0.4) + (domain_relevance_inv * 0.2)
```
Al llegar a 1800 entradas, evictas las 200 con score más alto. Preserva conocimiento consultado frecuentemente.

**Embedding model**: NO cambies de MiniLM-L6-v2. Ya corre en MPS (Neural Engine), ya integrado en `LocalEmbeddingProvider`. Opcional: `bge-small-en-v1.5` (misma API, drop-in replacement, mejor recall en inglés técnico).

---

## 3. Compresión de Contexto para 0.8B

El Qwen 0.8B con contexto de 6K+ hace que la latencia suba no linealmente. Objetivo: **≤ 2K tokens de contexto enriquecido** para respuesta en < 800ms.

### Pipeline de 3 Capas: `FreshContextCompressor`

Extiende tu `SemanticCompressor` actual con una rama específica para live knowledge.

**Capa A — Map**: comprimir cada chunk recuperado con el 0.8B mismo.

```python
async def _compress_chunk(self, chunk: str, query: str) -> str:
    prompt = f"Extract only facts directly relevant to: '{query}'\n\nText: {chunk}\n\nFacts:"
    return await self.mlx_provider.complete(prompt, max_tokens=80)
```

Costo: ~50ms por chunk. Chunk de 300 tokens → ~60 tokens.

**Capa B — Rank**: de `top_k=5` chunks comprimidos, ordenar por relevancia (dot product vectores vs query vector). Ya lo tienes en `RAGQueryEngine`. Sin LLM, pura álgebra lineal.

**Capa C — Inject**: tomar los 3 chunks más relevantes (~180 tokens total) y crear bloque `<fresh_context>` en system prompt. Presupuesto final:

```
System prompt base         : ~300 tokens
<fresh_context> (3 chunks) : ~200 tokens
Historial conversación     : ~400 tokens (últimos 4 turns)
Working memory             : ~100 tokens
─────────────────────────────────────────
Total context              : ~1000 tokens  ← seguro para 0.8B
```

**Resúmenes jerárquicos**: cuando un tema tiene >10 entradas (detectado por KMeans sobre vectores), consolidas las 10 en 1 "episodio síntesis". Misma lógica que `ShortTermStore.distill_if_needed()`.

---

## 4. Enrutador de Decisión: ¿Cuándo Activar el Conocimiento Fresco?

Añadir un **slot nuevo al inicio del FastPathRouter**: `FreshKnowledge → [resto del orden actual]`.

### `FreshKnowledgePathRouter`

```python
# core/agents/fast_path_router.py — extiende el orden canónico

class FreshKnowledgeSignals:
    """Heurísticas que NO requieren LLM — costo: <2ms"""

    TEMPORAL_MARKERS = {
        "latest", "recent", "current", "today", "now",
        "2024", "2025", "new", "update", "release",
        "version", "changed", "trending"
    }

    STALENESS_THRESHOLD_DAYS = 90

    @classmethod
    def score(cls, query: str) -> float:
        tokens = set(query.lower().split())
        temporal_hit = len(tokens & cls.TEMPORAL_MARKERS) / max(len(tokens), 1)
        return temporal_hit  # 0.0 a 1.0
```

**Lógica de 3 niveles**:

- **Nivel 1** — Score léxico ≥ 0.15: busca en `LiveKnowledgeStore` con `top_k=3`. Si `max_similarity ≥ 0.78` → activa contexto fresco, pasa al `reason_node` con bloque `<fresh_context>`. Costo: ~8ms.

- **Nivel 2** — Score < 0.15 pero query contiene entidad en `LiveKnowledgeStore` con `published_at < 7 días`: activa igual. Detección por dict lookup en memoria, sin NLP.

- **Nivel 3** — Ninguno: salta al flow normal. Cero overhead.

### Integración Exacta

En `AgentRuntime.run()` y `run_streaming()`, justo después de:
```python
fast_path_result = await self.fast_path.try_all(...)
```

Añadir:
```python
fresh_ctx = await self.fresh_router.try_enrich(query)
if fresh_ctx:
    initial_state["ambient_context"] = fresh_ctx.to_prompt_block()
```

El `ambient_context` ya fluye hacia `_build_system_prompt()`. No necesitas modificar el grafo LangGraph — solo el punto de inyección previo.

---

## Mapa de Archivos

```
core/
  knowledge/                    ← NUEVO módulo
    __init__.py
    sync_agent.py               # KnowledgeSyncAgent + Sources
    live_store.py               # LiveKnowledgeStore (LanceDB tabla nueva)
    fresh_compressor.py         # FreshContextCompressor (extiende SemanticCompressor)
    fresh_router.py             # FreshKnowledgePathRouter

  agents/
    fast_path_router.py         # MODIFICAR: FreshKnowledge al inicio del orden
    runtime.py                  # MODIFICAR: inyectar ambient_context desde fresh_router

  memory/
    vector_store.py             # MODIFICAR: soporte int8 vectors (1 línea)

main.py                         # MODIFICAR: wiring paso 7
config/settings.toml            # MODIFICAR: sección [knowledge]
```

No tocas el grafo LangGraph, no tocas el ProviderRegistry, no modificas el pipeline de 8 etapas. Todo se enchufa en puntos de extensión que ya existen: `ambient_context`, `SemanticCompressor`, y el orden del `FastPathRouter`.

---

## Advertencia

El bottleneck real no es RAM — es la latencia de embeddings durante sync. `MiniLM-L6` en MPS del M1 procesa ~200 chunks/segundo. Para 50 artículos nuevos de RSS (~10 chunks c/u), el sync cycle completo toma ~2.5 segundos de GPU, aceptable si corre idle en background. **No hagas embeddings síncronos durante una query activa** — por eso el `asyncio.Lock` y el check de actividad son no-negociables.
