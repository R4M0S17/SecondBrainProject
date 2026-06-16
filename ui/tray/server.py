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
import re
import signal
import subprocess
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import psutil

# Tuned pool limits: prevents socket exhaustion under concurrent requests.
# max_connections=20 gives headroom for bursts; max_keepalive=10 keeps warm
# sockets ready; keepalive_expiry=30s matches llama-server's keep-alive window.
_HTTP_POOL_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30.0,
)

from fastapi import (
    APIRouter,
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Security,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from loguru import logger
from pydantic import BaseModel, Field

from core.agents.conversation_store import ConversationStore
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.inference.inference_warnings import clear_inference_warnings, consume_inference_warnings
from core.inference.ram_preflight import RAM_WARNING_CRITICAL, collect_ram_warnings
from core.ingestion.pipeline import IngestionPipeline
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector, ResponseMetadata, ToolCallRecord
from core.tools.handlers.upload import process_uploaded_file
from ui.tray.wizard import recommend_lite_profile

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


class FileAttachment(BaseModel):
    filename: str
    mime_type: str
    content: str  # Contains raw text for docs/PDFs, or base64 for images
    type: str  # "pdf", "image", "text", or "unknown"


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    agent: str = GENERAL_AGENT_ID
    conversation_id: str | None = None
    attachments: list[FileAttachment] | None = None


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


class HealthResponse(BaseModel):
    llama_server: Literal["up", "restarting", "down"]
    last_restart_at: str | None = None
    restart_count_session: int = 0
    message: str | None = None


class StatusResponse(BaseModel):
    indexed_files: int
    engine_ok: bool
    model: str
    provider: str
    active_agent: str
    ram_pressure: Literal["ok", "warn", "critical"] = "ok"
    ram_total_gb: float = 0.0
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
    cpu_percent: float = 0.0
    hardware_snapshot: dict[str, Any] | None = None
    selection_rationale: str | None = None
    context_window: int = 0
    macos_permissions: dict[str, str] | None = None


class WizardStatusResponse(BaseModel):
    is_first_launch: bool
    engine_running: bool
    model_pulled: bool
    folders_configured: bool
    recommend_lite: bool = False


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


class FleetModeRequest(BaseModel):
    mode: Literal["auto", "pinned"]
    pinned_model_id: str | None = None


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
        self.rag_engine: Any = None  # RAGQueryEngine | None
        self.inference_engine: Any = None  # InferenceEngine | None
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
        self.macos_permissions: dict[str, str] = {"calendar": "unknown"}
        self.ram_monitor: RamMonitor = RamMonitor()
        self.llama_health_monitor: Any = None
        self.time_travel_recorder: Any = None
        self.recorder: Any = None
        self.workflow_store: Any = None
        # Maps conversation_id → llama-server slot_id for KV cache reuse.
        self._active_slots: dict[str, int] = {}
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


async def _start_component_in_background(name: str, starter) -> None:
    try:
        await starter()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("{} failed to start", name)


def _build_inference_engine(app: FastAPI, model: str) -> Any:
    """Construct an InferenceEngine backed by the shared connection pool."""
    from core.inference.engine import InferenceEngine

    return InferenceEngine(
        model=model,
        base_url=os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080"),
        http_client=getattr(app.state, "http_client", None),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Shared HTTP client — created ONCE, lives for the entire server process ──
    http_client = httpx.AsyncClient(
        limits=_HTTP_POOL_LIMITS,
        timeout=httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0),
    )
    app.state.http_client = http_client
    logger.info("Shared httpx.AsyncClient initialised (pool: {})", _HTTP_POOL_LIMITS)

    try:
        from core.observability.macos_perms import probe_calendar_permission

        app_state.macos_permissions["calendar"] = await probe_calendar_permission()
    except Exception:
        logger.exception("macOS calendar permission probe failed")
        app_state.macos_permissions["calendar"] = "unknown"

    startup_tasks: list[asyncio.Task[Any]] = []
    if app_state.embedding_provider is not None:
        cache = getattr(app_state.embedding_provider, "_cache", None)
        if cache is not None:
            startup_tasks.append(
                asyncio.create_task(
                    _start_component_in_background("EmbeddingCache.load", cache.load_from_store)
                )
            )
            startup_tasks.append(
                asyncio.create_task(
                    _start_component_in_background("EmbeddingCache.sweep", cache.sweep_expired)
                )
            )
    if app_state.model_manager is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background("ModelManager", app_state.model_manager.start)
            )
        )

    if app_state.llama_health_monitor is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background(
                    "LlamaServerHealthMonitor", app_state.llama_health_monitor.start
                )
            )
        )

    if app_state.time_travel_recorder is not None:
        app_state.time_travel_recorder.start()

    yield  # ── server is live ──────────────────────────────────────────────────

    # Graceful shutdown: cancel background tasks first, then close the HTTP pool.
    for task in startup_tasks:
        task.cancel()
    for task in startup_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass

    if app_state.llama_health_monitor is not None:
        await app_state.llama_health_monitor.stop()
    if app_state.model_manager is not None:
        await app_state.model_manager.stop()
    if app_state.time_travel_recorder is not None:
        app_state.time_travel_recorder.enforce_retention()
        await app_state.time_travel_recorder.shutdown()
    if app_state.recorder is not None:
        try:
            app_state.recorder.stop()
        except Exception:
            pass
    if app_state.workflow_store is not None:
        app_state.workflow_store.close()

    await http_client.aclose()
    logger.info("Shared httpx.AsyncClient closed cleanly")


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


def _safe_dest(path: Path) -> Path:
    """Ensure destination path doesn't overwrite existing files."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


# Dedicated secure file upload endpoint (STEP 1 implementation)
@api.post("/files/upload")
async def upload_files_endpoint(files: list[UploadFile] = File(...)) -> list[dict[str, Any]]:
    """Upload and pre-process documents/images safely.

    Reuses existing core.tools.handlers.upload extraction logic.

    Adds server-side validation and size limits to prevent abuse and DB bloat.
    """
    # Limits
    MAX_SINGLE_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file
    MAX_TOTAL_UPLOAD_BYTES = 30 * 1024 * 1024  # 30 MB total per request

    ALLOWED_MIMES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }

    parsed_attachments: list[dict[str, Any]] = []
    total_bytes = 0

    for file in files:
        # Basic content-type whitelist
        if file.content_type and file.content_type not in ALLOWED_MIMES:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {file.content_type}"
            )

        # Create a safe temporary file matching the suffix of the original upload
        suffix = Path(file.filename).suffix if file.filename else ""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
                # Stream file into temp file and enforce per-file + total limits
                while True:
                    chunk = file.file.read(8192)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    total_bytes += len(chunk)

                    if total_bytes > MAX_TOTAL_UPLOAD_BYTES:
                        # Clean up and respond with 413
                        raise HTTPException(status_code=413, detail="Total upload size exceeded")

                    if tmp.tell() > MAX_SINGLE_FILE_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File '{file.filename or 'unknown'}' exceeds single-file size limit",
                        )
                tmp.flush()

            # Reuses the existing high-quality tool validator & processor
            result = process_uploaded_file(
                temp_path,
                authorized_paths=app_state.authorized_read_paths,
                enforce_authorization=False,
            )

            if isinstance(result, dict) and "error" in result:
                raise HTTPException(status_code=400, detail=result["error"])

            parsed_attachments.append(
                {
                    "filename": file.filename or "unknown",
                    "mime_type": result.get("metadata", {}).get(
                        "mime_type", "application/octet-stream"
                    ),
                    "content": result.get("content"),
                    "type": result.get("type", "unknown"),
                }
            )

        finally:
            # Guarantee temporary file is deleted immediately from disk
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    return parsed_attachments


class SentenceBuffer:
    """Buffers tokens and flushes at short intervals for progressive display.

    Emits tokens progressively to simulate typing effect. Flushes on:
    sentence-ending punctuation, newlines, max chars exceeded, or max age exceeded.
    """

    def __init__(self, max_chars: int = 30, max_age_ms: int = 50) -> None:
        self._buf: list[str] = []
        self._max_chars = max_chars
        self._max_age_ms = max_age_ms
        self._last_flush = 0.0

    def add(self, token: str) -> str | None:
        self._buf.append(token)
        text = "".join(self._buf)
        age_ms = (time.monotonic() - self._last_flush) * 1000 if self._last_flush > 0 else 0.0
        if (
            len(text) >= self._max_chars
            or text.rstrip().endswith((".", "!", "?", "\n", ",", ";", ":"))
            or (self._last_flush > 0 and age_ms >= self._max_age_ms)
        ):
            return self.flush()
        return None

    def flush(self) -> str:
        result = "".join(self._buf)
        self._buf.clear()
        self._last_flush = time.monotonic()
        return result


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


def _build_augmented_question(
    question: str,
    attachments: list[FileAttachment] | None,
) -> str:
    if not attachments:
        return question

    max_total_chars = 12_000
    max_chars_per_file = 4_000
    remaining = max_total_chars
    context_parts = [
        "[Instruction]",
        "La pregunta del usuario se refiere a los archivos adjuntos. Usa su contenido para responder.",
        "[User Question]",
        question,
        "[Attached Files Context]",
    ]
    for att in attachments:
        if att.type == "image":
            context_parts.append(
                f"[File: {att.filename} (IMAGE)]\nMIME-Type: {att.mime_type}\n"
                "Nota: imagen adjunta enviada al modelo como dato multimodal."
            )
            continue

        if remaining <= 0:
            context_parts.append("[Context truncated: attachment limit reached]")
            break

        content = att.content or ""
        allowed = min(max_chars_per_file, remaining)
        clipped = content[:allowed]
        remaining -= len(clipped)
        truncated = len(content) > len(clipped)
        trunc_note = "\n[Attachment truncated for prompt size]" if truncated else ""
        context_parts.append(
            f"[File: {att.filename}]\nMIME-Type: {att.mime_type}\nContent:\n{clipped}{trunc_note}"
        )

    return "\n\n".join(context_parts)


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
    model_name = app_state._config.get("model", "Qwen3.5-2B-UD-Q4_K_XL.gguf")
    provider_name = "unknown"
    warnings: list[str] = []
    clear_inference_warnings()
    await _apply_ram_pressure_warnings(warnings)
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
    text_attachments = [a for a in (req.attachments or []) if a.type != "image"]
    image_attachments = [
        {"filename": a.filename, "mime_type": a.mime_type, "content": a.content, "type": a.type}
        for a in (req.attachments or [])
        if a.type == "image"
    ]
    augmented_question = _build_augmented_question(query_text, text_attachments)

    try:
        answer, final_state = await app_state.runtime.run(
            augmented_question,
            agent_id,
            conversation_id=conv_id,
            intent_query=query_text,
            attachments=image_attachments,
        )
    except Exception as exc:
        logger.exception("Runtime error during /query")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    total_latency_ms = (time.perf_counter() - start) * 1000
    warnings.extend(consume_inference_warnings())
    meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
    for tc in final_state.tool_trace[pre_trace_len:]:
        meta.tools_called.append(
            ToolCallRecord(
                name=tc.tool_name,
                args_summary=str(tc.args)[:100] if tc.args else "",
                result_summary=(tc.result or "")[:200],
                latency_ms=tc.latency_ms,
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
        history_question = req.question
        if getattr(req, "attachments", None):
            filenames = ", ".join(
                att.filename for att in req.attachments if getattr(att, "filename", None)
            )
            history_question = f"{req.question}\n\n[Attached files: {filenames}]"
        app_state.conv_store.append(conv_id, history_question, answer, meta_model.model_dump())
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

    model_name = app_state._config.get("model", "Qwen3.5-2B-UD-Q4_K_XL.gguf")
    provider_name = "unknown"
    warnings: list[str] = []
    clear_inference_warnings()
    await _apply_ram_pressure_warnings(warnings)
    # When model_manager is active, resolve model identity inside each generator
    # so we can emit a specialist_loading SSE event before the blocking load.
    if app_state.provider_registry is not None and app_state.model_manager is None:
        try:
            chat = app_state.provider_registry.get_chat()
            model_name = chat.model_id()
            provider_name = app_state.provider_registry.primary_name
        except Exception:
            warnings.append("provider_fallback")

    if req.agent == "auto":
        route = await app_state.router.route_with_llm(req.question)
        agent_id = route.agent_id
        query_text = route.query
    else:
        agent_id = req.agent
        query_text = req.question

    app_state.active_agent_id = agent_id
    app_state.metrics.set_active_agent(agent_id)

    stream_conv_id = req.conversation_id
    if stream_conv_id is None or app_state.conv_store.get(stream_conv_id) is None:
        stream_conv_id = app_state.conv_store.create(agent_id)

    # Separate image attachments for multimodal support
    text_attachments = [a for a in (req.attachments or []) if a.type != "image"]
    image_attachments_stream = [
        {"filename": a.filename, "mime_type": a.mime_type, "content": a.content, "type": a.type}
        for a in (req.attachments or [])
        if a.type == "image"
    ]
    # Build augmented question for streaming endpoint (LLM context only)
    augmented_question = _build_augmented_question(query_text, text_attachments)

    # Phase 2: always use runtime.run() (tool loop) for /query/stream so live-data
    # questions invoke tools; token streaming is simulated from the final answer.
    pre_trace_len = 0
    try:
        _pre = app_state.runtime._state_store.load(agent_id)
        pre_trace_len = len(_pre.tool_trace)
    except Exception:
        pass

    start = time.perf_counter()

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
            from core.agents.runtime import ContextSourcesEvent, StreamRunComplete

            slot_id_in = app_state._active_slots.get(stream_conv_id)
            answer_parts: list[str] = []
            final_state = None
            live_streamed = False
            buf = SentenceBuffer()
            async for chunk in app_state.runtime.run_streaming(
                augmented_question,
                agent_id,
                conversation_id=stream_conv_id,
                intent_query=query_text,
                slot_id=slot_id_in,
                attachments=image_attachments_stream,
            ):
                if isinstance(chunk, ContextSourcesEvent):
                    yield f"data: {json.dumps({'type': 'context_sources', 'sources': chunk.sources, 'episode_count': chunk.episode_count})}\n\n"
                    continue
                if isinstance(chunk, StreamRunComplete):
                    remaining = buf.flush()
                    if remaining:
                        answer_parts.append(remaining)
                        yield f"data: {json.dumps({'token': remaining})}\n\n"
                    final_state = chunk.final_state
                    if not answer_parts:
                        answer_parts = [chunk.answer]
                    break
                live_streamed = True
                answer_parts.append(chunk)
                flushed = buf.add(chunk)
                if flushed is not None:
                    yield f"data: {json.dumps({'token': flushed})}\n\n"

            if final_state is None:
                raise RuntimeError("run_streaming ended without StreamRunComplete")
            answer = "".join(answer_parts)

            if not live_streamed:
                words = answer.split(" ")
                for i, word in enumerate(words):
                    token = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except asyncio.CancelledError:
            logger.info("Client disconnected during streaming for conv={}", stream_conv_id)
            return
        except Exception as exc:
            logger.exception("Runtime error during /query/stream (tools path)")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        total_latency_ms = (time.perf_counter() - start) * 1000
        warnings.extend(consume_inference_warnings())
        meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)
        for tc in final_state.tool_trace[pre_trace_len:]:
            meta.tools_called.append(
                ToolCallRecord(
                    name=tc.tool_name,
                    args_summary=str(tc.args)[:100] if tc.args else "",
                    result_summary=(tc.result or "")[:200],
                    latency_ms=tc.latency_ms,
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
            history_question = query_text
            if getattr(req, "attachments", None):
                filenames = ", ".join(
                    att.filename for att in req.attachments if getattr(att, "filename", None)
                )
                history_question = f"{query_text}\n\n[Attached files: {filenames}]"
            app_state.conv_store.append(
                stream_conv_id, history_question, answer, meta_model.model_dump()
            )
        except Exception:
            logger.exception("Failed to persist streaming (tools) turn for {}", stream_conv_id)

        yield f"data: {json.dumps({'metadata': meta_model.model_dump(), 'conversation_id': stream_conv_id})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator_tools(), media_type="text/event-stream")


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
                answer, final_state = await app_state.runtime.run(
                    query_text, agent_id, conversation_id=plan_conv_id
                )
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

                    answer, final_state = await app_state.runtime.run(
                        step_text, agent_id, conversation_id=plan_conv_id
                    )

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

    model_name = app_state._config.get("model", "Qwen3.5-2B-UD-Q4_K_XL.gguf")
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
        pipeline = IngestionPipeline()
        total = 0
        for raw_path in paths:
            p = Path(raw_path).expanduser()
            if p.is_file():
                total += await _ingest_file(p, pipeline)
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file() and f.suffix.lower() in {".pdf", ".txt", ".md", ".py", ".docx"}:
                        total += await _ingest_file(f, pipeline)
        job.files_indexed = total
        job.status = "done"
        logger.info("Index job {} completed: {} chunks indexed", job_id, total)
    except Exception as exc:
        job.status = "error"
        job.message = str(exc)
        logger.exception("Index job {} failed", job_id)


async def _ingest_file(path: Path, pipeline: IngestionPipeline) -> int:
    if app_state.vector_store is None or app_state.inference_engine is None:
        return 0
    try:
        docs = pipeline.ingest(str(path))
        if not docs:
            return 0
        count = await app_state.vector_store.upsert(docs, app_state.inference_engine)
        logger.debug("Indexed {} chunks from {}", count, path.name)
        return count
    except Exception as exc:
        logger.warning("Failed to index {}: {}", path.name, exc)
        return 0


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


async def _apply_ram_pressure_warnings(warnings: list[str]) -> None:
    """Record RAM pressure in metadata; purge embedding cache when critical."""
    codes = collect_ram_warnings(app_state.ram_monitor)
    for code in codes:
        if code not in warnings:
            warnings.append(code)
    if RAM_WARNING_CRITICAL in codes and app_state.embedding_provider is not None:
        cache = getattr(app_state.embedding_provider, "_cache", None)
        if cache is not None:
            await cache.clear()


@api.get("/documents")
async def list_documents_endpoint() -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if app_state.vector_store is not None:
        try:
            indexed = app_state.vector_store.get_indexed_files()
            for source_path, file_modified in sorted(
                indexed.items(), key=lambda x: x[1], reverse=True
            ):
                files.append(
                    {
                        "source_path": source_path,
                        "file_modified": file_modified,
                        "filename": Path(source_path).name,
                    }
                )
        except Exception as exc:
            logger.warning("Failed to list documents: {}", exc)
    return files


@api.delete("/documents")
async def delete_document_endpoint(source_path: str) -> dict[str, Any]:
    if app_state.vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store not available")
    try:
        count = app_state.vector_store.delete_by_source(source_path)
        return {"deleted": count, "source_path": source_path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@api.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    if app_state.llama_health_monitor is None:
        return HealthResponse(
            llama_server="up",
            last_restart_at=None,
            restart_count_session=0,
            message=None,
        )
    snap = app_state.llama_health_monitor.snapshot()
    return HealthResponse(
        llama_server=snap.llama_server,
        last_restart_at=snap.last_restart_at,
        restart_count_session=snap.restart_count_session,
        message=snap.message,
    )


@api.get("/engine/activity")
async def engine_activity_endpoint() -> dict:
    return {
        "engine_state": (
            getattr(app_state, "engine_suspender", None).state
            if hasattr(app_state, "engine_suspender") and app_state.engine_suspender
            else "unknown"
        )
    }


@api.get("/status", response_model=StatusResponse)
async def status_endpoint() -> StatusResponse:
    cpu_percent = psutil.cpu_percent(interval=0)
    ram_snap = app_state.ram_monitor.snapshot()
    ram_total_gb = ram_snap["total_gb"]
    ram_available_gb = ram_snap["available_gb"]
    ram_used_gb = ram_snap["used_gb"]
    ram_pressure = ram_snap["pressure"]

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
        ram_pressure=ram_pressure,
        ram_total_gb=round(ram_total_gb, 2),
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
        cpu_percent=cpu_percent,
        hardware_snapshot=hardware_snapshot,
        selection_rationale=selection_rationale,
        context_window=context_window,
        macos_permissions=dict(app_state.macos_permissions),
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


def _fleet_hardware_payload(hw: Any) -> dict[str, Any]:
    from core.inference.fleet.hardware_monitor import HardwareSnapshot

    if not isinstance(hw, HardwareSnapshot):
        raise TypeError("expected HardwareSnapshot")
    ram_used = max(0.0, hw.ram_total_gb - hw.ram_available_gb)
    ram_pressure_pct = round((ram_used / hw.ram_total_gb) * 100, 1) if hw.ram_total_gb > 0 else 0.0
    gpu_backend = hw.gpu_backend if hw.gpu_backend in ("metal", "cuda", "none") else "none"
    return {
        "ram_total_gb": round(hw.ram_total_gb, 2),
        "ram_available_gb": round(hw.ram_available_gb, 2),
        "ram_pressure_pct": ram_pressure_pct,
        "gpu_backend": gpu_backend,
        "gpu_vram_total_gb": round(hw.gpu_vram_total_gb, 2),
        "gpu_vram_available_gb": round(hw.gpu_vram_available_gb, 2),
        "unified_memory": hw.unified_memory,
    }


def _fleet_model_entry(model: Any) -> dict[str, Any]:
    from core.inference.fleet.model_registry import ModelConfig

    if not isinstance(model, ModelConfig):
        raise TypeError("expected ModelConfig")
    path = Path(model.path).expanduser()
    return {
        "id": model.id,
        "family": model.family,
        "path": model.path,
        "params_b": model.params_b,
        "quant": model.quant,
        "ram_required_gb": model.ram_required_gb,
        "vram_required_gb": model.vram_required_gb,
        "gpu_layers": model.gpu_layers,
        "context_length": model.context_length,
        "capabilities": list(model.capabilities),
        "speed_tokens_per_sec": model.speed_tokens_per_sec,
        "available_on_disk": path.exists(),
    }


def _require_fleet() -> Any:
    fleet = app_state.fleet_orchestrator
    if fleet is None:
        raise HTTPException(status_code=503, detail="Fleet orchestrator not initialised")
    return fleet


@api.get("/fleet/status")
async def fleet_status() -> dict[str, Any]:
    fleet = _require_fleet()
    sel = fleet.current_selection
    if sel is None:
        sel = fleet.select_on_startup()
    if sel is None:
        raise HTTPException(status_code=503, detail="No fleet models configured")
    hw = fleet._hw_snapshot
    if hw is None:
        from core.inference.fleet.hardware_monitor import snapshot

        hw = snapshot()
        fleet._hw_snapshot = hw
    return {
        "mode": app_state._config.get("fleet_mode", fleet.mode),
        "current_model": _fleet_model_entry(sel.model),
        "hardware": _fleet_hardware_payload(hw),
        "swap_in_progress": False,
        "swap_target_model_id": None,
        "model_swaps_session": fleet.swaps_session_count,
        "selection_rationale": sel.rationale,
    }


@api.get("/fleet/models")
async def fleet_models() -> dict[str, Any]:
    fleet = _require_fleet()
    models = fleet.list_models()
    active = fleet.current_selection.model.id if fleet.current_selection else ""
    return {
        "models": [_fleet_model_entry(m) for m in models],
        "active_model_id": active,
    }


@api.patch("/fleet/config")
async def fleet_config(req: FleetModeRequest) -> dict[str, Any]:
    fleet = _require_fleet()
    app_state._config["fleet_mode"] = req.mode
    if req.mode == "pinned":
        if not req.pinned_model_id:
            raise HTTPException(
                status_code=400,
                detail="pinned_model_id is required when mode is pinned",
            )
        try:
            fleet.pin_model(req.pinned_model_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app_state._config["fleet_pinned_model_id"] = req.pinned_model_id
    else:
        fleet.use_auto_selection()
        app_state._config.pop("fleet_pinned_model_id", None)
    app_state._save_config()
    return app_state._config


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

        # Hot-switch the running llama-server to the selected model
        prev_model = app_state._config.get("model")
        if target == "llamacpp" and app_state.model_manager is None and model_name != prev_model:
            try:
                await _switch_llamacpp_model(model_name)
            except Exception:
                logger.exception("Failed to hot-switch model")

    if "inference_backend" in settings and app_state.provider_registry is not None:
        backend: str = settings["inference_backend"]
        registry = app_state.provider_registry
        if backend in registry.available_providers():
            registry.set_primary(backend)
            logger.info("Inference backend switched to '{}'", backend)
            # Persist to desktop.json so choice survives restart
            try:
                _desktop_cfg_path = Path.home() / ".cerebro" / "desktop.json"
                if _desktop_cfg_path.is_file():
                    _dcfg = json.loads(_desktop_cfg_path.read_text())
                    _dcfg["inference_backend"] = backend
                    _desktop_cfg_path.write_text(json.dumps(_dcfg, indent=2))
                    logger.info("Persisted inference_backend='{}' to desktop.json", backend)
            except Exception:
                logger.warning("Failed to persist inference_backend to desktop.json")
        else:
            logger.warning(
                "Backend '{}' not available (registered: {})",
                backend,
                registry.available_providers(),
            )

    if "watched_folders" in settings and app_state.runtime is not None:
        from functools import partial

        from core.tools.handlers.filesystem import list_directory, read_file, search_files

        startup_reads = list(app_state.authorized_read_paths or [])
        merged_reads = list(dict.fromkeys(startup_reads + list(settings["watched_folders"])))
        app_state.authorized_read_paths = merged_reads
        tr = app_state.runtime._tool_registry
        if "read_file" in tr:
            tr["read_file"] = partial(read_file, authorized_paths=merged_reads)
        if "list_directory" in tr:
            tr["list_directory"] = partial(list_directory, authorized_paths=merged_reads)
        if "search_files" in tr:
            tr["search_files"] = partial(search_files, authorized_paths=merged_reads)

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

    # llama.cpp GGUF models (from all model dirs)
    for m in _find_all_gguf():
        models.append(
            {
                "name": m["name"],
                "size_gb": m["size_gb"],
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
    models = _find_all_gguf()
    active_model: str | None = None
    if app_state.model_manager is not None:
        mm_status = app_state.model_manager.specialist_status
        if mm_status.get("loaded") and mm_status.get("role"):
            active_model = mm_status["role"]

    return {"models": models, "active_model": active_model}


# ── Tool Registry Browser ───────────────────────────────────────────


@api.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """Return all registered tool definitions with permission state."""
    if app_state.runtime is None:
        return []
    tools: list[dict[str, Any]] = []
    config = app_state._config
    tool_perms = config.get("tool_permissions", {})
    for name, td in app_state.runtime._tool_definitions.items():
        enabled = True
        if name == "web_search":
            enabled = tool_perms.get("search_web", False)
        elif td.required_permission in ("tools.fs.write", "tools.calendar.write"):
            enabled = tool_perms.get("write_file", True)
        elif td.required_permission == "tools.fs.read":
            enabled = tool_perms.get("read_file", True)
        elif td.required_permission == "tools.automation.record":
            enabled = tool_perms.get("execute_python", True)
        tools.append(
            {
                "name": td.name,
                "description": td.description,
                "required_permission": td.required_permission,
                "requires_confirmation": td.requires_confirmation,
                "scope": td.scope.value,
                "audit_level": td.audit_level.value,
                "enabled": enabled,
                "parameters": td.parameters,
            }
        )
    return tools


app.include_router(api)

# ──────────────────────────────────────────────────────────────────────────────
# Debug router  (/api/debug/runs)  —  Time-Travel Debugger
# ──────────────────────────────────────────────────────────────────────────────


class DebugRunModel(BaseModel):
    id: str
    agent_id: str
    query: str
    conversation_id: str | None = None
    created_at: float
    duration_ms: float | None = None
    success: bool = False


class DebugStepModel(BaseModel):
    id: str
    run_id: str
    step_number: int
    node_name: str
    input_preview: str | None = None
    output_preview: str | None = None
    tool_name: str | None = None
    tool_args_json: str | None = None
    tool_result_preview: str | None = None
    needs_confirmation: bool = False
    timestamp: float


debug = APIRouter(prefix="/api/debug")


@debug.get("/runs", response_model=list[DebugRunModel])
async def debug_list_runs(limit: int = 50, offset: int = 0):
    if app_state.time_travel_recorder is None:
        return []
    return app_state.time_travel_recorder.get_runs(limit=limit, offset=offset)


@debug.get("/runs/{run_id}/steps", response_model=list[DebugStepModel])
async def debug_run_steps(run_id: str):
    if app_state.time_travel_recorder is None:
        return []
    return app_state.time_travel_recorder.get_run_steps(run_id)


@debug.get("/steps/{step_id}")
async def debug_step_detail(step_id: str):
    if app_state.time_travel_recorder is None:
        raise HTTPException(status_code=404, detail="Recorder not available")
    detail = app_state.time_travel_recorder.get_step_detail(step_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return detail


app.include_router(debug)

# ──────────────────────────────────────────────────────────────────────────────
# Workflow router  (/api/workflows/*)  —  Desktop Automation
# ──────────────────────────────────────────────────────────────────────────────

wf = APIRouter(prefix="/api/workflows")


@wf.get("", response_model=list[dict])
async def workflow_list():
    if app_state.workflow_store is None:
        return []
    return app_state.workflow_store.list_all()


@wf.get("/{wf_id}", response_model=dict | None)
async def workflow_get(wf_id: str):
    if app_state.workflow_store is None:
        raise HTTPException(status_code=404, detail="Workflow store not available")
    w = app_state.workflow_store.get(wf_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return w


@wf.delete("/{wf_id}")
async def workflow_delete(wf_id: str):
    if app_state.workflow_store is None:
        raise HTTPException(status_code=404, detail="Workflow store not available")
    ok = app_state.workflow_store.delete(wf_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True}


@wf.post("/{wf_id}/run")
async def workflow_run(wf_id: str):
    if app_state.workflow_store is None:
        raise HTTPException(status_code=404, detail="Workflow store not available")
    from core.automation.tools import make_run_workflow

    handler = make_run_workflow(app_state.workflow_store)
    result = await handler(workflow_id=wf_id)
    return {"result": result}


app.include_router(wf)

# ──────────────────────────────────────────────────────────────────────────────
# Wizard router  (/api/wizard/*)
# ──────────────────────────────────────────────────────────────────────────────

_LLAMA_CPP_BASE = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080")
_LLAMA_CPP_MODELS_DIR = Path(
    os.getenv("CEREBRO_MODELS_DIR", str(Path(__file__).parent.parent.parent / "bin" / "models"))
).expanduser()


def _find_all_gguf() -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    dirs = [_LLAMA_CPP_MODELS_DIR]

    root_dir = _LLAMA_CPP_MODELS_DIR.parent.parent
    for candidate in [root_dir / "cerebro" / "bin" / "models", root_dir / "bin" / "models"]:
        if candidate.is_dir() and candidate.resolve() != _LLAMA_CPP_MODELS_DIR.resolve():
            dirs.append(candidate)
            break

    for d in dirs:
        if not d.is_dir():
            continue
        for gguf in sorted(d.glob("*.gguf")):
            if gguf.name.startswith("mmproj"):
                continue
            if gguf.name not in seen:
                seen.add(gguf.name)
                try:
                    size_gb = round(gguf.stat().st_size / 1_073_741_824, 1)
                except (OSError, FileNotFoundError):
                    continue
                models.append({"name": gguf.name, "size_gb": size_gb, "provider": "llama_cpp"})
    return models


def _kill_process_on_port(port: int) -> bool:
    try:
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                os.kill(int(pid), signal.SIGTERM)
            return True
    except Exception:
        pass
    return False


def _find_mmproj(models_dir: Path) -> Path | None:
    for f in sorted(models_dir.glob("mmproj*.gguf")):
        return f
    return None


def _update_args_mmproj(args_file: Path) -> None:
    content = args_file.read_text()
    # Remove any existing --mmproj line
    content = re.sub(r"^--mmproj\s+.*$\n?", "", content, flags=re.MULTILINE)
    mmproj_path = _find_mmproj(_LLAMA_CPP_MODELS_DIR)
    if mmproj_path is not None:
        root = _LLAMA_CPP_MODELS_DIR.parent.parent
        rel = mmproj_path.relative_to(root)
        content += f"--mmproj {rel}\n"
    args_file.write_text(content)


async def _switch_llamacpp_model(model_name: str) -> None:
    root = _LLAMA_CPP_MODELS_DIR.parent.parent

    model_path: Path | None = None
    for base in [_LLAMA_CPP_MODELS_DIR, root / "cerebro" / "bin" / "models"]:
        candidate = base / model_name
        if candidate.is_file() or candidate.is_symlink():
            model_path = candidate
            break

    if model_path is None:
        raise FileNotFoundError(f"Model GGUF not found: {model_name}")

    rel_path = model_path.relative_to(root)

    args_file = root / "config" / "chat.args"
    if args_file.is_file():
        content = args_file.read_text()
        content = re.sub(
            r"^--model\s+.*$",
            f"--model {rel_path}",
            content,
            flags=re.MULTILINE,
        )
        args_file.write_text(content)
        _update_args_mmproj(args_file)

    killed = _kill_process_on_port(8080)
    if killed:
        await asyncio.sleep(1)

    engine_script = root / "bin" / "start_engine.sh"
    if engine_script.is_file():
        subprocess.Popen(
            ["bash", str(engine_script), "chat"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
        for attempt in range(30):
            try:
                r = await client.get(f"{_LLAMA_CPP_BASE}/health")
                if r.status_code == 200:
                    logger.info("llama-server is healthy after model switch to {}", model_name)
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
        logger.error(
            "llama-server did not become healthy within 60s after switching to {}", model_name
        )


wizard = APIRouter(prefix="/api/wizard")


def _wizard_claude_mode() -> bool:
    return os.getenv("CEREBRO_INFERENCE_BACKEND", "llamacpp").lower() == "claude"


async def _llamacpp_running(
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Check llama.cpp health, reusing the shared connection pool when available."""
    timeout = httpx.Timeout(3.0)
    try:
        if client is not None:
            r = await client.get(f"{_LLAMA_CPP_BASE}/health", timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.get(f"{_LLAMA_CPP_BASE}/health")
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
            recommend_lite=recommend_lite_profile(),
        )
    running = await _llamacpp_running(
        client=getattr(app_state, "http_client", None),
    )
    models_ok = (
        any(_LLAMA_CPP_MODELS_DIR.glob("*.gguf")) if _LLAMA_CPP_MODELS_DIR.exists() else False
    )
    return WizardStatusResponse(
        is_first_launch=not app_state._wizard_done,
        engine_running=running,
        model_pulled=models_ok,
        folders_configured=bool(app_state._config.get("watched_folders")),
        recommend_lite=recommend_lite_profile(),
    )


@wizard.post("/check-llamacpp")
async def wizard_check_llamacpp() -> dict[str, Any]:
    if _wizard_claude_mode():
        return {
            "running": True,
            "status": "skipped",
            "reason": "Claude API mode — llama.cpp not needed for inference",
        }
    return {
        "running": await _llamacpp_running(
            client=getattr(app_state, "http_client", None),
        )
    }


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
    found = [f for f in _LLAMA_CPP_MODELS_DIR.glob("*.gguf") if not f.name.startswith("mmproj")]
    return {"ok": bool(found), "models": [f.name for f in found]}


@wizard.post("/reprobe-calendar-permission")
async def wizard_reprobe_calendar_permission() -> dict[str, str]:
    """Re-run the Calendar Automation probe (after user grants permission in Settings)."""
    from core.observability.macos_perms import probe_calendar_permission

    try:
        state = await probe_calendar_permission()
    except Exception:
        state = "unknown"
    app_state.macos_permissions["calendar"] = state
    return {"calendar": state}


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
