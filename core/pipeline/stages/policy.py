"""Stage 5 — Policy Validation.

Validates the assembled prompt (not individual tool calls — that is handled by
core.tools.policy.PolicyEngine). This stage enforces input-level security:
length limits, blocked content patterns, and basic sanity checks.
"""

from __future__ import annotations

from loguru import logger

from core.pipeline.pipeline import PipelineContext

try:
    from core.tools.policy import PolicyResult
except ImportError:  # pragma: no cover
    PolicyResult = None  # type: ignore[assignment,misc]

_DEFAULT_MAX_PROMPT_CHARS = 16_000  # generous post-assembly limit
_DEFAULT_BLOCKED_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your instructions",
    "forget your system prompt",
]


class PolicyValidationStage:
    """Prompt-level policy gate.

    Sets ctx.policy_result to approved=False if the prompt violates rules.
    Does NOT raise — downstream stages are responsible for checking the result.
    """

    def __init__(
        self,
        max_prompt_chars: int = _DEFAULT_MAX_PROMPT_CHARS,
        blocked_patterns: list[str] | None = None,
    ) -> None:
        self._max_chars = max_prompt_chars
        self._blocked = (
            blocked_patterns if blocked_patterns is not None else _DEFAULT_BLOCKED_PATTERNS
        )

    def name(self) -> str:
        return "policy_validation"

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        prompt = ctx.prompt or ctx.normalized_input or ctx.raw_input

        if len(prompt) > self._max_chars:
            reason = f"Prompt exceeds maximum length ({len(prompt)} > {self._max_chars} chars)"
            logger.warning("PolicyValidationStage: {}", reason)
            ctx.policy_result = _denied(reason)
            return ctx

        lower = prompt.lower()
        for pattern in self._blocked:
            if pattern in lower:
                reason = f"Blocked pattern detected: '{pattern}'"
                logger.warning("PolicyValidationStage: {}", reason)
                ctx.policy_result = _denied(reason)
                return ctx

        ctx.policy_result = _approved()
        return ctx


def _approved() -> PolicyResult:
    return PolicyResult(
        approved=True,
        requires_user_confirmation=False,
        reason=None,
        sanitized_args={},
    )


def _denied(reason: str) -> PolicyResult:
    return PolicyResult(
        approved=False,
        requires_user_confirmation=False,
        reason=reason,
        sanitized_args={},
    )
