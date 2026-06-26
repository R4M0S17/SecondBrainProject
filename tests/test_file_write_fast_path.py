"""Tests for file-write fast path (Problem A — deterministic write_file routing)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.file_content_generator import strip_generated_file_body
from core.agents.file_write_fast_path import (
    classify_file_content,
    extract_fenced_code,
    is_content_specification,
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


def test_classify_recipe_description_as_spec():
    body, source, spec = classify_file_content(
        "una receta de pizza casera con masa fina, para 2 personas",
        "receta.txt",
    )
    assert source == "spec"
    assert "receta" in spec.lower()
    assert body == spec


def test_classify_truth_table_as_spec():
    assert is_content_specification(
        "una tabla de la verdad para matematica discreta", "truthtable.txt"
    )
    _, source, spec = classify_file_content(
        "en donde escribas una tabla de la verdad para matematica discreta",
        "truthtable.txt",
    )
    assert source == "spec"
    assert "tabla" in spec.lower()
    assert not spec.lower().startswith("en donde")


def test_classify_playstation_games_as_spec():
    assert is_content_specification("3 videojuegos de playstation", "juegos.txt")
    _, source, _ = classify_file_content("3 videojuegos de playstation", "juegos.txt")
    assert source == "spec"


def test_classify_invented_names_as_spec():
    assert is_content_specification("solamente 3 nombres de mujer inventados", "prueba.txt")


def test_parse_curly_quoted_filename(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo “prueba.txt” con solamente 3 nombres de mujer inventados",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "prueba.txt"
    assert intent.content_source == "spec"


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


def test_parse_spanish_create_file_loose_without_contenido_keyword(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo pruebapython.txt con un a funcion con recursion de la sisecion de fibonacci",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "pruebapython.txt"
    assert "fibonacci" in intent.content.lower()
    assert intent.content_source == "spec"


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


def test_parse_spanish_create_file_with_el_contenido_de_curly_quotes(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo nota_escritorio_cerebro.txt con el contenido de “hola desde escritorio cerebro”",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "nota_escritorio_cerebro.txt"
    assert "hola desde escritorio cerebro" in intent.content.lower()
    assert intent.path == str((tmp_path / "nota_escritorio_cerebro.txt").resolve())


def test_parse_spanish_create_file_with_el_contenido_de_plain_quotes(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        'crea un archivo nota_escritorio_cerebro.txt con el contenido de "hola desde escritorio cerebro"',
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "nota_escritorio_cerebro.txt"
    assert "hola desde escritorio cerebro" in intent.content.lower()
    assert intent.path == str((tmp_path / "nota_escritorio_cerebro.txt").resolve())


def test_parse_spanish_create_file_calendar_without_contenido_keyword(tmp_path):
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo calendarioprueba.txt con los 3 proximos cumpleaños en mi calendario",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "calendarioprueba.txt"
    # The parser should at least capture the calendar intent as part of the extracted content.
    assert "cumple" in intent.content.lower()


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,needle",
    [
        (
            "crea un archivo truthtable.txt con una tabla de la verdad para matematica discreta",
            "tabla",
        ),
        (
            "crea un archivo juegos.txt con 3 videojuegos de playstation",
            "playstation",
        ),
    ],
)
@pytest.mark.asyncio
async def test_runtime_generates_content_for_manual_fail_cases(
    tmp_path, monkeypatch, query, needle
):
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    generated_body = (
        "p | q | p AND q\n" "F | F | F\n"
        if "truthtable" in query
        else "God of War\nHorizon Zero Dawn\nSpider-Man"
    )
    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value=generated_body)
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

    answer, final_state = await runtime.run(query, agent_id)
    assert final_state.pending_tool_name == "write_file"
    written = final_state.pending_tool_args["content"]
    if "truthtable" in query:
        mock_chat.complete.assert_called_once()
        assert "en donde escribas" not in written.lower()
        assert "|" in written or "AND" in written
    else:
        # Uses heuristic fallback — no LLM call.
        mock_chat.complete.assert_not_called()
        assert written.strip() not in ("", "3 videojuegos de playstation")
        assert "\n" in written
    assert "generad" in answer.lower()


@pytest.mark.asyncio
async def test_runtime_generates_content_for_spec_loose_spanish(tmp_path, monkeypatch):
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
        "crea un archivo pruebapython.txt con un a funcion con recursion de la sisecion de fibonacci",
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


def test_parse_spanish_create_file_without_filename_auto_generates_name(tmp_path):
    """'crea un archivo con 3 nombres de hombre inventados' should NOT capture 'con' as filename."""
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo con 3 nombres de hombre inventados",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename != "con", "Should not use 'con' as filename"
    assert intent.filename in ("nombres.txt", "nombres_3.txt", "hombres.txt", "inventados.txt"), (
        f"Expected auto-generated filename, got '{intent.filename}'"
    )
    assert intent.content_source == "spec"


def test_parse_spanish_create_file_with_invalid_filename_rejected(tmp_path):
    """Common Spanish stop words like 'con', 'por', 'para' should not become filenames."""
    roots = [str(tmp_path)]
    for stop_word in ("con", "por", "para", "sin", "del", "que"):
        intent = parse_file_write_intent(
            f"crea un archivo {stop_word} 3 nombres inventados",
            write_roots=roots,
        )
        assert intent is not None, f"Should still match for stop_word='{stop_word}'"
        assert intent.filename != stop_word, (
            f"Should not use '{stop_word}' as filename"
        )


def test_parse_spanish_create_file_explicit_name_with_con_in_content(tmp_path):
    """Explicit filenames should still work even when they contain 'con'."""
    roots = [str(tmp_path)]
    intent = parse_file_write_intent(
        "crea un archivo lista_con_nombres.txt con 3 nombres de hombre inventados",
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "lista_con_nombres.txt"


def test_strip_generated_file_body_removes_json_action_answer():
    """JSON {'action': 'answer', 'answer': '...'} envelope should be stripped."""
    raw = '{"action": "answer", "answer": "Liam\\nNoah\\nOliver"}'
    result = strip_generated_file_body(raw)
    assert result == "Liam\nNoah\nOliver"


def test_strip_generated_file_body_removes_json_tool_with_content():
    """JSON {'action': 'tool', 'tool': 'write_file', 'args': {'content': '...'}} should strip."""
    raw = '{"action": "tool", "tool": "write_file", "args": {"path": "x.txt", "content": "Liam\\nNoah\\nOliver"}}'
    result = strip_generated_file_body(raw)
    assert result == "Liam\nNoah\nOliver"  # json.loads unescapes \\n → \n


def test_strip_generated_file_body_json_with_newlines():
    """JSON with literal \\n inside strings should decode properly."""
    raw = '{"action": "answer", "answer": "Liam\\nNoah\\nOliver"}'
    result = strip_generated_file_body(raw)
    assert result == "Liam\nNoah\nOliver"


# ----- heuristic fallback tests -----

def test_fallback_4_female_names():
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("4 nombres de mujer")
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 4
    assert all(isinstance(n, str) and len(n) > 0 for n in lines)


def test_fallback_3_male_names():
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("3 nombres de hombre inventados")
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 3


def test_fallback_5_playstation_games():
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("5 videojuegos de playstation")
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 4  # capped at available items


def test_fallback_recipe_pizza():
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("una receta de pizza")
    assert result is not None
    assert any("harina" in line.lower() for line in result.split("\n"))


def test_fallback_not_triggered_for_code():
    from core.agents.file_content_generator import _try_fallback
    assert _try_fallback("un programa python usando recursion fibonacci") is None


def test_fallback_lasagna_recipe():
    """'receta de lasagna' should produce a complete recipe with ingredients."""
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("una receta de lasagna")
    assert result is not None
    assert "lasagna" in result.lower() or "lasaña" in result.lower()
    assert any(w in result.lower() for w in ("ingrediente", "carne", "horno"))


def test_fallback_generic_recipe():
    """'receta de pollo al horno' should produce a generic recipe template."""
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("una receta de pollo al horno")
    assert result is not None
    assert "pollo al horno" in result.lower()
    assert "ingredientes" in result.lower()


@pytest.mark.asyncio
async def test_runtime_file_write_fast_path_lasagna_no_llm(tmp_path, monkeypatch):
    """'crea un archivo receta.txt con una receta de lasagna' should use fallback."""
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    mock_chat = MagicMock()
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
        "crea un archivo receta.txt con una receta de lasagna",
        agent_id,
    )
    mock_chat.complete.assert_not_called()
    assert final_state.pending_tool_name == "write_file"
    content = final_state.pending_tool_args["content"]
    assert "lasagna" in content.lower()
    assert "receta.txt" in final_state.pending_tool_args["path"]
    assert "generad" in answer.lower()


def test_fallback_2_invented_names():
    from core.agents.file_content_generator import _try_fallback
    result = _try_fallback("2 nombres inventados")
    assert result is not None
    lines = result.split("\n")
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_runtime_file_write_fast_path_female_names_no_llm(tmp_path, monkeypatch):
    """'crea un archivo con 4 nombres de mujer' should use fallback, not LLM."""
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["write_file"]
    store.save(state)

    mock_chat = MagicMock()
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
        "crea un archivo con 4 nombres de mujer",
        agent_id,
    )
    # Should NOT call the LLM — heuristic fallback kicks in.
    mock_chat.complete.assert_not_called()
    assert final_state.pending_tool_name == "write_file"
    content = final_state.pending_tool_args["content"]
    lines = content.strip().split("\n")
    assert len(lines) == 4, f"Expected 4 names, got {len(lines)}: {content}"
    assert all(len(name) > 0 for name in lines)
    assert "nombres" in final_state.pending_tool_args["path"].lower() or \
           "mujer" in final_state.pending_tool_args["path"].lower()
    assert "generad" in answer.lower()
