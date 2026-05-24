from __future__ import annotations

import ast
import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger

READ_FILE_MAX_BYTES = 8192
SEARCH_FILES_MAX_LINE_CHARS = 200
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
    _require_authorized_path(path, authorized_paths, operation="leer")
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return f"Error reading file: {exc}"
    total = len(raw)
    if total <= READ_FILE_MAX_BYTES:
        return raw.decode("utf-8", errors="replace")
    text = raw[:READ_FILE_MAX_BYTES].decode("utf-8", errors="replace")
    hint = _READ_TRUNCATION_HINT.format(shown=READ_FILE_MAX_BYTES, total=total)
    return f"{text}\n{hint}"


def write_file(path: str, content: str, authorized_paths: list[str]) -> str:
    _require_authorized_path(path, authorized_paths, operation="escribir en")
    p = Path(path)
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


def search_files(
    pattern: str,
    authorized_paths: list[str],
    base_path: str | None = None,
    extension: str | None = None,
    max_results: int = 20,
) -> str:
    """Recursively search for files matching pattern within authorized paths.

    Returns formatted list with size and modification date for each match.
    """
    start = Path(base_path or authorized_paths[0]).expanduser().resolve()
    _require_authorized_path(str(start), authorized_paths, operation="buscar en")
    if not start.exists():
        return f"Directory not found: {start}"

    ext = extension.lower() if extension else None
    matches: list[str] = []
    for p in start.rglob(pattern):
        if not p.is_file():
            continue
        if ext and p.suffix.lower() != ext:
            continue
        if not validate_path(str(p), authorized_paths):
            continue
        try:
            stat = p.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            size_kb = stat.st_size / 1024
            line = f"{p}  ({size_kb:.1f} KB, modified {modified})"
            if len(line) > SEARCH_FILES_MAX_LINE_CHARS:
                line = line[: SEARCH_FILES_MAX_LINE_CHARS - 3] + "..."
            matches.append(line)
        except OSError:
            line = str(p)
            if len(line) > SEARCH_FILES_MAX_LINE_CHARS:
                line = line[: SEARCH_FILES_MAX_LINE_CHARS - 3] + "..."
            matches.append(line)
        if len(matches) >= max_results:
            break

    if not matches:
        return f"No files found matching '{pattern}' in {start}"
    return "\n".join(matches)


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
