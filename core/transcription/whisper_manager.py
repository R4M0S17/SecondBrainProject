"""WhisperManager: gestiona el ciclo de vida del proceso whisper-server.

Estrategia de RAM: el proceso arranca bajo demanda (primera llamada
a /api/transcribe) y se mantiene vivo. Si no se usa durante 5 minutos,
se apaga automáticamente para liberar ~388 MB de RAM.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

WHISPER_SERVER_PORT = 8765
WHISPER_SERVER_URL = f"http://127.0.0.1:{WHISPER_SERVER_PORT}"
WHISPER_MODEL_PATH = Path("bin/whisper/ggml-base.bin")
WHISPER_BIN_PATH = Path("bin/whisper-src/build/bin/whisper-server")

IDLE_SHUTDOWN_SECONDS = 300


class WhisperManager:
    """Gestiona el proceso whisper-server como proceso hijo residente."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._ready = False
        self._lock = asyncio.Lock()
        self._last_use: float = 0.0
        self._watchdog_task: asyncio.Task | None = None

    @property
    def is_available(self) -> bool:
        """True si el binario y el modelo existen en disco."""
        return WHISPER_BIN_PATH.exists() and WHISPER_MODEL_PATH.exists()

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    async def ensure_running(self) -> bool:
        """Arranca whisper-server si no está corriendo. Thread-safe."""
        async with self._lock:
            if self.is_running and self._ready:
                return True
            if not self.is_available:
                logger.warning("whisper-server no disponible: binario o modelo faltante")
                return False
            return await self._start()

    async def _start(self) -> bool:
        cmd = [
            str(WHISPER_BIN_PATH),
            "-m",
            str(WHISPER_MODEL_PATH),
            "--host",
            "127.0.0.1",
            "--port",
            str(WHISPER_SERVER_PORT),
            "-l",
            "auto",
            "-t",
            "4",
            "--convert",
        ]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._last_use = time.monotonic()

        for _ in range(16):
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get(f"{WHISPER_SERVER_URL}/")
                    if resp.status_code in (200, 404):
                        self._ready = True
                        self._start_watchdog()
                        logger.info("whisper-server listo en puerto %d", WHISPER_SERVER_PORT)
                        return True
            except httpx.ConnectError:
                continue

        logger.error("whisper-server no respondió en 8 segundos")
        self._process.kill()
        return False

    def _start_watchdog(self) -> None:
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog())

    async def _stop_watchdog(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None

    async def _watchdog(self) -> None:
        """Apaga el servidor tras IDLE_SHUTDOWN_SECONDS de inactividad."""
        try:
            while True:
                await asyncio.sleep(60)
                if self.is_running and self._last_use > 0:
                    idle = time.monotonic() - self._last_use
                    if idle > IDLE_SHUTDOWN_SECONDS:
                        logger.info(
                            "whisper-server inactivo por %.0fs — apagando",
                            idle,
                        )
                        self.shutdown()
                        return
        except asyncio.CancelledError:
            pass

    async def transcribe(self, wav_bytes: bytes, language: str = "auto") -> dict:
        """Envía audio WAV a whisper-server y retorna el texto transcrito.

        wav_bytes: audio WAV (16 kHz mono PCM), ya convertido por el frontend.
        language: "auto" para detección automática, "es", "en", etc.
        """
        if not await self.ensure_running():
            raise RuntimeError("whisper-server no disponible")

        self._last_use = time.monotonic()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(tmp_path, "rb") as f:
                    response = await client.post(
                        f"{WHISPER_SERVER_URL}/inference",
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={
                            "temperature": "0.0",
                            "temperature_inc": "0.2",
                            "response_format": "verbose_json",
                            **({"language": language} if language != "auto" else {}),
                        },
                    )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        finally:
            os.unlink(tmp_path)

    async def health_check(self) -> dict:
        """Retorna el estado del proceso y su disponibilidad."""
        available = self.is_available
        running = self.is_running
        reachable = False

        if running:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    await client.get(f"{WHISPER_SERVER_URL}/")
                reachable = True
            except Exception:
                pass

        idle_seconds = 0.0
        if running and self._last_use > 0:
            idle_seconds = time.monotonic() - self._last_use

        return {
            "available": available,
            "running": running,
            "reachable": reachable,
            "model": str(WHISPER_MODEL_PATH) if available else None,
            "port": WHISPER_SERVER_PORT,
            "idle_seconds": round(idle_seconds, 1),
            "idle_shutdown_seconds": IDLE_SHUTDOWN_SECONDS,
        }

    def shutdown(self) -> None:
        """Termina el proceso graceful al cerrar la aplicación."""
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            self._watchdog_task = None
        if self._process and self._process.poll() is None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("whisper-server terminado")
        self._ready = False
