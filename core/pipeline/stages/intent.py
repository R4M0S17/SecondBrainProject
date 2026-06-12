"""Stage 2 — Intent Detection."""

from __future__ import annotations

from core.pipeline.pipeline import Intent, PipelineContext

_QUESTION_WORDS = {
    "qué",
    "quién",
    "cómo",
    "cuándo",
    "dónde",
    "por qué",
    "cuál",
    "what",
    "who",
    "how",
    "when",
    "where",
    "why",
    "which",
}


class IntentDetectionStage:
    def name(self) -> str:
        return "intent_detection"

    def can_skip(self) -> bool:
        return True  # intent defaults to UNKNOWN if this stage fails

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        text = (ctx.normalized_input or ctx.raw_input).strip()

        if text.startswith("/config"):
            ctx.detected_intent = Intent.CONFIG
        elif text.startswith("/academic"):
            ctx.detected_intent = Intent.AGENT_ACTION
            ctx.metadata.setdefault("intent_tags", [])
            ctx.metadata["intent_tags"].append("academic")
        elif text.startswith("/code"):
            ctx.detected_intent = Intent.AGENT_ACTION
            ctx.metadata.setdefault("intent_tags", [])
            ctx.metadata["intent_tags"].append("code")
        elif _looks_like_question(text):
            ctx.detected_intent = Intent.RAG_QUERY
        else:
            ctx.detected_intent = Intent.AGENT_ACTION

        return ctx


def _looks_like_question(text: str) -> bool:
    lower = text.lower()
    if text.strip().endswith("?") or text.strip().startswith("¿"):
        return True
    first_word = lower.split()[0] if lower.split() else ""
    return first_word in _QUESTION_WORDS
