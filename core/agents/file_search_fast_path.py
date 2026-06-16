"""Deterministic file-search pre-route — skips LLM JSON for find/list intents."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from core.tools.handlers.filesystem import search_files, validate_path

_WRITE_VERB_RE = re.compile(
    r"\b(crea|crear|escribe|escribir|write|create|guarda|guardar)\b",
    re.IGNORECASE,
)
_SEARCH_VERB_RE = re.compile(
    r"\b(busca|buscar|encuentra|encontrar|localiza|localizar|mu[eé]strame|muestra|"
    r"lista|listar|search|find|look\s+for|where\s+is|d[oó]nde\s+est[aá])\b",
    re.IGNORECASE,
)
_META_QUESTION_RE = re.compile(
    r"^(expl[ií]came|explain|qu[eé]\s+es|what\s+is|what\s+are|c[oó]mo\s+funciona|"
    r"how\s+(?:do|does|can|to))\b",
    re.IGNORECASE,
)
_FILE_NOUN_RE = re.compile(r"\b(archivos?|ficheros?|files?)\b", re.IGNORECASE)
_EXT_HINT_RE = re.compile(
    r"(?:extensi[oó]n|extension|tipo|formato)\s+[\"']?\.?([\w]{1,12})[\"']?",
    re.IGNORECASE,
)
_GLOB_RE = re.compile(
    r"(\*\.[\w]+|\*\*?/?[\w*./\\-]+|[\w][\w.\-]*\.(?:py|txt|md|json|js|ts|pdf|csv|ya?ml|gguf))",
    re.IGNORECASE,
)
_NAMED_RE = re.compile(
    r"(?:archivo|file|fichero)s?\s+(?:llamado|named|called|de\s+nombre)\s+"
    r"[\"']?([\w][\w.\-]*)[\"']?",
    re.IGNORECASE,
)
_FIND_NAMED_RE = re.compile(
    r"(?:find|search\s+for|busca(?:r)?)\s+(?:files?\s+)?"
    r"(?:named|called|llamados?|de\s+nombre)\s+[\"']?([\w][\w.\-]*)[\"']?",
    re.IGNORECASE,
)
_CONTENT_RE = re.compile(
    r"(?:conteniendo|contenga|que\s+contengan?|with|that\s+contain(?:s)?)\s+"
    r"[\"']?(.+?)[\"']?\s*$",
    re.IGNORECASE,
)
_PY_FILES_RE = re.compile(
    r"\b(archivos?\s+)?(?:de\s+)?python\b|\bpython\s+files?\b|\b\.py\b",
    re.IGNORECASE,
)

_LOCATION_RE = re.compile(
    r"\b(en|dentro de|solo en|on|in|inside)\s+(el\s+)?"
    r"(escritorio|desktop|documentos|documents|descargas|downloads)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FileSearchIntent:
    pattern: str = "*"
    extension: str | None = None
    name_contains: str | None = None
    query_text: str | None = None
    max_results: int = 20


def _paths_from_env(var_name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return [str(Path(p).expanduser().resolve()) for p in defaults]
    return [str(Path(p.strip()).expanduser().resolve()) for p in raw.split(":") if p.strip()]


def authorized_read_paths() -> list[str]:
    cerebro_files = os.path.expanduser(os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles"))
    repo_default = str(Path(__file__).resolve().parents[2])
    return _paths_from_env(
        "CEREBRO_AUTHORIZED_READ_PATHS",
        [repo_default, cerebro_files, "~/Desktop"],
    )


def is_file_search_query(query: str) -> bool:
    text = query.strip()
    if not text or len(text) < 4:
        return False
    # Reject meta-questions about searching (not actual search requests)
    if _META_QUESTION_RE.search(text):
        return False
    # If there's a write intent without search intent, skip
    if _WRITE_VERB_RE.search(text) and _FILE_NOUN_RE.search(text):
        if not _SEARCH_VERB_RE.search(text):
            return False
    # Bare glob patterns like "*.py" are search queries even without a verb
    if _GLOB_RE.search(text) and len(text) < 30:
        return True
    if not _SEARCH_VERB_RE.search(text):
        # No search verb — but content or file-name patterns still count
        if _FILE_NOUN_RE.search(text) and (
            _CONTENT_RE.search(text)
            or _NAMED_RE.search(text)
            or _FIND_NAMED_RE.search(text)
            or _EXT_HINT_RE.search(text)
            or _PY_FILES_RE.search(text)
        ):
            return True
        return False
    if _FILE_NOUN_RE.search(text):
        return True
    if _GLOB_RE.search(text):
        return True
    if _NAMED_RE.search(text) or _FIND_NAMED_RE.search(text):
        return True
    if _EXT_HINT_RE.search(text) or _PY_FILES_RE.search(text):
        return True
    if _CONTENT_RE.search(text):
        return True
    return False


def _resolve_base_path(query: str, authorized_paths: list[str]) -> str | None:
    """Map natural-language locations (escritorio, documents, downloads) to a base_path.

    Only returns a path if it is inside one of the authorized_paths.
    """
    m = _LOCATION_RE.search(query)
    if not m:
        return None

    location = m.group(3).lower()
    home = Path.home()
    candidate: Path | None = None

    if location in {"escritorio", "desktop"}:
        candidate = home / "Desktop"
    elif location in {"documentos", "documents"}:
        candidate = home / "Documents"
    elif location in {"descargas", "downloads"}:
        candidate = home / "Downloads"

    if candidate is None:
        return None

    resolved = str(candidate.expanduser().resolve())
    if not validate_path(resolved, authorized_paths):
        return None
    return resolved


def parse_file_search_intent(query: str) -> FileSearchIntent | None:
    if not is_file_search_query(query):
        return None

    pattern = "*"
    extension: str | None = None
    name_contains: str | None = None
    query_text: str | None = None
    max_results = 20

    if m := _EXT_HINT_RE.search(query):
        extension = f".{m.group(1).lower()}"
    elif _PY_FILES_RE.search(query):
        extension = ".py"

    if m := _FIND_NAMED_RE.search(query):
        name_contains = m.group(1)
        pattern = f"*{name_contains}*"
    elif m := _NAMED_RE.search(query):
        name_contains = m.group(1)
        pattern = f"*{name_contains}*"

    globs = _GLOB_RE.findall(query)
    if globs:
        pattern = globs[-1]

    if m := _CONTENT_RE.search(query):
        query_text = m.group(1).strip()

    if re.search(r"\b(solo|only)\s+(uno|un|one|1)\b", query, re.I):
        max_results = 1
    elif m_limit := re.search(r"\b(primeros?|first)\s+(\d{1,2})\b", query, re.I):
        max_results = min(int(m_limit.group(2)), 50)

    return FileSearchIntent(
        pattern=pattern,
        extension=extension,
        name_contains=name_contains,
        query_text=query_text,
        max_results=max_results,
    )


def try_file_search_fast_path(
    query: str,
    authorized_tools: list[str] | None,
    *,
    authorized_paths: list[str] | None = None,
) -> str | None:
    """Run search_files locally when the user asks to find/list files."""
    tools = authorized_tools or []
    # Empty tools list means "no restriction" — allow search.
    # Only reject when a non-empty tool list lacks search_files.
    if tools and "search_files" not in tools:
        return None

    intent = parse_file_search_intent(query)
    if intent is None:
        return None

    paths = authorized_paths or authorized_read_paths()
    return search_files(
        intent.pattern,
        paths,
        base_path=_resolve_base_path(query, paths),
        extension=intent.extension,
        name_contains=intent.name_contains,
        query_text=intent.query_text,
        max_results=intent.max_results,
    )
