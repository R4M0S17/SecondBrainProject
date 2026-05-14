from __future__ import annotations

import re

import httpx
from loguru import logger

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

_INTENT_RE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(cumple|cumplea|birthday|anniversary)\w*", re.IGNORECASE), "calendar"),
    (
        re.compile(
            r"\b(evento|reuni[oó]n|cita|calendar|hora|d[ií]a|fecha)\w*",
            re.IGNORECASE,
        ),
        "calendar",
    ),
    (
        re.compile(
            r"\b(c[oó]digo|funci[oó]n|bug|stack ?trace|python|typescript)\w*",
            re.IGNORECASE,
        ),
        "code",
    ),
    (
        re.compile(r"\b(paper|pdf|art[ií]culo|res[uú]me|estudia)\w*", re.IGNORECASE),
        "academic",
    ),
]


class LLMRouter:
    def __init__(self, base_url: str = "http://127.0.0.1:8080") -> None:
        self._base_url = base_url.rstrip("/")

    async def classify(self, query: str) -> str:
        q = query.lower()
        for pat, cat in _INTENT_RE:
            if pat.search(q):
                return cat
        truncated = query[:300]
        payload = {
            "model": "router",
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
