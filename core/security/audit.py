from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:
    """Structured JSONL audit log with monthly rotation and retention.

    No hash chaining (adds complexity with no real defense for a local app —
    an attacker with filesystem access can rewrite anything, including chain hashes).
    """

    def __init__(self, log_dir: Path, retention_days: int = 90):
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._rotate()

    def _rotate(self) -> None:
        self.current_file = self.log_dir / f"audit-{datetime.now().strftime('%Y%m')}.jsonl"
        self._cleanup_old()

    def _cleanup_old(self) -> None:
        cutoff = datetime.now().timestamp() - (self.retention_days * 86400)
        for f in self.log_dir.glob("audit-*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)

    def log(self, event: dict) -> None:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        with open(self.current_file, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def query(self, event_type: str | None = None,
              limit: int = 100) -> list[dict]:
        entries = []
        for f in sorted(self.log_dir.glob("audit-*.jsonl"), reverse=True):
            with open(f) as fh:
                for line in fh:
                    entry = json.loads(line)
                    if event_type and entry.get("event") != event_type:
                        continue
                    entries.append(entry)
                    if len(entries) >= limit:
                        return entries
        return entries
