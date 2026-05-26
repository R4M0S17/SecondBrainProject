"""Extract create/delete reminder intents from natural language via the chat LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from core.agents.llm_parse_utils import extract_json_object, repair_tool_json, strip_markdown_fences
from core.inference.registry import Message

if TYPE_CHECKING:
    pass

_READ_HINT_RE = re.compile(
    r"\b("
    r"pr[oó]ximos?|proximos?|"
    r"cu[aá]ndo|when|lista|listar|mu[eé]strame|muestra|hay|qu[eé]\s+tengo|"
    r"cumpleaños|cumpleaño|cumple|birthday|"
    r"contenido\s+de\s+los|contenido\s+del|"
    r"crea\s+un\s+archivo|crear\s+un\s+archivo|write\s+a\s+file|create\s+a\s+file"
    r")\b",
    re.IGNORECASE,
)

_WRITE_HINT_RE = re.compile(
    r"\b("
    r"recordatorio|reminder|recu[eé]rdame|remind\s+me|"
    r"crea|crear|agrega|agregar|a[nñ]ade|añadir|"
    r"borra|borrar|elimina|eliminar|quita|quitar|delete|remove"
    r")\b",
    re.IGNORECASE,
)

# Flexible Spanish/English shapes (backup when extractor LLM returns bad JSON).
_HEURISTIC_ADD = [
    re.compile(
        r"(?:recordatorio|reminder|tarea)\b.*?\bpara\s+"
        r"(?P<when>.+?)\s+(?:llamado|de\s+nombre|nombrado|called|named)\s+"
        r'["\']?(?P<title>[^"\']+)["\']?\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:recordatorio|reminder|tarea)\s+"
        r"(?P<when>.+?)\s+con\s+(?:nombre|titulo|título|llamado)\s+"
        r'["\']?(?P<title>[^"\']+)["\']?\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:recordatorio|reminder|tarea)\s+"
        r"(?:llamado|de\s+nombre|nombrado|called|named)\s+"
        r'["\']?(?P<title>[^"\']+)["\']?\s+\bpara\s+(?P<when>.+?)\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        r"recu[eé]rdame\s+(?P<title>.+?)\s+\b(?:para|el|en|a)\s+(?P<when>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"remind\s+me(?:\s+to)?\s+(?P<title>.+?)\s+(?:on|at|for)\s+(?P<when>.+?)\s*$",
        re.IGNORECASE,
    ),
]

_HEURISTIC_DELETE_PATTERNS = [
    re.compile(
        r"(?:borra|borrar|elimina|eliminar|quita|quitar|delete|remove)\s+"
        r"(?:el\s+)?(?:recordatorio|reminder|tarea)\s+"
        r"(?:de|del|para|el)?\s*(?P<when>mañana|manana|hoy|today|pasado\s+mañana|pasado\s+manana)\s+"
        r"(?:que\s+se\s+llama|llamado|nombrado|called|named)\s+"
        r'["\']?(?P<title>[^"\']+)["\']?\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:borra|borrar|elimina|eliminar|quita|quitar|delete|remove)\s+"
        r"(?:el\s+)?(?:recordatorio|reminder|tarea)\s+"
        r"(?:que\s+se\s+llama|llamado|nombrado|called|named)\s+"
        r'["\']?(?P<title>[^"\']+)["\']?\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:borra|borrar|elimina|eliminar|quita|quitar|delete|remove)\s+"
        r"(?:el\s+)?(?:recordatorio|reminder|tarea)\s+"
        r'(?:llamado|de\s+nombre|nombrado|called|named)?\s*["\']?(?P<title>[^"\']+)["\']?\s*$',
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True)
class ReminderIntent:
    action: str  # "add" | "delete" | "none"
    title: str = ""
    datetime_str: str = ""  # add: full when; delete: optional day scope (e.g. mañana)


def is_reminder_write_query(query: str) -> bool:
    """True when the user likely wants to create or delete a calendar reminder."""
    text = query.strip()
    if not text or _READ_HINT_RE.search(text):
        return False
    # File-create + calendar content → file_write_calendar_fusion, not add_reminder.
    from core.agents.file_write_fast_path import parse_file_write_intent

    if parse_file_write_intent(text) is not None:
        return False
    return bool(_WRITE_HINT_RE.search(text))


def heuristic_parse_reminder(query: str) -> ReminderIntent | None:
    """Parse common reminder phrasings without calling the LLM."""
    text = query.strip()
    if not text:
        return None

    for pattern in _HEURISTIC_DELETE_PATTERNS:
        m = pattern.search(text)
        if m:
            title = m.group("title").strip().strip("\"'")
            when = (m.groupdict().get("when") or "").strip()
            if title:
                return ReminderIntent(action="delete", title=title, datetime_str=when)

    for pattern in _HEURISTIC_ADD:
        m = pattern.search(text)
        if m:
            title = m.group("title").strip().strip("\"'")
            when = m.group("when").strip()
            if title and when:
                return ReminderIntent(action="add", title=title, datetime_str=when)
    return None


def _parse_extractor_json(raw: str) -> ReminderIntent | None:
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    text = strip_markdown_fences(text)
    json_text = extract_json_object(text)
    if json_text is None:
        return None
    repaired = repair_tool_json(json_text)
    try:
        data = json.loads(repaired)
    except json.JSONDecodeError:
        logger.warning("reminder extractor JSON parse failed: {}", text[:300])
        return None
    if not isinstance(data, dict):
        return None

    intent = str(data.get("intent", data.get("action", "none"))).lower()
    if intent in ("none", "no", "skip"):
        return ReminderIntent(action="none")
    if intent in ("add", "create", "crear"):
        title = str(data.get("title", data.get("nombre", data.get("name", "")))).strip()
        when = str(
            data.get("datetime_str", data.get("when", data.get("fecha", data.get("date", ""))))
        ).strip()
        if title and when:
            return ReminderIntent(action="add", title=title, datetime_str=when)
        return None
    if intent in ("delete", "borrar", "eliminar"):
        title = str(data.get("title", data.get("nombre", data.get("name", "")))).strip()
        when = str(
            data.get("datetime_str", data.get("when", data.get("day", data.get("fecha", ""))))
        ).strip()
        if title:
            return ReminderIntent(action="delete", title=title, datetime_str=when)
        return None
    return None


async def extract_reminder_intent(
    query: str,
    chat: object,
    *,
    current_date: str,
) -> ReminderIntent | None:
    """Ask the chat model to map free-form Spanish/English to structured reminder fields."""
    prompt = (
        "Analiza si el usuario quiere CREAR o BORRAR un recordatorio en Apple Calendar.\n"
        f"FECHA Y HORA ACTUAL: {current_date}\n\n"
        f'Usuario: "{query}"\n\n'
        "Responde SOLO con un JSON válido (sin markdown, sin explicación):\n"
        '- Crear: {"intent":"add","title":"<título corto>","datetime_str":"<día y hora completos en español o inglés natural>"}\n'
        '- Borrar: {"intent":"delete","title":"<título exacto>","datetime_str":"<día opcional, ej. mañana>"}\n'
        '- No es crear/borrar recordatorio: {"intent":"none"}\n\n'
        "Reglas:\n"
        '- datetime_str debe incluir día Y hora (ej. "mañana a las 3pm", "tomorrow at 3pm").\n'
        "- title: solo el nombre del recordatorio, sin la fecha.\n"
        '- Si pide "recordatorio para mañana a las 3pm llamado X", title=X y datetime_str=mañana a las 3pm.\n'
        '- Variantes: "con nombre", "llamado", "called", "para el", "recuérdame".\n'
    )
    messages: list[Message] = [{"role": "user", "content": prompt}]
    raw = await chat.complete(messages)  # type: ignore[attr-defined]
    intent = _parse_extractor_json(str(raw))
    if intent is not None:
        return intent

    logger.warning("reminder extractor LLM parse failed, trying heuristic: {}", str(raw)[:200])
    return heuristic_parse_reminder(query)


def resolve_reminder_intent(
    query: str,
    *,
    llm_intent: ReminderIntent | None = None,
) -> ReminderIntent | None:
    """Prefer LLM extraction; fall back to heuristic for reliable UX."""
    if llm_intent is not None and llm_intent.action != "none":
        return llm_intent
    return heuristic_parse_reminder(query)
