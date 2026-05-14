"""Module A4 — Pipeline Middleware.

Every interaction passes through a linear chain of PipelineStages. Each stage
receives a PipelineContext, mutates it, and returns it. The Pipeline runner
measures per-stage latency, handles can_skip failures, and exposes insert/remove
for runtime composition.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from loguru import logger

if TYPE_CHECKING:
    from core.agents.state_store import ToolCall
    from core.memory.context_builder import AssembledContext
    from core.tools.policy import PolicyResult


# --------------------------------------------------------------------------- #
# Domain types
# --------------------------------------------------------------------------- #


class Intent(StrEnum):
    RAG_QUERY = "rag_query"
    AGENT_ACTION = "agent_action"
    DIRECT_ACTION = "direct_action"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass
class AuditRecord:
    agent_id: str
    query_id: str
    timestamp: datetime
    stage_latencies: dict[str, float] = field(default_factory=dict)  # stage -> ms
    warnings: list[str] = field(default_factory=list)


@dataclass
class PipelineContext:
    raw_input: str
    audit_record: AuditRecord
    normalized_input: str | None = None
    detected_intent: Intent | None = None
    assembled_context: AssembledContext | None = None
    prompt: str | None = None
    policy_result: PolicyResult | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: str | None = None
    final_response: str | None = None
    metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Stage protocol
# --------------------------------------------------------------------------- #


@runtime_checkable
class PipelineStage(Protocol):
    async def process(self, ctx: PipelineContext) -> PipelineContext: ...

    def name(self) -> str: ...

    def can_skip(self) -> bool: ...


# --------------------------------------------------------------------------- #
# Exception
# --------------------------------------------------------------------------- #


class PipelineError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Pipeline runner
# --------------------------------------------------------------------------- #


class Pipeline:
    def __init__(self, stages: list[PipelineStage]) -> None:
        self._stages: list[PipelineStage] = list(stages)

    async def run(
        self,
        raw_input: str,
        agent_id: str = "default",
        extra_metadata: dict | None = None,
    ) -> PipelineContext:
        """Execute all stages in order and return the final context."""
        audit = AuditRecord(
            agent_id=agent_id,
            query_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
        )
        ctx = PipelineContext(
            raw_input=raw_input,
            audit_record=audit,
            metadata={"agent_id": agent_id, **(extra_metadata or {})},
        )

        for stage in self._stages:
            t0 = time.monotonic()
            try:
                ctx = await stage.process(ctx)
            except Exception as exc:
                elapsed_ms = (time.monotonic() - t0) * 1000
                ctx.audit_record.stage_latencies[stage.name()] = elapsed_ms
                if stage.can_skip():
                    logger.warning(
                        "Pipeline: stage '{}' failed (can_skip=True): {}", stage.name(), exc
                    )
                    ctx.audit_record.warnings.append(f"stage_skip:{stage.name()}")
                    continue
                raise PipelineError(f"Stage '{stage.name()}' failed: {exc}") from exc
            elapsed_ms = (time.monotonic() - t0) * 1000
            ctx.audit_record.stage_latencies[stage.name()] = elapsed_ms

        return ctx

    def insert_stage(self, stage: PipelineStage, after: str) -> None:
        """Insert a new stage immediately after the stage named `after`."""
        for i, s in enumerate(self._stages):
            if s.name() == after:
                self._stages.insert(i + 1, stage)
                return
        raise ValueError(f"Stage '{after}' not found — cannot insert after it")

    def remove_stage(self, name: str) -> None:
        """Remove the stage with the given name. No-op if not present."""
        self._stages = [s for s in self._stages if s.name() != name]

    @property
    def stage_names(self) -> list[str]:
        return [s.name() for s in self._stages]
