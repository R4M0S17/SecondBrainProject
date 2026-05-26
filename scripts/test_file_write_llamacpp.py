#!/usr/bin/env python3
"""Live smoke: smart file-write fast path with llama.cpp on :8080.

Verifies parse + runtime (including LLM content generation for specs).
Starts llama-server if needed; stops it when finished.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LLAMA_BASE = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_HEALTH = f"{LLAMA_BASE}/health"
MODEL = os.getenv(
    "CEREBRO_LLAMACPP_MODEL",
    "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
)

FUSION_QUERY = (
    "crea un archivo pruebacalendario.txt con contenido de los proximos "
    "3 cumpleaños en mi calendario"
)

FUSION_QUERY_NO_CONTENT_KEYWORD = (
    "crea un archivo pruebacalendario_no_contenido.txt con los 3 proximos "
    "cumpleaños en mi calendario"
)

PROMPTS = [
    (
        "literal",
        'crea un archivo smart_literal.txt con contenido "hola que tal?"',
        lambda content, path: content.strip() == "hola que tal",
    ),
    (
        "spec",
        "crea un archivo pruebacodigo.txt con contenido de un programa python "
        "usando recursion para la secuencia de fibonacci",
        lambda content, path: (
            ("fibonacci" in content.lower())
            or ("def fib" in content.lower())
            or ("fib(" in content.lower())
        ),
    ),
    (
        "spec_loose_es",
        "crea un archivo pruebapython_loose.txt con un a funcion con recursion de la sisecion de fibonacci",
        lambda content, path: (
            ("def fibonacci" in content.lower())
            or ("def fib" in content.lower())
            or ("fib(" in content.lower())
        ),
    ),
    (
        "truth_table",
        "crea un archivo truthtable.txt con una tabla de la verdad para matematica discreta",
        lambda content, path: (
            content.strip() != "una tabla de la verdad para matematica discreta"
            and ("|" in content or "AND" in content.upper() or "verdad" in content.lower())
            and len(content) > 60
        ),
    ),
    (
        "games_list",
        "crea un archivo juegos.txt con 3 videojuegos de playstation",
        lambda content, path: (
            content.strip() != "3 videojuegos de playstation"
            and "\n" in content
            and len(content) > 40
        ),
    ),
    (
        "fenced",
        "crea un archivo pruebacodigo2 con contenido ```python\n"
        "def fibonacci(n):\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    return fibonacci(n-1)+fibonacci(n-2)\n"
        "```",
        lambda content, path: (
            ("def fibonacci" in content.lower()) or ("def fib" in content.lower())
        )
        and "```" not in content,
    ),
]


def _llama_up() -> bool:
    try:
        return httpx.get(LLAMA_HEALTH, timeout=2.0).status_code == 200
    except Exception:
        return False


def _start_engine() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["./bin/start_engine.sh", "chat"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_llama(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    subprocess.run(["pkill", "-f", "llama-server"], check=False)


def _check_parse(tmp: Path) -> None:
    from core.agents.file_write_calendar_fusion import is_calendar_backed_file_content
    from core.agents.file_write_fast_path import parse_file_write_intent
    from core.agents.reminder_intent_resolver import is_reminder_write_query

    assert not is_reminder_write_query(FUSION_QUERY)
    roots = [str(tmp)]
    fusion_parse = parse_file_write_intent(FUSION_QUERY, write_roots=roots)
    if fusion_parse is None:
        raise SystemExit("FAIL parse [fusion]: no file-write intent")
    blob = fusion_parse.content_spec or fusion_parse.content
    if not is_calendar_backed_file_content(blob):
        raise SystemExit(f"FAIL parse [fusion]: not calendar-backed: {blob!r}")
    print(f"OK parse [fusion]: file={fusion_parse.filename} (calendar body at runtime)")

    for label, query, _ in PROMPTS:
        intent = parse_file_write_intent(query, write_roots=roots)
        if intent is None:
            raise SystemExit(f"FAIL parse [{label}]: no intent for {query[:60]!r}…")
        if not hasattr(intent, "content_source"):
            raise SystemExit(f"FAIL parse [{label}]: FileWriteIntent missing content_source")
        print(f"OK parse [{label}]: source={intent.content_source} file={intent.filename}")


async def _check_calendar_fusion_runtime(
    tmp: Path,
    agent_id: str = "general-v1",
    query: str = FUSION_QUERY,
) -> None:
    """Full stack: calendar read + write_file pending (not add_reminder)."""
    from unittest.mock import AsyncMock, MagicMock

    from core.agents.reminder_intent_resolver import is_reminder_write_query
    from core.agents.runtime import AgentRuntime
    from core.agents.state_store import AgentStateStore
    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
    from core.inference.registry import ProviderRegistry
    from core.tools.handlers.filesystem import write_file as fs_write_file

    assert not is_reminder_write_query(query)

    os.environ["CEREBRO_FILES_PATH"] = str(tmp)
    store = AgentStateStore(state_dir=str(tmp / "state"))
    state = store.load(agent_id)
    if agent_id == "calendar-v1":
        from core.agents.specialized import CALENDAR_TOOLS

        state.profile.authorized_tools = [t for t in CALENDAR_TOOLS if t != "write_file"]
    else:
        state.profile.authorized_tools = ["write_file", "search_upcoming", "add_reminder"]
    store.save(state)

    chat = LlamaCppChatProvider(model=MODEL, base_url=LLAMA_BASE, timeout=180)
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.0] * 384)
    embed.dimensions = MagicMock(return_value=384)
    registry = ProviderRegistry(ram_threshold_primary_gb=0.25, ram_threshold_fallback_gb=0.25)
    registry.register("primary", chat, embed)

    short_term = MagicMock()
    short_term.push_message = MagicMock()
    runtime = AgentRuntime(
        registry=registry,
        state_store=store,
        context_builder=MagicMock(_short_term=short_term),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = lambda *a, **k: None
    runtime.save_conversation_session = lambda *a, **k: None

    runtime._tool_registry = {"write_file": lambda path, content: f"written:{path}"}
    answer, final = await runtime.run(query, agent_id)
    if final.pending_tool_name != "write_file":
        raise SystemExit(
            f"FAIL fusion runtime [{agent_id}]: expected write_file, got {final.pending_tool_name!r}\n"
            f"answer={answer[:400]!r}"
        )
    if "cumple" not in final.pending_tool_args.get("content", "").lower():
        raise SystemExit(
            f"FAIL fusion runtime [{agent_id}]: calendar body missing:\n"
            f"{final.pending_tool_args.get('content', '')[:400]!r}"
        )

    # Simulate tool-confirm approve so we verify the file is actually created.
    pending_path = Path(final.pending_tool_args.get("path", ""))
    pending_content = str(final.pending_tool_args.get("content", ""))
    if pending_path and pending_content:
        if pending_path.exists():
            pending_path.unlink()
        msg = fs_write_file(str(pending_path), pending_content, [str(tmp)])
        if "Archivo escrito en:" not in msg or not pending_path.exists():
            raise SystemExit(
                f"FAIL fusion runtime [{agent_id}]: wrote pending file failed\n"
                f"path={pending_path}\nmsg={msg}"
            )
    print(f"OK fusion runtime [{agent_id}]: pending write_file with birthday lines")


async def _check_runtime(tmp: Path) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from core.agents.runtime import AgentRuntime
    from core.agents.state_store import AgentStateStore
    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
    from core.inference.registry import ProviderRegistry
    from core.tools.handlers.filesystem import write_file as fs_write_file

    os.environ["CEREBRO_FILES_PATH"] = str(tmp)
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    chat = LlamaCppChatProvider(model=MODEL, base_url=LLAMA_BASE, timeout=120)
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.0] * 384)
    embed.dimensions = MagicMock(return_value=384)
    # Low thresholds so live test passes when llama-server already uses most RAM.
    registry = ProviderRegistry(ram_threshold_primary_gb=0.25, ram_threshold_fallback_gb=0.25)
    registry.register("primary", chat, embed)

    short_term = MagicMock()
    short_term.push_message = MagicMock()
    runtime = AgentRuntime(
        registry=registry,
        state_store=store,
        context_builder=MagicMock(_short_term=short_term),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = lambda *a, **k: None
    runtime.save_conversation_session = lambda *a, **k: None

    for label, query, content_ok in PROMPTS:
        answer, final = await runtime.run(query, agent_id)
        if final.pending_tool_name != "write_file":
            raise SystemExit(
                f"FAIL runtime [{label}]: expected pending write_file, got {final.pending_tool_name!r}\n"
                f"answer={answer[:200]!r}"
            )
        content = final.pending_tool_args.get("content", "")
        path = final.pending_tool_args.get("path", "")
        if not content_ok(content, path):
            raise SystemExit(
                f"FAIL runtime [{label}]: bad content/path\npath={path}\ncontent={content[:300]!r}"
            )
        if label == "fenced" and not path.endswith(".py"):
            print(f"WARN runtime [{label}]: expected .py extension, got {path}")

        # Execute the pending write_file now (simulates tool-confirm approve).
        target = Path(path)
        if target.exists():
            target.unlink()
        msg = fs_write_file(str(target), content, [str(tmp)])
        assert "Archivo escrito en:" in msg
        assert target.exists(), f"FAIL runtime [{label}]: file not created at {path}"

        # Sanity: the content written matches the content predicate.
        written = target.read_text(encoding="utf-8")
        if not content_ok(written, str(target)):
            raise SystemExit(
                f"FAIL runtime [{label}]: written content failed predicate\npath={path}\nwritten[:200]={written[:200]!r}"
            )

        # Extra regression: relative path tool calls should land in tmp root.
        rel_name = target.name
        rel_target = tmp / rel_name
        if rel_target.exists():
            rel_target.unlink()
        msg2 = fs_write_file(rel_name, content, [str(tmp)])
        assert "Archivo escrito en:" in msg2
        assert rel_target.exists(), f"FAIL runtime [{label}]: relative path file not created"

        print(
            f"OK runtime [{label}]: pending write_file → {Path(path).name} ({len(content)} chars)"
        )


async def _check_runtime_writes_to_default_cerebrofiles_real(tmp: Path) -> None:
    """Verify the user-like prompt writes into ~/Desktop/CerebroFiles (default root)."""
    from unittest.mock import AsyncMock, MagicMock

    from core.agents.runtime import AgentRuntime
    from core.agents.state_store import AgentStateStore
    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
    from core.inference.registry import ProviderRegistry
    from core.tools.handlers.filesystem import write_file as fs_write_file

    # Use the real default root (do not rely on CEREBRO_AUTHORIZED_* overrides).
    cerebrofiles = Path.home() / "Desktop" / "CerebroFiles"
    cerebrofiles.mkdir(parents=True, exist_ok=True)

    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp / "state_real"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    chat = LlamaCppChatProvider(model=MODEL, base_url=LLAMA_BASE, timeout=120)
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.0] * 384)
    embed.dimensions = MagicMock(return_value=384)
    registry = ProviderRegistry(ram_threshold_primary_gb=0.25, ram_threshold_fallback_gb=0.25)
    registry.register("primary", chat, embed)

    short_term = MagicMock()
    short_term.push_message = MagicMock()
    runtime = AgentRuntime(
        registry=registry,
        state_store=store,
        context_builder=MagicMock(_short_term=short_term),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = lambda *a, **k: None
    runtime.save_conversation_session = lambda *a, **k: None

    # Keep it exactly like the user prompt structure (no path, quoted Spanish).
    filename = "nota_escritorio_cerebro.txt"
    prompt = "crea un archivo " + filename + " con el contenido de “hola desde escritorio cerebro”"

    # Force the default write root for this test only.
    original_files_path = os.environ.get("CEREBRO_FILES_PATH")
    os.environ["CEREBRO_FILES_PATH"] = str(cerebrofiles)

    try:
        answer, final = await runtime.run(prompt, agent_id)
    finally:
        if original_files_path is None:
            os.environ.pop("CEREBRO_FILES_PATH", None)
        else:
            os.environ["CEREBRO_FILES_PATH"] = original_files_path
    if final.pending_tool_name != "write_file":
        raise SystemExit(
            "FAIL default-write: expected pending write_file, got "
            f"{final.pending_tool_name!r}\nanswer={answer[:300]!r}"
        )

    pending_path = final.pending_tool_args.get("path", "")
    pending_content = final.pending_tool_args.get("content", "")
    if not str(pending_path).endswith(filename):
        raise SystemExit(
            "FAIL default-write: pending path doesn't end with filename\n"
            f"pending_path={pending_path!r}"
        )

    # Simulate tool-confirm approval: actually execute the handler.
    target = Path(pending_path).resolve()
    if target.exists():
        target.unlink()
    msg = fs_write_file(str(target), str(pending_content), [str(cerebrofiles)])
    assert "Archivo escrito en:" in msg
    if not target.exists():
        raise SystemExit(f"FAIL default-write: file not created at {target}")
    written = target.read_text(encoding="utf-8", errors="ignore").lower()
    if "hola desde escritorio cerebro" not in written:
        raise SystemExit(
            "FAIL default-write: content mismatch\n" f"written[:200]={written[:200]!r}"
        )

    print(f"OK default-write: wrote {target} ({len(pending_content)} chars)")


async def _main_async(tmp: Path) -> None:
    _check_parse(tmp)
    await _check_runtime(tmp)
    await _check_runtime_writes_to_default_cerebrofiles_real(tmp)
    await _check_calendar_fusion_runtime(tmp, "general-v1")
    await _check_calendar_fusion_runtime(tmp, "calendar-v1")
    await _check_calendar_fusion_runtime(tmp, "general-v1", query=FUSION_QUERY_NO_CONTENT_KEYWORD)


def main() -> int:
    started: subprocess.Popen[bytes] | None = None
    if not _llama_up():
        print("Starting llama.cpp engine…")
        started = _start_engine()
        for _ in range(90):
            if _llama_up():
                break
            time.sleep(1)
        else:
            _stop_llama(started)
            raise SystemExit("FAIL: llama-server not healthy on :8080")
    else:
        print("llama.cpp already running on", LLAMA_BASE)

    tmp = ROOT / ".tmp_file_write_live"
    tmp.mkdir(exist_ok=True)
    try:
        asyncio.run(_main_async(tmp))
    finally:
        print("Stopping llama-server…")
        _stop_llama(started)
        if _llama_up():
            print("WARN: llama-server still responding after stop")
        else:
            print("llama.cpp stopped (port 8080 free)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
