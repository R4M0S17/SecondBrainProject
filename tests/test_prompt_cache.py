from pathlib import Path

from core.inference.prompt_cache import (
    prompt_cache_fingerprint,
    prompt_cache_path,
    sync_prompt_cache,
)


def test_prompt_cache_fingerprint_stable_for_same_input():
    fp1 = prompt_cache_fingerprint("system", ["b", "a"])
    fp2 = prompt_cache_fingerprint("system", ["a", "b"])
    assert fp1 == fp2


def test_prompt_cache_fingerprint_changes_when_tools_change():
    base = prompt_cache_fingerprint("system", ["read_file"])
    changed = prompt_cache_fingerprint("system", ["read_file", "write_file"])
    assert base != changed


def test_sync_prompt_cache_deletes_stale_cache(tmp_path, monkeypatch):
    cache = tmp_path / "chat.cache"
    sidecar = tmp_path / "chat.cache.sha256"
    cache.write_text("stale", encoding="utf-8")
    sidecar.write_text("old-hash", encoding="utf-8")
    monkeypatch.setenv("CEREBRO_PROMPT_CACHE_PATH", str(cache))

    sync_prompt_cache("new system", ["tool_a"])

    assert not cache.exists()
    assert sidecar.read_text(encoding="utf-8") == prompt_cache_fingerprint("new system", ["tool_a"])


def test_sync_prompt_cache_keeps_cache_when_fingerprint_matches(tmp_path, monkeypatch):
    cache = tmp_path / "chat.cache"
    sidecar = tmp_path / "chat.cache.sha256"
    fp = prompt_cache_fingerprint("system", ["tool_a"])
    cache.write_text("warm", encoding="utf-8")
    sidecar.write_text(fp, encoding="utf-8")
    monkeypatch.setenv("CEREBRO_PROMPT_CACHE_PATH", str(cache))

    sync_prompt_cache("system", ["tool_a"])

    assert cache.read_text(encoding="utf-8") == "warm"


def test_default_prompt_cache_path_points_at_chat_profile():
    assert prompt_cache_path() == Path("bin/cache/chat.cache")


def test_prompt_cache_fingerprint_ignores_dynamic_date_line():
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from core.agents.runtime import _build_system_prompt
    from core.agents.state_store import AgentProfile, AgentState
    from core.memory.context_builder import AssembledContext

    now = datetime.now(UTC).isoformat()
    state = AgentState(
        profile=AgentProfile(
            id="t",
            name="Test",
            domain_tags=[],
            authorized_tools=["read_file"],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="summary A",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )
    ctx = AssembledContext(
        session_history=[],
        retrieved_memory=[],
        retrieved_documents=[],
        agent_summary="",
        total_tokens_estimated=0,
        sources_used=[],
    )
    t1 = datetime(2026, 5, 19, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    t2 = datetime(2026, 5, 19, 16, 0, 0, tzinfo=ZoneInfo("America/New_York"))

    from unittest.mock import patch

    with patch("core.agents.runtime._now_human") as mock_human:
        from core.agents.runtime import _now_human as real_now_human

        mock_human.side_effect = [real_now_human(t1), real_now_human(t2)]
        p1 = _build_system_prompt(state, ctx, [])
        p2 = _build_system_prompt(state, ctx, [])

    fp1 = prompt_cache_fingerprint(p1, ["read_file"], model_id="llama.gguf")
    fp2 = prompt_cache_fingerprint(p2, ["read_file"], model_id="llama.gguf")
    assert fp1 == fp2


def test_prompt_cache_fingerprint_changes_with_model_id():
    fp_a = prompt_cache_fingerprint("system", ["a"], model_id="model-a.gguf")
    fp_b = prompt_cache_fingerprint("system", ["a"], model_id="model-b.gguf")
    assert fp_a != fp_b
