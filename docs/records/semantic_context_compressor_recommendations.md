# Semantic Context Compressor — Recomendaciones

## Estado actual
- **24/24 tests pasando** (pytest automatizados)
- Path B (TF-IDF): ✅ producción-ready, ~2-3ms, 0.23MB pico
- Path A (Neural): ✅ código correcto, probado con httpx mock, pero requiere servidor llama.cpp con `--embeddings`
- **No está activo** en el pipeline de producción (`main.py` no lo instancia)

## Recomendaciones

### 1. Activar en producción
El compressor está implementado, testeado, y el `RAGQueryEngine` acepta un `compressor` opcional. Solo falta instanciarlo en `main.py`:

```python
from core.utils.compressor import SemanticCompressor
rag_engine = RAGQueryEngine(store=store, engine=engine,
    compressor=SemanticCompressor(embed_fn=None))  # TF-IDF por defecto
```

### 2. Usar Path B (TF-IDF) como default
TF-IDF no necesita llama.cpp, es rápido (~2-3ms), memoria baja (~0.23MB), y funciona con cualquier backend. Recomendado para activación inmediata.

### 3. Path A (Neural) solo con servidor embedding dedicado
Para Path A se necesita un servidor llama.cpp con `--embeddings --pooling mean`. Mejor usar un puerto separado (8082) para no mezclar con el servidor chat. El embedding del mismo modelo chat es lento bajo presión de memoria (~18s por call).

### 4. Arreglar deprecation warning (prioridad baja)
`core/utils/compressor.py:105` usa `asyncio.iscoroutinefunction()` deprecado en Python 3.14, se elimina en 3.16. Cambiar a `inspect.iscoroutinefunction()`.

### 5. max_tokens=600 es agresivo
Para queries complejas o muchos chunks, considerar subir a 800-1000 tokens. El valor actual funciona bien para 3-5 chunks de ~6 oraciones cada uno.

### 6. Monitorear compression ratio
El test muestra reducción promedio >65% con TF-IDF. Si cae debajo de 30%, revisar thresholds de filtrado (especialmente Phase B: `mean_score * 0.5`).

### 7. Frontend no muestra "compressed" badge
`AssembledContext.documents_compressed` existe pero nunca se setea a `True`. El frontend podría mostrar un badge "Compressed ⚡" en SourcesPanel cuando esté activo.
