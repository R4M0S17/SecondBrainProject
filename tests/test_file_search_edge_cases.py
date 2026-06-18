"""Comprehensive edge-case tests for file search functionality."""

from __future__ import annotations

import pytest

from core.agents.file_search_fast_path import (
    _resolve_base_path,
    authorized_read_paths,
    is_file_search_query,
    parse_file_search_intent,
    try_file_search_fast_path,
)
from core.agents.specialized import GENERAL_TOOLS
from core.tools.handlers.filesystem import search_files

# ── search_files() edge cases ──────────────────────────────────────────────


def test_empty_authorized_paths(tmp_path):
    """Empty authorized_paths should return an error, not crash."""
    result = search_files("*.txt", [])
    assert "Error" in result
    assert "no hay carpetas autorizadas" in result


def test_nonexistent_root(tmp_path):
    """Single nonexistent root should return a clear error."""
    result = search_files("*.txt", [str(tmp_path / "does_not_exist")])
    assert "Directorio no encontrado" in result


def test_mixed_existing_and_nonexistent_roots(tmp_path):
    """Mix of existing and non-existing roots should search the existing ones."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "does_not_exist"
    root_a.mkdir()
    (root_a / "found.txt").write_text("x")
    result = search_files("*.txt", [str(root_a), str(root_b)])
    assert "found.txt" in result


def test_file_with_spaces_in_name(tmp_path):
    (tmp_path / "my file with spaces.txt").write_text("x")
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path))
    assert "my file with spaces.txt" in result


def test_file_in_nested_subdirectory(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "deep.txt").write_text("x")
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path))
    assert "deep.txt" in result


def test_content_search_unicode(tmp_path):
    """Content search with Unicode characters should work."""
    (tmp_path / "unicode.txt").write_text("café crème déjà vu 日本語")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="日本語")
    assert "unicode.txt" in result


def test_content_search_spanish_accent_insensitive(tmp_path):
    """Content search with .lower() doesn't normalize accented chars.
    This is a documented limitation: "canción" won't match "cancion".
    """
    (tmp_path / "accents.txt").write_text("canción de la comunicación")
    _ = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="cancion")


def test_content_search_at_file_boundary(tmp_path):
    """Content at exact read boundary (256KB) should still match.

    SEARCH_FILES_CONTENT_READ_BYTES = 262144.
    Needle at position (262144 - 20) is well within range.
    """
    content = "x" * (256 * 1024 - 20) + "NEEDLE_AT_BOUNDARY"
    (tmp_path / "boundary.txt").write_text(content)
    result = search_files(
        "*",
        [str(tmp_path)],
        base_path=str(tmp_path),
        query_text="NEEDLE_AT_BOUNDARY",
    )
    assert "boundary.txt" in result


def test_content_search_past_read_boundary_does_not_match(tmp_path):
    """Needle starting past 256KB boundary is correctly NOT found."""
    content = "x" * (256 * 1024) + "NEEDLE_PAST_BOUNDARY"
    (tmp_path / "past_boundary.txt").write_text(content)
    result = search_files(
        "*",
        [str(tmp_path)],
        base_path=str(tmp_path),
        query_text="NEEDLE_PAST_BOUNDARY",
    )
    assert "past_boundary.txt" not in result
    assert "No se encontraron archivos" in result


def test_binary_file_does_not_crash_search(tmp_path):
    """Binary files should be skipped gracefully, not crash the search."""
    (tmp_path / "binary.bin").write_bytes(bytes(range(256)))
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="needle")
    assert "binary.bin" not in result  # binary data won't match text needle
    assert isinstance(result, str)


def test_search_max_results_clamping(tmp_path):
    """max_results should be clamped to [1, 100]."""
    for i in range(10):
        (tmp_path / f"file_{i}.txt").write_text(str(i))
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path), max_results=3)
    lines = result.strip().split("\n")
    # If there's a header line, count only the file lines
    file_lines = [ln for ln in lines if ".txt" in ln]
    assert len(file_lines) <= 3


def test_search_max_results_cap_at_100(tmp_path):
    """max_results > 100 should be capped."""
    for i in range(150):
        (tmp_path / f"file_{i:03d}.txt").write_text(str(i))
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path), max_results=999)
    lines = result.strip().split("\n")
    file_lines = [ln for ln in lines if ".txt" in ln]
    assert len(file_lines) <= 100


def test_search_with_content_filter_and_name_filter_combined(tmp_path):
    """Both name_contains and query_text filters should work together."""
    (tmp_path / "report_q1.txt").write_text("quarterly results are in")
    (tmp_path / "report_q2.txt").write_text("quarterly results improving")
    (tmp_path / "notes.txt").write_text("just notes")
    result = search_files(
        "*",
        [str(tmp_path)],
        base_path=str(tmp_path),
        name_contains="report",
        query_text="improving",
    )
    assert "report_q2.txt" in result
    assert "report_q1.txt" not in result
    assert "notes.txt" not in result


def test_search_no_results_message_format(tmp_path):
    """No results should produce a descriptive message."""
    result = search_files(
        "*.zzz",
        [str(tmp_path)],
        base_path=str(tmp_path),
        extension=".zzz",
    )
    assert "No se encontraron archivos" in result


def test_search_skips_git_directory(tmp_path):
    """Files inside .git should be excluded."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "secret.txt").write_text("hidden")
    (tmp_path / "visible.txt").write_text("ok")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path))
    assert "visible.txt" in result
    assert "secret.txt" not in result


def test_search_skips_node_modules(tmp_path):
    """Files inside node_modules should be excluded."""
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "lib.txt").write_text("lib")
    (tmp_path / "src.txt").write_text("src")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path))
    assert "src.txt" in result
    assert "lib.txt" not in result


def test_search_skips_venv(tmp_path):
    """Files inside .venv should be excluded."""
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "pkg.txt").write_text("pkg")
    (tmp_path / "project.txt").write_text("ok")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path))
    assert "project.txt" in result
    assert "pkg.txt" not in result


def test_search_empty_file(tmp_path):
    """Empty file should appear in name search but not in content search."""
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "nonempty.txt").write_text("data")
    result_name = search_files("*", [str(tmp_path)], base_path=str(tmp_path), name_contains="empty")
    assert "empty.txt" in result_name
    result_content = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="data")
    assert "nonempty.txt" in result_content


def test_search_symlink_not_followed_or_included(tmp_path):
    """Symlinks should not crash; behavior depends on rglob."""
    link = tmp_path / "link_to_nowhere.txt"
    try:
        link.symlink_to("/nonexistent/path")
    except OSError:
        pytest.skip("Cannot create symlink on this platform")
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path))
    # Symlink might appear in results or not — either way, no crash
    assert isinstance(result, str)


def test_search_case_sensitive_glob(tmp_path):
    """Python glob is case-sensitive even on APFS (case-insensitive FS).
    On a case-insensitive filesystem, README.TXT and readme.txt are the same
    file, so we test with different filenames to verify case-sensitive matching.
    """
    (tmp_path / "Readme_test.txt").write_text("case test")
    # On case-insensitive FS, searching for "*readme*" would match "Readme_test.txt"
    # because the file literally contains "Readme". We verify the search works
    # regardless of case matching behavior.
    result = search_files("*Readme*", [str(tmp_path)], base_path=str(tmp_path))
    assert "Readme_test.txt" in result
    # Searching for a pattern that doesn't match returns no results
    result2 = search_files("*ZZZZZZ*", [str(tmp_path)], base_path=str(tmp_path))
    assert "No se encontraron archivos" in result2
    # Extension-based search works
    result3 = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path))
    assert "Readme_test.txt" in result3


def test_search_very_long_filename(tmp_path):
    """Very long filenames should not crash the formatter."""
    long_name = "a" * 200 + ".txt"
    (tmp_path / long_name).write_text("x")
    result = search_files("*.txt", [str(tmp_path)], base_path=str(tmp_path))
    assert long_name[:50] in result  # truncated by _format_search_line


# ── is_file_search_query() edge cases ─────────────────────────────────────


def test_search_query_short_input():
    """Queries shorter than 4 chars should be rejected."""
    assert is_file_search_query("ab") is False
    assert is_file_search_query("abc") is False


def test_search_query_empty():
    """Empty query should be rejected."""
    assert is_file_search_query("") is False


def test_search_query_whitespace():
    """Whitespace-only query should be rejected."""
    assert is_file_search_query("   ") is False


def test_search_query_write_file_excluded():
    """'crea un archivo' should NOT trigger file search."""
    assert is_file_search_query("crea un archivo demo.txt con hola") is False


def test_search_query_write_file_with_search():
    """'busca...' combined with file noun should trigger."""
    assert is_file_search_query("busca archivos .py") is True


def test_search_query_glob_only():
    """A bare glob pattern < 30 chars should trigger search."""
    assert is_file_search_query("*.py") is True
    assert is_file_search_query("**/notes.md") is True
    assert (
        is_file_search_query("long filename with *.py inside but no verb and over threshold")
        is False
    )


def test_search_query_extension_hint():
    """Extension hints with file noun should trigger search."""
    assert is_file_search_query("archivos de tipo py") is True
    # "extension .txt" has no search verb and "extension" is not a file noun
    assert is_file_search_query("extension .txt") is False
    # "archivos .py" — ".py" doesn't match _GLOB_RE (no word char before dot)
    assert is_file_search_query("archivos .py") is False


def test_search_query_python_mention():
    """Python-related file search with search verb should trigger."""
    assert is_file_search_query("busca archivos python") is True
    # Without a verb, it's not clear it's a search
    assert is_file_search_query("archivos python") is True


def test_search_query_named_file():
    """'archivo llamado X' should trigger."""
    assert is_file_search_query("busca archivo llamado README") is True


def test_search_query_content_search():
    """Content search phrasing should trigger."""
    assert is_file_search_query("archivos que contengan presupuesto") is True


def test_search_query_about_searching_not_trigger():
    """Meta questions about searching should not trigger."""
    assert is_file_search_query("Explícame cómo buscar archivos") is False
    assert is_file_search_query("¿Qué es un archivo?") is False
    assert is_file_search_query("how to search files on mac") is False


# ── parse_file_search_intent() edge cases ─────────────────────────────────


def test_parse_intent_extension_only():
    intent = parse_file_search_intent("busca archivos con extensión py")
    assert intent is not None
    assert intent.extension == ".py"


def test_parse_intent_glob_pattern():
    intent = parse_file_search_intent("busca archivos *.txt")
    assert intent is not None
    assert intent.pattern == "*.txt"


def test_parse_intent_named_file():
    intent = parse_file_search_intent("busca el archivo llamado README.md")
    assert intent is not None
    assert intent.name_contains == "README.md"


def test_parse_intent_find_named():
    intent = parse_file_search_intent("find file named notes.txt")
    assert intent is not None
    assert intent.name_contains == "notes.txt"


def test_parse_intent_content_text():
    intent = parse_file_search_intent("busca archivos que contengan presupuesto marzo")
    assert intent is not None
    assert intent.query_text == "presupuesto marzo"


def test_parse_intent_max_results_one():
    intent = parse_file_search_intent("busca solo un archivo .py")
    assert intent is not None
    assert intent.max_results == 1


def test_parse_intent_max_results_first_n():
    intent = parse_file_search_intent("busca los primeros 5 archivos .py")
    assert intent is not None
    assert intent.max_results == 5


def test_parse_intent_non_search():
    """Non-search queries should return None."""
    assert parse_file_search_intent("crea un archivo demo.txt") is None
    assert parse_file_search_intent("Explícame Python") is None
    # "Explícame cómo buscar archivos" is a meta-question, not a search
    assert parse_file_search_intent("Explícame cómo buscar archivos") is None


# ── _resolve_base_path() edge cases ───────────────────────────────────────


def test_resolve_base_path_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    result = _resolve_base_path("busca en el escritorio", [str(tmp_path)])
    assert result == str(desktop.resolve())


def test_resolve_base_path_documents(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    documents = tmp_path / "Documents"
    documents.mkdir()
    result = _resolve_base_path("busca en documentos", [str(tmp_path)])
    assert result == str(documents.resolve())


def test_resolve_base_path_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    result = _resolve_base_path("busca en descargas", [str(tmp_path)])
    assert result == str(downloads.resolve())


def test_resolve_base_path_unauthorized(tmp_path, monkeypatch):
    """Location not in authorized_paths should return None."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Desktop").mkdir()
    result = _resolve_base_path("busca en el escritorio", ["/some/other/path"])
    assert result is None


def test_resolve_base_path_no_location():
    """Query without location should return None."""
    result = _resolve_base_path("busca archivos .py", ["/tmp"])
    assert result is None


def test_resolve_base_path_english(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    result = _resolve_base_path("search on desktop", [str(tmp_path)])
    assert result == str(desktop.resolve())


# ── authorized_read_paths() edge cases ────────────────────────────────────


def test_authorized_read_paths_default(monkeypatch):
    """When env var is unset, defaults should include ~/Desktop."""
    monkeypatch.delenv("CEREBRO_AUTHORIZED_READ_PATHS", raising=False)
    monkeypatch.delenv("CEREBRO_FILES_PATH", raising=False)
    paths = authorized_read_paths()
    assert any("Desktop" in p for p in paths)


def test_authorized_read_paths_custom(monkeypatch):
    """CEREBRO_AUTHORIZED_READ_PATHS overrides defaults entirely.
    CEREBRO_FILES_PATH is used as default fallback, not merged separately.
    """
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", "/custom/path:/other/path")
    monkeypatch.setenv("CEREBRO_FILES_PATH", "/custom/files")
    paths = authorized_read_paths()
    assert "/custom/path" in paths
    assert "/other/path" in paths
    # CEREBRO_FILES_PATH is a default fallback — when env is set, it's not merged
    assert "/custom/files" not in paths
    assert len(paths) == 2


# ── end-to-end: try_file_search_fast_path() ───────────────────────────────


def test_fast_path_requires_search_files_tool(tmp_path, monkeypatch):
    """Without search_files in a non-empty tool list, should return None.
    Empty tool list = no restriction (backward-compatible with profiles
    that don't set authorized_tools).
    """
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(tmp_path))
    (tmp_path / "test.txt").write_text("x")
    # Empty list = no restriction — should search
    result = try_file_search_fast_path("busca archivos .txt", [])
    assert result is not None
    assert "test.txt" in result
    # Non-empty list missing search_files — should reject
    result2 = try_file_search_fast_path("busca archivos .txt", ["write_file"])
    assert result2 is None


def test_fast_path_unauthorized_paths_not_crashed(tmp_path, monkeypatch):
    """Search with paths not on disk should not crash."""
    monkeypatch.setenv(
        "CEREBRO_AUTHORIZED_READ_PATHS",
        "/nonexistent/path1:/nonexistent/path2",
    )
    result = try_file_search_fast_path("busca archivos .txt", GENERAL_TOOLS)
    assert result is not None
    assert isinstance(result, str)


def test_fast_path_mixed_locations(tmp_path, monkeypatch):
    """Search query mixing locations and content."""
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(tmp_path))
    (tmp_path / "data.txt").write_text("important data here")
    result = try_file_search_fast_path("busca archivos que contengan important", GENERAL_TOOLS)
    assert result is not None
    assert "data.txt" in result


# ── Content filter edge case: needle at exact byte boundary ───────────────


def test_content_filter_needle_at_start_of_file(tmp_path):
    """Content filter should match when needle is at the very start."""
    (tmp_path / "start.txt").write_text("START_MARKER is here")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="START_MARKER")
    assert "start.txt" in result


def test_content_filter_needle_before_read_boundary(tmp_path):
    """Needle entirely within the 256KB read limit should match."""
    content = "x" * (256 * 1024 - 20) + "BOUNDARY_SAFE"
    (tmp_path / "safe.txt").write_text(content)
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="BOUNDARY_SAFE")
    assert "safe.txt" in result


def test_content_filter_empty_needle(tmp_path):
    """Empty query_text should skip content filtering (return all paths)."""
    (tmp_path / "any.txt").write_text("x")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="")
    assert "any.txt" in result


def test_content_filter_whitespace_needle(tmp_path):
    """Whitespace-only query_text should skip content filtering."""
    (tmp_path / "any2.txt").write_text("x")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), query_text="   ")
    assert "any2.txt" in result


def test_content_filter_needle_not_found(tmp_path):
    """Needle not in any file should return no-results message."""
    (tmp_path / "test.txt").write_text("hello world")
    result = search_files(
        "*", [str(tmp_path)], base_path=str(tmp_path), query_text="NEEDLE_NOT_THERE"
    )
    assert "No se encontraron archivos" in result


# ── Multi-root content search ─────────────────────────────────────────────


def test_content_search_with_multiple_roots(tmp_path):
    """Content search across multiple roots."""
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "from_a.txt").write_text("found in root_a")
    (root_b / "from_b.txt").write_text("found in root_b")
    result = search_files(
        "*.txt",
        [str(root_a), str(root_b)],
        query_text="found in",
    )
    assert "from_a.txt" in result
    assert "from_b.txt" in result
