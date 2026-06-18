"""SIGSTOP/SIGCONT engine suspension to free RAM during inactivity."""

from __future__ import annotations

import asyncio
import os
import signal
from datetime import UTC, datetime

from loguru import logger


class EngineSuspender:
    """Suspend llama-server via SIGSTOP during inactivity; SIGCONT on demand.

    A suspended process's physical pages are reclaimable by the kernel under
    memory pressure. On resume (SIGCONT), pages fault in lazily (~200ms) vs
    8-second full model reload if we killed the process.
    """

    def __init__(self, timeout_s: int = 180) -> None:
        self._pid: int | None = None
        self._timeout_s = timeout_s
        self._last_activity = datetime.now(UTC)
        self._suspended = False
        self._task: asyncio.Task[None] | None = None

    def bind_pid(self, pid: int) -> None:
        self._pid = pid
        self._touch()
        logger.info("EngineSuspender bound to PID {}", pid)

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def state(self) -> str:
        if self._pid is None:
            return "unknown"
        return "suspended" if self._suspended else "active"

    def _touch(self) -> None:
        self._last_activity = datetime.now(UTC)
        if self._suspended:
            try:
                os.kill(self._pid, signal.SIGCONT)
                self._suspended = False
                logger.info("EngineSuspender: SIGCONT (resumed)")
            except OSError as exc:
                logger.warning("EngineSuspender: SIGCONT failed: {}", exc)

    def check(self) -> None:
        if self._pid is None or self._suspended:
            return
        elapsed = (datetime.now(UTC) - self._last_activity).total_seconds()
        if elapsed > self._timeout_s:
            try:
                os.kill(self._pid, signal.SIGSTOP)
                self._suspended = True
                logger.info(
                    "EngineSuspender: SIGSTOP after {:.0f}s idle (PID {})",
                    elapsed,
                    self._pid,
                )
            except OSError as exc:
                logger.warning("EngineSuspender: SIGSTOP failed: {}", exc)

    def resume(self) -> None:
        if self._pid is not None and self._suspended:
            try:
                os.kill(self._pid, signal.SIGCONT)
                self._suspended = False
                logger.debug("EngineSuspender: SIGCONT (resume)")
            except OSError as exc:
                logger.warning("EngineSuspender: SIGCONT resume failed: {}", exc)
        self._touch()

    async def run_loop(self, interval_s: float = 15.0) -> None:
        """Background check every *interval_s* seconds."""
        try:
            while True:
                await asyncio.sleep(interval_s)
                self.check()
        except asyncio.CancelledError:
            # If suspended when cancelled, resume so engine stays usable
            if self._suspended:
                try:
                    os.kill(self._pid, signal.SIGCONT)
                except OSError:
                    pass
            raise

    def start_background(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self.run_loop(), name="engine-suspender")

    async def stop_background(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
