from __future__ import annotations

import os
import re

import httpx
from loguru import logger

from core.agents.intent_keywords import classify_intent_fast

_CLASSIFY_PROMPT = """\
Classify the user's request into ONE category:
- code: programming, debugging, scripts, technical problems
- calendar: scheduling, events, reminders, dates
- academic: notes, summaries, study, documents, PDFs
- general: everything else

Respond with ONLY the category word.

User: {query}
Category:"""

_CATEGORY_RE = re.compile(r"\b(code|calendar|academic|general)\b", re.IGNORECASE)


class LLMRouter:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        model: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model or os.getenv(
            "CEREBRO_LLAMACPP_MODEL",
            "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        )

    async def classify(self, query: str) -> str:
        fast = classify_intent_fast(query)
        if fast is not None:
            return fast

        truncated = query[:300]
        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": _CLASSIFY_PROMPT.format(query=truncated)},
            ],
            "max_tokens": 5,
            "temperature": 0.0,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip().lower()
                match = _CATEGORY_RE.search(content)
                if match:
                    return match.group(1).lower()
                logger.warning(
                    "LLMRouter: unexpected response '{}', falling back to general", content
                )
        except Exception as exc:
            logger.warning("LLMRouter classify failed: {} — falling back to general", exc)
        return "general"
