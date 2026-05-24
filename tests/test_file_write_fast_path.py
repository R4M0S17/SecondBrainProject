"""Tests for file-write fast path (Problem A — deterministic write_file routing)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.file_content_generator import strip_generated_file_body
from core.agents.file_write_fast_path import (
    classify_file_content,
    extract_fenced_code,
    parse_file_write_intent,
    suggest_filename,
    try_file_write_fast_path,
)
from core.agents.runtime import AgentRuntime
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from core.tools.handlers.filesystem import write_file
from core.tools.registry import register_filesystem_tools


def test_classify_fibonacci_description_as_spec():
    body, source, spec = classify_file_content(
        "de un programa pytho usando recursion para la secuencia de fibonacci",
        "pruebacodigo.txt",
    )
    assert source == "spec"
    assert "fibonacci" in spec.lower()
    assert body == spec


def test_extract_fenced_python():
    raw = "```python\ndef fib(n):\n    return n\n```"
    code = extract_fenced_code(raw)
    assert code is not None
    assert code.startswith("def fib")


def test_suggest_py_extension_for_code_spec():
    assert suggest_filename("pruebacodigo2", "def fibonacci", "fenced") == "pruebacodigo2.py"


def test_parse_spanish_create_file(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo ejemplo.txt con contenido Hola, mundo!",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "ejemplo.txt"
    assert intent.content == "Hola, mundo"
    assert intent.path == str((tmp_path / "ejemplo.txt").resolve())


def test_parse_english_write_file(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "Write a file called test-cerebro.txt with the word hello",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "test-cerebro.txt"
    assert intent.content == "hello"
    assert (tmp_path / "test-cerebro.txt").name in intent.path


def test_parse_explicit_write_file_path(tmp_path):
    target = tmp_path / "nested" / "ejemplo.txt"
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        f"Usa write_file para crear {target} con contenido Hola",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.path == str(target.resolve())
    assert intent.content == "Hola"


def test_try_fast_path_requires_write_file_tool(tmp_path):
    roots = [str(tmp_path)]
    q = "crea archivo foo.txt con contenido bar"
    assert try_file_write_fast_path(q, ["write_file"], write_roots=roots) is not None
    assert try_file_write_fast_path(q, ["read_file"], write_roots=roots) is None


def test_write_file_returns_path_message(tmp_path):
    target = tmp_path / "out.txt"
    msg = write_file(str(target), "hello", [str(tmp_path)])
    assert "Archivo escrito en:" in msg
    assert target.read_text() == "hello"


@pytest.mark.asyncio
async def test_runtime_file_write_fast_path_sets_pending_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action":"answer","answer":"hallucinated"}')
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_builder = MagicMock()
    mock_builder._short_term = MagicMock()
    mock_builder._short_term.push_message = MagicMock()

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, final_state = await runtime.run(
        "crea un archivo ejemplo.txt con contenido Hola",
        agent_id,
    )
    mock_chat.complete.assert_not_called()
    assert final_state.pending_tool_name == "write_file"
    assert final_state.pending_tool_args == {
        "path": str((tmp_path / "ejemplo.txt").resolve()),
        "content": "Hola",
    }
    assert "aprobación" in answer.lower() or "aprobacion" in answer.lower()
    assert "ejemplo.txt" in answer


@pytest.mark.asyncio
async def test_runtime_generates_content_for_spec(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    fib_code = "def fibonacci(n):\n    return n\n"
    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value=f"```python\n{fib_code}```")
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=MagicMock(_short_term=MagicMock()),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = MagicMock()

    answer, final_state = await runtime.run(
        "crea un archivo pruebacodigo.txt con contenido de un programa python "
        "usando recursion para la secuencia de fibonacci",
        agent_id,
    )
    mock_chat.complete.assert_called_once()
    assert final_state.pending_tool_name == "write_file"
    assert "def fibonacci" in final_state.pending_tool_args["content"]
    assert "generada" in answer.lower() or "generado" in answer.lower()


def test_strip_generated_file_body_removes_fences():
    raw = "```python\nprint('hi')\n```"
    assert strip_generated_file_body(raw) == "print('hi')"


@pytest.mark.asyncio
async def test_api_query_file_write_pending_tool(tmp_path, monkeypatch):
    """POST /api/query queues write_file via fast path; confirm writes the file."""
    from httpx import ASGITransport, AsyncClient

    from ui.tray.server import app, app_state

    files_dir = tmp_path / "files"
    files_dir.mkdir()
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(files_dir))

    registry_tools = {}
    from core.tools.registry import ToolRegistry

    reg = ToolRegistry()
    register_filesystem_tools(
        reg,
        authorized_read_paths=[str(files_dir)],
        authorized_write_paths=[str(files_dir)],
    )
    registry_tools = reg.handlers()

    store = AgentStateStore(state_dir=str(tmp_path / "agent_state"))
    state = store.load("general-v1")
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.model_id = MagicMock(return_value="test-model")
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)
    mock_registry.primary_name = "mock"

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=MagicMock(_short_term=MagicMock()),
        tool_registry=registry_tools,
        tool_definitions=reg.definitions(),
    )
    runtime._context_builder._short_term.push_message = MagicMock()
    runtime.save_conversation_session = MagicMock()

    from core.agents.conversation_store import ConversationStore
    from core.observability.response_meta import MetricsCollector

    app_state.runtime = runtime
    app_state.conv_store = ConversationStore(str(tmp_path / "convs"))
    app_state.metrics = MetricsCollector()
    app_state._pending_tools = {}
    app_state.provider_registry = mock_registry

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/query",
            json={
                "question": "Write a file called test-cerebro.txt with the word hello",
                "agent": "general-v1",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["pending_tool"]["name"] == "write_file"
        conv_id = body["conversation_id"]
        target = files_dir / "test-cerebro.txt"
        assert not target.exists()

        confirm = await client.post(
            "/api/tool-confirm",
            json={"conversation_id": conv_id, "decision": "approve"},
        )
        assert confirm.status_code == 200
        assert target.exists()
        assert target.read_text() == "hello"
        assert "Archivo escrito en:" in confirm.json()["answer"]
