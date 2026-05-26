"""Shared helpers for parsing and repairing LLM JSON tool responses."""

from __future__ import annotations

import re

_FENCE_BLOCK_RE = re.compile(r"^```(?:json|JSON)?\s*\n(.*)\n```\s*$", re.DOTALL)
_UNQUOTED_VALUE_RE = re.compile(r'("(?:tool|action)"\s*:\s*)([A-Za-z_][A-Za-z0-9_]*)')


def strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences; tolerate trailing whitespace on the closing fence."""
    stripped = text.strip()
    match = _FENCE_BLOCK_RE.match(stripped)
    if match:
        return match.group(1).strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if not lines:
        return stripped
    first = lines[0].strip()
    if first.lower() in ("```json", "```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_object(text: str) -> str | None:
    """Return the first balanced `{...}` object, respecting JSON string literals."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def repair_tool_json(text: str) -> str:
    """Quote bare identifiers after ``tool`` / mistaken tool-in-``action`` keys."""

    def _quote(m: re.Match[str]) -> str:
        key, val = m.group(1), m.group(2)
        if val in ("tool", "answer", "true", "false", "null"):
            return m.group(0)
        return f'{key}"{val}"'

    return _UNQUOTED_VALUE_RE.sub(_quote, text)
