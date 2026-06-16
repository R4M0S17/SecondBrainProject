from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


@dataclass
class ToolCall:
    tool_name: str
    args: dict
    result: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    latency_ms: float = 0.0


@dataclass
class AgentProfile:
    id: str
    name: str
    domain_tags: list[str]
    authorized_tools: list[str]
    preferences: dict
    created_at: str
    updated_at: str


@dataclass
class AgentState:
    profile: AgentProfile
    session_summary: str
    working_memory: dict
    tool_trace: list[ToolCall]
    semantic_memory_refs: list[str]
    execution_count: int
    last_active: str
    # Transient — not persisted; set after runtime.run() when a tool needs confirmation
    pending_tool_name: str | None = None
    pending_tool_args: dict | None = None


# --------------------------------------------------------------------------- #
# Serialization helpers (no dataclasses.asdict to keep explicit control)
# --------------------------------------------------------------------------- #


def _profile_to_dict(p: AgentProfile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "domain_tags": p.domain_tags,
        "authorized_tools": p.authorized_tools,
        "preferences": p.preferences,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _profile_from_dict(d: dict) -> AgentProfile:
    now = datetime.now(UTC).isoformat()
    return AgentProfile(
        id=d["id"],
        name=d.get("name", d["id"]),
        domain_tags=d.get("domain_tags", []),
        authorized_tools=d.get("authorized_tools", []),
        preferences=d.get("preferences", {}),
        created_at=d.get("created_at", now),
        updated_at=d.get("updated_at", now),
    )


def _state_to_dict(s: AgentState) -> dict:
    return {
        "profile": _profile_to_dict(s.profile),
        "session_summary": s.session_summary,
        "working_memory": s.working_memory,
        "tool_trace": [
            {
                "tool_name": tc.tool_name,
                "args": tc.args,
                "result": tc.result,
                "timestamp": tc.timestamp,
            }
            for tc in s.tool_trace
        ],
        "semantic_memory_refs": s.semantic_memory_refs,
        "execution_count": s.execution_count,
        "last_active": s.last_active,
    }


def _state_from_dict(d: dict) -> AgentState:
    return AgentState(
        profile=_profile_from_dict(d["profile"]),
        session_summary=d.get("session_summary", ""),
        working_memory=d.get("working_memory", {}),
        tool_trace=[
            ToolCall(
                tool_name=tc["tool_name"],
                args=tc.get("args", {}),
                result=tc.get("result", ""),
                timestamp=tc.get("timestamp", ""),
            )
            for tc in d.get("tool_trace", [])
        ],
        semantic_memory_refs=d.get("semantic_memory_refs", []),
        execution_count=d.get("execution_count", 0),
        last_active=d.get("last_active", datetime.now(UTC).isoformat()),
    )


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #


class AgentStateStore:
    # Trim tool_trace to last N entries before writing to keep files small
    TOOL_TRACE_LIMIT = 50

    def __init__(self, state_dir: str) -> None:
        self._state_dir = Path(state_dir).expanduser()
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, agent_id: str) -> Path:
        return self._state_dir / f"{agent_id}.json"

    def _empty_state(self, agent_id: str) -> AgentState:
        now = datetime.now(UTC).isoformat()
        return AgentState(
            profile=AgentProfile(
                id=agent_id,
                name=agent_id,
                domain_tags=[],
                authorized_tools=[],
                preferences={},
                created_at=now,
                updated_at=now,
            ),
            session_summary="",
            working_memory={},
            tool_trace=[],
            semantic_memory_refs=[],
            execution_count=0,
            last_active=now,
        )

    def load(self, agent_id: str) -> AgentState:
        path = self._path(agent_id)
        if not path.exists():
            return self._empty_state(agent_id)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return _state_from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Corrupted state for '{}': {}. Returning empty state.", agent_id, e)
            return self._empty_state(agent_id)

    def save(self, state: AgentState) -> None:
        state.tool_trace = state.tool_trace[-self.TOOL_TRACE_LIMIT :]
        state.last_active = datetime.now(UTC).isoformat()
        state.profile.updated_at = state.last_active

        path = self._path(state.profile.id)
        tmp_path = path.with_suffix(".tmp")

        payload = json.dumps(_state_to_dict(state), indent=2, ensure_ascii=False)
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, path)  # atomic on POSIX — no partial writes visible

    def list_agents(self) -> list[AgentProfile]:
        profiles: list[AgentProfile] = []
        for json_file in sorted(self._state_dir.glob("*.json")):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(_profile_from_dict(data["profile"]))
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping unreadable agent file: {}", json_file.name)
        return profiles

    def delete(self, agent_id: str) -> None:
        path = self._path(agent_id)
        if path.exists():
            path.unlink()
            logger.info("Deleted agent state: {}", agent_id)
