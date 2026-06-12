from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


class AuditLogger:
    def __init__(self, audit_dir: str) -> None:
        self._dir = Path(audit_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _current_log(self) -> Path:
        month = datetime.now(UTC).strftime("%Y-%m")
        return self._dir / f"audit-{month}.jsonl"

    def log_tool_call(
        self,
        agent_id: str,
        tool: str,
        args_sanitized: dict,
        result_summary: str,
        approved: bool,
        timestamp: datetime,
    ) -> None:
        record = {
            "ts": timestamp.isoformat(),
            "agent_id": agent_id,
            "tool": tool,
            "args": args_sanitized,
            "result_summary": result_summary,
            "approved": approved,
        }
        try:
            with self._current_log().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("AuditLogger: failed to write: {}", exc)
