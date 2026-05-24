"""Fingerprint-based invalidation for llama.cpp prompt caches."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

_DEFAULT_CACHE = os.path.join("bin", "cache", "chat.cache")

# Volatile system-prompt sections — must not bust the cache every turn.
_DATE_LINE_RE = re.compile(r"FECHA Y HORA ACTUAL: [^\n]+\n")
_SESSION_BLOCK_RE = re.compile(
    r"HISTORIAL COMPRIMIDO DE SESIÓN:\n.*?(?=\nMEMORIA RECUPERADA:)",
    re.DOTALL,
)
_MEMORY_BLOCK_RE = re.compile(
    r"MEMORIA RECUPERADA:\n.*?(?=\n\n(?:INSTRUCCIONES DE RESPUESTA:|Responde de forma))",
    re.DOTALL,
)
_AMBIENT_BLOCK_RE = re.compile(
    r"\n\n[^\n]+\n\n(?:INSTRUCCIONES DE RESPUESTA:|Responde de forma)",
    re.DOTALL,
)


def prompt_cache_path() -> Path:
    override = os.getenv("CEREBRO_PROMPT_CACHE_PATH")
    if override:
        return Path(os.path.expanduser(override))
    return Path(_DEFAULT_CACHE)


def _stable_prompt_for_fingerprint(system_prompt: str) -> str:
    """Strip per-turn dynamic fields so fingerprint stays stable within a session."""
    stable = system_prompt
    stable = _DATE_LINE_RE.sub("FECHA Y HORA ACTUAL: <dynamic>\n", stable)
    stable = _SESSION_BLOCK_RE.sub("HISTORIAL COMPRIMIDO DE SESIÓN:\n<dynamic>\n", stable)
    stable = _MEMORY_BLOCK_RE.sub("MEMORIA RECUPERADA:\n<dynamic>\n", stable)
    if "INSTRUCCIONES DE RESPUESTA:" in stable:
        stable = _AMBIENT_BLOCK_RE.sub(
            "\n\n<ambient>\n\nINSTRUCCIONES DE RESPUESTA:", stable, count=1
        )
    return stable


def prompt_cache_fingerprint(
    system_prompt: str,
    authorized_tools: list[str],
    *,
    model_id: str = "",
) -> str:
    tools_key = ",".join(sorted(authorized_tools))
    stable_prompt = _stable_prompt_for_fingerprint(system_prompt)
    payload = f"{model_id}\0{stable_prompt}\0{tools_key}".encode()
    return hashlib.sha256(payload).hexdigest()


def _sidecar_path(cache_path: Path) -> Path:
    return cache_path.with_name(cache_path.name + ".sha256")


def sync_prompt_cache(
    system_prompt: str,
    authorized_tools: list[str],
    *,
    model_id: str = "",
) -> None:
    """Drop the on-disk prompt cache sidecar when the stable prompt fingerprint changes."""
    cache_path = prompt_cache_path()
    sidecar = _sidecar_path(cache_path)
    fingerprint = prompt_cache_fingerprint(system_prompt, authorized_tools, model_id=model_id)

    if sidecar.exists() and sidecar.read_text(encoding="utf-8").strip() == fingerprint:
        return

    if cache_path.exists():
        cache_path.unlink()

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(fingerprint, encoding="utf-8")
