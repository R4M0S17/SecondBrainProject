"""Generate file body from a content specification via the chat provider."""

from __future__ import annotations

import re

from core.inference.registry import Message

_FENCE_RE = re.compile(r"```(?:\w+)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_THINKING_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_generated_file_body(raw: str) -> str:
    """Remove markdown fences, thinking blocks, and surrounding prose from model output."""
    text = _THINKING_RE.sub("", raw).strip()
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


async def generate_file_content(
    *,
    user_query: str,
    filename: str,
    content_spec: str,
    chat: object,
) -> str:
    """Ask the chat model for executable file contents only (no markdown wrapper)."""
    prompt = (
        f'Genera ÚNICAMENTE el contenido del archivo "{filename}".\n'
        f"Petición del usuario: {user_query}\n"
        f"Descripción del contenido: {content_spec}\n\n"
        "Reglas:\n"
        "- Devuelve solo el texto que debe guardarse en el archivo.\n"
        "- Sin explicación antes ni después.\n"
        "- Sin bloques markdown (sin ```).\n"
        "- Si es código, debe ser completo y ejecutable."
    )
    messages: list[Message] = [{"role": "user", "content": prompt}]
    raw = await chat.complete(messages)  # type: ignore[attr-defined]
    body = strip_generated_file_body(str(raw))
    if not body:
        raise ValueError("empty generated file content")
    return body
