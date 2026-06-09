from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path

import httpx
from loguru import logger

_DEFAULT_MODELS_DIR = Path(__file__).parents[2] / "bin" / "models"

_MODELS_DIR = Path(os.environ.get("CEREBRO_MODELS_DIR", str(_DEFAULT_MODELS_DIR)))
_ROUTER_MODEL = os.environ.get("CEREBRO_ROUTER_MODEL", "SmolLM2-135M-Instruct-Q4_K_M.gguf")
_GENERAL_MODEL = os.environ.get("CEREBRO_GENERAL_MODEL", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
_CODE_MODEL = os.environ.get("CEREBRO_CODE_MODEL", "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf")
_ROUTER_PORT = int(os.environ.get("CEREBRO_ROUTER_PORT", "8080"))
_SPECIALIST_PORT = int(os.environ.get("CEREBRO_SPECIALIST_PORT", "8081"))
_ROUTER_CTX = int(os.environ.get("CEREBRO_ROUTER_CTX", "1024"))
_SPECIALIST_CTX = int(os.environ.get("CEREBRO_SPECIALIST_CTX", "4096"))
_SWAP_TIMEOUT = int(os.environ.get("CEREBRO_SWAP_TIMEOUT", "60"))
_EMBED_MODEL = os.environ.get("CEREBRO_EMBED_MODEL", "v5-nano-retrieval-Q4_K_M.gguf")
_EMBED_PORT = int(os.environ.get("CEREBRO_EMBED_PORT", "8082"))
_EMBED_CTX = int(os.environ.get("CEREBRO_EMBED_CTX", "512"))

_LLAMA_SERVER = os.environ.get("LLAMA_SERVER_BIN", "llama-server")

_ROLE_MODEL: dict[str, str] = {
    "general": _GENERAL_MODEL,
    "code": _CODE_MODEL,
}


def _validate_swap_model_files() -> None:
    """Ensure GGUF files exist before ModelManager spawns subprocesses."""
    missing: list[str] = []
    router_path = _MODELS_DIR / _ROUTER_MODEL
    embed_path = _MODELS_DIR / _EMBED_MODEL
    general_path = _MODELS_DIR / _GENERAL_MODEL
    code_path = _MODELS_DIR / _CODE_MODEL
    if not router_path.is_file():
        missing.append(str(router_path))
    if not embed_path.is_file():
        missing.append(str(embed_path))
    if not general_path.is_file() and not code_path.is_file():
        missing.append(str(general_path))
        missing.append(str(code_path))
    if missing:
        joined = "\n  ".join(missing)
        raise FileNotFoundError(
            f"Model swapping requires these files under {_MODELS_DIR}:\n  {joined}\n"
            "Set CEREBRO_LLAMACPP_SIMPLE=true to use a single external llama-server, "
            "or add the missing GGUFs."
        )


class ModelManager:
    def __init__(self) -> None:
        _validate_swap_model_files()
        self._router_proc: subprocess.Popen | None = None
        self._specialist_proc: subprocess.Popen | None = None
        self._embed_proc: subprocess.Popen | None = None
        self._specialist_role: str | None = None
        self._last_activity: float = 0.0
        self._watchdog_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def router_url(self) -> str:
        return f"http://127.0.0.1:{_ROUTER_PORT}"

    @property
    def specialist_url(self) -> str:
        return f"http://127.0.0.1:{_SPECIALIST_PORT}"

    @property
    def embed_url(self) -> str:
        return f"http://127.0.0.1:{_EMBED_PORT}"

    async def start(self) -> None:
        try:
            model_path = _MODELS_DIR / _ROUTER_MODEL
            self._router_proc = self._launch(str(model_path), _ROUTER_PORT, _ROUTER_CTX)
            logger.info("Waiting for router (SmolLM2) on port {}", _ROUTER_PORT)
            await self._wait_healthy(_ROUTER_PORT)
            logger.info("Router ready at {}", self.router_url)

            embed_path = _MODELS_DIR / _EMBED_MODEL
            self._embed_proc = self._launch_embed(str(embed_path), _EMBED_PORT, _EMBED_CTX)
            logger.info("Waiting for embedding server (Jina) on port {}", _EMBED_PORT)
            await self._wait_healthy(_EMBED_PORT)
            logger.info("Embedding server ready at {}", self.embed_url)

            self._watchdog_task = asyncio.create_task(self._watchdog())
        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        self._kill(self._specialist_proc)
        self._specialist_proc = None
        self._kill(self._embed_proc)
        self._embed_proc = None
        self._kill(self._router_proc)
        self._router_proc = None
        logger.info("ModelManager stopped")

    async def ensure_specialist(self, role: str) -> int:
        if role not in _ROLE_MODEL:
            role = "general"

        async with self._lock:
            if self._specialist_proc is not None and self._specialist_role == role:
                self._last_activity = time.monotonic()
                return _SPECIALIST_PORT

            if self._specialist_proc is not None:
                logger.info("Swapping specialist: {} → {}", self._specialist_role, role)
                self._kill(self._specialist_proc)
                self._specialist_proc = None
                self._specialist_role = None

            model_path = _MODELS_DIR / _ROLE_MODEL[role]
            logger.info("Loading specialist '{}' from {}", role, model_path)
            self._specialist_proc = self._launch(str(model_path), _SPECIALIST_PORT, _SPECIALIST_CTX)
            self._specialist_role = role
            self._last_activity = time.monotonic()

        await self._wait_healthy(_SPECIALIST_PORT)
        logger.info("Specialist '{}' ready at {}", role, self.specialist_url)
        return _SPECIALIST_PORT

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(10)
            async with self._lock:
                if self._specialist_proc is None:
                    continue
                idle = time.monotonic() - self._last_activity
                if idle >= _SWAP_TIMEOUT:
                    logger.info(
                        "Specialist idle {:.0f}s — unloading '{}'", idle, self._specialist_role
                    )
                    self._kill(self._specialist_proc)
                    self._specialist_proc = None
                    self._specialist_role = None

    async def _wait_healthy(self, port: int, retries: int = 60, interval: float = 1.0) -> None:
        url = f"http://127.0.0.1:{port}/health"
        for _ in range(retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return
            except Exception:
                pass
            await asyncio.sleep(interval)
        raise TimeoutError(f"llama-server on port {port} never became healthy after {retries}s")

    @property
    def specialist_status(self) -> dict:
        return {
            "role": self._specialist_role,
            "loaded": self._specialist_proc is not None,
            "embed_loaded": self._embed_proc is not None,
        }

    @staticmethod
    def _launch(model_path: str, port: int, ctx: int) -> subprocess.Popen:
        cmd = [
            _LLAMA_SERVER,
            "--model",
            model_path,
            "--port",
            str(port),
            "--ctx-size",
            str(ctx),
            "--context-shift",
            "--n-gpu-layers",
            "99",
            "--chat-template",
            "chatml",
            "--log-disable",
        ]
        logger.debug("Launching: {}", " ".join(cmd))
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _launch_embed(model_path: str, port: int, ctx: int) -> subprocess.Popen:
        cmd = [
            _LLAMA_SERVER,
            "--model",
            model_path,
            "--port",
            str(port),
            "--ctx-size",
            str(ctx),
            "--n-gpu-layers",
            "99",
            "--embedding",
            "--log-disable",
        ]
        logger.debug("Launching embed server: {}", " ".join(cmd))
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _kill(proc: subprocess.Popen | None) -> None:
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as exc:
            logger.warning("Error terminating process: {}", exc)
