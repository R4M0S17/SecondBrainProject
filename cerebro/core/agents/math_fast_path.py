"""Zero-token arithmetic fast path (FIX_TEST2 H3.1).

Pure numeric expressions are evaluated via :func:`evaluate_math` before the
LangGraph runs. Word problems still use the LLM + ``evaluate_math`` tool.
"""

from __future__ import annotations

import re

from core.tools.handlers.math import evaluate_math

# Entire query is (mostly) a numeric expression.
_PURE_MATH_RE = re.compile(
    r"^\s*([\d\s+\-*/()×x.,%]+)\s*[?.=!]?\s*$",
    re.IGNORECASE,
)

# Span inside phrased prompts: ``What is 17 × 23? Show only the number.``
_EMBEDDED_EXPR_RE = re.compile(
    r"(\d+(?:[.,]\d+)?(?:\s*(?:\*\*|//|[+\-*/×x%])\s*\d+(?:[.,]\d+)?)+)",
    re.IGNORECASE,
)

_HAS_OPERATOR_RE = re.compile(
    r"(?:\*\*|//|[+\-*/%]|(?<=\d)[×x](?=\d))",
    re.IGNORECASE,
)


def _normalize_math_expr(expr: str) -> str:
    normalized = expr.replace("×", "*").strip()
    return re.sub(r"(?<=\d)x(?=\d)", "*", normalized, flags=re.IGNORECASE)


def _is_valid_pure_math(expr: str) -> bool:
    if not expr or not re.search(r"\d", expr):
        return False
    return _HAS_OPERATOR_RE.search(expr) is not None


def extract_pure_math_expression(query: str) -> str | None:
    """Return a normalized expression string, or None if not pure arithmetic."""
    text = query.strip()
    if not text:
        return None

    whole = _PURE_MATH_RE.match(text)
    if whole:
        expr = _normalize_math_expr(whole.group(1))
        if _is_valid_pure_math(expr):
            return expr

    for match in _EMBEDDED_EXPR_RE.finditer(text):
        expr = _normalize_math_expr(match.group(1))
        if not _is_valid_pure_math(expr):
            continue
        if _PURE_MATH_RE.match(expr):
            return expr

    return None


def try_pure_math_fast_path(
    query: str,
    authorized_tools: list[str] | None,
) -> str | None:
    """Evaluate pure arithmetic locally; return answer text or None to use the LLM."""
    tools = authorized_tools or []
    if tools and "evaluate_math" not in tools:
        return None

    expr = extract_pure_math_expression(query)
    if expr is None:
        return None

    result = evaluate_math(expr)
    if result.startswith("Error:"):
        return None
    return result
