"""Time-Travel Debugger — SQLite-backed recorder for agent execution traces.

Records every LangGraph transition (state snapshots, tokens, tool calls) during
``AgentRuntime.run_streaming()`` and exposes them via the debug REST API.

Writes go through an ``asyncio.Queue`` background worker that batches inserts
every 500 ms so the hot path is never blocked.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# SQLite schema
# --------------------------------------------------------------------------- #

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS execution_runs (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    query       TEXT NOT NULL,
    conversation_id TEXT,
    created_at  REAL NOT NULL,
    duration_ms REAL,
    success     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS execution_steps (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES execution_runs(id) ON DELETE CASCADE,
    step_number         INTEGER NOT NULL,
    node_name           TEXT NOT NULL,
    input_preview       TEXT,
    output_preview      TEXT,
    tool_name           TEXT,
    tool_args_json      TEXT,
    tool_result_preview TEXT,
    needs_confirmation  INTEGER DEFAULT 0,
    timestamp           REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_tokens (
    id          TEXT PRIMARY KEY,
    step_id     TEXT NOT NULL REFERENCES execution_steps(id) ON DELETE CASCADE,
    token_order INTEGER NOT NULL,
    token_text  TEXT NOT NULL,
    is_final    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_steps_run ON execution_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_tokens_step ON execution_tokens(step_id);
CREATE INDEX IF NOT EXISTS idx_runs_created ON execution_runs(created_at DESC);
"""


# --------------------------------------------------------------------------- #
# Public API types
# --------------------------------------------------------------------------- #


class RunRecord:
    """Represents a single agent execution run."""

    __slots__ = (
        "id",
        "agent_id",
        "query",
        "conversation_id",
        "created_at",
        "duration_ms",
        "success",
    )

    def __init__(self, row: sqlite3.Row) -> None:
        self.id: str = row["id"]
        self.agent_id: str = row["agent_id"]
        self.query: str = row["query"]
        self.conversation_id: str | None = row["conversation_id"]
        self.created_at: float = row["created_at"]
        self.duration_ms: float | None = row["duration_ms"]
        self.success: bool = bool(row["success"])


class StepRecord:
    """Represents one LangGraph node transition."""

    __slots__ = (
        "id",
        "run_id",
        "step_number",
        "node_name",
        "input_preview",
        "output_preview",
        "tool_name",
        "tool_args_json",
        "tool_result_preview",
        "needs_confirmation",
        "timestamp",
    )

    def __init__(self, row: sqlite3.Row) -> None:
        self.id: str = row["id"]
        self.run_id: str = row["run_id"]
        self.step_number: int = row["step_number"]
        self.node_name: str = row["node_name"]
        self.input_preview: str | None = row["input_preview"]
        self.output_preview: str | None = row["output_preview"]
        self.tool_name: str | None = row["tool_name"]
        self.tool_args_json: str | None = row["tool_args_json"]
        self.tool_result_preview: str | None = row["tool_result_preview"]
        self.needs_confirmation: bool = bool(row["needs_confirmation"])
        self.timestamp: float = row["timestamp"]


# --------------------------------------------------------------------------- #
# TimeTravelRecorder
# --------------------------------------------------------------------------- #

_FLUSH_INTERVAL = 0.5  # seconds
_BATCH_SIZE = 50  # max queue items before forced flush


class TimeTravelRecorder:
    """Records agent execution traces to SQLite.

    Usage::

        recorder = TimeTravelRecorder(db_path="/path/to/db.sqlite")
        await recorder.start()
        # ... agent runs ...
        await recorder.shutdown()

    All write operations are non-blocking — they enqueue work on an internal
    ``asyncio.Queue`` drained by a background worker.
    """

    def __init__(self, db_path: str, ttl_days: int = 7, max_runs: int = 500) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl_days = ttl_days
        self._max_runs = max_runs
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        self._conn = conn

    def start(self) -> None:
        """Start the background flush worker."""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def shutdown(self) -> None:
        """Drain pending writes and close the database."""
        if self._worker_task is not None:
            await self._queue.join()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Write API (non-blocking, enqueues work) ────────────────────────────

    async def start_run(
        self,
        run_id: str,
        agent_id: str,
        query: str,
        conversation_id: str | None = None,
    ) -> None:
        """Record the beginning of an agent execution."""
        await self._queue.put(
            {
                "type": "start_run",
                "id": run_id,
                "agent_id": agent_id,
                "query": query,
                "conversation_id": conversation_id,
                "created_at": time.time(),
            }
        )

    async def record_step(
        self,
        step_id: str,
        run_id: str,
        step_number: int,
        node_name: str,
        input_preview: str | None = None,
        output_preview: str | None = None,
        tool_name: str | None = None,
        tool_args: dict | None = None,
        tool_result_preview: str | None = None,
        needs_confirmation: bool = False,
    ) -> None:
        """Record a LangGraph node transition."""
        await self._queue.put(
            {
                "type": "record_step",
                "id": step_id,
                "run_id": run_id,
                "step_number": step_number,
                "node_name": node_name,
                "input_preview": input_preview,
                "output_preview": output_preview,
                "tool_name": tool_name,
                "tool_args_json": json.dumps(tool_args) if tool_args else None,
                "tool_result_preview": tool_result_preview,
                "needs_confirmation": 1 if needs_confirmation else 0,
                "timestamp": time.time(),
            }
        )

    async def record_tokens(
        self,
        step_id: str,
        tokens: list[tuple[str, bool]],
    ) -> None:
        """Record a batch of tokens for a step.

        Each item is a ``(token_text, is_final)`` tuple.
        """
        if not tokens:
            return
        await self._queue.put(
            {
                "type": "record_tokens",
                "step_id": step_id,
                "tokens": [
                    (uuid.uuid4().hex, i, t, 1 if f else 0) for i, (t, f) in enumerate(tokens)
                ],
            }
        )

    async def end_run(self, run_id: str, success: bool) -> None:
        """Mark a run as finished, computing duration from start time."""
        await self._queue.put(
            {
                "type": "end_run",
                "id": run_id,
                "success": 1 if success else 0,
                "duration_ms": None,  # computed in worker from created_at
            }
        )

    # ── Read API (direct SQLite queries, not through queue) ────────────────

    def get_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if self._conn is None:
            return []
        cur = self._conn.execute(
            "SELECT * FROM execution_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_run_steps(self, run_id: str) -> list[dict[str, Any]]:
        if self._conn is None:
            return []
        cur = self._conn.execute(
            "SELECT * FROM execution_steps WHERE run_id = ? ORDER BY step_number ASC",
            (run_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_step_detail(self, step_id: str) -> dict[str, Any] | None:
        if self._conn is None:
            return None
        cur = self._conn.execute(
            "SELECT * FROM execution_steps WHERE id = ?",
            (step_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        step = dict(row)
        # attach tokens
        tok_cur = self._conn.execute(
            "SELECT token_order, token_text, is_final FROM execution_tokens "
            "WHERE step_id = ? ORDER BY token_order ASC",
            (step_id,),
        )
        step["tokens"] = [dict(t) for t in tok_cur.fetchall()]
        return step

    def get_run_count(self) -> int:
        if self._conn is None:
            return 0
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM execution_runs")
        row = cur.fetchone()
        return row["cnt"] if row else 0

    # ── Cleanup ────────────────────────────────────────────────────────────

    def enforce_retention(self) -> None:
        """Delete runs exceeding TTL or max_runs count."""
        if self._conn is None:
            return
        cutoff = time.time() - (self._ttl_days * 86400)
        self._conn.execute("DELETE FROM execution_runs WHERE created_at < ?", (cutoff,))
        # Keep only latest N runs
        cur = self._conn.execute(
            "SELECT id FROM execution_runs ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (self._max_runs,),
        )
        stale = [r["id"] for r in cur.fetchall()]
        for sid in stale:
            self._conn.execute("DELETE FROM execution_runs WHERE id = ?", (sid,))
        self._conn.commit()

    # ── Internal ───────────────────────────────────────────────────────────

    async def _worker_loop(self) -> None:
        """Background worker that drains the queue and batches SQLite writes."""
        buffer: list[dict[str, Any]] = []

        while True:
            try:
                with_immediate = await asyncio.wait_for(self._queue.get(), timeout=_FLUSH_INTERVAL)
                buffer.append(with_immediate)
                # Drain any additional items that arrived during the window
                while len(buffer) < _BATCH_SIZE and not self._queue.empty():
                    buffer.append(self._queue.get_nowait())
            except TimeoutError:
                pass

            if buffer:
                self._flush(buffer)
                buffer.clear()

    def _flush(self, items: list[dict[str, Any]]) -> None:
        if self._conn is None:
            return
        for item in items:
            try:
                self._apply(item)
            except Exception:
                pass  # swallow per-item errors to keep worker alive
        self._conn.commit()

    def _apply(self, item: dict[str, Any]) -> None:
        t = item["type"]
        if t == "start_run":
            self._conn.execute(
                "INSERT OR IGNORE INTO execution_runs (id, agent_id, query, conversation_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item["agent_id"],
                    item["query"],
                    item["conversation_id"],
                    item["created_at"],
                ),
            )
        elif t == "record_step":
            self._conn.execute(
                "INSERT OR IGNORE INTO execution_steps "
                "(id, run_id, step_number, node_name, input_preview, output_preview, "
                "tool_name, tool_args_json, tool_result_preview, needs_confirmation, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item["run_id"],
                    item["step_number"],
                    item["node_name"],
                    item["input_preview"],
                    item["output_preview"],
                    item["tool_name"],
                    item["tool_args_json"],
                    item["tool_result_preview"],
                    item["needs_confirmation"],
                    item["timestamp"],
                ),
            )
        elif t == "record_tokens":
            if not item["tokens"]:
                return
            self._conn.executemany(
                "INSERT OR IGNORE INTO execution_tokens (id, step_id, token_order, token_text, is_final) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (tid, item["step_id"], order, text, final)
                    for tid, order, text, final in item["tokens"]
                ],
            )
        elif t == "end_run":
            if item["duration_ms"] is None:
                # Compute from created_at
                cur = self._conn.execute(
                    "SELECT created_at FROM execution_runs WHERE id = ?",
                    (item["id"],),
                )
                row = cur.fetchone()
                if row:
                    item["duration_ms"] = (time.time() - row["created_at"]) * 1000
            self._conn.execute(
                "UPDATE execution_runs SET duration_ms = ?, success = ? WHERE id = ?",
                (item["duration_ms"], item["success"], item["id"]),
            )
