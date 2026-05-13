"""Module 9 + A6 — REST API server (port 7842).

FastAPI backend consumed by the Tauri tray UI.
All components (runtime, vector_store, provider_registry) are injected via
`app_state` so tests can replace them without spinning up real infrastructure.

Module A6 adds ResponseMetadata to every /query reply and wires MetricsCollector
into /status for richer aggregate stats.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import psutil
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from loguru import logger
from pydantic import BaseModel, Field

from core.agents.conversation_store import ConversationStore
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.observability.response_meta import MetricsCollector, ResponseMetadata, ToolCallRecord

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models for request / response serialisation
# ──────────────────────────────────────────────────────────────────────────────


class SourceRefModel(BaseModel):
    path: str
    chunk_index: int
    score: float


class ToolCallRecordModel(BaseModel):
    name: str
    args_summary: str
    result_summary: str
    latency_ms: float
    approved: bool


class MemoryRefModel(BaseModel):
    id: str
    summary_snippet: str
    relevance_score: float


class PendingToolModel(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ResponseMetadataModel(BaseModel):
    sources_used: list[SourceRefModel] = Field(default_factory=list)
    tools_called: list[ToolCallRecordModel] = Field(default_factory=list)
    memory_retrieved: list[MemoryRefModel] = Field(default_factory=list)
    inference_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    iterations: int = 1
    model_used: str = ""
    provider_used: str = ""
    warnings: list[str] = Field(default_factory=list)
    pipeline_stages_ms: dict[str, float] = Field(default_factory=dict)
    pending_tool: PendingToolModel | None = None


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str
    metadata: ResponseMetadataModel | None = None


class ConversationSummary(BaseModel):
    conv_id: str
    agent_id: str
    started_at: str
    last_active: str
    message_count: int
    first_user_message: str


class ConversationDetail(BaseModel):
    conv_id: str
    agent_id: str
    started_at: str
    last_active: str
    messages: list[ConversationMessage]


class ToolConfirmRequest(BaseModel):
    conversation_id: str
    decision: Literal["approve", "deny"]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    agent: str = GENERAL_AGENT_ID
    conversation_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    metadata: ResponseMetadataModel
    conversation_id: str


class IndexRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)


class IndexResponse(BaseModel):
    status: str
    job_id: str


class IndexStatusResponse(BaseModel):
    job_id: str
    status: Literal["running", "done", "error"]
    files_indexed: int
    message: str = ""


@dataclass
class _IndexJob:
    status: Literal["running", "done", "error"] = "running"
    files_indexed: int = 0
    message: str = ""


class StatusResponse(BaseModel):
    indexed_files: int
    engine_ok: bool
    model: str
    provider: str
    active_agent: str
    ram_used_gb: float
    ram_available_gb: float
    queries_total: int
    avg_latency_ms: float
    p95_latency_ms: float
    tool_call_count: int
    memory_hits: int
    provider_fallbacks: int
    specialist_role: str | None = None
    specialist_loaded: bool = False
    current_model_id: str | None = None
    current_model_quant: str | None = None
    current_model_params_b: float | None = None
    hardware_snapshot: dict[str, Any] | None = None
    selection_rationale: str | None = None
    context_window: int = 0


class WizardStatusResponse(BaseModel):
    is_first_launch: bool
    engine_running: bool
    model_pulled: bool
    folders_configured: bool


class EmbeddingCacheStatsResponse(BaseModel):
    """Embedding cache statistics response.

    Fields:
        hits: Number of cache hits
        misses: Number of cache misses
        hit_rate_percent: Hit rate as percentage (0-100)
        size: Current number of cached embeddings
        max_size: Maximum cache size
        evictions: Total evictions due to LRU
        avg_get_latency_ms: Average get operation latency
        avg_put_latency_ms: Average put operation latency
        ttl_seconds: TTL setting or None if no expiry
        persistence_store: Backend store name (InMemoryCacheStore or SQLiteCacheStore)
    """

    hits: int
    misses: int
    hit_rate_percent: float
    size: int
    max_size: int
    evictions: int = 0
    avg_get_latency_ms: float = 0.0
    avg_put_latency_ms: float = 0.0
    ttl_seconds: int | None = None
    persistence_store: str = "InMemoryCacheStore"


class SetFoldersRequest(BaseModel):
    folders: list[str]


# ──────────────────────────────────────────────────────────────────────────────
# App state — injectable for tests
# ──────────────────────────────────────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.runtime: Any = None  # AgentRuntime | None
        self.vector_store: Any = None  # VectorStore | None
        self.provider_registry: Any = None  # ProviderRegistry | None
        self.model_manager: Any = None  # ModelManager | None
        self.planner: Any = None  # TaskPlanner | None
        self.enricher: Any = None  # ContextEnricher | None
        self.embedding_provider: Any = None  # CachedEmbeddingProvider | None
        self.fleet_orchestrator: Any = None  # FleetOrchestrator | None
        self.router: SpecializedAgentRouter = SpecializedAgentRouter()
        self.active_agent_id: str = GENERAL_AGENT_ID
        self.metrics: MetricsCollector = MetricsCollector()
        self.cerebro_files_path: str = os.path.expanduser(
            os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles")
        )
        self.authorized_read_paths: list[str] = []
        self.authorized_write_paths: list[str] = []
        self._index_jobs: dict[str, _IndexJob] = {}
        # Keyed by conversation_id; holds pending tool call info awaiting user decision.
        self._pending_tools: dict[str, dict] = {}
        self._wizard_done: bool = False
        _state_dir = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser()
        self._wizard_state_file: Path = _state_dir / "wizard.json"
        self._config_file: Path = _state_dir / "config.json"
        self._config: dict[str, Any] = self._load_config()
        self.conv_store: ConversationStore = ConversationStore(str(_state_dir))
        self._load_wizard_state()

    def _load_config(self) -> dict[str, Any]:
        try:
            if self._config_file.exists():
                return json.loads(self._config_file.read_text())
        except Exception:
            pass
        return {}

    def _save_config(self) -> None:
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            self._config_file.write_text(json.dumps(self._config, indent=2))
        except Exception:
            pass

    def _load_wizard_state(self) -> None:
        try:
            if self._wizard_state_file.exists():
                data = json.loads(self._wizard_state_file.read_text())
                self._wizard_done = data.get("done", False)
        except Exception:
            pass

    def _save_wizard_state(self) -> None:
        try:
            self._wizard_state_file.parent.mkdir(parents=True, exist_ok=True)
            self._wizard_state_file.write_text(json.dumps({"done": self._wizard_done}))
        except Exception:
            pass

    # kept for backwards-compat with existing call sites
    @property
    def queries_total(self) -> int:
        return self.metrics.get_stats().queries_total

    @property
    def avg_latency_ms(self) -> float:
        return self.metrics.get_stats().avg_latency_ms


app_state = AppState()

# ──────────────────────────────────────────────────────────────────────────────
# Optional API key auth — skipped entirely when CEREBRO_API_KEY is unset
# ──────────────────────────────────────────────────────────────────────────────

_API_KEY_HEADER = APIKeyHeader(name="X-Cerebro-Key", auto_error=False)
_CEREBRO_API_KEY: str = os.getenv("CEREBRO_API_KEY", "")


async def _verify_api_key(key: str | None = Security(_API_KEY_HEADER)) -> None:
    if not _CEREBRO_API_KEY:
        return
    if key != _CEREBRO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app_state.model_manager is not None:
        try:
            await app_state.model_manager.start()
        except Exception:
            logger.exception("ModelManager failed to start — model swapping disabled")
    yield
    if app_state.model_manager is not None:
        await app_state.model_manager.stop()


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI application
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cerebro API", version="1.0.0", lifespan=lifespan, dependencies=[Depends(_verify_api_key)]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
api = APIRouter(prefix="/api")


def _build_metadata(
    total_latency_ms: float,
    model_name: str,
    provider_name: str,
    warnings: list[str],
) -> ResponseMetadata:
    return ResponseMetadata(
        inference_latency_ms=total_latency_ms,
        total_latency_ms=total_latency_ms,
        model_used=model_name,
        provider_used=provider_name,
        warnings=warnings,
    )


def _meta_to_model(meta: ResponseMetadata) -> ResponseMetadataModel:
    pending: PendingToolModel | None = None
    if meta.pending_tool:
        pending = PendingToolModel(
            name=meta.pending_tool["name"],
            args=meta.pending_tool.get("args", {}),
        )
    return ResponseMetadataModel(
        sources_used=[
            SourceRefModel(path=s.path, chunk_index=s.chunk_index, score=s.score)
            for s in meta.sources_used
        ],
        tools_called=[
            ToolCallRecordModel(
                name=t.name,
                args_summary=t.args_summary,
                result_summary=t.result_summary,
                latency_ms=t.latency_ms,
                approved=t.approved,
            )
            for t in meta.tools_called
        ],
        memory_retrieved=[],
        inference_latency_ms=meta.inference_latency_ms,
        total_latency_ms=round(meta.total_latency_ms, 2),
        iterations=meta.iterations,
        model_used=meta.model_used,
        provider_used=meta.provider_used,
        warnings=meta.warnings,
        pipeline_stages_ms=meta.pipeline_stages_ms,
        pending_tool=pending,
    )


@api.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    if app_state.runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime not initialized. Start the llama.cpp server and reload.",
        )

    if req.agent == "auto":
        route = await app_state.router.route_with_llm(req.question)
        agent_id = route.agent_id
        query_text = route.query
    else:
        agent_id = req.agent
        query_text = req.question

    app_state.active_agent_id = agent_id
    app_state.metrics.set_active_agent(agent_id)

    # Resolve model name for metadata; ensure specialist is loaded when model swapping is active.
    model_name = "phi3:mini"
    provider_name = "unknown"
    warnings: list[str] = []
    if app_state.provider_registry is not None:
        try:
            if app_state.model_manager is not None:
                chat = await app_state.provider_registry.get_chat_for_agent(
                    agent_id, app_state.model_manager
                )
            else:
                chat = app_state.provider_registry.get_chat()
            model_name = chat.model_id()
            provider_name = app_state.provider_registry.primary_name
        except Exception:
            warnings.append("provider_fallback")

    # Resolve or create conversation session
    conv_id = req.conversation_id
    if conv_id is None or app_state.conv_store.get(conv_id) is None:
        conv_id = app_state.conv_store.create(agent_id)

    # Snapshot tool trace length before the run to isolate current-query calls.
    pre_trace_len = 0
    if app_state.runtime is not None:
        try:
            _pre = app_state.runtime._state_store.load(agent_id)
            pre_trace_len = len(_pre.tool_trace)
        except Exception:
            pass

    start = time.perf_counter()
    try:
        answer, final_state = await app_state.runtime.run(query_text, agent_id)
    except Exception as exc:
        logger.exception("Runtime error during /query")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    total_latency_ms = (time.perf_counter() - start) * 1000
    meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
    for tc in final_state.tool_trace[pre_trace_len:]:
        meta.tools_called.append(
            ToolCallRecord(
                name=tc.tool_name,
                args_summary=str(tc.args)[:100] if tc.args else "",
                result_summary=(tc.result or "")[:200],
                latency_ms=0.0,
                approved=True,
            )
        )

    # Store pending tool state and surface it in metadata so the frontend can show ConfirmModal.
    if final_state.pending_tool_name:
        app_state._pending_tools[conv_id] = {
            "tool_name": final_state.pending_tool_name,
            "tool_args": final_state.pending_tool_args or {},
            "agent_id": agent_id,
        }
        meta.pending_tool = {
            "name": final_state.pending_tool_name,
            "args": final_state.pending_tool_args or {},
        }

    app_state.metrics.record_query(meta)
    meta_model = _meta_to_model(meta)

    try:
        app_state.conv_store.append(conv_id, req.question, answer, meta_model.model_dump())
    except Exception:
        logger.exception("Failed to persist conversation turn for {}", conv_id)

    return QueryResponse(answer=answer, metadata=meta_model, conversation_id=conv_id)


@api.post("/query/stream")
async def query_stream_endpoint(req: QueryRequest) -> StreamingResponse:
    if app_state.runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime not initialized. Start the llama.cpp server and reload.",
        )

    if req.agent == "auto":
        route = await app_state.router.route_with_llm(req.question)
        agent_id = route.agent_id
        query_text = route.query
    else:
        agent_id = req.agent
        query_text = req.question

    app_state.active_agent_id = agent_id
    app_state.metrics.set_active_agent(agent_id)

    model_name = "phi3:mini"
    provider_name = "unknown"
    warnings: list[str] = []
    # When model_manager is active, resolve model identity inside each generator
    # so we can emit a specialist_loading SSE event before the blocking load.
    if app_state.provider_registry is not None and app_state.model_manager is None:
        try:
            chat = app_state.provider_registry.get_chat()
            model_name = chat.model_id()
            provider_name = app_state.provider_registry.primary_name
        except Exception:
            warnings.append("provider_fallback")

    stream_conv_id = req.conversation_id
    if stream_conv_id is None or app_state.conv_store.get(stream_conv_id) is None:
        stream_conv_id = app_state.conv_store.create(agent_id)

    # Use runtime.run() (tool loop) for any agent with tools; stream() for tool-less agents.
    # Checking confirmation-required tools only was a bug: calendar/academic/code agents
    # need run() regardless of whether they have destructive tools.
    pre_trace_len = 0
    uses_tools = False
    try:
        _pre = app_state.runtime._state_store.load(agent_id)
        uses_tools = bool(_pre.profile.authorized_tools)
        pre_trace_len = len(_pre.tool_trace)
    except Exception:
        pass

    start = time.perf_counter()

    if uses_tools:

        async def event_generator_tools():
            nonlocal model_name, provider_name, warnings
            if app_state.model_manager is not None and app_state.provider_registry is not None:
                yield f"data: {json.dumps({'event': 'specialist_loading'})}\n\n"
                try:
                    _chat = await app_state.provider_registry.get_chat_for_agent(
                        agent_id, app_state.model_manager
                    )
                    model_name = _chat.model_id()
                    provider_name = "llamacpp"
                except Exception:
                    warnings.append("provider_fallback")
            try:
                answer, final_state = await app_state.runtime.run(query_text, agent_id)
            except Exception as exc:
                logger.exception("Runtime error during /query/stream (tools path)")
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Simulate streaming word by word.
            words = answer.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'token': token})}\n\n"

            total_latency_ms = (time.perf_counter() - start) * 1000
            meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
            for tc in final_state.tool_trace[pre_trace_len:]:
                meta.tools_called.append(
                    ToolCallRecord(
                        name=tc.tool_name,
                        args_summary=str(tc.args)[:100] if tc.args else "",
                        result_summary=(tc.result or "")[:200],
                        latency_ms=0.0,
                        approved=True,
                    )
                )

            if final_state.pending_tool_name:
                app_state._pending_tools[stream_conv_id] = {
                    "tool_name": final_state.pending_tool_name,
                    "tool_args": final_state.pending_tool_args or {},
                    "agent_id": agent_id,
                }
                meta.pending_tool = {
                    "name": final_state.pending_tool_name,
                    "args": final_state.pending_tool_args or {},
                }

            app_state.metrics.record_query(meta)
            meta_model = _meta_to_model(meta)

            try:
                app_state.conv_store.append(
                    stream_conv_id, query_text, answer, meta_model.model_dump()
                )
            except Exception:
                logger.exception("Failed to persist streaming (tools) turn for {}", stream_conv_id)

            yield f"data: {json.dumps({'metadata': meta_model.model_dump(), 'conversation_id': stream_conv_id})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator_tools(), media_type="text/event-stream")

    async def event_generator():
        nonlocal model_name, provider_name, warnings
        if app_state.model_manager is not None and app_state.provider_registry is not None:
            yield f"data: {json.dumps({'event': 'specialist_loading'})}\n\n"
            try:
                _chat = await app_state.provider_registry.get_chat_for_agent(
                    agent_id, app_state.model_manager
                )
                model_name = _chat.model_id()
                provider_name = "llamacpp"
            except Exception:
                warnings.append("provider_fallback")
        tokens: list[str] = []
        try:
            async for token in app_state.runtime.stream(query_text, agent_id):
                tokens.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.exception("Streaming error during /query/stream")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        total_latency_ms = (time.perf_counter() - start) * 1000
        meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
        app_state.metrics.record_query(meta)
        meta_model = _meta_to_model(meta)

        try:
            app_state.conv_store.append(
                stream_conv_id, query_text, "".join(tokens), meta_model.model_dump()
            )
        except Exception:
            logger.exception("Failed to persist streaming conversation turn for {}", stream_conv_id)

        yield f"data: {json.dumps({'metadata': meta_model.model_dump(), 'conversation_id': stream_conv_id})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api.post("/query/plan")
async def query_plan_endpoint(req: QueryRequest) -> StreamingResponse:
    """Execute a complex multi-step query using task decomposition.

    For complex queries, decomposes the task into steps and executes each
    sequentially, streaming progress. Falls back to regular run() for simple queries.
    """
    if app_state.runtime is None or app_state.planner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime or planner not initialized.",
        )

    if req.agent == "auto":
        route = await app_state.router.route_with_llm(req.question)
        agent_id = route.agent_id
        query_text = route.query
    else:
        agent_id = req.agent
        query_text = req.question

    app_state.active_agent_id = agent_id
    app_state.metrics.set_active_agent(agent_id)

    plan_conv_id = req.conversation_id
    if plan_conv_id is None or app_state.conv_store.get(plan_conv_id) is None:
        plan_conv_id = app_state.conv_store.create(agent_id)

    start = time.perf_counter()

    async def event_generator_plan():
        """Decompose query, execute plan sequentially, stream step progress."""
        try:
            # Check if task is complex; if not, fall back to single-step run()
            is_complex = app_state.planner.is_complex_task(query_text)
            if not is_complex:
                answer, final_state = await app_state.runtime.run(query_text, agent_id)
                yield f"data: {json.dumps({'step': 0, 'description': query_text[:100], 'total': 1})}\n\n"
                words = answer.split(" ")
                for i, word in enumerate(words):
                    token = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {json.dumps({'step': 0, 'token': token})}\n\n"
            else:
                # Decompose into steps
                steps = await app_state.planner.decompose(query_text)
                total_steps = len(steps)

                # Execute each step sequentially
                for step_idx, step_text in enumerate(steps):
                    yield f"data: {json.dumps({'step': step_idx, 'description': step_text[:100], 'total': total_steps})}\n\n"

                    answer, final_state = await app_state.runtime.run(step_text, agent_id)

                    # Stream tokens for this step's answer
                    words = answer.split(" ")
                    for i, word in enumerate(words):
                        token = word + (" " if i < len(words) - 1 else "")
                        yield f"data: {json.dumps({'step': step_idx, 'token': token})}\n\n"

            # Emit final metadata
            total_latency_ms = (time.perf_counter() - start) * 1000
            model_name = "unknown"
            provider_name = "unknown"
            warnings: list[str] = []

            try:
                if app_state.provider_registry is not None:
                    chat = app_state.provider_registry.get_chat()
                    model_name = chat.model_id()
                    provider_name = app_state.provider_registry.primary_name
            except Exception:
                warnings.append("provider_fallback")

            meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
            app_state.metrics.record_query(meta)
            meta_model = _meta_to_model(meta)

            yield f"data: {json.dumps({'plan_complete': True, 'metadata': meta_model.model_dump(), 'conversation_id': plan_conv_id})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.exception("Error in /query/plan")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator_plan(), media_type="text/event-stream")


@api.post("/tool-confirm", response_model=QueryResponse)
async def tool_confirm_endpoint(req: ToolConfirmRequest) -> QueryResponse:
    """Resume a paused agent run by approving or denying its pending tool call."""
    pending = app_state._pending_tools.pop(req.conversation_id, None)
    if pending is None:
        raise HTTPException(
            status_code=404, detail="No pending tool confirmation for this conversation"
        )

    tool_name: str = pending["tool_name"]
    tool_args: dict = pending["tool_args"]

    model_name = "phi3:mini"
    provider_name = "unknown"
    warnings: list[str] = []
    if app_state.provider_registry is not None:
        try:
            chat = app_state.provider_registry.get_chat()
            model_name = chat.model_id()
            provider_name = app_state.provider_registry.primary_name
        except Exception:
            warnings.append("provider_fallback")

    start = time.perf_counter()

    if req.decision == "deny":
        answer = f"Entendido. No ejecutaré `{tool_name}`. ¿En qué más puedo ayudarte?"
        approved = False
        result_summary = "denied by user"
    else:
        if app_state.runtime is None:
            raise HTTPException(status_code=503, detail="Runtime not initialized")
        try:
            handler = app_state.runtime._tool_registry.get(tool_name)
            if handler is None:
                raise ValueError(f"Tool '{tool_name}' not in registry")
            if inspect.iscoroutinefunction(handler):
                result_text = str(await handler(**tool_args))
            else:
                result_text = str(await asyncio.to_thread(handler, **tool_args))
        except Exception as exc:
            result_text = f"Error: {exc}"
            logger.exception("Tool '{}' failed during confirmation-approved execution", tool_name)
        answer = f"Herramienta `{tool_name}` ejecutada:\n{result_text}"
        approved = True
        result_summary = result_text[:200]

    total_latency_ms = (time.perf_counter() - start) * 1000
    meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
    meta.tools_called.append(
        ToolCallRecord(
            name=tool_name,
            args_summary=str(tool_args)[:100],
            result_summary=result_summary,
            latency_ms=total_latency_ms,
            approved=approved,
        )
    )
    app_state.metrics.record_query(meta)
    meta_model = _meta_to_model(meta)

    try:
        app_state.conv_store.append(
            req.conversation_id, "[tool-confirm]", answer, meta_model.model_dump()
        )
    except Exception:
        logger.exception("Failed to persist tool-confirm turn for {}", req.conversation_id)

    return QueryResponse(answer=answer, metadata=meta_model, conversation_id=req.conversation_id)


async def _run_index_job(job_id: str, paths: list[str]) -> None:
    job = app_state._index_jobs[job_id]
    try:
        file_count = 0
        for raw_path in paths:
            p = Path(raw_path).expanduser()
            if p.is_file():
                file_count += 1
            elif p.is_dir():
                file_count += sum(1 for f in p.rglob("*") if f.is_file())
        job.files_indexed = file_count
        job.status = "done"
        logger.info("Index job {} completed: {} files", job_id, file_count)
    except Exception as exc:
        job.status = "error"
        job.message = str(exc)
        logger.exception("Index job {} failed", job_id)


@api.post("/index", response_model=IndexResponse)
async def index_endpoint(req: IndexRequest) -> IndexResponse:
    job_id = str(uuid.uuid4())
    app_state._index_jobs[job_id] = _IndexJob()
    asyncio.create_task(_run_index_job(job_id, req.paths))
    logger.info("Index job {} queued for {} paths", job_id, len(req.paths))
    return IndexResponse(status="started", job_id=job_id)


@api.get("/index/status", response_model=IndexStatusResponse)
async def index_status_endpoint(job_id: str) -> IndexStatusResponse:
    job = app_state._index_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return IndexStatusResponse(
        job_id=job_id,
        status=job.status,
        files_indexed=job.files_indexed,
        message=job.message,
    )


@api.get("/status", response_model=StatusResponse)
async def status_endpoint() -> StatusResponse:
    vm = psutil.virtual_memory()
    ram_total_gb = vm.total / (1024**3)
    ram_available_gb = vm.available / (1024**3)
    ram_used_gb = ram_total_gb - ram_available_gb

    engine_ok = False
    model_name = "—"
    active_provider = "unknown"
    context_window = 0
    if app_state.provider_registry is not None:
        try:
            chat = app_state.provider_registry.get_chat()
            engine_ok = chat.is_available()
            model_name = chat.model_id()
            active_provider = app_state.provider_registry.primary_name
            context_window = chat.context_window()
        except Exception:
            pass

    indexed_files = 0
    if app_state.vector_store is not None:
        try:
            indexed_files = len(app_state.vector_store.get_indexed_files())
        except Exception:
            pass

    stats = app_state.metrics.get_stats()

    specialist_role: str | None = None
    specialist_loaded = False
    if app_state.model_manager is not None:
        s = app_state.model_manager.specialist_status
        specialist_role = s["role"]
        specialist_loaded = s["loaded"]

    current_model_id = None
    current_model_quant = None
    current_model_params_b = None
    hardware_snapshot = None
    selection_rationale = None
    if app_state.fleet_orchestrator is not None:
        sel = app_state.fleet_orchestrator.current_selection
        if sel is not None:
            current_model_id = sel.model.id
            current_model_quant = sel.model.quant
            current_model_params_b = sel.model.params_b
            selection_rationale = sel.rationale
            if app_state.fleet_orchestrator._hw_snapshot is not None:
                hw = app_state.fleet_orchestrator._hw_snapshot
                hardware_snapshot = {
                    "ram_total_gb": round(hw.ram_total_gb, 2),
                    "ram_available_gb": round(hw.ram_available_gb, 2),
                    "cpu_count": hw.cpu_count,
                    "cpu_percent": hw.cpu_percent,
                    "gpu_backend": hw.gpu_backend,
                    "gpu_vram_total_gb": round(hw.gpu_vram_total_gb, 2),
                    "gpu_vram_available_gb": round(hw.gpu_vram_available_gb, 2),
                    "unified_memory": hw.unified_memory,
                }

    return StatusResponse(
        indexed_files=indexed_files,
        engine_ok=engine_ok,
        model=model_name,
        provider=active_provider,
        active_agent=app_state.active_agent_id,
        ram_used_gb=round(ram_used_gb, 2),
        ram_available_gb=round(ram_available_gb, 2),
        queries_total=stats.queries_total,
        avg_latency_ms=stats.avg_latency_ms,
        p95_latency_ms=stats.p95_latency_ms,
        tool_call_count=stats.tool_call_count,
        memory_hits=stats.memory_hits,
        provider_fallbacks=stats.provider_fallbacks,
        specialist_role=specialist_role,
        specialist_loaded=specialist_loaded,
        current_model_id=current_model_id,
        current_model_quant=current_model_quant,
        current_model_params_b=current_model_params_b,
        hardware_snapshot=hardware_snapshot,
        selection_rationale=selection_rationale,
        context_window=context_window,
    )


@api.get("/cache/embedding-stats", response_model=EmbeddingCacheStatsResponse)
async def embedding_cache_stats() -> EmbeddingCacheStatsResponse:
    if app_state.embedding_provider is None:
        return EmbeddingCacheStatsResponse(
            hits=0, misses=0, hit_rate_percent=0.0, size=0, max_size=0
        )
    try:
        stats = app_state.embedding_provider.get_cache_stats()
        return EmbeddingCacheStatsResponse(**stats)
    except Exception as e:
        logger.warning("Failed to get embedding cache stats: {}", e)
        return EmbeddingCacheStatsResponse(
            hits=0, misses=0, hit_rate_percent=0.0, size=0, max_size=0
        )


@api.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations() -> list[ConversationSummary]:
    records = app_state.conv_store.list_all()
    result: list[ConversationSummary] = []
    for r in records:
        first_user_msg = next((t.content for t in r.turns if t.role == "user"), "")
        result.append(
            ConversationSummary(
                conv_id=r.conv_id,
                agent_id=r.agent_id,
                started_at=r.started_at,
                last_active=r.last_active,
                message_count=len(r.turns),
                first_user_message=first_user_msg[:120],
            )
        )
    return result


@api.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(conv_id: str) -> ConversationDetail:
    record = app_state.conv_store.get(conv_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
    messages: list[ConversationMessage] = []
    for t in record.turns:
        meta: ResponseMetadataModel | None = None
        if t.metadata:
            try:
                meta = ResponseMetadataModel(**t.metadata)
            except Exception:
                pass
        messages.append(
            ConversationMessage(
                role=t.role,
                content=t.content,
                timestamp=t.timestamp,
                metadata=meta,
            )
        )
    return ConversationDetail(
        conv_id=record.conv_id,
        agent_id=record.agent_id,
        started_at=record.started_at,
        last_active=record.last_active,
        messages=messages,
    )


@api.get("/config")
async def get_config() -> dict[str, Any]:
    return app_state._config


@api.patch("/config")
async def patch_config(settings: dict[str, Any] = Body(...)) -> dict[str, Any]:
    app_state._config.update(settings)

    if "model" in settings and app_state.provider_registry is not None:
        model_name: str = settings["model"]
        registry = app_state.provider_registry

        target = "llamacpp"
        if "mlx" in registry.available_providers():
            if registry.get_chat("mlx").model_id() == model_name:
                target = "mlx"

        if target == "llamacpp" and "llamacpp" in registry.available_providers():
            registry.get_chat("llamacpp").set_model(model_name)  # type: ignore[union-attr]

        registry.set_primary(target)

    app_state._save_config()
    return app_state._config


@api.get("/models")
async def list_models() -> dict[str, Any]:
    models: list[dict[str, Any]] = []

    # MLX model — prepend if registered
    if app_state.provider_registry is not None:
        if "mlx" in app_state.provider_registry.available_providers():
            try:
                mlx_chat = app_state.provider_registry.get_chat("mlx")
                models.append(
                    {
                        "name": mlx_chat.model_id(),
                        "size_gb": 0,
                        "provider": "mlx",
                    }
                )
            except Exception:
                pass

    # llama.cpp GGUF models
    if _LLAMA_CPP_MODELS_DIR.is_dir():
        for gguf in sorted(_LLAMA_CPP_MODELS_DIR.glob("*.gguf")):
            models.append(
                {
                    "name": gguf.name,
                    "size_gb": round(gguf.stat().st_size / 1_073_741_824, 1),
                    "provider": "llamacpp",
                }
            )

    # Active model from registry
    active_model: str | None = None
    if app_state.provider_registry is not None:
        try:
            active_model = app_state.provider_registry.get_chat().model_id()
        except Exception:
            pass

    return {"models": models, "active_model": active_model}


@api.get("/llama-cpp/models")
async def list_llama_cpp_models() -> dict[str, Any]:
    models: list[dict[str, Any]] = []
    if _LLAMA_CPP_MODELS_DIR.is_dir():
        for gguf in sorted(_LLAMA_CPP_MODELS_DIR.glob("*.gguf")):
            size_gb = round(gguf.stat().st_size / 1_073_741_824, 1)
            models.append({"name": gguf.name, "size_gb": size_gb, "provider": "llama_cpp"})

    active_model: str | None = None
    if app_state.model_manager is not None:
        mm_status = app_state.model_manager.specialist_status
        if mm_status.get("loaded") and mm_status.get("role"):
            active_model = mm_status["role"]

    return {"models": models, "active_model": active_model}


app.include_router(api)

# ──────────────────────────────────────────────────────────────────────────────
# Wizard router  (/api/wizard/*)
# ──────────────────────────────────────────────────────────────────────────────

_LLAMA_CPP_BASE = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080")
_LLAMA_CPP_MODELS_DIR = Path(
    os.getenv("CEREBRO_MODELS_DIR", str(Path(__file__).parent.parent.parent / "bin" / "models"))
).expanduser()

wizard = APIRouter(prefix="/api/wizard")


def _wizard_claude_mode() -> bool:
    return os.getenv("CEREBRO_INFERENCE_BACKEND", "llamacpp").lower() == "claude"


async def _llamacpp_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{_LLAMA_CPP_BASE}/health")
            return r.status_code == 200
    except Exception:
        return False


@wizard.get("/status", response_model=WizardStatusResponse)
async def wizard_status() -> WizardStatusResponse:
    if _wizard_claude_mode():
        has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        return WizardStatusResponse(
            is_first_launch=not app_state._wizard_done,
            engine_running=True,
            model_pulled=has_key,
            folders_configured=bool(app_state._config.get("watched_folders")),
        )
    running = await _llamacpp_running()
    models_ok = (
        any(_LLAMA_CPP_MODELS_DIR.glob("*.gguf")) if _LLAMA_CPP_MODELS_DIR.exists() else False
    )
    return WizardStatusResponse(
        is_first_launch=not app_state._wizard_done,
        engine_running=running,
        model_pulled=models_ok,
        folders_configured=bool(app_state._config.get("watched_folders")),
    )


@wizard.post("/check-llamacpp")
async def wizard_check_llamacpp() -> dict[str, Any]:
    if _wizard_claude_mode():
        return {
            "running": True,
            "status": "skipped",
            "reason": "Claude API mode — llama.cpp not needed for inference",
        }
    return {"running": await _llamacpp_running()}


@wizard.post("/check-models")
async def wizard_check_models() -> dict[str, Any]:
    if _wizard_claude_mode():
        has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        return {
            "ok": has_key,
            "status": "skipped",
            "message": (
                "ANTHROPIC_API_KEY is set — Claude API ready"
                if has_key
                else "Set ANTHROPIC_API_KEY for Claude API inference"
            ),
            "models": [],
        }
    if not _LLAMA_CPP_MODELS_DIR.exists():
        return {"ok": False, "detail": f"Models directory not found: {_LLAMA_CPP_MODELS_DIR}"}
    found = list(_LLAMA_CPP_MODELS_DIR.glob("*.gguf"))
    return {"ok": bool(found), "models": [f.name for f in found]}


@wizard.post("/set-folders")
async def wizard_set_folders(body: SetFoldersRequest) -> dict[str, bool]:
    app_state._config["watched_folders"] = body.folders
    return {"ok": True}


@wizard.post("/complete")
async def wizard_complete() -> dict[str, bool]:
    app_state._wizard_done = True
    app_state._save_wizard_state()
    return {"ok": True}


app.include_router(wizard)
