"""Background watchdog for llama-server liveness and crash recovery (A5)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from loguru import logger

from core.inference.engine_desired import get_engine_desired
from core.observability.ram_monitor import RamMonitor

LlamaServerState = Literal["up", "restarting", "down"]


@dataclass(frozen=True)
class HealthSnapshot:
    llama_server: LlamaServerState
    last_restart_at: str | None
    restart_count_session: int
    message: str | None = None


def _default_spawn_engine(profile: str) -> None:
    from core.inference.engine_manager import spawn_chat_engine

    spawn_chat_engine(profile)


class LlamaServerHealthMonitor:
    """Ping llama-server and restart it after consecutive failures."""

    def __init__(
        self,
        base_url: str,
        *,
        profile: str = "chat",
        ping_interval_s: float = 5.0,
        failure_threshold: int = 2,
        max_restarts_per_window: int = 3,
        restart_window_s: float = 300.0,
        ram_monitor: RamMonitor | None = None,
        spawn_engine: Callable[[], None] | None = None,
        ping: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._ping_interval_s = ping_interval_s
        self._failure_threshold = failure_threshold
        self._max_restarts_per_window = max_restarts_per_window
        self._restart_window = timedelta(seconds=restart_window_s)
        self._ram_monitor = ram_monitor or RamMonitor()
        self._spawn_engine = spawn_engine or (lambda: _default_spawn_engine(self._profile))
        self._ping = ping

        self._state: LlamaServerState = "down"
        self._message: str | None = None
        self._failures = 0
        self._restart_count_session = 0
        self._last_restart_at: datetime | None = None
        self._restart_times: list[datetime] = []
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def snapshot(self) -> HealthSnapshot:
        last = self._last_restart_at.isoformat() if self._last_restart_at else None
        return HealthSnapshot(
            llama_server=self._state,
            last_restart_at=last,
            restart_count_session=self._restart_count_session,
            message=self._message,
        )

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="llama-server-health")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _http_ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                response = await client.get(f"{self._base_url}/health")
                return int(response.status_code) == 200
        except Exception:
            return False

    async def _check_ping(self) -> bool:
        if self._ping is not None:
            return await self._ping()
        return await self._http_ping()

    def _prune_restart_window(self, now: datetime) -> None:
        cutoff = now - self._restart_window
        self._restart_times = [t for t in self._restart_times if t > cutoff]

    def _can_restart(self, now: datetime) -> bool:
        self._prune_restart_window(now)
        return len(self._restart_times) < self._max_restarts_per_window

    async def _attempt_restart(self) -> None:
        if get_engine_desired() == "off":
            self._state = "down"
            self._message = "engine_desired_off"
            logger.info("Llama-server restart skipped (engine_desired=off)")
            return

        now = datetime.now(UTC)
        ram = self._ram_monitor.snapshot()
        if ram["pressure"] == "critical" or ram["available_gb"] < float(
            os.getenv("CEREBRO_RAM_MIN_AVAILABLE_GB", "0.5")
        ):
            self._state = "down"
            self._message = "ram_pressure_critical"
            logger.warning(
                "Llama-server restart deferred: RAM critical ({:.2f} GB available)",
                ram["available_gb"],
            )
            return

        if not self._can_restart(now):
            self._state = "down"
            self._message = "restart_limit_exceeded"
            logger.error(
                "Llama-server restart limit exceeded ({} in {:.0f}s)",
                self._max_restarts_per_window,
                self._restart_window.total_seconds(),
            )
            return

        self._state = "restarting"
        self._message = None
        try:
            await asyncio.to_thread(self._spawn_engine)
            self._restart_count_session += 1
            self._last_restart_at = now
            self._restart_times.append(now)
            self._failures = 0
            logger.warning(
                "Llama-server restarting (attempt {} this session)", self._restart_count_session
            )
        except Exception as exc:
            self._state = "down"
            self._message = "restart_failed"
            logger.exception("Llama-server restart spawn failed: {}", exc)

    async def _run_loop(self) -> None:
        while True:
            try:
                ok = await self._check_ping()
                async with self._lock:
                    if ok:
                        self._failures = 0
                        if self._state != "up":
                            logger.info("Llama-server is up at {}", self._base_url)
                        self._state = "up"
                        if self._message in (None, "ram_pressure_critical"):
                            self._message = None
                    else:
                        self._failures += 1
                        if self._failures >= self._failure_threshold:
                            if get_engine_desired() == "off":
                                self._state = "down"
                                self._message = "engine_desired_off"
                            else:
                                if self._state == "up":
                                    logger.warning(
                                        "Llama-server missed {} pings — recovering",
                                        self._failures,
                                    )
                                if self._state != "restarting":
                                    await self._attempt_restart()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Llama-server health loop error")
            await asyncio.sleep(self._ping_interval_s)
