"""Tests for Module A4 — Pipeline Middleware."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from core.pipeline.pipeline import (
    AuditRecord,
    Intent,
    Pipeline,
    PipelineContext,
)
from core.pipeline.stages.audit import AuditStage
from core.pipeline.stages.context import ContextRetrievalStage
from core.pipeline.stages.intent import IntentDetectionStage
from core.pipeline.stages.normalization import InputNormalizationStage
from core.pipeline.stages.policy import PolicyValidationStage
from core.pipeline.stages.postprocess import PostProcessingStage
from core.pipeline.stages.prompt import PromptAssemblyStage
from core.pipeline.stages.tools import ToolExecutionStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_audit() -> AuditRecord:
    return AuditRecord(
        agent_id="test-agent",
        query_id="test-query",
        timestamp=datetime.now(UTC),
    )


def _build_full_pipeline() -> Pipeline:
    """Return a Pipeline with all 8 stages wired (no real backends — no-op stubs)."""
    return Pipeline(
        stages=[
            InputNormalizationStage(),
            IntentDetectionStage(),
            ContextRetrievalStage(),  # no builder → no-op
            PromptAssemblyStage(),
            PolicyValidationStage(),
            ToolExecutionStage(),  # no engine → warning response
            PostProcessingStage(),
            AuditStage(),  # no logger → no-op
        ]
    )


# ---------------------------------------------------------------------------
# Test 1: Full pipeline executes all 8 stages in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_executes_all_eight_stages_in_order():
    """All 8 stage names must appear in audit_record.stage_latencies after run()."""
    pipeline = _build_full_pipeline()

    ctx = await pipeline.run("¿Cuál es el significado de la vida?", agent_id="agent-1")

    executed = list(ctx.audit_record.stage_latencies.keys())

    expected_order = [
        "normalization",
        "intent_detection",
        "context_retrieval",
        "prompt_assembly",
        "policy_validation",
        "tool_execution",
        "post_processing",
        "audit",
    ]
    assert executed == expected_order, f"Unexpected order: {executed}"
    assert ctx.final_response is not None


# ---------------------------------------------------------------------------
# Test 2: Stage with can_skip=True that fails does not abort the pipeline
# ---------------------------------------------------------------------------


class _FailingSkippableStage:
    """A stage that always raises and declares itself skippable."""

    def name(self) -> str:
        return "failing_skippable"

    def can_skip(self) -> bool:
        return True

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        raise RuntimeError("Simulated stage failure")


class _RecordingStage:
    """A stage that appends its name to ctx.metadata['order'] so we can verify execution."""

    def __init__(self, tag: str) -> None:
        self._tag = tag

    def name(self) -> str:
        return self._tag

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.metadata.setdefault("order", []).append(self._tag)
        ctx.raw_response = ctx.raw_response or "response"
        ctx.final_response = ctx.final_response or "response"
        return ctx


@pytest.mark.asyncio
async def test_can_skip_stage_failure_does_not_abort_pipeline():
    """A stage with can_skip=True that raises must be skipped with a warning
    and the pipeline must continue executing subsequent stages."""
    pipeline = Pipeline(
        stages=[
            _RecordingStage("stage_a"),
            _FailingSkippableStage(),
            _RecordingStage("stage_b"),
        ]
    )

    ctx = await pipeline.run("test input")

    # Both non-failing stages ran
    assert ctx.metadata.get("order") == ["stage_a", "stage_b"]
    # The skip was recorded in warnings
    assert any("failing_skippable" in w for w in ctx.audit_record.warnings)
    # The failing stage's latency is still recorded
    assert "failing_skippable" in ctx.audit_record.stage_latencies


# ---------------------------------------------------------------------------
# Test 3: insert_stage / remove_stage work without affecting other stages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_and_remove_stage_do_not_break_pipeline():
    """Dynamically adding and removing stages must preserve correct execution order."""
    pipeline = Pipeline(
        stages=[
            _RecordingStage("alpha"),
            _RecordingStage("gamma"),
        ]
    )

    # Insert "beta" after "alpha"
    pipeline.insert_stage(_RecordingStage("beta"), after="alpha")
    assert pipeline.stage_names == ["alpha", "beta", "gamma"]

    # Remove "beta"
    pipeline.remove_stage("beta")
    assert pipeline.stage_names == ["alpha", "gamma"]

    # Pipeline still runs correctly after structural changes
    ctx = await pipeline.run("hello")
    assert ctx.metadata.get("order") == ["alpha", "gamma"]


@pytest.mark.asyncio
async def test_insert_stage_raises_for_unknown_anchor():
    pipeline = Pipeline(stages=[_RecordingStage("only")])
    with pytest.raises(ValueError, match="not found"):
        pipeline.insert_stage(_RecordingStage("new"), after="nonexistent")


# ---------------------------------------------------------------------------
# Test 4: AuditRecord never contains document content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_record_never_contains_document_content():
    """The AuditStage must log only metadata — never raw document text."""
    secret_content = "TOP SECRET: nuclear launch codes are abc123"

    # Craft a context where document content exists but must not reach the logger
    mock_logger = MagicMock()
    logged_calls: list[dict] = []

    def capture_log(**kwargs):
        logged_calls.append(kwargs)

    mock_logger.log_tool_call = capture_log

    audit_stage = AuditStage(audit_logger=mock_logger)
    ctx = PipelineContext(
        raw_input="query",
        audit_record=_empty_audit(),
        normalized_input="query",
        detected_intent=Intent.RAG_QUERY,
        raw_response=secret_content,
        final_response=secret_content,
        metadata={"sources": ["/path/to/doc.pdf"], "agent_id": "test"},
    )
    # Simulate policy approved
    from core.tools.policy import PolicyResult

    ctx.policy_result = PolicyResult(
        approved=True, requires_user_confirmation=False, reason=None, sanitized_args={}
    )

    await audit_stage.process(ctx)

    assert len(logged_calls) == 1
    call = logged_calls[0]

    # Flatten all logged values to strings for content check
    log_dump = str(call)
    assert secret_content not in log_dump, "AuditStage leaked document content into the audit log"
    # Result summary must only contain metadata (lengths, intent labels)
    assert "result_summary" in call
    assert secret_content not in call["result_summary"]
