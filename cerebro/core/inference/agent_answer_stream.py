"""Incremental parser for grammar-constrained agent JSON streamed from llama.cpp."""

from __future__ import annotations

import re
from enum import Enum
from typing import Final

# Matches opening through the answer string's opening quote (GBNF allows ws).
_ANSWER_OPEN_RE: Final = re.compile(
    r'^\{\s*"action"\s*:\s*"answer"\s*,\s*"answer"\s*:\s*"',
    re.DOTALL,
)
_TOOL_OPEN_RE: Final = re.compile(
    r'^\{\s*"action"\s*:\s*"tool"',
    re.DOTALL,
)


class _Mode(str, Enum):
    SEEKING = "seeking"
    IN_ANSWER = "in_answer"
    TOOL_BUFFER = "tool_buffer"
    FAILED = "failed"


class AgentAnswerStreamParser:
    """Extract user-visible tokens from a streaming agent JSON envelope.

    Once the prefix ``{"action":"answer","answer":"`` is matched (whitespace
    per GBNF), decoded characters inside the JSON string are emitted. Tool
    responses are buffered without emission so the caller can parse the full
    payload after the stream ends.
    """

    def __init__(self) -> None:
        self._mode = _Mode.SEEKING
        self._prefix_buf = ""
        self._raw = ""
        self._escape = False
        self._unicode_hex = ""
        self._answer_closed = False

    @property
    def raw(self) -> str:
        return self._raw

    @property
    def streamed_answer(self) -> bool:
        return self._mode == _Mode.IN_ANSWER or self._answer_closed

    def feed(self, chunk: str) -> list[str]:
        if self._mode in (_Mode.TOOL_BUFFER, _Mode.FAILED) or self._answer_closed:
            self._raw += chunk
            return []

        out: list[str] = []
        for ch in chunk:
            self._raw += ch
            if self._mode == _Mode.SEEKING:
                self._prefix_buf += ch
                out.extend(self._advance_prefix())
            elif self._mode == _Mode.IN_ANSWER:
                token = self._consume_answer_char(ch)
                if token is not None:
                    out.append(token)
        return out

    def _advance_prefix(self) -> list[str]:
        buf = self._prefix_buf
        if _TOOL_OPEN_RE.match(buf):
            self._mode = _Mode.TOOL_BUFFER
            return []

        if _ANSWER_OPEN_RE.match(buf):
            self._mode = _Mode.IN_ANSWER
            self._prefix_buf = ""
            return []

        if self._could_still_match(buf):
            return []

        self._mode = _Mode.FAILED
        return []

    @staticmethod
    def _could_still_match(buf: str) -> bool:
        compact = re.sub(r"\s+", "", buf)
        if not compact.startswith("{"):
            return False
        answer_prefix = '{"action":"answer","answer":"'
        tool_prefix = '{"action":"tool"'
        if compact.startswith(tool_prefix):
            return len(compact) < len(tool_prefix) + 1
        if answer_prefix.startswith(compact) or tool_prefix.startswith(compact):
            return True
        return len(compact) <= len('{"action"')

    def _consume_answer_char(self, ch: str) -> str | None:
        if self._unicode_hex:
            self._unicode_hex += ch
            if len(self._unicode_hex) == 4:
                try:
                    decoded = chr(int(self._unicode_hex, 16))
                except ValueError:
                    decoded = ""
                self._unicode_hex = ""
                self._escape = False
                return decoded
            return None

        if self._escape:
            self._escape = False
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
            if ch == "u":
                self._unicode_hex = ""
                return None
            return mapping.get(ch, ch)

        if ch == "\\":
            self._escape = True
            return None

        if ch == '"':
            self._answer_closed = True
            self._mode = _Mode.SEEKING
            return None

        return ch
