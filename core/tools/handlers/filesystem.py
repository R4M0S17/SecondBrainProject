from __future__ import annotations

import ast
import subprocess
from datetime import datetime
from pathlib import Path

from core.i18n.messages import _L
from loguru import logger

READ_FILE_MAX_BYTES = 8192
SEARCH_FILES_MAX_LINE_CHARS = 200
SEARCH_FILES_MAX_SCAN_FOR_CONTENT = 250
SEARCH_FILES_CONTENT_READ_BYTES = 256 * 1024

_SKIP_SEARCH_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        ".cursor",
        "htmlcov",
    }
)
_READ_TRUNCATION_HINT = (
    "[Archivo truncado: {shown}/{total} bytes. "
    "Pídeme una sección específica con read_file_range si necesitas más.]"
)


class PathNotAuthorizedError(Exception):
    """Raised when a filesystem tool targets a path outside authorized roots."""

    def __init__(
        self,
        path: str,
        authorized_paths: list[str],
        *,
        operation: str = "acceder",
    ) -> None:
        self.path = path
        self.authorized_paths = [str(Path(p).expanduser().resolve()) for p in authorized_paths]
        self.operation = operation
        roots = ", ".join(self.authorized_paths) or "(ninguna ruta configurada)"
        super().__init__(
            f"No puedo {operation} a '{path}'. "
            f"Solo está permitido dentro de: {roots}. "
            f"Mueve la petición a una de esas carpetas o amplía "
            f"CEREBRO_AUTHORIZED_WRITE_PATHS / CEREBRO_AUTHORIZED_READ_PATHS."
        )


def validate_path(path: str, authorized_paths: list[str]) -> bool:
    """Return True if path resolves to within any of the authorized_paths."""
    resolved = Path(path).resolve()
    for auth in authorized_paths:
        try:
            resolved.relative_to(Path(auth).resolve())
            return True
        except ValueError:
            continue
    return False


def _require_authorized_path(
    path: str,
    authorized_paths: list[str],
    *,
    operation: str,
) -> None:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(path, authorized_paths, operation=operation)


def read_file(path: str, authorized_paths: list[str]) -> str:
    """
    Read entire file content (up to READ_FILE_MAX_BYTES).
    Safe: validates path authorization + handles encoding errors.
    """
    _require_authorized_path(path, authorized_paths, operation="leer")
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        raw = p.read_bytes()
    except OSError as exc:
        logger.error("read_file OSError: {}", exc)
        return f"Error reading file: {exc}"

    total = len(raw)
    if total <= READ_FILE_MAX_BYTES:
        return raw.decode("utf-8", errors="replace")

    text = raw[:READ_FILE_MAX_BYTES].decode("utf-8", errors="replace")
    hint = _READ_TRUNCATION_HINT.format(shown=READ_FILE_MAX_BYTES, total=total)
    return f"{text}\n{hint}"


def read_file_range(
    path: str,
    authorized_paths: list[str],
    start_byte: int = 0,
    end_byte: int | None = None,
) -> str:
    """
    Read a specific byte range from a file (useful for large files).

    Args:
        path: File path
        authorized_paths: List of authorized root paths
        start_byte: Start offset (default: 0)
        end_byte: End offset (default: start + MAX_BYTES). If None, reads from start to end.

    Returns:
        Text content or error message
    """
    _require_authorized_path(path, authorized_paths, operation="leer")
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"

    try:
        raw = p.read_bytes()
    except OSError as exc:
        logger.error("read_file_range OSError: {}", exc)
        return f"Error reading file: {exc}"

    total = len(raw)

    # Validate range
    if start_byte < 0 or start_byte >= total:
        return f"Error: start_byte {start_byte} out of range [0, {total})"

    if end_byte is None:
        end_byte = min(start_byte + READ_FILE_MAX_BYTES, total)
    elif end_byte > total:
        end_byte = total
    elif end_byte <= start_byte:
        return f"Error: end_byte {end_byte} must be > start_byte {start_byte}"

    chunk = raw[start_byte:end_byte]
    text = chunk.decode("utf-8", errors="replace")

    # Show range info
    header = f"[Bytes {start_byte:,}–{end_byte:,} of {total:,}]\n"

    if end_byte < total:
        hint = (
            f"\n[Truncado: mostrando {end_byte - start_byte:,} de {total - start_byte:,} bytes restantes. "
            f"Usa read_file_range con start_byte={end_byte} para obtener más.]"
        )
        return header + text + hint

    return header + text


def write_file(path: str, content: str, authorized_paths: list[str]) -> str:
    p = Path(path).expanduser()
    # If the model/tool sends a relative path (e.g. "nota.txt"), place it inside
    # the first authorized root so "create file without path" works again.
    if not p.is_absolute() and authorized_paths:
        p = Path(authorized_paths[0]) / p.name
    _require_authorized_path(str(p), authorized_paths, operation="escribir en")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        logger.info("write_file: wrote {} bytes to {}", len(content), path)
        resolved = str(p.resolve())
        return f"Archivo escrito en: {resolved} ({len(content)} bytes)"
    except OSError as exc:
        logger.error("write_file failed: {}", exc)
        return f"Error: no se pudo escribir en {path}: {exc}"


def create_directory(path: str, authorized_paths: list[str]) -> bool:
    _require_authorized_path(path, authorized_paths, operation="crear directorio en")
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.info("create_directory: {}", path)
        return True
    except OSError as exc:
        logger.error("create_directory failed: {}", exc)
        return False


def list_directory(path: str, authorized_paths: list[str]) -> list[str]:
    _require_authorized_path(path, authorized_paths, operation="listar")
    p = Path(path)
    if not p.exists():
        return []
    if not p.is_dir():
        return [str(p)]
    return [str(child) for child in sorted(p.iterdir())]


def _normalize_glob_pattern(pattern: str) -> str:
    """Turn a bare name like ``report`` into ``*report*`` for rglob."""
    p = (pattern or "*").strip()
    if not p:
        return "*"
    if any(ch in p for ch in "*?[]"):
        return p
    return f"*{p}*"


def _normalize_extension(extension: str | None) -> str | None:
    if not extension:
        return None
    ext = extension.strip().lower()
    if not ext:
        return None
    return ext if ext.startswith(".") else f".{ext}"


def _path_in_skipped_tree(path: Path) -> bool:
    return any(part in _SKIP_SEARCH_DIRS for part in path.parts)


def _format_search_line(path: Path) -> str:
    try:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = stat.st_size / 1024
        line = f"{path}  ({size_kb:.1f} KB, modificado {modified})"
    except OSError:
        line = str(path)
    if len(line) > SEARCH_FILES_MAX_LINE_CHARS:
        return line[: SEARCH_FILES_MAX_LINE_CHARS - 3] + "..."
    return line


def _search_roots(
    authorized_paths: list[str],
    base_path: str | None,
) -> list[Path]:
    if base_path:
        root = Path(base_path).expanduser().resolve()
        _require_authorized_path(str(root), authorized_paths, operation="buscar en")
        return [root]
    return [Path(p).expanduser().resolve() for p in authorized_paths]


def _collect_name_matches(
    roots: list[Path],
    *,
    pattern: str,
    authorized_paths: list[str],
    extension: str | None,
    name_contains: str | None,
) -> list[Path]:
    glob_pat = _normalize_glob_pattern(pattern)
    name_lower = name_contains.lower() if name_contains else None
    ext = _normalize_extension(extension)
    found: list[Path] = []

    for root in roots:
        if not root.exists():
            continue
        if not root.is_dir():
            if root.is_file() and validate_path(str(root), authorized_paths):
                found.append(root)
            continue
        try:
            candidates = root.rglob(glob_pat)
        except OSError:
            continue
        for path in candidates:
            if not path.is_file():
                continue
            if _path_in_skipped_tree(path):
                continue
            if ext and path.suffix.lower() != ext:
                continue
            if name_lower and name_lower not in path.name.lower():
                continue
            if not validate_path(str(path), authorized_paths):
                continue
            found.append(path)
    return found


def _filter_by_content(paths: list[Path], query_text: str, *, max_hits: int) -> list[Path]:
    needle = query_text.strip().lower()
    if not needle:
        return paths
    hits: list[Path] = []
    scanned = 0
    for path in paths:
        if len(hits) >= max_hits:
            break
        if scanned >= SEARCH_FILES_MAX_SCAN_FOR_CONTENT:
            break
        scanned += 1
        try:
            blob = path.read_bytes()[:SEARCH_FILES_CONTENT_READ_BYTES]
        except OSError:
            continue
        if needle in blob.decode("utf-8", errors="ignore").lower():
            hits.append(path)
    return hits


def search_files(
    pattern: str,
    authorized_paths: list[str],
    base_path: str | None = None,
    extension: str | None = None,
    max_results: int = 20,
    name_contains: str | None = None,
    query_text: str | None = None,
) -> str:
    """Search authorized folders by glob, name substring, extension, and optional text inside files."""
    if not authorized_paths:
        return "Error: no hay carpetas autorizadas para lectura (CEREBRO_AUTHORIZED_READ_PATHS)."

    roots = _search_roots(authorized_paths, base_path)
    missing = [str(r) for r in roots if not r.exists()]
    if missing and len(missing) == len(roots):
        return f"Directorio no encontrado: {missing[0]}"

    existing_roots = [r for r in roots if r.exists()]
    if not existing_roots:
        return f"Directorio no encontrado: {roots[0]}"

    roots_label = ", ".join(str(r) for r in existing_roots)
    cap = max(1, min(int(max_results), 100))

    matches = _collect_name_matches(
        existing_roots,
        pattern=pattern,
        authorized_paths=authorized_paths,
        extension=extension,
        name_contains=name_contains,
    )

    if query_text and query_text.strip():
        matches = _filter_by_content(matches, query_text, max_hits=cap * 3)

    def _mtime_key(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    matches.sort(key=_mtime_key, reverse=True)
    total_found = len(matches)
    shown = matches[:cap]
    lines = [_format_search_line(p) for p in shown]

    if not lines:
        parts = [_L("filesystem.search_filter_pattern", value=pattern)]
        if name_contains:
            parts.append(_L("filesystem.search_filter_name", value=name_contains))
        if extension:
            parts.append(_L("filesystem.search_filter_extension", value=extension))
        if query_text and query_text.strip():
            parts.append(_L("filesystem.search_filter_text", value=query_text.strip()))
        detail = ", ".join(parts)
        return _L("filesystem.not_found", detail=detail, roots_label=roots_label)

    header = ""
    if total_found > len(shown):
        header = _L("filesystem.showing_results", shown=len(shown), total=total_found, cap=cap)
    return header + "\n".join(lines)


def create_python_file(filename: str, code: str, authorized_paths: list[str]) -> str:
    if not filename.endswith(".py"):
        return (
            "Error: create_python_file requires a .py filename. "
            "Use write_file for plain-text targets."
        )
    if "/" in filename or "\\" in filename:
        return "Error: filename must not contain path separators"
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return f"Error: code is not valid Python ({exc.msg} at line {exc.lineno})"
    base = Path(authorized_paths[0]).expanduser().resolve()
    dest = base / filename
    _require_authorized_path(str(dest), authorized_paths, operation="escribir en")
    try:
        base.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")
        logger.info("create_python_file: wrote {} to {}", filename, dest)
        return f"Python file created: {dest}"
    except OSError as exc:
        return f"Error creating file: {exc}"


def delete_file(path: str, authorized_paths: list[str]) -> str:
    _require_authorized_path(path, authorized_paths, operation="eliminar")
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a regular file: {path}"
    try:
        # Move to Trash instead of hard delete (safer on macOS)
        subprocess.run(
            ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{p}"'],
            check=True,
            capture_output=True,
        )
        logger.info("delete_file: moved {} to Trash", p)
        return f"File moved to Trash: {p}"
    except subprocess.CalledProcessError as exc:
        return f"Error deleting file: {exc.stderr.decode().strip() or exc}"
