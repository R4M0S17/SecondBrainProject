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
