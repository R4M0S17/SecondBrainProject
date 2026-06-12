"""Stage 8 — Audit.

Writes a structured record to the AuditLogger. Only metadata is logged —
never document content, prompt text, or LLM responses (privacy-first).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from core.pipeline.pipeline import PipelineContext

if TYPE_CHECKING:
    from core.tools.audit import AuditLogger


class AuditStage:
    def __init__(self, audit_logger: AuditLogger | None = None) -> None:
        self._logger = audit_logger

    def name(self) -> str:
        return "audit"

    def can_skip(self) -> bool:
        return True  # audit failure must never block the response

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if self._logger is None:
            return ctx

        approved = ctx.policy_result.approved if ctx.policy_result is not None else True
        args_safe = {
            "intent": str(ctx.detected_intent),
            "stage_latencies_ms": ctx.audit_record.stage_latencies,
            "warnings": ctx.audit_record.warnings,
            "sources_count": len(ctx.metadata.get("sources", [])),
        }
        result_safe = (
            f"response_chars={len(ctx.final_response or '')}" f" intent={ctx.detected_intent}"
        )

        try:
            self._logger.log_tool_call(
                agent_id=ctx.audit_record.agent_id,
                tool="pipeline",
                args_sanitized=args_safe,
                result_summary=result_safe,
                approved=approved,
                timestamp=datetime.now(UTC),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("AuditStage: failed to write audit record: {}", exc)

        return ctx
