# Agentic Personal OS — Addendum de Arquitectura v1.1
## Motor Agentic Local con Memoria Persistente y Capa de Proveedores

> **Base:** `agentic_personal_os_dev.md` (v1.0) — este addendum extiende, no reemplaza.
> Todos los módulos originales (0–13) permanecen vigentes; las secciones siguientes describen cambios de diseño y módulos nuevos que se superponen.

---

## Resumen de cambios vs v1.0

| Módulo original | Cambio |
|-----------------|--------|
| Module 1 — Inference Engine | Convertir en capa de proveedores (`ProviderRegistry`) ✓ |
| Module 3 — Vector Memory | Añadir plano de memoria de agente persistente ✓ |
| Module 6 — Tool Use | Añadir políticas, permisos y auditoría por agente ✓ |
| Module 7 — LangGraph | Convertir en runtime de agente con estado durable en disco ✓ |
| Module 9 — Tauri UI | Añadir `ResponseMetadata` en `/query`, `MetricsCollector` en `/status` ✓ |
| Module 12 — Security | Reforzar validación de ruta, sandbox y trazabilidad de acciones |

**Nuevas incorporaciones:** `A1` Provider Registry ✓ · `A2` Persistent Agent Runtime ✓ · `A3` Two-Level Memory ✓ · `A4` Pipeline Middleware ✓ · `A5` Tool Governance ✓ · `A6` Observability ✓ · `A7` Workspace UI

---

## Módulo A1 — Capa de Proveedores de IA
**Refactoriza Module 1**

**Archivos:** `core/inference/providers/` · `core/inference/registry.py`

### Principio

Ningún módulo de negocio invocará un modelo directamente. Todo acceso a generación, embeddings y (en el futuro) visión o transcripción pasará por interfaces estables registradas en `ProviderRegistry`.

### Interfaces estables

```python
class ChatProvider(Protocol):
    async def complete(self, messages: list[Message], **kwargs) -> str: ...
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...
    def model_id(self) -> str: ...
    def context_window(self) -> int: ...
    def is_available(self) -> bool: ...

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    def dimensions(self) -> int: ...

class ProviderRegistry:
    def register(self, name: str, chat: ChatProvider, embed: EmbeddingProvider) -> None: ...
    def get_chat(self, name: str | None = None) -> ChatProvider: ...
    def get_embed(self, name: str | None = None) -> EmbeddingProvider: ...
    def available_providers(self) -> list[str]: ...
    def select_for_task(self, task: TaskHint) -> str: ...  # auto-selección por RAM/latencia
```

### Criterios de selección automática (`select_for_task`)

| Condición | Modelo elegido |
|-----------|----------------|
| RAM libre > 4 GB | Modelo principal (`phi3:mini` o configurado) |
| RAM libre 2–4 GB | Modelo compacto (`qwen2:1.5b`) |
| RAM libre < 2 GB | Respuesta de ruta baja: "Recursos insuficientes" |
| Tarea = embedding | Siempre `nomic-embed-text` (sin excepción) |
| Ollama no disponible | `OllamaUnavailableError` → degradación elegante |

### Implementación inicial

```python
# core/inference/providers/ollama_provider.py
class OllamaChatProvider:
    def __init__(self, model: str, base_url: str, timeout: int = 30): ...

class OllamaEmbeddingProvider:
    def __init__(self, model: str = "nomic-embed-text", base_url: str, timeout: int = 30): ...
```

### Actualización de `settings.toml`

```toml
[providers]
default_chat = "phi3:mini"
fallback_chat = "qwen2:1.5b"
embedding = "nomic-embed-text"
base_url = "http://localhost:11434"

[providers.selection]
ram_threshold_primary_gb = 4.0
ram_threshold_fallback_gb = 2.0
```

### Tests — `tests/test_providers.py`
- [x] `ProviderRegistry` devuelve proveedor correcto por nombre
- [x] `select_for_task` elige fallback cuando RAM < umbral
- [x] Embedding nunca usa el modelo de chat
- [x] `is_available()` retorna `False` sin excepción cuando Ollama está caído

---

## Módulo A2 — Runtime de Agente con Estado Persistente
**Refactoriza Module 7**

**Archivos:** `core/agents/runtime.py` · `core/agents/profiles/` · `core/agents/state_store.py`

### Estado de agente persistente

```python
@dataclass
class AgentProfile:
    id: str                        # UUID fijo por agente
    name: str
    domain_tags: list[str]         # e.g. ["academic", "code"]
    authorized_tools: list[str]    # subconjunto de herramientas habilitadas
    preferences: dict              # instrucciones de comportamiento
    created_at: datetime
    updated_at: datetime

@dataclass
class AgentState:
    profile: AgentProfile
    session_summary: str           # resumen comprimido del historial activo
    working_memory: dict           # objetivos temporales, instrucciones actuales
    tool_trace: list[ToolCall]     # últimas N llamadas a herramientas
    semantic_memory_refs: list[str]  # IDs de chunks recuperados frecuentemente
    execution_count: int
    last_active: datetime
```

### StateStore — persistencia en disco

```python
class AgentStateStore:
    def __init__(self, state_dir: str): ...           # ~/.cerebro/agents/
    def load(self, agent_id: str) -> AgentState: ...
    def save(self, state: AgentState) -> None: ...    # atómico, con backup previo
    def list_agents(self) -> list[AgentProfile]: ...
    def delete(self, agent_id: str) -> None: ...
```

El archivo en disco por agente es `~/.cerebro/agents/<agent_id>.json`. La escritura es atómica: se escribe en `.tmp` y luego se renombra para evitar corrupción.

### Flujo de ejecución actualizado (LangGraph)

```
[load_state]
     ↓
[context_assembly]   ← combina: session_summary + working_memory + semantic_memory
     ↓
[reason_node]        ← LLM decide: necesita herramienta O puede responder
     ↓            ↓
[tool_node]     [end_node]
     ↓
[observe_node]
     ↓
[update_state]       ← actualiza session_summary y tool_trace
     ↓
[reason_node]        ← siguiente iteración
```

Nodo `update_state` es obligatorio: cada interacción debe actualizar el perfil del agente antes de devolver respuesta.

### Límites heredados de v1.0 (sin cambios)
- Máx 10 iteraciones por query
- Máx 5 tool calls por query
- Timeout total: 120 segundos
- Detección de tool call duplicada → abortar

### Tests — `tests/test_agent_runtime.py`
- [x] `AgentStateStore` persiste y recarga estado sin pérdida de datos
- [x] Escritura atómica: simular interrupción → archivo no queda corrupto
- [x] `update_state` actualiza `session_summary` tras cada interacción
- [x] Agente sin perfil guardado inicializa estado vacío correctamente

---

## Módulo A3 — Arquitectura de Memoria en Dos Niveles
**Extiende Module 3**

**Archivos:** `core/memory/short_term.py` · `core/memory/long_term.py` · `core/memory/context_builder.py`

### Plano corto (ShortTermMemory)

Contexto operativo inmediato, mantenido en RAM durante la sesión activa.

```python
@dataclass
class ShortTermMemory:
    active_messages: list[Message]      # conversación actual
    last_tool_results: list[ToolResult] # resultados recientes de herramientas
    current_instructions: str          # instrucciones de sistema activas
    temporal_goals: list[str]           # objetivos de la sesión actual

class ShortTermStore:
    def push_message(self, msg: Message) -> None: ...
    def push_tool_result(self, result: ToolResult) -> None: ...
    def get_context(self) -> ShortTermMemory: ...
    def clear(self) -> None: ...
    def to_summary(self, provider: ChatProvider) -> str: ...  # comprime para persistir
```

### Plano largo (LongTermMemory)

Memoria semántica y episódica indexada en LanceDB + resúmenes persistentes en disco.

```python
class LongTermStore:
    def __init__(self, vector_store: VectorStore, agent_id: str): ...
    async def search(self, query: str, context: RetrievalContext) -> list[MemoryChunk]: ...
    async def store_episode(self, summary: str, tags: list[str]) -> str: ...   # → chunk_id
    def get_agent_episodes(self, agent_id: str, limit: int = 20) -> list[MemoryChunk]: ...

@dataclass
class RetrievalContext:
    query: str
    task_tags: list[str]      # para filtrar por dominio
    date_range: tuple | None  # None = sin filtro temporal
    source_filter: list[str]  # None = todas las fuentes
    min_confidence: float = 0.5
```

### LanceDB — campos adicionales para memoria de agente

Extiende el esquema de la tabla `documents` (Module 3) con una tabla separada `agent_memory`:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | str (PK) | UUID del episodio |
| `agent_id` | str | ID del agente propietario |
| `content` | str | Resumen del episodio |
| `vector` | list[float] (768d) | Embedding del resumen |
| `tags` | str (JSON) | Etiquetas de dominio |
| `created_at` | float | Unix timestamp |
| `confidence` | float | 0.0–1.0 |
| `source` | str | `"episode"` o `"document"` |

### ContextBuilder — ensamblaje antes de responder

```python
class ContextBuilder:
    def __init__(self, short_term: ShortTermStore, long_term: LongTermStore): ...
    async def build(self, query: str, agent_state: AgentState) -> AssembledContext: ...

@dataclass
class AssembledContext:
    session_history: list[Message]
    retrieved_memory: list[MemoryChunk]
    retrieved_documents: list[SearchResult]
    agent_summary: str
    total_tokens_estimated: int
    sources_used: list[str]    # para audit trail
```

**Orden de prioridad en el contexto (de mayor a menor importancia):**
1. `current_instructions` + `working_memory` del agente
2. `session_summary` comprimido
3. Documentos recuperados (por similitud + filtros)
4. Episodios de memoria del agente
5. Mensajes recientes de la sesión activa

### Tests — `tests/test_memory_levels.py`
- [x] `ShortTermStore.to_summary()` produce resumen de < 500 tokens
- [x] `LongTermStore.search()` filtra correctamente por `task_tags`
- [x] `ContextBuilder.build()` respeta el presupuesto de tokens
- [x] Episodio almacenado es recuperable por similitud

---

## Módulo A4 — Capa de Pipelines y Middleware
**Nuevo módulo**

**Archivos:** `core/pipeline/` · `core/pipeline/stages/`

### Cadena de procesamiento

Toda interacción pasa por una cadena de etapas modulares. Cada etapa recibe un `PipelineContext` y lo devuelve modificado (o lanza excepción controlada).

```python
@dataclass
class PipelineContext:
    raw_input: str
    normalized_input: str | None
    detected_intent: Intent | None
    assembled_context: AssembledContext | None
    prompt: str | None
    policy_result: PolicyResult | None
    tool_calls: list[ToolCall]
    raw_response: str | None
    final_response: str | None
    audit_record: AuditRecord
    metadata: dict

class PipelineStage(Protocol):
    async def process(self, ctx: PipelineContext) -> PipelineContext: ...
    def name(self) -> str: ...
    def can_skip(self) -> bool: ...  # si True, el error no aborta el pipeline
```

### Etapas obligatorias v1.1

| Orden | Etapa | Archivo | Función |
|-------|-------|---------|---------|
| 1 | `InputNormalizationStage` | `stages/normalization.py` | Strip, límite de longitud, detección de idioma |
| 2 | `IntentDetectionStage` | `stages/intent.py` | Clasifica: query RAG / agente / acción / config |
| 3 | `ContextRetrievalStage` | `stages/context.py` | Llama a `ContextBuilder.build()` |
| 4 | `PromptAssemblyStage` | `stages/prompt.py` | Construye el prompt final desde contexto |
| 5 | `PolicyValidationStage` | `stages/policy.py` | Valida que el prompt no viola reglas de seguridad |
| 6 | `ToolExecutionStage` | `stages/tools.py` | Ejecuta herramientas aprobadas por política |
| 7 | `PostProcessingStage` | `stages/postprocess.py` | Formatea respuesta, extrae fuentes |
| 8 | `AuditStage` | `stages/audit.py` | Registra metadatos sin contenido sensible |

### Pipeline runner

```python
class Pipeline:
    def __init__(self, stages: list[PipelineStage]): ...
    async def run(self, raw_input: str, agent_state: AgentState) -> PipelineContext: ...
    def insert_stage(self, stage: PipelineStage, after: str) -> None:  # extensible sin romper core
    def remove_stage(self, name: str) -> None: ...
```

Insertar o eliminar etapas no modifica las interfaces de otros módulos.

### Tests — `tests/test_pipeline.py`
- [x] Pipeline completo ejecuta las 8 etapas en orden
- [x] Etapa con `can_skip=True` que falla no aborta el pipeline
- [x] `insert_stage` / `remove_stage` funciona sin afectar otras etapas
- [x] `AuditRecord` nunca contiene contenido de documentos

---

## Módulo A5 — Gobernanza de Herramientas
**Refactoriza Module 6**

**Archivos:** `core/tools/registry.py` · `core/tools/policy.py` · `core/tools/audit.py`

### Principio

Las herramientas no son funciones libres. Son acciones mediadas por políticas vinculadas al perfil del agente que las solicita.

### ToolRegistry

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable
    required_permission: str        # e.g. "tools.write_file"
    requires_confirmation: bool     # acciones destructivas o de escritura
    scope: ToolScope                # LOCAL | SANDBOXED | RESTRICTED
    audit_level: AuditLevel         # NONE | METADATA | FULL

class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None: ...
    def get(self, name: str) -> ToolDefinition: ...
    def list_for_agent(self, agent: AgentProfile) -> list[ToolDefinition]: ...
    def is_authorized(self, tool_name: str, agent: AgentProfile) -> bool: ...
```

### PolicyEngine

```python
class PolicyEngine:
    async def validate_call(
        self,
        tool: ToolDefinition,
        args: dict,
        agent: AgentProfile,
        context: PipelineContext
    ) -> PolicyResult: ...

@dataclass
class PolicyResult:
    approved: bool
    requires_user_confirmation: bool
    reason: str | None
    sanitized_args: dict    # args después de validación de ruta
```

### Reglas de política obligatorias

| Herramienta | Regla |
|-------------|-------|
| `write_file` | Validar que `path` está en `authorized_write_paths` antes de ejecutar |
| `read_file` | Validar que `path` está en `watched_paths` |
| `execute_python` | Scope `SANDBOXED`: restricciones de v1.0 + registro de código ejecutado |
| `create_directory` | Requiere confirmación si el directorio padre no existe |
| Toda escritura | Registro de auditoría con: agente, herramienta, args sanitizados, timestamp, resultado |

Ningún agente puede ejecutar herramientas fuera de su `authorized_tools`. El `PolicyEngine` rechaza la llamada antes de llegar al handler.

### AuditLogger

```python
class AuditLogger:
    def log_tool_call(
        self,
        agent_id: str,
        tool: str,
        args_sanitized: dict,   # sin contenido de archivos
        result_summary: str,    # sin contenido sensible
        approved: bool,
        timestamp: datetime
    ) -> None: ...
```

Archivo de auditoría: `~/.cerebro/audit/audit-<YYYY-MM>.jsonl` (rotación mensual).

### Tests — `tests/test_tool_governance.py`
- [x] `PolicyEngine` rechaza herramienta no en `authorized_tools` del agente
- [x] `write_file` con path fuera de `authorized_write_paths` → `PolicyResult(approved=False)`
- [x] `execute_python` registra el código ejecutado en audit
- [x] `AuditLogger` no escribe contenido de documentos en el log

---

## Módulo A6 — Observabilidad y Depuración
**Nuevo módulo**

**Archivos:** `core/observability/` · `core/observability/response_meta.py`

### ResponseMetadata — adjunto a toda respuesta

```python
@dataclass
class ResponseMetadata:
    sources_used: list[SourceRef]        # [{path, chunk_index, score}]
    tools_called: list[ToolCallRecord]   # [{name, args_summary, result_summary, latency_ms}]
    memory_retrieved: list[MemoryRef]    # [{id, summary_snippet, relevance_score}]
    inference_latency_ms: float
    total_latency_ms: float
    iterations: int
    model_used: str
    provider_used: str
    warnings: list[str]                  # e.g. "tool_fallback", "memory_truncated"
    pipeline_stages_ms: dict[str, float] # latencia por etapa del pipeline

@dataclass
class SourceRef:
    path: str
    chunk_index: int
    score: float

@dataclass
class ToolCallRecord:
    name: str
    args_summary: str   # resumen, nunca contenido completo
    result_summary: str
    latency_ms: float
    approved: bool
```

### Actualización del endpoint `/query`

```json
{
  "answer": "...",
  "metadata": {
    "sources_used": [...],
    "tools_called": [...],
    "memory_retrieved": [...],
    "inference_latency_ms": 4200,
    "total_latency_ms": 5100,
    "iterations": 2,
    "model_used": "phi3:mini",
    "provider_used": "ollama",
    "warnings": []
  }
}
```

### MetricsCollector

```python
class MetricsCollector:
    def record_query(self, meta: ResponseMetadata) -> None: ...
    def get_stats(self) -> SystemStats: ...    # para /status

@dataclass
class SystemStats:
    queries_total: int
    avg_latency_ms: float
    p95_latency_ms: float
    tool_call_count: int
    memory_hits: int
    provider_fallbacks: int
    active_agent: str
```

### Tests — `tests/test_observability.py`
- [x] `ResponseMetadata` siempre presente en respuesta de `/query`
- [x] `warnings` incluye `"provider_fallback"` cuando se usa modelo alternativo
- [x] `MetricsCollector` calcula p95 correctamente con muestras conocidas
- [x] `MetricsCollector` acumula `tool_call_count`, `memory_hits`, `provider_fallbacks`
- [x] `/status` expone `p95_latency_ms`, `tool_call_count`, `memory_hits`, `provider_fallbacks`
- [x] `/status` refleja queries registradas por `MetricsCollector`

---

## Módulo A7 — Experiencia de Usuario tipo Workspace
**Refactoriza Module 9**

**Stack:** Tauri 2.0 · React 18 · TypeScript · Tailwind CSS (sin cambio de stack)

### Nuevos paneles requeridos en la UI

| Panel | Contenido | Trigger de visibilidad |
|-------|-----------|------------------------|
| **Agent Selector** | Lista de agentes guardados, estado, última actividad | Siempre visible |
| **Model Selector** | Proveedor activo, modelo, estado RAM | Siempre visible |
| **Sources Panel** | Fuentes usadas en la última respuesta (path + score) | Post-respuesta |
| **Memory Panel** | Episodios recuperados, score de relevancia | Post-respuesta |
| **Tool History** | Herramientas llamadas, args resumidos, resultado | Post-respuesta |
| **System State** | RAM usada, latencia p50, iteraciones, warnings | Status bar |
| **Confirmation Modal** | Acciones pendientes de aprobación del usuario | Cuando `requires_user_confirmation=True` |

### Indicadores visuales obligatorios

- Icono de memoria activa cuando `memory_retrieved` no está vacío
- Icono de herramienta cuando `tools_called` no está vacío
- Badge en cada respuesta con el modelo que la generó
- Toast de warning cuando `warnings` no está vacío
- Modal bloqueante cuando una herramienta requiere confirmación del usuario

### Actualización del endpoint `/status`

> Los campos de A6 ya están disponibles. A7 los expone visualmente en la status bar.

```json
{
  "indexed_files": 142,
  "ollama_ok": true,
  "model": "phi3:mini",
  "provider": "ollama",
  "active_agent": "academic-v1",
  "ram_used_gb": 3.8,
  "ram_available_gb": 4.2,
  "queries_total": 47,
  "avg_latency_ms": 5200,
  "p95_latency_ms": 8400,
  "tool_call_count": 12,
  "memory_hits": 34,
  "provider_fallbacks": 0
}
```

### Tests — `tests/test_api.py` (adiciones)
- [x] `/query` respuesta incluye `metadata` con todos los campos requeridos
- [x] `/status` incluye `active_agent`, `ram_used_gb`, `ram_available_gb`
- [ ] Confirmation modal se activa cuando API devuelve `requires_confirmation=true`

---

## Módulo A8 — Reglas de Rendimiento y Confiabilidad
**Extiende Module 12 (Performance Limits)**

### Tabla actualizada

| Métrica | Target v1.0 | Target v1.1 | Acción si se supera |
|---------|-------------|-------------|---------------------|
| RAM (Python + Ollama) | < 5.5 GB | < 5.5 GB | Cambiar a modelo fallback vía `ProviderRegistry` |
| RAG latency p50 | < 8s | < 8s | Reducir `top_k` de 5 a 3 |
| RAG latency p95 | < 20s | < 20s | Log + warning en `ResponseMetadata` |
| Indexing 100-page file | < 60s | < 60s | Background, nunca bloquear UI |
| LanceDB size | < 2 GB / 10k docs | < 2 GB / 10k docs | Notificar al usuario |
| CPU idle | < 2% | < 2% | Descargar modelo tras 10 min sin actividad |
| Pipeline total | — | < 500ms overhead (sin inferencia) | Log de etapa lenta |
| State persistence | — | < 50ms por `save()` | Escritura asíncrona en background |

### Degradación elegante

```
Ollama no disponible
  → ProviderRegistry.get_chat() → OllamaUnavailableError
  → Pipeline.PolicyValidationStage → bloquea ejecución
  → Respuesta: "El servicio de inferencia local no está disponible. Inicia Ollama e intenta de nuevo."
  → UI muestra estado "Ollama: ✗" en status bar

RAM < 2 GB disponible
  → ProviderRegistry.select_for_task() → "insufficient_resources"
  → Pipeline aborta antes de inferencia
  → Respuesta: "Memoria insuficiente para inferencia. Cierra otras aplicaciones."
  → warning: "low_memory" en ResponseMetadata
```

---

## Actualización de Folder Structure

```
cerebro/
  core/
    inference/
      providers/              # A1: OllamaChatProvider, OllamaEmbeddingProvider
      registry.py             # A1: ProviderRegistry
    ingestion/                # sin cambios (Module 2)
    memory/
      vector_store.py         # Module 3: sin cambios
      short_term.py           # A3: ShortTermStore
      long_term.py            # A3: LongTermStore (extiende VectorStore)
      context_builder.py      # A3: ContextBuilder
    rag/                      # sin cambios (Module 4)
    watcher/                  # sin cambios (Module 5)
    tools/
      registry.py             # A5: ToolRegistry
      policy.py               # A5: PolicyEngine
      audit.py                # A5: AuditLogger
      handlers/               # Module 6: implementaciones de cada tool
    agents/
      runtime.py              # A2: AgentRuntime (LangGraph + estado persistente)
      state_store.py          # A2: AgentStateStore
      profiles/               # A2: perfiles de agentes guardados
      specialized.py          # Module 8: sin cambios en interfaz
    pipeline/
      pipeline.py             # A4: Pipeline runner
      stages/                 # A4: 8 etapas modulares
    observability/
      response_meta.py        # A6: ResponseMetadata, ToolCallRecord, SourceRef, MemoryRef, MetricsCollector, SystemStats ✓
  ui/
    tray/                     # A7: workspace UI (Tauri + React)
  scheduler/
    proactive.py              # Module 10: ProactiveScheduler, TriggerEvent, TriggerKind, NotificationSink ✓
  integrations/               # Module 11
  config/                     # Module 12
  tests/
  dist/
```

---

## Actualización de `settings.toml` (schema completo v1.1)

```toml
[general]
app_name = "Cerebro"
language = "es"
log_level = "INFO"

[providers]
default_chat = "phi3:mini"
fallback_chat = "qwen2:1.5b"
embedding = "nomic-embed-text"
base_url = "http://localhost:11434"

[providers.selection]
ram_threshold_primary_gb = 4.0
ram_threshold_fallback_gb = 2.0

[inference]
timeout_seconds = 30
context_window = 4096

[ingestion]
watched_paths = []
chunk_size = 512
chunk_overlap = 64
min_chunk_size = 50
excluded_patterns = [".git", "node_modules", "__pycache__", ".venv"]

[memory]
db_path = "~/.cerebro/db"
agent_state_dir = "~/.cerebro/agents"
short_term_max_messages = 50
long_term_episode_limit = 500

[tools]
enable_execute_python = true
enable_write_file = true
authorized_write_paths = []
require_confirmation_on_write = true

[pipeline]
max_input_length = 4000
intent_detection_enabled = true
audit_enabled = true

[ui]
hotkey = "cmd+shift+space"
port = 7842
show_sources_panel = true
show_memory_panel = true
show_tool_history = true

[scheduler]
enabled = true
check_interval_minutes = 5
do_not_disturb = false

[security]
max_file_size_mb = 50
sandbox_timeout_seconds = 10
sandbox_memory_mb = 64
audit_log_dir = "~/.cerebro/audit"
audit_rotation = "monthly"
```

---

## Nuevas dependencias de stack

| Componente | Tecnología | Install |
|------------|-----------|---------|
| Provider abstraction | `typing.Protocol` (stdlib) | — |
| Atomic state writes | `os.replace` (stdlib) | — |
| RAM monitoring | `psutil` | `pip install psutil` |
| Audit logging | `jsonlines` | `pip install jsonlines` |
| Pipeline stages | Sin dependencia adicional | — |

Stack base de v1.0 (Module 0) permanece sin cambios.

---

## Architecture Decision Log — Adiciones v1.1

| Decisión | Por qué |
|----------|---------|
| `ProviderRegistry` sobre llamadas directas a Ollama | Permite alternar modelos en tiempo de ejecución sin tocar lógica de negocio |
| Estado de agente en JSON en disco (no SQLite) | Legible, inspeccionable, versionable con git; suficiente para un agente local |
| Dos planos de memoria separados (corto/largo) | Contexto inmediato en RAM (< 1ms), episódico en LanceDB (< 100ms); no mezclar latencias |
| Pipeline como cadena de etapas independientes | Permite insertar logging, seguridad o A/B testing sin modificar el núcleo del agente |
| `PolicyEngine` antes de ejecutar cualquier tool | Ningún agente puede escapar sus permisos; la validación no depende de que el LLM sea "correcto" |
| `ResponseMetadata` en toda respuesta | El sistema debe ser explicable desde el primer día; debug sin logs de contenido sensible |
| Confirmación de usuario para escrituras | Acción irreversible + escritura a disco = el usuario debe aprobar siempre |
