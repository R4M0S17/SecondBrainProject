"""Stage 1 — Input Normalization."""

from __future__ import annotations

from core.pipeline.pipeline import PipelineContext

_MAX_LENGTH = 4000


class InputNormalizationStage:
    def name(self) -> str:
        return "normalization"

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        text = ctx.raw_input.strip()
        if len(text) > _MAX_LENGTH:
            text = text[:_MAX_LENGTH]
            ctx.audit_record.warnings.append("input_truncated")
        ctx.normalized_input = text
        ctx.metadata["detected_language"] = _detect_language(text)
        return ctx


def _detect_language(text: str) -> str:
    """Heuristic: count Spanish-specific characters and common words."""
    spanish_chars = set("áéíóúüñ¿¡")
    spanish_words = {
        "el",
        "la",
        "de",
        "que",
        "en",
        "y",
        "los",
        "del",
        "las",
        "un",
        "una",
        "es",
        "por",
        "con",
        "como",
    }
    lower = text.lower()
    char_hits = sum(1 for c in lower if c in spanish_chars)
    word_hits = sum(1 for w in lower.split() if w in spanish_words)
    return "es" if char_hits + word_hits >= 2 else "en"
