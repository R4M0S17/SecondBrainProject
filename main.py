"""Cerebro — entry point."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os

import uvicorn

from core.agents.context_enricher import ContextEnricher
from core.agents.llm_router import LLMRouter
from core.agents.planner import TaskPlanner
from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.agents.state_store import AgentStateStore
from core.cache.embedding_cache import CachedEmbeddingProvider, EmbeddingCache
from core.inference.model_manager import ModelManager
from core.inference.platform import mlx_available
from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider
from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
from core.inference.registry import ProviderRegistry
from core.memory.context_builder import ContextBuilder
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from core.tools.registry import (
    ToolRegistry,
    register_calendar_tools,
    register_filesystem_tools,
    register_macos_tools,
)
from ui.tray.server import app, app_state

DB_PATH = os.path.expanduser(os.getenv("CEREBRO_DB", "~/.cerebro/db"))
STATE_DIR = os.path.expanduser(os.getenv("CEREBRO_STATE", "~/.cerebro/state"))
PORT = int(os.getenv("CEREBRO_PORT", "7842"))
RAM_PRIMARY_GB = float(os.getenv("CEREBRO_RAM_PRIMARY_GB", "1.0"))
RAM_FALLBACK_GB = float(os.getenv("CEREBRO_RAM_FALLBACK_GB", "0.3"))
MLX_MODEL = os.getenv("CEREBRO_MLX_MODEL", "mlx-community/Phi-4-mini-instruct-4bit")
MLX_ENABLED = os.getenv("CEREBRO_MLX_ENABLED", "auto")  # "auto" | "true" | "false"
INFERENCE_BACKEND = os.getenv("CEREBRO_INFERENCE_BACKEND", "llamacpp")  # "llamacpp" | "mlx"
LLAMACPP_URL = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080")
LLAMACPP_EMBED_URL = os.getenv("CEREBRO_LLAMACPP_EMBED_URL", "http://127.0.0.1:8082")
LLAMACPP_MODEL = os.getenv("CEREBRO_LLAMACPP_MODEL", "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf")
LLAMACPP_PROFILE = os.getenv("CEREBRO_LLAMACPP_PROFILE", "chat")
LLAMACPP_SIMPLE = os.getenv("CEREBRO_LLAMACPP_SIMPLE", "false").lower() == "true"

CEREBRO_FILES_PATH = os.path.expanduser(os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles"))
AUTHORIZED_READ_PATHS = [
    os.path.expanduser("~/Desktop/Javier/SecondBrain"),
    CEREBRO_FILES_PATH,
]
AUTHORIZED_WRITE_PATHS = [CEREBRO_FILES_PATH]
PROACTIVE_CONTEXT = os.getenv("CEREBRO_PROACTIVE_CONTEXT", "true").lower() == "true"


def _build_app_state() -> None:
    from loguru import logger

    from core.inference.fleet.orchestrator import FleetOrchestrator

    # Fleet orchestration for intelligent startup model selection
    fleet = FleetOrchestrator()
    fleet_selection = fleet.select_on_startup()
    app_state.fleet_orchestrator = fleet

    if fleet_selection:
        logger.info("Fleet: {}", fleet_selection.rationale)

    registry = ProviderRegistry(
        ram_threshold_primary_gb=RAM_PRIMARY_GB,
        ram_threshold_fallback_gb=RAM_FALLBACK_GB,
    )

    model_manager: ModelManager | None = None
    llm_router: LLMRouter | None = None
    use_mlx = (MLX_ENABLED == "true") or (MLX_ENABLED == "auto" and mlx_available())

    if INFERENCE_BACKEND == "llamacpp":
        if LLAMACPP_SIMPLE:
            embed_base = LlamaCppEmbeddingProvider(base_url=LLAMACPP_EMBED_URL)
            embed = CachedEmbeddingProvider(embed_base, EmbeddingCache(max_size=200))
            llamacpp_chat = LlamaCppChatProvider(
                model=LLAMACPP_MODEL,
                base_url=LLAMACPP_URL,
                profile=LLAMACPP_PROFILE,
            )
            registry.register("llamacpp", llamacpp_chat, embed)
            registry.set_primary("llamacpp")
            if use_mlx:
                from core.inference.providers.mlx_provider import (
                    MlxChatProvider,
                    MlxEmbeddingProviderStub,
                )

                registry.register(
                    "mlx", MlxChatProvider(model_repo=MLX_MODEL), MlxEmbeddingProviderStub()
                )
                logger.info("Inference: llama.cpp simple → {} | MLX secondary", LLAMACPP_URL)
            else:
                logger.info("Inference: llama.cpp simple → {}", LLAMACPP_URL)
        else:
            model_manager = ModelManager()
            llm_router = LLMRouter()
            app_state.model_manager = model_manager

            embed_base = LlamaCppEmbeddingProvider(base_url=model_manager.embed_url)
            embed = CachedEmbeddingProvider(embed_base, EmbeddingCache(max_size=200))
            llamacpp_chat = LlamaCppChatProvider(
                model=LLAMACPP_MODEL,
                base_url=model_manager.specialist_url,
                profile=LLAMACPP_PROFILE,
            )
            registry.register("llamacpp", llamacpp_chat, embed)
            if use_mlx:
                from core.inference.providers.mlx_provider import (
                    MlxChatProvider,
                    MlxEmbeddingProviderStub,
                )

                registry.register(
                    "mlx", MlxChatProvider(model_repo=MLX_MODEL), MlxEmbeddingProviderStub()
                )
                logger.info(
                    "Inference: llama.cpp model swapping (specialist {}, embeddings {}) | MLX secondary",
                    model_manager.specialist_url,
                    model_manager.embed_url,
                )
            else:
                logger.info(
                    "Inference: llama.cpp model swapping (specialist {}, embeddings {})",
                    model_manager.specialist_url,
                    model_manager.embed_url,
                )
    else:
        # MLX-only mode (CEREBRO_INFERENCE_BACKEND=mlx)
        if not use_mlx:
            raise RuntimeError(
                "No inference backend available. "
                "Set CEREBRO_INFERENCE_BACKEND=llamacpp or ensure MLX is available on Apple Silicon."
            )
        from core.inference.providers.mlx_provider import MlxChatProvider, MlxEmbeddingProviderStub

        embed_base = LlamaCppEmbeddingProvider(base_url=LLAMACPP_EMBED_URL)
        embed = CachedEmbeddingProvider(embed_base, EmbeddingCache(max_size=200))
        registry.register("mlx", MlxChatProvider(model_repo=MLX_MODEL), MlxEmbeddingProviderStub())
        logger.info("Inference: MLX only")

    vector_store = VectorStore(db_path=DB_PATH)
    state_store = AgentStateStore(state_dir=STATE_DIR)

    short_term = ShortTermStore()
    long_term = LongTermStore(vector_store=vector_store, agent_id=GENERAL_AGENT_ID, embed=embed)
    context_builder = ContextBuilder(short_term=short_term, long_term=long_term)

    cal_registry = ToolRegistry()
    register_calendar_tools(cal_registry)
    register_filesystem_tools(
        cal_registry,
        authorized_read_paths=AUTHORIZED_READ_PATHS,
        authorized_write_paths=AUTHORIZED_WRITE_PATHS,
    )
    register_macos_tools(cal_registry)

    app_state.cerebro_files_path = CEREBRO_FILES_PATH
    app_state.authorized_read_paths = AUTHORIZED_READ_PATHS
    app_state.authorized_write_paths = AUTHORIZED_WRITE_PATHS

    # A8: Context enricher for proactive ambient context injection
    enricher = ContextEnricher(
        authorized_read_paths=AUTHORIZED_READ_PATHS,
        cerebro_files_path=CEREBRO_FILES_PATH,
        enabled=PROACTIVE_CONTEXT,
    )

    runtime = AgentRuntime(
        registry=registry,
        state_store=state_store,
        context_builder=context_builder,
        tool_registry=cal_registry.handlers(),
        tool_definitions=cal_registry.definitions(),
        enricher=enricher,
    )

    # A7: Task planner for multi-step decomposition
    planner = TaskPlanner(runtime)

    router = SpecializedAgentRouter(llm_router=llm_router)
    router.ensure_profiles(state_store)

    app_state.runtime = runtime
    app_state.vector_store = vector_store
    app_state.provider_registry = registry
    app_state.router = router
    app_state.enricher = enricher
    app_state.planner = planner
    app_state.embedding_provider = embed


if __name__ == "__main__":
    _build_app_state()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
