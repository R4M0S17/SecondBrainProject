"""Cerebro — entry point."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os
import re
import signal
import subprocess
import sys
from pathlib import Path

# Load persisted secrets (API keys) from ~/.cerebro/state/secrets.json
try:
    import json as _json

    _state_dir = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser()
    _secrets_path = _state_dir / "secrets.json"
    if _secrets_path.exists():
        for _k, _v in _json.loads(_secrets_path.read_text()).items():
            os.environ.setdefault(_k, _v)
except Exception:
    pass

# Auto-generate CEREBRO_API_KEY on first run
try:
    import json as _json
    import secrets as _secrets

    _state_dir = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser()
    _secrets_path = _state_dir / "secrets.json"
    if "CEREBRO_API_KEY" not in os.environ:
        _existing = {}
        if _secrets_path.exists():
            _existing = _json.loads(_secrets_path.read_text())
        if "CEREBRO_API_KEY" not in _existing:
            _new_key = f"ck_{_secrets.token_urlsafe(32)}"
            _existing["CEREBRO_API_KEY"] = _new_key
            _state_dir.mkdir(parents=True, exist_ok=True)
            _secrets_path.write_text(_json.dumps(_existing, indent=2))
            _secrets_path.chmod(0o600)
            os.environ["CEREBRO_API_KEY"] = _new_key
        else:
            os.environ.setdefault("CEREBRO_API_KEY", _existing["CEREBRO_API_KEY"])
except Exception:
    pass

import httpx
import numpy as np
import psutil
import uvicorn

from core.agents.context_enricher import ContextEnricher
from core.agents.llm_router import LLMRouter
from core.agents.planner import TaskPlanner
from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.agents.state_store import AgentStateStore
from core.cache.embedding_cache import CachedEmbeddingProvider, EmbeddingCache
from core.feature_flags import is_sandbox
from core.inference.embedding_factory import build_embedding_provider, default_embeddings_backend
from core.inference.engine import InferenceEngine
from core.inference.model_manager import ModelManager
from core.inference.platform import mlx_available
from core.inference.providers.llamacpp_provider import _VISION_MODEL_RE, LlamaCppChatProvider
from core.inference.registry import ProviderRegistry
from core.knowledge_sync.models import SyncSourceConfig
from core.knowledge_sync.orchestrator import KnowledgeSyncOrchestrator
from core.knowledge_sync.router import router as ks_router
from core.memory.context_builder import ContextBuilder
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from core.observability.time_travel import TimeTravelRecorder
from core.rag.query_engine import RAGQueryEngine
from core.reflection.reflector import Reflector
from core.tools.registry import (
    ToolRegistry,
    register_automation_tools,
    register_calendar_tools,
    register_filesystem_tools,
    register_macos_tools,
    register_math_tools,
    register_web_tools,
)
from core.utils.compressor import SemanticCompressor
from ui.tray.server import app, app_state


def _prompt_lite_profile() -> None:
    """If ≤10 GB RAM and running interactively, offer the lite-8gb profile."""
    if not sys.stdin.isatty():
        return
    if os.environ.get("CEREBRO_SKIP_LITE_PROMPT"):
        return
    # If user already set any CEREBRO_* env vars, they have their own config
    if any(k.startswith("CEREBRO_") for k in os.environ):
        return
    try:
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
    except Exception:
        return
    if total_ram_gb > 10:
        return

    print(f"\n💻 System RAM: {total_ram_gb:.0f} GB — lite-8gb profile recommended")
    print("   (local embeddings, no MLX, ContextEnricher off, lower RAM usage)")
    answer = input("Use lite profile? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        os.environ.setdefault("CEREBRO_LLAMACPP_SIMPLE", "true")
        os.environ.setdefault("CEREBRO_PROACTIVE_CONTEXT", "false")
        os.environ.setdefault("CEREBRO_MLX_ENABLED", "false")
        os.environ.setdefault("CEREBRO_EMBEDDINGS_BACKEND", "local")
        os.environ.setdefault("CEREBRO_RAM_PRIMARY_GB", "0.8")
        os.environ.setdefault("CEREBRO_RAM_FALLBACK_GB", "0.4")
        print("✅ lite-8gb profile activated\n")


_prompt_lite_profile()


def _prompt_language() -> None:
    if "CEREBRO_LOCALE" in os.environ or not sys.stdin.isatty():
        return
    print()
    answer = input("🌐 Language / Idioma [E]nglish / [S]panish [E]: ").strip().lower()
    if answer in ("s", "spanish", "español", "es"):
        os.environ["CEREBRO_LOCALE"] = "es"
        print("✅ Idioma: Español")
    else:
        os.environ["CEREBRO_LOCALE"] = "en"
        print("✅ Language: English")
    print()


_prompt_language()

# Sync locale + profile from persisted config.json if env not already set
_PROFILE_FROM_CONFIG = "normal"
try:
    _cfg_path = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser() / "config.json"
    if _cfg_path.exists():
        import json as _json

        _cfg = _json.loads(_cfg_path.read_text())
        if "locale" in _cfg and "CEREBRO_LOCALE" not in os.environ:
            os.environ["CEREBRO_LOCALE"] = str(_cfg["locale"])
        from core.feature_flags import (
            MAIN_CHAT_MODEL,
            LOW_POWER_CHAT_MODEL,
            apply_profile_guard,
            config_needs_low_power_migration,
            low_power_mode_enabled,
        )

        if config_needs_low_power_migration(_cfg):
            _cfg = apply_profile_guard(_cfg)
            _cfg_path.write_text(_json.dumps(_cfg, indent=2))
            _PROFILE_FROM_CONFIG = _cfg.get("profile") or "normal"
            _lp_model = _cfg.get("model") or LOW_POWER_CHAT_MODEL
            os.environ["CEREBRO_LLAMACPP_MODEL"] = _lp_model
        elif "CEREBRO_LLAMACPP_MODEL" not in os.environ:
            persisted = _cfg.get("model")
            if isinstance(persisted, str) and persisted:
                os.environ["CEREBRO_LLAMACPP_MODEL"] = persisted
            else:
                os.environ["CEREBRO_LLAMACPP_MODEL"] = MAIN_CHAT_MODEL
except Exception:
    pass

CEREBRO_HOST = os.getenv("CEREBRO_HOST", "127.0.0.1")
DB_PATH = os.path.expanduser(os.getenv("CEREBRO_DB", "~/.cerebro/db"))
STATE_DIR = os.path.expanduser(os.getenv("CEREBRO_STATE", "~/.cerebro/state"))
PORT = int(os.getenv("CEREBRO_PORT", "7842"))
EMBEDDING_CACHE_DB = os.path.join(DB_PATH, "embedding_cache.sqlite")
EMBEDDING_CACHE_TTL_DAYS = int(os.getenv("CEREBRO_EMBEDDING_CACHE_TTL_DAYS", "30"))
EMBEDDING_CACHE_TTL_SECONDS = EMBEDDING_CACHE_TTL_DAYS * 86400
RAM_PRIMARY_GB = float(os.getenv("CEREBRO_RAM_PRIMARY_GB", "1.0"))
RAM_FALLBACK_GB = float(os.getenv("CEREBRO_RAM_FALLBACK_GB", "0.3"))
MLX_MODEL = os.getenv("CEREBRO_MLX_MODEL", "mlx-community/Qwen3.5-2B-MLX-4bit")
MLX_ENABLED = os.getenv("CEREBRO_MLX_ENABLED", "auto")  # "auto" | "true" | "false"
INFERENCE_BACKEND = os.getenv(
    "CEREBRO_INFERENCE_BACKEND", "llamacpp"
)  # "llamacpp" | "mlx" | "claude"
LLAMACPP_URL = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080")
LLAMACPP_EMBED_URL = os.getenv("CEREBRO_LLAMACPP_EMBED_URL", "http://127.0.0.1:8082")
LLAMACPP_MODEL = os.getenv(
    "CEREBRO_LLAMACPP_MODEL",
    "Qwen3.5-2B-UD-Q4_K_XL.gguf",
)
LLAMACPP_PROFILE = os.getenv("CEREBRO_LLAMACPP_PROFILE", "chat")
LLAMACPP_ARGS_FILE = os.getenv("CEREBRO_LLAMACPP_ARGS_FILE", "config/chat.args")
LLAMACPP_SIMPLE = os.getenv("CEREBRO_LLAMACPP_SIMPLE", "true").lower() == "true"
REFLECTION_MODEL_URL = os.getenv("CEREBRO_REFLECTION_MODEL_URL", "")

CEREBRO_FILES_PATH = os.path.expanduser(os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles"))
Path(CEREBRO_FILES_PATH).mkdir(parents=True, exist_ok=True)


def _paths_from_env(var_name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return [os.path.expanduser(p) for p in defaults]
    return [os.path.expanduser(p.strip()) for p in raw.split(":") if p.strip()]


AUTHORIZED_READ_PATHS = _paths_from_env(
    "CEREBRO_AUTHORIZED_READ_PATHS",
    [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Desktop/Javier/SecondBrain"),
        CEREBRO_FILES_PATH,
    ],
)
AUTHORIZED_WRITE_PATHS = _paths_from_env(
    "CEREBRO_AUTHORIZED_WRITE_PATHS",
    [CEREBRO_FILES_PATH],
)
for _write_root in AUTHORIZED_WRITE_PATHS:
    Path(_write_root).mkdir(parents=True, exist_ok=True)

PROACTIVE_CONTEXT = os.getenv("CEREBRO_PROACTIVE_CONTEXT", "true").lower() == "true"
EMBED_MODEL = os.getenv("CEREBRO_LLAMACPP_EMBED_MODEL", "jina-embeddings")


def _make_embed_provider():
    return build_embedding_provider(embed_url=LLAMACPP_EMBED_URL, embed_model=EMBED_MODEL)


def _setup_llamacpp(
    *, embed_url: str, llm_url: str
) -> tuple[CachedEmbeddingProvider, LlamaCppChatProvider]:
    embed_base = build_embedding_provider(embed_url=embed_url, embed_model=EMBED_MODEL)
    embed = CachedEmbeddingProvider(
        embed_base,
        EmbeddingCache(
            max_size=200,
            persist_db_path=EMBEDDING_CACHE_DB,
            ttl_seconds=EMBEDDING_CACHE_TTL_SECONDS,
        ),
    )
    llamacpp_chat = LlamaCppChatProvider(
        model=LLAMACPP_MODEL,
        base_url=llm_url,
        profile=LLAMACPP_PROFILE,
    )
    return embed, llamacpp_chat


def _ensure_engine_running(engine_script: Path, profile: str = "normal") -> None:
    """Start llama-server on :8080 if not already healthy."""
    from core.feature_flags import auto_start_engine_enabled

    if not auto_start_engine_enabled():
        return

    import subprocess as _sp
    import time as _time

    # Retry a few times in case the launcher started the engine but it hasn't bound the port yet
    for attempt in range(3):
        try:
            pid = _sp.run(
                ["lsof", "-t", "-i", ":8080", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=5,
            )
            if pid.returncode == 0 and pid.stdout.strip():
                return  # Already running
        except Exception:
            pass
        if attempt < 2:
            _time.sleep(1)

    if engine_script.is_file():
        logger = __import__("loguru").logger
        logger.info("Engine not running — starting llama-server (profile: {})…", profile)
        engine_profile = "chat-lowpower" if profile == "low-power" else "chat"
        _sp.Popen(
            ["bash", str(engine_script), engine_profile],
            cwd=Path(__file__).parent,
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            start_new_session=True,
        )
        _time.sleep(1)


def _ensure_chat_args() -> None:
    """Ensure config/chat.args points to LLAMACPP_MODEL with mmproj for vision.

    If the file was stale (e.g. from a previous hot-swap), rewrite it and
    restart the engine so the new args take effect.
    """
    # Determine args file based on profile
    profile = _PROFILE_FROM_CONFIG
    low_power = os.getenv("CEREBRO_LOW_POWER_ENABLED", "").lower() in ("1", "true", "yes")
    if low_power:
        profile = "low-power"
    args_file = "config/chat-lowpower.args" if profile == "low-power" else "config/chat.args"
    args_path = Path(__file__).parent / args_file
    if not args_path.is_file():
        return
    content = args_path.read_text()
    # Strip comments — llama-server $(cat) would choke on them
    clean = re.sub(r"#.*$", "", content, flags=re.MULTILINE)
    clean = re.sub(r"\n\s*\n", "\n", clean).strip()
    # Ensure each flag is on its own line (fixes concatenated flags like
    # --log-disable--mmproj from previous _update_args_mmproj bugs)
    clean = re.sub(r"(?<=[^\n])--", r"\n--", clean).strip()
    model_line = f"--model bin/models/{LLAMACPP_MODEL}"
    new_content = re.sub(
        r"^--model\s+.*$",
        model_line,
        clean,
        flags=re.MULTILINE,
    )
    if _VISION_MODEL_RE.search(LLAMACPP_MODEL):
        if not re.search(r"^--mmproj\s+", new_content, re.MULTILINE):
            new_content += "\n--mmproj bin/models/mmproj-F16.gguf\n"
    else:
        new_content = re.sub(r"^--mmproj\s+.*$\n?", "", new_content, flags=re.MULTILINE)

    _engine_script = Path(__file__).parent / "bin" / "start_engine.sh"

    # Ensure --mmproj flag is present if the model is vision-capable
    def _ensure_mmproj(path: Path) -> None:
        if not _VISION_MODEL_RE.search(LLAMACPP_MODEL):
            return
        _content = path.read_text()
        if "--mmproj" not in _content:
            _mmproj_dir = Path(__file__).parent / "bin" / "models"
            _mmproj_files = sorted(_mmproj_dir.glob("mmproj*.gguf"))
            if _mmproj_files:
                with open(path, "a") as _f:
                    _f.write(f"--mmproj bin/models/{_mmproj_files[0].name}\n")

    _model_path = Path(__file__).parent / "bin" / "models" / LLAMACPP_MODEL
    if not _model_path.is_file():
        logger = __import__("loguru").logger
        logger.warning(
            "Model file not found: {} — skipping chat.args rewrite to avoid engine failure",
            _model_path,
        )
        _ensure_engine_running(_engine_script, profile)
        return

    if clean == new_content:
        _ensure_mmproj(args_path)
        _ensure_engine_running(_engine_script, profile)
        return

    args_path.write_text(new_content + "\n")
    _ensure_mmproj(args_path)
    logger = __import__("loguru").logger
    logger.info("chat.args was stale — rewrote to match {}. Restarting engine.", LLAMACPP_MODEL)
    try:
        import time as _time

        pid = subprocess.run(
            ["lsof", "-t", "-i", ":8080", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if pid.returncode == 0 and pid.stdout.strip():
            for p in pid.stdout.strip().split("\n"):
                try:
                    os.kill(int(p), signal.SIGTERM)
                except OSError:
                    pass
            _time.sleep(2)
        from core.feature_flags import auto_start_engine_enabled

        if auto_start_engine_enabled() and _engine_script.is_file():
            engine_profile = "chat-lowpower" if profile == "low-power" else "chat"
            subprocess.Popen(
                ["bash", str(_engine_script), engine_profile],
                cwd=Path(__file__).parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            logger.info("Engine restarted with {} (profile: {}). Waiting for health…", LLAMACPP_MODEL, profile)
            _time.sleep(1)
    except Exception as exc:
        logger.warning("Failed to restart engine after chat.args update: {}", exc)


def _build_app_state() -> None:
    from loguru import logger

    from core.inference.fleet.orchestrator import FleetOrchestrator

    if INFERENCE_BACKEND == "llamacpp":
        _ensure_chat_args()

    # ── EngineSuspender: SIGSTOP engine after inactivity ─────────────
    from core.inference.engine_suspender import EngineSuspender

    engine_suspender = EngineSuspender(timeout_s=180)
    if INFERENCE_BACKEND == "llamacpp":
        try:
            _pid = subprocess.run(
                ["lsof", "-t", "-i", ":8080", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if _pid.returncode == 0 and _pid.stdout.strip():
                first_pid = int(_pid.stdout.strip().split("\n")[0])
                engine_suspender.bind_pid(first_pid)
                engine_suspender.start_background()
            else:
                logger.info("EngineSuspender: no llama-server on :8080 — suspender idle")
        except Exception as exc:
            logger.warning("EngineSuspender: bind failed: {}", exc)
    app_state.engine_suspender = engine_suspender

    # ── AdaptiveContext: shrink ctx-size under RAM pressure ───────────
    from core.inference.adaptive_context import AdaptiveContext

    app_state.adaptive_ctx = AdaptiveContext()

    # ─────────────────────────────────────────────────────────────────

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

    if INFERENCE_BACKEND == "claude":
        from core.inference.providers.claude_api_provider import ClaudeApiChatProvider

        embed_base = _make_embed_provider()
        embed = CachedEmbeddingProvider(
            embed_base,
            EmbeddingCache(
                max_size=200,
                persist_db_path=EMBEDDING_CACHE_DB,
                ttl_seconds=EMBEDDING_CACHE_TTL_SECONDS,
            ),
        )
        claude_model = os.environ.get("CEREBRO_CLAUDE_MODEL", "claude-sonnet-4-6")
        chat_provider = ClaudeApiChatProvider(model=claude_model)
        registry.register("claude", chat_provider, embed)
        registry.set_primary("claude")
        logger.info("Inference: Claude API ({})", claude_model)
    elif INFERENCE_BACKEND == "llamacpp":
        model_manager = None
        llm_router = LLMRouter(base_url=LLAMACPP_URL, model=LLAMACPP_MODEL)
        app_state.model_manager = None
        use_simple = LLAMACPP_SIMPLE

        if not use_simple:
            try:
                model_manager = ModelManager()
                llm_router = LLMRouter(
                    base_url=model_manager.specialist_url,
                    model=LLAMACPP_MODEL,
                )
                app_state.model_manager = model_manager
            except FileNotFoundError as exc:
                logger.warning(
                    "Model swapping disabled — missing GGUF files ({}). "
                    "Falling back to simple llama.cpp at {}.",
                    exc,
                    LLAMACPP_URL,
                )
                use_simple = True

        logger.info(
            "llamacpp mode: simple={} (set CEREBRO_LLAMACPP_SIMPLE=false for model swapping)",
            use_simple,
        )

        if use_simple:
            embed_url = LLAMACPP_EMBED_URL
            llm_url = LLAMACPP_URL
        else:
            assert model_manager is not None
            embed_url = model_manager.embed_url
            llm_url = model_manager.specialist_url
        embed, llamacpp_chat = _setup_llamacpp(embed_url=embed_url, llm_url=llm_url)

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
            logger.info(
                "Inference: llama.cpp {} | MLX secondary",
                "model-swap" if not use_simple else f"simple → {LLAMACPP_URL}",
            )
        else:
            logger.info(
                "Inference: llama.cpp {}",
                "model-swap" if not use_simple else f"simple → {LLAMACPP_URL}",
            )
    else:
        # MLX-only mode (CEREBRO_INFERENCE_BACKEND=mlx)
        if not use_mlx:
            raise RuntimeError(
                "No inference backend available. "
                "Set CEREBRO_INFERENCE_BACKEND=llamacpp, CEREBRO_INFERENCE_BACKEND=claude "
                "(with ANTHROPIC_API_KEY), or ensure MLX is available on Apple Silicon."
            )

        # Kill any stale llama.cpp engine to free ~2.5 GB RAM
        try:
            _pid = subprocess.run(
                ["lsof", "-t", "-i", ":8080", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if _pid.returncode == 0 and _pid.stdout.strip():
                for p in _pid.stdout.strip().split("\n"):
                    try:
                        os.kill(int(p), signal.SIGTERM)
                        logger.info("Killed stale llama.cpp on :8080 to free RAM for MLX")
                    except OSError:
                        pass
                import time as _time

                _time.sleep(2)
        except Exception:
            pass

        from core.inference.providers.mlx_provider import MlxChatProvider, MlxEmbeddingProviderStub

        embed_base = _make_embed_provider()
        embed = CachedEmbeddingProvider(
            embed_base,
            EmbeddingCache(
                max_size=200,
                persist_db_path=EMBEDDING_CACHE_DB,
                ttl_seconds=EMBEDDING_CACHE_TTL_SECONDS,
            ),
        )
        registry.register("mlx", MlxChatProvider(model_repo=MLX_MODEL), MlxEmbeddingProviderStub())
        logger.info("Inference: MLX only")

    if "claude" in registry.available_providers() and registry.primary_name != "claude":
        registry.register_emergency("claude")
        logger.info("Emergency fallback provider: claude")

    embed_backend = default_embeddings_backend()
    logger.info(
        "Embeddings: {} (dim={}, embed server not required when backend=local)",
        embed_backend,
        embed.dimensions(),
    )

    vector_store = VectorStore(db_path=DB_PATH, embedding_dim=embed.dimensions())
    state_store = AgentStateStore(state_dir=STATE_DIR)

    short_term = ShortTermStore()
    long_term = LongTermStore(vector_store=vector_store, agent_id=GENERAL_AGENT_ID, embed=embed)

    llm_engine = InferenceEngine(
        model=LLAMACPP_MODEL,
        base_url=LLAMACPP_URL,
    )

    # ── Semantic Compressor ────────────────────────────────────────────
    compressor_embed_fn = None
    if os.getenv("CEREBRO_LLAMACPP_EMBED_URL"):
        try:
            resp = httpx.get(f"{LLAMACPP_EMBED_URL.rstrip('/')}/health", timeout=2.0)
            if resp.status_code == 200:

                async def _embed_for_compressor(texts: list[str]) -> np.ndarray:
                    results = []
                    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as _client:
                        for text in texts:
                            r = await _client.post(
                                f"{LLAMACPP_EMBED_URL.rstrip('/')}/v1/embeddings",
                                json={"model": EMBED_MODEL, "input": text},
                            )
                            r.raise_for_status()
                            results.append(r.json()["data"][0]["embedding"])
                    return np.array(results, dtype=np.float32)

                compressor_embed_fn = _embed_for_compressor
                logger.info(
                    "SemanticCompressor inicializado usando Path A (Neural) → {}",
                    LLAMACPP_EMBED_URL,
                )
            else:
                logger.warning(
                    "Embed server at {} responded {}, falling back to Path B (TF-IDF)",
                    LLAMACPP_EMBED_URL,
                    resp.status_code,
                )
        except Exception as exc:
            logger.warning(
                "Embed server at {} unreachable ({}), falling back to Path B (TF-IDF)",
                LLAMACPP_EMBED_URL,
                exc,
            )
    else:
        logger.info("SemanticCompressor inicializado usando Path B (TF-IDF)")

    compressor = SemanticCompressor(embed_fn=compressor_embed_fn)

    context_builder = ContextBuilder(
        short_term=short_term,
        long_term=long_term,
        vector_store=vector_store,
        inference_engine=llm_engine,
        embed_provider=embed,
        compressor=compressor,
    )

    rag_embed_fn = embed.embed if hasattr(embed, "embed") else None
    rag_engine = RAGQueryEngine(
        store=vector_store,
        engine=llm_engine,
        compressor=compressor,
        embed_fn=rag_embed_fn,
    )
    app_state.rag_engine = rag_engine

    # ── Knowledge Sync Orchestrator ────────────────────────────────────
    app_state.knowledge_sync_orchestrator = KnowledgeSyncOrchestrator(
        registry=registry,
        vector_store=vector_store,
        inference_engine=llm_engine,
        embed_provider=embed,
        state_dir=STATE_DIR,
        interest_tags=(
            os.getenv("CEREBRO_INTEREST_TAGS", "").split(",")
            if os.getenv("CEREBRO_INTEREST_TAGS")
            else None
        ),
    )

    app.include_router(ks_router)

    for src_cfg in app_state._config.get("knowledge_sync", {}).get("sources", []):
        app_state.knowledge_sync_orchestrator.add_source(SyncSourceConfig(**src_cfg))
    # ───────────────────────────────────────────────────────────────────

    # ── Desktop Automation (Recorder + Workflow Store) ────────────────
    from core.automation.recorder import Recorder
    from core.automation.workflow_store import WorkflowStore

    automation_db = os.path.join(DB_PATH, "automation.sqlite")
    recorder = Recorder()
    workflow_store = WorkflowStore(db_path=automation_db)
    app_state.recorder = recorder
    app_state.workflow_store = workflow_store
    # ────────────────────────────────────────────────────────────────────

    cal_registry = ToolRegistry()
    if not is_sandbox():
        register_calendar_tools(cal_registry)
        register_macos_tools(cal_registry)
        register_automation_tools(
            cal_registry,
            recorder=recorder,
            workflow_store=workflow_store,
            chat_provider_getter=lambda: registry.get_chat() if registry else None,
        )
    register_filesystem_tools(
        cal_registry,
        authorized_read_paths=AUTHORIZED_READ_PATHS,
        authorized_write_paths=AUTHORIZED_WRITE_PATHS,
    )
    register_math_tools(cal_registry)
    register_web_tools(cal_registry)

    from core.tools.security_audit import audit_confirmation_gates

    audit_issues = audit_confirmation_gates(cal_registry)
    if audit_issues:
        logger.warning("Security audit — state-changing tools without confirmation:")
        for issue in audit_issues:
            logger.warning(f"  • {issue}")
        if os.environ.get("CEREBRO_API_KEY") and CEREBRO_HOST in ("0.0.0.0", "::"):
            logger.critical("Security audit failed — refusing to start in production mode")
            raise SystemExit(1)

    if INFERENCE_BACKEND == "llamacpp":
        from core.agents.runtime import _SYSTEM_TEMPLATE
        from core.inference.prompt_cache import sync_prompt_cache

        tool_names = list(cal_registry.definitions().keys())
        bootstrap_prompt = _SYSTEM_TEMPLATE.format(
            agent_name="bootstrap",
            instructions="",
            current_date="<dynamic>",
            current_year="<dynamic>",
            session_summary="<dynamic>",
            memory_context="<dynamic>",
            document_context="",
            ambient_context="",
            available_tools_detail="<tools>",
        )
        sync_prompt_cache(bootstrap_prompt, tool_names, model_id=LLAMACPP_MODEL)

    app_state.cerebro_files_path = CEREBRO_FILES_PATH
    app_state.authorized_read_paths = AUTHORIZED_READ_PATHS
    app_state.authorized_write_paths = AUTHORIZED_WRITE_PATHS
    logger.info("Filesystem authorized read paths: {}", AUTHORIZED_READ_PATHS)
    logger.info("Filesystem authorized write paths: {}", AUTHORIZED_WRITE_PATHS)

    # A8: Context enricher for proactive ambient context injection
    enricher = ContextEnricher(
        authorized_read_paths=AUTHORIZED_READ_PATHS,
        cerebro_files_path=CEREBRO_FILES_PATH,
        enabled=PROACTIVE_CONTEXT and not is_sandbox(),
        macos_permissions=app_state.macos_permissions,
        language=os.getenv("CEREBRO_LOCALE", "en"),
    )

    time_travel_db = os.path.join(DB_PATH, "time_travel.sqlite")
    time_travel = TimeTravelRecorder(db_path=time_travel_db, ttl_days=7, max_runs=500)
    app_state.time_travel_recorder = time_travel

    # ── Reflection-Turn (optional small model for answer critique) ─────────
    _reflector_provider = None
    if REFLECTION_MODEL_URL:
        _reflector_provider = LlamaCppChatProvider(
            model="reflection",
            base_url=REFLECTION_MODEL_URL,
            profile="chat",
        )
    reflector = Reflector(provider=_reflector_provider, enabled=True)
    # ────────────────────────────────────────────────────────────────────────

    runtime = AgentRuntime(
        registry=registry,
        state_store=state_store,
        context_builder=context_builder,
        tool_registry=cal_registry.handlers(),
        tool_definitions=cal_registry.definitions(),
        enricher=enricher,
        conversation_store=app_state.conv_store,
        config_getter=lambda: app_state._config,
        time_travel_recorder=time_travel,
        reflector=reflector,
        engine_suspender=engine_suspender,
        authorized_read_paths_getter=lambda: app_state.authorized_read_paths,
        adaptive_ctx=app_state.adaptive_ctx,
    )

    # A7: Task planner for multi-step decomposition
    planner = TaskPlanner(runtime)

    router = SpecializedAgentRouter(llm_router=llm_router)
    router.ensure_profiles(state_store)

    app_state.runtime = runtime
    app_state.vector_store = vector_store
    app_state.state_store = state_store
    app_state.short_term = short_term
    app_state.provider_registry = registry
    app_state.router = router
    app_state.enricher = enricher
    app_state.planner = planner
    app_state.embedding_provider = embed
    app_state.inference_engine = llm_engine

    from core.security.secrets import SecretsManager
    _state_dir_path = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser()
    app_state.secrets_mgr = SecretsManager(
        _state_dir_path,
        env_api_key=os.environ.get("CEREBRO_API_KEY"),
    )

    if INFERENCE_BACKEND == "llamacpp":
        from core.feature_flags import auto_start_engine_enabled
        from core.inference.engine_desired import set_engine_desired
        from core.inference.health_monitor import LlamaServerHealthMonitor

        if auto_start_engine_enabled():
            set_engine_desired("on")

        app_state.llama_health_monitor = LlamaServerHealthMonitor(
            base_url=LLAMACPP_URL,
            profile=LLAMACPP_PROFILE,
            ram_monitor=app_state.ram_monitor,
        )


if __name__ == "__main__":
    from loguru import logger as _logger

    if CEREBRO_HOST in ("0.0.0.0", "::"):
        _logger.warning(
            "⚠  Binding to %s — Cerebro will be reachable from other machines on your network. "
            "Set CEREBRO_API_KEY to require authentication.",
            CEREBRO_HOST,
        )
        _api_key = os.environ.get("CEREBRO_API_KEY", "")
        if not _api_key:
            _logger.critical(
                "CEREBRO_API_KEY is required when binding to %s. "
                "Set CEREBRO_HOST=127.0.0.1 or provide CEREBRO_API_KEY.",
                CEREBRO_HOST,
            )
            raise SystemExit(1)

    _build_app_state()
    uvicorn.run(app, host=CEREBRO_HOST, port=PORT)
