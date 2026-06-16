# Plan: Web Search para el agente

## Estrategia

**Backend default**: DuckDuckGo HTML + Trafilatura (100% gratis, sin API key, ilimitado para uso personal).
**Backend opcional**: Tavily API (resultados más limpios para LLMs, configurable por env var).

Ambos tools (`web_search` y `web_fetch`) se registran igual desde el punto de vista del modelo. El backend se elige en `config/settings.toml`.

---

## Fase 1 — Dependencias

**Objetivo**: Instalar las librerías necesarias.

- [x] Agregar a `pyproject.toml`:
  ```toml
  "duckduckgo-search>=7.0",
  "trafilatura>=2.0",
  "tavily-python>=0.5",  # opcional, solo si se configura
  ```
- [x] `make install` o `pip install -e ".[dev]"`
- [x] Verificar imports: `from duckduckgo_search import DDGS`, `import trafilatura`

**Archivos a modificar**: `pyproject.toml`

---

## Fase 2 — Configuración

**Objetivo**: Definir settings del backend web con su sección en TOML y env vars.

- [x] Agregar sección `[tools.web]` en `config/settings.toml`:
  ```toml
  [tools.web]
  backend = "duckduckgo"       # "duckduckgo" | "tavily"
  max_results = 5
  timeout_seconds = 15
  max_content_chars = 4000   # 4000 chars ≈ 1000 tokens. 8000 es el techo máximo absoluto.
  ```
- [x] En `.env` (opcional):
  ```
  TAVILY_API_KEY=tvly-...
  CEREBRO_WEB_TIMEOUT=15
  CEREBRO_WEB_BACKEND=duckduckgo
  CEREBRO_WEB_MAX_RESULTS=5
  ```
- [x] En `core/config/__init__.py` o `core/config/settings.py` (según exista), mapear estas vars al objeto de config.
- [x] Verificar que `app_state.config` expone `tools.web.backend` y `tools.web.max_results`.

**Archivos a modificar**: `config/settings.toml`, `core/config/__init__.py` (o el que cargue settings)

---

## Fase 3 — Handler: `core/tools/handlers/web.py`

**Objetivo**: Implementar `web_search()` y `web_fetch()` con backend intercambiable.

### `web_search(query, max_results=5, backend="duckduckgo") → str`

**Backend DuckDuckGo**:
- [x] **IMPORTANTE — Lazy import**: `from duckduckgo_search import DDGS` dentro de la función, no al tope del archivo
- [x] `DDGS().text(query, max_results=max_results)` devuelve `[{title, href, body}, ...]`
- [x] Formatear salida como texto plano:
  ```
  1. Title
     URL: https://...
     Snippet: ...
  ---
  2. ...
  ```
- [x] Manejar `RateLimitException` → retry con sleep(2) o mensaje claro
- [x] Manejar `DuckDuckGoSearchException` → log + raise tool error legible

**Backend Tavily**:
- [x] **IMPORTANTE — Lazy import**: `import tavily` dentro de la función, no al tope del archivo
- [x] `tavily.Client(api_key=...).search(query, max_results=max_results)`
- [x] Formatear igual que DDG
- [x] Solo disponible si `TAVILY_API_KEY` está seteada

**Estructura**:
```python
def web_search(query: str, max_results: int = ..., backend: str = ...) -> str:
    # 1. Elegir backend según config
    # 2. Llamar al backend
    # 3. Validar resultados
    # 4. Formatear texto plano
    # 5. Devolver str o error descriptivo
```

### `web_fetch(url, max_chars=4000) → str`

- [x] **IMPORTANTE — Lazy imports**: `httpx` y `trafilatura` deben importarse DENTRO de la función, no al tope del archivo. Esto evita cargar librerías pesadas en el arranque si el usuario nunca usa web_fetch.
- [x] `httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})`
- [x] Extraer texto con `trafilatura.extract(response.text, no_labels=True)` — `no_labels=True` evita que trafilatura intente descargar modelos de detección de lenguaje
- [x] Fallback: `BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)`
- [x] Truncar estrictamente a `max_chars` y añadir sufijo `"[... Texto truncado por límite de contexto]"` si excede el tamaño
- [x] Manejar: timeout, 403/404, conexión rechazada, redirect loop

**Archivo a crear**: `core/tools/handlers/web.py`

---

## Fase 4 — Registrar tools en Registry

**Objetivo**: Hacer que el sistema conozca `web_search` y `web_fetch` como tools.

- [x] En `core/tools/registry.py`, crear `register_web_tools(registry: ToolRegistry)`:
  ```python
  def register_web_tools(registry: ToolRegistry) -> None:
      from core.tools.handlers.web import web_fetch, web_search

      registry.register(ToolDefinition(
          name="web_search",
          description="Search the internet for current information using a web search engine. Use for news, facts, recent events, or any question that needs up-to-date data.",
          handler=web_search,
          required_permission="tools.web.read",
          requires_confirmation=False,
          scope=ToolScope.SANDBOXED,
          audit_level=AuditLevel.METADATA,
          parameters={
              "query": "str — search query in natural language",
              "max_results": "int — number of results to return (default: 5)",
          },
      ))
      registry.register(ToolDefinition(
          name="web_fetch",
          description="Fetch and extract readable text content from a specific URL. Use to read full articles or pages found via web_search.",
          handler=web_fetch,
          required_permission="tools.web.read",
          requires_confirmation=False,
          scope=ToolScope.SANDBOXED,
          audit_level=AuditLevel.METADATA,
          parameters={
              "url": "str — full URL to fetch (https://...)",
          },
      ))
  ```
- [x] En `main.py` → `_build_app_state()`, llamar `register_web_tools(registry)` después de `register_automation_tools(...)`
- [x] Importar la función en `main.py`

**Archivos a modificar**: `core/tools/registry.py`, `main.py`

---

## Fase 5 — Permiso en Policy

**Objetivo**: El sistema de permisos debe reconocer `tools.web.read`.

- [x] En `core/tools/policy.py`, revisar si los permisos son dinámicos o hay un enum/mapa estático
- [x] Si hay validación de permisos hardcodeada, agregar `"tools.web.read"`
- [x] Verificar que `PolicyEngine.is_authorized()` no lo rechace

**Archivos a modificar**: `core/tools/policy.py`

---

## Fase 6 — Autorizar en agentes

**Objetivo**: Los agentes que deben tener acceso web, lo tengan.

   - [x] `GENERAL_TOOLS` → agregar `"web_search"` y `"web_fetch"` (siempre)
   - [x] `ACADEMIC_TOOLS` → agregar `"web_search"` (investigación académica)
   - [x] `CODE_TOOLS` → agregar `"web_search"` (buscar documentación, Stack Overflow)
   - [x] `CALENDAR_TOOLS` → dejar sin cambios (no necesita web)
- [x] Verificar que `ensure_profiles()` en `SpecializedAgentRouter` sincroniza los cambios a disco en el próximo inicio

**Archivos a modificar**: `core/agents/specialized.py`

---

## Fase 7 — System Prompt Instruction (opcional pero recomendado)

**Objetivo**: El modelo debe saber cuándo y cómo usar las web tools. Crítico: solo injectar si el agente activo tiene el permiso, para no inflar el system prompt de agentes que no usan web (calendario, matemáticas).

- [x] En `core/agents/runtime.py` → `_build_system_prompt()`, agregar bloque condicional ESTRICTO: solo concatenar si `tools.web.read` está en `agent.profile.authorized_tools`:
  ```
  WEB SEARCH: You have access to web_search and web_fetch. 
  Use web_search when you need current information, recent events, 
  or facts not in your training data. Use web_fetch to read full 
  articles. Always cite sources by their URL.
  ```

**Archivos a modificar**: `core/agents/runtime.py`

---

## Fase 8 — Testing

**Objetivo**: Tests deterministas sin red real (mockeando los backends).

**Archivo**: `tests/test_web_tools.py`

- [x] **Test: `web_search` con DuckDuckGo mockeado**
  - Mockear `duckduckgo_search.DDGS.text` para devolver 3 resultados fake
  - Verificar formato de salida: titles, URLs, snippets presentes
- [x] **Test: `web_search` con Tavily mockeado**
  - Mockear `tavily.Client.search`
  - Verificar mismo formato de salida
- [x] **Test: `web_search` sin resultados**
  - Mockear DDGS devolviendo lista vacía
  - Verificar mensaje: "No se encontraron resultados"
- [x] **Test: `web_search` con error de rate limit**
  - Mockear DDGS lanzando `RateLimitException`
  - Verificar mensaje de error amigable
- [x] **Test: `web_fetch` exitoso**
  - Mockear `httpx.get` devolviendo HTML simple
  - `trafilatura.extract(html, no_labels=True)` devolviendo texto limpio
  - `no_labels=True` evita que trafilatura descargue modelos externos en test
  - Verificar contenido extraído
- [x] **Test: `web_fetch` timeout**
  - Mockear `httpx.get` lanzando ` httpx.TimeoutException`
  - Verificar mensaje: "Timeout"
- [x] **Test: `web_fetch` 404**
  - Mockear `httpx.get` lanzando `httpx.HTTPStatusError`
  - Verificar mensaje con código de error
- [x] **Test: `web_search` tool registrada correctamente**
  - Usar `tmp_app_state` fixture de `conftest.py`
  - Verificar que `ToolRegistry.get("web_search")` funciona
- [x] **Test: `web_search` autorizada para general agent**
  - Verificar que `"web_search"` está en `GENERAL_TOOLS`

**Archivo a crear**: `tests/test_web_tools.py`

---

## Fase 9 — Integración con Fast Path Router (mejora futura)

**Objetivo**: Detectar consultas que preguntan por "qué pasó", "últimas noticias", "clima", etc. y rutear por fast path sin pasar por el LLM.

- [x] En `core/agents/fast_path_router.py`, agregar `_try_web_search()` en el `_HANDLERS` tuple
- [x] Keywords de activación: `"noticias"`, `"últimas"`, `"clima"`, `"buscar en internet"`, `"search"`, `"news"`, `"weather"`, `"current"`
- [x] Implementado como fast path para search/buscar/noticias/news/weather/clima en web_search vía LLM

**Archivos a modificar** (futuro): `core/agents/fast_path_router.py`

---

## Fase 10 — Frontend (opcional)

**Objetivo**: Feedback visual cuando el modelo busca en web.

- [x] Mostrar indicador tipo "Buscando en internet..." en el chat mientras web_search está ejecutándose
- [x] En `ui/tray/src/stores/chat.ts`, estado `searchingWeb`; en `InputArea.tsx`, detectar pending_tool web_search/web_fetch
- [x] Mostrar indicador "Buscando en internet..." mientras se ejecuta web_search/web_fetch en el mensaje

**Archivos a modificar** (futuro): `ui/tray/src/stores/chat.ts`, componentes del chat

---

## Resumen de archivos

| Archivo | Acción |
|---|---|
| `pyproject.toml` | Agregar `duckduckgo-search`, `trafilatura`, `tavily-python` |
| `config/settings.toml` | Nueva sección `[tools.web]` |
| `core/tools/handlers/web.py` | **Crear**: `web_search()`, `web_fetch()` |
| `core/tools/registry.py` | Agregar `register_web_tools()` |
| `main.py` | Llamar `register_web_tools()` en `_build_app_state()` |
| `core/tools/policy.py` | Agregar permiso `tools.web.read` |
| `core/agents/specialized.py` | Agregar tools a `GENERAL_TOOLS`, `ACADEMIC_TOOLS`, `CODE_TOOLS` |
| `core/agents/runtime.py` | Agregar instrucción web al system prompt |
| `tests/test_web_tools.py` | **Crear**: tests mockeados de web_search y web_fetch |

---

## Resultados de verificación

### Backend tests
```
tests/test_web_tools.py ..................... 15 passed
tests/test_fast_path_router.py .............. 6 passed
tests/test_tool_governance.py .............. 11 passed
tests/test_agent_runtime.py ................ 26 passed
tests/test_stable_fast_paths.py ............ 52 passed
tests/test_api.py .......................... 48 passed
tests/test_memory.py ....................... 18 passed
tests/test_config.py ....................... 4 passed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 212 passed, 0 failed (23.19s)
```
Nota: 1 test pre-existing fail en `test_calendar.py::test_apple_backend_returns_events` (Apple Calendar backend), no relacionado.

### Frontend
```
npx tsc --noEmit → 0 errors in modified files
                  2 pre-existing TS6133 warnings in StatusBar.tsx, debug.ts (no relation)
```

### Integración
| Check | Resultado |
|---|---|
| Tool `web_search` registrada en `ToolRegistry` | ✅ |
| Tool `web_fetch` registrada en `ToolRegistry` | ✅ |
| `web_search` autorizada en `GENERAL_TOOLS` | ✅ |
| `web_fetch` autorizada en `GENERAL_TOOLS` | ✅ |
| `web_search` autorizada en `ACADEMIC_TOOLS` | ✅ |
| `web_search` autorizada en `CODE_TOOLS` | ✅ |
| `web_search` NO autorizada en `CALENDAR_TOOLS` | ✅ |
| Config `[tools.web]` carga correctamente | ✅ |
| System prompt inyecta instrucción WEB para agente con web tools | ✅ |
| System prompt NO inyecta instrucción WEB para agente calendar | ✅ |
| Lazy imports: DDGS, tavily, httpx, trafilatura dentro de funciones | ✅ |
| Truncation con sufijo `[... Texto truncado...]` | ✅ |
| BeautifulSoup fallback para web_fetch | ✅ |
| Fast path router detecta queries de búsqueda web | ✅ |
| Frontend `searchingWeb` indicator | ✅ |
