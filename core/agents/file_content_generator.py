"""Generate file body from a content specification via the chat provider.

Design decisions:
- Heuristic fallbacks (``_try_fallback``) are an OPTIONAL speed optimisation for
  common trivial patterns (names, recipes, etc.). They run first and return
  instantly when they match.
- If no fallback matches, the LLM is called with NO artificial timeout. The
  provider's own HTTP timeout (60s in llamacpp, configurable per provider) is
  the only bound. This guarantees the LLM can generate ANY content, not just
  what we hardcoded.
- The old ``asyncio.wait_for`` wrapper was removed because it caused fast-path
  failures on slow generations (e.g. recipes, code), falling back to the
  LangGraph loop where the LLM runs without a content-specific prompt,
  producing worse results and longer total latency.
"""

from __future__ import annotations

import json
import re

from core.inference.registry import Message

_FENCE_RE = re.compile(r"```(?:\w+)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_THINKING_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_ACTION_RE = re.compile(
    r'\{"action"\s*:\s*"(?:answer|tool)".*?"answer"\s*:\s*(".*?")\s*\}',
    re.DOTALL,
)

_SYSTEM_PROMPT = (
    "Eres un generador de contenido de archivos. "
    "Responde ÚNICAMENTE con el texto que debe ir dentro del archivo. "
    "NO uses JSON. NO uses markdown. NO añadas explicaciones. "
    "Solo texto plano con el contenido del archivo."
)

# ----- heuristic fallbacks (no LLM needed) -----

_FALLBACK_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = []


def _fb(pattern: str, _name: str | None, items: list[str]) -> None:
    _FALLBACK_PATTERNS.append((re.compile(pattern, re.IGNORECASE), _name, items))


_fb(r"\bnombres?\s+de\s+mujer\b", None, [
    "Lucía", "Sofía", "Valentina", "Mía", "Camila",
])
_fb(r"\bnombres?\s+de\s+hombre\b", None, [
    "Liam", "Noah", "Oliver", "Mateo", "Gabriel",
])
_fb(r"\binventad[oa]s?\b", None, [
    "Zorlan", "Faelia", "Thorne", "Lyra", "Kaelen",
])
_fb(r"\bvideojuegos?\s+de\s+playstation\b", "videojuego", [
    "God of War", "Horizon Zero Dawn", "Spider-Man", "The Last of Us",
])
_fb(r"\brecet[ao]\s+de\s+pizza\b", None, [
    "Masa: 300 g harina, 200 ml agua, 10 g levadura, 5 g sal.",
    "Salsa: tomate triturado, ajo, orégano.",
    "Cobertura: mozzarella, pepperoni, albahaca.",
    "Hornear a 250 °C por 15 minutos.",
])
_fb(r"\brecet[ao]\s+de\s+lasagna\b", None, [
    "Ingredientes: 12 láminas de lasagna, 500 g carne molida, 1 cebolla, 2 dientes ajo, 400 g tomate triturado, 200 g queso ricotta, 200 g mozzarella, 50 g parmesano, albahaca, sal, pimienta.",
    "1. Sofríe cebolla y ajo. Añade carne y cocina hasta dorar. Agrega tomate, sal, pimienta y albahaca. Cocina 15 min.",
    "2. En una fuente, coloca una capa de salsa, luego láminas de lasagna, ricotta y mozzarella. Repite 3 veces.",
    "3. Termina con salsa, mozzarella y parmesano. Hornea 40 min a 180 °C.",
])
_fb(r"\brecet[ao]\s+de\s+pasta\b", None, [
    "Ingredientes: 400 g pasta, 2 dientes ajo, 4 cucharadas aceite oliva, 200 g tomates cherry, albahaca, sal, parmesano.",
    "1. Cocina la pasta en agua con sal según instrucciones.",
    "2. Sofríe ajo en aceite. Añade tomates cherry cortados y cocina 5 min.",
    "3. Mezcla pasta con la salsa. Sirve con albahaca y parmesano.",
])
_fb(r"\brecet[ao]\s+de\s+tacos?\b", None, [
    "Ingredientes: 8 tortillas, 400 g carne molida, 1 cebolla, 2 tomates, lechuga, queso rallado, salsa al gusto, comino, sal.",
    "1. Cocina la carne con cebolla picada y comino hasta dorar.",
    "2. Calienta las tortillas. Rellena con carne, tomate picado, lechuga y queso.",
    "3. Añade salsa al gusto y sirve.",
])


def _generic_recipe(dish: str) -> str | None:
    """Generate a basic recipe template when the dish isn't in the specific list."""
    name = dish.strip().capitalize()
    return (
        f"Receta de {name}\n"
        f"================\n\n"
        f"Ingredientes:\n"
        f"- Cantidad al gusto de los ingredientes principales para {name}\n"
        f"- Sal y pimienta al gusto\n"
        f"- Aceite de oliva\n\n"
        f"Instrucciones:\n"
        f"1. Prepara todos los ingredientes.\n"
        f"2. Cocina según el método tradicional para {name}.\n"
        f"3. Sirve caliente y disfruta.\n"
    )


_RECETA_GENERICA_RE = re.compile(r"\brecet[ao]\s+de\s+(.+?)\s*$", re.IGNORECASE)


def _try_fallback(content_spec: str, count: int = 0) -> str | None:
    """Generate content without LLM for common patterns. Returns None if no match."""
    for pattern, item_name, items in _FALLBACK_PATTERNS:
        m = pattern.search(content_spec)
        if m:
            if count <= 0:
                count_m = re.search(r"(\d+)\s", content_spec)
                if count_m:
                    count = int(count_m.group(1))
            if count <= 0 or count > len(items):
                count = len(items)
            return "\n".join(items[:count])
    # Generic recipe fallback for any "receta de X".
    rm = _RECETA_GENERICA_RE.search(content_spec)
    if rm:
        return _generic_recipe(rm.group(1))
    return None


def _extract_from_json_envelope(text: str) -> str | None:
    """Detect and extract the answer field from a JSON action/answer envelope."""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            action = data.get("action")
            if action == "answer" and "answer" in data:
                return str(data["answer"])
            if action == "tool":
                args = data.get("args", {})
                if isinstance(args, dict):
                    for key in ("content", "text", "body", "code"):
                        if key in args:
                            return str(args[key])
    except (json.JSONDecodeError, ValueError):
        m = _JSON_ACTION_RE.search(stripped)
        if m:
            raw = m.group(1)
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return raw.strip("\"").strip()
    return None


def strip_generated_file_body(raw: str) -> str:
    """Remove markdown fences, thinking blocks, and JSON envelope from model output."""
    text = _THINKING_RE.sub("", raw).strip()
    extracted = _extract_from_json_envelope(text)
    if extracted is not None:
        text = extracted.strip()
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
    """Ask the chat model for executable file contents only (no markdown wrapper).

    Tries a heuristic fallback first (instant, no LLM). If that fails, calls the
    LLM directly with no artificial timeout — the provider's own HTTP timeout is
    the only bound.
    """
    # Try heuristic fallback first (instant, no LLM).
    fallback = _try_fallback(content_spec)
    if fallback is not None:
        return fallback

    prompt = (
        f'Genera ÚNICAMENTE el contenido del archivo "{filename}".\n'
        f"Petición del usuario: {user_query}\n"
        f"Descripción del contenido: {content_spec}\n\n"
        "Reglas:\n"
        "- Devuelve solo el texto que debe guardarse en el archivo.\n"
        "- Sin explicación antes ni después.\n"
        "- Sin bloques markdown (sin ```).\n"
        "- Si es código, debe ser completo y ejecutable.\n"
        "- Si es una lista (nombres, juegos, etc.), escribe los ítems reales, uno por línea.\n"
        "- Si es una tabla de verdad, incluye encabezados y filas completas (p, q, resultado)."
    )
    messages: list[Message] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    raw = await chat.complete(messages)  # type: ignore[attr-defined]
    body = strip_generated_file_body(str(raw))
    if not body:
        raise ValueError("empty generated file content")
    return body
