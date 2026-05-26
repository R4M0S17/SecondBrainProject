"""Deterministic file-write pre-route (Problem A / FIX_TEST2 H3.3).

Parses explicit create-file intents and returns ``write_file`` args without
relying on the LLM to emit valid tool JSON. Content may be literal, extracted
from fenced code, or a specification that requires LLM generation in runtime.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.tools.handlers.filesystem import validate_path

ContentSource = Literal["literal", "fenced", "spec"]

_FILENAME = r"[\w][\w.\-]*(?:\.\w{1,12})?"
_ABS_PATH = r"(?:~|/)[^\s\"']+\.\w{1,12}"
# ASCII + Spanish curly quotes around filenames in chat UI.
_QUOTE = r"[\"'“”‘’]"

_INVALID_FILENAMES = frozenset(
    {"de", "un", "el", "la", "los", "las", "texto", "ejemplo", "archivo"}
)

# Spanish: crea [un] archivo [llamado|de nombre] X [con] (contenido|texto) Y
_ES_CREATE_RE = re.compile(
    rf"(?:crea|crear|escribe|escribir|guarda|guardar)\s+"
    rf"(?:un\s+)?(?:archivo|fichero)\s+"
    rf"(?:(?:llamado|de\s+nombre|nombrado)\s+)?"
    rf"{_QUOTE}?(?P<filename>{_FILENAME}){_QUOTE}?"
    # User language is often: "crea un archivo X con una función..." (sin "contenido"/"texto").
    # We treat that as the file body/spec.
    rf"\s+(?:con\s+)?"
    rf"(?:(?:contenido|el\s+contenido|el\s+texto|texto)(?:\s+de)?\s+)?"
    rf"(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_ES_CREATE_SHORT_RE = re.compile(
    rf"(?:crea|crear)\s+(?:un\s+)?(?:archivo|fichero)\s+"
    rf"{_QUOTE}?(?P<filename>{_FILENAME}){_QUOTE}?"
    rf"\s+con\s+"
    rf"(?:(?:contenido|el\s+contenido|el\s+texto|texto)(?:\s+de)?\s+)?"
    rf"(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_EN_CREATE_RE = re.compile(
    rf"(?:write|create|save)\s+(?:a\s+)?file\s+"
    rf"(?:called|named)\s+{_QUOTE}?(?P<filename>{_FILENAME}){_QUOTE}?"
    rf"\s+(?:with\s+)?(?:content\s+|the\s+word\s+|containing\s+)?(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_EXPLICIT_WRITE_RE = re.compile(
    rf"write_file.*?(?:path|ruta)\s*[=:]?\s*[\"']?(?P<path>{_ABS_PATH}|{_FILENAME})[\"']?"
    rf".*?(?:content|contenido)\s*[=:]?\s*[\"']?(?P<content>.+?)[\"']?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_CREAR_PATH_RE = re.compile(
    rf"(?:crea|crear)\s+(?P<path>{_ABS_PATH}|{_FILENAME})\s+"
    rf"con\s+"
    rf"(?:(?:contenido|el\s+contenido|el\s+texto|texto)(?:\s+de)?\s+)?"
    rf"(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_PATH_CONTENT_RE = re.compile(
    rf"(?P<path>{_ABS_PATH}|{_FILENAME})\s+con\s+"
    rf"(?:(?:contenido|el\s+contenido|el\s+texto|texto)(?:\s+de)?\s+)?"
    rf"(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_ES_CREATE_CALENDAR_RE = re.compile(
    rf"(?:crea|crear|escribe|escribir|guarda|guardar)\s+"
    rf"(?:un\s+)?(?:archivo|fichero)\s+"
    rf"(?:(?:llamado|de\s+nombre|nombrado)\s+)?"
    rf"{_QUOTE}?(?P<filename>{_FILENAME}){_QUOTE}?"
    rf"\s+(?:con\s+)?"
    # Calendar-backed export requests are commonly written as:
    # "crea un archivo X con los proximos cumpleaños en mi calendario"
    # so we allow missing "contenido" keyword, but only when calendar keywords appear.
    rf"(?=(?:.|\n)*\b(?:cumpleaños|cumpleaño|cumple|birthday|anniversary|calendario|agenda)\b)"
    rf"(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_USA_WRITE_RE = re.compile(
    rf"write_file\s+para\s+crear\s+(?P<path>{_ABS_PATH}|{_FILENAME})\s+"
    rf"con\s+(?:(?:contenido)(?:\s+de)?\s+)?(?P<content>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_QUOTED_CONTENT_RE = re.compile(
    r"^(?:contenido|content|texto|text)\s+(.+)$",
    re.IGNORECASE,
)

_FENCED_CODE_RE = re.compile(r"```(?:\w+)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)

_SPEC_HINT_RE = re.compile(
    r"\b("
    r"programa|script|c[oó]digo|funci[oó]n|recursi[oó]n|fibonacci|"
    r"recet[ao]s?|panqueques?|crepes?|cocinar|"
    r"tabla(?:s)?|verdad|matem[aá]tica|discreta|l[oó]gica|"
    r"videojuegos?|playstation|ps\d|nombres?|mujer(?:es)?|hombre(?:s)?|inventad[oa]s?|"
    r"lista|listado|ejemplos?|ideas?|"
    r"cumplea(?:ñ|n)os|cumplea(?:ñ|n)o|cumpleannos|cumpleanos|cumpleaños|cumpleaño|cumple|"
    r"implementa|usando|que\s+calcule|que\s+haga|en\s+python|en\s+javascript|"
    r"secuencia\s+de|archivo\s+python"
    r")\b",
    re.IGNORECASE,
)

# Meta-instructions captured by the parser (not file bytes).
_INSTRUCTION_PREFIX_RE = re.compile(
    r"^(?:"
    r"(?:en\s+)?(?:donde|el\s+cual)\s+(?:escribas|escribes|escribir|pon(?:gas|ga)|incluyas|incluya)|"
    r"en\s+el\s+que\s+(?:escribas|escribes)|"
    r"que\s+(?:contenga|tenga|incluya)\s+"
    r")",
    re.IGNORECASE,
)

_QUANTITY_NOUN_RE = re.compile(
    r"^(?:solamente\s+|solo\s+)?\d+\s+\w+",
    re.IGNORECASE,
)

_SOURCE_CODE_RE = re.compile(
    r"^\s*(def |class |import |from |#include|function |const |let |var |public |package )",
    re.MULTILINE,
)

_PATTERNS: list[re.Pattern[str]] = [
    _EXPLICIT_WRITE_RE,
    _USA_WRITE_RE,
    _CREAR_PATH_RE,
    _PATH_CONTENT_RE,
    _ES_CREATE_CALENDAR_RE,
    _ES_CREATE_RE,
    _ES_CREATE_SHORT_RE,
    _EN_CREATE_RE,
]


@dataclass(frozen=True)
class FileWriteIntent:
    path: str
    content: str
    filename: str
    content_source: ContentSource = "literal"
    content_spec: str = ""
    generated: bool = False
    filled_from: str = ""

    def with_content(self, content: str, *, source: ContentSource = "literal") -> FileWriteIntent:
        return FileWriteIntent(
            path=self.path,
            content=content,
            filename=self.filename,
            content_source=source,
            content_spec=self.content_spec,
            generated=True,
            filled_from=self.filled_from,
        )


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
    # Strip both ASCII quotes and common Spanish curly quotes.
    text = raw.strip().strip("\"'“”‘’").strip()
    text = re.sub(r"[.?!]+\s*$", "", text).strip()
    m = _QUOTED_CONTENT_RE.match(text)
    if m:
        return m.group(1).strip().strip("\"'“”‘’")
    return text


def extract_fenced_code(text: str) -> str | None:
    m = _FENCED_CODE_RE.search(text)
    if not m:
        return None
    code = m.group(1).strip()
    return code or None


def _looks_like_source_code(text: str) -> bool:
    return bool(_SOURCE_CODE_RE.search(text))


def _normalize_spec_text(text: str) -> str:
    """Strip leading instructional wrappers so generation gets a clean brief."""
    out = text.strip()
    out = _INSTRUCTION_PREFIX_RE.sub("", out).strip()
    out = re.sub(r"^(?:solamente|solo)\s+", "", out, flags=re.IGNORECASE).strip()
    return out


def _looks_like_finished_literal(text: str) -> bool:
    """True when the captured fragment is plausibly the final file body."""
    stripped = text.strip()
    if not stripped:
        return False
    # Multi-line structured content (tables, lists, recipes with steps).
    if "\n" in stripped and len(stripped) > 40:
        return True
    # Truth-table style rows.
    if re.search(r"\b[TF01]\b.*\b[TF01]\b", stripped) or "|" in stripped:
        return True
    # Comma-separated list of short items the user likely pasted verbatim.
    if "," in stripped and not _QUANTITY_NOUN_RE.match(stripped):
        if _SPEC_HINT_RE.search(stripped):
            return False
        parts = [p.strip() for p in stripped.split(",") if p.strip()]
        if len(parts) >= 2 and all(2 < len(p) <= 32 for p in parts):
            return True
    # Very short exact literals the user likely meant verbatim.
    if len(stripped) <= 48 and not _SPEC_HINT_RE.search(stripped):
        if not re.search(
            r"\b(con|para|usando|inventad|escrib|genera|tabla|lista|videojuego|nombre)\b",
            stripped,
            re.IGNORECASE,
        ):
            return True
    return False


def is_content_specification(text: str, filename: str) -> bool:
    """True when the user describes what to write instead of supplying literal bytes."""
    cleaned = _clean_content(text)
    if _looks_like_source_code(cleaned):
        return False
    if _looks_like_finished_literal(cleaned):
        return False
    if _SPEC_HINT_RE.search(cleaned):
        return True
    if _INSTRUCTION_PREFIX_RE.match(cleaned):
        return True
    if _QUANTITY_NOUN_RE.match(cleaned):
        return True
    if re.search(r"\b(de un|de una)\s+(programa|script|c[oó]digo)\b", cleaned, re.IGNORECASE):
        return True
    if re.search(
        r"\b(pequeñ[ao]|breve|simple|completa?|detallad[ao])\s+",
        cleaned,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\bpara\s+(cocinar|matem[aá]tica|discreta|python|javascript)\b", cleaned, re.IGNORECASE
    ):
        return True
    ext = Path(filename).suffix.lower()
    if ext in (".py", ".js", ".ts", ".java", ".go", ".rs") and len(cleaned) > 40:
        if not _looks_like_source_code(cleaned) and _SPEC_HINT_RE.search(cleaned + " " + filename):
            return True
    # Default for create-file intents: short directive phrases are specs, not bytes.
    if len(cleaned) < 120 and re.search(
        r"\b(con|para|donde|escrib|inventad|genera|incluy)\b", cleaned, re.IGNORECASE
    ):
        return True
    return False


def classify_file_content(raw: str, filename: str) -> tuple[str, ContentSource, str]:
    """Return (body, source, spec_for_generation)."""
    cleaned = _clean_content(raw)
    fenced = extract_fenced_code(cleaned)
    if fenced is not None:
        return fenced, "fenced", ""
    if is_content_specification(cleaned, filename):
        spec = _normalize_spec_text(cleaned) or cleaned
        return spec, "spec", spec
    return cleaned, "literal", ""


def suggest_filename(filename: str, body_or_spec: str, source: ContentSource) -> str:
    """Add a sensible extension when the user omitted one but asked for code."""
    name = Path(filename.strip().strip("\"'")).name
    if Path(name).suffix:
        return name
    blob = body_or_spec.lower()
    if source in ("fenced", "spec") or _looks_like_source_code(body_or_spec):
        if re.search(r"\bpython\b|fibonacci|\.py\b|def\s+\w+\(", blob, re.IGNORECASE):
            return f"{name}.py"
        if re.search(r"\bjavascript\b|\.js\b", blob, re.IGNORECASE):
            return f"{name}.js"
    return name


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

    raw_name = path_or_name.strip().strip("\"'")
    provisional = Path(raw_name).name
    if provisional.lower() in _INVALID_FILENAMES or len(provisional) < 3:
        return None

    body, source, spec = classify_file_content(content_raw, provisional)
    if not body:
        return None

    filename = suggest_filename(provisional, body if source != "spec" else spec or body, source)
    if "/" in raw_name or raw_name.startswith("~"):
        expanded = Path(raw_name).expanduser()
        target = expanded if expanded.suffix else expanded.parent / filename
        resolved = _resolve_path(str(target), write_roots)
    else:
        resolved = _resolve_path(filename, write_roots)
    if resolved is None:
        return None

    return FileWriteIntent(
        path=resolved,
        content=body,
        filename=Path(resolved).name,
        content_source=source,
        content_spec=spec,
        filled_from="",
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
