"""SQLite-backed store for recorded Desktop Automation workflows."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflows (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    applescript TEXT NOT NULL,
    parameters  TEXT NOT NULL DEFAULT '[]',
    tags        TEXT NOT NULL DEFAULT '[]',
    steps       TEXT NOT NULL DEFAULT '[]',
    workflow_type TEXT NOT NULL DEFAULT 'desktop',
    recipe_key  TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    run_count   INTEGER NOT NULL DEFAULT 0,
    last_run    REAL
);

CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    started_at  REAL NOT NULL,
    finished_at REAL,
    success     INTEGER NOT NULL,
    output      TEXT,
    error       TEXT,
    params      TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_wf ON workflow_runs(workflow_id, started_at DESC);
"""

_MIGRATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("steps", "TEXT NOT NULL DEFAULT '[]'"),
    ("workflow_type", "TEXT NOT NULL DEFAULT 'desktop'"),
    ("recipe_key", "TEXT"),
)


class WorkflowStore:
    """Persists recorded AppleScript workflows and execution history."""

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._migrate_schema()
        self._conn.commit()

    def _migrate_schema(self) -> None:
        cur = self._conn.execute("PRAGMA table_info(workflows)")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_def in _MIGRATION_COLUMNS:
            if col_name not in existing:
                self._conn.execute(f"ALTER TABLE workflows ADD COLUMN {col_name} {col_def}")

    def save(
        self,
        name: str,
        applescript: str,
        description: str = "",
        parameters: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        steps: list[dict[str, Any]] | None = None,
        workflow_type: str = "desktop",
        recipe_key: str | None = None,
    ) -> str:
        wid = uuid.uuid4().hex
        now = time.time()
        self._conn.execute(
            "INSERT INTO workflows "
            "(id, name, description, applescript, parameters, tags, steps, workflow_type, recipe_key, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                wid,
                name,
                description,
                applescript,
                json.dumps(parameters or []),
                json.dumps(tags or []),
                json.dumps(steps or []),
                workflow_type,
                recipe_key,
                now,
                now,
            ),
        )
        self._conn.commit()
        return wid

    def get(self, wid: str) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT * FROM workflows WHERE id = ?", (wid,))
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT * FROM workflows ORDER BY created_at DESC")
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def update(
        self,
        wid: str,
        *,
        name: str | None = None,
        description: str | None = None,
        applescript: str | None = None,
        tags: list[str] | None = None,
        steps: list[dict[str, Any]] | None = None,
    ) -> bool:
        updates: list[str] = []
        values: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if applescript is not None:
            updates.append("applescript = ?")
            values.append(applescript)
        if tags is not None:
            updates.append("tags = ?")
            values.append(json.dumps(tags))
        if steps is not None:
            updates.append("steps = ?")
            values.append(json.dumps(steps))
        if not updates:
            return False
        updates.append("updated_at = ?")
        values.append(time.time())
        values.append(wid)
        self._conn.execute(
            f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        self._conn.commit()
        return True

    def increment_run_count(self, wid: str) -> None:
        self._conn.execute(
            "UPDATE workflows SET run_count = run_count + 1, last_run = ? WHERE id = ?",
            (time.time(), wid),
        )
        self._conn.commit()

    def record_run(
        self,
        workflow_id: str,
        *,
        started_at: float,
        finished_at: float,
        success: bool,
        output: str | None = None,
        error: str | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO workflow_runs "
            "(id, workflow_id, started_at, finished_at, success, output, error, params) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                workflow_id,
                started_at,
                finished_at,
                1 if success else 0,
                output,
                error,
                json.dumps(params or {}),
            ),
        )
        self._conn.commit()
        return run_id

    def list_runs(self, workflow_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        cap = max(1, min(limit, 100))
        cur = self._conn.execute(
            "SELECT * FROM workflow_runs WHERE workflow_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (workflow_id, cap),
        )
        return [self._run_row_to_dict(r) for r in cur.fetchall()]

    def delete(self, wid: str) -> bool:
        cur = self._conn.execute("DELETE FROM workflows WHERE id = ?", (wid,))
        self._conn.commit()
        return cur.rowcount > 0

    def search(self, query: str) -> list[dict[str, Any]]:
        like = f"%{query}%"
        cur = self._conn.execute(
            "SELECT * FROM workflows WHERE name LIKE ? OR description LIKE ? "
            "ORDER BY run_count DESC, created_at DESC",
            (like, like),
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["parameters"] = json.loads(d.get("parameters") or "[]")
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["steps"] = json.loads(d.get("steps") or "[]")
        d["workflow_type"] = d.get("workflow_type") or "desktop"
        d["recipe_key"] = d.get("recipe_key")
        return d

    @staticmethod
    def _run_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["success"] = bool(d.get("success"))
        d["params"] = json.loads(d.get("params") or "{}")
        return d
