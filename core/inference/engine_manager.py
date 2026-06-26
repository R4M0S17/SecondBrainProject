"""Spawn, stop, and health-check llama-server (:8080) and embed server (:8082)."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger

from core.inference.embedding_factory import default_embeddings_backend
from core.inference.engine_desired import get_engine_desired, set_engine_desired

CHAT_BASE_URL = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
EMBED_BASE_URL = os.getenv("CEREBRO_LLAMACPP_EMBED_URL", "http://127.0.0.1:8082").rstrip("/")
CHAT_PORT = 8080
EMBED_PORT = 8082
DEFAULT_CHAT_WAIT_SEC = 180.0
DEFAULT_EMBED_WAIT_SEC = 60.0
POLL_SEC = 2.0


@dataclass(frozen=True)
class EngineStatus:
    desired: Literal["on", "off"]
    running: bool
    model: str
    llama_server: Literal["up", "restarting", "down"]
    embed_running: bool


def _project_root() -> Path:
    return Path(os.getenv("CEREBRO_ROOT", Path(__file__).resolve().parents[2]))


def _chat_profile() -> str:
    low_power = os.getenv("CEREBRO_LOW_POWER_ENABLED", "").lower() in ("1", "true", "yes")
    return "chat-lowpower" if low_power else "chat"


def _model_name(config: dict[str, Any] | None = None) -> str:
    if config:
        model = config.get("model")
        if isinstance(model, str) and model:
            return model
    return os.getenv("CEREBRO_LLAMACPP_MODEL", "—")


def embed_server_enabled() -> bool:
    return default_embeddings_backend() == "llamacpp"


def http_healthy(base_url: str, *, timeout: float = 3.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url}/health")
            return int(response.status_code) == 200
    except Exception:
        return False


def listen_pids(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return [int(pid) for pid in result.stdout.strip().split("\n") if pid.strip().isdigit()]
    except Exception:
        return []


def stop_port(port: int) -> None:
    pids = listen_pids(port)
    if not pids:
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(1)
    for pid in listen_pids(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def spawn_chat_engine(profile: str | None = None) -> None:
    engine_profile = profile or _chat_profile()
    root = _project_root()
    script = root / "bin" / "start_engine.sh"
    if not script.is_file():
        raise FileNotFoundError(f"start_engine.sh not found at {script}")
    logger.info("Spawning llama-server (profile={})", engine_profile)
    subprocess.Popen(
        ["bash", str(script), engine_profile],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def spawn_embed_engine() -> None:
    root = _project_root()
    script = root / "bin" / "start_engine.sh"
    if not script.is_file():
        raise FileNotFoundError(f"start_engine.sh not found at {script}")
    logger.info("Spawning embed server")
    subprocess.Popen(
        ["bash", str(script), "embed"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_chat_engine() -> None:
    stop_port(CHAT_PORT)


def stop_embed_engine() -> None:
    stop_port(EMBED_PORT)


def stop_all_engines() -> None:
    stop_chat_engine()
    stop_embed_engine()


def wait_for_chat(timeout_sec: float = DEFAULT_CHAT_WAIT_SEC) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if http_healthy(CHAT_BASE_URL):
            return True
        time.sleep(POLL_SEC)
    return False


def wait_for_embed(timeout_sec: float = DEFAULT_EMBED_WAIT_SEC) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if http_healthy(EMBED_BASE_URL):
            return True
        time.sleep(POLL_SEC)
    return False


def get_status(
    *,
    config: dict[str, Any] | None = None,
    health_monitor: Any | None = None,
) -> EngineStatus:
    desired = get_engine_desired()
    running = http_healthy(CHAT_BASE_URL)
    embed_running = http_healthy(EMBED_BASE_URL)

    llama_server: Literal["up", "restarting", "down"] = "up" if running else "down"
    if health_monitor is not None:
        try:
            llama_server = health_monitor.snapshot().llama_server
        except Exception:
            pass

    return EngineStatus(
        desired=desired,
        running=running,
        model=_model_name(config),
        llama_server=llama_server,
        embed_running=embed_running,
    )


def start_engine_sync(
    *,
    config: dict[str, Any] | None = None,
    chat_wait_sec: float = DEFAULT_CHAT_WAIT_SEC,
    start_embed: bool | None = None,
) -> EngineStatus:
    set_engine_desired("on")

    if not http_healthy(CHAT_BASE_URL):
        spawn_chat_engine()
        if not wait_for_chat(chat_wait_sec):
            logger.error("Chat engine did not become healthy within {:.0f}s", chat_wait_sec)
            return get_status(config=config)

    should_embed = embed_server_enabled() if start_embed is None else start_embed
    if should_embed and not http_healthy(EMBED_BASE_URL):
        spawn_embed_engine()
        if not wait_for_embed():
            logger.warning("Embed server did not become healthy within {:.0f}s", DEFAULT_EMBED_WAIT_SEC)

    return get_status(config=config)


def stop_engine_sync(*, config: dict[str, Any] | None = None) -> EngineStatus:
    set_engine_desired("off")
    stop_all_engines()
    return get_status(config=config)
