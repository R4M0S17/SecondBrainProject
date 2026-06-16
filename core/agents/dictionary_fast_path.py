from __future__ import annotations

import re

import httpx

_DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en"

_DEFINE_RE = re.compile(
    r"\b(?:define|definir|definition|meaning|significado|"
    r"qu[eé]\s+significa|what\s+(?:does|is)\s+"
    r"(?:the\s+)?(?:meaning|definition)\s+of|"
    r"what\s+does\s+\w+\s+mean)\b",
    re.IGNORECASE,
)

_QUICK_DEF_RE = re.compile(
    r"^\s*def(?:ine)?\s+([a-zA-Z]+)\s*$",
    re.IGNORECASE,
)

_WORD_RE = re.compile(
    r"(?:define|definir|significado\s+de|qu[eé]\s+significa|"
    r"what\s+(?:does|is)\s+(?:\w+\s+)?(?:mean|meaning|definition)\s+of|"
    r"definition\s+of|meaning\s+of)\s+"
    r"([A-Za-z]+)",
    re.IGNORECASE,
)


def _extract_word(query: str) -> str | None:
    qm = _QUICK_DEF_RE.match(query)
    if qm:
        return qm.group(1).lower()

    wm = _WORD_RE.search(query)
    if wm:
        return wm.group(1).lower()

    words = [
        w.strip(".,!?;:\"'()").lower()
        for w in query.strip().split()
        if w.strip(".,!?;:\"'()").lower()
        not in {"define", "definir", "definition", "meaning", "significado", "mean"}
    ]
    meaningful = [w for w in words if w and w.isalpha() and len(w) >= 2]
    if meaningful:
        return meaningful[-1]
    return None


def _format_definition(data: list) -> str:
    if not data:
        return "No se encontró definición."
    try:
        entry = data[0]
        word = entry.get("word", "?")
        phonetic = entry.get("phonetic", "")
        origin = entry.get("origin", "")

        lines = [f"**{word}**"]
        if phonetic:
            lines[0] += f"  —  _{phonetic}_"
        if origin:
            lines.append(f"*Origen:* {origin}")

        for meaning in entry.get("meanings", [])[:3]:
            part = meaning.get("partOfSpeech", "")
            definitions = meaning.get("definitions", [])
            if not definitions:
                continue
            first = definitions[0]
            def_text = first.get("definition", "")
            example = first.get("example", "")
            if part:
                lines.append(f"\n*{part}*")
            lines.append(f"   {def_text}")
            if example:
                lines.append(f"   *Ej: “{example}”*")

            if len(definitions) > 1:
                synonyms = first.get("synonyms", [])
                if synonyms:
                    lines.append(f"   *Sinónimos:* {', '.join(synonyms[:5])}")

        return "\n".join(lines)
    except (KeyError, IndexError):
        return "No se pudo interpretar la respuesta del diccionario."


def try_dictionary_fast_path(query: str) -> str | None:
    if not _DEFINE_RE.search(query) and not _QUICK_DEF_RE.match(query):
        return None

    word = _extract_word(query)
    if not word:
        return "¿Qué palabra quieres definir? Ej: 'define serendipia' o 'qué significa epifanía'."

    try:
        resp = httpx.get(
            f"{_DICT_API}/{word}",
            timeout=8.0,
        )
        if resp.status_code == 404:
            return f"No encontré definición para '{word}'."
        resp.raise_for_status()
        return _format_definition(resp.json())
    except httpx.HTTPError:
        return f"Error al consultar '{word}'. Intenta de nuevo."
