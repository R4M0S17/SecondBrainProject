"""Tests for Module 12 — Config & Security Layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.loader import ConfigError, load_settings
from config.security import validate_path

# ──────────────────────────────────────────────────────────────────────────────
# load_settings — happy path
# ──────────────────────────────────────────────────────────────────────────────


def test_load_settings_default_path_succeeds():
    settings = load_settings()
    assert isinstance(settings, dict)


def test_load_settings_returns_all_required_sections():
    settings = load_settings()
    for section in (
        "general",
        "inference",
        "ingestion",
        "memory",
        "tools",
        "ui",
        "scheduler",
        "security",
    ):
        assert section in settings, f"Missing section: [{section}]"


def test_load_settings_values_have_correct_types():
    settings = load_settings()
    assert isinstance(settings["inference"]["timeout_seconds"], int)
    assert isinstance(settings["ingestion"]["chunk_size"], int)
    assert isinstance(settings["ingestion"]["watched_paths"], list)
    assert isinstance(settings["scheduler"]["do_not_disturb"], bool)
    assert isinstance(settings["security"]["max_file_size_mb"], int)


def test_load_settings_from_explicit_path(tmp_path: Path):
    p = tmp_path / "custom.toml"
    p.write_text('[general]\napp_name = "TestApp"\nlanguage = "en"\n')

    settings = load_settings(str(p))

    assert settings["general"]["app_name"] == "TestApp"
    assert settings["general"]["language"] == "en"


def test_load_settings_empty_toml_returns_empty_dict(tmp_path: Path):
    p = tmp_path / "empty.toml"
    p.write_text("")

    assert load_settings(str(p)) == {}


def test_load_settings_nested_values(tmp_path: Path):
    p = tmp_path / "nested.toml"
    p.write_text('[ingestion]\nchunk_size = 256\nwatched_paths = ["/tmp", "/home"]\n')
    settings = load_settings(str(p))

    assert settings["ingestion"]["chunk_size"] == 256
    assert settings["ingestion"]["watched_paths"] == ["/tmp", "/home"]


# ──────────────────────────────────────────────────────────────────────────────
# load_settings — error cases
# ──────────────────────────────────────────────────────────────────────────────


def test_load_settings_missing_file_raises_config_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(str(tmp_path / "nonexistent.toml"))


def test_load_settings_invalid_toml_raises_config_error(tmp_path: Path):
    p = tmp_path / "bad.toml"
    p.write_text("[invalid toml !!!")

    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_settings(str(p))


def test_config_error_is_exception_subclass():
    exc = ConfigError("test")
    assert isinstance(exc, Exception)


# ──────────────────────────────────────────────────────────────────────────────
# validate_path — accepts authorized paths
# ──────────────────────────────────────────────────────────────────────────────


def test_validate_path_accepts_child_of_watched(tmp_path: Path):
    child = str(tmp_path / "notes" / "doc.md")
    assert validate_path(child, [str(tmp_path)]) is True


def test_validate_path_accepts_exact_watched_dir(tmp_path: Path):
    assert validate_path(str(tmp_path), [str(tmp_path)]) is True


def test_validate_path_accepts_deeply_nested_path(tmp_path: Path):
    deep = str(tmp_path / "a" / "b" / "c" / "d" / "file.txt")
    assert validate_path(deep, [str(tmp_path)]) is True


def test_validate_path_accepts_one_of_multiple_watched(tmp_path: Path):
    dir_a = str(tmp_path / "a")
    dir_b = str(tmp_path / "b")
    path_in_b = str(tmp_path / "b" / "file.txt")
    assert validate_path(path_in_b, [dir_a, dir_b]) is True


# ──────────────────────────────────────────────────────────────────────────────
# validate_path — rejects unauthorized paths
# ──────────────────────────────────────────────────────────────────────────────


def test_validate_path_rejects_path_outside_watched(tmp_path: Path):
    allowed = str(tmp_path / "allowed")
    outside = str(tmp_path / "secret" / "credentials.txt")
    assert validate_path(outside, [allowed]) is False


def test_validate_path_rejects_traversal_escape(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    escaped = str(allowed / ".." / "secret")
    assert validate_path(escaped, [str(allowed)]) is False


def test_validate_path_empty_watched_returns_false(tmp_path: Path):
    assert validate_path(str(tmp_path / "file.txt"), []) is False


def test_validate_path_returns_false_when_no_watched_matches(tmp_path: Path):
    dir_a = str(tmp_path / "a")
    dir_b = str(tmp_path / "b")
    path_in_c = str(tmp_path / "c" / "file.txt")
    assert validate_path(path_in_c, [dir_a, dir_b]) is False


def test_validate_path_sibling_directory_rejected(tmp_path: Path):
    # /tmp/watched/ should NOT authorize /tmp/watched-secret/
    watched = str(tmp_path / "watched")
    sibling = str(tmp_path / "watched-secret" / "file.txt")
    assert validate_path(sibling, [watched]) is False
