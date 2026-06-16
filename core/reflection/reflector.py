"""Reflection-Turn module — lightweight answer critic.

Wraps a small critic model (e.g. SmolLM2-135M) or falls back to pure heuristic
checks.  Injected into ``AgentRuntime`` so every final answer is reviewed before
it reaches the user.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.inference.registry import ChatProvider, Message


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclass
class CritiqueResult:
    """Outcome of a single critique pass.

    Attributes:
        score: 0–10 quality score (10 = perfect).
        issues: List of detected issues.
        needs_correction: True when score < 7 or any issue severity >= 4.
        corrected_answer: When a correction was applied, the new answer (else None).
        latency_ms: Time spent in critique.
    """

    score: int = 10
    issues: list[dict[str, Any]] = field(default_factory=list)
    needs_correction: bool = False
    corrected_answer: str | None = None
    latency_ms: float = 0.0


# --------------------------------------------------------------------------- #
# Heuristic rules  (no model needed)
# --------------------------------------------------------------------------- #

_HEURISTIC_RULES: list[tuple[str, str, int]] = [
    # (type, pattern_to_check, severity)
    ("format", r"(?i)\b(?:como\s+asistente|como\s+ia|como\s+modelo\s+de\s+lenguaje)\b", 3),
    ("format", r"^(?:Lo siento|Sorry)", 2),
    ("factual", r"(?i)\d{4}[-\s]\d{4}[-\s]\d{4}", 4),  # looks like invented credit card
    ("consistency", r"(?i)(?:por un lado|por otro lado).*(?:sin embargo|no obstante)", 2),
    ("completeness", r"\b(?:no\s+tengo\s+información|no\s+puedo\s+proporcionar)\b", 3),
]

# Patterns that look like a model regurgitating its training data
_TRAINING_LEAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(?:última|last)\s*(?:actualización|update|vez)\s*(?:en\s+)?\d{4}"),
    re.compile(r"(?i)my knowledge (?:is|was) (?:cut.?off|up to date)"),
    re.compile(r"(?i)(?:conocimiento|knowledge).*(?:cortado|cut.?off)"),
    re.compile(r"(?i)(?:cortado|cut.?off).*(?:conocimiento|knowledge)"),
]


def _heuristic_checks(answer: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for issue_type, pattern, severity in _HEURISTIC_RULES:
        if re.search(pattern, answer):
            issues.append(
                {
                    "type": issue_type,
                    "description": f"Patrón detectado: {pattern[:50]}",
                    "severity": severity,
                }
            )
            break  # one per type max

    for pat in _TRAINING_LEAK_PATTERNS:
        if pat.search(answer):
            issues.append(
                {
                    "type": "factual",
                    "description": "Posible fecha de entrenamiento (conocimiento estático)",
                    "severity": 4,
                }
            )
            break

    return issues


# --------------------------------------------------------------------------- #
# Prompt template for LLM-based critique
# --------------------------------------------------------------------------- #

_CRITIC_SYSTEM_PROMPT = """\
Eres un crítico de respuestas de IA. Tu única función es revisar respuestas y
señalar problemas factuales, contradicciones internas, formato incorrecto o
falta de evidencia.

Responde SOLO con JSON sin markdown:

{
  "issues": [
    {
      "type": "factual|consistency|format|completeness",
      "description": "descripción clara del problema",
      "severity": 1-5
    }
  ],
  "score": 0-10
}
"""


def _build_critique_messages(query: str, context: str | None, answer: str) -> list[Message]:
    ctx_part = f"\nContexto usado:\n{context[:1500]}" if context else ""
    return [
        {"role": "system", "content": _CRITIC_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Pregunta original:\n{query}\n"
                f"{ctx_part}"
                f"\n\nRespuesta a evaluar:\n{answer[:2000]}"
            ),
        },
    ]


# --------------------------------------------------------------------------- #
# Reflector
# --------------------------------------------------------------------------- #


class Reflector:
    """Reviews agent answers for quality issues.

    Usage::

        reflector = Reflector(provider=my_chat_provider)
        result = await reflector.critique(query, context, answer)
        if result.needs_correction:
            # re-run with result.issues as guidance
    """

    def __init__(
        self,
        provider: ChatProvider | None = None,
        enabled: bool = True,
        timeout: float = 5.0,
    ) -> None:
        self._provider = provider
        self._enabled = enabled
        self._timeout = timeout
        self._stats: dict[str, int] = {
            "triggered": 0,
            "corrected": 0,
            "skipped": 0,
        }

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    async def critique(
        self,
        query: str,
        answer: str,
        context: str | None = None,
    ) -> CritiqueResult:
        """Evaluate *answer* quality.

        Returns a ``CritiqueResult`` with score, issues, and whether a
        correction pass is recommended.
        """
        if not self._enabled:
            return CritiqueResult(score=10, needs_correction=False)

        t0 = time.perf_counter()
        self._stats["triggered"] += 1

        # 1. Heuristic checks (always run — cheap)
        issues = _heuristic_checks(answer)

        # 2. LLM critique (when a provider is configured)
        if self._provider:
            try:
                llm_issues, llm_score = await asyncio.wait_for(
                    self._llm_call(query, context, answer),
                    timeout=self._timeout,
                )
                # Merge: LLM issues take priority, but deduplicate by type
                seen_types = {i["type"] for i in issues}
                for i in llm_issues:
                    if i["type"] not in seen_types:
                        issues.append(i)
                        seen_types.add(i["type"])
                score = min(llm_score, 10)
            except TimeoutError:
                self._stats["skipped"] += 1
                score = 10
            except Exception:
                self._stats["skipped"] += 1
                score = 10
        else:
            # Heuristic-only score: start at 10, subtract based on issues
            severity_penalty = sum(i["severity"] for i in issues)
            score = max(0, 10 - severity_penalty)

        needs_correction = score < 7 or any(i.get("severity", 0) >= 4 for i in issues)
        latency = (time.perf_counter() - t0) * 1000

        if needs_correction:
            self._stats["corrected"] += 1

        return CritiqueResult(
            score=score,
            issues=issues,
            needs_correction=needs_correction,
            latency_ms=round(latency, 1),
        )

    async def _llm_call(
        self,
        query: str,
        context: str | None,
        answer: str,
    ) -> tuple[list[dict[str, Any]], int]:
        messages = _build_critique_messages(query, context, answer)
        raw = await self._provider.complete(messages, temperature=0.1)  # type: ignore[union-attr]
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw)
        issues: list[dict[str, Any]] = data.get("issues", [])
        score: int = int(data.get("score", 10))
        return issues, score
