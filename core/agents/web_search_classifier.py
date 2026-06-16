"""Web search intent classifier using lightweight LLM inference.

Replaces fragile regex patterns for informational queries with a
binary classifier: "Does this query need web search? yes/no".

Uses the existing ProviderRegistry to get whatever model is available
(Qwen3.5-2B when RAM allows, SmolLM2-360M as fallback).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from core.inference.registry import ProviderRegistry

# Prompt for binary classification — kept minimal for speed
_CLASSIFIER_PROMPT = """You are a query classifier. Determine if the user's question requires real-time information from the internet to answer accurately.

Rules:
- Say YES if the query asks about current events, recent information, definitions, explanations, facts that may change over time, or anything requiring up-to-date data.
- Say NO if the query is about personal scheduling (calendar, meetings, reminders), file operations, math calculations, or general conversation.

Reply with ONLY "yes" or "no" (lowercase, no punctuation).

Examples:
Query: what is machine learning
Answer: yes

Query: what happened today in the world
Answer: yes

Query: who is the president of france
Answer: yes

Query: how does photosynthesis work
Answer: yes

Query: what is my next meeting
Answer: no

Query: create a reminder for tomorrow
Answer: no

Query: 2+2
Answer: no

Query: find my notes file
Answer: no

Query: hello how are you
Answer: no

Query: {query}
Answer:"""

# Fallback: if LLM classifier fails, use simple heuristic
_HEURISTIC_INFO_RE = re.compile(
    r"\b(qu[eé]|what|who|how|where|when|why|define|explain|"
    r"cu[aá]l|cu[aá]ndo|c[oó]mo|d[oó]nde|por\s+qu[eé]|qui[eé]n)\b",
    re.IGNORECASE,
)

# Follow-up patterns that request summary/elaboration of previous web search
_FOLLOW_UP_RE = re.compile(
    r"\b(expl[ií]came\s+m[aá]s|expl[ií]came|explicarme\s+m[aá]s|"
    r"res[uú]melo|res[uú]mene|res[uú]meme|"
    r"dame\s+m[aá]s\s+(detalles|info|informaci[oó]n)|"
    r"m[aá]s\s+(detalles|info|informaci[oó]n)|"
    r"tell\s+me\s+more|explain\s+more|summarize|summary|"
    r"more\s+details|elaborate|give\s+me\s+(a\s+)?summary|"
    r"qu[eé]\s+m[aá]s|"
    r"profundiza|ampl[ií]a|"
    r"need\s+more\s+info|i\s+need\s+more)\b",
    re.IGNORECASE,
)


def is_follow_up_query(query: str) -> bool:
    """Check if query is a follow-up requesting more detail on previous result."""
    return bool(_FOLLOW_UP_RE.search(query.strip()))


async def classify_needs_web_search(
    query: str,
    registry: ProviderRegistry,
    *,
    timeout_seconds: float = 3.0,
) -> bool:
    """Classify whether a query needs web search using LLM.

    Falls back to heuristic regex if LLM call fails or times out.

    Args:
        query: The user's query text.
        registry: ProviderRegistry to get the chat provider.
        timeout_seconds: Max time for LLM inference (default 3s).

    Returns:
        True if query likely needs web search, False otherwise.
    """
    import asyncio

    q = query.strip()
    if not q:
        return False

    # Very short queries (< 5 chars) are unlikely to need web search
    if len(q) < 5:
        return False

    try:
        from core.inference.registry import Message, TaskHint

        provider_name = registry.select_for_task(TaskHint.CHAT)
        chat = registry.get_chat(provider_name)
    except Exception as exc:
        logger.debug("Web classifier: no chat provider available: {}", exc)
        return _heuristic_fallback(q)

    try:
        prompt = _CLASSIFIER_PROMPT.format(query=q)
        messages: list[Message] = [{"role": "user", "content": prompt}]

        # Use asyncio.wait_for to enforce timeout
        result = await asyncio.wait_for(
            chat.complete(messages, max_tokens=5, temperature=0.0),
            timeout=timeout_seconds,
        )

        answer = result.strip().lower()
        logger.debug("Web classifier LLM response: '{}' for query: '{}'", answer, q[:50])

        # Parse yes/no from response
        if "yes" in answer:
            return True
        if "no" in answer:
            return False

        # Ambiguous response — fall back to heuristic
        logger.debug("Web classifier: ambiguous response '{}', using heuristic", answer)
        return _heuristic_fallback(q)

    except TimeoutError:
        logger.debug("Web classifier: LLM timeout for query: '{}'", q[:50])
        return _heuristic_fallback(q)
    except Exception as exc:
        logger.debug("Web classifier: LLM failed: {}", exc)
        return _heuristic_fallback(q)


def _heuristic_fallback(query: str) -> bool:
    """Simple regex-based fallback when LLM is unavailable.

    Only matches common question words — less accurate than LLM
    but avoids false positives on calendar/file queries.
    """
    q = query.lower().strip()

    # Exclude obvious non-web-search patterns
    if re.search(r"\b(calendario|agenda|recordatorio|reminder)\b", q):
        return False
    if re.search(r"\b(archivo|fichero|documento|file|document)\b", q):
        return False
    if re.search(r"\d+\s*[+\-*×x/]\s*\d+", q):
        return False

    return bool(_HEURISTIC_INFO_RE.search(q))
