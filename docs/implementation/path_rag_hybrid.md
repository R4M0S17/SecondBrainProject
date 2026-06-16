# Path de Implementacion: RAG Hibrido (Web + Local + Sincronizacion en Rafaga)

> **Blueprint tecnico para Cerebro2 — MacBook Pro M1 8GB RAM**
> Fecha: 2026-06-07
> Estado: Pendiente de ejecucion

---

## Tabla de Contenidos

- [0. Principios Rectores y Restricciones](#0-principios-rectores-y-restricciones)
- [1. Fase 0 — Candado Matematico (test-stable como red de seguridad)](#1-fase-0--candado-matematico)
- [2. Fase 1 — Modulo de Deteccion de Conectividad](#2-fase-1--modulo-de-deteccion-de-conectividad)
- [3. Fase 2 — Web-RAG (Escenario Con Internet)](#3-fase-2--web-rag-escenario-con-internet)
- [4. Fase 3 — Local-RAG (Escenario Sin Internet)](#4-fase-3--local-rag-escenario-sin-internet)
- [5. Fase 4 — Sincronizacion en Rafaga (Escenario Hibrido)](#5-fase-4--sincronizacion-en-rafaga)
- [6. Fase 5 — Integracion en AgentRuntime.run() con Feature Flag](#6-fase-5--integracion-en-agentruntimerun-con-feature-flag)
- [7. Fase 6 — Pruebas de Integracion y Degradacion Elegante](#7-fase-6--pruebas-de-integracion-y-degradacion-elegante)
- [8. Resumen de Archivos Nuevos y Modificados](#8-resumen-de-archivos-nuevos-y-modificados)

---

## 0. Principios Rectores y Restricciones

### 0.1 HardWARE LIMITS (8GB RAM — Cero Swap)

| Recurso | Budget Maximo | Estrategia |
|---|---|---|
| RAM para embeddings locales | ~120 MB | `all-MiniLM-L6-v2` via `LocalEmbeddingProvider` (384 dims, ya integrado) |
| RAM para inferencia chat | ~1.5 GB | Qwen 3.5 2B Q4_K_M.gguf via llama.cpp (ya configurado) |
| RAM para DB vectorial | ~50-200 MB | LanceDB en disco, mmap (ya integrado) |
| RAM para web scraping | ~30 MB | `httpx` + `selectolax` (parser ligero, sin BeautifulSoup) |
| RAM total nueva estimada | ~200-350 MB | Margen seguro dentro de 8GB |

### 0.2 Decisiones Tecnicas Fundamentales

| Decision | Eleccion | Justificacion |
|---|---|---|
| **Modelo de Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Ya integrado en `LocalEmbeddingProvider` (`core/inference/providers/local_embedding_provider.py:14`). 384 dims, ~80MB en disco, ~120MB en RAM. No cargar nada nuevo. |
| **Base de Datos Vectorial** | LanceDB (existente) | Ya integrado en `core/memory/vector_store.py`. Zero dependencias nuevas. Mmap en disco. |
| **Web Search API** | DuckDuckGo Instant Answer API | Gratuita, sin API key, respuesta JSON ligera. Fallback: `duckduckgo-search` package. |
| **HTML Parser** | `selectolax` | ~5x mas rapido que BeautifulSoup, menor footprint de RAM. |
| **Feature Flag** | Variable de entorno `CEREBRO_RAG_MODE` | Valores: `local` \| `web` \| `hybrid` \| `off` (default: `off`). Coherente con el patron existente (`CEREBRO_INFERENCE_BACKEND`, `CEREBRO_MLX_ENABLED`). |
| **Punto de Integracion** | `ContextBuilder.build()` + nuevo `RAGStrategy` | No tocar `AgentRuntime.run()` fast paths. Inyectar contexto RAG antes del prompt. |

### 0.3 Arquitectura de Integracion (No-Invasiva)

```
                    ┌─────────────────────────────────────┐
                    │        AgentRuntime.run()            │
                    │  (fast paths INTACTOS — cero riesgo) │
                    └──────────────┬──────────────────────┘
                                   │ (si ningun fast path aplica)
                                   ▼
                    ┌─────────────────────────────────────┐
                    │     ContextBuilder.build()           │
                    │  + RAGContextInjector (NUEVO)        │
                    │    ├─ WebRAG (si hay red)            │
                    │    ├─ LocalRAG (si no hay red)       │
                    │    └─ HybridRAG (snapshot cache)     │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │   System Prompt con contexto RAG     │
                    │   → LlamaCppChatProvider.complete()  │
                    └─────────────────────────────────────┘
```

**Regla de oro**: Los fast paths en `FastPathRouter.try_all()` (`core/agents/fast_path_router.py:58-76`) NO se modifican. El RAG se inyecta como contexto adicional en `ContextBuilder`, igual que `LongTermStore` ya lo hace.

---

## 1. Fase 0 — Candado Matematico

> **Objetivo**: Validar que `make test-stable` pasa al 100% ANTES de tocar cualquier codigo. Este es nuestro candado de regresion.

### 1.1 Verificar estado actual de tests estables

- [ ] Ejecutar el suite completo de tests estables y capturar baseline:
  ```bash
  make test-stable 2>&1 | tee docs/implementation/baseline_test_stable.txt
  ```
- [ ] Verificar que el resultado sea `X passed, 0 failed` (documentar el numero exacto).
- [ ] Ejecutar el suite general para capturar baseline completo:
  ```bash
  python -m pytest tests/ -v --tb=short -m "not live" 2>&1 | tee docs/implementation/baseline_test_full.txt
  ```

### 1.2 Crear script de verificacion rapida de candado

- [ ] Crear archivo `scripts/check_stable_lock.sh`:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  echo "=== Candado Matematico: test-stable ==="
  python -m pytest tests/test_stable_fast_paths.py \
    tests/test_file_write_fast_path.py \
    tests/test_file_write_calendar_fusion.py \
    tests/test_calendar_fast_path.py \
    tests/test_file_search_fast_path.py \
    tests/test_math_fast_path.py \
    -v -m "not live" --tb=short -q
  echo "=== Candado OK — cero regresiones ==="
  ```
- [ ] Hacer ejecutable:
  ```bash
  chmod +x scripts/check_stable_lock.sh
  ```
- [ ] Ejecutar y verificar:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

### 1.3 Regla de ejecucion obligatoria

> **CONTRATO**: Antes de cada commit durante toda la implementacion, ejecutar `./scripts/check_stable_lock.sh`. Si falla un solo test, REVERTIR los cambios antes de continuar.

- [ ] Documentar esta regla en `AGENTS.md` (seccion nueva "RAG Hybrid Development Rules"):
  ```markdown
  ## RAG Hybrid Development Rules
  - Before ANY commit during RAG hybrid implementation, run: ./scripts/check_stable_lock.sh
  - If any test fails, REVERT before proceeding.
  - New RAG tests go in tests/test_web_rag.py, tests/test_local_rag.py, tests/test_hybrid_rag.py
  - RAG tests MUST NOT require llama.cpp or network (use mocks).
  ```

---

## 2. Fase 1 — Modulo de Deteccion de Conectividad

> **Objetivo**: Crear un modulo que determine si hay internet disponible, con cache de estado y timeout corto. Este modulo sera usado por Web-RAG y Hybrid-RAG.

### 2.1 Tests primero (TDD)

- [ ] Crear archivo `tests/test_connectivity.py`:
  ```python
  """Tests for core/net/connectivity.py — deterministic, no real network."""

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, patch

  from core.net.connectivity import ConnectivityChecker, NetworkState


  class TestConnectivityChecker:
      """Unit tests for ConnectivityChecker."""

      @pytest.mark.asyncio
      async def test_check_online_when_reachable(self):
          checker = ConnectivityChecker()
          with patch.object(checker, "_probe", new_callable=AsyncMock, return_value=True):
              state = await checker.check()
          assert state == NetworkState.ONLINE
          assert checker.is_online is True

      @pytest.mark.asyncio
      async def test_check_offline_when_unreachable(self):
          checker = ConnectivityChecker()
          with patch.object(checker, "_probe", new_callable=AsyncMock, return_value=False):
              state = await checker.check()
          assert state == NetworkState.OFFLINE
          assert checker.is_online is False

      @pytest.mark.asyncio
      async def test_cached_result_within_ttl(self):
          checker = ConnectivityChecker(cache_ttl_seconds=60.0)
          with patch.object(checker, "_probe", new_callable=AsyncMock, return_value=True) as mock_probe:
              await checker.check()
              await checker.check()
              mock_probe.assert_called_once()  # second call uses cache

      @pytest.mark.asyncio
      async def test_cache_expired_after_ttl(self):
          checker = ConnectivityChecker(cache_ttl_seconds=0.0)
          with patch.object(checker, "_probe", new_callable=AsyncMock, return_value=True) as mock_probe:
              await checker.check()
              await checker.check()
              assert mock_probe.call_count == 2

      @pytest.mark.asyncio
      async def test_force_offline_mode(self):
          checker = ConnectivityChecker()
          checker.force_offline()
          assert checker.is_online is False
          state = await checker.check()
          assert state == NetworkState.FORCED_OFFLINE

      @pytest.mark.asyncio
      async def test_probe_timeout_is_short(self):
          """Probe must timeout in <=2s to avoid blocking queries."""
          checker = ConnectivityChecker(probe_timeout_seconds=0.5)
          # Simulate a slow probe
          async def slow_probe(*args, **kwargs):
              import asyncio
              await asyncio.sleep(10)
              return True
          with patch("httpx.AsyncClient.get", side_effect=slow_probe):
              result = await checker._probe()
          assert result is False
  ```

- [ ] Ejecutar tests (deben FALLAR — TDD):
  ```bash
  python -m pytest tests/test_connectivity.py -v --tb=short
  ```

### 2.2 Implementar modulo de conectividad

- [ ] Crear directorio:
  ```bash
  mkdir -p core/net
  ```
- [ ] Crear archivo `core/net/__init__.py`:
  ```python
  """Network utilities for Cerebro RAG hybrid mode."""
  ```
- [ ] Crear archivo `core/net/connectivity.py`:
  ```python
  """Lightweight connectivity checker with TTL cache.

  Uses a HEAD request to a well-known endpoint (Cloudflare DNS over HTTPS)
  to minimize latency and avoid DNS resolution issues.
  """

  from __future__ import annotations

  import asyncio
  import enum
  import time

  import httpx
  from loguru import logger

  _PROBE_URL = "https://1.1.1.1/dns-query"
  _PROBE_HEADERS = {"Accept": "application/dns-message"}


  class NetworkState(enum.Enum):
      ONLINE = "online"
      OFFLINE = "offline"
      FORCED_OFFLINE = "forced_offline"
      UNKNOWN = "unknown"


  class ConnectivityChecker:
      def __init__(
          self,
          *,
          probe_timeout_seconds: float = 1.5,
          cache_ttl_seconds: float = 30.0,
      ) -> None:
          self._probe_timeout = probe_timeout_seconds
          self._cache_ttl = cache_ttl_seconds
          self._cached_state: NetworkState = NetworkState.UNKNOWN
          self._cached_at: float = 0.0
          self._forced_offline: bool = False

      @property
      def is_online(self) -> bool:
          return self._cached_state == NetworkState.ONLINE

      def force_offline(self) -> None:
          self._forced_offline = True
          self._cached_state = NetworkState.FORCED_OFFLINE
          self._cached_at = time.monotonic()

      def force_online(self) -> None:
          self._forced_offline = False
          self._cached_at = 0.0  # invalidate cache

      async def check(self) -> NetworkState:
          if self._forced_offline:
              return NetworkState.FORCED_OFFLINE
          now = time.monotonic()
          if (now - self._cached_at) < self._cache_ttl:
              return self._cached_state
          reachable = await self._probe()
          self._cached_state = NetworkState.ONLINE if reachable else NetworkState.OFFLINE
          self._cached_at = now
          if reachable:
              logger.debug("Connectivity: ONLINE")
          else:
              logger.debug("Connectivity: OFFLINE")
          return self._cached_state

      async def _probe(self) -> bool:
          try:
              async with httpx.AsyncClient(timeout=httpx.Timeout(self._probe_timeout)) as client:
                  resp = await client.get(
                      _PROBE_URL,
                      headers=_PROBE_HEADERS,
                      follow_redirects=False,
                  )
                  return resp.status_code < 500
          except Exception:
              return False
  ```

- [ ] Ejecutar tests (deben PASAR):
  ```bash
  python -m pytest tests/test_connectivity.py -v
  ```
- [ ] Ejecutar candado (debe seguir pasando):
  ```bash
  ./scripts/check_stable_lock.sh
  ```

---

## 3. Fase 2 — Web-RAG (Escenario Con Internet)

> **Objetivo**: Cuando hay internet, interceptar la query del usuario, buscar en la web (DuckDuckGo), limpiar resultados a texto plano (max 3-4), e inyectar como contexto en el prompt del sistema.

### 3.1 Instalar dependencias nuevas

- [ ] Agregar a `pyproject.toml` en `[project.dependencies]`:
  ```toml
  "duckduckgo-search>=6.0",
  "selectolax>=0.3",
  ```
- [ ] Instalar:
  ```bash
  pip install duckduckgo-search selectolax
  ```

### 3.2 Tests primero (TDD)

- [ ] Crear archivo `tests/test_web_rag.py`:
  ```python
  """Tests for core/rag/web_rag.py — all network calls mocked."""

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from core.rag.web_rag import WebRAGEngine, WebSearchResult, WebRAGConfig


  class TestWebSearchResult:
      def test_truncate_body_to_max_chars(self):
          result = WebSearchResult(
              title="Test",
              url="https://example.com",
              body="x" * 5000,
              score=0.9,
          )
          truncated = result.with_truncated_body(max_chars=500)
          assert len(truncated.body) <= 500

      def test_to_context_snippet(self):
          result = WebSearchResult(
              title="BTC Price",
              url="https://example.com/btc",
              body="Bitcoin is trading at $67,000.",
              score=0.95,
          )
          snippet = result.to_context_snippet()
          assert "BTC Price" in snippet
          assert "example.com" in snippet
          assert "67,000" in snippet


  class TestWebRAGEngine:
      @pytest.mark.asyncio
      async def test_search_returns_results(self):
          config = WebRAGConfig(max_results=3, max_body_chars=800)
          engine = WebRAGEngine(config=config)
          mock_results = [
              WebSearchResult(title="R1", url="https://a.com", body="Body 1", score=0.9),
              WebSearchResult(title="R2", url="https://b.com", body="Body 2", score=0.8),
          ]
          with patch.object(engine, "_fetch_search_results", new_callable=AsyncMock, return_value=mock_results):
              results = await engine.search("bitcoin price")
          assert len(results) == 2
          assert results[0].title == "R1"

      @pytest.mark.asyncio
      async def test_search_limits_to_max_results(self):
          config = WebRAGConfig(max_results=2)
          engine = WebRAGEngine(config=config)
          mock_results = [
              WebSearchResult(title=f"R{i}", url=f"https://{i}.com", body=f"Body {i}", score=0.9 - i * 0.1)
              for i in range(5)
          ]
          with patch.object(engine, "_fetch_search_results", new_callable=AsyncMock, return_value=mock_results):
              results = await engine.search("test query")
          assert len(results) == 2

      @pytest.mark.asyncio
      async def test_build_context_block(self):
          config = WebRAGConfig(max_results=3, max_body_chars=500)
          engine = WebRAGEngine(config=config)
          results = [
              WebSearchResult(title="BTC", url="https://a.com", body="Price is $67K", score=0.9),
              WebSearchResult(title="ETH", url="https://b.com", body="Price is $3.5K", score=0.8),
          ]
          context = engine.build_context_block(results)
          assert "BTC" in context
          assert "ETH" in context
          assert "FUENTE WEB" in context

      @pytest.mark.asyncio
      async def test_search_handles_network_error_gracefully(self):
          config = WebRAGConfig(max_results=3)
          engine = WebRAGEngine(config=config)
          with patch.object(engine, "_fetch_search_results", new_callable=AsyncMock, side_effect=Exception("No network")):
              results = await engine.search("test")
          assert results == []

      @pytest.mark.asyncio
      async def test_fetch_and_clean_page(self):
          engine = WebRAGEngine()
          mock_html = "<html><body><p>Hello world</p><script>evil()</script></body></html>"
          with patch("httpx.AsyncClient.get") as mock_get:
              mock_resp = MagicMock()
              mock_resp.status_code = 200
              mock_resp.text = mock_html
              mock_get.return_value = mock_resp
              text = await engine._fetch_and_clean_page("https://example.com")
          assert "Hello world" in text
          assert "evil" not in text

      @pytest.mark.asyncio
      async def test_context_block_respects_token_budget(self):
          config = WebRAGConfig(max_results=4, max_body_chars=2000, context_char_budget=1500)
          engine = WebRAGEngine(config=config)
          results = [
              WebSearchResult(title=f"T{i}", url=f"https://{i}.com", body="x" * 500, score=0.9 - i * 0.1)
              for i in range(4)
          ]
          context = engine.build_context_block(results)
          assert len(context) <= 1500 + 200  # small tolerance for headers
  ```

- [ ] Ejecutar tests (deben FALLAR — TDD):
  ```bash
  python -m pytest tests/test_web_rag.py -v --tb=short
  ```

### 3.3 Implementar WebRAGEngine

- [ ] Crear archivo `core/rag/web_rag.py`:
  ```python
  """Web-RAG: search the web and inject results into the LLM context.

  Uses DuckDuckGo Instant Answer API (free, no key required).
  Falls back to duckduckgo-search package for richer results.
  HTML cleaning via selectolax (fast, low-memory).
  """

  from __future__ import annotations

  import asyncio
  from dataclasses import dataclass, field

  import httpx
  from loguru import logger

  _REQUEST_TIMEOUT = 8.0
  _PAGE_FETCH_TIMEOUT = 5.0
  _USER_AGENT = "Cerebro/2.0 (Local AI Assistant)"


  @dataclass
  class WebRAGConfig:
      max_results: int = 3
      max_body_chars: int = 800
      context_char_budget: int = 3000
      fetch_page_body: bool = True
      enabled: bool = True


  @dataclass
  class WebSearchResult:
      title: str
      url: str
      body: str
      score: float = 0.0

      def with_truncated_body(self, max_chars: int) -> WebSearchResult:
          if len(self.body) <= max_chars:
              return self
          return WebSearchResult(
              title=self.title,
              url=self.url,
              body=self.body[:max_chars].rsplit(" ", 1)[0] + "...",
              score=self.score,
          )

      def to_context_snippet(self) -> str:
          return f"[{self.title}]({self.url})\n{self.body}"


  class WebRAGEngine:
      def __init__(self, config: WebRAGConfig | None = None) -> None:
          self._config = config or WebRAGConfig()

      async def search(self, query: str) -> list[WebSearchResult]:
          if not self._config.enabled:
              return []
          try:
              raw = await self._fetch_search_results(query)
              truncated = [r.with_truncated_body(self._config.max_body_chars) for r in raw]
              return truncated[: self._config.max_results]
          except Exception as exc:
              logger.warning("WebRAG search failed: {}", exc)
              return []

      async def _fetch_search_results(self, query: str) -> list[WebSearchResult]:
          try:
              from duckduckgo_search import DDGS

              loop = asyncio.get_event_loop()
              results = await loop.run_in_executor(None, self._ddg_sync, query)
              return results
          except ImportError:
              logger.warning("duckduckgo-search not installed, using fallback")
              return await self._ddg_fallback(query)

      def _ddg_sync(self, query: str) -> list[WebSearchResult]:
          from duckduckgo_search import DDGS

          results: list[WebSearchResult] = []
          with DDGS() as ddgs:
              for r in ddgs.text(query, max_results=self._config.max_results * 2):
                  results.append(
                      WebSearchResult(
                          title=r.get("title", ""),
                          url=r.get("href", ""),
                          body=r.get("body", ""),
                          score=1.0,
                      )
                  )
          return results

      async def _ddg_fallback(self, query: str) -> list[WebSearchResult]:
          async with httpx.AsyncClient(timeout=httpx.Timeout(_REQUEST_TIMEOUT)) as client:
              resp = await client.get(
                  "https://api.duckduckgo.com/",
                  params={"q": query, "format": "json", "no_html": "1"},
                  headers={"User-Agent": _USER_AGENT},
              )
              resp.raise_for_status()
              data = resp.json()
          results: list[WebSearchResult] = []
          if data.get("Abstract"):
              results.append(
                  WebSearchResult(
                      title=data.get("Heading", ""),
                      url=data.get("AbstractURL", ""),
                      body=data["Abstract"],
                      score=1.0,
                  )
              )
          for r in data.get("RelatedTopics", [])[: self._config.max_results]:
              if isinstance(r, dict) and "Text" in r:
                  results.append(
                      WebSearchResult(
                          title=r.get("Text", "")[:80],
                          url=r.get("FirstURL", ""),
                          body=r.get("Text", ""),
                          score=0.5,
                      )
                  )
          return results

      async def _fetch_and_clean_page(self, url: str) -> str:
          try:
              async with httpx.AsyncClient(timeout=httpx.Timeout(_PAGE_FETCH_TIMEOUT)) as client:
                  resp = await client.get(
                      url,
                      headers={"User-Agent": _USER_AGENT},
                      follow_redirects=True,
                  )
                  if resp.status_code != 200:
                      return ""
                  html = resp.text
          except Exception as exc:
              logger.debug("Page fetch failed for {}: {}", url, exc)
              return ""
          return self._clean_html(html)

      @staticmethod
      def _clean_html(html: str) -> str:
          try:
              from selectolax.parser import HTMLParser

              tree = HTMLParser(html)
              for tag in tree.css("script, style, nav, header, footer, iframe"):
                  tag.decompose()
              text = tree.text(separator=" ", strip=True)
              lines = [line.strip() for line in text.splitlines() if line.strip()]
              return " ".join(lines)
          except ImportError:
              import re

              text = re.sub(r"<[^>]+>", " ", html)
              text = re.sub(r"\s+", " ", text).strip()
              return text

      def build_context_block(self, results: list[WebSearchResult]) -> str:
          if not results:
              return ""
          snippets: list[str] = []
          total_chars = 0
          for r in results:
              snippet = r.to_context_snippet()
              if total_chars + len(snippet) > self._config.context_char_budget:
                  remaining = self._config.context_char_budget - total_chars
                  if remaining > 100:
                      snippets.append(snippet[:remaining] + "...")
                  break
              snippets.append(snippet)
              total_chars += len(snippet)
          header = "--- FUENTE WEB (resultados en tiempo real) ---\n"
          return header + "\n\n".join(snippets)
  ```

- [ ] Ejecutar tests (deben PASAR):
  ```bash
  python -m pytest tests/test_web_rag.py -v
  ```
- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

---

## 4. Fase 3 — Local-RAG (Escenario Sin Internet)

> **Objetivo**: Cuando no hay internet, usar la DB vectorial LanceDB existente + `LocalEmbeddingProvider` (all-MiniLM-L6-v2) para buscar fragmentos relevantes en disco e inyectarlos al prompt.

### 4.1 Analisis de infraestructura existente

El proyecto YA tiene:
- `VectorStore` (LanceDB) en `core/memory/vector_store.py` — con `search()` y `upsert()`.
- `LocalEmbeddingProvider` en `core/inference/providers/local_embedding_provider.py` — 384 dims, ~120MB RAM.
- `RAGQueryEngine` en `core/rag/query_engine.py` — busca en VectorStore y genera respuesta.
- `LongTermStore` en `core/memory/long_term.py` — busqueda con filtros por agente, tags, fecha.
- Pipeline de ingestion en `core/ingestion/pipeline.py` — parse PDF/DOCX, chunk, embed, insert.

**Lo que falta**: Un `LocalRAGEngine` dedicado que:
1. Use solo `LocalEmbeddingProvider` (no dependa de llama.cpp embed server).
2. Tenga un pool de documentos "siempre disponibles" (cotizaciones, docs de referencia).
3. Libere el modelo de embeddings despues de usar si la RAM esta critica.

### 4.2 Tests primero (TDD)

- [ ] Crear archivo `tests/test_local_rag.py`:
  ```python
  """Tests for core/rag/local_rag.py — all vector operations mocked."""

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from core.rag.local_rag import LocalRAGEngine, LocalRAGConfig, LocalRAGChunk


  class TestLocalRAGConfig:
      def test_defaults(self):
          config = LocalRAGConfig()
          assert config.top_k == 5
          assert config.min_score == 0.3
          assert config.max_context_chars == 3000

      def test_custom_values(self):
          config = LocalRAGConfig(top_k=3, min_score=0.5, max_context_chars=2000)
          assert config.top_k == 3


  class TestLocalRAGChunk:
      def test_to_context_snippet(self):
          chunk = LocalRAGChunk(
              content="Bitcoin price is $67,000",
              source="snapshot_2026_06_07.json",
              score=0.92,
          )
          snippet = chunk.to_context_snippet()
          assert "Bitcoin" in snippet
          assert "snapshot_2026" in snippet


  class TestLocalRAGEngine:
      @pytest.mark.asyncio
      async def test_search_returns_chunks(self):
          engine = LocalRAGEngine(config=LocalRAGConfig())
          mock_store = MagicMock()
          mock_store.search = AsyncMock(return_value=[
              MagicMock(content="BTC $67K", source_path="snap.json", score=0.9),
          ])
          mock_embed = MagicMock()
          mock_embed.embed = AsyncMock(return_value=[0.1] * 384)
          engine._vector_store = mock_store
          engine._embed_provider = mock_embed
          chunks = await engine.search("bitcoin price")
          assert len(chunks) == 1
          assert chunks[0].content == "BTC $67K"

      @pytest.mark.asyncio
      async def test_search_filters_by_min_score(self):
          config = LocalRAGConfig(min_score=0.5)
          engine = LocalRAGEngine(config=config)
          mock_store = MagicMock()
          mock_store.search = AsyncMock(return_value=[
              MagicMock(content="High score", source_path="a.json", score=0.9),
              MagicMock(content="Low score", source_path="b.json", score=0.2),
          ])
          mock_embed = MagicMock()
          mock_embed.embed = AsyncMock(return_value=[0.1] * 384)
          engine._vector_store = mock_store
          engine._embed_provider = mock_embed
          chunks = await engine.search("test")
          assert len(chunks) == 1
          assert chunks[0].content == "High score"

      @pytest.mark.asyncio
      async def test_build_context_block(self):
          engine = LocalRAGEngine()
          chunks = [
              LocalRAGChunk(content="Data point 1", source="src1.json", score=0.9),
              LocalRAGChunk(content="Data point 2", source="src2.json", score=0.8),
          ]
          context = engine.build_context_block(chunks)
          assert "Data point 1" in context
          assert "Data point 2" in context
          assert "MEMORIA LOCAL" in context

      @pytest.mark.asyncio
      async def test_search_handles_empty_store(self):
          engine = LocalRAGEngine()
          mock_store = MagicMock()
          mock_store.search = AsyncMock(return_value=[])
          mock_embed = MagicMock()
          mock_embed.embed = AsyncMock(return_value=[0.1] * 384)
          engine._vector_store = mock_store
          engine._embed_provider = mock_embed
          chunks = await engine.search("nonexistent topic")
          assert chunks == []

      @pytest.mark.asyncio
      async def test_context_block_respects_budget(self):
          config = LocalRAGConfig(max_context_chars=500)
          engine = LocalRAGEngine(config=config)
          chunks = [
              LocalRAGChunk(content="x" * 300, source="a.json", score=0.9),
              LocalRAGChunk(content="y" * 300, source="b.json", score=0.8),
          ]
          context = engine.build_context_block(chunks)
          assert len(context) <= 500 + 200  # tolerance for headers

      @pytest.mark.asyncio
      async def test_ingest_snapshot(self):
          engine = LocalRAGEngine()
          mock_store = MagicMock()
          mock_store.upsert = AsyncMock(return_value=5)
          mock_embed = MagicMock()
          engine._vector_store = mock_store
          engine._embed_provider = mock_embed
          count = await engine.ingest_snapshot(
              source_path="snapshot.json",
              chunks=["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
          )
          assert count == 5
  ```

- [ ] Ejecutar tests (deben FALLAR — TDD):
  ```bash
  python -m pytest tests/test_local_rag.py -v --tb=short
  ```

### 4.3 Implementar LocalRAGEngine

- [ ] Crear archivo `core/rag/local_rag.py`:
  ```python
  """Local-RAG: offline vector search using existing LanceDB + MiniLM embeddings.

  Reuses the project's VectorStore and LocalEmbeddingProvider infrastructure.
  Adds snapshot ingestion for hybrid sync mode.
  """

  from __future__ import annotations

  from dataclasses import dataclass

  from loguru import logger

  from core.ingestion.pipeline import Document
  from core.inference.registry import EmbeddingProvider
  from core.memory.vector_store import VectorStore


  @dataclass
  class LocalRAGConfig:
      top_k: int = 5
      min_score: float = 0.3
      max_context_chars: int = 3000


  @dataclass
  class LocalRAGChunk:
      content: str
      source: str
      score: float

      def to_context_snippet(self) -> str:
          return f"[{self.source}] (relevance: {self.score:.2f})\n{self.content}"


  class LocalRAGEngine:
      def __init__(
          self,
          config: LocalRAGConfig | None = None,
          vector_store: VectorStore | None = None,
          embed_provider: EmbeddingProvider | None = None,
      ) -> None:
          self._config = config or LocalRAGConfig()
          self._vector_store = vector_store
          self._embed_provider = embed_provider

      async def search(self, query: str) -> list[LocalRAGChunk]:
          if not self._vector_store or not self._embed_provider:
              logger.debug("LocalRAG: no vector store or embed provider configured")
              return []
          try:
              results = await self._vector_store.search(
                  query=query,
                  engine=self._embed_provider,
                  top_k=self._config.top_k,
              )
          except Exception as exc:
              logger.warning("LocalRAG search failed: {}", exc)
              return []
          chunks: list[LocalRAGChunk] = []
          for r in results:
              score = 1.0 - (r.score or 0.0) if r.score else 0.0
              if score < self._config.min_score:
                  continue
              chunks.append(
                  LocalRAGChunk(
                      content=r.content,
                      source=r.source_path or "unknown",
                      score=score,
                  )
              )
          return chunks

      def build_context_block(self, chunks: list[LocalRAGChunk]) -> str:
          if not chunks:
              return ""
          snippets: list[str] = []
          total_chars = 0
          for chunk in chunks:
              snippet = chunk.to_context_snippet()
              if total_chars + len(snippet) > self._config.max_context_chars:
                  remaining = self._config.max_context_chars - total_chars
                  if remaining > 100:
                      snippets.append(snippet[:remaining] + "...")
                  break
              snippets.append(snippet)
              total_chars += len(snippet)
          header = "--- MEMORIA LOCAL (datos cacheados en disco) ---\n"
          return header + "\n\n".join(snippets)

      async def ingest_snapshot(
          self,
          source_path: str,
          chunks: list[str],
          metadata: dict | None = None,
      ) -> int:
          if not self._vector_store or not self._embed_provider:
              logger.warning("LocalRAG: cannot ingest — no store/embed configured")
              return 0
          documents: list[Document] = []
          for i, chunk_text in enumerate(chunks):
              documents.append(
                  Document(
                      id=f"{source_path}__chunk_{i}",
                      content=chunk_text,
                      source_path=source_path,
                      chunk_index=i,
                      metadata=metadata or {},
                  )
              )
          count = await self._vector_store.upsert(
              documents=documents,
              engine=self._embed_provider,
          )
          logger.info("LocalRAG: ingested {} chunks from {}", count, source_path)
          return count
  ```

- [ ] Ejecutar tests (deben PASAR):
  ```bash
  python -m pytest tests/test_local_rag.py -v
  ```
- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

---

## 5. Fase 4 — Sincronizacion en Rafaga (Escenario Hibrido)

> **Objetivo**: Worker en segundo plano que monitorea la conexion. Al detectar internet, descarga snapshots (JSON con datos actualizados), los vectoriza y los anexa a la DB local. Si la red se corta, el sistema lee de la DB local sincronizada (degradacion elegante).

### 5.1 Tests primero (TDD)

- [ ] Crear archivo `tests/test_hybrid_rag.py`:
  ```python
  """Tests for core/rag/hybrid_sync.py — all I/O mocked."""

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from core.rag.hybrid_sync import (
      HybridSyncWorker,
      SnapshotSource,
      SnapshotRecord,
      SyncConfig,
      SyncState,
  )


  class TestSyncConfig:
      def test_defaults(self):
          config = SyncConfig()
          assert config.check_interval_seconds == 300
          assert config.max_snapshots_per_source == 10
          assert config.enabled is True

      def test_disabled(self):
          config = SyncConfig(enabled=False)
          assert config.enabled is False


  class TestSnapshotSource:
      def test_from_dict(self):
          source = SnapshotSource(
              name="crypto_prices",
              url="https://api.example.com/prices",
              parser="json",
              refresh_minutes=60,
          )
          assert source.name == "crypto_prices"
          assert source.refresh_minutes == 60


  class TestSnapshotRecord:
      def test_to_chunks(self):
          record = SnapshotRecord(
              source="crypto",
              fetched_at=1717000000.0,
              data={"btc": 67000, "eth": 3500},
          )
          chunks = record.to_chunks()
          assert len(chunks) >= 1
          assert any("67000" in c for c in chunks)


  class TestHybridSyncWorker:
      @pytest.mark.asyncio
      async def test_check_and_sync_when_online(self):
          worker = HybridSyncWorker(config=SyncConfig())
          mock_connectivity = MagicMock()
          mock_connectivity.check = AsyncMock(return_value=MagicMock(value="online"))
          mock_connectivity.is_online = True
          mock_local_rag = MagicMock()
          mock_local_rag.ingest_snapshot = AsyncMock(return_value=3)
          worker._connectivity = mock_connectivity
          worker._local_rag = mock_local_rag
          worker._sources = [
              SnapshotSource(name="test", url="https://api.test.com", parser="json", refresh_minutes=60)
          ]
          with patch.object(worker, "_fetch_snapshot", new_callable=AsyncMock) as mock_fetch:
              mock_fetch.return_value = SnapshotRecord(
                  source="test", fetched_at=1717000000.0, data={"key": "value"}
              )
              state = await worker.check_and_sync()
          assert state == SyncState.SYNCED

      @pytest.mark.asyncio
      async def test_check_and_sync_when_offline(self):
          worker = HybridSyncWorker(config=SyncConfig())
          mock_connectivity = MagicMock()
          mock_connectivity.check = AsyncMock(return_value=MagicMock(value="offline"))
          mock_connectivity.is_online = False
          worker._connectivity = mock_connectivity
          state = await worker.check_and_sync()
          assert state == SyncState.OFFLINE_USING_CACHE

      @pytest.mark.asyncio
      async def test_fetch_snapshot_parses_json(self):
          worker = HybridSyncWorker()
          mock_response = MagicMock()
          mock_response.status_code = 200
          mock_response.json.return_value = {"btc": 67000, "eth": 3500}
          with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
              record = await worker._fetch_snapshot(
                  SnapshotSource(name="crypto", url="https://api.test.com", parser="json", refresh_minutes=60)
              )
          assert record is not None
          assert record.data["btc"] == 67000

      @pytest.mark.asyncio
      async def test_fetch_snapshot_handles_error(self):
          worker = HybridSyncWorker()
          with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("timeout")):
              record = await worker._fetch_snapshot(
                  SnapshotSource(name="test", url="https://api.test.com", parser="json", refresh_minutes=60)
              )
          assert record is None

      @pytest.mark.asyncio
      async def test_snapshot_record_to_chunks(self):
          record = SnapshotRecord(
              source="prices",
              fetched_at=1717000000.0,
              data={"btc": 67000, "eth": 3500, "sol": 150},
          )
          chunks = record.to_chunks()
          assert len(chunks) >= 1
          full_text = " ".join(chunks)
          assert "67000" in full_text

      @pytest.mark.asyncio
      async def test_is_source_stale(self):
          import time
          worker = HybridSyncWorker()
          source = SnapshotSource(name="test", url="https://x.com", parser="json", refresh_minutes=60)
          worker._last_sync = {"test": time.time() - 7200}  # 2 hours ago
          assert worker._is_source_stale(source) is True
          worker._last_sync = {"test": time.time() - 60}  # 1 minute ago
          assert worker._is_source_stale(source) is False

      @pytest.mark.asyncio
      async def test_sync_state_transitions(self):
          assert SyncState.SYNCED.value == "synced"
          assert SyncState.OFFLINE_USING_CACHE.value == "offline_using_cache"
          assert SyncState.SYNC_FAILED.value == "sync_failed"
  ```

- [ ] Ejecutar tests (deben FALLAR — TDD):
  ```bash
  python -m pytest tests/test_hybrid_rag.py -v --tb=short
  ```

### 5.2 Implementar HybridSyncWorker

- [ ] Crear archivo `core/rag/hybrid_sync.py`:
  ```python
  """Hybrid sync: background worker that fetches snapshots when online,
  vectorizes them, and stores in local LanceDB for offline access.

  Graceful degradation: when network drops, LocalRAG reads from the
  last synced snapshot data in the vector store.
  """

  from __future__ import annotations

  import asyncio
  import enum
  import json
  import time
  from dataclasses import dataclass, field

  import httpx
  from loguru import logger


  class SyncState(enum.Enum):
      SYNCED = "synced"
      OFFLINE_USING_CACHE = "offline_using_cache"
      SYNC_FAILED = "sync_failed"
      DISABLED = "disabled"


  @dataclass
  class SyncConfig:
      check_interval_seconds: int = 300
      max_snapshots_per_source: int = 10
      fetch_timeout_seconds: float = 10.0
      enabled: bool = True


  @dataclass
  class SnapshotSource:
      name: str
      url: str
      parser: str  # "json" | "text"
      refresh_minutes: int = 60
      headers: dict[str, str] = field(default_factory=dict)


  @dataclass
  class SnapshotRecord:
      source: str
      fetched_at: float
      data: dict | list | str

      def to_chunks(self) -> list[str]:
          if isinstance(self.data, str):
              return [self.data]
          if isinstance(self.data, list):
              return [json.dumps(item, ensure_ascii=False) for item in self.data]
          if isinstance(self.data, dict):
              chunks: list[str] = []
              for key, value in self.data.items():
                  chunks.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
              return chunks
          return [str(self.data)]


  class HybridSyncWorker:
      def __init__(
          self,
          config: SyncConfig | None = None,
          sources: list[SnapshotSource] | None = None,
          connectivity=None,
          local_rag=None,
      ) -> None:
          self._config = config or SyncConfig()
          self._sources = sources or []
          self._connectivity = connectivity
          self._local_rag = local_rag
          self._last_sync: dict[str, float] = {}
          self._running = False
          self._task: asyncio.Task | None = None

      @property
      def state(self) -> SyncState:
          if not self._config.enabled:
              return SyncState.DISABLED
          if self._connectivity and not self._connectivity.is_online:
              return SyncState.OFFLINE_USING_CACHE
          return SyncState.SYNCED

      async def check_and_sync(self) -> SyncState:
          if not self._config.enabled:
              return SyncState.DISABLED
          if self._connectivity:
              net_state = await self._connectivity.check()
              if not self._connectivity.is_online:
                  logger.debug("HybridSync: offline, using cached snapshots")
                  return SyncState.OFFLINE_USING_CACHE
          synced_any = False
          for source in self._sources:
              if not self._is_source_stale(source):
                  continue
              record = await self._fetch_snapshot(source)
              if record is None:
                  continue
              if self._local_rag:
                  chunks = record.to_chunks()
                  source_path = f"snapshot__{source.name}__{int(record.fetched_at)}.json"
                  await self._local_rag.ingest_snapshot(
                      source_path=source_path,
                      chunks=chunks,
                      metadata={"source": source.name, "fetched_at": record.fetched_at},
                  )
              self._last_sync[source.name] = time.time()
              synced_any = True
          return SyncState.SYNCED if synced_any else SyncState.OFFLINE_USING_CACHE

      def _is_source_stale(self, source: SnapshotSource) -> bool:
          last = self._last_sync.get(source.name, 0.0)
          return (time.time() - last) > (source.refresh_minutes * 60)

      async def _fetch_snapshot(self, source: SnapshotSource) -> SnapshotRecord | None:
          try:
              async with httpx.AsyncClient(timeout=httpx.Timeout(self._config.fetch_timeout_seconds)) as client:
                  resp = await client.get(source.url, headers=source.headers or {})
                  if resp.status_code != 200:
                      logger.warning("Snapshot fetch failed: {} -> {}", source.url, resp.status_code)
                      return None
                  if source.parser == "json":
                      data = resp.json()
                  else:
                      data = resp.text
              return SnapshotRecord(
                  source=source.name,
                  fetched_at=time.time(),
                  data=data,
              )
          except Exception as exc:
              logger.warning("Snapshot fetch error for {}: {}", source.name, exc)
              return None

      async def start_periodic(self) -> None:
          if self._running:
              return
          self._running = True
          self._task = asyncio.create_task(self._periodic_loop())
          logger.info("HybridSync: started periodic sync (every {}s)", self._config.check_interval_seconds)

      async def stop(self) -> None:
          self._running = False
          if self._task:
              self._task.cancel()
              try:
                  await self._task
              except asyncio.CancelledError:
                  pass
          logger.info("HybridSync: stopped")

      async def _periodic_loop(self) -> None:
          while self._running:
              try:
                  await self.check_and_sync()
              except Exception as exc:
                  logger.warning("HybridSync periodic error: {}", exc)
              await asyncio.sleep(self._config.check_interval_seconds)
  ```

- [ ] Ejecutar tests (deben PASAR):
  ```bash
  python -m pytest tests/test_hybrid_rag.py -v
  ```
- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

### 5.3 Configurar fuentes de snapshot por defecto

- [ ] Crear archivo `config/snapshot_sources.json`:
  ```json
  [
    {
      "name": "crypto_prices",
      "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
      "parser": "json",
      "refresh_minutes": 30,
      "headers": {}
    },
    {
      "name": "exchange_rates",
      "url": "https://open.er-api.com/v6/latest/USD",
      "parser": "json",
      "refresh_minutes": 120,
      "headers": {}
    }
  ]
  ```

---

## 6. Fase 5 — Integracion en AgentRuntime.run() con Feature Flag

> **Objetivo**: Conectar los tres escenarios RAG al flujo principal SIN tocar los fast paths. Usar `ContextBuilder` como punto de inyeccion y `CEREBRO_RAG_MODE` como feature flag.

### 6.1 Crear RAGStrategy (patrón Strategy)

- [ ] Crear archivo `core/rag/strategy.py`:
  ```python
  """RAG Strategy pattern: selects Web, Local, or Hybrid RAG based on
  connectivity state and feature flag configuration.
  """

  from __future__ import annotations

  import enum
  import os

  from loguru import logger


  class RAGMode(enum.Enum):
      OFF = "off"
      WEB = "web"
      LOCAL = "local"
      HYBRID = "hybrid"


  def get_rag_mode() -> RAGMode:
      raw = os.getenv("CEREBRO_RAG_MODE", "off").strip().lower()
      try:
          return RAGMode(raw)
      except ValueError:
          logger.warning("Unknown CEREBRO_RAG_MODE={!r}, falling back to 'off'", raw)
          return RAGMode.OFF
  ```

### 6.2 Crear RAGContextInjector (puente entre RAG y ContextBuilder)

- [ ] Crear archivo `core/rag/context_injector.py`:
  ```python
  """RAGContextInjector: bridges RAG engines with ContextBuilder.

  Called during context assembly (before prompt building) to inject
  web or local RAG context into the system prompt.
  """

  from __future__ import annotations

  from loguru import logger

  from core.net.connectivity import ConnectivityChecker
  from core.rag.local_rag import LocalRAGEngine
  from core.rag.strategy import RAGMode, get_rag_mode
  from core.rag.web_rag import WebRAGEngine


  class RAGContextInjector:
      def __init__(
          self,
          web_engine: WebRAGEngine | None = None,
          local_engine: LocalRAGEngine | None = None,
          connectivity: ConnectivityChecker | None = None,
          mode: RAGMode | None = None,
      ) -> None:
          self._web = web_engine
          self._local = local_engine
          self._connectivity = connectivity
          self._mode = mode or get_rag_mode()

      @property
      def mode(self) -> RAGMode:
          return self._mode

      @property
      def is_enabled(self) -> bool:
          return self._mode != RAGMode.OFF

      async def inject(self, query: str) -> str:
          if not self.is_enabled:
              return ""

          if self._mode == RAGMode.WEB:
              return await self._web_inject(query)

          if self._mode == RAGMode.LOCAL:
              return await self._local_inject(query)

          if self._mode == RAGMode.HYBRID:
              return await self._hybrid_inject(query)

          return ""

      async def _web_inject(self, query: str) -> str:
          if not self._web:
              return ""
          results = await self._web.search(query)
          context = self._web.build_context_block(results)
          if context:
              logger.debug("WebRAG injected {} chars of context", len(context))
          return context

      async def _local_inject(self, query: str) -> str:
          if not self._local:
              return ""
          chunks = await self._local.search(query)
          context = self._local.build_context_block(chunks)
          if context:
              logger.debug("LocalRAG injected {} chars of context", len(context))
          return context

      async def _hybrid_inject(self, query: str) -> str:
          if self._connectivity:
              net_state = await self._connectivity.check()
              if self._connectivity.is_online:
                  context = await self._web_inject(query)
                  if context:
                      return context
                  logger.debug("HybridRAG: web returned empty, falling back to local")
              else:
                  logger.debug("HybridRAG: offline, using local cache")
          context = await self._local_inject(query)
          return context
  ```

### 6.3 Tests para RAGContextInjector

- [ ] Crear archivo `tests/test_rag_context_injector.py`:
  ```python
  """Tests for core/rag/context_injector.py — all engines mocked."""

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, MagicMock

  from core.rag.context_injector import RAGContextInjector
  from core.rag.strategy import RAGMode
  from core.rag.web_rag import WebSearchResult


  class TestRAGContextInjector:
      @pytest.mark.asyncio
      async def test_inject_returns_empty_when_off(self):
          injector = RAGContextInjector(mode=RAGMode.OFF)
          result = await injector.inject("test query")
          assert result == ""

      @pytest.mark.asyncio
      async def test_inject_web_mode(self):
          mock_web = MagicMock()
          mock_web.search = AsyncMock(return_value=[
              WebSearchResult(title="Test", url="https://x.com", body="Data", score=0.9),
          ])
          mock_web.build_context_block.return_value = "--- FUENTE WEB ---\nTest"
          injector = RAGContextInjector(web_engine=mock_web, mode=RAGMode.WEB)
          result = await injector.inject("test query")
          assert "FUENTE WEB" in result

      @pytest.mark.asyncio
      async def test_inject_local_mode(self):
          mock_local = MagicMock()
          mock_local.search = AsyncMock(return_value=[])
          mock_local.build_context_block.return_value = ""
          injector = RAGContextInjector(local_engine=mock_local, mode=RAGMode.LOCAL)
          result = await injector.inject("test query")
          assert result == ""

      @pytest.mark.asyncio
      async def test_inject_hybrid_online(self):
          mock_web = MagicMock()
          mock_web.search = AsyncMock(return_value=[
              WebSearchResult(title="Live", url="https://x.com", body="Live data", score=0.9),
          ])
          mock_web.build_context_block.return_value = "--- FUENTE WEB ---\nLive"
          mock_local = MagicMock()
          mock_conn = MagicMock()
          mock_conn.check = AsyncMock()
          mock_conn.is_online = True
          injector = RAGContextInjector(
              web_engine=mock_web,
              local_engine=mock_local,
              connectivity=mock_conn,
              mode=RAGMode.HYBRID,
          )
          result = await injector.inject("test")
          assert "FUENTE WEB" in result
          mock_local.search.assert_not_called()

      @pytest.mark.asyncio
      async def test_inject_hybrid_offline_falls_back_to_local(self):
          mock_web = MagicMock()
          mock_local = MagicMock()
          mock_local.search = AsyncMock(return_value=[])
          mock_local.build_context_block.return_value = "--- MEMORIA LOCAL ---\nCached"
          mock_conn = MagicMock()
          mock_conn.check = AsyncMock()
          mock_conn.is_online = False
          injector = RAGContextInjector(
              web_engine=mock_web,
              local_engine=mock_local,
              connectivity=mock_conn,
              mode=RAGMode.HYBRID,
          )
          result = await injector.inject("test")
          assert "MEMORIA LOCAL" in result
          mock_web.search.assert_not_called()

      @pytest.mark.asyncio
      async def test_inject_hybrid_online_but_web_empty_falls_to_local(self):
          mock_web = MagicMock()
          mock_web.search = AsyncMock(return_value=[])
          mock_web.build_context_block.return_value = ""
          mock_local = MagicMock()
          mock_local.search = AsyncMock(return_value=[])
          mock_local.build_context_block.return_value = "--- MEMORIA LOCAL ---\nFallback"
          mock_conn = MagicMock()
          mock_conn.check = AsyncMock()
          mock_conn.is_online = True
          injector = RAGContextInjector(
              web_engine=mock_web,
              local_engine=mock_local,
              connectivity=mock_conn,
              mode=RAGMode.HYBRID,
          )
          result = await injector.inject("obscure query")
          assert "MEMORIA LOCAL" in result

      def test_is_enabled(self):
          assert RAGContextInjector(mode=RAGMode.OFF).is_enabled is False
          assert RAGContextInjector(mode=RAGMode.WEB).is_enabled is True
          assert RAGContextInjector(mode=RAGMode.LOCAL).is_enabled is True
          assert RAGContextInjector(mode=RAGMode.HYBRID).is_enabled is True
  ```

- [ ] Ejecutar tests (deben PASAR):
  ```bash
  python -m pytest tests/test_rag_context_injector.py -v
  ```
- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

### 6.4 Integrar RAGContextInjector en ContextBuilder

> **Punto exacto de modificacion**: `core/memory/context_builder.py`, metodo `build()`.
> No se modifica `AgentRuntime.run()` ni `FastPathRouter`.

- [ ] Modificar `core/memory/context_builder.py` — agregar parametro opcional `rag_injector` al constructor:
  ```python
  # En __init__, agregar:
  def __init__(
      self,
      short_term: ShortTermStore,
      long_term: LongTermStore,
      token_budget: int = DEFAULT_TOKEN_BUDGET,
      rag_injector: RAGContextInjector | None = None,  # NUEVO
  ) -> None:
      self._short_term = short_term
      self._long_term = long_term
      self._token_budget = token_budget
      self._rag_injector = rag_injector  # NUEVO
  ```

- [ ] Modificar `ContextBuilder.build()` — llamar al inyector RAG despues de recuperar memoria:
  ```python
  # Dentro de build(), despues de recuperar retrieved_memory:
  rag_context = ""
  if self._rag_injector and self._rag_injector.is_enabled:
      try:
          rag_context = await self._rag_injector.inject(query)
      except Exception as exc:
          logger.warning("RAG injection failed (graceful degradation): {}", exc)
          rag_context = ""
  ```

- [ ] Modificar `AssembledContext` — agregar campo `rag_context`:
  ```python
  @dataclass
  class AssembledContext:
      session_history: list[Message]
      retrieved_memory: list[MemoryChunk]
      retrieved_documents: list[SearchResult]
      agent_summary: str
      total_tokens_estimated: int
      sources_used: list[str]
      documents_compressed: bool = False
      rag_context: str = ""  # NUEVO
  ```

- [ ] Modificar `_build_system_prompt()` en `core/agents/runtime.py` — inyectar `rag_context` en el template:
  ```python
  # Agregar al template _SYSTEM_TEMPLATE, despues de {ambient_context}:
  # {rag_context}
  # Y en _build_system_prompt(), pasar:
  # rag_context=context.rag_context or ""
  ```

- [ ] Agregar tests de integracion en `tests/test_rag_context_injector.py`:
  ```python
  class TestContextBuilderRAGIntegration:
      @pytest.mark.asyncio
      async def test_build_includes_rag_context(self):
          mock_short = MagicMock()
          mock_short.get_context.return_value = MagicMock(
              active_messages=[], last_tool_results=None,
              current_instructions="", temporal_goals=None,
          )
          mock_long = MagicMock()
          mock_long.search = AsyncMock(return_value=[])
          mock_rag = MagicMock()
          mock_rag.is_enabled = True
          mock_rag.inject = AsyncMock(return_value="--- FUENTE WEB ---\nBTC $67K")
          builder = ContextBuilder(
              short_term=mock_short,
              long_term=mock_long,
              rag_injector=mock_rag,
          )
          mock_agent_state = MagicMock()
          mock_agent_state.profile.preferences = {"instructions": ""}
          mock_agent_state.working_memory = {}
          mock_agent_state.session_summary = ""
          ctx = await builder.build("bitcoin price", mock_agent_state)
          assert "FUENTE WEB" in ctx.rag_context

      @pytest.mark.asyncio
      async def test_build_handles_rag_failure_gracefully(self):
          mock_short = MagicMock()
          mock_short.get_context.return_value = MagicMock(
              active_messages=[], last_tool_results=None,
              current_instructions="", temporal_goals=None,
          )
          mock_long = MagicMock()
          mock_long.search = AsyncMock(return_value=[])
          mock_rag = MagicMock()
          mock_rag.is_enabled = True
          mock_rag.inject = AsyncMock(side_effect=Exception("network error"))
          builder = ContextBuilder(
              short_term=mock_short,
              long_term=mock_long,
              rag_injector=mock_rag,
          )
          mock_agent_state = MagicMock()
          mock_agent_state.profile.preferences = {"instructions": ""}
          mock_agent_state.working_memory = {}
          mock_agent_state.session_summary = ""
          ctx = await builder.build("test", mock_agent_state)
          assert ctx.rag_context == ""
  ```

- [ ] Ejecutar todos los tests nuevos:
  ```bash
  python -m pytest tests/test_rag_context_injector.py tests/test_web_rag.py tests/test_local_rag.py tests/test_hybrid_rag.py tests/test_connectivity.py -v
  ```
- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

### 6.5 Wiring en main.py

- [ ] Modificar `main.py` — agregar import y creacion de componentes RAG en `_build_app_state()`:
  ```python
  # Despues de la creacion de rag_engine (linea ~277):
  from core.net.connectivity import ConnectivityChecker
  from core.rag.strategy import get_rag_mode
  from core.rag.web_rag import WebRAGEngine, WebRAGConfig
  from core.rag.local_rag import LocalRAGEngine, LocalRAGConfig
  from core.rag.context_injector import RAGContextInjector
  from core.rag.hybrid_sync import HybridSyncWorker, SyncConfig, SnapshotSource

  rag_mode = get_rag_mode()
  connectivity = ConnectivityChecker()

  web_rag = None
  local_rag = None
  rag_injector = None
  sync_worker = None

  if rag_mode != RAGMode.OFF:
      web_rag = WebRAGEngine(WebRAGConfig(max_results=3, max_body_chars=800))
      local_rag = LocalRAGEngine(
          config=LocalRAGConfig(top_k=5, min_score=0.3),
          vector_store=vector_store,
          embed_provider=embed,
      )
      rag_injector = RAGContextInjector(
          web_engine=web_rag,
          local_engine=local_rag,
          connectivity=connectivity,
          mode=rag_mode,
      )
      if rag_mode == RAGMode.HYBRID:
          import json
          snapshot_path = os.path.join(os.path.dirname(__file__), "config", "snapshot_sources.json")
          sources: list[SnapshotSource] = []
          if os.path.exists(snapshot_path):
              with open(snapshot_path) as f:
                  for s in json.load(f):
                      sources.append(SnapshotSource(**s))
          sync_worker = HybridSyncWorker(
              config=SyncConfig(),
              sources=sources,
              connectivity=connectivity,
              local_rag=local_rag,
          )
      logger.info("RAG mode: {}", rag_mode.value)
  ```

- [ ] Modificar la creacion de `ContextBuilder` en `main.py` para pasar `rag_injector`:
  ```python
  # Cambiar de:
  context_builder = ContextBuilder(short_term=short_term, long_term=long_term)
  # A:
  context_builder = ContextBuilder(
      short_term=short_term,
      long_term=long_term,
      rag_injector=rag_injector,
  )
  ```

- [ ] Agregar `sync_worker` a `app_state` y arrancarlo si aplica:
  ```python
  app_state.rag_injector = rag_injector
  app_state.hybrid_sync = sync_worker

  if sync_worker:
      asyncio.create_task(sync_worker.start_periodic())
  ```

- [ ] Ejecutar candado:
  ```bash
  ./scripts/check_stable_lock.sh
  ```

### 6.6 Actualizar settings.toml

- [ ] Agregar seccion `[rag]` a `config/settings.toml`:
  ```toml
  [rag]
  mode = "off"  # off | web | local | hybrid
  web_max_results = 3
  web_max_body_chars = 800
  web_context_budget = 3000
  local_top_k = 5
  local_min_score = 0.3
  local_max_context_chars = 3000
  sync_interval_seconds = 300
  ```

### 6.7 Actualizar AppState

- [ ] Agregar campos a `AppState` en `ui/tray/server.py`:
  ```python
  rag_injector: RAGContextInjector | None = None
  hybrid_sync: HybridSyncWorker | None = None
  connectivity: ConnectivityChecker | None = None
  ```

---

## 7. Fase 6 — Pruebas de Integracion y Degradacion Elegante

> **Objetivo**: Validar el flujo completo con tests de integracion que simulen los tres escenarios y la degradacion.

### 7.1 Tests de integracion end-to-end (mockeando LLM)

- [ ] Crear archivo `tests/test_rag_integration.py`:
  ```python
  """Integration tests for the full RAG hybrid pipeline.

  These tests mock the LLM provider and network but exercise the real
  ContextBuilder → RAGContextInjector → Engine flow.
  """

  from __future__ import annotations

  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from core.memory.context_builder import ContextBuilder, AssembledContext
  from core.rag.context_injector import RAGContextInjector
  from core.rag.strategy import RAGMode
  from core.rag.web_rag import WebRAGEngine, WebSearchResult
  from core.rag.local_rag import LocalRAGEngine, LocalRAGChunk


  class TestFullRAGPipeline:
      @pytest.mark.asyncio
      async def test_web_rag_end_to_end(self):
          mock_web = MagicMock(spec=WebRAGEngine)
          mock_web.search = AsyncMock(return_value=[
              WebSearchResult(title="BTC", url="https://x.com", body="$67,000", score=0.95),
          ])
          mock_web.build_context_block.return_value = (
              "--- FUENTE WEB (resultados en tiempo real) ---\n"
              "[BTC](https://x.com)\n$67,000"
          )
          injector = RAGContextInjector(web_engine=mock_web, mode=RAGMode.WEB)
          context = await injector.inject("cual es el precio de bitcoin")
          assert "67,000" in context
          assert "FUENTE WEB" in context

      @pytest.mark.asyncio
      async def test_local_rag_end_to_end(self):
          mock_local = MagicMock(spec=LocalRAGEngine)
          mock_local.search = AsyncMock(return_value=[
              LocalRAGChunk(content="BTC $67K cached", source="snap.json", score=0.88),
          ])
          mock_local.build_context_block.return_value = (
              "--- MEMORIA LOCAL (datos cacheados en disco) ---\n"
              "[snap.json] (relevance: 0.88)\nBTC $67K cached"
          )
          injector = RAGContextInjector(local_engine=mock_local, mode=RAGMode.LOCAL)
          context = await injector.inject("bitcoin price")
          assert "67K" in context

      @pytest.mark.asyncio
      async def test_hybrid_degradation_online_to_offline(self):
          mock_web = MagicMock(spec=WebRAGEngine)
          mock_web.search = AsyncMock(return_value=[
              WebSearchResult(title="Live", url="https://x.com", body="Live $67K", score=0.95),
          ])
          mock_web.build_context_block.return_value = "--- FUENTE WEB ---\nLive $67K"
          mock_local = MagicMock(spec=LocalRAGEngine)
          mock_local.search = AsyncMock(return_value=[])
          mock_local.build_context_block.return_value = "--- MEMORIA LOCAL ---\nCached $66K"
          mock_conn = MagicMock()
          mock_conn.check = AsyncMock()

          injector = RAGContextInjector(
              web_engine=mock_web,
              local_engine=mock_local,
              connectivity=mock_conn,
              mode=RAGMode.HYBRID,
          )

          mock_conn.is_online = True
          context_online = await injector.inject("bitcoin")
          assert "FUENTE WEB" in context_online

          mock_conn.is_online = False
          context_offline = await injector.inject("bitcoin")
          assert "MEMORIA LOCAL" in context_offline

      @pytest.mark.asyncio
      async def test_rag_failure_does_not_break_context_builder(self):
          mock_short = MagicMock()
          mock_short.get_context.return_value = MagicMock(
              active_messages=[], last_tool_results=None,
              current_instructions="", temporal_goals=None,
          )
          mock_long = MagicMock()
          mock_long.search = AsyncMock(return_value=[])
          mock_rag = MagicMock()
          mock_rag.is_enabled = True
          mock_rag.inject = AsyncMock(side_effect=RuntimeError("catastrophic failure"))
          builder = ContextBuilder(
              short_term=mock_short,
              long_term=mock_long,
              rag_injector=mock_rag,
          )
          mock_agent_state = MagicMock()
          mock_agent_state.profile.preferences = {"instructions": ""}
          mock_agent_state.working_memory = {}
          mock_agent_state.session_summary = ""
          ctx = await builder.build("test", mock_agent_state)
          assert ctx.rag_context == ""

  class TestGracefulDegradation:
      @pytest.mark.asyncio
      async def test_web_engine_timeout_returns_empty(self):
          from core.rag.web_rag import WebRAGEngine, WebRAGConfig
          engine = WebRAGEngine(config=WebRAGConfig())
          with patch.object(engine, "_fetch_search_results", new_callable=AsyncMock, side_effect=TimeoutError):
              results = await engine.search("test")
          assert results == []

      @pytest.mark.asyncio
      async def test_local_rag_missing_store_returns_empty(self):
          from core.rag.local_rag import LocalRAGEngine
          engine = LocalRAGEngine()
          chunks = await engine.search("test")
          assert chunks == []

      @pytest.mark.asyncio
      async def test_sync_worker_network_error_continues(self):
          from core.rag.hybrid_sync import HybridSyncWorker, SnapshotSource, SyncState
          worker = HybridSyncWorker(config=SyncConfig())
          mock_conn = MagicMock()
          mock_conn.check = AsyncMock()
          mock_conn.is_online = True
          worker._connectivity = mock_conn
          worker._sources = [
              SnapshotSource(name="fail", url="https://broken.api", parser="json", refresh_minutes=1),
          ]
          with patch.object(worker, "_fetch_snapshot", new_callable=AsyncMock, return_value=None):
              state = await worker.check_and_sync()
          assert state == SyncState.OFFLINE_USING_CACHE
  ```

- [ ] Ejecutar tests de integracion:
  ```bash
  python -m pytest tests/test_rag_integration.py -v
  ```

### 7.2 Verificacion final del candado

- [ ] Ejecutar TODOS los tests (nuevos + existentes):
  ```bash
  python -m pytest tests/ -v --tb=short -m "not live" 2>&1 | tee docs/implementation/final_test_results.txt
  ```
- [ ] Ejecutar candado de estabilidad:
  ```bash
  ./scripts/check_stable_lock.sh
  ```
- [ ] Verificar que NO hay regresiones comparando con el baseline:
  ```bash
  diff docs/implementation/baseline_test_stable.txt docs/implementation/final_test_results.txt
  ```

### 7.3 Prueba manual de humo

- [ ] Arrancar el sistema con RAG desactivado (modo actual):
  ```bash
  CEREBRO_RAG_MODE=off make run
  ```
  Verificar que todas las funcionalidades existentes siguen operando.

- [ ] Arrancar con Web-RAG:
  ```bash
  CEREBRO_RAG_MODE=web make run
  ```
  Probar: "cual es el precio de bitcoin hoy?" — debe incluir datos de la web.

- [ ] Arrancar con Local-RAG:
  ```bash
  CEREBRO_RAG_MODE=local make run
  ```
  Verificar que busca en la DB local.

- [ ] Arrancar con Hybrid-RAG:
  ```bash
  CEREBRO_RAG_MODE=hybrid make run
  ```
  Verificar sincronizacion en background y degradacion al cortar red.

---

## 8. Resumen de Archivos Nuevos y Modificados

### Archivos Nuevos

| Archivo | Proposito | Fase |
|---|---|---|
| `core/net/__init__.py` | Package init para modulos de red | 1 |
| `core/net/connectivity.py` | Deteccion de conectividad con TTL cache | 1 |
| `core/rag/web_rag.py` | Motor Web-RAG (DuckDuckGo + selectolax) | 2 |
| `core/rag/local_rag.py` | Motor Local-RAG (LanceDB + MiniLM) | 3 |
| `core/rag/hybrid_sync.py` | Worker de sincronizacion en rafaga | 4 |
| `core/rag/strategy.py` | Enum RAGMode + feature flag | 5 |
| `core/rag/context_injector.py` | Puente RAG → ContextBuilder | 5 |
| `config/snapshot_sources.json` | Config de fuentes de snapshot | 4 |
| `scripts/check_stable_lock.sh` | Script de verificacion de candado | 0 |
| `tests/test_connectivity.py` | Tests para modulo de conectividad | 1 |
| `tests/test_web_rag.py` | Tests para Web-RAG | 2 |
| `tests/test_local_rag.py` | Tests para Local-RAG | 3 |
| `tests/test_hybrid_rag.py` | Tests para Hybrid Sync | 4 |
| `tests/test_rag_context_injector.py` | Tests para RAGContextInjector | 5 |
| `tests/test_rag_integration.py` | Tests de integracion end-to-end | 6 |

### Archivos Modificados

| Archivo | Cambio | Riesgo | Fase |
|---|---|---|---|
| `pyproject.toml` | Agregar `duckduckgo-search`, `selectolax` | Bajo (dependencias nuevas) | 2 |
| `config/settings.toml` | Agregar seccion `[rag]` | Nulo (seccion nueva) | 5 |
| `core/memory/context_builder.py` | Agregar `rag_injector` param + `rag_context` field | **Medio** (cambio en constructor) | 5 |
| `core/agents/runtime.py` | Agregar `{rag_context}` al system prompt template | **Medio** (template change) | 5 |
| `main.py` | Wiring de componentes RAG | Bajo (codigo condicional) | 5 |
| `ui/tray/server.py` | Agregar campos a AppState | Nulo (campos opcionales) | 5 |
| `AGENTS.md` | Agregar regla de candado | Nulo | 0 |

### Variables de Entorno Nuevas

| Variable | Default | Valores | Proposito |
|---|---|---|---|
| `CEREBRO_RAG_MODE` | `off` | `off` / `web` / `local` / `hybrid` | Feature flag principal |

### Matriz de Riesgo

| Componente | Toca Fast Paths? | Requiere LLM? | Requiere Red? | Regresion posible? |
|---|---|---|---|---|
| `ConnectivityChecker` | No | No | Solo probe (mockeable) | No |
| `WebRAGEngine` | No | No | Si (graceful fail) | No |
| `LocalRAGEngine` | No | No (solo embed) | No | No |
| `HybridSyncWorker` | No | No | Si (graceful fail) | No |
| `RAGContextInjector` | No | No | Depende del modo | No |
| `ContextBuilder.build()` | No | No | No | **Minimo** (param opcional) |
| `_SYSTEM_TEMPLATE` | No | No | No | **Minimo** (placeholder nuevo) |

---

## Orden de Ejecucion Recomendado

```
Fase 0: Candado (15 min)
  ↓
Fase 1: Connectivity (30 min)
  ↓
Fase 2: Web-RAG (1 hora)
  ↓
Fase 3: Local-RAG (45 min)
  ↓
Fase 4: Hybrid Sync (1 hora)
  ↓
Fase 5: Integracion (1 hora)
  ↓
Fase 6: Pruebas finales (30 min)
  ↓
Total estimado: ~5 horas de trabajo
```

Cada fase es **independiente y verificable**. Si una fase falla, se puede revertir sin afectar las anteriores gracias al feature flag `CEREBRO_RAG_MODE=off`.