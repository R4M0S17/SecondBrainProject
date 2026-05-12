"""File system watcher with debounce for Cerebro's ingestion pipeline."""

import asyncio
import os
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

WATCHED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".md", ".py", ".docx"})
IGNORED_DIRS: frozenset[str] = frozenset({".git", "node_modules", "__pycache__", ".venv"})
DEBOUNCE_SECONDS: float = 3.0


class _CerebroEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: "FileWatcher") -> None:
        super().__init__()
        self._watcher = watcher

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._on_modified(event)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._on_modified(event)


class FileWatcher:
    """Watches filesystem paths and enqueues changed files for re-indexing."""

    def __init__(self, paths: list[str], ingestion_queue: asyncio.Queue) -> None:
        self._paths = paths
        self._queue = ingestion_queue
        self._observer = Observer()
        self._handler = _CerebroEventHandler(self)
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        for path in self._paths:
            self._observer.schedule(self._handler, path, recursive=True)
        self._observer.start()
        logger.info("FileWatcher started on {} path(s): {}", len(self._paths), self._paths)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
        for handle in list(self._timers.values()):
            handle.cancel()
        self._timers.clear()
        logger.info("FileWatcher stopped")

    def _should_ignore(self, filepath: str) -> bool:
        path = Path(filepath)

        if path.name.startswith("."):
            return True

        if path.name.endswith((".swp", ".tmp", "~")):
            return True

        if any(part in IGNORED_DIRS for part in path.parts):
            return True

        return path.suffix.lower() not in WATCHED_EXTENSIONS

    def _on_modified(self, event: FileSystemEvent) -> None:
        filepath = os.path.abspath(event.src_path)

        if self._should_ignore(filepath):
            return

        if self._loop is None:
            logger.warning("FileWatcher._on_modified called before start(); ignoring event")
            return

        self._loop.call_soon_threadsafe(self._schedule_debounce, filepath)

    def _schedule_debounce(self, filepath: str) -> None:
        """Cancel pending timer for filepath and start a fresh one. Runs in event loop."""
        existing = self._timers.get(filepath)
        if existing is not None:
            existing.cancel()
        self._timers[filepath] = self._loop.call_later(  # type: ignore[union-attr]
            DEBOUNCE_SECONDS, self._enqueue, filepath
        )
        logger.debug("Debounce reset for: {}", filepath)

    def _enqueue(self, filepath: str) -> None:
        """Put filepath into the ingestion queue. Runs in event loop after debounce expires."""
        self._timers.pop(filepath, None)
        self._queue.put_nowait(filepath)
        logger.debug("Enqueued for ingestion: {}", filepath)
