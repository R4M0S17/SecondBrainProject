from __future__ import annotations

import json
import os
from pathlib import Path

from core.knowledge_sync.models import SyncState, SyncStatus


class SyncStateStore:
    def __init__(self, state_dir: str = "~/.cerebro/state") -> None:
        self._root = Path(os.path.expanduser(state_dir)) / "knowledge_sync"
        self._root.mkdir(parents=True, exist_ok=True)

    def load(self, source_id: str) -> SyncState:
        path = self._root / f"{source_id}.json"
        if not path.is_file():
            return SyncState(source_id=source_id)
        try:
            data = json.loads(path.read_text())
            if "status" in data:
                data["status"] = SyncStatus(data["status"])
            return SyncState(**data)
        except (json.JSONDecodeError, TypeError):
            return SyncState(source_id=source_id)

    def save(self, state: SyncState) -> None:
        path = self._root / f"{state.source_id}.json"
        path.write_text(
            json.dumps(
                {
                    "source_id": state.source_id,
                    "status": state.status.value,
                    "last_sync_at": state.last_sync_at,
                    "last_sync_duration_ms": state.last_sync_duration_ms,
                    "last_error": state.last_error,
                    "etag": state.etag,
                    "last_modified": state.last_modified,
                    "items_fetched_count": state.items_fetched_count,
                    "items_indexed_count": state.items_indexed_count,
                    "consecutive_errors": state.consecutive_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
