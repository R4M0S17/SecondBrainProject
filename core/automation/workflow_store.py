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
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    run_count   INTEGER NOT NULL DEFAULT 0,
    last_run    REAL
);

CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at DESC);
"""


class WorkflowStore:
    """Persists recorded AppleScript workflows.

    Each workflow stores the raw AppleScript source and metadata about its
    parameters, tags, and usage count.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def save(
        self,
        name: str,
        applescript: str,
        description: str = "",
        parameters: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        wid = uuid.uuid4().hex
        now = time.time()
        self._conn.execute(
            "INSERT INTO workflows (id, name, description, applescript, parameters, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                wid,
                name,
                description,
                applescript,
                json.dumps(parameters or []),
                json.dumps(tags or []),
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
        d["parameters"] = json.loads(d.get("parameters", "[]"))
        d["tags"] = json.loads(d.get("tags", "[]"))
        return d
