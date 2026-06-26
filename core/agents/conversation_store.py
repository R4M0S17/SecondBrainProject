"""Module 8 — Conversation persistence.

Stores multi-turn conversation records as JSON files under
~/.cerebro/state/conversations/.  Each record holds an ordered list of
ConversationTurn objects (alternating user / assistant) plus lightweight
bookkeeping fields for listing / browsing sessions.

The API ``conversation_id`` is the durable session key (same UUID for the
lifetime of a chat surface).  ``session_summary`` holds compressed context
from older turns when the resume cap (``CEREBRO_SESSION_RESUME_MAX_TURNS``)
drops verbatim history.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ConversationRecord:
    conv_id: str
    agent_id: str
    started_at: str
    last_active: str
    turns: list[ConversationTurn] = field(default_factory=list)
    session_summary: str = ""
    pinned: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Serialization helpers
# ──────────────────────────────────────────────────────────────────────────────


def _record_to_dict(r: ConversationRecord) -> dict:
    return {
        "conv_id": r.conv_id,
        "agent_id": r.agent_id,
        "started_at": r.started_at,
        "last_active": r.last_active,
        "session_summary": r.session_summary,
        "pinned": r.pinned,
        "turns": [
            {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp,
                "metadata": t.metadata,
            }
            for t in r.turns
        ],
    }


def _record_from_dict(d: dict) -> ConversationRecord:
    return ConversationRecord(
        conv_id=d["conv_id"],
        agent_id=d.get("agent_id", ""),
        started_at=d.get("started_at", ""),
        last_active=d.get("last_active", ""),
        session_summary=d.get("session_summary", ""),
        pinned=d.get("pinned", False),
        turns=[
            ConversationTurn(
                role=t["role"],
                content=t["content"],
                timestamp=t.get("timestamp", ""),
                metadata=t.get("metadata", {}),
            )
            for t in d.get("turns", [])
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Store
# ──────────────────────────────────────────────────────────────────────────────


class ConversationStore:
    def __init__(self, state_dir: str) -> None:
        self._dir = Path(state_dir).expanduser() / "conversations"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, conv_id: str) -> Path:
        return self._dir / f"{conv_id}.json"

    def create(self, agent_id: str) -> str:
        conv_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self._write(
            ConversationRecord(
                conv_id=conv_id,
                agent_id=agent_id,
                started_at=now,
                last_active=now,
            )
        )
        return conv_id

    def append(
        self,
        conv_id: str,
        user_content: str,
        assistant_content: str,
        metadata: dict,
    ) -> None:
        record = self.get(conv_id)
        if record is None:
            raise KeyError(f"Conversation {conv_id!r} not found")
        now = datetime.now(UTC).isoformat()
        record.turns.append(ConversationTurn(role="user", content=user_content, timestamp=now))
        record.turns.append(
            ConversationTurn(
                role="assistant", content=assistant_content, timestamp=now, metadata=metadata
            )
        )
        record.last_active = now
        self._write(record)

    def get(self, conv_id: str) -> ConversationRecord | None:
        path = self._path(conv_id)
        if not path.exists():
            return None
        try:
            return _record_from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Corrupted conversation {}: {}", conv_id, exc)
            return None

    def set_pinned(self, conv_id: str, pinned: bool) -> bool:
        record = self.get(conv_id)
        if record is None:
            return False
        record.pinned = pinned
        self._write(record)
        return True

    def update_session_summary(self, conv_id: str, summary: str) -> None:
        record = self.get(conv_id)
        if record is None:
            raise KeyError(f"Conversation {conv_id!r} not found")
        record.session_summary = summary
        self._write(record)

    def list_all(self) -> list[ConversationRecord]:
        records: list[ConversationRecord] = []
        for p in sorted(self._dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                records.append(_record_from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except Exception:
                logger.warning("Skipping unreadable conversation file: {}", p.name)
        return records

    def delete(self, conv_id: str) -> bool:
        path = self._path(conv_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except Exception as exc:
            logger.warning("Failed to delete conversation {}: {}", conv_id, exc)
            return False

    def _write(self, record: ConversationRecord) -> None:
        path = self._path(record.conv_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(_record_to_dict(record), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
