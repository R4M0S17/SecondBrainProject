"""Build llama.cpp GBNF grammars for agent JSON responses."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

_TOOL_NAME_RULE_MARKER = "# TOOL_NAME_RULE"
_TOOL_NAME_RULE_PATTERN = re.compile(
    r"# TOOL_NAME_RULE[^\n]*\ntool-name ::= .*",
    re.MULTILINE,
)


def grammar_base_path() -> Path:
    root = Path(os.getenv("CEREBRO_ROOT", Path(__file__).resolve().parents[2]))
    return root / "config" / "grammars" / "agent_response.gbnf"


@lru_cache(maxsize=64)
def build_agent_response_grammar(authorized_tools: tuple[str, ...]) -> str:
    """Return GBNF text constraining model output to answer or tool JSON shapes."""
    base = grammar_base_path().read_text(encoding="utf-8")

    if authorized_tools:
        tool_alt = " | ".join(f'"{name}"' for name in sorted(authorized_tools))
        tool_rule = f"{_TOOL_NAME_RULE_MARKER} — injected\ntool-name ::= {tool_alt} ws"
        grammar = _TOOL_NAME_RULE_PATTERN.sub(tool_rule, base, count=1)
    else:
        tool_rule = f'{_TOOL_NAME_RULE_MARKER} — no tools\ntool-name ::= "__none__" ws'
        grammar = _TOOL_NAME_RULE_PATTERN.sub(tool_rule, base, count=1)
        grammar = grammar.replace(
            "root ::= answer-response | tool-response",
            "root ::= answer-response",
            1,
        )

    return grammar


def clear_grammar_cache() -> None:
    build_agent_response_grammar.cache_clear()
