"""Deterministic file-write pre-route (Problem A / FIX_TEST2 H3.3).

Parses explicit create-file intents and returns ``write_file`` args without
relying on the LLM to emit valid tool JSON. The runtime still pauses for user
confirmation before anything is written.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from core.tools.handlers.filesystem import validate_path

_FILENAME = r"[\w][\w.\-]*(?:\.\w{1,12})?"
_ABS_PATH = r"(?:~|/)[^\s\"']+\.\w{1,12}"

# Spanish: crea [un] archivo [llamado|de nombre] X [con] (contenido|texto) Y
_ES_CREATE_RE = re.compile(
    rf"(?:crea|crear|escribe|escribir|guarda|guardar)\s+"
    rf"(?:un\s+)?(?:archivo|fichero)\s+"
    rf"(?:(?:llamado|de\s+nombre|nombrado)\s+)?"
    rf"[\"']?(?P<filename>{_FILENAME})[\"']?"
    rf"\s+(?:con\s+)?(?:contenido|el\s+texto|texto)\s+(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Shorter Spanish: crea archivo X con contenido Y
_ES_CREATE_SHORT_RE = re.compile(
    rf"(?:crea|crear)\s+(?:un\s+)?(?:archivo|fichero)\s+"
    rf"[\"']?(?P<filename>{_FILENAME})[\"']?"
    rf"\s+con\s+(?:contenido|el\s+texto)\s+(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# English: write/create/save [a] file [called|named] X with [content|the word] Y
_EN_CREATE_RE = re.compile(
    rf"(?:write|create|save)\s+(?:a\s+)?file\s+"
    rf"(?:called|named)\s+[\"']?(?P<filename>{_FILENAME})[\"']?"
    rf"\s+(?:with\s+)?(?:content\s+|the\s+word\s+|containing\s+)?(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Explicit write_file mention
_EXPLICIT_WRITE_RE = re.compile(
    rf"write_file.*?(?:path|ruta)\s*[=:]?\s*[\"']?(?P<path>{_ABS_PATH}|{_FILENAME})[\"']?"
    rf".*?(?:content|contenido)\s*[=:]?\s*[\"']?(?P<content>.+?)[\"']?\s*$",
    re.IGNORECASE | re.DOTALL,
)

# crear PATH con contenido TEXT
_CREAR_PATH_RE = re.compile(
    rf"(?:crea|crear)\s+(?P<path>{_ABS_PATH}|{_FILENAME})\s+"
    rf"con\s+(?:contenido|el\s+texto)\s+(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# PATH con contenido TEXT
_PATH_CONTENT_RE = re.compile(
    rf"(?P<path>{_ABS_PATH}|{_FILENAME})\s+con\s+(?:contenido|el\s+texto)\s+(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Usa write_file para crear PATH con contenido TEXT
_USA_WRITE_RE = re.compile(
    rf"write_file\s+para\s+crear\s+(?P<path>{_ABS_PATH}|{_FILENAME})\s+"
    rf"con\s+contenido\s+(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_QUOTED_CONTENT_RE = re.compile(
    r"^(?:contenido|content|texto|text)\s+(.+)$",
    re.IGNORECASE,
)

_PATTERNS: list[re.Pattern[str]] = [
    _EXPLICIT_WRITE_RE,
    _USA_WRITE_RE,
    _CREAR_PATH_RE,
    _PATH_CONTENT_RE,
    _ES_CREATE_RE,
    _ES_CREATE_SHORT_RE,
    _EN_CREATE_RE,
]


@dataclass(frozen=True)
class FileWriteIntent:
    path: str
    content: str
    filename: str


def _paths_from_env(var_name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return [str(Path(p).expanduser().resolve()) for p in defaults]
    return [str(Path(p.strip()).expanduser().resolve()) for p in raw.split(":") if p.strip()]


def default_write_root() -> str:
    return str(
        Path(os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles")).expanduser().resolve()
    )


def authorized_write_paths() -> list[str]:
    root = default_write_root()
    return _paths_from_env("CEREBRO_AUTHORIZED_WRITE_PATHS", [root])


def _clean_content(raw: str) -> str:
    text = raw.strip().strip("\"'").strip()
    text = re.sub(r"[.?!]+\s*$", "", text).strip()
    m = _QUOTED_CONTENT_RE.match(text)
    if m:
        return m.group(1).strip().strip("\"'")
    return text


def _resolve_path(path_or_name: str, write_roots: list[str]) -> str | None:
    candidate = Path(path_or_name.strip().strip("\"'")).expanduser()
    if not candidate.is_absolute():
        candidate = Path(write_roots[0]) / candidate.name
    resolved = candidate.resolve()
    if validate_path(str(resolved), write_roots):
        return str(resolved)
    return None


def _intent_from_match(m: re.Match[str], write_roots: list[str]) -> FileWriteIntent | None:
    path_or_name = m.groupdict().get("path") or m.groupdict().get("filename")
    content_raw = m.groupdict().get("content")
    if not path_or_name or not content_raw:
        return None
    content_clean = _clean_content(content_raw)
    if not content_clean:
        return None
    resolved = _resolve_path(path_or_name, write_roots)
    if resolved is None:
        return None
    return FileWriteIntent(
        path=resolved,
        content=content_clean,
        filename=Path(resolved).name,
    )


def parse_file_write_intent(
    query: str,
    *,
    write_roots: list[str] | None = None,
) -> FileWriteIntent | None:
    """Return a resolved write intent, or None if the query is not a file-create request."""
    text = query.strip()
    if not text:
        return None

    roots = write_roots or authorized_write_paths()
    if not roots:
        return None

    for pattern in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        intent = _intent_from_match(m, roots)
        if intent is not None:
            return intent

    return None


def try_file_write_fast_path(
    query: str,
    authorized_tools: list[str] | None,
    *,
    write_roots: list[str] | None = None,
) -> FileWriteIntent | None:
    """Parse a file-create query when ``write_file`` is allowed for this agent."""
    tools = authorized_tools or []
    if tools and "write_file" not in tools:
        return None
    return parse_file_write_intent(query, write_roots=write_roots)
