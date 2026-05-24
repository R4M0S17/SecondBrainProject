"""Zero-token intent classification via keyword / regex (A4 fast path)."""

from __future__ import annotations

import re

# Order matters: first match wins.
INTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Calendar — scheduling, events, reminders (ES + EN)
    (re.compile(r"\b(cumple|cumplea|birthday|anniversary)\w*", re.IGNORECASE), "calendar"),
    (re.compile(r"\b(calendario|agenda|recordatorio|recu[eé]rdame)\w*", re.IGNORECASE), "calendar"),
    (
        re.compile(
            r"\b(evento|reuni[oó]n|cita|appointment|schedule|calendar|invitaci[oó]n)\w*",
            re.IGNORECASE,
        ),
        "calendar",
    ),
    (
        re.compile(
            r"\b(hora|fecha|d[ií]a|mañana|manana|today|tomorrow|pr[oó]xima semana)\w*",
            re.IGNORECASE,
        ),
        "calendar",
    ),
    (
        re.compile(
            r"\b(crea|crear|a[nñ]ade|añadir|agendar|programar|schedule)\w*.*\b"
            r"(evento|cita|reuni|recordatorio|meeting|reminder)\w*",
            re.IGNORECASE,
        ),
        "calendar",
    ),
    (
        re.compile(
            r"\b(evento|cita|reuni|recordatorio|meeting)\w*.*\b"
            r"(crea|crear|a[nñ]ade|agendar|programar)\w*",
            re.IGNORECASE,
        ),
        "calendar",
    ),
    # Code — programming, files, scripts
    (
        re.compile(
            r"\b(python|javascript|typescript|java|rust|golang|node\.?js)\b",
            re.IGNORECASE,
        ),
        "code",
    ),
    (
        re.compile(
            r"\b(c[oó]digo|funci[oó]n|bug|debug|refactor|script|stack ?trace|\.py\b|\.js\b|\.ts\b)",
            re.IGNORECASE,
        ),
        "code",
    ),
    (
        re.compile(
            r"\b(escribe|escribir|guardar|write|save|create)\w*.*\b(archivo|fichero|file)\w*",
            re.IGNORECASE,
        ),
        "code",
    ),
    (
        re.compile(
            r"\b(archivo|fichero|file|directorio|directory|folder|carpeta)\w*",
            re.IGNORECASE,
        ),
        "code",
    ),
    # Academic — documents, study
    (
        re.compile(
            r"\b(pdf|paper|art[ií]culo|res[uú]me|resumen|estudia|apuntes|notas)\w*",
            re.IGNORECASE,
        ),
        "academic",
    ),
    # Math — general agent uses evaluate_math tool
    (re.compile(r"\d+\s*[×x*]\s*\d+"), "general"),
    (
        re.compile(r"\b(cu[aá]nto es|calculate|calcular|compute)\b.*\d", re.IGNORECASE),
        "general",
    ),
]


def classify_intent_fast(query: str) -> str | None:
    """Return intent category or None if no keyword signal."""
    text = query.strip()
    if not text:
        return None
    for pattern, category in INTENT_PATTERNS:
        if pattern.search(text):
            return category
    return None
